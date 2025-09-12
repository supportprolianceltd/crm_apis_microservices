# import json
# from auth_service.authentication import RS256TenantJWTAuthentication
# import jwt
# import uuid
# import random
# import logging
# import requests
# from datetime import datetime, timedelta
# import requests
# from django.conf import settings
# from django.core.cache import cache
# from django.db import connection
# from django.utils import timezone
# from django.contrib.auth import get_user_model, authenticate

# from rest_framework import serializers, status
# from rest_framework.views import APIView
# from rest_framework.response import Response
# from rest_framework.permissions import IsAuthenticated, AllowAny
# from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
# from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
# from rest_framework_simplejwt.tokens import RefreshToken
# from rest_framework_simplejwt.authentication import JWTAuthentication

# from kafka import KafkaProducer

# from django_tenants.utils import tenant_context

# from core.models import Tenant
# from users.models import CustomUser, UserProfile, BlacklistedToken, RSAKeyPair
# from users.serializers import CustomUserSerializer

# from auth_service.utils.jwt_rsa import issue_rsa_jwt, decode_rsa_jwt, blacklist_refresh_token

# logger = logging.getLogger(__name__)

# class UserProfileMinimalSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = UserProfile
#         fields = [
#             "id",
#             "user",
#             "employee_id",
#             "access_duration",
#             "system_access_rostering",
#             "system_access_hr",
#             "system_access_recruitment",
#             "system_access_training",
#             "system_access_finance",
#             "system_access_compliance",
#             "system_access_co_superadmin",
#             "system_access_asset_management"
#         ]

# class CustomUserMinimalSerializer(serializers.ModelSerializer):
#     profile = UserProfileMinimalSerializer(read_only=True)

#     class Meta:
#         model = CustomUser
#         fields = [
#             "id",
#             "email",
#             "username",
#             "first_name",
#             "last_name",
#             "role",
#             "job_role",
#             "tenant",
#             "branch",
#             "has_accepted_terms",
#             "profile"
#         ]


# class TokenValidateView(APIView):
#     permission_classes = [IsAuthenticated]
#     authentication_classes = [RS256TenantJWTAuthentication]  # Use your custom backend

#     def get(self, request):
#         logger.info(f"TokenValidateView request payload: {request.headers}")
#         try:
#             user = request.user
#             tenant = getattr(request, "tenant", None)
#             with tenant_context(tenant):
#                 user_data = CustomUserSerializer(user).data
#                 response_data = {
#                     'status': 'success',
#                     'user': user_data,
#                     'tenant_id': str(tenant.id),
#                     'tenant_schema': tenant.schema_name
#                 }
#                 logger.info(f"TokenValidateView response: {response_data}")
#                 logger.info("Token validation successful")
#                 return Response(response_data, status=status.HTTP_200_OK)
#         except Exception as e:
#             logger.error(f"Token validation failed: {str(e)}")
#             logger.info("Token validation unsuccessful")
#             response_data = {
#                 'status': 'error',
#                 'message': 'Invalid or expired token.'
#             }
#             logger.info(f"TokenValidateView response: {response_data}")
#             return Response(response_data, status=status.HTTP_401_UNAUTHORIZED)
# # class TokenValidateView(APIView):
# #     permission_classes = [IsAuthenticated]
# #     authentication_classes = [JWTAuthentication]

# #     def get(self, request):
# #         try:
# #             user = request.user
# #             tenant = request.tenant
# #             with tenant_context(tenant):
# #                 user_data = CustomUserSerializer(user).data
# #                 return Response({
# #                     'status': 'success',
# #                     'user': user_data,
# #                     'tenant_id': str(tenant.id),
# #                     'tenant_schema': tenant.schema_name
# #                 }, status=status.HTTP_200_OK)
# #         except Exception as e:
# #             logger.error(f"Token validation failed: {str(e)}")
# #             return Response({
# #                 'status': 'error',
# #                 'message': 'Invalid or expired token.'
# #             }, status=status.HTTP_401_UNAUTHORIZED)


# class CustomTokenSerializer(TokenObtainPairSerializer):
#     @classmethod
#     def get_token(cls, user):
#         return super().get_token(user)

#     def validate(self, attrs):
#         user = authenticate(
#             email=attrs.get("email"),
#             password=attrs.get("password")
#         )
#         if not user:
#             raise serializers.ValidationError("Invalid credentials")

