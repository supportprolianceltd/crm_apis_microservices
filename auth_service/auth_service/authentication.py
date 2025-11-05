# auth_service/authentication.py

import jwt
from django.contrib.auth.backends import ModelBackend
from rest_framework.authentication import BaseAuthentication
from rest_framework import exceptions
from django.contrib.auth import get_user_model
from django_tenants.utils import tenant_context, get_public_schema_name
from users.models import RSAKeyPair, CustomUser
from core.models import Tenant, GlobalUser, UsernameIndex  # All imports here
import logging

logger = logging.getLogger(__name__)

# auth_service/authentication.py - Enhanced RS256CookieJWTAuthentication
class RS256CookieJWTAuthentication(BaseAuthentication):
    def authenticate(self, request):
        token = request.COOKIES.get('access_token')
        if not token:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
        if not token:
            return None

        try:
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")
            if not kid:
                raise exceptions.AuthenticationFailed("No 'kid' in token header.")

            unverified_payload = jwt.decode(token, options={"verify_signature": False})
            tenant_id = unverified_payload.get("tenant_id")
            tenant_schema = unverified_payload.get("tenant_schema")
            user_type = unverified_payload.get("user_type", "tenant")  # Get user type
            
            if not tenant_id or not tenant_schema:
                raise exceptions.AuthenticationFailed("Missing tenant info in token.")

            tenant = Tenant.objects.get(id=tenant_id, schema_name=tenant_schema)
            
            with tenant_context(tenant):
                keypair = RSAKeyPair.objects.filter(kid=kid, active=True).first()
                if not keypair:
                    raise exceptions.AuthenticationFailed("Invalid token key.")

                public_key = keypair.public_key_pem
                payload = jwt.decode(token, public_key, algorithms=["RS256"])

                email = payload.get("sub")
                if not email:
                    raise exceptions.AuthenticationFailed("No subject in token.")

                # Get user based on type
                user = None
                if user_type == "global":
                    user = GlobalUser.objects.filter(email=email).first()
                else:
                    user = CustomUser.objects.filter(email=email, tenant=tenant).first()
                    
                if not user:
                    raise exceptions.AuthenticationFailed("User not found.")

                # Attach tenant to user for consistency
                user.tenant = tenant
                request.tenant = tenant

                return (user, payload)
                
        except Tenant.DoesNotExist:
            raise exceptions.AuthenticationFailed("Invalid tenant in token.")
        except jwt.ExpiredSignatureError:
            raise exceptions.AuthenticationFailed("Token has expired.")
        except jwt.InvalidTokenError as e:
            raise exceptions.AuthenticationFailed(f"Invalid token: {str(e)}")


