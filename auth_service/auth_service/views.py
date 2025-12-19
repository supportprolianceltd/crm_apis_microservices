# auth_service/views.py (Full, with remember_me implementation)
import json
import logging
import random
import uuid
from datetime import datetime, timedelta
from urllib.parse import urlparse

import jwt
import requests
from core.models import Tenant, UsernameIndex, GlobalUser
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.core.cache import cache
from django.db import connection
from django.utils import timezone
from django_tenants.utils import tenant_context, get_public_schema_name
from jose import jwk
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from users.models import (
    BlacklistedToken,
    BlockedIP,
    CustomUser,
    RSAKeyPair,
    UserActivity,
)
from users.serializers import (
    CustomUserMinimalSerializer,
    CustomUserSerializer,
)
# 2FA imports
import pyotp
import qrcode
from io import BytesIO
import base64

from auth_service.authentication import RS256TenantJWTAuthentication, RS256CookieJWTAuthentication
from auth_service.utils.jwt_rsa import (
    blacklist_refresh_token,
    decode_rsa_jwt,
    issue_rsa_jwt,
)
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from rest_framework.pagination import PageNumberPagination
from auth_service.utils.kafka_producer import publish_event

logger = logging.getLogger(__name__)

# ============================================================================
# ENVIRONMENT-AWARE HELPER FUNCTIONS
# ============================================================================
def set_auth_cookies(response, access_token, refresh_token, remember_me=False):
    """Set authentication tokens with environment-aware settings"""
    # CRITICAL FIX: For development, always use these settings
    if settings.DEPLOYMENT_ENV == 'development':
        cookie_domain = None  # Must be None for localhost
        secure = False        # Must be False for HTTP
        samesite = 'Lax'     # Lax works for same-site requests
    else:
        cookie_domain = get_cookie_domain()
        secure = getattr(settings, 'COOKIE_SECURE', True)
        samesite = getattr(settings, 'COOKIE_SAMESITE', 'Lax')

    refresh_days = 30 if remember_me else 7
    refresh_max_age = refresh_days * 24 * 60 * 60

    logger.info(f"🍪 Setting cookies - Domain: {cookie_domain}, SameSite: {samesite}, Secure: {secure}, Remember Me: {remember_me}")

    # Access token cookie
    response.set_cookie(
        key='access_token',
        value=access_token,
        httponly=True,
        secure=secure,
        samesite=samesite,
        max_age=72 * 60 * 60,  # 72 hours
        domain=cookie_domain,
        path='/'
    )
    
    # Refresh token cookie
    response.set_cookie(
        key='refresh_token',
        value=refresh_token,
        httponly=True,
        secure=secure,
        samesite=samesite,
        max_age=refresh_max_age,  # Dynamic based on remember_me
        domain=cookie_domain,
        path='/'
    )
    
    return response


def get_cookie_domain():
    """
    Smart cookie domain detection - FIXED for development
    """
    web_page_url = getattr(settings, 'WEB_PAGE_URL', 'http://localhost:5173')
    parsed_url = urlparse(web_page_url)
    netloc = parsed_url.netloc
    
    # CRITICAL: Development environment - MUST use None
    if settings.DEPLOYMENT_ENV == 'development':
        logger.debug("🔧 Development: using None for cookie domain")
        return None  # This allows cookies on localhost with different ports
    
    # Production/Staging - extract domain
    domain = netloc.split(':')[0].lower()
    domain = domain.replace('www.', '')
    
    # For production, use the base domain
    if settings.DEPLOYMENT_ENV in ['production', 'staging']:
        # If it's an IP address, use None
        if any(char.isdigit() for char in domain.replace('.', '')):
            logger.warning(f"⚠️ Using IP: {domain}, using None for domain")
            return None
        else:
            # Add leading dot for subdomain sharing
            cookie_domain = f".{domain}" if not domain.startswith('.') else domain
            logger.debug(f"🔧 Production cookie domain: {cookie_domain}")
            return cookie_domain
    
    return None

def delete_auth_cookies(response):
    """Delete cookies with same settings used for creation"""
    cookie_domain = get_cookie_domain()
    
    response.delete_cookie(
        'access_token', 
        domain=cookie_domain,
        path='/'
    )
    response.delete_cookie(
        'refresh_token', 
        domain=cookie_domain,
        path='/'
    )
    logger.info("✅ Authentication cookies deleted")
    return response

class CustomPagination(PageNumberPagination):
    page_size = 20  # Adjust as needed

    def get_next_link(self):
        """Override to use gateway base URL."""
        if not self.page.has_next():
            return None
        gateway_url = getattr(settings, 'GATEWAY_URL', None)
        if not gateway_url:
            return super().get_next_link()  # Fallback to default

        request = self.request
        # Build base path from current request (e.g., /api/user/users/)
        path = request.path
        # Get query params, update 'page', preserve others
        query_params = request.query_params.copy()
        query_params['page'] = self.page.next_page_number()
        query_string = urlencode(query_params, doseq=True)

        # Reconstruct full URL with gateway scheme/host
        parsed_gateway = urlparse(gateway_url)
        full_url = f"{parsed_gateway.scheme}://{parsed_gateway.netloc}{path}?{query_string}"
        return full_url

    def get_previous_link(self):
        """Override to use gateway base URL."""
        if not self.page.has_previous():
            return None
        gateway_url = getattr(settings, 'GATEWAY_URL', None)
        if not gateway_url:
            return super().get_previous_link()  # Fallback to default

        request = self.request
        path = request.path
        query_params = request.query_params.copy()
        query_params['page'] = self.page.previous_page_number()
        query_string = urlencode(query_params, doseq=True)

        parsed_gateway = urlparse(gateway_url)
        full_url = f"{parsed_gateway.scheme}://{parsed_gateway.netloc}{path}?{query_string}"
        return full_url

    def get_paginated_response(self, data):
        """Ensure the full response uses overridden links."""
        response = super().get_paginated_response(data)
        gateway_url = getattr(settings, 'GATEWAY_URL', None)
        if gateway_url:
            response['next'] = self.get_next_link()
            response['previous'] = self.get_previous_link()
        return response

# ============================================================================
# VIEWS
# ============================================================================
class SimpleCookieTestView(APIView):
    permission_classes = [AllowAny]
    
    def get(self, request):
        """Simple endpoint to test basic cookie setting"""
        response = Response({
            'message': 'Simple cookie test',
            'cookies_received': list(request.COOKIES.keys()),
        })
        
        # Set a very simple cookie
        response.set_cookie(
            'simple_test',
            'working',
            httponly=False,
            secure=False,  # Force false for development
            samesite='Lax',
            max_age=3600,
            path='/'
        )
        
        return response

        
class CookieDebugView(APIView):
    permission_classes = [AllowAny]
    
    def get(self, request):
        """Debug endpoint to check cookie setting"""
        from auth_service.views import set_auth_cookies, get_cookie_domain
        
        # Use getattr for all settings to avoid AttributeError
        response_data = {
            'message': 'Cookie debug information',
            'cookies_received': dict(request.COOKIES),
            'headers': {
                'origin': request.META.get('HTTP_ORIGIN'),
                'host': request.META.get('HTTP_HOST'),
                'user_agent': request.META.get('HTTP_USER_AGENT'),
                'referer': request.META.get('HTTP_REFERER'),
            },
            'settings': {
                'cookie_domain': get_cookie_domain(),
                'cookie_samesite': getattr(settings, 'COOKIE_SAMESITE', 'Lax'),
                'cookie_secure': getattr(settings, 'COOKIE_SECURE', False),
                'cors_allowed_origins': getattr(settings, 'CORS_ALLOWED_ORIGINS', []),
                'deployment_env': getattr(settings, 'DEPLOYMENT_ENV', 'unknown'),
                'debug': settings.DEBUG,
                'tenant_cache_prefix': getattr(settings, 'TENANT_CACHE_PREFIX', 'NOT_SET'),
            }
        }
        
        response = Response(response_data)
        
        # Try to set a test cookie
        try:
            response = set_auth_cookies(response, 'test-access-debug', 'test-refresh-debug', remember_me=False)
            
            # Also set a simple cookie without our helper to test
            response.set_cookie(
                'simple_test_cookie',
                'simple_test_value',
                httponly=False,  # Make it accessible to JS for testing
                secure=getattr(settings, 'COOKIE_SECURE', False),
                samesite=getattr(settings, 'COOKIE_SAMESITE', 'Lax'),
                domain=get_cookie_domain(),
                path='/'
            )
        except Exception as e:
            response_data['cookie_setting_error'] = str(e)
        
        return response
    
    def post(self, request):
        """Test if cookies are sent back"""
        return Response({
            'cookies_sent_back': dict(request.COOKIES),
            'has_access_token': 'access_token' in request.COOKIES,
            'has_refresh_token': 'refresh_token' in request.COOKIES,
            'has_simple_test': 'simple_test_cookie' in request.COOKIES,
        })