#         # Access token payload
#         access_payload = {
#             "jti": str(uuid.uuid4()),  # Unique JWT ID
#             "sub": user.email,
#             "role": user.role,
#             "tenant_id": user.tenant.id,
#             "tenant_schema": user.tenant.schema_name,
#             "has_accepted_terms": user.has_accepted_terms,
#             "user": CustomUserMinimalSerializer(user).data,
#             "email": user.email,
#             "type": "access",
#             "exp": (timezone.now() + timedelta(minutes=15)).timestamp(),
#         }
#         access_token = issue_rsa_jwt(access_payload, user.tenant)

#         # Refresh token payload
#         refresh_jti = str(uuid.uuid4())
#         refresh_payload = {
#             "jti": refresh_jti,
#             "sub": user.email,
#             "tenant_id": user.tenant.id,
#             "type": "refresh",
#             "exp": (timezone.now() + timedelta(days=7)).timestamp(),
#         }
#         refresh_token = issue_rsa_jwt(refresh_payload, user.tenant)

#         data = {
#             "access": access_token,
#             "refresh": refresh_token,
#             "tenant_id": user.tenant.id,
#             "tenant_schema": user.tenant.schema_name,
#             "user": CustomUserMinimalSerializer(user).data,
#             "has_accepted_terms": user.has_accepted_terms,
#         }
#         return data


# class CustomTokenObtainPairView(TokenObtainPairView):
#     serializer_class = CustomTokenSerializer



# class CustomTokenRefreshSerializer(TokenRefreshSerializer):
#     def validate(self, attrs):
#         user = authenticate(
#             email=attrs.get("email"),
#             password=attrs.get("password")
#         )
#         if not user:
#             raise serializers.ValidationError("Invalid credentials")

#         # Access token payload
#         access_payload = {
#             "jti": str(uuid.uuid4()),  # Unique JWT ID
#             "sub": user.email,
#             "role": user.role,
#             "tenant_id": user.tenant.id,
#             "tenant_schema": user.tenant.schema_name,
#             "has_accepted_terms": user.has_accepted_terms,
#             "user": CustomUserMinimalSerializer(user).data,
#             "email": user.email,
#             "type": "access",
#             "exp": (timezone.now() + timedelta(minutes=15)).timestamp(),
#         }
#         access_token = issue_rsa_jwt(access_payload, user.tenant)

#         # Refresh token payload
#         refresh_jti = str(uuid.uuid4())
#         refresh_payload = {
#             "jti": refresh_jti,
#             "sub": user.email,
#             "tenant_id": user.tenant.id,
#             "type": "refresh",
#             "exp": (timezone.now() + timedelta(days=7)).timestamp(),
#         }
#         refresh_token = issue_rsa_jwt(refresh_payload, user.tenant)

#         # --- Send login event notification ---
#         try:
#             request = self.context.get('request')
#             ip = request.META.get('REMOTE_ADDR', '') if request else ''
#             now_iso = timezone.now().isoformat()
#             event_payload = {
#                 "metadata": {
#                     "tenant_id": "test-tenant-1",
#                     "event_type": "user.login.succeeded",
#                     "event_id": "evt-001",
#                     "created_at": now_iso,
#                     "source": "auth-service"
#                 },
#                 "data": {
#                     "user_email": user.email,
#                     "ip": ip,
#                     "time": now_iso,
#                     "user_id": str(user.id)
#                 }
#             }
          
#             requests.post(settings.NOTIFICATIONS_EVENT_URL, json=event_payload, timeout=3)
#         except Exception as e:
#             logger.error(f"Failed to send login event notification: {e}")
#         # --- End event notification ---

#         data = {
#             "access": access_token,
#             "refresh": refresh_token,
#             "tenant_id": user.tenant.id,
#             "tenant_schema": user.tenant.schema_name,
#             "user": CustomUserMinimalSerializer(user).data,
#             "has_accepted_terms": user.has_accepted_terms,
#         }
#         return data
#     # def validate(self, attrs):
#     #     refresh = RefreshToken(attrs['refresh'])
#     #     tenant_id = refresh.get('tenant_id', None)
#     #     tenant_schema = refresh.get('tenant_schema', None)

#     #     if not tenant_id or not tenant_schema:
#     #         raise serializers.ValidationError("Invalid token: tenant info missing")

#     #     try:
#     #         tenant = Tenant.objects.get(id=tenant_id, schema_name=tenant_schema)
#     #     except Tenant.DoesNotExist:
#     #         raise serializers.ValidationError("Invalid tenant")

#     #     with tenant_context(tenant):
#     #         data = super().validate(attrs)
#     #         data['tenant_id'] = str(tenant.id)
#     #         data['tenant_schema'] = tenant.schema_name
#     #         return data



