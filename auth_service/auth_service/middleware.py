

# # from django_tenants.middleware import TenantMainMiddleware
# # from django_tenants.utils import get_public_schema_name
# # from core.models import Domain, Tenant
# # from users.models import PasswordResetToken, RSAKeyPair
# # from django.http import JsonResponse
# # from django.db import connection
# # import logging
# # import json
# # import jwt

# # logger = logging.getLogger(__name__)

# # class CustomTenantMiddleware(TenantMainMiddleware):
# #     def process_request(self, request):
# #         try:
# #             host = request.get_host()
# #         except Exception as e:
# #             host = f"Invalid host: {e}"
# #         logger.info(f"Processing request: {request.method} {request.path}, Host: {host}")

# #         # Public paths (excluding /api/token/)
# #         public_paths = [
# #             '/api/docs/', '/api/schema/', '/api/token/refresh/',
# #             '/api/social/callback/', '/api/admin/create/',
# #             '/api/user/password/reset/', '/api/user/password/reset/confirm/',
# #             '/api/applications-engine/applications/parse-resume/application/autofil/',
# #             '/api/talent-engine/requisitions/by-link/',
# #         ]

# #         if any(request.path.startswith(path) for path in public_paths):
# #             try:
# #                 public_tenant = Tenant.objects.get(schema_name=get_public_schema_name())
# #                 request.tenant = public_tenant
# #                 connection.set_schema(public_tenant.schema_name)
# #                 logger.info(f"Set public schema for path: {public_tenant.schema_name}")
# #                 return
# #             except Tenant.DoesNotExist:
# #                 logger.error("Public tenant does not exist")
# #                 return JsonResponse({'error': 'Public tenant not configured'}, status=404)

# #         # Handle /api/token/, /api/login/, or /api/verify-2fa/ for email-based tenant resolution
# #         if (request.path.startswith('/api/token/') or 
# #             request.path.startswith('/api/login/') or 
# #             request.path.startswith('/api/verify-2fa/')) and request.method == 'POST':
# #             try:
# #                 body = request.body.decode('utf-8') if request.body else '{}'
# #                 logger.debug(f"Request body: {body}")
# #                 data = json.loads(body)
# #                 email = data.get('email')
# #                 if not email:
# #                     logger.error("No email provided in login/token request")
# #                     return JsonResponse({'error': 'Email is required'}, status=400)

# #                 email_domain = email.split('@')[1]
# #                 logger.debug(f"Email domain: {email_domain}")
# #                 domain = Domain.objects.filter(domain=email_domain).first()
# #                 if not domain:
# #                     logger.error(f"No domain found for email domain: {email_domain}")
# #                     return JsonResponse({'error': f'No tenant found for email domain: {email_domain}'}, status=404)

# #                 request.tenant = domain.tenant
# #                 connection.set_schema(domain.tenant.schema_name)
# #                 logger.info(f"Set tenant schema for email domain {email_domain}: {domain.tenant.schema_name}")
# #                 with connection.cursor() as cursor:
# #                     cursor.execute("SHOW search_path;")
# #                     logger.debug(f"Current search_path: {cursor.fetchone()[0]}")
# #                 return
# #             except (ValueError, KeyError, json.JSONDecodeError) as e:
# #                 logger.error(f"Error processing login/token request: {str(e)}")
# #                 return JsonResponse({'error': 'Invalid request format'}, status=400)

# #         # Handle password reset confirmation
# #         if request.path.startswith('/api/user/password/reset/confirm/') and request.method == 'POST':
# #             try:
# #                 body = request.body.decode('utf-8') if request.body else '{}'
# #                 data = json.loads(body)
# #                 token = data.get('token')
# #                 if not token:
# #                     logger.error("No token provided in password reset confirm request")
# #                     return JsonResponse({'error': 'Token is required'}, status=400)

# #                 reset_token = PasswordResetToken.objects.filter(token=token).first()
# #                 if not reset_token:
# #                     logger.error(f"Invalid or missing reset token: {token}")
# #                     return JsonResponse({'error': 'Invalid or missing token'}, status=400)