class EnvironmentInfoView(APIView):
    permission_classes = [AllowAny]
    
    def get(self, request):
        """Return current environment configuration for debugging"""
        # Get cookie domain for this environment
        from auth_service.views import get_cookie_domain
        cookie_domain = get_cookie_domain()
        
        info = {
            'environment': getattr(settings, 'DEPLOYMENT_ENV', 'unknown'),
            'debug': settings.DEBUG,
            'frontend_urls': getattr(settings, 'FRONTEND_URLS', []),
            'cookie_domain': cookie_domain,
            'cookie_samesite': getattr(settings, 'COOKIE_SAMESITE', 'Lax'),
            'cookie_secure': getattr(settings, 'COOKIE_SECURE', False),
            'cors_allowed_origins': getattr(settings, 'CORS_ALLOWED_ORIGINS', []),
            'web_page_url': getattr(settings, 'WEB_PAGE_URL', ''),
        }
        
        # Check cookies IN this request
        cookies_received = {
            'access_token': bool(request.COOKIES.get('access_token')),
            'refresh_token': bool(request.COOKIES.get('refresh_token')),
        }
        
        # Log what cookies the backend can see
        all_cookies = list(request.COOKIES.keys())
        
        info['cookies_received'] = cookies_received
        info['all_cookies_seen_by_backend'] = all_cookies
        info['request_origin'] = request.META.get('HTTP_ORIGIN', '')
        info['request_host'] = request.get_host()
        
        return Response(info)