# class CustomTokenRefreshView(APIView):
#     permission_classes = [AllowAny]

#     def post(self, request):
#         refresh_token = request.data.get("refresh")
#         if not refresh_token:
#             return Response({"detail": "No refresh token provided."}, status=status.HTTP_400_BAD_REQUEST)
#         try:
#             payload = decode_rsa_jwt(refresh_token)
#             if payload.get("type") != "refresh":
#                 return Response({"detail": "Invalid token type."}, status=status.HTTP_400_BAD_REQUEST)
#             jti = payload.get("jti")
#             if BlacklistedToken.objects.filter(jti=jti).exists():
#                 return Response({"detail": "Token blacklisted."}, status=status.HTTP_401_UNAUTHORIZED)

#             # Blacklist the old refresh token (rotation)
#             exp = datetime.fromtimestamp(payload["exp"])
#             BlacklistedToken.objects.create(jti=jti, expires_at=exp)

#             # Issue new refresh token
#             user = get_user_model().objects.get(email=payload["sub"])
#             new_refresh_jti = str(uuid.uuid4())
#             refresh_payload = {
#                 "jti": new_refresh_jti,
#                 "sub": user.email,
#                 "tenant_id": user.tenant.id,
#                 "type": "refresh",
#                 "exp": (timezone.now() + timedelta(days=7)).timestamp(),
#             }
#             new_refresh_token = issue_rsa_jwt(refresh_payload, user.tenant)

#             # Issue new access token
#             access_payload = {
#                 "jti": str(uuid.uuid4()),
#                 "sub": user.email,
#                 "role": user.role,
#                 "tenant_id": user.tenant.id,
#                 "tenant_schema": user.tenant.schema_name,
#                 "has_accepted_terms": user.has_accepted_terms,
#                 "user": CustomUserMinimalSerializer(user).data,
#                 "email": user.email,
#                 "type": "access",
#                 "exp": (timezone.now() + timedelta(minutes=15)).timestamp(),
#             }
#             access_token = issue_rsa_jwt(access_payload, user.tenant)

#             return Response({
#                 "access": access_token,
#                 "refresh": new_refresh_token
#             })
#         except Exception as e:
#             return Response({"detail": str(e)}, status=status.HTTP_401_UNAUTHORIZED)



# class LoginWith2FAView(TokenObtainPairView):
#     serializer_class = CustomTokenSerializer
#     permission_classes = [AllowAny]

#     def post(self, request, *args, **kwargs):
#         serializer = self.get_serializer(data=request.data, context={'request': request})
#         try:
#             serializer.is_valid(raise_exception=True)
#         except serializers.ValidationError as e:
#             return Response(e.detail, status=status.HTTP_401_UNAUTHORIZED)

#         user = serializer.user
#         tenant = getattr(request, "tenant", None)

#         # Generate and send 2FA code
#         code = f"{random.randint(100000, 999999)}"
#         cache.set(f"2fa_{user.id}", code, timeout=300)
#         event_payload = {
#             "data": {
#                 "user_email": user.email,
#                 "2fa_code": code,
#                 "2fa_method": "email",
#                 "ip_address": request.META.get('REMOTE_ADDR', ''),
#                 "user_agent": request.META.get('HTTP_USER_AGENT', ''),
#                 "expires_in_seconds": 300
#             },
#             "metadata": {
#                 "event_id": f"evt-{uuid.uuid4()}",
#                 "event_type": "auth.2fa.code.requested",
#                 "created_at": datetime.utcnow().isoformat() + "Z",
#                 "source": "auth-service",
#                 "tenant_id": str(getattr(tenant, "id", "unknown"))
#             }
#         }
#         try:
#             requests.post(settings.NOTIFICATIONS_EVENT_URL, json=event_payload, timeout=3)
#         except Exception as e:
#             logger.error(f"Failed to send 2FA event notification: {e}")

#         # Return the code in the response (for testing/demo purposes)
#         return Response({
#             "detail": "2FA code sent to your email.",
#             "2fa_code": code
#         }, status=200)

