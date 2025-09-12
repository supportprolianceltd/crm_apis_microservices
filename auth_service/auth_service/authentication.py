# from rest_framework.authentication import BaseAuthentication
# from rest_framework import exceptions
# from django.contrib.auth import get_user_model
# from users.models import RSAKeyPair, CustomUser
# import jwt

# class RS256TenantJWTAuthentication(BaseAuthentication):
#     keyword = "Bearer"

#     def authenticate(self, request):
#         auth_header = request.headers.get("Authorization", "")
#         if not auth_header.startswith(self.keyword + " "):
#             return None

#         token = auth_header[len(self.keyword) + 1 :]
#         try:
#             # 1. Extract kid from JWT header
#             unverified_header = jwt.get_unverified_header(token)
#             kid = unverified_header.get("kid")
#             if not kid:
#                 raise exceptions.AuthenticationFailed("No 'kid' in token header.")

#             # 2. Get the keypair and tenant
#             keypair = RSAKeyPair.objects.filter(kid=kid, active=True).first()
#             if not keypair:
#                 raise exceptions.AuthenticationFailed("Invalid token key.")

#             public_key = keypair.public_key_pem

#             # 3. Decode and verify the JWT
#             payload = jwt.decode(token, public_key, algorithms=["RS256"])

#             # 4. Get the user (by email or sub)
#             email = payload.get("sub")
#             if not email:
#                 raise exceptions.AuthenticationFailed("No subject in token.")

#             user = get_user_model().objects.filter(email=email, tenant=keypair.tenant).first()
#             if not user:
#                 raise exceptions.AuthenticationFailed("User not found.")

#             # Optionally: attach tenant to request for downstream use
#             request.tenant = keypair.tenant

#             return (user, payload)
#         except jwt.ExpiredSignatureError:
#             raise exceptions.AuthenticationFailed("Token has expired.")
#         except jwt.InvalidTokenError as e:
#             raise exceptions.AuthenticationFailed(f"Invalid token: {str(e)}")


from rest_framework.authentication import BaseAuthentication
from rest_framework import exceptions
from django.contrib.auth import get_user_model
from users.models import RSAKeyPair, CustomUser
from django_tenants.utils import tenant_context
import jwt
import logging

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