# Add this test endpoint to actually SET cookies and verify
class TestCookieSetView(APIView):
    """Test endpoint to verify cookie setting works"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        from auth_service.views import set_auth_cookies
        
        # Create a test response
        response = Response({
            'message': 'Test cookies set',
            'timestamp': timezone.now().isoformat(),
        })
        
        # Set test cookies
        response = set_auth_cookies(
            response,
            'test-access-token-12345',
            'test-refresh-token-67890',
            remember_me=False
        )
        
        return response
    
    def get(self, request):
        """Check if test cookies are present"""
        return Response({
            'cookies_present': {
                'access_token': bool(request.COOKIES.get('access_token')),
                'refresh_token': bool(request.COOKIES.get('refresh_token')),
            },
            'cookie_values': {
                'access_token': request.COOKIES.get('access_token', 'NOT_PRESENT')[:50],  # First 50 chars
                'refresh_token': request.COOKIES.get('refresh_token', 'NOT_PRESENT')[:50],
            }
        })

class TokenValidateView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [RS256TenantJWTAuthentication, RS256CookieJWTAuthentication]

    def get(self, request):
        logger.info(f"TokenValidateView request payload: {request.headers}")
        try:
            user = request.user
            tenant = getattr(request, "tenant", None)
            
            if not tenant:
                return Response({
                    "status": "error", 
                    "message": "Tenant context missing"
                }, status=status.HTTP_400_BAD_REQUEST)
                
            with tenant_context(tenant):
                user_data = CustomUserSerializer(user).data
                response_data = {
                    "status": "success",
                    "user": user_data,
                    "tenant_id": str(tenant.id),
                    "tenant_organizational_id": str(tenant.organizational_id),
                    "tenant_name": str(tenant.name),
                    "tenant_unique_id": str(tenant.unique_id),
                    "tenant_schema": tenant.schema_name,
                }
                logger.info("Token validation successful")
                return Response(response_data, status=status.HTTP_200_OK)
                
        except Exception as e:
            logger.error(f"Token validation failed: {str(e)}")
            return Response({
                "status": "error", 
                "message": "Token validation failed",
                "code": "TOKEN_INVALID"
            }, status=status.HTTP_401_UNAUTHORIZED)


class CustomTokenSerializer(serializers.Serializer):
    username = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(required=True)
    remember_me = serializers.BooleanField(required=False, default=False)
    otp_method = serializers.ChoiceField(
        choices=[('email', 'Email'), ('phone', 'Phone')],
        required=False,
        help_text="Optional: Override your preferred OTP method. If not specified, your profile preference will be used."
    )

    def validate(self, attrs):
        logger.info(f"🔐🔐🔐 CUSTOM SERIALIZER VALIDATE CALLED")
        
        remember_me = attrs.get('remember_me', False)
        ip_address = self.context["request"].META.get("REMOTE_ADDR")
        user_agent = self.context["request"].META.get("HTTP_USER_AGENT", "")
        tenant = self.context["request"].tenant

        # Get identifier
        identifier = attrs.get("email") or attrs.get("username")
        if not identifier:
            logger.error("❌ No email or username provided")
            self._log_activity(None, tenant or Tenant.objects.first(), "login", 
                             {"reason": "No email or username provided"}, 
                             ip_address, user_agent, False)
            raise serializers.ValidationError("Email or username is required.")

        logger.info(f"🔐 Attempting authentication for identifier: {identifier}")

        # Try authentication - this will handle both CustomUser and GlobalUser
        user = None
        if '@' in identifier:
            logger.info("🔐 Using email authentication")
            user = self._authenticate_by_email(identifier, attrs.get("password"), tenant)
        else:
            logger.info("🔐 Using username authentication")
            user = self._authenticate_by_username(identifier, attrs.get("password"))

        if not user:
            logger.error(f"❌ Authentication failed for identifier: {identifier}")
            self._log_activity(None, tenant or Tenant.objects.first(), "login",
                             {"reason": "Invalid credentials", "method": "username" if "username" in attrs else "email"},
                             ip_address, user_agent, False)
            raise serializers.ValidationError("Invalid credentials")

        # Check if user is locked or inactive
        is_locked = getattr(user, 'is_locked', False)
        if callable(is_locked):
            is_locked = is_locked()
            
        is_active = getattr(user, 'is_active', True)
        user_status = getattr(user, 'status', 'active')
        
        if is_locked or user_status == "suspended" or not is_active:
            self._log_activity(user, user.tenant, "login",
                             {"reason": "Account locked or suspended", "method": "username" if "username" in attrs else "email"},
                             ip_address, user_agent, False)
            raise serializers.ValidationError("Account is locked or suspended")

        # Check IP blocking (use user's tenant)
        if BlockedIP.objects.filter(ip_address=ip_address, tenant=user.tenant, is_active=True).exists():
            self._log_activity(user, user.tenant, "login",
                             {"reason": "IP address blocked", "method": "username" if "username" in attrs else "email"},
                             ip_address, user_agent, False)
            raise serializers.ValidationError("This IP address is blocked")

        # Determine OTP method - check user preference first, then allow override
        otp_method = attrs.get('otp_method')

        if not otp_method:
            # Check user's preferred OTP method from profile
            try:
                user_profile = user.profile
                otp_method = getattr(user_profile, 'preferred_otp_method', 'email')
                if not otp_method:
                    otp_method = 'email'  # Default fallback
            except Exception:
                otp_method = 'email'  # Default if no profile

        # Validate phone number if phone method is selected
        if otp_method == 'phone':
            # Check if user has a work phone number
            try:
                user_profile = user.profile
                if not user_profile.work_phone:
                    raise serializers.ValidationError("No phone number found. Please add a work phone number to your profile or use email verification.")
            except Exception:
                raise serializers.ValidationError("No phone number found. Please add a work phone number to your profile or use email verification.")

        # Cache login data for OTP verification
        cache_key = f"login_pending_{user.id}"
        cache.set(cache_key, {
            'remember_me': remember_me,
            'method': "username" if "username" in attrs else "email",
            'otp_method': otp_method,
            'ip_address': ip_address,
            'user_agent': user_agent
        }, timeout=300)  # 5 minutes

        # Send OTP to email or phone based on method
        otp_code = f"{random.randint(100000, 999999)}"
        logger.info(f"🔐 OTP generated for user {user.email} via {otp_method}: {otp_code}")
        cache.set(f"otp_{user.id}", {'code': otp_code, 'remember_me': remember_me, 'otp_method': otp_method}, timeout=300)

        # Send OTP via email or SMS based on method
        if otp_method == 'email':
            # Check cache to prevent duplicate OTP sends (atomic)
            cache_key = f"otp_sent_{user.id}"
            if not cache.add(cache_key, True, timeout=300):
                logger.warning(f"OTP already sent recently for user {user.email}, skipping")
            else:
                # Get the domain/URL the user is logging in from
                request = self.context.get("request")
                login_domain = None
                if request:
                    # Try to get from Origin header first, then Host
                    origin = request.META.get('HTTP_ORIGIN')
                    if origin:
                        login_domain = urlparse(origin).netloc
                    else:
                        host = request.META.get('HTTP_HOST')
                        if host:
                            login_domain = host.split(':')[0]  # Remove port if present

                # Send OTP via email (using Kafka events)
                from auth_service.utils.kafka_producer import publish_event
                # event_payload = {
                #     "event_type": "auth.2fa.code.requested",
                #     "tenant_id": str(user.tenant.unique_id),
                #     "timestamp": timezone.now().isoformat() + "Z",
                #     "payload": {
                #         "user_email": user.email,
                #         "user_first_name": getattr(user, 'first_name', ''),
                #         "user_last_name": getattr(user, 'last_name', ''),
                #         "2fa_code": otp_code,
                #         "2fa_method": "email",
                #         "ip_address": ip_address,
                #         "user_agent": user_agent,
                #         "login_method": "username" if "username" in attrs else "email",
                #         "remember_me": remember_me,
                #         "expires_in_seconds": 300,
                #         "login_domain": login_domain,
                #         "tenant_name": user.tenant.name,
                #         "tenant_logo": user.tenant.logo,
                #         "tenant_primary_color": user.tenant.primary_color,
                #         "tenant_secondary_color": user.tenant.secondary_color,
                #     },
                #     "metadata": {
                #         "event_id": f"evt-{uuid.uuid4()}",
                #         "created_at": timezone.now().isoformat() + "Z",
                #         "source": "auth-service",
                #         "tenant_id": str(user.tenant.unique_id),
                #     },
                # }
                
                
                event_payload = {
                    "metadata": {
                        "event_id": f"evt-{uuid.uuid4()}",
                        "event_type": "auth.2fa.code.requested",
                        "created_at": timezone.now().isoformat() + "Z",
                        "source": "auth-service",
                        "tenant_id": str(user.tenant.unique_id),
                    },
                    "data": {
                        "user_email": user.email,
                        "user_first_name": getattr(user, 'first_name', ''),
                        "user_last_name": getattr(user, 'last_name', ''),
                        "2fa_code": otp_code,
                        "2fa_method": "email",
                        "ip_address": ip_address,
                        "user_agent": user_agent,
                        "login_method": "username" if "username" in attrs else "email",
                        "remember_me": remember_me,
                        "expires_in_seconds": 300,
                        "login_domain": login_domain,
                        "tenant_name": user.tenant.name,
                        "tenant_logo": user.tenant.logo,
                        "tenant_primary_color": user.tenant.primary_color,
                        "tenant_secondary_color": user.tenant.secondary_color,
                    }
                }
                                
                try:
                    notifications_url = settings.NOTIFICATIONS_SERVICE_URL + "/events/"
                    response = requests.post(notifications_url, json=event_payload, timeout=5)
                    response.raise_for_status()
                    logger.info(f"✅ OTP email notification sent. Status: {response.status_code}")
                except Exception as e:
                    logger.warning(f"[❌ OTP Email Notification Error] Failed to send OTP email: {str(e)}")
                   
                try:
                   # publish_event("auth-events", event_payload)
                    logger.info(f"✅ OTP email event sent to Kafka")
                except Exception as e:
                    logger.warning(f"[❌ OTP Email Event Error] Failed to send OTP event: {str(e)}")
        else:  # otp_method == 'phone'
            # Send OTP via SMS (requires SMS service integration)
            user_profile = user.profile
            phone_number = user_profile.work_phone

            # TODO: Integrate with SMS service (e.g., Twilio)
            # For now, log the OTP and phone number for testing
            logger.info(f"📱 OTP SMS would be sent to {phone_number}: {otp_code}")



        # Don't complete login yet, require OTP verification
        destination = user.email if otp_method == 'email' else user.profile.work_phone
        method_text = "email" if otp_method == 'email' else "phone"
        return {
            "requires_otp": True,
            "user_id": user.id,
            "email": user.email,
            "otp_method": otp_method,
            "message": f"OTP sent to your {method_text}. Please verify to complete login."
        }



    def _authenticate_by_email(self, email, password, tenant):
        """Authenticate by email: Try tenant first, fallback to global"""
        logger.info(f"🔄 Email auth for: {email}")
        
        # Try tenant-specific authentication first
        if tenant and tenant.schema_name != get_public_schema_name():
            with tenant_context(tenant):
                user = authenticate(email=email, password=password)
                if user:
                    return user

        # Fallback to global user authentication
        try:
            public_tenant = Tenant.objects.get(schema_name=get_public_schema_name())
            with tenant_context(public_tenant):
                user = authenticate(email=email, password=password)
                if user:
                    user.tenant = public_tenant  # Attach for consistency
                    return user
        except Exception as e:
            logger.error(f"❌ Global email auth error: {str(e)}")
            
        return None

    def _authenticate_by_username(self, username, password):
        """Authenticate by username via global index"""
        logger.info(f"🔄 Username auth for: {username}")
        
        try:
            # Global lookup in public schema
            index_entry = UsernameIndex.objects.get(username=username)
            target_tenant = index_entry.tenant
            
            with tenant_context(target_tenant):
                # Try CustomUser first
                try:
                    user = CustomUser.objects.get(id=index_entry.user_id)
                    if user.check_password(password):
                        return user
                except CustomUser.DoesNotExist:
                    # Fallback to GlobalUser for public tenant
                    if target_tenant.schema_name == get_public_schema_name():
                        try:
                            user = GlobalUser.objects.get(id=index_entry.user_id)
                            user.tenant = target_tenant  # Attach for consistency
                            if user.check_password(password):
                                return user
                        except GlobalUser.DoesNotExist:
                            pass
            return None
            
        except UsernameIndex.DoesNotExist:
            logger.error(f"❌ Username '{username}' not found in index")
            return None
        except Exception as e:
            logger.error(f"❌ Username auth error: {str(e)}")
            return None

    def _generate_tokens(self, user, remember_me, method, ip_address, user_agent):
        """Generate JWT tokens for user (works for both CustomUser and GlobalUser)"""
        # Get user attributes safely
        username = getattr(user, 'username', user.email)
        role = getattr(user, 'role', 'super-admin')
        status = getattr(user, 'status', 'active')
        has_accepted_terms = getattr(user, 'has_accepted_terms', True)

        # Fetch primary domain
        primary_domain = user.tenant.domains.filter(is_primary=True).first()
        tenant_domain = primary_domain.domain if primary_domain else None

        # Access token
        access_payload = {
            "jti": str(uuid.uuid4()),
            "sub": user.email,
            "id": user.id,
            "first_name": user.last_name,
            "last_name": user.last_name,
            "username": username,
            "role": role,
            "status": status,
            "tenant_id": str(user.tenant.unique_id),
            "tenant_organizational_id": str(user.tenant.organizational_id),
            "tenant_name": str(user.tenant.name),
            "tenant_secondary_color": str(user.tenant.secondary_color),
            "tenant_primary_color": str(user.tenant.primary_color),
            "tenant_unique_id": str(user.tenant.unique_id),
            "tenant_schema": user.tenant.schema_name,
            "tenant_domain": tenant_domain,
            "has_accepted_terms": has_accepted_terms,
            "user_type": "global" if isinstance(user, GlobalUser) else "ordinary",
            "email": user.email,
            "type": "access",
            "exp": (timezone.now() + timedelta(hours=72)).timestamp(),
        }
        access_token = issue_rsa_jwt(access_payload, user.tenant)

        # Refresh token
        refresh_jti = str(uuid.uuid4())
        refresh_days = 30 if remember_me else 7
        refresh_payload = {
            "jti": refresh_jti,
            "sub": user.email,
            "username": username,
            "tenant_id": str(user.tenant.unique_id),
            "tenant_organizational_id": str(user.tenant.organizational_id),
            "tenant_name": str(user.tenant.name),
            "tenant_unique_id": str(user.tenant.unique_id),
            "tenant_domain": tenant_domain,
            "user_type": "global" if isinstance(user, GlobalUser) else "tenant",
            "type": "refresh",
            "remember_me": remember_me,
            "exp": (timezone.now() + timedelta(days=refresh_days)).timestamp(),
        }
        refresh_token = issue_rsa_jwt(refresh_payload, user.tenant)

        # Send notification for successful login
        self._send_login_notification(user, method, ip_address, user_agent, remember_me)

        return {
            "access": access_token,
            "refresh": refresh_token,
            "tenant_id": str(user.tenant.unique_id),
            "tenant_organizational_id": str(user.tenant.organizational_id),
            "tenant_name": str(user.tenant.name),
            "tenant_unique_id": str(user.tenant.unique_id),
            "tenant_secondary_color": str(user.tenant.secondary_color),
            "tenant_primary_color": str(user.tenant.primary_color),
            "tenant_schema": user.tenant.schema_name,
            "tenant_domain": tenant_domain,
            "user": {
                "id": user.id,
                "email": user.email,
                "first_name": getattr(user, 'first_name', ''),
                "last_name": getattr(user, 'last_name', ''),
                "username": username,
                "role": role,
                "user_type": "global" if isinstance(user, GlobalUser) else "tenant",
            },
            "has_accepted_terms": has_accepted_terms,
            "remember_me": remember_me,
        }

    def _send_login_notification(self, user, method, ip_address, user_agent, remember_me):
        """Send login notification event via Kafka"""
        try:
            from auth_service.utils.kafka_producer import publish_event
            event_payload = {
                "event_type": "user.login.succeeded",
                "tenant_id": str(user.tenant.unique_id),
                "timestamp": timezone.now().isoformat() + "Z",
                "payload": {
                    "user_email": user.email,
                    "login_method": method,
                    "ip_address": ip_address,
                    "timestamp": timezone.now().isoformat(),
                    "user_id": str(user.id),
                    "user_agent": user_agent,
                    "remember_me": remember_me,
                    "user_type": "global" if isinstance(user, GlobalUser) else "tenant",
                    # Include tenant branding for in-app notifications
                    "tenant_name": user.tenant.name,
                    "tenant_logo": user.tenant.logo,
                    "tenant_primary_color": user.tenant.primary_color,
                    "tenant_secondary_color": user.tenant.secondary_color,
                    # Always use custom email template in notification service
                    "html_template": "email/otp_email.html",
                },
                "metadata": {
                    "event_id": str(uuid.uuid4()),
                    "created_at": timezone.now().isoformat() + "Z",
                    "source": "auth-service",
                },
            }

            publish_event("auth-events", event_payload)
            logger.info("✅ Login success event sent to Kafka")

        except Exception as e:
            logger.warning(f"[❌ Login Event Error] Failed to send login event: {str(e)}")

    def _log_activity(self, user, tenant, action, details, ip_address, user_agent, success):
        """Helper to safely log UserActivity for both user types"""
        try:
            if not tenant:
                tenant = Tenant.objects.get(schema_name=get_public_schema_name())
                
            UserActivity.objects.create(
                user=user,
                tenant=tenant,
                action=action,
                performed_by=None,
                details=details,
                ip_address=ip_address,
                user_agent=user_agent,
                success=success,
            )
        except Exception as e:
            logger.error(f"❌ Failed to log activity '{action}': {str(e)}")


class CustomTokenObtainPairView(APIView):
    """
    Custom token obtain view that uses our completely custom serializer.
    Now sets tokens as HttpOnly cookies for security.
    """
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = CustomTokenSerializer

    # def post(self, request, *args, **kwargs):
    #     logger.info(f"🔐 CUSTOM TOKEN VIEW - Processing login request")
    #     serializer = self.serializer_class(data=request.data, context={'request': request})
        
    #     try:
    #         serializer.is_valid(raise_exception=True)
    #         logger.info("✅ Custom token serializer validation successful")
            
    #         # Get validated data (includes tokens)
    #         validated_data = serializer.validated_data
    #         remember_me = request.data.get('remember_me', False)
            
    #         # Create response with JSON data (for backward compatibility or non-cookie clients)
    #         response = Response(validated_data, status=status.HTTP_200_OK)
            
    #         # Set cookies for secure storage using helper function
    #         response = set_auth_cookies(
    #             response, 
    #             validated_data['access'], 
    #             validated_data['refresh'],
    #             remember_me=remember_me
    #         )
            
    #         logger.info("✅ Login successful with cookies set")
    #         return response
            
    #     except serializers.ValidationError as e:
    #         logger.error(f"❌ Custom token serializer validation failed: {e.detail}")
    #         return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)
    #     except Exception as e:
    #         logger.error(f"❌ Unexpected error in custom token view: {str(e)}")
    #         return Response(
    #             {"detail": "Authentication failed"}, 
    #             status=status.HTTP_400_BAD_REQUEST
    #         )


    def post(self, request, *args, **kwargs):
        logger.info(f"🔐 CUSTOM TOKEN VIEW - Processing login request")
        
        # NEW: Default to public tenant if middleware didn't set it (for global login)
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            try:
                tenant = Tenant.objects.get(schema_name=get_public_schema_name())
                request.tenant = tenant  # Attach for serializer/middleware consistency
                logger.info("🔄 Defaulted to public tenant for global login (no middleware resolution)")
            except Tenant.DoesNotExist:
                logger.error("Public tenant missing!")
                return Response({"detail": "System configuration error: Public tenant not found."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        serializer = self.serializer_class(data=request.data, context={'request': request})
        
        try:
            serializer.is_valid(raise_exception=True)
            logger.info("✅ Custom token serializer validation successful")

            # Get validated data
            validated_data = serializer.validated_data

            # Check if OTP is required
            if validated_data.get("requires_otp"):
                return Response({
                    "requires_otp": True,
                    "user_id": validated_data["user_id"],
                    "email": validated_data["email"],
                    "otp_method": validated_data.get("otp_method", "email"),
                    "message": validated_data["message"]
                }, status=status.HTTP_200_OK)

            # Normal login flow
            remember_me = request.data.get('remember_me', False)

            # Create response with JSON data (for backward compatibility or non-cookie clients)
            response = Response(validated_data, status=status.HTTP_200_OK)

            # Set cookies for secure storage using helper function
            response = set_auth_cookies(
                response,
                validated_data['access'],
                validated_data['refresh'],
                remember_me=remember_me
            )

            logger.info("✅ Login successful with cookies set")
            return response
            
        except serializers.ValidationError as e:
            logger.error(f"❌ Custom token serializer validation failed: {e.detail}")
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"❌ Unexpected error in custom token view: {str(e)}")
            return Response(
                {"detail": "Authentication failed"}, 
                status=status.HTTP_400_BAD_REQUEST
            )



class LoginWith2FAView(APIView):
    permission_classes = [AllowAny]
    serializer_class = CustomTokenSerializer

    def post(self, request, *args, **kwargs):
        ip_address = request.META.get("REMOTE_ADDR")
        user_agent = request.META.get("HTTP_USER_AGENT", "")
        tenant = getattr(request, "tenant", None)

        if not tenant:
            UserActivity.objects.create(
                user=None,
                tenant=Tenant.objects.first(),
                action="login",
                performed_by=None,
                details={"reason": "Tenant not found"},
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
            )
            return Response({"detail": "Tenant not found."}, status=status.HTTP_400_BAD_REQUEST)

        with tenant_context(tenant):
            serializer = self.serializer_class(data=request.data, context={"request": request})
            try:
                serializer.is_valid(raise_exception=True)
            except serializers.ValidationError as e:
                identifier = request.data.get("email") or request.data.get("username")
                # Updated: Use global index for username resolution in error logging
                if identifier and '@' not in identifier:
                    try:
                        index_entry = UsernameIndex.objects.get(username=identifier)
                        user = CustomUser.objects.get(id=index_entry.user_id)
                    except (UsernameIndex.DoesNotExist, CustomUser.DoesNotExist):
                        user = None
                else:
                    user = CustomUser.objects.filter(email=identifier, tenant=tenant).first()
                method = "username" if request.data.get("username") else "email"
                UserActivity.objects.create(
                    user=user,
                    tenant=tenant,
                    action="login",
                    performed_by=None,
                    details={"reason": f"Invalid credentials ({method}): {str(e)}"},
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False,
                )
                return Response(e.detail, status=status.HTTP_401_UNAUTHORIZED)

            # Get the user from the serializer's internal state
            # We need to extract user from the authentication methods
            identifier = request.data.get("email") or request.data.get("username")
            if '@' in identifier:
                user = authenticate(email=identifier, password=request.data.get("password"))
            else:
                # Use the same username authentication logic
                serializer_instance = self.serializer_class(context={"request": request})
                user = serializer_instance._authenticate_by_username(identifier, request.data.get("password"))

            method = "username" if request.data.get("username") else "email"
            if user.is_locked or user.status == "suspended" or not user.is_active:
                UserActivity.objects.create(
                    user=user,
                    tenant=tenant,
                    action="login",
                    performed_by=None,
                    details={"reason": "Account locked or suspended", "method": method},
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False,
                )
                return Response({"detail": "Account is locked or suspended."}, status=status.HTTP_403_FORBIDDEN)

            if BlockedIP.objects.filter(ip_address=ip_address, tenant=tenant, is_active=True).exists():
                UserActivity.objects.create(
                    user=user,
                    tenant=tenant,
                    action="login",
                    performed_by=None,
                    details={"reason": "IP address blocked", "method": method},
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False,
                )
                return Response({"detail": "This IP address is blocked."}, status=status.HTTP_403_FORBIDDEN)

            remember_me = request.data.get('remember_me', False)
            code = f"{random.randint(100000, 999999)}"
            cache.set(f"2fa_{user.id}", {'code': code, 'remember_me': remember_me}, timeout=300)

            event_payload = {
                "event_type": "auth.2fa.code.requested",
                "tenant_id": str(getattr(tenant, "unique_id", getattr(tenant, "id", "unknown"))),
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "payload": {
                    "user_email": user.email,
                    "user_first_name": getattr(user, 'first_name', ''),
                    "user_last_name": getattr(user, 'last_name', ''),
                    "2fa_code": code,
                    "2fa_method": "email",
                    "ip_address": ip_address,
                    "user_agent": user_agent,
                    "login_method": method,
                    "remember_me": remember_me,
                    "expires_in_seconds": 300,
                    "login_domain": request.get_host() if hasattr(request, 'get_host') else None,
                    "tenant_name": getattr(tenant, 'name', ''),
                    "tenant_logo": getattr(tenant, 'logo', None),
                    "tenant_primary_color": getattr(tenant, 'primary_color', ''),
                    "tenant_secondary_color": getattr(tenant, 'secondary_color', ''),
                },
                "metadata": {
                    "event_id": f"evt-{uuid.uuid4()}",
                    "created_at": datetime.utcnow().isoformat() + "Z",
                    "source": "auth-service",
                },
            }
            try:
                requests.post(settings.NOTIFICATIONS_EVENT_URL, json=event_payload, timeout=3)
            except Exception as e:
                logger.error(f"Failed to send 2FA event notification: {e}")

            UserActivity.objects.create(
                user=user,
                tenant=tenant,
                action="login",
                performed_by=None,
                details={"reason": "2FA code sent", "method": method},
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
            )
            return Response({"detail": "2FA code sent to your email.", "2fa_code": code}, status=200)

class CustomTokenRefreshView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []  # Add this line to disable authentication

    def post(self, request):
        # Try to get refresh token from cookies first, then fallback to body
        refresh_token = request.COOKIES.get('refresh_token') or request.data.get("refresh")
        ip_address = request.META.get("REMOTE_ADDR")
        user_agent = request.META.get("HTTP_USER_AGENT", "")

        if not refresh_token:
            UserActivity.objects.create(
                user=None,
                tenant=Tenant.objects.first(),
                action="refresh_token",
                performed_by=None,
                details={"reason": "No refresh token provided"},
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
            )
            return Response({"detail": "No refresh token provided."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Decode token without verification to extract tenant_id
            unverified_payload = jwt.decode(refresh_token, options={"verify_signature": False})
            tenant_id = unverified_payload.get("tenant_id")
            if not tenant_id:
                UserActivity.objects.create(
                    user=None,
                    tenant=Tenant.objects.first(),
                    action="refresh_token",
                    performed_by=None,
                    details={"reason": "Tenant ID missing in token payload"},
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False,
                )
                return Response({"detail": "Tenant ID missing in token payload."}, status=status.HTTP_400_BAD_REQUEST)

            # Fetch tenant and verify schema
            try:
                tenant = Tenant.objects.get(id=tenant_id)
                logger.info(f"Fetched tenant: id={tenant_id}, schema_name={tenant.schema_name}")
            except Tenant.DoesNotExist:
                UserActivity.objects.create(
                    user=None,
                    tenant=Tenant.objects.first(),
                    action="refresh_token",
                    performed_by=None,
                    details={"reason": f"Tenant not found for tenant_id: {tenant_id}"},
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False,
                )
                return Response({"detail": f"Tenant not found for tenant_id: {tenant_id}."}, status=status.HTTP_400_BAD_REQUEST)

            # Set tenant context and log current schema
            with tenant_context(tenant):
                logger.info(f"Current schema: {connection.schema_name}")
                # Validate and decode refresh token
                payload = decode_rsa_jwt(refresh_token, tenant)
                if payload.get("type") != "refresh":
                    UserActivity.objects.create(
                        user=None,
                        tenant=tenant,
                        action="refresh_token",
                        performed_by=None,
                        details={"reason": "Invalid token type"},
                        ip_address=ip_address,
                        user_agent=user_agent,
                        success=False,
                    )
                    return Response({"detail": "Invalid token type."}, status=status.HTTP_400_BAD_REQUEST)

                jti = payload.get("jti")
                if BlacklistedToken.objects.filter(jti=jti).exists():
                    UserActivity.objects.create(
                        user=None,
                        tenant=tenant,
                        action="refresh_token",
                        performed_by=None,
                        details={"reason": "Token blacklisted"},
                        ip_address=ip_address,
                        user_agent=user_agent,
                        success=False,
                    )
                    return Response({"detail": "Token blacklisted."}, status=status.HTTP_401_UNAUTHORIZED)

                # Blacklist the used refresh token
                exp = datetime.fromtimestamp(payload["exp"])
                BlacklistedToken.objects.create(jti=jti, expires_at=exp)

                # Retrieve user
                user = get_user_model().objects.get(email=payload["sub"])

                # Log successful refresh activity
                UserActivity.objects.create(
                    user=user,
                    tenant=tenant,
                    action="refresh_token",
                    performed_by=None,
                    details={"reason": "Token refresh successful"},
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=True,
                )

                # Fetch the primary domain
                primary_domain = tenant.domains.filter(is_primary=True).first()
                tenant_domain = primary_domain.domain if primary_domain else None

                remember_me = payload.get('remember_me', False)

                # Issue new access token (matching CustomTokenSerializer)
                access_payload = {
                    "jti": str(uuid.uuid4()),
                    "sub": user.email,
                    "role": user.role,
                    "status": user.status,
                    "tenant_id": user.tenant.id,
                    "tenant_organizational_id": str(tenant.organizational_id),
                    "tenant_unique_id": str(tenant.unique_id),
                    "tenant_schema": user.tenant.schema_name,
                    "tenant_domain": tenant_domain,
                    "has_accepted_terms": user.has_accepted_terms,
                    "user": CustomUserMinimalSerializer(user).data,
                    "email": user.email,
                    "type": "access",
                    "exp": (timezone.now() + timedelta(hours=72)).timestamp(),
                }
                access_token = issue_rsa_jwt(access_payload, user.tenant)

                # Issue new refresh token
                new_refresh_jti = str(uuid.uuid4())
                refresh_days = 30 if remember_me else 7
                refresh_payload = {
                    "jti": new_refresh_jti,
                    "sub": user.email,
                    "tenant_id": user.tenant.id,
                    "tenant_organizational_id": str(user.tenant.organizational_id),
                    "tenant_unique_id": str(tenant.unique_id),
                    "tenant_domain": tenant_domain,
                    "type": "refresh",
                    "remember_me": remember_me,
                    "exp": (timezone.now() + timedelta(days=refresh_days)).timestamp(),
                }
                new_refresh_token = issue_rsa_jwt(refresh_payload, user.tenant)

                data = {
                    "access": access_token,
                    "refresh": new_refresh_token,
                    "tenant_id": user.tenant.id,
                    "tenant_organizational_id": str(user.tenant.organizational_id),
                    "tenant_unique_id": str(tenant.unique_id),
                    "tenant_schema": user.tenant.schema_name,
                    "tenant_domain": tenant_domain,
                    "user": CustomUserMinimalSerializer(user).data,
                    "has_accepted_terms": user.has_accepted_terms,
                }

                # Create response and set new cookies using helper function
                response = Response(data, status=status.HTTP_200_OK)
                response = set_auth_cookies(response, access_token, new_refresh_token, remember_me=remember_me)
                
                logger.info("✅ Token refresh successful with new cookies")
                return response

        except Exception as e:
            UserActivity.objects.create(
                user=None,
                tenant=Tenant.objects.first(),
                action="refresh_token",
                performed_by=None,
                details={"reason": f"Token refresh failed: {str(e)}"},
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
            )
            return Response({"detail": str(e)}, status=status.HTTP_401_UNAUTHORIZED)

class SilentTokenRenewView(APIView):
    """
    Silent token renewal endpoint for proactive background refresh.
    Supports GET requests, reads refresh from cookie, sets new cookies,
    returns minimal response (204 No Content if successful, or error).
    Designed for timer-based calls without user interaction.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        # Reuse refresh logic but minimal response for silent calls
        ip_address = request.META.get("REMOTE_ADDR")
        user_agent = request.META.get("HTTP_USER_AGENT", "")

        refresh_token = request.COOKIES.get('refresh_token')
        if not refresh_token:
            logger.debug("Silent renew: No refresh token in cookie")
            return Response(status=status.HTTP_204_NO_CONTENT)  # Silently do nothing if no token

        try:
            # Decode to extract tenant_id (same as refresh)
            unverified_payload = jwt.decode(refresh_token, options={"verify_signature": False})
            tenant_id = unverified_payload.get("tenant_id")
            if not tenant_id:
                logger.debug("Silent renew: No tenant_id in refresh token")
                return Response(status=status.HTTP_204_NO_CONTENT)

            tenant = Tenant.objects.get(id=tenant_id)
            with tenant_context(tenant):
                # Validate refresh token (reuse decode_rsa_jwt)
                payload = decode_rsa_jwt(refresh_token, tenant)
                if payload.get("type") != "refresh":
                    logger.debug("Silent renew: Invalid refresh token type")
                    return Response(status=status.HTTP_204_NO_CONTENT)

                jti = payload.get("jti")
                if BlacklistedToken.objects.filter(jti=jti).exists():
                    logger.debug("Silent renew: Refresh token blacklisted")
                    return Response(status=status.HTTP_204_NO_CONTENT)

                # Blacklist old refresh
                exp = datetime.fromtimestamp(payload["exp"])
                BlacklistedToken.objects.create(jti=jti, expires_at=exp)

                # Get user
                user = get_user_model().objects.get(email=payload["sub"])

                # Minimal logging for silent renew (no full activity log to reduce noise)
                logger.debug(f"Silent renew successful for user {user.email} in tenant {tenant.schema_name}")

                # Fetch primary domain
                primary_domain = tenant.domains.filter(is_primary=True).first()
                tenant_domain = primary_domain.domain if primary_domain else None

                remember_me = payload.get('remember_me', False)

                # Issue new tokens (same as refresh)
                access_payload = {
                    "jti": str(uuid.uuid4()),
                    "sub": user.email,
                    "role": user.role,
                    "status": user.status,
                    "tenant_id": user.tenant.id,
                    "tenant_organizational_id": str(tenant.organizational_id),
                    "tenant_unique_id": str(tenant.unique_id),
                    "tenant_schema": user.tenant.schema_name,
                    "tenant_domain": tenant_domain,
                    "has_accepted_terms": user.has_accepted_terms,
                    "user": CustomUserMinimalSerializer(user).data,
                    "email": user.email,
                    "type": "access",
                    "exp": (timezone.now() + timedelta(hours=72)).timestamp(),
                }
                access_token = issue_rsa_jwt(access_payload, user.tenant)

                new_refresh_jti = str(uuid.uuid4())
                refresh_days = 30 if remember_me else 7
                refresh_payload = {
                    "jti": new_refresh_jti,
                    "sub": user.email,
                    "tenant_id": user.tenant.id,
                    "tenant_organizational_id": str(user.tenant.organizational_id),
                    "tenant_unique_id": str(tenant.unique_id),
                    "tenant_domain": tenant_domain,
                    "type": "refresh",
                    "remember_me": remember_me,
                    "exp": (timezone.now() + timedelta(days=refresh_days)).timestamp(),
                }
                new_refresh_token = issue_rsa_jwt(refresh_payload, user.tenant)

                # Set new cookies (no JSON body for minimal silent response)
                response = Response(status=status.HTTP_204_NO_CONTENT)
                response = set_auth_cookies(response, access_token, new_refresh_token, remember_me=remember_me)

                # Optional: Log success minimally
                UserActivity.objects.create(
                    user=user,
                    tenant=tenant,
                    action="silent_renew",
                    performed_by=None,
                    details={"reason": "Silent token renewal"},
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=True,
                )

                return response

        except Tenant.DoesNotExist:
            logger.debug("Silent renew: Tenant not found")
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            logger.debug(f"Silent renew failed: {str(e)}")
            return Response(status=status.HTTP_204_NO_CONTENT)  # Silently fail without error to avoid breaking UI