# #                 request.tenant = reset_token.tenant
# #                 connection.set_schema(reset_token.tenant.schema_name)
# #                 logger.info(f"Set tenant schema for reset token: {reset_token.tenant.schema_name}")
# #                 return
# #             except (ValueError, KeyError, json.JSONDecodeError) as e:
# #                 logger.error(f"Error processing reset token request: {str(e)}")
# #                 return JsonResponse({'error': 'Invalid request format'}, status=400)

# #         # Try JWT authentication with tenant schema from unverified payload
# #         try:
# #             auth_header = request.headers.get('Authorization', '')
# #             if auth_header.startswith('Bearer '):
# #                 token = auth_header.split(' ')[1]
# #                 # Extract tenant_id and tenant_schema from unverified JWT
# #                 unverified_payload = jwt.decode(token, options={"verify_signature": False})
# #                 tenant_id = unverified_payload.get("tenant_id")
# #                 tenant_schema = unverified_payload.get("tenant_schema")
# #                 logger.info(f"Unverified JWT: tenant_id={tenant_id}, tenant_schema={tenant_schema}")

# #                 if tenant_id and tenant_schema:
# #                     try:
# #                         tenant = Tenant.objects.get(id=tenant_id, schema_name=tenant_schema)
# #                         request.tenant = tenant
# #                         connection.set_schema(tenant.schema_name)
# #                         logger.info(f"Set tenant schema from JWT: {tenant.schema_name}")
# #                     except Tenant.DoesNotExist:
# #                         logger.error(f"Tenant not found: id={tenant_id}, schema={tenant_schema}")
# #                         return JsonResponse({'error': 'Invalid tenant'}, status=404)

# #                 # Now validate JWT with correct schema set
# #                 unverified_header = jwt.get_unverified_header(token)
# #                 kid = unverified_header.get("kid")
# #                 if not kid:
# #                     logger.error("No 'kid' header in JWT")
# #                     return JsonResponse({'error': 'Invalid token key'}, status=401)

# #                 keypair = RSAKeyPair.objects.filter(kid=kid, active=True).first()
# #                 if not keypair:
# #                     logger.error(f"No RSAKeyPair found for kid={kid} in schema={connection.schema_name}")
# #                     return JsonResponse({'error': 'Invalid token key'}, status=401)

# #                 tenant = keypair.tenant
# #                 request.tenant = tenant
# #                 connection.set_schema(tenant.schema_name)
# #                 logger.info(f"Set tenant schema from RSAKeyPair: {tenant.schema_name}")
# #                 return
# #         except jwt.InvalidTokenError as e:
# #             logger.error(f"JWT decode failed: {str(e)}")
# #             return JsonResponse({'error': 'Invalid token'}, status=401)
# #         except Exception as e:
# #             logger.error(f"JWT authentication failed: {str(e)}")
# #             return JsonResponse({'error': f'JWT error: {str(e)}'}, status=401)

# #         # Fallback to hostname
# #         try:
# #             hostname = request.get_host().split(':')[0]
# #             if hostname == '0.0.0.0':
# #                 hostname = 'localhost'
# #         except Exception as e:
# #             logger.error(f"Error getting host: {str(e)}")
# #             hostname = 'localhost'

# #         domain = Domain.objects.filter(domain=hostname).first()
# #         if domain:
# #             request.tenant = domain.tenant
# #             connection.set_schema(domain.tenant.schema_name)
# #             logger.info(f"Set tenant schema from hostname: {domain.tenant.schema_name}")
# #             return

# #         # Development fallback
# #         if hostname in ['127.0.0.1', 'localhost']:
# #             try:
# #                 tenant = Tenant.objects.get(schema_name='example')
# #                 request.tenant = tenant
# #                 connection.set_schema(tenant.schema_name)
# #                 logger.info(f"Set tenant schema for local development: {tenant.schema_name}")
# #                 return
# #             except Tenant.DoesNotExist:
# #                 logger.error("Development tenant 'example' does not exist")
# #                 return JsonResponse({'error': 'Development tenant not configured'}, status=404)

# #         logger.error(f"No tenant found for hostname: {hostname}")
# #         return JsonResponse({'error': f'No tenant found for hostname: {hostname}'}, status=404)
    