# class Verify2FAView(APIView):
#     permission_classes = [AllowAny]
#     def post(self, request):
#         email = request.data.get("email")
#         code = request.data.get("2fa_code")
#         tenant = getattr(request, "tenant", None)
#         if not tenant:
#             return Response({"detail": "Tenant not found."}, status=400)
#         with tenant_context(tenant):
#             user = get_user_model().objects.filter(email__iexact=email, tenant=tenant).first()
#             if not user:
#                 return Response({"detail": "Invalid user."}, status=400)
#             cached_code = cache.get(f"2fa_{user.id}")
#             if not cached_code or cached_code != code:
#                 return Response({"detail": "Invalid or expired 2FA code."}, status=400)
#             refresh = RefreshToken.for_user(user)
#             access = refresh.access_token
#             data = {
#                 "refresh": str(refresh),
#                 "access": str(access),
#                 "tenant_id": user.tenant.id,
#                 "tenant_schema": user.tenant.schema_name,
#                 "user": CustomUserMinimalSerializer(user).data,
#                 "has_accepted_terms": user.has_accepted_terms
#             }
#             cache.delete(f"2fa_{user.id}")
#             return Response(data, status=200)



# class LogoutView(APIView):
#     permission_classes = [AllowAny]  # Or IsAuthenticated if you require auth

#     def post(self, request):
#         refresh_token = request.data.get("refresh")
#         if not refresh_token:
#             return Response({"detail": "No refresh token provided."}, status=status.HTTP_400_BAD_REQUEST)
#         try:
#             # Blacklist the refresh token
#             blacklist_refresh_token(refresh_token)
#             return Response({"detail": "Logged out successfully."})
#         except Exception as e:
#             return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

# # class PublicKeyView(APIView):
# #     permission_classes = []

# #     def get(self, request, kid):
# #         keypair = RSAKeyPair.objects.filter(kid=kid, active=True).first()
# #         if not keypair:
# #             return Response({"error": "Key not found"}, status=404)
# #         return Response({"public_key": keypair.public_key_pem})


# from django_tenants.utils import tenant_context
# from core.models import Tenant

# # class PublicKeyView(APIView):
# #     permission_classes = []

# #     def get(self, request, kid):
# #         tenant_id = request.GET.get("tenant_id")
# #         if tenant_id:
# #             try:
# #                 tenant = Tenant.objects.get(id=tenant_id)
# #                 with tenant_context(tenant):
# #                     keypair = RSAKeyPair.objects.filter(kid=kid, active=True).first()
# #             except Tenant.DoesNotExist:
# #                 keypair = None
# #         else:
# #             keypair = RSAKeyPair.objects.filter(kid=kid, active=True).first()

# #         if not keypair:
# #             return Response({"error": "Key not found"}, status=404)
# #         return Response({"public_key": keypair.public_key_pem})
    


# class PublicKeyView(APIView):
#     permission_classes = [AllowAny]  # Temporary for debugging

#     def get(self, request, kid):
#         tenant_id = request.query_params.get('tenant_id')
#         if not tenant_id:
#             logger.error("No tenant_id provided in query params")
#             return Response({"error": "tenant_id is required"}, status=400)

#         try:
#             tenant = Tenant.objects.get(id=tenant_id)
#             connection.set_schema(tenant.schema_name)
#             logger.info(f"Set schema to {tenant.schema_name} for kid={kid}")
#             keypair = RSAKeyPair.objects.get(kid=kid, tenant=tenant, active=True)
#             return Response({"public_key": keypair.public_key_pem})
#         except Tenant.DoesNotExist:
#             logger.error(f"Tenant not found: id={tenant_id}")
#             return Response({"error": "Tenant not found"}, status=404)
#         except RSAKeyPair.DoesNotExist:
#             logger.error(f"No RSAKeyPair found for kid={kid} in schema={tenant.schema_name}")
#             return Response({"error": "Keypair not found"}, status=404)



# from jose import jwk as jose_jwk
# from django_tenants.utils import tenant_context
# from rest_framework.views import APIView
# from rest_framework.response import Response
# from rest_framework.permissions import AllowAny

# class JWKSView(APIView):
#     permission_classes = [AllowAny]

#     def get(self, request):
#         jwks = {"keys": []}
#         tenants = Tenant.objects.all()
#         for tenant in tenants:
#             with tenant_context(tenant):
#                 for keypair in RSAKeyPair.objects.filter(active=True):
#                     rsa_key = jose_jwk.RSAKey(key=keypair.public_key_pem, algorithm='RS256')
#                     pub_jwk = rsa_key.to_dict()
#                     pub_jwk['kid'] = keypair.kid
#                     pub_jwk['use'] = 'sig'
#                     pub_jwk['alg'] = 'RS256'
#                     jwks["keys"].append(pub_jwk)
#         return Response(jwks)
    

# from rest_framework.permissions import IsAuthenticated
# from rest_framework.views import APIView
# from rest_framework.response import Response
# from django.utils import timezone
# from datetime import timedelta

# class JitsiTokenView(APIView):
#     permission_classes = [IsAuthenticated]

