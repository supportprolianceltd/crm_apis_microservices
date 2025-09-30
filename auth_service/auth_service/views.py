import json
import logging
import random
import uuid
from datetime import datetime, timedelta

import jwt
import requests
from core.models import Tenant
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.core.cache import cache
from django.db import connection
from django.utils import timezone
from django_tenants.utils import tenant_context
from jose import jwk
from kafka import KafkaProducer
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer
)
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from users.models import (
    BlacklistedToken,
    BlockedIP,
    CustomUser,
    RSAKeyPair,
    UserActivity,
    UserProfile,
)
from users.serializers import (
    # CustomTokenSerializer,
    CustomUserMinimalSerializer,
    CustomUserSerializer,
)

from auth_service.authentication import RS256TenantJWTAuthentication
from auth_service.utils.jwt_rsa import (
    blacklist_refresh_token,
    decode_rsa_jwt,
    issue_rsa_jwt,
)

logger = logging.getLogger(__name__)


# class TokenValidateView(APIView):
#     permission_classes = [IsAuthenticated]
#     authentication_classes = [RS256TenantJWTAuthentication]

#     def get(self, request):
#         logger.info(f"TokenValidateView request payload: {request.headers}")
#         try:
#             user = request.user
#             tenant = getattr(request, "tenant", None)
#             with tenant_context(tenant):
#                 user_data = CustomUserSerializer(user).data
#                 response_data = {
#                     "status": "success",
#                     "user": user_data,
#                     "tenant_id": str(tenant.id),
#                     "tenant_organizational_id": str(tenant.organizational_id),
#                     "tenant_unique_id": str(tenant.unique_id),
#                     "tenant_schema": tenant.schema_name,
#                 }
#                 # logger.info(f"TokenValidateView response: {response_data}")
#                 logger.info("Token validation successful")
#                 return Response(response_data, status=status.HTTP_200_OK)
#         except Exception as e:
#             logger.error(f"Token validation failed: {str(e)}")
#             logger.info("Token validation unsuccessful")
#             response_data = {"status": "error", "message": "Invalid or expired token."}
#             # logger.info(f"TokenValidateView response: {response_data}")
#             return Response(response_data, status=status.HTTP_401_UNAUTHORIZED)

# In your auth service - add better error handling
# class TokenValidateView(APIView):
#     permission_classes = [IsAuthenticated]
#     authentication_classes = [RS256TenantJWTAuthentication]

#     def get(self, request):
#         logger.info(f"TokenValidateView request payload: {request.headers}")
#         try:
#             # Add request source checking
#             forwarded_by_gateway = request.headers.get('X-Gateway-Request-ID')
#             if not forwarded_by_gateway:
#                 logger.warning("Token validation request not from gateway")
#                 return Response({
#                     "status": "error", 
#                     "message": "Invalid request source"
#                 }, status=status.HTTP_400_BAD_REQUEST)
                
#             user = request.user
#             tenant = getattr(request, "tenant", None)
            
#             if not tenant:
#                 return Response({
#                     "status": "error", 
#                     "message": "Tenant context missing"
#                 }, status=status.HTTP_400_BAD_REQUEST)
                
#             with tenant_context(tenant):
#                 user_data = CustomUserSerializer(user).data
#                 response_data = {
#                     "status": "success",
#                     "user": user_data,
#                     "tenant_id": str(tenant.id),
#                     "tenant_organizational_id": str(tenant.organizational_id),
#                     "tenant_unique_id": str(tenant.unique_id),
#                     "tenant_schema": tenant.schema_name,
#                 }
#                 logger.info("Token validation successful")
#                 return Response(response_data, status=status.HTTP_200_OK)
                
#         except Exception as e:
#             logger.error(f"Token validation failed: {str(e)}")
#             # Return more specific error information
#             return Response({
#                 "status": "error", 
#                 "message": "Token validation failed",
#                 "code": "TOKEN_INVALID"
#             }, status=status.HTTP_401_UNAUTHORIZED)