class RS256TenantJWTAuthentication(BaseAuthentication):
    """
    JWT authentication using RS256 with tenant context.
    This should NOT be used for token obtain endpoints.
    """
    keyword = "Bearer"

    def authenticate(self, request):
        # Skip authentication for public endpoints (CRITICAL FIX)
        public_paths = [
            '/api/token/', 
            '/api/login/', 
            '/api/token/refresh/', 
            '/api/user/password/reset/',
            '/api/user/public-register/',
            '/api/verify-2fa/'
        ]
        
        # Check if this is a public endpoint that should skip authentication
        if any(request.path.startswith(path) for path in public_paths):
            logger.debug(f"Skipping authentication for public path: {request.path}")
            return None
            
        # Also skip if this is the token obtain endpoint (double protection)
        if request.path in ['/api/token/', '/api/login/'] and request.method == 'POST':
            logger.debug(f"Skipping authentication for token obtain endpoint: {request.path}")
            return None

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith(self.keyword + " "):
            # No Bearer token found - let other authentication classes try
            return None

        token = auth_header[len(self.keyword) + 1 :]
        
        try:
            # Extract kid from unverified JWT header
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")
            if not kid:
                logger.warning("No 'kid' found in JWT header")
                return None

            # Extract tenant info from unverified payload to find the right keypair
            unverified_payload = jwt.decode(token, options={"verify_signature": False})
            tenant_id = unverified_payload.get("tenant_id")
            tenant_schema = unverified_payload.get("tenant_schema")
            
            if not tenant_id or not tenant_schema:
                logger.warning("Missing tenant_id or tenant_schema in token payload")
                return None

            # Get the tenant
            try:
                tenant = Tenant.objects.get(id=tenant_id, schema_name=tenant_schema)
            except Tenant.DoesNotExist:
                logger.warning(f"Tenant not found: id={tenant_id}, schema={tenant_schema}")
                return None

            # Get active keypair in the tenant's schema
            with tenant_context(tenant):
                keypair = RSAKeyPair.objects.filter(kid=kid, active=True).first()
                if not keypair:
                    logger.warning(f"No active RSAKeyPair found for kid={kid} in tenant {tenant.schema_name}")
                    return None

                public_key = keypair.public_key_pem

                # Now verify the token signature with the correct public key
                payload = jwt.decode(token, public_key, algorithms=["RS256"])
                
                # Get user from the verified payload
                email = payload.get("sub")
                if not email:
                    logger.warning("No subject (sub) in token payload")
                    return None

                # Get the user within tenant context
                user = CustomUser.objects.filter(email=email, tenant=tenant).first()
                if not user:
                    # Fallback for public tenant global admin
                    if tenant.schema_name == get_public_schema_name():
                        user = GlobalUser.objects.filter(email=email).first()
                        if user:
                            # Attach tenant for consistency
                            user.tenant = tenant
                    if not user:
                        logger.warning(f"User not found: {email} in tenant {tenant.schema_name}")
                        return None

                # Log impersonation if present
                if payload.get("impersonated_by"):
                    logger.info(f"Impersonated token used by {payload['impersonated_by']} for user {email} in tenant {tenant.schema_name}")

                # Attach tenant to request for downstream use
                request.tenant = tenant

                return (user, payload)
                
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in RS256TenantJWTAuthentication: {str(e)}")
            return None

    def authenticate_header(self, request):
        return self.keyword
    

class UsernameModelBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get('username')
        if username and password:
            try:
                # Global resolution via index
                index_entry = UsernameIndex.objects.get(username=username)
                target_tenant = index_entry.tenant
                with tenant_context(target_tenant):  # Switch schema
                    user = get_user_model().objects.get(id=index_entry.user_id)
                    if user.check_password(password) and self.user_can_authenticate(user):
                        # Attach tenant to request if needed
                        if hasattr(request, 'tenant'):
                            request.tenant = target_tenant
                        return user
            except (UsernameIndex.DoesNotExist, get_user_model().DoesNotExist):
                pass
        return None

    def user_can_authenticate(self, user):
        is_active = getattr(user, 'is_active', None)
        return is_active or super().user_can_authenticate(user)

# auth_service/authentication.py - Enhanced backend
class GlobalUserBackend(ModelBackend):
    """
    Backend for authenticating GlobalUser in public schema (platform super-admins).
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get('username') or kwargs.get('email')
        
        if username and password:
            try:
                # Get public tenant
                public_schema = get_public_schema_name()
                public_tenant = Tenant.objects.get(schema_name=public_schema)
                
                with tenant_context(public_tenant):
                    # Try email first, then username
                    user = None
                    if '@' in username:
                        user = GlobalUser.objects.filter(email=username).first()
                    else:
                        user = GlobalUser.objects.filter(username=username).first()
                    
                    if user and user.check_password(password) and self.user_can_authenticate(user):
                        # Attach tenant for consistency
                        user.tenant = public_tenant
                        logger.info(f"✅ GlobalUser authenticated: {user.email}")
                        return user
                    elif user and user.check_password(password) and not self.user_can_authenticate(user):
                        user.increment_login_attempts()
                        
            except Tenant.DoesNotExist:
                logger.warning(f"Public tenant not found for schema: {public_schema}")
            except Exception as e:
                logger.warning(f"GlobalUser auth failed for {username}: {e}")
        return None

    def user_can_authenticate(self, user):
        """Check if user can authenticate (not locked and active)"""
        if user.is_locked():
            logger.warning(f"GlobalUser {user.email} is locked until {user.locked_until}")
            return False
        return user.is_active and super().user_can_authenticate(user)

    def get_user(self, user_id):
        try:
            public_schema = get_public_schema_name()
            public_tenant = Tenant.objects.get(schema_name=public_schema)
            with tenant_context(public_tenant):
                return GlobalUser.objects.get(pk=user_id)
        except (Tenant.DoesNotExist, GlobalUser.DoesNotExist):
            return None