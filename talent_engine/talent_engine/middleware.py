# MicroserviceJWTMiddleware: Decodes JWT from Authorization header and attaches payload to request
import jwt
import requests
import logging
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin
from rest_framework.exceptions import AuthenticationFailed
from django.http import JsonResponse
from django.db import connection

logger = logging.getLogger('talent_engine')

from django.contrib.auth.models import AnonymousUser
from rest_framework.exceptions import AuthenticationFailed

public_paths = ['/api/docs/', '/api/schema/', '/api/health/',  
                '/api/talent-engine/requisitions/by-link/',
                '/api/talent-engine/requisitions/unique_link/',
                '/api/talent-engine/requisitions/public/published/',
                '/api/talent-engine/requisitions/public/close/']



class SimpleUser:
    def __init__(self, payload):
        self.pk = payload.get('user', {}).get('id')
        self.username = payload.get('user', {}).get('username', '')
        self.email = payload.get('email', '')
        self.role = payload.get('role', '')
        self.tenant_id = payload.get('tenant_id')
        self.tenant_schema = payload.get('tenant_schema')
        self.is_authenticated = True
        self.is_active = True
        self.is_staff = payload.get('role') in ['admin', 'staff']
        self.is_superuser = payload.get('role') == 'admin'

    def __str__(self):
        return self.username or self.email


class MicroserviceRS256JWTMiddleware(MiddlewareMixin):
    def process_request(self, request):
        # Allow public endpoints without JWT
        if any(request.path.startswith(public) for public in public_paths):
            request.user = AnonymousUser()
            return

        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            logger.info("No Bearer token provided")
            request.user = AnonymousUser()
            return

        token = auth.split(' ')[1]
        try:
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")
            if not kid:
                raise AuthenticationFailed("No 'kid' in token header.")

            unverified_payload = jwt.decode(token, options={"verify_signature": False})
            tenant_id = unverified_payload.get("tenant_id")
            tenant_schema = unverified_payload.get("tenant_schema")
            logger.info(f"Unverified JWT: kid={kid}, tenant_id={tenant_id}, tenant_schema={tenant_schema}")

            resp = requests.get(
                f"{settings.AUTH_SERVICE_URL}/api/public-key/{kid}/?tenant_id={tenant_id}",
                headers={'Authorization': auth},  # Pass the same token
                timeout=5
            )
            logger.info(f"Public key response: {resp.status_code} {resp.text}")
            if resp.status_code != 200:
                raise AuthenticationFailed(f"Could not fetch public key: {resp.status_code}")

            public_key = resp.json().get("public_key")
            if not public_key:
                raise AuthenticationFailed("Public key not found.")

            payload = jwt.decode(token, public_key, algorithms=["RS256"])
            request.jwt_payload = payload
            request.user = SimpleUser(payload)  # Set custom user
            logger.info(f"Set request.user: {request.user}, is_authenticated={request.user.is_authenticated}")

        except jwt.ExpiredSignatureError:
            return JsonResponse({'error': 'Token has expired'}, status=401)
        except jwt.InvalidTokenError as e:
            return JsonResponse({'error': f'Invalid token: {str(e)}'}, status=401)
        except Exception as e:
            logger.error(f"JWT error: {str(e)}")
            return JsonResponse({'error': f'JWT error: {str(e)}'}, status=401)


class CustomTenantSchemaMiddleware:
    """
    Middleware to switch DB schema based on tenant_schema in JWT or request data.
    No local tenant model required!
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        logger.info(f"Incoming request path: {request.path}")
        logger.info(f"Authorization header: {request.META.get('HTTP_AUTHORIZATION')}")

        # Step 1: Handle public endpoints
       
        if any(request.path.startswith(path) for path in public_paths):
            connection.set_schema_to_public()
            logger.info("Set public schema for public endpoint")
            return self.get_response(request)

        # Step 2: Extract tenant_schema from JWT payload (set by JWT middleware)
        jwt_payload = getattr(request, 'jwt_payload', None)
        tenant_schema = None
        if jwt_payload:
            tenant_schema = jwt_payload.get('tenant_schema')
        # Optionally, fallback to request.data or query params if needed

        if not tenant_schema:
            logger.error("Tenant schema missing in JWT or request.")
            return JsonResponse({'error': 'Tenant schema missing from token'}, status=403)

        # Step 3: Switch schema
        try:
            connection.set_schema(tenant_schema)
            logger.info(f"Set schema to: {tenant_schema}")
        except Exception as e:
            logger.error(f"Schema switch failed: {str(e)}")
            return JsonResponse({'error': 'Invalid tenant schema'}, status=404)

        return self.get_response(request)