class TokenValidateView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [RS256TenantJWTAuthentication]

    def get(self, request):
        logger.info(f"TokenValidateView request payload: {request.headers}")
        try:
            # TEMPORARILY COMMENT THIS OUT FOR DEVELOPMENT
            # forwarded_by_gateway = request.headers.get('X-Gateway-Request-ID')
            # if not forwarded_by_gateway:
            #     logger.warning("Token validation request not from gateway")
            #     return Response({
            #         "status": "error", 
            #         "message": "Invalid request source"
            #     }, status=status.HTTP_400_BAD_REQUEST)
                
            user = request.user
            tenant = getattr(request, "tenant", None)
            
            if not tenant:
                return Response({
                    "status": "error", 
                    "message": "Tenant context missing"
                }, status=status.HTTP_400_BAD_REQUEST)
                
            with tenant_context(tenant):
                user_data = CustomUserSerializer(user).data
                response_data = {
                    "status": "success",
                    "user": user_data,
                    "tenant_id": str(tenant.id),
                    "tenant_organizational_id": str(tenant.organizational_id),
                    "tenant_unique_id": str(tenant.unique_id),
                    "tenant_schema": tenant.schema_name,
                }
                logger.info("Token validation successful")
                return Response(response_data, status=status.HTTP_200_OK)
                
        except Exception as e:
            logger.error(f"Token validation failed: {str(e)}")
            return Response({
                "status": "error", 
                "message": "Token validation failed",
                "code": "TOKEN_INVALID"
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        
class CustomTokenSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        return super().get_token(user)

    # def validate(self, attrs):
    #     print("🔥🔥🔥 validate() from CustomTokenSerializer called!")

    #     ip_address = self.context["request"].META.get("REMOTE_ADDR")
    #     user_agent = self.context["request"].META.get("HTTP_USER_AGENT", "")
    #     tenant = self.context["request"].tenant

    #     with tenant_context(tenant):
    #         user = authenticate(email=attrs.get("email"), password=attrs.get("password"))

    #         if not user:
    #             UserActivity.objects.create(
    #                 user=None,
    #                 tenant=tenant,
    #                 action="login",
    #                 performed_by=None,
    #                 details={"reason": "Invalid credentials"},
    #                 ip_address=ip_address,
    #                 user_agent=user_agent,
    #                 success=False,
    #             )
    #             raise serializers.ValidationError("Invalid credentials")

    #         if user.is_locked or not user.is_active:
    #             UserActivity.objects.create(
    #                 user=user,
    #                 tenant=tenant,
    #                 action="login",
    #                 performed_by=None,
    #                 details={"reason": "Account locked or suspended"},
    #                 ip_address=ip_address,
    #                 user_agent=user_agent,
    #                 success=False,
    #             )
    #             raise serializers.ValidationError("Account is locked or suspended")

    #         if BlockedIP.objects.filter(ip_address=ip_address, tenant=tenant, is_active=True).exists():
    #             UserActivity.objects.create(
    #                 user=user,
    #                 tenant=tenant,
    #                 action="login",
    #                 performed_by=None,
    #                 details={"reason": "IP address blocked"},
    #                 ip_address=ip_address,
    #                 user_agent=user_agent,
    #                 success=False,
    #             )
    #             raise serializers.ValidationError("This IP address is blocked")

    #         # ✅ SUCCESS: Reset login attempts & log activity
    #         user.reset_login_attempts()
    #         UserActivity.objects.create(
    #             user=user,
    #             tenant=tenant,
    #             action="login",
    #             performed_by=None,
    #             details={},
    #             ip_address=ip_address,
    #             user_agent=user_agent,
    #             success=True,
    #         )

    #         # ✅ SEND NOTIFICATION EVENT AFTER LOGIN SUCCESS
    #         logger.info("🎯 Reached login success block. Sending login event to notification service.")
    #         try:
    #             event_payload = {
    #                 "metadata": {
    #                     "tenant_id": str(tenant.unique_id),
    #                     "event_type": "user.login.succeeded",
    #                     "event_id": str(uuid.uuid4()),
    #                     "created_at": timezone.now().isoformat(),
    #                     "source": "auth-service",
    #                 },
    #                 "data": {
    #                     "user_email": user.email,
    #                     "ip_address": ip_address,
    #                     "timestamp": timezone.now().isoformat(),
    #                     "user_id": str(user.id),
    #                     "user_agent": user_agent,
    #                 },
    #             }

    #             notifications_url = settings.NOTIFICATIONS_SERVICE_URL + "/events/"
    #             logger.info(f"➡️ POST to {notifications_url} with payload: {event_payload}")

    #             response = requests.post(notifications_url, json=event_payload, timeout=5)
    #             response.raise_for_status()  # Raise if status != 200
    #             logger.info(f"✅ Notification sent. Status: {response.status_code}, Response: {response.text}")

    #         except requests.exceptions.RequestException as e:
    #             logger.warning(f"[❌ Notification Error] Failed to send login event: {str(e)}")
    #         except Exception as e:
    #             logger.error(f"[❌ Notification Exception] Unexpected error: {str(e)}")

    #         # ✅ Issue JWT Tokens
    #         access_payload = {
    #             "jti": str(uuid.uuid4()),
    #             "sub": user.email,
    #             "role": user.role,
    #             "status": user.status,
    #             "tenant_id": user.tenant.id,
    #             "tenant_organizational_id": str(tenant.organizational_id),
    #             "tenant_unique_id": str(tenant.unique_id),
    #             "tenant_schema": user.tenant.schema_name,
    #             "has_accepted_terms": user.has_accepted_terms,
    #             "user": CustomUserMinimalSerializer(user).data,
    #             "email": user.email,
    #             "type": "access",
    #             "exp": (timezone.now() + timedelta(minutes=180)).timestamp(),
    #         }
    #         access_token = issue_rsa_jwt(access_payload, user.tenant)

    #         refresh_jti = str(uuid.uuid4())
    #         refresh_payload = {
    #             "jti": refresh_jti,
    #             "sub": user.email,
    #             "tenant_id": user.tenant.id,
    #             "tenant_organizational_id": str(user.tenant.organizational_id),
    #             "tenant_unique_id": str(user.tenant.unique_id),
    #             "type": "refresh",
    #             "exp": (timezone.now() + timedelta(days=7)).timestamp(),
    #         }
    #         refresh_token = issue_rsa_jwt(refresh_payload, user.tenant)

    #         data = {
    #             "access": access_token,
    #             "refresh": refresh_token,
    #             "tenant_id": user.tenant.id,
    #             "tenant_organizational_id": str(user.tenant.organizational_id),
    #             "tenant_unique_id": str(user.tenant.unique_id),
    #             "tenant_schema": user.tenant.schema_name,
    #             "user": CustomUserMinimalSerializer(user).data,
    #             "has_accepted_terms": user.has_accepted_terms,
    #         }

    #         return data


    def validate(self, attrs):
        print("🔥🔥🔥 validate() from CustomTokenSerializer called!")

        ip_address = self.context["request"].META.get("REMOTE_ADDR")
        user_agent = self.context["request"].META.get("HTTP_USER_AGENT", "")
        tenant = self.context["request"].tenant

        with tenant_context(tenant):
            user = authenticate(email=attrs.get("email"), password=attrs.get("password"))

            if not user:
                UserActivity.objects.create(
                    user=None,
                    tenant=tenant,
                    action="login",
                    performed_by=None,
                    details={"reason": "Invalid credentials"},
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False,
                )
                raise serializers.ValidationError("Invalid credentials")

            if user.is_locked or not user.is_active:
                UserActivity.objects.create(
                    user=user,
                    tenant=tenant,
                    action="login",
                    performed_by=None,
                    details={"reason": "Account locked or suspended"},
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False,
                )
                raise serializers.ValidationError("Account is locked or suspended")

            if BlockedIP.objects.filter(ip_address=ip_address, tenant=tenant, is_active=True).exists():
                UserActivity.objects.create(
                    user=user,
                    tenant=tenant,
                    action="login",
                    performed_by=None,
                    details={"reason": "IP address blocked"},
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False,
                )
                raise serializers.ValidationError("This IP address is blocked")

            # ✅ SUCCESS: Reset login attempts & log activity
            user.reset_login_attempts()
            UserActivity.objects.create(
                user=user,
                tenant=tenant,
                action="login",
                performed_by=None,
                details={},
                ip_address=ip_address,
                user_agent=user_agent,
                success=True,
            )

            # ✅ SEND NOTIFICATION EVENT AFTER LOGIN SUCCESS
            logger.info("🎯 Reached login success block. Sending login event to notification service.")
            try:
                event_payload = {
                    "metadata": {
                        "tenant_id": str(tenant.unique_id),
                        "event_type": "user.login.succeeded",
                        "event_id": str(uuid.uuid4()),
                        "created_at": timezone.now().isoformat(),
                        "source": "auth-service",
                    },
                    "data": {
                        "user_email": user.email,
                        "ip_address": ip_address,
                        "timestamp": timezone.now().isoformat(),
                        "user_id": str(user.id),
                        "user_agent": user_agent,
                    },
                }

                notifications_url = settings.NOTIFICATIONS_SERVICE_URL + "/events/"
                logger.info(f"➡️ POST to {notifications_url} with payload: {event_payload}")

                response = requests.post(notifications_url, json=event_payload, timeout=5)
                response.raise_for_status()  # Raise if status != 200
                logger.info(f"✅ Notification sent. Status: {response.status_code}, Response: {response.text}")

            except requests.exceptions.RequestException as e:
                logger.warning(f"[❌ Notification Error] Failed to send login event: {str(e)}")
            except Exception as e:
                logger.error(f"[❌ Notification Exception] Unexpected error: {str(e)}")

            # ✅ Fetch the primary domain
            primary_domain = tenant.domain_set.filter(is_primary=True).first()
            tenant_domain = primary_domain.domain if primary_domain else None

            # ✅ Issue JWT Tokens
            access_payload = {
                "jti": str(uuid.uuid4()),
                "sub": user.email,
                "role": user.role,
                "status": user.status,
                "tenant_id": user.tenant.id,
                "tenant_organizational_id": str(tenant.organizational_id),
                "tenant_unique_id": str(tenant.unique_id),
                "tenant_schema": user.tenant.schema_name,
                "tenant_domain": tenant_domain,  # Add tenant domain to access token
                "has_accepted_terms": user.has_accepted_terms,
                "user": CustomUserMinimalSerializer(user).data,
                "email": user.email,
                "type": "access",
                "exp": (timezone.now() + timedelta(minutes=180)).timestamp(),
            }
            access_token = issue_rsa_jwt(access_payload, user.tenant)

            refresh_jti = str(uuid.uuid4())
            refresh_payload = {
                "jti": refresh_jti,
                "sub": user.email,
                "tenant_id": user.tenant.id,
                "tenant_organizational_id": str(user.tenant.organizational_id),
                "tenant_unique_id": str(user.tenant.unique_id),
                "tenant_domain": tenant_domain,  # Add tenant domain to refresh token
                "type": "refresh",
                "exp": (timezone.now() + timedelta(days=7)).timestamp(),
            }
            refresh_token = issue_rsa_jwt(refresh_payload, user.tenant)

            data = {
                "access": access_token,
                "refresh": refresh_token,
                "tenant_id": user.tenant.id,
                "tenant_organizational_id": str(user.tenant.organizational_id),
                "tenant_unique_id": str(user.tenant.unique_id),
                "tenant_schema": user.tenant.schema_name,
                "tenant_domain": tenant_domain,  # Add tenant domain to response
                "user": CustomUserMinimalSerializer(user).data,
                "has_accepted_terms": user.has_accepted_terms,
            }

            return data
    


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenSerializer


# class CustomTokenRefreshView(APIView):
#     permission_classes = [AllowAny]

#     def post(self, request):
#         refresh_token = request.data.get("refresh")
#         ip_address = request.META.get("REMOTE_ADDR")
#         user_agent = request.META.get("HTTP_USER_AGENT", "")

#         if not refresh_token:
#             UserActivity.objects.create(
#                 user=None,
#                 tenant=Tenant.objects.first(),  # Fallback tenant
#                 action="login",
#                 performed_by=None,
#                 details={"reason": "No refresh token provided"},
#                 ip_address=ip_address,
#                 user_agent=user_agent,
#                 success=False,
#             )
#             return Response({"detail": "No refresh token provided."}, status=status.HTTP_400_BAD_REQUEST)
#         try:
#             payload = decode_rsa_jwt(refresh_token)
#             if payload.get("type") != "refresh":
#                 UserActivity.objects.create(
#                     user=None,
#                     tenant=Tenant.objects.first(),
#                     action="login",
#                     performed_by=None,
#                     details={"reason": "Invalid token type"},
#                     ip_address=ip_address,
#                     user_agent=user_agent,
#                     success=False,
#                 )
#                 return Response({"detail": "Invalid token type."}, status=status.HTTP_400_BAD_REQUEST)
#             jti = payload.get("jti")
#             if BlacklistedToken.objects.filter(jti=jti).exists():
#                 UserActivity.objects.create(
#                     user=None,
#                     tenant=Tenant.objects.first(),
#                     action="login",
#                     performed_by=None,
#                     details={"reason": "Token blacklisted"},
#                     ip_address=ip_address,
#                     user_agent=user_agent,
#                     success=False,
#                 )
#                 return Response({"detail": "Token blacklisted."}, status=status.HTTP_401_UNAUTHORIZED)

#             exp = datetime.fromtimestamp(payload["exp"])
#             BlacklistedToken.objects.create(jti=jti, expires_at=exp)

#             user = get_user_model().objects.get(email=payload["sub"])
#             tenant = user.tenant
#             with tenant_context(tenant):
#                 UserActivity.objects.create(
#                     user=user,
#                     tenant=tenant,
#                     action="login",
#                     performed_by=None,
#                     details={"reason": "Token refresh"},
#                     ip_address=ip_address,
#                     user_agent=user_agent,
#                     success=True,
#                 )
#                 new_refresh_jti = str(uuid.uuid4())
#                 refresh_payload = {
#                     "jti": new_refresh_jti,
#                     "sub": user.email,
#                     "tenant_id": user.tenant.id,
#                     "type": "refresh",
#                     "exp": (timezone.now() + timedelta(days=7)).timestamp(),
#                 }
#                 new_refresh_token = issue_rsa_jwt(refresh_payload, user.tenant)

#                 access_payload = {
#                     "jti": str(uuid.uuid4()),
#                     "sub": user.email,
#                     "role": user.role,
#                     "tenant_id": user.tenant.id,
#                     "tenant_schema": user.tenant.schema_name,
#                     "has_accepted_terms": user.has_accepted_terms,
#                     "user": CustomUserMinimalSerializer(user).data,
#                     "email": user.email,
#                     "type": "access",
#                     "exp": (timezone.now() + timedelta(minutes=15)).timestamp(),
#                 }
#                 access_token = issue_rsa_jwt(access_payload, user.tenant)

#                 return Response({"access": access_token, "refresh": new_refresh_token})
#         except Exception as e:
#             UserActivity.objects.create(
#                 user=None,
#                 tenant=Tenant.objects.first(),
#                 action="login",
#                 performed_by=None,
#                 details={"reason": f"Token refresh failed: {str(e)}"},
#                 ip_address=ip_address,
#                 user_agent=user_agent,
#                 success=False,
#             )
#             return Response({"detail": str(e)}, status=status.HTTP_401_UNAUTHORIZED)


class CustomTokenRefreshView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []  # Add this line to disable authentication

    def post(self, request):
        refresh_token = request.data.get("refresh")
        ip_address = request.META.get("REMOTE_ADDR")
        user_agent = request.META.get("HTTP_USER_AGENT", "")

        if not refresh_token:
            UserActivity.objects.create(
                user=None,
                tenant=Tenant.objects.first(),
                action="refresh_token",
                performed_by=None,
                details={"reason": "No refresh token provided"},
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
            )
            return Response({"detail": "No refresh token provided."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Decode token without verification to extract tenant_id
            unverified_payload = jwt.decode(refresh_token, options={"verify_signature": False})
            tenant_id = unverified_payload.get("tenant_id")
            if not tenant_id:
                UserActivity.objects.create(
                    user=None,
                    tenant=Tenant.objects.first(),
                    action="refresh_token",
                    performed_by=None,
                    details={"reason": "Tenant ID missing in token payload"},
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False,
                )
                return Response({"detail": "Tenant ID missing in token payload."}, status=status.HTTP_400_BAD_REQUEST)

            # Fetch tenant and verify schema
            try:
                tenant = Tenant.objects.get(id=tenant_id)
                logger.info(f"Fetched tenant: id={tenant_id}, schema_name={tenant.schema_name}")
            except Tenant.DoesNotExist:
                UserActivity.objects.create(
                    user=None,
                    tenant=Tenant.objects.first(),
                    action="refresh_token",
                    performed_by=None,
                    details={"reason": f"Tenant not found for tenant_id: {tenant_id}"},
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False,
                )
                return Response({"detail": f"Tenant not found for tenant_id: {tenant_id}."}, status=status.HTTP_400_BAD_REQUEST)

            # Set tenant context and log current schema
            with tenant_context(tenant):
                logger.info(f"Current schema: {connection.schema_name}")
                # Validate and decode refresh token
                payload = decode_rsa_jwt(refresh_token)
                if payload.get("type") != "refresh":
                    UserActivity.objects.create(
                        user=None,
                        tenant=tenant,
                        action="refresh_token",
                        performed_by=None,
                        details={"reason": "Invalid token type"},
                        ip_address=ip_address,
                        user_agent=user_agent,
                        success=False,
                    )
                    return Response({"detail": "Invalid token type."}, status=status.HTTP_400_BAD_REQUEST)

                jti = payload.get("jti")
                if BlacklistedToken.objects.filter(jti=jti).exists():
                    UserActivity.objects.create(
                        user=None,
                        tenant=tenant,
                        action="refresh_token",
                        performed_by=None,
                        details={"reason": "Token blacklisted"},
                        ip_address=ip_address,
                        user_agent=user_agent,
                        success=False,
                    )
                    return Response({"detail": "Token blacklisted."}, status=status.HTTP_401_UNAUTHORIZED)

                # Blacklist the used refresh token
                exp = datetime.fromtimestamp(payload["exp"])
                BlacklistedToken.objects.create(jti=jti, expires_at=exp)

                # Retrieve user
                user = get_user_model().objects.get(email=payload["sub"])

                # Log successful refresh activity
                UserActivity.objects.create(
                    user=user,
                    tenant=tenant,
                    action="refresh_token",
                    performed_by=None,
                    details={"reason": "Token refresh successful"},
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=True,
                )

                # Issue new access token (matching CustomTokenSerializer)
                access_payload = {
                    "jti": str(uuid.uuid4()),
                    "sub": user.email,
                    "role": user.role,
                    "status": user.status,
                    "tenant_id": user.tenant.id,
                    "tenant_organizational_id": str(tenant.organizational_id),
                    "tenant_unique_id": str(tenant.unique_id),
                    "tenant_schema": user.tenant.schema_name,
                    "has_accepted_terms": user.has_accepted_terms,
                    "user": CustomUserMinimalSerializer(user).data,
                    "email": user.email,
                    "type": "access",
                    "exp": (timezone.now() + timedelta(minutes=15)).timestamp(),
                }
                access_token = issue_rsa_jwt(access_payload, user.tenant)

                # Issue new refresh token
                new_refresh_jti = str(uuid.uuid4())
                refresh_payload = {
                    "jti": new_refresh_jti,
                    "sub": user.email,
                    "tenant_id": user.tenant.id,
                    "tenant_organizational_id": str(tenant.organizational_id),
                    "tenant_unique_id": str(tenant.unique_id),
                    "type": "refresh",
                    "exp": (timezone.now() + timedelta(days=7)).timestamp(),
                }
                new_refresh_token = issue_rsa_jwt(refresh_payload, user.tenant)

                return Response({
                    "access": access_token,
                    "refresh": new_refresh_token,
                    "tenant_id": user.tenant.id,
                    "tenant_organizational_id": str(tenant.organizational_id),
                    "tenant_unique_id": str(tenant.unique_id),
                    "tenant_schema": user.tenant.schema_name,
                    "user": CustomUserMinimalSerializer(user).data,
                    "has_accepted_terms": user.has_accepted_terms,
                }, status=status.HTTP_200_OK)

        except Exception as e:
            UserActivity.objects.create(
                user=None,
                tenant=Tenant.objects.first(),
                action="refresh_token",
                performed_by=None,
                details={"reason": f"Token refresh failed: {str(e)}"},
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
            )
            return Response({"detail": str(e)}, status=status.HTTP_401_UNAUTHORIZED)


class LoginWith2FAView(TokenObtainPairView):
    serializer_class = CustomTokenSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        ip_address = request.META.get("REMOTE_ADDR")
        user_agent = request.META.get("HTTP_USER_AGENT", "")
        tenant = getattr(request, "tenant", None)

        if not tenant:
            UserActivity.objects.create(
                user=None,
                tenant=Tenant.objects.first(),
                action="login",
                performed_by=None,
                details={"reason": "Tenant not found"},
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
            )
            return Response({"detail": "Tenant not found."}, status=status.HTTP_400_BAD_REQUEST)

        with tenant_context(tenant):
            serializer = self.get_serializer(data=request.data, context={"request": request})
            try:
                serializer.is_valid(raise_exception=True)
            except serializers.ValidationError as e:
                user = CustomUser.objects.filter(email=request.data.get("email")).first()
                UserActivity.objects.create(
                    user=user,
                    tenant=tenant,
                    action="login",
                    performed_by=None,
                    details={"reason": f"Invalid credentials: {str(e)}"},
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False,
                )
                return Response(e.detail, status=status.HTTP_401_UNAUTHORIZED)

            user = serializer.user
            if user.is_locked or user.status == "suspended" or not user.is_active:
                UserActivity.objects.create(
                    user=user,
                    tenant=tenant,
                    action="login",
                    performed_by=None,
                    details={"reason": "Account locked or suspended"},
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False,
                )
                return Response({"detail": "Account is locked or suspended."}, status=status.HTTP_403_FORBIDDEN)

            if BlockedIP.objects.filter(ip_address=ip_address, tenant=tenant, is_active=True).exists():
                UserActivity.objects.create(
                    user=user,
                    tenant=tenant,
                    action="login",
                    performed_by=None,
                    details={"reason": "IP address blocked"},
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False,
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
                    "expires_in_seconds": 300,
                },
                "metadata": {
                    "event_id": f"evt-{uuid.uuid4()}",
                    "event_type": "auth.2fa.code.requested",
                    "created_at": datetime.utcnow().isoformat() + "Z",
                    "source": "auth-service",
                    "tenant_id": str(getattr(tenant, "id", "unknown")),
                },
            }
            try:
                requests.post(settings.NOTIFICATIONS_EVENT_URL, json=event_payload, timeout=3)
            except Exception as e:
                logger.error(f"Failed to send 2FA event notification: {e}")

            UserActivity.objects.create(
                user=user,
                tenant=tenant,
                action="login",
                performed_by=None,
                details={"reason": "2FA code sent"},
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
            )
            return Response({"detail": "2FA code sent to your email.", "2fa_code": code}, status=200)


class Verify2FAView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")
        code = request.data.get("2fa_code")
        ip_address = request.META.get("REMOTE_ADDR")
        user_agent = request.META.get("HTTP_USER_AGENT", "")
        tenant = getattr(request, "tenant", None)
        if not tenant:
            UserActivity.objects.create(
                user=None,
                tenant=Tenant.objects.first(),
                action="login",
                performed_by=None,
                details={"reason": "Tenant not found"},
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
            )
            return Response({"detail": "Tenant not found."}, status=400)
        with tenant_context(tenant):
            user = get_user_model().objects.filter(email__iexact=email, tenant=tenant).first()
            if not user:
                UserActivity.objects.create(
                    user=None,
                    tenant=tenant,
                    action="login",
                    performed_by=None,
                    details={"reason": "Invalid user"},
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False,
                )
                return Response({"detail": "Invalid user."}, status=400)
            cached_code = cache.get(f"2fa_{user.id}")
            if not cached_code or cached_code != code:
                UserActivity.objects.create(
                    user=user,
                    tenant=tenant,
                    action="login",
                    performed_by=None,
                    details={"reason": "Invalid or expired 2FA code"},
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False,
                )
                return Response({"detail": "Invalid or expired 2FA code."}, status=400)

            user.reset_login_attempts()
            UserActivity.objects.create(
                user=user,
                tenant=tenant,
                action="login",
                performed_by=None,
                details={"reason": "2FA verified"},
                ip_address=ip_address,
                user_agent=user_agent,
                success=True,
            )
            refresh = RefreshToken.for_user(user)
            access = refresh.access_token
            data = {
                "refresh": str(refresh),
                "access": str(access),
                "tenant_id": user.tenant.id,
                "tenant_schema": user.tenant.schema_name,
                "user": CustomUserMinimalSerializer(user).data,
                "has_accepted_terms": user.has_accepted_terms,
            }
            cache.delete(f"2fa_{user.id}")
            return Response(data, status=200)


class LogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        ip_address = request.META.get("REMOTE_ADDR")
        user_agent = request.META.get("HTTP_USER_AGENT", "")
        tenant = getattr(request, "tenant", Tenant.objects.first())

        if not refresh_token:
            UserActivity.objects.create(
                user=None,
                tenant=tenant,
                action="logout",
                performed_by=None,
                details={"reason": "No refresh token provided"},
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
            )
            return Response({"detail": "No refresh token provided."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            blacklist_refresh_token(refresh_token)
            UserActivity.objects.create(
                user=None,
                tenant=tenant,
                action="logout",
                performed_by=None,
                details={},
                ip_address=ip_address,
                user_agent=user_agent,
                success=True,
            )
            return Response({"detail": "Logged out successfully."})
        except Exception as e:
            UserActivity.objects.create(
                user=None,
                tenant=tenant,
                action="logout",
                performed_by=None,
                details={"reason": str(e)},
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
            )
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class PublicKeyView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, kid):
        tenant_id = request.query_params.get("tenant_id")
        if not tenant_id:
            logger.error("No tenant_id provided in query params")
            return Response({"error": "tenant_id is required"}, status=400)

        try:
            logger.info(f"Set tenant_id to {tenant_id} ")
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


class JWKSView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        jwks = {"keys": []}
        tenants = Tenant.objects.all()
        for tenant in tenants:
            with tenant_context(tenant):
                for keypair in RSAKeyPair.objects.filter(active=True):
                    rsa_key = jwk.construct(keypair.public_key_pem, algorithm="RS256")
                    pub_jwk = rsa_key.to_dict()
                    pub_jwk["kid"] = keypair.kid
                    pub_jwk["use"] = "sig"
                    pub_jwk["alg"] = "RS256"
                    jwks["keys"].append(pub_jwk)
        return Response(jwks)


class JitsiTokenView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        room = request.data.get("room")
        moderator = request.data.get("moderator", True)
        ip_address = request.META.get("REMOTE_ADDR")
        user_agent = request.META.get("HTTP_USER_AGENT", "")
        if not room:
            UserActivity.objects.create(
                user=request.user,
                tenant=request.tenant,
                action="jitsi_token",
                performed_by=None,
                details={"reason": "Room name required"},
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
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
            "exp": int((timezone.now() + timedelta(days=7)).timestamp()),  # Extend to 7 days
            "iat": int(timezone.now().timestamp()),
        }
        token = issue_rsa_jwt(payload, tenant)
        UserActivity.objects.create(
            user=user,
            tenant=tenant,
            action="jitsi_token",
            performed_by=None,
            details={"room": room},
            ip_address=ip_address,
            user_agent=user_agent,
            success=True,
        )
        return Response({"token": token})