class VerifyOTPView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        identifier = request.data.get("email") or request.data.get("username")  # Accept email or username
        code = request.data.get("otp_code")
        ip_address = request.META.get("REMOTE_ADDR")
        user_agent = request.META.get("HTTP_USER_AGENT", "")
        tenant = getattr(request, "tenant", None)
        if not tenant:
            UserActivity.objects.create(
                user=None,
                tenant=Tenant.objects.first(),
                action="login",
                performed_by=None,
                details={"reason": "Tenant not found"},
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
            )
            return Response({"detail": "Tenant not found."}, status=400)

        # More robust identifier validation
        if not identifier or not isinstance(identifier, str) or not identifier.strip():
            return Response({"detail": "Email or username is required for OTP verification."}, status=400)

        identifier = identifier.strip()  # Remove whitespace

        # Resolve user based on identifier type
        user = None
        if '@' in identifier:
            # Email verification
            user = get_user_model().objects.filter(email__iexact=identifier, tenant=tenant).first()
        else:
            # Username verification
            try:
                index_entry = UsernameIndex.objects.get(username=identifier)
                target_tenant = index_entry.tenant
                with tenant_context(target_tenant):
                    user = CustomUser.objects.get(id=index_entry.user_id)
            except (UsernameIndex.DoesNotExist, CustomUser.DoesNotExist):
                user = None

        if not user:
            UserActivity.objects.create(
                user=None,
                tenant=tenant,
                action="login",
                performed_by=None,
                details={"reason": "Invalid user"},
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
            )
            return Response({"detail": "Invalid user."}, status=400)

        # Verify OTP with user's tenant context
        with tenant_context(user.tenant):
            cached_data = cache.get(f"otp_{user.id}")
            if not cached_data or not isinstance(cached_data, dict) or cached_data.get('code') != code:
                UserActivity.objects.create(
                    user=user,
                    tenant=user.tenant,
                    action="login",
                    performed_by=None,
                    details={"reason": "Invalid or expired OTP code"},
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False,
                )
                return Response({"detail": "Invalid or expired OTP code."}, status=400)

            # Check that verification method matches login method
            login_method = cached_data.get('method')
            if login_method == 'email' and '@' not in identifier:
                UserActivity.objects.create(
                    user=user,
                    tenant=user.tenant,
                    action="login",
                    performed_by=None,
                    details={"reason": "Method mismatch: logged in with email, verifying with username"},
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False,
                )
                return Response({"detail": "Please use email for OTP verification as you logged in with email."}, status=400)
            elif login_method == 'username' and '@' in identifier:
                UserActivity.objects.create(
                    user=user,
                    tenant=user.tenant,
                    action="login",
                    performed_by=None,
                    details={"reason": "Method mismatch: logged in with username, verifying with email"},
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False,
                )
                return Response({"detail": "Please use username for OTP verification as you logged in with username."}, status=400)

            remember_me = cached_data.get('remember_me', False)
            user.reset_login_attempts()
            UserActivity.objects.create(
                user=user,
                tenant=tenant,
                action="login",
                performed_by=None,
                details={"reason": "OTP verified"},
                ip_address=ip_address,
                user_agent=user_agent,
                success=True,
            )

            # Issue tokens (reuse logic from serializer)
            primary_domain = tenant.domains.filter(is_primary=True).first()
            tenant_domain = primary_domain.domain if primary_domain else None

            access_payload = {
                "jti": str(uuid.uuid4()),
                "sub": user.email,
                "username": user.username,
                "role": user.role,
                "status": user.status,
                "tenant_id": user.tenant.id,
                "tenant_organizational_id": str(tenant.organizational_id),
                "tenant_unique_id": str(tenant.unique_id),
                "tenant_schema": user.tenant.schema_name,
                "tenant_domain": tenant_domain,
                "has_accepted_terms": user.has_accepted_terms,
                "user": CustomUserMinimalSerializer(user).data,
                "email": user.email,
                "type": "access",
                "exp": (timezone.now() + timedelta(minutes=180)).timestamp(),
            }
            access_token = issue_rsa_jwt(access_payload, user.tenant)

            refresh_jti = str(uuid.uuid4())
            refresh_days = 30 if remember_me else 7
            refresh_payload = {
                "jti": refresh_jti,
                "sub": user.email,
                "username": user.username,
                "tenant_id": user.tenant.id,
                "tenant_organizational_id": str(user.tenant.organizational_id),
                "tenant_unique_id": str(tenant.unique_id),
                "tenant_domain": tenant_domain,
                "type": "refresh",
                "remember_me": remember_me,
                "exp": (timezone.now() + timedelta(days=refresh_days)).timestamp(),
            }
            refresh_token = issue_rsa_jwt(refresh_payload, user.tenant)

            data = {
                "access": access_token,
                "refresh": refresh_token,
                "tenant_id": user.tenant.id,
                "tenant_schema": user.tenant.schema_name,
                "tenant_domain": tenant_domain,
                "user": CustomUserMinimalSerializer(user).data,
                "has_accepted_terms": user.has_accepted_terms,
                "remember_me": remember_me,
            }

            # Create response and set cookies using helper function
            response = Response(data, status=200)
            response = set_auth_cookies(response, access_token, refresh_token, remember_me=remember_me)

            cache.delete(f"otp_{user.id}")
            
            # Publish login success event to Kafka for notification processing
            try:
                login_event = {
                    'event_type': 'user.login.succeeded',
                     "tenant_id": str(user.tenant.unique_id),
                    'timestamp': timezone.now().isoformat(),
                    'payload': {
                        'user_id': str(user.id),
                        'email': user.email,
                        'first_name': user.first_name,
                        'last_name': user.last_name,
                        'email': user.email,
                        'username': user.username,
                        'login_time': timezone.now().isoformat(),
                        'ip_address': ip_address,
                        'user_agent': user_agent,
                        'login_method': login_method,
                        # Include tenant branding for in-app notifications
                        'tenant_name': user.tenant.name,
                        'tenant_logo': user.tenant.logo,
                        'tenant_primary_color': user.tenant.primary_color,
                        'tenant_secondary_color': user.tenant.secondary_color,
                    }
                }
                #success = publish_event('auth-events', login_event)
                # if success:
                #     logger.info(f"✅ Published user.login.succeeded event to Kafka for user {user.email}")
                # else:
                #     logger.warning(f"⚠️ Failed to publish user.login.succeeded event to Kafka for user {user.email}")
            
            except Exception as e:
                logger.error(f"❌ Error publishing login event to Kafka: {str(e)}")
                # Don't fail login if Kafka fails - continue with response
            
            logger.info("✅ OTP verification successful with cookies set")
            return response

class LogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        # Get refresh token from cookies or body
        refresh_token = request.COOKIES.get('refresh_token') or request.data.get("refresh")
        ip_address = request.META.get("REMOTE_ADDR")
        user_agent = request.META.get("HTTP_USER_AGENT", "")
        tenant = getattr(request, "tenant", Tenant.objects.first())

        if not refresh_token:
            UserActivity.objects.create(
                user=None,
                tenant=tenant,
                action="logout",
                performed_by=None,
                details={"reason": "No refresh token provided"},
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
            )
            return Response({"detail": "No refresh token provided."}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # FIXED: Decode unverified to get tenant_id
            unverified_payload = jwt.decode(refresh_token, options={"verify_signature": False})
            tenant_id = unverified_payload.get("tenant_id")
            logger.info(f"Logout: Resolving tenant_id={tenant_id} from refresh token")
            
            if not tenant_id:
                logger.warning("No tenant_id in refresh token, using default")
                UserActivity.objects.create(
                    user=None,
                    tenant=tenant,
                    action="logout",
                    performed_by=None,
                    details={"reason": "No tenant_id in token"},
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False,
                )
                return Response({"detail": "Invalid token: No tenant ID."}, status=status.HTTP_400_BAD_REQUEST)

            # Fetch tenant
            tenant = Tenant.objects.get(id=tenant_id)
            with tenant_context(tenant):
                # Validate and decode refresh token
                payload = decode_rsa_jwt(refresh_token, tenant)
                if payload.get("type") != "refresh":
                    UserActivity.objects.create(
                        user=None,
                        tenant=tenant,
                        action="logout",
                        performed_by=None,
                        details={"reason": "Invalid token type"},
                        ip_address=ip_address,
                        user_agent=user_agent,
                        success=False,
                    )
                    return Response({"detail": "Invalid token type."}, status=status.HTTP_400_BAD_REQUEST)

                jti = payload.get("jti")
                if BlacklistedToken.objects.filter(jti=jti).exists():
                    UserActivity.objects.create(
                        user=None,
                        tenant=tenant,
                        action="logout",
                        performed_by=None,
                        details={"reason": "Token already blacklisted"},
                        ip_address=ip_address,
                        user_agent=user_agent,
                        success=False,
                    )
                    return Response({"detail": "Token already blacklisted."}, status=status.HTTP_400_BAD_REQUEST)

                # Blacklist the used refresh token
                exp = datetime.fromtimestamp(payload["exp"])
                BlacklistedToken.objects.create(jti=jti, expires_at=exp)
            
            UserActivity.objects.create(
                user=None,
                tenant=tenant,
                action="logout",
                performed_by=None,
                details={},
                ip_address=ip_address,
                user_agent=user_agent,
                success=True,
            )
            
            # Create response and delete cookies using helper function
            response = Response({"detail": "Logged out successfully."})
            response = delete_auth_cookies(response)
            
            logger.info("✅ Logout successful with cookies deleted")
            return response
            
        except Tenant.DoesNotExist:
            logger.error(f"Logout: Tenant {tenant_id} not found")
            UserActivity.objects.create(
                user=None,
                tenant=Tenant.objects.first(),
                action="logout",
                performed_by=None,
                details={"reason": f"Tenant not found: {tenant_id}"},
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
            )
            return Response({"detail": "Invalid tenant in token"}, status=400)
        except jwt.DecodeError as e:
            logger.error(f"Logout: Invalid refresh token: {e}")
            UserActivity.objects.create(
                user=None,
                tenant=tenant,
                action="logout",
                performed_by=None,
                details={"reason": "Invalid refresh token"},
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
            )
            return Response({"detail": "Invalid refresh token"}, status=400)
        except Exception as e:
            logger.error(f"Logout unexpected error: {e}")
            UserActivity.objects.create(
                user=None,
                tenant=tenant,
                action="logout",
                performed_by=None,
                details={"reason": str(e)},
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
            )
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class PublicKeyView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, kid):
        tenant_id = request.query_params.get("tenant_id")
        if not tenant_id:
            logger.error("No tenant_id provided in query params")
            return Response({"error": "tenant_id is required"}, status=400)

        try:
            logger.info(f"Set tenant_id to {tenant_id} ")
            tenant = Tenant.objects.get(id=tenant_id)
            connection.set_schema(tenant.schema_name)
            logger.info(f"Set schema to {tenant.schema_name} for kid={kid}")
            keypair = RSAKeyPair.objects.get(kid=kid, tenant=tenant, active=True)
            return Response({"public_key": keypair.public_key_pem})
        except Tenant.DoesNotExist:
            logger.error(f"Tenant not found: id={tenant_id}")
            return Response({"error": "Tenant not found"}, status=404)
        except RSAKeyPair.DoesNotExist:
            logger.error(f"No RSAKeyPair found for kid={kid} in schema={tenant.schema_name}")
            return Response({"error": "Keypair not found"}, status=404)

