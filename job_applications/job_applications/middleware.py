import logging
from django.db import connection
from django.http import JsonResponse
from rest_framework.exceptions import AuthenticationFailed
import jwt
import requests
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger('job_applications')

public_paths = [
    '/api/docs/',
    '/api/schema/',
    '/api/health/',
    '/api/applications-engine/applications/parse-resume/autofill/',  # <-- Fix here
    '/api/applications-engine/apply-jobs/',
    '/api/applications-engine/applications/code/', 
]


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
        # Add Django auth compatibility
        self.pk = self.id
        self.is_staff = (self.role == 'admin')
        self.is_superuser = (self.role == 'admin')

    def save(self, *args, **kwargs):
        pass  # For compatibility

    def get_username(self):
        return self.username
    
    



# class MicroserviceRS256JWTMiddleware(MiddlewareMixin):
#     def __init__(self, get_response):
#         self.get_response = get_response

#     def __call__(self, request):
#         logger.info("Entering MicroserviceRS256JWTMiddleware")  # <-- Added logging
#         auth = request.headers.get('Authorization', '')
#         if not auth.startswith('Bearer '):
#             logger.info("No Bearer token provided")
#             return self.get_response(request)
#         token = auth.split(' ')[1]
#         try:
#             unverified_header = jwt.get_unverified_header(token)
#             kid = unverified_header.get("kid")
#             unverified_payload = jwt.decode(token, options={"verify_signature": False})
#             tenant_id = unverified_payload.get("tenant_id")
#             tenant_schema = unverified_payload.get("tenant_schema")
#             logger.info(f"Unverified JWT: kid={kid}, tenant_id={tenant_id}, tenant_schema={tenant_schema}")

#             # Try RS256 first
#             try:
#                 if kid:
#                     public_key_url = f"{settings.AUTH_SERVICE_URL}/api/public-key/{kid}/?tenant_id={tenant_id}"
#                     logger.info(f"Fetching public key from: {public_key_url}")
#                     resp = requests.get(
#                         public_key_url,
#                         headers={'Authorization': auth},
#                         timeout=5
#                     )
#                     logger.info(f"Public key response: {resp.status_code} {resp.text}")
#                     if resp.status_code == 200:
#                         public_key = resp.json().get("public_key")
#                         if public_key:
#                             payload = jwt.decode(token, public_key, algorithms=["RS256"])
#                             request.jwt_payload = payload
#                             request.user = SimpleUser(payload)
#                             logger.info(f"Successfully decoded JWT with RS256, schema={connection.schema_name}")
#                             return self.get_response(request)
#                         else:
#                             logger.warning("Public key not found in auth-service response")
#                     else:
#                         logger.error(f"Public key fetch failed: {resp.status_code} {resp.text}")
#             except requests.RequestException as e:
#                 logger.error(f"Failed to fetch public key: {str(e)}")

#             # Fallback to HS256
#             try:
#                 payload = jwt.decode(
#                     token,
#                     settings.SIMPLE_JWT.get('SIGNING_KEY', settings.SECRET_KEY),
#                     algorithms=["HS256"]
#                 )
#                 request.jwt_payload = payload
#                 request.user = SimpleUser(payload)
#                 logger.info(f"Successfully decoded JWT with HS256 fallback, schema={connection.schema_name}")
#             except jwt.InvalidTokenError as e:
#                 logger.error(f"HS256 decoding failed: {str(e)}")
#                 raise AuthenticationFailed(f"Invalid token: {str(e)}")

#         except jwt.ExpiredSignatureError:
#             return JsonResponse({'error': 'Token has expired'}, status=401)
#         except jwt.InvalidTokenError as e:
#             return JsonResponse({'error': f'Invalid token: {str(e)}'}, status=401)
#         except Exception as e:
#             logger.error(f"JWT error: {str(e)}")
#             return JsonResponse({'error': f'JWT error: {str(e)}'}, status=401)

#         return self.get_response(request)


