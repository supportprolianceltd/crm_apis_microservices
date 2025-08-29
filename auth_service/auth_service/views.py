from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import serializers
from django_tenants.utils import tenant_context
from core.models import  Tenant
from users.serializers import CustomUserSerializer
import logging
import jwt
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework import status
from kafka import KafkaProducer
import json
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils import timezone
import jwt
import requests
import uuid
from datetime import datetime
from django.core.cache import cache
import random
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model, authenticate

logger = logging.getLogger(__name__)

class TokenValidateView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        try:
            user = request.user
            tenant = request.tenant
            with tenant_context(tenant):
                user_data = CustomUserSerializer(user).data
                return Response({
                    'status': 'success',
                    'user': user_data,
                    'tenant_id': str(tenant.id),
                    'tenant_schema': tenant.schema_name
                }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Token validation failed: {str(e)}")
            return Response({
                'status': 'error',
                'message': 'Invalid or expired token.'
            }, status=status.HTTP_401_UNAUTHORIZED)




class CustomTokenSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['tenant_id'] = user.tenant.id
        token['tenant_schema'] = user.tenant.schema_name
        token['has_accepted_terms'] = user.has_accepted_terms  # Add to token
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user
        # Check if token was issued before last password reset
        refresh = RefreshToken(data['refresh'])
        decoded_token = jwt.decode(data['access'], settings.SECRET_KEY, algorithms=["HS256"])
        token_iat = decoded_token.get('iat')
        if user.last_password_reset and token_iat < user.last_password_reset.timestamp():
            raise serializers.ValidationError("Token is invalid due to recent password reset.")
        data['tenant_id'] = user.tenant.id
        data['tenant_schema'] = user.tenant.schema_name
        data['user'] = CustomUserSerializer(user, context=self.context).data
        data['has_accepted_terms'] = user.has_accepted_terms  # Include in response

        # --- Send notification event ---
        try:
            event_payload = {
                "metadata": {
                    "tenant_id": "test-tenant-1",
                    "event_type": "user.login.succeeded",
                    "event_id": f"evt-{uuid.uuid4()}",
                    "created_at": datetime.utcnow().isoformat() + "Z",
                    "source": "auth-service"
                },
                "data": {
                    "user_email": user.email,
                    "ip_address": self.context['request'].META.get('REMOTE_ADDR', ''),
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "user_id": f"user-{user.id}",
                    "user_agent": self.context['request'].META.get('HTTP_USER_AGENT', '')
                }
            }
            requests.post(settings.NOTIFICATIONS_EVENT_URL, json=event_payload, timeout=3)
            # print("Login event notification sent.")
            # logger.info(f"Failed to send login event notification: {event_payload}")
        except Exception as e:
            logger.error(f"Failed to send login event notification: {e}")

        return data




class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenSerializer



class CustomTokenRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        refresh = RefreshToken(attrs['refresh'])
        tenant_id = refresh.get('tenant_id', None)
        tenant_schema = refresh.get('tenant_schema', None)

        if not tenant_id or not tenant_schema:
            raise serializers.ValidationError("Invalid token: tenant info missing")

        try:
            tenant = Tenant.objects.get(id=tenant_id, schema_name=tenant_schema)
        except Tenant.DoesNotExist:
            raise serializers.ValidationError("Invalid tenant")

        with tenant_context(tenant):
            data = super().validate(attrs)
            data['tenant_id'] = str(tenant.id)
            data['tenant_schema'] = tenant.schema_name
            return data



class CustomTokenRefreshView(TokenRefreshView):
    serializer_class = CustomTokenRefreshSerializer


class LoginWith2FAView(TokenObtainPairView):
    serializer_class = CustomTokenSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        try:
            serializer.is_valid(raise_exception=True)
        except serializers.ValidationError as e:
            return Response(e.detail, status=status.HTTP_401_UNAUTHORIZED)

        user = serializer.user
        tenant = getattr(request, "tenant", None)

        # Generate and send 2FA code
        code = f"{random.randint(100000, 999999)}"
        cache.set(f"2fa_{user.id}", code, timeout=300)
        event_payload = {
            "data": {
                "user_email": user.email,
                "2fa_code": code,
                "2fa_method": "email",
                "ip_address": request.META.get('REMOTE_ADDR', ''),
                "user_agent": request.META.get('HTTP_USER_AGENT', ''),
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

        # Return the code in the response (for testing/demo purposes)
        return Response({
            "detail": "2FA code sent to your email.",
            "2fa_code": code
        }, status=200)

class Verify2FAView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        email = request.data.get("email")
        code = request.data.get("2fa_code")
        tenant = getattr(request, "tenant", None)
        if not tenant:
            return Response({"detail": "Tenant not found."}, status=400)
        with tenant_context(tenant):
            user = get_user_model().objects.filter(email__iexact=email, tenant=tenant).first()
            if not user:
                return Response({"detail": "Invalid user."}, status=400)
            cached_code = cache.get(f"2fa_{user.id}")
            if not cached_code or cached_code != code:
                return Response({"detail": "Invalid or expired 2FA code."}, status=400)
            refresh = RefreshToken.for_user(user)
            access = refresh.access_token
            data = {
                "refresh": str(refresh),
                "access": str(access),
                "tenant_id": user.tenant.id,
                "tenant_schema": user.tenant.schema_name,
                "user": CustomUserSerializer(user).data,
                "has_accepted_terms": user.has_accepted_terms
            }
            cache.delete(f"2fa_{user.id}")
            return Response(data, status=200)