class JWKSView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        jwks = {"keys": []}
        tenants = Tenant.objects.all()
        for tenant in tenants:
            with tenant_context(tenant):
                for keypair in RSAKeyPair.objects.filter(active=True):
                    rsa_key = jwk.construct(keypair.public_key_pem, algorithm="RS256")
                    pub_jwk = rsa_key.to_dict()
                    pub_jwk["kid"] = keypair.kid
                    pub_jwk["use"] = "sig"
                    pub_jwk["alg"] = "RS256"
                    jwks["keys"].append(pub_jwk)
        return Response(jwks)

class JitsiTokenView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        room = request.data.get("room")
        moderator = request.data.get("moderator", True)
        ip_address = request.META.get("REMOTE_ADDR")
        user_agent = request.META.get("HTTP_USER_AGENT", "")
        if not room:
            UserActivity.objects.create(
                user=request.user,
                tenant=request.tenant,
                action="jitsi_token",
                performed_by=None,
                details={"reason": "Room name required"},
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
            )
            return Response({"error": "Room name required"}, status=400)
        user = request.user
        tenant = request.tenant
        payload = {
            "context": {
                "user": {
                    "name": f"{user.first_name} {user.last_name}",
                    "email": user.email,
                    "moderator": moderator,
                },
            },
            "room": room,
            "sub": "server1.prolianceltd.com",
            "iss": "crm-app",
            "aud": "jitsi",
            # In JitsiTokenView.post
            "exp": int((timezone.now() + timedelta(days=7)).timestamp()),  # Extend to 7 days
            "iat": int(timezone.now().timestamp()),
        }
        token = issue_rsa_jwt(payload, tenant)
        UserActivity.objects.create(
            user=user,
            tenant=tenant,
            action="jitsi_token",
            performed_by=None,
            details={"room": room},
            ip_address=ip_address,
            user_agent=user_agent,
            success=True,
        )
        return Response({"token": token})


