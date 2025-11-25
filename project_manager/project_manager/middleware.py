# MicroserviceJWTMiddleware: Decodes JWT from Authorization header and attaches payload to request
import jwt
import requests
import logging
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin
from rest_framework.exceptions import AuthenticationFailed
from django.http import JsonResponse
from django.db import connection, close_old_connections
from django.contrib.auth.models import AnonymousUser
from django.utils.functional import SimpleLazyObject

logger = logging.getLogger('project_manager')

public_paths = [
    '/api/docs/',
    '/api/schema/',
    '/api/health/',
    # Temporarily allow knowledge base endpoints for development
    '/api/knowledge-base/',
]

# Paths that require authentication but not tenant schema
auth_only_paths = [
    '/api/project-manager/api/',
]


class SimpleUser:
    """
    Lightweight user object for JWT authentication.
    Compatible with Django's authentication system without requiring database User model.
    """
    def __init__(self, payload):
        # Extract user info from JWT payload
        self.pk = payload.get('sub')  # Primary identifier
        self.id = self.pk  # Alias for pk
        self.username = payload.get('username', '')
        self.first_name = payload.get('first_name', '')
        self.last_name = payload.get('last_name', '')
        self.email = payload.get('email', '')
        self.role = payload.get('role', '')
        self.tenant_id = payload.get('tenant_id')
        self.tenant_schema = payload.get('tenant_schema')
        
        # Django compatibility attributes
        self.is_active = True
        self.is_staff = payload.get('role') in ['admin', 'staff', 'co-admin']
        self.is_superuser = payload.get('role') == 'admin'
        
        # Backend attribute for Django compatibility
        self.backend = 'project_manager.middleware.JWTAuthenticationBackend'
        
        # Store full payload for reference
        self._payload = payload

    @property
    def is_authenticated(self):
        """
        Always return True. This is a way to tell if the user has been authenticated.
        Django expects this to be a property/callable, not a simple boolean attribute.
        """
        return True
    
    @property
    def is_anonymous(self):
        """
        Always return False. This is a way to tell if the user is anonymous.
        """
        return False

    def __str__(self):
        return self.username or self.email or str(self.pk)
    
    def __repr__(self):
        return f"<SimpleUser: {self.username} ({self.email})>"
    
    def get_username(self):
        """Django compatibility method"""
        return self.username or self.email
    
    def get_full_name(self):
        """Return full name"""
        return f"{self.first_name} {self.last_name}".strip() or self.email
    
    def get_short_name(self):
        """Return short name"""
        return self.first_name or self.username or self.email
    
    def has_perm(self, perm, obj=None):
        """Simple permission check - customize based on your needs"""
        return self.is_active and (self.is_superuser or self.is_staff)
    
    def has_perms(self, perm_list, obj=None):
        """Check multiple permissions"""
        return all(self.has_perm(perm, obj) for perm in perm_list)
    
    def has_module_perms(self, app_label):
        """Check if user has any permissions in the app"""
        return self.is_active and (self.is_superuser or self.is_staff)

        
class DatabaseConnectionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        close_old_connections()
        
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except Exception as e:
            logger.error(f"Database connection verification failed: {str(e)}")
            connection.close()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
            except Exception as e2:
                logger.error(f"Failed to reestablish database connection: {str(e2)}")
                return JsonResponse(
                    {"detail": "Database connection unavailable"},
                    status=503
                )

        response = self.get_response(request)
        close_old_connections()
        return response