# from django_tenants.middleware import TenantMainMiddleware
# from django_tenants.utils import get_public_schema_name
# from core.models import Domain, Tenant
# from users.models import PasswordResetToken, RSAKeyPair
# from django.http import JsonResponse
# from django.db import connection
# import logging
# import json
# import jwt

# logger = logging.getLogger(__name__)

# class CustomTenantMiddleware(TenantMainMiddleware):
#     def process_request(self, request):
#         try:
#             host = request.get_host()
#         except Exception as e:
#             host = f"Invalid host: {e}"
#         logger.info(f"Processing request: {request.method} {request.path}, Host: {host}")

#         # Updated public paths - remove password reset endpoints
#         public_paths = [
#             '/api/docs/', '/api/schema/', '/api/token/refresh/',
#             '/api/social/callback/', '/api/admin/create/',
#             '/api/applications-engine/applications/parse-resume/application/autofil/',
#             '/api/talent-engine/requisitions/by-link/',
#         ]

#         # Handle password reset request by email domain (similar to login)
#         if request.path.startswith('/api/user/password/reset/') and request.method == 'POST':
#             try:
#                 body = request.body.decode('utf-8') if request.body else '{}'
#                 logger.debug(f"Password reset request body: {body}")
#                 data = json.loads(body)
#                 email = data.get('email')
#                 if not email:
#                     logger.error("No email provided in password reset request")
#                     return JsonResponse({'error': 'Email is required'}, status=400)

#                 email_domain = email.split('@')[1]
#                 logger.debug(f"Password reset email domain: {email_domain}")
#                 domain = Domain.objects.filter(domain=email_domain).first()
#                 if not domain:
#                     logger.error(f"No domain found for email domain: {email_domain}")
#                     return JsonResponse({'error': f'No tenant found for email domain: {email_domain}'}, status=404)

#                 request.tenant = domain.tenant
#                 connection.set_schema(domain.tenant.schema_name)
#                 logger.info(f"Set tenant schema for password reset: {domain.tenant.schema_name}")
#                 return
#             except (ValueError, IndexError) as e:
#                 logger.error(f"Invalid email format in password reset: {str(e)}")
#                 return JsonResponse({'error': 'Invalid email format'}, status=400)
#             except (KeyError, json.JSONDecodeError) as e:
#                 logger.error(f"Error processing password reset request: {str(e)}")
#                 return JsonResponse({'error': 'Invalid request format'}, status=400)

#         # Handle password reset confirmation by token
#         if request.path.startswith('/api/user/password/reset/confirm/') and request.method == 'POST':
#             try:
#                 body = request.body.decode('utf-8') if request.body else '{}'
#                 data = json.loads(body)
#                 token = data.get('token')
#                 if not token:
#                     logger.error("No token provided in password reset confirm request")
#                     return JsonResponse({'error': 'Token is required'}, status=400)

#                 # Look up reset token to determine tenant
#                 reset_token = PasswordResetToken.objects.select_related('tenant').filter(token=token).first()
#                 if not reset_token:
#                     logger.error(f"Invalid or missing reset token: {token}")
#                     return JsonResponse({'error': 'Invalid or missing token'}, status=400)

#                 request.tenant = reset_token.tenant
#                 connection.set_schema(reset_token.tenant.schema_name)
#                 logger.info(f"Set tenant schema for reset token: {reset_token.tenant.schema_name}")
#                 return
#             except (ValueError, KeyError, json.JSONDecodeError) as e:
#                 logger.error(f"Error processing reset token request: {str(e)}")
#                 return JsonResponse({'error': 'Invalid request format'}, status=400)

#         # Handle login/token endpoints (existing functionality)
#         if (request.path.startswith('/api/token/') or 
#             request.path.startswith('/api/login/') or 
#             request.path.startswith('/api/verify-2fa/')) and request.method == 'POST':
#             try:
#                 body = request.body.decode('utf-8') if request.body else '{}'
#                 logger.debug(f"Request body: {body}")
#                 data = json.loads(body)
#                 email = data.get('email')
#                 if not email:
#                     logger.error("No email provided in login/token request")
#                     return JsonResponse({'error': 'Email is required'}, status=400)