#     def post(self, request):
#         room = request.data.get('room')
#         moderator = request.data.get('moderator', True)
#         if not room:
#             return Response({"error": "Room name required"}, status=400)
#         user = request.user
#         tenant = request.tenant
#         payload = {
#             "context": {
#                 "user": {
#                     "name": f"{user.first_name} {user.last_name}",
#                     "email": user.email,
#                     "moderator": moderator,
#                 },
#             },
#             "room": room,
#             "sub": "server1.prolianceltd.com",
#             "iss": "crm-app",
#             "aud": "jitsi",
#             "exp": int((timezone.now() + timedelta(hours=1)).timestamp()),
#             "iat": int(timezone.now().timestamp()),
#         }
#         token = issue_rsa_jwt(payload, tenant)
#         return Response({"token": token})

import json
from auth_service.authentication import RS256TenantJWTAuthentication
import jwt
import uuid
import random
import logging
import requests
from datetime import datetime, timedelta
from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.utils import timezone
from django.contrib.auth import get_user_model, authenticate
from rest_framework import serializers, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.authentication import JWTAuthentication
from kafka import KafkaProducer
from django_tenants.utils import tenant_context
from core.models import Tenant
from users.models import CustomUser, UserProfile, BlacklistedToken, RSAKeyPair, UserActivity,BlockedIP
from users.serializers import CustomUserSerializer
from auth_service.utils.jwt_rsa import issue_rsa_jwt, decode_rsa_jwt, blacklist_refresh_token

logger = logging.getLogger(__name__)

class UserProfileMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = [
            "id",
            "user",
            "employee_id",
            "access_duration",
            "system_access_rostering",
            "system_access_hr",
            "system_access_recruitment",
            "system_access_training",
            "system_access_finance",
            "system_access_compliance",
            "system_access_co_superadmin",
            "system_access_asset_management"
        ]

class CustomUserMinimalSerializer(serializers.ModelSerializer):
    profile = UserProfileMinimalSerializer(read_only=True)

    class Meta:
        model = CustomUser
        fields = [
            "id",
            "email",
            "username",
            "first_name",
            "last_name",
            "role",
            "job_role",
            "tenant",
            "branch",
            "is_locked",
            "has_accepted_terms",
            "profile"
        ]