def get_jwt_user(request):
    """
    Helper function to get user from JWT token.
    This is called lazily to prevent issues with other middleware.
    """
    # Check if already processed
    if hasattr(request, '_jwt_user_cache'):
        return request._jwt_user_cache
    
    # Allow public endpoints without JWT
    if any(request.path.startswith(public) for public in public_paths):
        logger.info("✓ Public endpoint - returning AnonymousUser")
        request._jwt_user_cache = AnonymousUser()
        return request._jwt_user_cache

    # Get Authorization header
    auth = request.headers.get('Authorization', '')
    
    if not auth.startswith('Bearer '):
        logger.warning("✗ No Bearer token - returning AnonymousUser")
        request._jwt_user_cache = AnonymousUser()
        return request._jwt_user_cache

    token = auth.split(' ')[1]

    try:
        # Get JWT header
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        alg = unverified_header.get("alg")

        if not kid:
            logger.error("✗ No 'kid' in token header")
            request._jwt_user_cache = AnonymousUser()
            return request._jwt_user_cache

        # Decode without verification to get tenant info
        unverified_payload = jwt.decode(token, options={"verify_signature": False})
        tenant_id = unverified_payload.get("tenant_id")

        # Fetch public key from auth service
        public_key_url = f"{settings.AUTH_SERVICE_URL}/api/public-key/{kid}/?tenant_id={tenant_id}"

        try:
            resp = requests.get(
                public_key_url,
                headers={'Authorization': auth},
                timeout=5
            )

            if resp.status_code != 200:
                logger.warning(f"✗ Could not fetch public key: {resp.status_code} - falling back to AnonymousUser")
                request._jwt_user_cache = AnonymousUser()
                return request._jwt_user_cache

            public_key = resp.json().get("public_key")
            if not public_key:
                logger.warning("✗ Public key not found in response - falling back to AnonymousUser")
                request._jwt_user_cache = AnonymousUser()
                return request._jwt_user_cache
        except requests.RequestException as e:
            logger.warning(f"✗ Public key request failed: {str(e)} - falling back to AnonymousUser")
            request._jwt_user_cache = AnonymousUser()
            return request._jwt_user_cache

        # Decode and verify JWT
        payload = jwt.decode(token, public_key, algorithms=[alg])
        
        # Store payload and create user
        request.jwt_payload = payload
        user = SimpleUser(payload)
        request._jwt_user_cache = user
        
        logger.info(f"✓✓✓ JWT User created: {user} (pk={user.pk}) ✓✓✓")
        return user

    except jwt.ExpiredSignatureError:
        logger.error("✗ Token expired")
        request._jwt_user_cache = AnonymousUser()
        return request._jwt_user_cache
    except jwt.InvalidTokenError as e:
        logger.error(f"✗ Invalid token: {str(e)}")
        request._jwt_user_cache = AnonymousUser()
        return request._jwt_user_cache
    except Exception as e:
        logger.error(f"✗ Unexpected JWT error: {str(e)}")
        logger.exception("Full traceback:")
        request._jwt_user_cache = AnonymousUser()
        return request._jwt_user_cache


class MicroserviceRS256JWTMiddleware(MiddlewareMixin):
    """
    JWT Middleware that sets request.user from JWT token using SimpleLazyObject.
    This ensures the user is only loaded when accessed and persists throughout the request.
    """
    
    def process_request(self, request):
        logger.info(f"========== JWT MIDDLEWARE START ==========")
        logger.info(f"Method: {request.method}, Path: {request.path}")
        
        # Use SimpleLazyObject to defer user loading until actually needed
        # This prevents other middleware from resetting request.user
        request.user = SimpleLazyObject(lambda: get_jwt_user(request))
        
        logger.info(f"✓ JWT user object attached as SimpleLazyObject")
        logger.info(f"========== JWT MIDDLEWARE END ==========")


class CustomTenantSchemaMiddleware:
    """
    Simplified middleware that uses public schema for all requests.
    This matches the pattern used by other microservices.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        logger.info(f"========== TENANT MIDDLEWARE START ==========")
        logger.info(f"Method: {request.method}, Path: {request.path}")

        # Force evaluation of lazy user object to ensure JWT is processed
        user = request.user
        logger.info(f"User: {user}")
        logger.info(f"User type: {type(user).__name__}")
        logger.info(f"User is_authenticated: {user.is_authenticated}")

        # No schema switching needed - using default connection
        logger.info("No schema switching - using default database connection")
        try:
            response = self.get_response(request)
            logger.info(f"========== TENANT MIDDLEWARE END ==========")
            return response
        except Exception as e:
            logger.error(f"✗ Request processing failed: {str(e)}")
            logger.exception("Full traceback:")
            return JsonResponse({'error': 'Request processing error'}, status=500)