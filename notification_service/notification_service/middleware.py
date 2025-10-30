import jwt
import requests
import logging
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin
from rest_framework.exceptions import AuthenticationFailed
from django.http import JsonResponse
from django.db import close_old_connections, connection
from django.contrib.auth.models import AnonymousUser

logger = logging.getLogger('notifications')

# Public paths for Notification service
public_paths = [
    '/api/docs/',
    '/api/schema/',
    '/api/notifications/health/',
    '/admin/',
    '/static/',
]

class SimpleUser:
    def __init__(self, payload):
        self.pk = payload.get('user', {}).get('id')
        self.username = payload.get('user', {}).get('username', '')
        self.email = payload.get('email', '')
        self.role = payload.get('role', '')
        self.tenant_id = payload.get('tenant_unique_id')  # Key change: tenant_unique_id from your HR
        self.tenant_schema = payload.get('tenant_schema')
        self.is_authenticated = True
        self.is_active = True
        self.is_staff = payload.get('role') in ['hr', 'admin', 'root-admin']
        self.is_superuser = payload.get('role') == 'root-admin'
        self.jwt_payload = payload

    def __str__(self):
        return self.username or self.email

    def has_perm(self, perm, obj=None):
        if self.is_superuser:
            return True
        if perm == 'notifications.access':
            return self.role in ['hr', 'admin', 'root-admin']
        return False

    def has_module_perms(self, app_label):
        if self.is_superuser:
            return True
        if app_label == 'notifications':
            return self.role in ['hr', 'admin', 'root-admin']
        return False

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

class MicroserviceRS256JWTMiddleware(MiddlewareMixin):
    """
    JWT authentication middleware for Notification microservice
    Validates RS256 tokens and sets request.user with tenant context
    """
    
    def process_request(self, request):
        if any(request.path.startswith(path) for path in public_paths):
            request.user = AnonymousUser()
            request.jwt_payload = None
            request.tenant_id = None
            return

        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        if not auth_header.startswith('Bearer '):
            logger.warning(f"No Bearer token provided for protected path: {request.path}")
            request.user = AnonymousUser()
            request.jwt_payload = None
            request.tenant_id = None
            return

        token = auth_header.split(' ')[1]
        
        try:
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")
            alg = unverified_header.get("alg")
            logger.info(f"Token header: kid={kid}, alg={alg}")
            
            if not kid:
                logger.error("No 'kid' in token header")
                raise AuthenticationFailed("Invalid token format: missing key ID")

            if alg != "RS256":
                logger.error(f"Unsupported algorithm in token: {alg}. Expected RS256.")
                raise AuthenticationFailed(f"Unsupported algorithm: {alg}")

            unverified_payload = jwt.decode(token, options={"verify_signature": False})
            tenant_id = unverified_payload.get("tenant_unique_id")  # Matching your HR
            tenant_schema = unverified_payload.get("tenant_schema")
            
            logger.info(f"JWT validation: kid={kid}, tenant_id={tenant_id}, tenant_schema={tenant_schema}")

            resp = requests.get(
                f"{settings.AUTH_SERVICE_URL}/api/public-key/{kid}/?tenant_id={tenant_id}",
                headers={'Authorization': auth_header},
                timeout=5
            )
            logger.info(f"Public key response: {resp.status_code}")
            if resp.status_code != 200:
                logger.error(f"Failed to fetch public key: {resp.status_code} - {resp.text}")
                raise AuthenticationFailed(f"Could not fetch public key: {resp.status_code}")

            public_key_data = resp.json()
            public_key = public_key_data.get("public_key")
            if not public_key:
                logger.error("Public key not found in response")
                raise AuthenticationFailed("Authentication service error: no public key")

            payload = jwt.decode(
                token, 
                public_key, 
                algorithms=["RS256"],
                options={"verify_aud": False}
            )
            
            request.jwt_payload = payload
            request.user = SimpleUser(payload)
            request.tenant_id = tenant_id  # Set for easy access in views
            
            logger.info(f"Authenticated user: {request.user.email}, tenant: {request.tenant_id}")

        except jwt.ExpiredSignatureError:
            logger.warning("JWT token has expired")
            return JsonResponse(
                {'error': 'Token has expired', 'code': 'token_expired'}, 
                status=401
            )
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid JWT token: {str(e)}")
            return JsonResponse(
                {'error': f'Invalid token: {str(e)}', 'code': 'invalid_token'}, 
                status=401
            )
        except requests.RequestException as e:
            logger.error(f"Auth service request failed: {str(e)}")
            return JsonResponse(
                {'error': 'Authentication service unavailable', 'code': 'auth_service_down'}, 
                status=503
            )
        except Exception as e:
            logger.error(f"Unexpected JWT processing error: {str(e)}")
            return JsonResponse(
                {'error': 'Authentication failed', 'code': 'auth_failed'}, 
                status=401
            )