#                 email_domain = email.split('@')[1]
#                 logger.debug(f"Email domain: {email_domain}")
#                 domain = Domain.objects.filter(domain=email_domain).first()
#                 if not domain:
#                     logger.error(f"No domain found for email domain: {email_domain}")
#                     return JsonResponse({'error': f'No tenant found for email domain: {email_domain}'}, status=404)

#                 request.tenant = domain.tenant
#                 connection.set_schema(domain.tenant.schema_name)
#                 logger.info(f"Set tenant schema for email domain {email_domain}: {domain.tenant.schema_name}")
#                 with connection.cursor() as cursor:
#                     cursor.execute("SHOW search_path;")
#                     logger.debug(f"Current search_path: {cursor.fetchone()[0]}")
#                 return
#             except (ValueError, IndexError) as e:
#                 logger.error(f"Invalid email format in login: {str(e)}")
#                 return JsonResponse({'error': 'Invalid email format'}, status=400)
#             except (KeyError, json.JSONDecodeError) as e:
#                 logger.error(f"Error processing login/token request: {str(e)}")
#                 return JsonResponse({'error': 'Invalid request format'}, status=400)

#         # Public paths handling
#         if any(request.path.startswith(path) for path in public_paths):
#             try:
#                 public_tenant = Tenant.objects.get(schema_name=get_public_schema_name())
#                 request.tenant = public_tenant
#                 connection.set_schema(public_tenant.schema_name)
#                 logger.info(f"Set public schema for path: {public_tenant.schema_name}")
#                 return
#             except Tenant.DoesNotExist:
#                 logger.error("Public tenant does not exist")
#                 return JsonResponse({'error': 'Public tenant not configured'}, status=404)

#         # JWT authentication with tenant schema from unverified payload
#         try:
#             auth_header = request.headers.get('Authorization', '')
#             if auth_header.startswith('Bearer '):
#                 token = auth_header.split(' ')[1]
#                 # Extract tenant_id and tenant_schema from unverified JWT
#                 unverified_payload = jwt.decode(token, options={"verify_signature": False})
#                 tenant_id = unverified_payload.get("tenant_id")
#                 tenant_schema = unverified_payload.get("tenant_schema")
#                 logger.info(f"Unverified JWT: tenant_id={tenant_id}, tenant_schema={tenant_schema}")

#                 if tenant_id and tenant_schema:
#                     try:
#                         tenant = Tenant.objects.get(id=tenant_id, schema_name=tenant_schema)
#                         request.tenant = tenant
#                         connection.set_schema(tenant.schema_name)
#                         logger.info(f"Set tenant schema from JWT: {tenant.schema_name}")
#                     except Tenant.DoesNotExist:
#                         logger.error(f"Tenant not found: id={tenant_id}, schema={tenant_schema}")
#                         return JsonResponse({'error': 'Invalid tenant'}, status=404)

#                 # Now validate JWT with correct schema set
#                 unverified_header = jwt.get_unverified_header(token)
#                 kid = unverified_header.get("kid")
#                 if not kid:
#                     logger.error("No 'kid' header in JWT")
#                     return JsonResponse({'error': 'Invalid token key'}, status=401)

#                 keypair = RSAKeyPair.objects.filter(kid=kid, active=True).first()
#                 if not keypair:
#                     logger.error(f"No RSAKeyPair found for kid={kid} in schema={connection.schema_name}")
#                     return JsonResponse({'error': 'Invalid token key'}, status=401)

#                 tenant = keypair.tenant
#                 request.tenant = tenant
#                 connection.set_schema(tenant.schema_name)
#                 logger.info(f"Set tenant schema from RSAKeyPair: {tenant.schema_name}")
#                 return
#         except jwt.InvalidTokenError as e:
#             logger.error(f"JWT decode failed: {str(e)}")
#             return JsonResponse({'error': 'Invalid token'}, status=401)
#         except Exception as e:
#             logger.error(f"JWT authentication failed: {str(e)}")
#             return JsonResponse({'error': f'JWT error: {str(e)}'}, status=401)

