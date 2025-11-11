# auth_service/middleware.py

import json
import time
import logging
import jwt

from django.conf import settings
from django.db import connection, transaction, IntegrityError
from django.http import JsonResponse
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin

from django_tenants.middleware import TenantMainMiddleware
from django_tenants.utils import get_public_schema_name

from core.models import Domain, Tenant, UsernameIndex
from users.models import PasswordResetToken, RSAKeyPair, UserActivity

from auth_service.utils.cache import get_cache_key, get_from_cache, set_to_cache

logger = logging.getLogger(__name__)


class ActivityLoggingMiddleware:
    """
    Middleware to log all HTTP requests/responses for activity tracking.
    Integrated into CustomTenantMiddleware's process_response.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Capture start time and meta
        request._activity_start = time.time()
        request._activity_meta = {
            'method': request.method,
            'path': request.path,
            'query_params': dict(request.GET),
            'ip': request.META.get('REMOTE_ADDR'),
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
        }

        response = self.get_response(request)

        # Log on response
        if hasattr(request, '_activity_start'):
            self._log_activity(request, response)

        return response

    def _log_activity(self, request, response):
        duration = time.time() - request._activity_start
        user = getattr(request, 'user', None)
        tenant = getattr(user, 'tenant', None) if user else None

        def _create_log():
            details = {
                'status_code': response.status_code,
                'duration_ms': round(duration * 1000, 2),
                **request._activity_meta,
            }
            # Sanitize sensitive data (e.g., passwords in POST)
            # if request.method == 'POST':
            #     body = request.body.decode('utf-8') if request.body else '{}'
            #     try:
            #         post_data = json.loads(body)
            #         # Mask sensitive fields
            #         if 'password' in post_data:
            #             post_data['password'] = '[REDACTED]'
            #         if 'token' in post_data:
            #             post_data['token'] = '[REDACTED]'
            #         details['post_data'] = post_data
            #     except json.JSONDecodeError:
            #         details['post_data'] = '[Invalid JSON]'

            # Infer action from path (customize for your app)
            path = request.path
            inferred_action = 'api_request'
            if '/withdrawals/' in path:
                inferred_action = 'withdrawal_requested' if request.method == 'POST' else 'withdrawal_updated'
            elif '/investments/' in path:
                inferred_action = 'investment_created' if request.method == 'POST' else 'investment_updated'
            elif '/profile/' in path:
                inferred_action = 'profile_updated'
            # Add more inferences as needed

            # UserActivity.objects.create(
            #     user=user,
            #     tenant=tenant,
            #     action=inferred_action,
            #     performed_by=user,
            #     details=details,
            #     success=(response.status_code < 400),
            # )

        transaction.on_commit(_create_log)




class EnhancedActivityLoggingMiddleware(MiddlewareMixin):
    """
    Enhanced middleware to capture ALL user interactions with comprehensive logging
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.excluded_paths = [
            '/admin/', '/static/', '/media/', '/health/',
            '/api/user/user-activities/',  # Avoid recursion
            '/api/docs/', '/api/schema/',  # Documentation endpoints
        ]
        self.sensitive_fields = ['password', 'token', 'secret', 'key', 'authorization']
    
    def __call__(self, request):
        # Skip logging for excluded paths
        if any(request.path.startswith(path) for path in self.excluded_paths):
            return self.get_response(request)
        
        # Capture request details
        start_time = time.time()
        response = self.get_response(request)
        duration = time.time() - start_time
        
        # Log the activity asynchronously
        self._log_http_activity(request, response, duration)
        
        return response
    

    def _log_http_activity(self, request, response, duration):
        """Log all HTTP requests as activities"""
        try:
            user = getattr(request, 'user', None)
            tenant = getattr(request, 'tenant', None)
            
            # Only log authenticated requests or important public endpoints
            if tenant and (user and user.is_authenticated or self._should_log_public_request(request)):
                action = self._infer_action_type(request, response)
                details = self._build_activity_details(request, response, duration)
                
                # Calculate success based on status code
                success = response.status_code < 400
                
                # Use transaction.on_commit to avoid blocking the request
                transaction.on_commit(
                    lambda: self._create_activity_record(
                        request, action, details, success  # Only pass 4 arguments
                    )
                )
                
        except Exception as e:
            logger.error(f"Error logging activity: {str(e)}", exc_info=True)


    def _create_activity_record(self, request, action, details, success=None):
        """Create the actual activity record with proper error handling"""
        try:
            user = None
            performed_by = None
            
            # CRITICAL FIX: Get tenant at the START, not inside conditional blocks
            tenant = getattr(request, 'tenant', None)
            
            # If no tenant on request, skip activity logging
            if not tenant:
                logger.debug(f"No tenant found for activity record: {action}")
                return
            
            # For login actions, try to extract user from request data
            if action == 'login' and success:
                # Extract user identifier from request data
                request_data = details.get('request_data', {})
                email = request_data.get('email')
                username = request_data.get('username')
                
                if email or username:
                    try:
                        from users.models import CustomUser
                        from django_tenants.utils import tenant_context
                        
                        with tenant_context(tenant):
                            if email:
                                user = CustomUser.objects.filter(email=email).first()
                            elif username:
                                user = CustomUser.objects.filter(username=username).first()
                            
                            if user:
                                performed_by = user
                    except Exception as e:
                        logger.warning(f"Could not find user for login activity: {e}")
            
            # For non-login actions, use the standard logic
            elif hasattr(request, 'user') and request.user.is_authenticated:
                user = request.user
                performed_by = request.user
            
            # Create the activity record (tenant is now guaranteed to be set)
            UserActivity.objects.create(
                user=user,
                tenant=tenant,
                action=action,
                performed_by=performed_by,
                details=details,
                ip_address=self._get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                success=success
            )
                
        except Exception as e:
            logger.error(f"Error creating activity record: {e}")




    def _should_log_public_request(self, request):
        """Determine if we should log public requests"""
        public_paths_to_log = [
            '/api/user/password/reset/',
            '/api/user/public-register/',
            '/api/token/',
            '/api/login/',
        ]
        return any(request.path.startswith(path) for path in public_paths_to_log)
    
    def _infer_action_type(self, request, response):
        """Map HTTP requests to meaningful action types"""
        method = request.method
        path = request.path.lower()
        
        # Authentication endpoints
        if '/token/' in path or '/login/' in path:
            return 'login' if response.status_code < 400 else 'login_failed'
        
        if '/password/reset/' in path:
            if 'confirm' in path:
                return 'password_reset_confirm'
            return 'password_reset_request'
        
        if '/logout/' in path:
            return 'logout'
        
        # User management
        if '/users/' in path:
            if method == 'POST': 
                if 'bulk' in path:
                    return 'bulk_user_create'
                return 'user_created'
            if method in ['PUT', 'PATCH']: 
                return 'user_updated'
            if method == 'DELETE': 
                return 'user_deleted'
        
        # Client management
        if '/clients/' in path:
            if method == 'POST': return 'user_created'
            if method in ['PUT', 'PATCH']: return 'user_updated'
            if method == 'DELETE': return 'user_deleted'
        
        # Document management
        if '/documents/' in path:
            if method == 'POST': return 'document_uploaded'
            if method in ['PUT', 'PATCH']: return 'document_updated'
            if method == 'DELETE': return 'document_deleted'
            if 'acknowledge' in path: return 'document_acknowledged'
            if 'permissions' in path: return 'document_permission_granted'
        
        # Investment management
        if '/investments/' in path:
            if method == 'POST': return 'investment_created'
            if method in ['PUT', 'PATCH']: return 'investment_updated'
        
        # Withdrawal management
        if '/withdrawals/' in path:
            if method == 'POST': return 'withdrawal_requested'
            if 'approve' in path: return 'withdrawal_approved'
            if 'reject' in path: return 'withdrawal_rejected'
        
        # Group management
        if '/groups/' in path:
            if method == 'POST': return 'group_created'
            if method in ['PUT', 'PATCH']: return 'group_updated'
            if method == 'DELETE': return 'group_deleted'
            if 'members' in path: 
                if method == 'POST': return 'group_member_added'
                if method == 'DELETE': return 'group_member_removed'
        
        # System operations
        if '/keys/' in path and method == 'POST':
            return 'rsa_key_created'
        
        if '/terms-and-conditions/' in path and method == 'POST':
            return 'terms_accepted'
        
        # Default to API request
        return 'api_request'
    
    def _build_activity_details(self, request, response, duration):
        """Build comprehensive activity details while sanitizing sensitive data"""
        details = {
            'method': request.method,
            'path': request.path,
            'status_code': response.status_code,
            'duration_ms': round(duration * 1000, 2),
            'query_params': self._sanitize_data(dict(request.GET)),
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
        }
        
        # Add request data for non-GET requests (sanitized)
        if request.method in ['POST', 'PUT', 'PATCH']:
            post_data = self._extract_post_data(request)
            details['request_data'] = self._sanitize_data(post_data)
        
        # Add response data for errors
        if response.status_code >= 400:
            try:
                response_data = json.loads(response.content.decode('utf-8'))
                details['error_details'] = self._sanitize_data(response_data)
            except:
                details['error_details'] = 'Unable to parse response'
        
        return details
    


    def _extract_post_data(self, request):
        """Extract POST data from request without consuming the stream"""
        try:
            # First try request.data (for DRF requests)
            if hasattr(request, 'data') and request.data:
                return request.data
            
            # For multipart/form-data
            if request.content_type == 'multipart/form-data' and request.POST:
                return dict(request.POST)
            
            # For JSON requests - check if we can safely read the body
            if request.content_type == 'application/json':
                # If body has already been read, we can't read it again
                if hasattr(request, '_body') and request._body:
                    try:
                        body = request._body
                        if isinstance(body, bytes):
                            body = body.decode('utf-8')
                        return json.loads(body) if body.strip() else {}
                    except:
                        return {'note': 'body_previously_consumed'}
                else:
                    # Try to read body if it hasn't been consumed
                    try:
                        if request.body:
                            return json.loads(request.body.decode('utf-8'))
                    except:
                        pass
            
            return {}
        except Exception as e:
            logger.debug(f"Could not extract POST data: {str(e)}")
            return {}


    def _sanitize_data(self, data):
        """Remove sensitive information from data"""
        if isinstance(data, dict):
            sanitized = {}
            for key, value in data.items():
                if any(sensitive in key.lower() for sensitive in self.sensitive_fields):
                    sanitized[key] = '[REDACTED]'
                else:
                    sanitized[key] = self._sanitize_data(value)
            return sanitized
        elif isinstance(data, list):
            return [self._sanitize_data(item) for item in data]
        else:
            return data
    

    def _get_client_ip(self, request):
        """Extract client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

 

class CustomTenantMiddleware(TenantMainMiddleware):
    def __init__(self, get_response):
        # Integrate ActivityLoggingMiddleware
        self.activity_middleware = ActivityLoggingMiddleware(get_response)
        super().__init__(self.activity_middleware)

    def process_request(self, request):
        try:
            host = request.get_host()
        except Exception as e:
            host = f"Invalid host: {e}"
        logger.info(f"Processing request: {request.method} {request.path}, Host: {host}")

        # Updated public paths (ADDED /api/logout/)
        public_paths = [
            '/api/docs/', '/api/schema/', '/api/token/refresh/',
            '/api/token/', '/api/login/', '/api/logout/',  # Exact for token/login, added logout
            '/api/social/callback/', '/api/admin/create/',
            '/api/applications-engine/applications/parse-resume/application/autofil/',
            '/api/talent-engine/requisitions/by-link/',
            '/api/user/public-register/',
            '/api/reviews/public/submit/',
        ]

        # Handle password reset request by email domain (similar to login)
        if request.path.startswith('/api/user/password/reset/') and request.method == 'POST':
            try:
                body = request.body.decode('utf-8') if request.body else '{}'
                logger.debug(f"Password reset request body: {body}")
                data = json.loads(body)
                email = data.get('email')
                if not email:
                    logger.error("No email provided in password reset request")
                    return JsonResponse({'error': 'Email is required'}, status=400)

                email_domain = email.split('@')[1]
                logger.debug(f"Password reset email domain: {email_domain}")
                domain = Domain.objects.filter(domain=email_domain).first()
                if not domain:
                    logger.error(f"No domain found for email domain: {email_domain}")
                    return JsonResponse({'error': f'No tenant found for email domain: {email_domain}'}, status=404)

                request.tenant = domain.tenant
                connection.set_schema(domain.tenant.schema_name)
                logger.info(f"Set tenant schema for password reset: {domain.tenant.schema_name}")

                # NEW: Tenant suspension check
                if request.tenant.status == 'suspended':
                    logger.warning(f"Access denied to suspended tenant for password reset: {request.tenant.schema_name}")
                    return JsonResponse({
                        'detail': 'Tenant account is currently suspended.',
                        'status': 'suspended',
                        'message': 'Your organization\'s account has been temporarily suspended due to administrative reasons. All access is restricted until reactivation.',
                        'support': 'Please contact your organization administrator or support team at support@yourcompany.com for assistance with reactivation.',
                        'timestamp': timezone.now().isoformat()
                    }, status=503)

                return
            except (ValueError, IndexError) as e:
                logger.error(f"Invalid email format in password reset: {str(e)}")
                return JsonResponse({'error': 'Invalid email format'}, status=400)
            except (KeyError, json.JSONDecodeError) as e:
                logger.error(f"Error processing password reset request: {str(e)}")
                return JsonResponse({'error': 'Invalid request format'}, status=400)

        # Handle password reset confirmation by token
        if request.path.startswith('/api/user/password/reset/confirm/') and request.method == 'POST':
            try:
                body = request.body.decode('utf-8') if request.body else '{}'
                data = json.loads(body)
                token = data.get('token')
                if not token:
                    logger.error("No token provided in password reset confirm request")
                    return JsonResponse({'error': 'Token is required'}, status=400)

                # Look up reset token to determine tenant
                reset_token = PasswordResetToken.objects.select_related('tenant').filter(token=token).first()
                if not reset_token:
                    logger.error(f"Invalid or missing reset token: {token}")
                    return JsonResponse({'error': 'Invalid or missing token'}, status=400)

                request.tenant = reset_token.tenant
                connection.set_schema(reset_token.tenant.schema_name)
                logger.info(f"Set tenant schema for reset token: {reset_token.tenant.schema_name}")

                # NEW: Tenant suspension check
                if request.tenant.status == 'suspended':
                    logger.warning(f"Access denied to suspended tenant for password reset confirm: {request.tenant.schema_name}")
                    return JsonResponse({
                        'detail': 'Tenant account is currently suspended.',
                        'status': 'suspended',
                        'message': 'Your organization\'s account has been temporarily suspended due to administrative reasons. All access is restricted until reactivation.',
                        'support': 'Please contact your organization administrator or support team at support@yourcompany.com for assistance with reactivation.',
                        'timestamp': timezone.now().isoformat()
                    }, status=503)

                return
            except (ValueError, KeyError, json.JSONDecodeError) as e:
                logger.error(f"Error processing reset token request: {str(e)}")
                return JsonResponse({'error': 'Invalid request format'}, status=400)

        # FIXED: Handle login/token endpoints with EXACT path matching (excludes /refresh/)
        if (request.path in ['/api/token/', '/api/login/', '/api/verify-2fa/'] or 
            request.path.startswith('/api/login/') or 
            request.path.startswith('/api/verify-2fa/')) and request.method == 'POST':
            try:
                body = request.body.decode('utf-8') if request.body else '{}'
                logger.debug(f"Request body: {body}")
                data = json.loads(body)
                
                # Check for email first (existing logic)
                email = data.get('email')
                if email:
                    email_domain = email.split('@')[1]
                    logger.debug(f"Email domain: {email_domain}")
                    domain = Domain.objects.filter(domain=email_domain).first()
                    if not domain:
                        logger.error(f"No domain found for email domain: {email_domain}")
                        return JsonResponse({'error': f'No tenant found for email domain: {email_domain}'}, status=404)
                    request.tenant = domain.tenant
                    connection.set_schema(domain.tenant.schema_name)
                    logger.info(f"Set tenant schema for email domain {email_domain}: {domain.tenant.schema_name}")
                    with connection.cursor() as cursor:
                        cursor.execute("SHOW search_path;")
                        logger.debug(f"Current search_path: {cursor.fetchone()[0]}")

                    # NEW: Tenant suspension check
                    if request.tenant.status == 'suspended':
                        logger.warning(f"Access denied to suspended tenant for login: {request.tenant.schema_name}")
                        return JsonResponse({
                            'detail': 'Tenant account is currently suspended.',
                            'status': 'suspended',
                            'message': 'Your organization\'s account has been temporarily suspended due to administrative reasons. All access is restricted until reactivation.',
                            'support': 'Please contact your organization administrator or support team at support@yourcompany.com for assistance with reactivation.',
                            'timestamp': timezone.now().isoformat()
                        }, status=503)
                    
                    return
                
                # UPDATED: For username-only, resolve tenant from UsernameIndex
                username = data.get('username')
                if username:
                    logger.info(f"🔐 Username login attempt: {username}")
                    
                    # Look up tenant from global UsernameIndex
                    try:
                        index_entry = UsernameIndex.objects.get(username=username)
                        target_tenant = index_entry.tenant
                        logger.info(f"✅ Resolved username '{username}' to tenant: {target_tenant.schema_name}")
                        
                        request.tenant = target_tenant
                        connection.set_schema(target_tenant.schema_name)
                        logger.info(f"Set tenant schema for username '{username}': {target_tenant.schema_name}")
                        
                        with connection.cursor() as cursor:
                            cursor.execute("SHOW search_path;")
                            logger.debug(f"Current search_path: {cursor.fetchone()[0]}")

                        # NEW: Tenant suspension check
                        if request.tenant.status == 'suspended':
                            logger.warning(f"Access denied to suspended tenant for username login: {request.tenant.schema_name}")
                            return JsonResponse({
                                'detail': 'Tenant account is currently suspended.',
                                'status': 'suspended',
                                'message': 'Your organization\'s account has been temporarily suspended due to administrative reasons. All access is restricted until reactivation.',
                                'support': 'Please contact your organization administrator or support team at support@yourcompany.com for assistance with reactivation.',
                                'timestamp': timezone.now().isoformat()
                            }, status=503)
                        
                        return
                        
                    except UsernameIndex.DoesNotExist:
                        logger.error(f"❌ No UsernameIndex found for username: {username}")
                        
                        # Fallback to hostname-based resolution if username not found
                        hostname = host.split(':')[0]  # Strip port
                        if hostname == '0.0.0.0':
                            hostname = 'localhost'
                        
                        domain_key = get_cache_key('public', 'domain', hostname)
                        domain = get_from_cache(domain_key)
                        if domain is None:
                            domain = Domain.objects.filter(domain=hostname).first()
                            if domain:
                                set_to_cache(domain_key, domain, timeout=600)  # 10 min cache
                            else:
                                logger.error(f"No domain found for hostname: {hostname}")
                                return JsonResponse({'error': f'No tenant found for hostname: {hostname}'}, status=404)
                        
                        request.tenant = domain.tenant
                        connection.set_schema(domain.tenant.schema_name)
                        logger.info(f"Set tenant schema for username fallback (hostname {hostname}): {domain.tenant.schema_name}")
                        with connection.cursor() as cursor:
                            cursor.execute("SHOW search_path;")
                            logger.debug(f"Current search_path: {cursor.fetchone()[0]}")

                        # NEW: Tenant suspension check
                        if request.tenant.status == 'suspended':
                            logger.warning(f"Access denied to suspended tenant for username fallback: {request.tenant.schema_name}")
                            return JsonResponse({
                                'detail': 'Tenant account is currently suspended.',
                                'status': 'suspended',
                                'message': 'Your organization\'s account has been temporarily suspended due to administrative reasons. All access is restricted until reactivation.',
                                'support': 'Please contact your organization administrator or support team at support@yourcompany.com for assistance with reactivation.',
                                'timestamp': timezone.now().isoformat()
                            }, status=503)
                        
                        return
                    
                else:
                    logger.error("No email or username provided in login request")
                    return JsonResponse({'error': 'Email or username is required'}, status=400)
                    
            except (ValueError, IndexError) as e:
                logger.error(f"Invalid format in login: {str(e)}")
                return JsonResponse({'error': 'Invalid email/username format'}, status=400)
            except (KeyError, json.JSONDecodeError) as e:
                logger.error(f"Error processing login/token request: {str(e)}")
                return JsonResponse({'error': 'Invalid request format'}, status=400)

        # Public paths handling with caching (now reached for /refresh/ and /logout/)
        if any(request.path.startswith(path) for path in public_paths):
            public_key = get_cache_key('public', 'tenant')
            public_tenant = get_from_cache(public_key)
            if public_tenant is None:
                try:
                    public_tenant = Tenant.objects.get(schema_name=get_public_schema_name())
                    set_to_cache(public_key, public_tenant, timeout=3600)  # Cache public tenant for 1 hour
                except Tenant.DoesNotExist:
                    logger.error("Public tenant does not exist")
                    return JsonResponse({'error': 'Public tenant not configured'}, status=404)
            request.tenant = public_tenant
            connection.set_schema(public_tenant.schema_name)
            logger.info(f"Set public schema for path: {public_tenant.schema_name}")
            return

        # JWT authentication with tenant schema from unverified payload
        try:
            auth_header = request.headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
                # Extract tenant_id and tenant_schema from unverified JWT
                unverified_payload = jwt.decode(token, options={"verify_signature": False})
                tenant_id = unverified_payload.get("tenant_id")
                tenant_schema = unverified_payload.get("tenant_schema")
                logger.info(f"Unverified JWT: tenant_id={tenant_id}, tenant_schema={tenant_schema}")

                if tenant_id and tenant_schema:
                    try:
                        tenant = Tenant.objects.get(id=tenant_id, schema_name=tenant_schema)
                        request.tenant = tenant
                        connection.set_schema(tenant.schema_name)
                        logger.info(f"Set tenant schema from JWT: {tenant.schema_name}")

                        # NEW: Tenant suspension check
                        if request.tenant.status == 'suspended':
                            logger.warning(f"Access denied to suspended tenant via JWT: {request.tenant.schema_name}")
                            return JsonResponse({
                                'detail': 'Tenant account is currently suspended.',
                                'status': 'suspended',
                                'message': 'Your organization\'s account has been temporarily suspended due to administrative reasons. All access is restricted until reactivation.',
                                'support': 'Please contact your organization administrator or support team at support@yourcompany.com for assistance with reactivation.',
                                'timestamp': timezone.now().isoformat()
                            }, status=503)

                    except Tenant.DoesNotExist:
                        logger.error(f"Tenant not found: id={tenant_id}, schema={tenant_schema}")
                        return JsonResponse({'error': 'Invalid tenant'}, status=404)

                # Now validate JWT with correct schema set
                unverified_header = jwt.get_unverified_header(token)
                kid = unverified_header.get("kid")
                if not kid:
                    logger.error("No 'kid' header in JWT")
                    return JsonResponse({'error': 'Invalid token key'}, status=401)

                # Use cached RSAKeyPair lookup
                keypair = RSAKeyPair.get_active_by_kid(kid, request.tenant if hasattr(request, 'tenant') else Tenant.objects.first())
                if not keypair:
                    logger.error(f"No RSAKeyPair found for kid={kid} in schema={connection.schema_name}")
                    return JsonResponse({'error': 'Invalid token key'}, status=401)

                tenant = keypair.tenant
                request.tenant = tenant
                connection.set_schema(tenant.schema_name)
                logger.info(f"Set tenant schema from RSAKeyPair: {tenant.schema_name}")

                # NEW: Tenant suspension check
                if request.tenant.status == 'suspended':
                    logger.warning(f"Access denied to suspended tenant via RSAKeyPair: {request.tenant.schema_name}")
                    return JsonResponse({
                        'detail': 'Tenant account is currently suspended.',
                        'status': 'suspended',
                        'message': 'Your organization\'s account has been temporarily suspended due to administrative reasons. All access is restricted until reactivation.',
                        'support': 'Please contact your organization administrator or support team at support@yourcompany.com for assistance with reactivation.',
                        'timestamp': timezone.now().isoformat()
                    }, status=503)

                return
        except jwt.InvalidTokenError as e:
            logger.error(f"JWT decode failed: {str(e)}")
            return JsonResponse({'error': 'Invalid token'}, status=401)
        except Exception as e:
            logger.error(f"JWT authentication failed: {str(e)}")
            return JsonResponse({'error': f'JWT error: {str(e)}'}, status=401)

        # Fallback to hostname with caching
        try:
            hostname = request.get_host().split(':')[0]
            if hostname == '0.0.0.0':
                hostname = 'localhost'
        except Exception as e:
            logger.error(f"Error getting host: {str(e)}")
            hostname = 'localhost'

        domain_key = get_cache_key('public', 'domain', hostname)
        domain = get_from_cache(domain_key)
        if domain is None:
            domain = Domain.objects.filter(domain=hostname).first()
            if domain:
                set_to_cache(domain_key, domain, timeout=600)  # Cache domain for 10 minutes
        if domain:
            request.tenant = domain.tenant
            connection.set_schema(domain.tenant.schema_name)
            logger.info(f"Set tenant schema from hostname: {domain.tenant.schema_name}")

            # NEW: Tenant suspension check
            if request.tenant.status == 'suspended':
                logger.warning(f"Access denied to suspended tenant via hostname: {request.tenant.schema_name}")
                return JsonResponse({
                    'detail': 'Tenant account is currently suspended.',
                    'status': 'suspended',
                    'message': 'Your organization\'s account has been temporarily suspended due to administrative reasons. All access is restricted until reactivation.',
                    'support': 'Please contact your organization administrator or support team at support@yourcompany.com for assistance with reactivation.',
                    'timestamp': timezone.now().isoformat()
                }, status=503)

            return

        # Enhanced dev fallback (create 'example' tenant via migration if needed)
        if hostname in ['127.0.0.1', 'localhost', '0.0.0.0']:
            try:
                tenant = Tenant.objects.get(schema_name='example')
                request.tenant = tenant
                connection.set_schema(tenant.schema_name)
                logger.info(f"Set dev tenant schema: {tenant.schema_name}")

                # NEW: Tenant suspension check (dev tenant should not be suspended, but check anyway)
                if request.tenant.status == 'suspended':
                    logger.warning(f"Access denied to suspended dev tenant: {request.tenant.schema_name}")
                    return JsonResponse({
                        'detail': 'Tenant account is currently suspended.',
                        'status': 'suspended',
                        'message': 'Your organization\'s account has been temporarily suspended due to administrative reasons. All access is restricted until reactivation.',
                        'support': 'Please contact your organization administrator or support team at support@yourcompany.com for assistance with reactivation.',
                        'timestamp': timezone.now().isoformat()
                    }, status=503)

                return
            except Tenant.DoesNotExist:
                logger.warning("Dev 'example' tenant missing—create via ./manage.py migrate_schemas --shared")

        logger.error(f"No tenant found for hostname: {hostname}")
        return JsonResponse({'error': f'No tenant found for hostname: {hostname}'}, status=404)