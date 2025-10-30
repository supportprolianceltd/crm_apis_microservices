
# from rest_framework.authentication import BaseAuthentication
# from rest_framework import exceptions
# from django.contrib.auth import get_user_model
# from users.models import RSAKeyPair, CustomUser
# from django_tenants.utils import tenant_context
# import jwt
# import logging

# logger = logging.getLogger(__name__)

# class RS256TenantJWTAuthentication(BaseAuthentication):
#     keyword = "Bearer"

#     def authenticate(self, request):
#         auth_header = request.headers.get("Authorization", "")
#         if not auth_header.startswith(self.keyword + " "):
#             return None

#         token = auth_header[len(self.keyword) + 1 :]
#         try:
#             # Extract kid from JWT header
#             unverified_header = jwt.get_unverified_header(token)
#             kid = unverified_header.get("kid")
#             if not kid:
#                 raise exceptions.AuthenticationFailed("No 'kid' in token header.")

#             # Get the keypair and tenant
#             keypair = RSAKeyPair.objects.filter(kid=kid, active=True).first()
#             if not keypair:
#                 raise exceptions.AuthenticationFailed("Invalid token key.")

#             public_key = keypair.public_key_pem

#             # Decode and verify the JWT
#             with tenant_context(keypair.tenant):
#                 payload = jwt.decode(token, public_key, algorithms=["RS256"])

#                 # Get the user (by email or sub)
#                 email = payload.get("sub")
#                 if not email:
#                     raise exceptions.AuthenticationFailed("No subject in token.")

#                 user = get_user_model().objects.filter(email=email, tenant=keypair.tenant).first()
#                 if not user:
#                     raise exceptions.AuthenticationFailed("User not found.")

#                 # Log impersonation usage if applicable
#                 if payload.get("impersonated_by"):
#                     logger.info(f"Impersonated token used by {payload['impersonated_by']} for user {email} in tenant {keypair.tenant.schema_name}")

#                 # Attach tenant to request for downstream use
#                 request.tenant = keypair.tenant

#                 return (user, payload)
#         except jwt.ExpiredSignatureError:
#             raise exceptions.AuthenticationFailed("Token has expired.")
#         except jwt.InvalidTokenError as e:
#             raise exceptions.AuthenticationFailed(f"Invalid token: {str(e)}")
        


# from django.contrib.auth.backends import ModelBackend
# from django.contrib.auth import get_user_model

# class UsernameModelBackend(ModelBackend):
#     def authenticate(self, request, username=None, password=None, **kwargs):
#         if username is None:
#             username = kwargs.get('username')
#         if username and password:
#             try:
#                 user = get_user_model().objects.get(username=username)
#                 if user.check_password(password) and self.user_can_authenticate(user):
#                     return user
#             except get_user_model().DoesNotExist:
#                 pass
#         return None

#     def user_can_authenticate(self, user):
#         is_active = getattr(user, 'is_active', None)
#         return is_active or super().user_can_authenticate(user)

from rest_framework.authentication import BaseAuthentication
from rest_framework import exceptions
from django.contrib.auth import get_user_model
from users.models import RSAKeyPair, CustomUser
from django_tenants.utils import tenant_context
import jwt
import logging
from core.models import UsernameIndex  # NEW: For global username auth

logger = logging.getLogger(__name__)

class RS256TenantJWTAuthentication(BaseAuthentication):
    keyword = "Bearer"

    def authenticate(self, request):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith(self.keyword + " "):
            return None

        token = auth_header[len(self.keyword) + 1 :]
        try:
            # Extract kid from JWT header
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")
            if not kid:
                raise exceptions.AuthenticationFailed("No 'kid' in token header.")

            # Get the keypair and tenant
            keypair = RSAKeyPair.objects.filter(kid=kid, active=True).first()
            if not keypair:
                raise exceptions.AuthenticationFailed("Invalid token key.")

            public_key = keypair.public_key_pem

            # Decode and verify the JWT
            with tenant_context(keypair.tenant):
                payload = jwt.decode(token, public_key, algorithms=["RS256"])

                # Get the user (by email or sub)
                email = payload.get("sub")
                if not email:
                    raise exceptions.AuthenticationFailed("No subject in token.")

                user = get_user_model().objects.filter(email=email, tenant=keypair.tenant).first()
                if not user:
                    raise exceptions.AuthenticationFailed("User not found.")

                # Log impersonation usage if applicable
                if payload.get("impersonated_by"):
                    logger.info(f"Impersonated token used by {payload['impersonated_by']} for user {email} in tenant {keypair.tenant.schema_name}")

                # Attach tenant to request for downstream use
                request.tenant = keypair.tenant

                return (user, payload)
        except jwt.ExpiredSignatureError:
            raise exceptions.AuthenticationFailed("Token has expired.")
        except jwt.InvalidTokenError as e:
            raise exceptions.AuthenticationFailed(f"Invalid token: {str(e)}")

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

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