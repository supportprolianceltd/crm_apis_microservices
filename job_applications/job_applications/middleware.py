# MicroserviceJWTMiddleware: Decodes JWT from Authorization header and attaches payload to request
import jwt
from django.conf import settings
from rest_framework.exceptions import AuthenticationFailed
import logging
import requests
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from django.http import JsonResponse
from django.contrib.auth.models import AnonymousUser
from rest_framework.authentication import BaseAuthentication
from django.contrib.auth.models import AnonymousUser


logger = logging.getLogger('job_applications')

class SimpleUser:
    is_authenticated = True
    is_active = True
    is_anonymous = False
    username = "microservice"
    email = ""
    def __init__(self, payload):
        self.id = payload.get('user_id')
        self.tenant_id = payload.get('tenant_id')
        self.role = payload.get('role', None)
        self.branch = payload.get('branch', None)
    def save(self, *args, **kwargs): pass  # For compatibility

    
class MicroserviceJWTMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        auth = request.headers.get('Authorization', '')
        if auth.startswith('Bearer '):
            token = auth.split(' ')[1]
            try:
                payload = jwt.decode(
                    token,
                    settings.SIMPLE_JWT['SIGNING_KEY'],
                    algorithms=[settings.SIMPLE_JWT['ALGORITHM']]
                )
                request.jwt_payload = payload
                request.user = SimpleUser(payload)
                logger.info(f"Set request.user: {request.user}, is_authenticated: {request.user.is_authenticated}")
            except jwt.ExpiredSignatureError:
                return JsonResponse({'error': 'Token expired'}, status=401)
            except jwt.InvalidTokenError:
                return JsonResponse({'error': 'Invalid token'}, status=401)
            except Exception as e:
                logger.error(f"JWT decoding error: {str(e)}")
                return JsonResponse({'error': 'Token error'}, status=401)
        else:
            request.user = AnonymousUser()

        response = self.get_response(request)
        logger.info(f"After MicroserviceJWTMiddleware response: request.user={request.user}, is_authenticated={getattr(request.user, 'is_authenticated', False)}")
        return response

class CustomTenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        logger.info(f"Incoming Authorization header: {auth_header}")

        public_paths = [
            '/api/docs/', '/api/schema/', '/api/health/',
            '/api/applications-engine/applications/parse-resume/autofill/',  # <-- Add this line
            '/api/applications-engine/apply-jobs/',  # <-- Add this line
        ]
        if any(request.path.startswith(path) for path in public_paths):
            request.tenant = None
            request.tenant_id = None
            request.user = AnonymousUser()  # <-- Add this line
            return self.get_response(request)

        if not auth_header.startswith("Bearer "):
            logger.warning("Authorization header missing Bearer prefix.")
            return JsonResponse({'error': 'Unauthorized'}, status=401)

        token_str = auth_header.split(" ")[1]
        try:
            validated_token = JWTAuthentication().get_validated_token(token_str)
            tenant_id = validated_token.get('tenant_id')
            user_id = validated_token.get('user_id')

            if not tenant_id:
                logger.error(f"Tenant ID missing in JWT token. Payload: {validated_token}")
                return JsonResponse({'error': 'Tenant ID missing from token'}, status=403)

            resp = requests.get(
                f"{settings.AUTH_SERVICE_URL}/api/tenant/tenants/{tenant_id}/",
                headers={'Authorization': auth_header},
                timeout=5
            )
            if resp.status_code == 200:
                tenant = resp.json()
                request.tenant = tenant
                request.tenant_id = tenant_id
                logger.info(f"Tenant set from AUTH_SERVICE: {tenant.get('schema_name', '')} (ID: {tenant_id})")
            else:
                logger.error(f"Tenant {tenant_id} not found in AUTH_SERVICE. Status: {resp.status_code}")
                return JsonResponse({'error': 'Invalid tenant'}, status=404)

            if not hasattr(request, 'user') or isinstance(request.user, AnonymousUser):
                request.user = SimpleUser(validated_token)
                logger.info(f"Set request.user from CustomTenantMiddleware: {request.user}, is_authenticated: {request.user.is_authenticated}")

        except InvalidToken as e:
            logger.error(f"Invalid JWT token: {str(e)} | Token: {token_str}")
            return JsonResponse({'error': 'Unauthorized - Invalid Token'}, status=401)
        except Exception as e:
            logger.exception("Unexpected error decoding JWT token.")
            return JsonResponse({'error': 'Unauthorized'}, status=401)

        response = self.get_response(request)
        logger.info(f"After CustomTenantMiddleware response: request.user={request.user}, is_authenticated={getattr(request.user, 'is_authenticated', False)}")
        return response

class MicroserviceJWTAuthentication(BaseAuthentication):
    def authenticate(self, request):
        # Only check if '_user' is set, not 'user' property
        if hasattr(request, '_user') and request._user and not isinstance(request._user, AnonymousUser):
            return (request._user, None)
        # Otherwise, let the middleware handle it (this should already be done)
        auth = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth.startswith('Bearer '):
            return None
        token = auth.split(' ')[1]
        try:
            payload = jwt.decode(
                token,
                settings.SIMPLE_JWT['SIGNING_KEY'],
                algorithms=[settings.SIMPLE_JWT['ALGORITHM']]
            )
            user = SimpleUser(payload)
            return (user, None)
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return None
        except Exception as e:
            logger.error(f"JWT authentication error: {str(e)}")
            return None