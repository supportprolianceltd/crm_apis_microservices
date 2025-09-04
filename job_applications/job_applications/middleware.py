import jwt
import requests
import logging
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin
from rest_framework.exceptions import AuthenticationFailed
from django.http import JsonResponse
from django.db import connection

logger = logging.getLogger('job_applications')

class SimpleUser:
    is_authenticated = True
    is_active = True
    is_anonymous = False
    def __init__(self, payload):
        self.id = payload.get('user_id')
        self.tenant_id = payload.get('tenant_id')
        self.role = payload.get('role')
        self.branch = payload.get('branch')
        self.email = payload.get('email', '')
        self.username = payload.get('username', '')
    def save(self, *args, **kwargs): pass  # For compatibility
    
class MicroserviceJWTMiddleware(MiddlewareMixin):
    def process_request(self, request):
        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            return
        token = auth.split(' ')[1]
        try:
            payload = jwt.decode(token, settings.SIMPLE_JWT['SIGNING_KEY'], algorithms=[settings.SIMPLE_JWT['ALGORITHM']])
        except Exception:
            raise AuthenticationFailed('Invalid JWT token')
        request.jwt_payload = payload
        request.user = None



class CustomTenantMiddleware:
    """
    Middleware to resolve tenant from JWT token for multi-tenant setup.
    Handles:
      - Public endpoints using public schema
      - Tenant extraction from JWT
      - Fallback to AUTH_SERVICE if tenant not found locally
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        logger.info(f"Incoming request path: {request.path}")
        logger.info(f"Authorization header: {request.META.get('HTTP_AUTHORIZATION')}")

        # -------------------------------
        # Step 1: Handle public endpoints
        # -------------------------------
        public_paths = ['/api/docs/', '/api/schema/', '/api/health/']
        if any(request.path.startswith(path) for path in public_paths):
            public_tenant = get_tenant_model().objects.get(schema_name=get_public_schema_name())
            request.tenant = public_tenant
            request.tenant_id = public_tenant.id
            connection.set_schema(public_tenant.schema_name)
            logger.info(f"Set public schema for path: {public_tenant.schema_name}")
            return self.get_response(request)

        # -------------------------------
        # Step 2: Extract tenant from JWT safely
        # -------------------------------
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith("Bearer "):
            logger.warning("Authorization header missing Bearer prefix.")
            return JsonResponse({'error': 'Unauthorized'}, status=401)

        token_str = auth_header.split(" ")[1]

        try:
            # Log signing key for debugging (remove in production)
            logger.info(f"Using SIGNING_KEY: {settings.SIMPLE_JWT.get('SIGNING_KEY')}")

            # Decode token manually
            validated_token = JWTAuthentication().get_validated_token(token_str)

            tenant_id = validated_token.get('tenant_id')
            tenant_schema = validated_token.get('tenant_schema')
            user_id = validated_token.get('user_id')

            if not tenant_id:
                logger.error(f"Tenant ID missing in JWT token. Payload: {validated_token}")
                return JsonResponse({'error': 'Tenant ID missing from token'}, status=403)

            # -------------------------------
            # Step 3: Lookup tenant in DB
            # -------------------------------
            try:
                tenant = get_tenant_model().objects.get(id=tenant_id)
                request.tenant = tenant
                request.tenant_id = tenant_id
                connection.set_schema(tenant.schema_name)
                logger.info(f"Tenant set from token: {tenant.schema_name} (ID: {tenant_id})")

            except get_tenant_model().DoesNotExist:
                # Optional: fetch tenant from AUTH_SERVICE if not found locally
                try:
                    response = requests.get(
                        f"{settings.AUTH_SERVICE_URL}/api/tenants/{tenant_id}/",
                        headers={'Authorization': auth_header},
                        timeout=5
                    )
                    if response.status_code == 200:
                        tenant_data = response.json()
                        tenant, _ = get_tenant_model().objects.get_or_create(
                            id=tenant_id,
                            defaults={
                                'name': tenant_data.get('name', ''),
                                'schema_name': tenant_data.get('schema_name', tenant_schema or f'tenant_{tenant_id}')
                            }
                        )
                        request.tenant = tenant
                        request.tenant_id = tenant_id
                        connection.set_schema(tenant.schema_name)
                        logger.info(f"Tenant created from AUTH service: {tenant.schema_name}")
                    else:
                        logger.error(f"Tenant {tenant_id} not found in AUTH service. Status: {response.status_code}")
                        return JsonResponse({'error': 'Invalid tenant'}, status=404)
                except requests.RequestException as e:
                    import jwt
                    from django.conf import settings
                    from django.utils.deprecation import MiddlewareMixin
                    from rest_framework.exceptions import AuthenticationFailed

                    class MicroserviceJWTMiddleware(MiddlewareMixin):
                        def process_request(self, request):
                            auth = request.headers.get('Authorization', '')
                            if not auth.startswith('Bearer '):
                                return
                            token = auth.split(' ')[1]
                            try:
                                payload = jwt.decode(token, settings.SIMPLE_JWT['SIGNING_KEY'], algorithms=[settings.SIMPLE_JWT['ALGORITHM']])
                            except Exception:
                                raise AuthenticationFailed('Invalid JWT token')
                            request.jwt_payload = payload
                            # Optionally, set request.user to a proxy or None
                            request.user = None
        except InvalidToken as e:
            logger.error(f"Invalid JWT token: {str(e)} | Token: {token_str}")
            return JsonResponse({'error': 'Unauthorized - Invalid Token'}, status=401)
        except Exception as e:
            logger.exception("Unexpected error decoding JWT token.")
            return JsonResponse({'error': 'Unauthorized'}, status=401)

        # -------------------------------
        # Step 4: Continue request processing
        # -------------------------------
        return self.get_response(request)

class MicroserviceRS256JWTMiddleware(MiddlewareMixin):
    """
    Middleware to decode RS256 JWTs using the public key fetched from the Auth Service by 'kid'.
    """
    def process_request(self, request):
        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            return
        token = auth.split(' ')[1]
        try:
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")
            if not kid:
                raise AuthenticationFailed("No 'kid' in token header.")

            # Decode token without verifying to get tenant_id and tenant_schema
            unverified_payload = jwt.decode(token, options={"verify_signature": False})
            tenant_id = unverified_payload.get("tenant_id")
            tenant_schema = unverified_payload.get("tenant_schema")

            # Fetch public key from Auth Service
            resp = requests.get(
                f"{settings.AUTH_SERVICE_URL}/api/public-key/{kid}/?tenant_id={tenant_id}",
                timeout=5
            )
            if resp.status_code != 200:
                logger.error(f"Public key fetch failed: {resp.status_code} {resp.text}")
                raise AuthenticationFailed("Could not fetch public key for token.")

            public_key = resp.json().get("public_key")
            if not public_key:
                raise AuthenticationFailed("Public key not found.")

            payload = jwt.decode(token, public_key, algorithms=["RS256"])
            request.jwt_payload = payload
            request.user = SimpleUser(payload)  # <-- Set user here!

        except jwt.ExpiredSignatureError:
            return JsonResponse({'error': 'Token has expired'}, status=401)
        except jwt.InvalidTokenError as e:
            return JsonResponse({'error': f'Invalid token: {str(e)}'}, status=401)
        except Exception as e:
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
        public_paths = ['/api/docs/', '/api/schema/', '/api/health/']
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