# ============================================================================
# TWO-FACTOR AUTHENTICATION VIEWS
# ============================================================================

class TwoFactorSetupView(APIView):
    """
    Generate and display QR code for 2FA setup
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [RS256TenantJWTAuthentication, RS256CookieJWTAuthentication]

    def get(self, request):
        """Generate QR code for 2FA setup"""
        user = request.user
        tenant = getattr(request, "tenant", None)

        if not tenant:
            return Response({"detail": "Tenant context missing"}, status=status.HTTP_400_BAD_REQUEST)

        with tenant_context(tenant):
            # Check if 2FA is already enabled
            if user.two_factor_enabled:
                return Response({
                    "detail": "Two-factor authentication is already enabled",
                    "enabled": True
                }, status=status.HTTP_400_BAD_REQUEST)

            # Generate secret if not exists
            if not user.two_factor_secret:
                secret = pyotp.random_base32()
                user.two_factor_secret = secret
                user.save()

            # Create TOTP object
            totp = pyotp.TOTP(user.two_factor_secret)
            provisioning_uri = totp.provisioning_uri(
                name=user.email,
                issuer_name=f"{tenant.name} CRM"
            )

            # Generate QR code
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(provisioning_uri)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")

            # Convert to base64
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            qr_code_base64 = base64.b64encode(buffer.getvalue()).decode()

            return Response({
                "secret": user.two_factor_secret,
                "qr_code": f"data:image/png;base64,{qr_code_base64}",
                "provisioning_uri": provisioning_uri
            })


class TwoFactorEnableView(APIView):
    """
    Enable 2FA after verification
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [RS256TenantJWTAuthentication, RS256CookieJWTAuthentication]

    def post(self, request):
        """Verify code and enable 2FA"""
        user = request.user
        tenant = getattr(request, "tenant", None)
        code = request.data.get("code")

        if not tenant:
            return Response({"detail": "Tenant context missing"}, status=status.HTTP_400_BAD_REQUEST)

        if not code:
            return Response({"detail": "Verification code is required"}, status=status.HTTP_400_BAD_REQUEST)

        with tenant_context(tenant):
            if user.two_factor_enabled:
                return Response({"detail": "Two-factor authentication is already enabled"}, status=status.HTTP_400_BAD_REQUEST)

            if not user.two_factor_secret:
                return Response({"detail": "Please setup 2FA first"}, status=status.HTTP_400_BAD_REQUEST)

            # Verify the code
            totp = pyotp.TOTP(user.two_factor_secret)
            if not totp.verify(code):
                return Response({"detail": "Invalid verification code"}, status=status.HTTP_400_BAD_REQUEST)

            # Generate backup codes
            backup_codes = [str(random.randint(100000, 999999)) for _ in range(10)]
            user.two_factor_enabled = True
            user.two_factor_backup_codes = backup_codes
            user.save()

            # Log activity
            UserActivity.objects.create(
                user=user,
                tenant=tenant,
                action="2fa_enabled",
                performed_by=user,
                details={"method": "TOTP"},
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                success=True,
            )

            return Response({
                "detail": "Two-factor authentication enabled successfully",
                "backup_codes": backup_codes
            })