#         # Fallback to hostname
#         try:
#             hostname = request.get_host().split(':')[0]
#             if hostname == '0.0.0.0':
#                 hostname = 'localhost'
#         except Exception as e:
#             logger.error(f"Error getting host: {str(e)}")
#             hostname = 'localhost'

#         domain = Domain.objects.filter(domain=hostname).first()
#         if domain:
#             request.tenant = domain.tenant
#             connection.set_schema(domain.tenant.schema_name)
#             logger.info(f"Set tenant schema from hostname: {domain.tenant.schema_name}")
#             return

#         # Development fallback
#         if hostname in ['127.0.0.1', 'localhost']:
#             try:
#                 tenant = Tenant.objects.get(schema_name='example')
#                 request.tenant = tenant
#                 connection.set_schema(tenant.schema_name)
#                 logger.info(f"Set tenant schema for local development: {tenant.schema_name}")
#                 return
#             except Tenant.DoesNotExist:
#                 logger.error("Development tenant 'example' does not exist")
#                 return JsonResponse({'error': 'Development tenant not configured'}, status=404)

#         logger.error(f"No tenant found for hostname: {hostname}")
#         return JsonResponse({'error': f'No tenant found for hostname: {hostname}'}, status=404)



from django_tenants.middleware import TenantMainMiddleware
from django_tenants.utils import get_public_schema_name
from core.models import Domain, Tenant
from users.models import PasswordResetToken, RSAKeyPair
from django.http import JsonResponse
from django.db import connection
import logging
import json
import jwt
from django.conf import settings
from auth_service.utils.cache import get_cache_key, get_from_cache, set_to_cache

logger = logging.getLogger(__name__)

class CustomTenantMiddleware(TenantMainMiddleware):
    def process_request(self, request):
        try:
            host = request.get_host()
        except Exception as e:
            host = f"Invalid host: {e}"
        logger.info(f"Processing request: {request.method} {request.path}, Host: {host}")

        # Updated public paths - remove password reset endpoints
        public_paths = [
            '/api/docs/', '/api/schema/', '/api/token/refresh/',
            '/api/social/callback/', '/api/admin/create/',
            '/api/applications-engine/applications/parse-resume/application/autofil/',
            '/api/talent-engine/requisitions/by-link/',
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
                return
            except (ValueError, KeyError, json.JSONDecodeError) as e:
                logger.error(f"Error processing reset token request: {str(e)}")
                return JsonResponse({'error': 'Invalid request format'}, status=400)

        # Handle login/token endpoints (existing functionality)
        if (request.path.startswith('/api/token/') or 
            request.path.startswith('/api/login/') or 
            request.path.startswith('/api/verify-2fa/')) and request.method == 'POST':
            try:
                body = request.body.decode('utf-8') if request.body else '{}'
                logger.debug(f"Request body: {body}")
                data = json.loads(body)
                email = data.get('email')
                if not email:
                    logger.error("No email provided in login/token request")
                    return JsonResponse({'error': 'Email is required'}, status=400)

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
                return
            except (ValueError, IndexError) as e:
                logger.error(f"Invalid email format in login: {str(e)}")
                return JsonResponse({'error': 'Invalid email format'}, status=400)
            except (KeyError, json.JSONDecodeError) as e:
                logger.error(f"Error processing login/token request: {str(e)}")
                return JsonResponse({'error': 'Invalid request format'}, status=400)

        # Public paths handling with caching
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
            return

        # Development fallback
        if hostname in ['127.0.0.1', 'localhost']:
            try:
                tenant = Tenant.objects.get(schema_name='example')
                request.tenant = tenant
                connection.set_schema(tenant.schema_name)
                logger.info(f"Set tenant schema for local development: {tenant.schema_name}")
                return
            except Tenant.DoesNotExist:
                logger.error("Development tenant 'example' does not exist")
                return JsonResponse({'error': 'Development tenant not configured'}, status=404)

        logger.error(f"No tenant found for hostname: {hostname}")
        return JsonResponse({'error': f'No tenant found for hostname: {hostname}'}, status=404)