class TokenValidateView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [RS256TenantJWTAuthentication]

    def get(self, request):
        logger.info(f"TokenValidateView request payload: {request.headers}")
        try:
            user = request.user
            tenant = getattr(request, "tenant", None)
            with tenant_context(tenant):
                user_data = CustomUserSerializer(user).data
                response_data = {
                    'status': 'success',
                    'user': user_data,
                    'tenant_id': str(tenant.id),
                    'tenant_schema': tenant.schema_name
                }
                logger.info(f"TokenValidateView response: {response_data}")
                logger.info("Token validation successful")
                return Response(response_data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Token validation failed: {str(e)}")
            logger.info("Token validation unsuccessful")
            response_data = {
                'status': 'error',
                'message': 'Invalid or expired token.'
            }
            logger.info(f"TokenValidateView response: {response_data}")
            return Response(response_data, status=status.HTTP_401_UNAUTHORIZED)

class CustomTokenSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        return super().get_token(user)

    def validate(self, attrs):
        ip_address = self.context['request'].META.get('REMOTE_ADDR')
        user_agent = self.context['request'].META.get('HTTP_USER_AGENT', '')
        tenant = self.context['request'].tenant

        with tenant_context(tenant):
            user = authenticate(
                email=attrs.get("email"),
                password=attrs.get("password")
            )
            if not user:
                UserActivity.objects.create(
                    user=None,
                    tenant=tenant,
                    action='login',
                    performed_by=None,
                    details={'reason': 'Invalid credentials'},
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False
                )
                raise serializers.ValidationError("Invalid credentials")

            if user.is_locked or not user.is_active:
                UserActivity.objects.create(
                    user=user,
                    tenant=tenant,
                    action='login',
                    performed_by=None,
                    details={'reason': 'Account locked or suspended'},
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False
                )
                raise serializers.ValidationError("Account is locked or suspended")

            if BlockedIP.objects.filter(ip_address=ip_address, tenant=tenant, is_active=True).exists():
                UserActivity.objects.create(
                    user=user,
                    tenant=tenant,
                    action='login',
                    performed_by=None,
                    details={'reason': 'IP address blocked'},
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False
                )
                raise serializers.ValidationError("This IP address is blocked")

            user.reset_login_attempts()
            UserActivity.objects.create(
                user=user,
                tenant=tenant,
                action='login',
                performed_by=None,
                details={},
                ip_address=ip_address,
                user_agent=user_agent,
                success=True
            )

            access_payload = {
                "jti": str(uuid.uuid4()),
                "sub": user.email,
                "role": user.role,
                "tenant_id": user.tenant.id,
                "tenant_schema": user.tenant.schema_name,
                "has_accepted_terms": user.has_accepted_terms,
                "user": CustomUserMinimalSerializer(user).data,
                "email": user.email,
                "type": "access",
                "exp": (timezone.now() + timedelta(minutes=15)).timestamp(),
            }
            access_token = issue_rsa_jwt(access_payload, user.tenant)

            refresh_jti = str(uuid.uuid4())
            refresh_payload = {
                "jti": refresh_jti,
                "sub": user.email,
                "tenant_id": user.tenant.id,
                "type": "refresh",
                "exp": (timezone.now() + timedelta(days=7)).timestamp(),
            }
            refresh_token = issue_rsa_jwt(refresh_payload, user.tenant)

            data = {
                "access": access_token,
                "refresh": refresh_token,
                "tenant_id": user.tenant.id,
                "tenant_schema": user.tenant.schema_name,
                "user": CustomUserMinimalSerializer(user).data,
                "has_accepted_terms": user.has_accepted_terms,
            }
            return data

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenSerializer

class CustomTokenRefreshView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        ip_address = request.META.get('REMOTE_ADDR')
        user_agent = request.META.get('HTTP_USER_AGENT', '')

        if not refresh_token:
            UserActivity.objects.create(
                user=None,
                tenant=Tenant.objects.first(),  # Fallback tenant
                action='login',
                performed_by=None,
                details={'reason': 'No refresh token provided'},
                ip_address=ip_address,
                user_agent=user_agent,
                success=False
            )
            return Response({"detail": "No refresh token provided."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            payload = decode_rsa_jwt(refresh_token)
            if payload.get("type") != "refresh":
                UserActivity.objects.create(
                    user=None,
                    tenant=Tenant.objects.first(),
                    action='login',
                    performed_by=None,
                    details={'reason': 'Invalid token type'},
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False
                )
                return Response({"detail": "Invalid token type."}, status=status.HTTP_400_BAD_REQUEST)
            jti = payload.get("jti")
            if BlacklistedToken.objects.filter(jti=jti).exists():
                UserActivity.objects.create(
                    user=None,
                    tenant=Tenant.objects.first(),
                    action='login',
                    performed_by=None,
                    details={'reason': 'Token blacklisted'},
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False
                )
                return Response({"detail": "Token blacklisted."}, status=status.HTTP_401_UNAUTHORIZED)

            exp = datetime.fromtimestamp(payload["exp"])
            BlacklistedToken.objects.create(jti=jti, expires_at=exp)

            user = get_user_model().objects.get(email=payload["sub"])
            tenant = user.tenant
            with tenant_context(tenant):
                UserActivity.objects.create(
                    user=user,
                    tenant=tenant,
                    action='login',
                    performed_by=None,
                    details={'reason': 'Token refresh'},
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=True
                )
                new_refresh_jti = str(uuid.uuid4())
                refresh_payload = {
                    "jti": new_refresh_jti,
                    "sub": user.email,
                    "tenant_id": user.tenant.id,
                    "type": "refresh",
                    "exp": (timezone.now() + timedelta(days=7)).timestamp(),
                }
                new_refresh_token = issue_rsa_jwt(refresh_payload, user.tenant)

                access_payload = {
                    "jti": str(uuid.uuid4()),
                    "sub": user.email,
                    "role": user.role,
                    "tenant_id": user.tenant.id,
                    "tenant_schema": user.tenant.schema_name,
                    "has_accepted_terms": user.has_accepted_terms,
                    "user": CustomUserMinimalSerializer(user).data,
                    "email": user.email,
                    "type": "access",
                    "exp": (timezone.now() + timedelta(minutes=15)).timestamp(),
                }
                access_token = issue_rsa_jwt(access_payload, user.tenant)

                return Response({
                    "access": access_token,
                    "refresh": new_refresh_token
                })
        except Exception as e:
            UserActivity.objects.create(
                user=None,
                tenant=Tenant.objects.first(),
                action='login',
                performed_by=None,
                details={'reason': f"Token refresh failed: {str(e)}"},
                ip_address=ip_address,
                user_agent=user_agent,
                success=False
            )
            return Response({"detail": str(e)}, status=status.HTTP_401_UNAUTHORIZED)

class LoginWith2FAView(TokenObtainPairView):
    serializer_class = CustomTokenSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        ip_address = request.META.get('REMOTE_ADDR')
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        tenant = getattr(request, "tenant", None)

        if not tenant:
            UserActivity.objects.create(
                user=None,
                tenant=Tenant.objects.first(),
                action='login',
                performed_by=None,
                details={'reason': 'Tenant not found'},
                ip_address=ip_address,
                user_agent=user_agent,
                success=False
            )
            return Response({"detail": "Tenant not found."}, status=status.HTTP_400_BAD_REQUEST)

        with tenant_context(tenant):
            serializer = self.get_serializer(data=request.data, context={'request': request})
            try:
                serializer.is_valid(raise_exception=True)
            except serializers.ValidationError as e:
                user = CustomUser.objects.filter(email=request.data.get("email")).first()
                UserActivity.objects.create(
                    user=user,
                    tenant=tenant,
                    action='login',
                    performed_by=None,
                    details={'reason': f"Invalid credentials: {str(e)}"},
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False
                )
                return Response(e.detail, status=status.HTTP_401_UNAUTHORIZED)

            user = serializer.user
            if user.is_locked or user.status == 'suspended' or not user.is_active:
                UserActivity.objects.create(
                    user=user,
                    tenant=tenant,
                    action='login',
                    performed_by=None,
                    details={'reason': 'Account locked or suspended'},
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False
                )
                return Response({"detail": "Account is locked or suspended."}, status=status.HTTP_403_FORBIDDEN)

            if BlockedIP.objects.filter(ip_address=ip_address, tenant=tenant, is_active=True).exists():
                UserActivity.objects.create(
                    user=user,
                    tenant=tenant,
                    action='login',
                    performed_by=None,
                    details={'reason': 'IP address blocked'},
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False
                )
                return Response({"detail": "This IP address is blocked."}, status=status.HTTP_403_FORBIDDEN)

            code = f"{random.randint(100000, 999999)}"
            cache.set(f"2fa_{user.id}", code, timeout=300)
            event_payload = {
                "data": {
                    "user_email": user.email,
                    "2fa_code": code,
                    "2fa_method": "email",
                    "ip_address": ip_address,
                    "user_agent": user_agent,
                    "expires_in_seconds": 300
                },
                "metadata": {
                    "event_id": f"evt-{uuid.uuid4()}",
                    "event_type": "auth.2fa.code.requested",
                    "created_at": datetime.utcnow().isoformat() + "Z",
                    "source": "auth-service",
                    "tenant_id": str(getattr(tenant, "id", "unknown"))
                }
            }
            try:
                requests.post(settings.NOTIFICATIONS_EVENT_URL, json=event_payload, timeout=3)
            except Exception as e:
                logger.error(f"Failed to send 2FA event notification: {e}")

            UserActivity.objects.create(
                user=user,
                tenant=tenant,
                action='login',
                performed_by=None,
                details={'reason': '2FA code sent'},
                ip_address=ip_address,
                user_agent=user_agent,
                success=False
            )
            return Response({
                "detail": "2FA code sent to your email.",
                "2fa_code": code
            }, status=200)

class Verify2FAView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        email = request.data.get("email")
        code = request.data.get("2fa_code")
        ip_address = request.META.get('REMOTE_ADDR')
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        tenant = getattr(request, "tenant", None)
        if not tenant:
            UserActivity.objects.create(
                user=None,
                tenant=Tenant.objects.first(),
                action='login',
                performed_by=None,
                details={'reason': 'Tenant not found'},
                ip_address=ip_address,
                user_agent=user_agent,
                success=False
            )
            return Response({"detail": "Tenant not found."}, status=400)
        with tenant_context(tenant):
            user = get_user_model().objects.filter(email__iexact=email, tenant=tenant).first()
            if not user:
                UserActivity.objects.create(
                    user=None,
                    tenant=tenant,
                    action='login',
                    performed_by=None,
                    details={'reason': 'Invalid user'},
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False
                )
                return Response({"detail": "Invalid user."}, status=400)
            cached_code = cache.get(f"2fa_{user.id}")
            if not cached_code or cached_code != code:
                UserActivity.objects.create(
                    user=user,
                    tenant=tenant,
                    action='login',
                    performed_by=None,
                    details={'reason': 'Invalid or expired 2FA code'},
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False
                )
                return Response({"detail": "Invalid or expired 2FA code."}, status=400)
            
            user.reset_login_attempts()
            UserActivity.objects.create(
                user=user,
                tenant=tenant,
                action='login',
                performed_by=None,
                details={'reason': '2FA verified'},
                ip_address=ip_address,
                user_agent=user_agent,
                success=True
            )
            refresh = RefreshToken.for_user(user)
            access = refresh.access_token
            data = {
                "refresh": str(refresh),
                "access": str(access),
                "tenant_id": user.tenant.id,
                "tenant_schema": user.tenant.schema_name,
                "user": CustomUserMinimalSerializer(user).data,
                "has_accepted_terms": user.has_accepted_terms
            }
            cache.delete(f"2fa_{user.id}")
            return Response(data, status=200)

class LogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        ip_address = request.META.get('REMOTE_ADDR')
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        tenant = getattr(request, "tenant", Tenant.objects.first())

        if not refresh_token:
            UserActivity.objects.create(
                user=None,
                tenant=tenant,
                action='logout',
                performed_by=None,
                details={'reason': 'No refresh token provided'},
                ip_address=ip_address,
                user_agent=user_agent,
                success=False
            )
            return Response({"detail": "No refresh token provided."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            blacklist_refresh_token(refresh_token)
            UserActivity.objects.create(
                user=None,
                tenant=tenant,
                action='logout',
                performed_by=None,
                details={},
                ip_address=ip_address,
                user_agent=user_agent,
                success=True
            )
            return Response({"detail": "Logged out successfully."})
        except Exception as e:
            UserActivity.objects.create(
                user=None,
                tenant=tenant,
                action='logout',
                performed_by=None,
                details={'reason': str(e)},
                ip_address=ip_address,
                user_agent=user_agent,
                success=False
            )
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class PublicKeyView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, kid):
        tenant_id = request.query_params.get('tenant_id')
        if not tenant_id:
            logger.error("No tenant_id provided in query params")
            return Response({"error": "tenant_id is required"}, status=400)

        try:
            tenant = Tenant.objects.get(id=tenant_id)
            connection.set_schema(tenant.schema_name)
            logger.info(f"Set schema to {tenant.schema_name} for kid={kid}")
            keypair = RSAKeyPair.objects.get(kid=kid, tenant=tenant, active=True)
            return Response({"public_key": keypair.public_key_pem})
        except Tenant.DoesNotExist:
            logger.error(f"Tenant not found: id={tenant_id}")
            return Response({"error": "Tenant not found"}, status=404)
        except RSAKeyPair.DoesNotExist:
            logger.error(f"No RSAKeyPair found for kid={kid} in schema={tenant.schema_name}")
            return Response({"error": "Keypair not found"}, status=404)

class JWKSView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        jwks = {"keys": []}
        tenants = Tenant.objects.all()
        for tenant in tenants:
            with tenant_context(tenant):
                for keypair in RSAKeyPair.objects.filter(active=True):
                    rsa_key = jose_jwk.RSAKey(key=keypair.public_key_pem, algorithm='RS256')
                    pub_jwk = rsa_key.to_dict()
                    pub_jwk['kid'] = keypair.kid
                    pub_jwk['use'] = 'sig'
                    pub_jwk['alg'] = 'RS256'
                    jwks["keys"].append(pub_jwk)
        return Response(jwks)

class JitsiTokenView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        room = request.data.get('room')
        moderator = request.data.get('moderator', True)
        ip_address = request.META.get('REMOTE_ADDR')
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        if not room:
            UserActivity.objects.create(
                user=request.user,
                tenant=request.tenant,
                action='jitsi_token',
                performed_by=None,
                details={'reason': 'Room name required'},
                ip_address=ip_address,
                user_agent=user_agent,
                success=False
            )
            return Response({"error": "Room name required"}, status=400)
        user = request.user
        tenant = request.tenant
        payload = {
            "context": {
                "user": {
                    "name": f"{user.first_name} {user.last_name}",
                    "email": user.email,
                    "moderator": moderator,
                },
            },
            "room": room,
            "sub": "server1.prolianceltd.com",
            "iss": "crm-app",
            "aud": "jitsi",
            # "exp": int((timezone.now() + timedelta(hours=1)).timestamp()),
            # In JitsiTokenView.post
            "exp": int((timezone.now() + timedelta(days=7)).timestamp()), # Extend to 7 days
            "iat": int(timezone.now().timestamp()),
        }
        token = issue_rsa_jwt(payload, tenant)
        UserActivity.objects.create(
            user=user,
            tenant=tenant,
            action='jitsi_token',
            performed_by=None,
            details={'room': room},
            ip_address=ip_address,
            user_agent=user_agent,
            success=True
        )
        return Response({"token": token})