class TwoFactorDisableView(APIView):
    """
    Disable 2FA
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [RS256TenantJWTAuthentication, RS256CookieJWTAuthentication]

    def post(self, request):
        """Disable 2FA"""
        user = request.user
        tenant = getattr(request, "tenant", None)
        code = request.data.get("code")

        if not tenant:
            return Response({"detail": "Tenant context missing"}, status=status.HTTP_400_BAD_REQUEST)

        with tenant_context(tenant):
            if not user.two_factor_enabled:
                return Response({"detail": "Two-factor authentication is not enabled"}, status=status.HTTP_400_BAD_REQUEST)

            if not code:
                return Response({"detail": "Verification code is required"}, status=status.HTTP_400_BAD_REQUEST)

            # Verify the code before disabling
            totp = pyotp.TOTP(user.two_factor_secret)
            if not totp.verify(code):
                return Response({"detail": "Invalid verification code"}, status=status.HTTP_400_BAD_REQUEST)

            # Disable 2FA
            user.two_factor_enabled = False
            user.two_factor_secret = None
            user.two_factor_backup_codes = []
            user.save()

            # Log activity
            UserActivity.objects.create(
                user=user,
                tenant=tenant,
                action="2fa_disabled",
                performed_by=user,
                details={"method": "TOTP"},
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                success=True,
            )

            return Response({"detail": "Two-factor authentication disabled successfully"})


class TwoFactorVerifyView(APIView):
    """
    Verify 2FA code during login
    """
    permission_classes = [AllowAny]

    def post(self, request):
        """Verify 2FA code and complete login"""
        email = request.data.get("email")
        code = request.data.get("code")
        tenant = getattr(request, "tenant", None)

        if not tenant:
            return Response({"detail": "Tenant context missing"}, status=status.HTTP_400_BAD_REQUEST)

        if not email or not code:
            return Response({"detail": "Email and verification code are required"}, status=status.HTTP_400_BAD_REQUEST)

        with tenant_context(tenant):
            try:
                user = CustomUser.objects.get(email=email, tenant=tenant)
            except CustomUser.DoesNotExist:
                return Response({"detail": "User not found"}, status=status.HTTP_404_NOT_FOUND)

            if not user.two_factor_enabled:
                return Response({"detail": "Two-factor authentication is not enabled for this account"}, status=status.HTTP_400_BAD_REQUEST)

            # Check if code is in backup codes first
            if code in user.two_factor_backup_codes:
                # Remove used backup code
                user.two_factor_backup_codes.remove(code)
                user.save()
                code_type = "backup"
            else:
                # Verify TOTP code
                totp = pyotp.TOTP(user.two_factor_secret)
                if not totp.verify(code):
                    return Response({"detail": "Invalid verification code"}, status=status.HTTP_400_BAD_REQUEST)
                code_type = "totp"

            # Get cached login data
            cached_key = f"login_pending_{user.id}"
            login_data = cache.get(cached_key)

            if not login_data:
                return Response({"detail": "Login session expired. Please try logging in again."}, status=status.HTTP_400_BAD_REQUEST)

            # Generate tokens
            primary_domain = tenant.domains.filter(is_primary=True).first()
            tenant_domain = primary_domain.domain if primary_domain else None

            access_payload = {
                "jti": str(uuid.uuid4()),
                "sub": user.email,
                "username": user.username,
                "role": user.role,
                "status": user.status,
                "tenant_id": user.tenant.id,
                "tenant_organizational_id": str(tenant.organizational_id),
                "tenant_unique_id": str(tenant.unique_id),
                "tenant_schema": user.tenant.schema_name,
                "tenant_domain": tenant_domain,
                "has_accepted_terms": user.has_accepted_terms,
                "user": CustomUserMinimalSerializer(user).data,
                "email": user.email,
                "type": "access",
                "exp": (timezone.now() + timedelta(minutes=180)).timestamp(),
            }
            access_token = issue_rsa_jwt(access_payload, user.tenant)

            refresh_jti = str(uuid.uuid4())
            refresh_days = 30 if login_data.get('remember_me', False) else 7
            refresh_payload = {
                "jti": refresh_jti,
                "sub": user.email,
                "username": user.username,
                "tenant_id": user.tenant.id,
                "tenant_organizational_id": str(user.tenant.organizational_id),
                "tenant_unique_id": str(tenant.unique_id),
                "tenant_domain": tenant_domain,
                "type": "refresh",
                "remember_me": login_data.get('remember_me', False),
                "exp": (timezone.now() + timedelta(days=refresh_days)).timestamp(),
            }
            refresh_token = issue_rsa_jwt(refresh_payload, user.tenant)

            data = {
                "access": access_token,
                "refresh": refresh_token,
                "tenant_id": user.tenant.id,
                "tenant_schema": user.tenant.schema_name,
                "tenant_domain": tenant_domain,
                "user": CustomUserMinimalSerializer(user).data,
                "has_accepted_terms": user.has_accepted_terms,
                "remember_me": login_data.get('remember_me', False),
            }

            # Log successful login
            UserActivity.objects.create(
                user=user,
                tenant=tenant,
                action="login",
                performed_by=None,
                details={"method": "2FA", "code_type": code_type},
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                success=True,
            )

            # Clear cache
            cache.delete(cached_key)

            # Create response and set cookies
            response = Response(data, status=status.HTTP_200_OK)
            response = set_auth_cookies(response, access_token, refresh_token, remember_me=login_data.get('remember_me', False))

            return response