# complete_lms/middleware.py
import jwt
import requests
import logging
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin
from rest_framework.exceptions import AuthenticationFailed
from django.http import JsonResponse
from django.db import connection
from django_tenants.utils import get_tenant_model  # Import Tenant model

logger = logging.getLogger('complete_lms')

from django.contrib.auth.models import AnonymousUser
from rest_framework.exceptions import AuthenticationFailed

public_paths = ['/api/docs/', '/api/schema/', '/api/health/']

TenantModel = get_tenant_model()  # shared.Tenant

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
        self._auth = None  # For DRF compatibility

    def __str__(self):
        return self.username or self.email

    def get_all_permissions(self):
        return set()  # For DRF compatibility

class MicroserviceRS256JWTMiddleware(MiddlewareMixin):
    def process_request(self, request):
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
                timeout=5
            )
            logger.info(f"Public key response: {resp.status_code} {resp.text}")
            if resp.status_code != 200:
                logger.error(f"Failed to fetch public key: {resp.status_code} {resp.text}")
                raise AuthenticationFailed(f"Could not fetch public key: {resp.status_code} {resp.text}")

            public_key = resp.json().get("public_key")
            if not public_key:
                raise AuthenticationFailed("Public key not found.")

            payload = jwt.decode(token, public_key, algorithms=["RS256"])
            request.jwt_payload = payload
            request.user = SimpleUser(payload)
            logger.info(f"Set request.user: {request.user}, is_authenticated={request.user.is_authenticated}")

        except jwt.ExpiredSignatureError:
            return JsonResponse({'error': 'Token has expired'}, status=401)
        except jwt.InvalidTokenError as e:
            return JsonResponse({'error': f'Invalid token: {str(e)}'}, status=401)
        except Exception as e:
            logger.error(f"JWT error: {str(e)}")
            return JsonResponse({'error': f'JWT error: {str(e)}'}, status=401)

class CustomTenantSchemaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        logger.info(f"Incoming request path: {request.path}")
        logger.info(f"Authorization header: {request.META.get('HTTP_AUTHORIZATION')}")

        if any(request.path.startswith(path) for path in public_paths):
            connection.set_schema_to_public()
            logger.info("Set public schema for public endpoint")
            return self.get_response(request)

        jwt_payload = getattr(request, 'jwt_payload', None)
        tenant_id = None
        tenant_schema = None
        if jwt_payload:
            tenant_id = jwt_payload.get('tenant_id')
            tenant_schema = jwt_payload.get('tenant_schema')
        if not tenant_id or not tenant_schema:
            logger.error("Tenant ID or schema missing in JWT or request.")
            return JsonResponse({'error': 'Tenant ID or schema missing from token'}, status=403)

        try:
            # Fetch real Tenant instance from shared schema (public)
            connection.set_schema_to_public()  # Ensure we're in public for Tenant lookup
            tenant = TenantModel.objects.get(id=tenant_id, schema_name=tenant_schema)
            request.tenant = tenant  # Set full Tenant instance
            connection.set_schema(tenant_schema)  # Switch to tenant schema
            logger.info(f"Set tenant: {tenant.schema_name} (ID: {tenant.id})")
        except TenantModel.DoesNotExist:
            logger.error(f"Tenant not found: ID={tenant_id}, schema={tenant_schema}")
            return JsonResponse({'error': 'Invalid tenant'}, status=404)
        except Exception as e:
            logger.error(f"Schema/tenant switch failed: {str(e)}")
            return JsonResponse({'error': 'Invalid tenant schema'}, status=404)

        return self.get_response(request)