class MicroserviceRS256JWTMiddleware(MiddlewareMixin):
    def __call__(self, request):
        logger.info("Entering MicroserviceRS256JWTMiddleware")
        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            logger.info("No Bearer token provided")
            return self.get_response(request)
        token = auth.split(' ')[1]
        try:
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")
            unverified_payload = jwt.decode(token, options={"verify_signature": False})
            tenant_id = unverified_payload.get("tenant_id")
            tenant_schema = unverified_payload.get("tenant_schema")
            logger.info(f"Unverified JWT: kid={kid}, tenant_id={tenant_id}, tenant_schema={tenant_schema}")

            # Try RS256 first
            try:
                if kid:
                    public_key_url = f"{settings.AUTH_SERVICE_URL}/api/public-key/{kid}/?tenant_id={tenant_id}"
                    logger.info(f"Fetching public key from: {public_key_url}")
                    resp = requests.get(
                        public_key_url,
                        headers={'Authorization': auth},
                        timeout=5
                    )
                    logger.info(f"Public key response: {resp.status_code} {resp.text}")
                    if resp.status_code == 200:
                        public_key = resp.json().get("public_key")
                        if public_key:
                            payload = jwt.decode(token, public_key, algorithms=["RS256"])
                            request.jwt_payload = payload
                            request.user = SimpleUser(payload)
                            logger.info(f"Set request.user: {request.user}, is_authenticated={request.user.is_authenticated}")
                            return self.get_response(request)
                        else:
                            logger.warning("Public key not found in auth-service response")
                    else:
                        logger.error(f"Public key fetch failed: {resp.status_code} {resp.text}")
            except requests.RequestException as e:
                logger.error(f"Failed to fetch public key: {str(e)}")

            # Fallback to HS256
            try:
                payload = jwt.decode(
                    token,
                    settings.SECRET_KEY,  # Remove SIMPLE_JWT reference
                    algorithms=["HS256"]
                )
                request.jwt_payload = payload
                request.user = SimpleUser(payload)
                logger.info(f"Set request.user (HS256): {request.user}, is_authenticated={request.user.is_authenticated}")
            except jwt.InvalidTokenError as e:
                logger.error(f"HS256 decoding failed: {str(e)}")
                raise AuthenticationFailed(f"Invalid token: {str(e)}")

        except jwt.ExpiredSignatureError:
            return JsonResponse({'error': 'Token has expired'}, status=401)
        except jwt.InvalidTokenError as e:
            return JsonResponse({'error': f'Invalid token: {str(e)}'}, status=401)
        except Exception as e:
            logger.error(f"JWT error: {str(e)}")
            return JsonResponse({'error': f'JWT error: {str(e)}'}, status=401)

        return self.get_response(request)

class CustomTenantSchemaMiddleware(MiddlewareMixin):
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # logger.info("Entering CustomTenantSchemaMiddleware")
        # logger.info(f"Incoming request path: {request.path}")
        # logger.info(f"Authorization header: {request.META.get('HTTP_AUTHORIZATION')}")

        # Handle public endpoints

        if any(request.path.startswith(path) for path in public_paths):
            connection.set_schema_to_public()
            logger.info("Set public schema for public endpoint")
            return self.get_response(request)

        # Extract tenant_schema from JWT payload
        jwt_payload = getattr(request, 'jwt_payload', None)
        tenant_schema = None
        tenant_id = None
        if jwt_payload:
            tenant_schema = jwt_payload.get('tenant_schema')
            tenant_id = jwt_payload.get('tenant_id')

        if not tenant_schema or not tenant_id:
            logger.error(f"Tenant schema or ID missing in JWT: {jwt_payload}")
            return JsonResponse({'error': 'Tenant schema or ID missing from token'}, status=403)

        # Set schema directly from JWT
        try:
            connection.set_schema(tenant_schema)
            logger.info(f"Set schema to: {tenant_schema}")
        except Exception as e:
            logger.error(f"Schema switch failed: {str(e)}")
            return JsonResponse({'error': 'Invalid tenant schema'}, status=404)

        return self.get_response(request)

        
# class CustomTenantSchemaMiddleware(MiddlewareMixin):
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        logger.info("Entering CustomTenantSchemaMiddleware")  # <-- Added logging
        logger.info(f"Incoming request path: {request.path}")
        logger.info(f"Authorization header: {request.headers.get('HTTP_AUTHORIZATION')}")
        

        # Handle public endpoints
      
        if any(request.path.startswith(path) for path in public_paths):
            connection.set_schema_to_public()
            logger.info("Set public schema for public endpoint")
            return self.get_response(request)

        # Extract tenant_schema from JWT payload
        jwt_payload = getattr(request, 'jwt_payload', None)
        tenant_schema = None
        tenant_id = None
        if jwt_payload:
            tenant_schema = jwt_payload.get('tenant_schema')
            tenant_id = jwt_payload.get('tenant_id')

        if not tenant_schema or not tenant_id:
            logger.error(f"Tenant schema or ID missing in JWT: {jwt_payload}")
            return JsonResponse({'error': 'Tenant schema or ID missing from token'}, status=403)

        # Validate tenant with auth-service
        try:
            tenant_url = f"{settings.AUTH_SERVICE_URL}/api/tenant/tenants/{tenant_id}/"
            logger.info(f"Validating tenant at: {tenant_url}")
            resp = requests.get(
                tenant_url,
                # headers={'Authorization': request.META.get('HTTP_AUTHORIZATION', '')},
                headers={'Authorization': request.headers.get('Authorization', '')},
                timeout=5
            )
            # logger.info(f"Tenant validation response: {resp.status_code} {resp.text}")
            if resp.status_code != 200:
                logger.error(f"Tenant validation failed: {resp.status_code} {resp.text}")
                return JsonResponse({'error': 'Invalid tenant'}, status=404)
        except requests.RequestException as e:
            logger.error(f"Tenant validation request failed: {str(e)}")
            return JsonResponse({'error': 'Failed to validate tenant'}, status=503)

        # Switch schema
        try:
            connection.set_schema(tenant_schema)
            logger.info(f"Set schema to: {tenant_schema}")
        except Exception as e:
            logger.error(f"Schema switch failed: {str(e)}")
            return JsonResponse({'error': 'Invalid tenant schema'}, status=404)

        return self.get_response(request)