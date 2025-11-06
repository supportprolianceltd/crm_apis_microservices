# Standard Library
import base64
import json
import logging
import secrets
import string
import random
import uuid
import urllib.parse
from django_tenants.utils import get_public_schema_name
from collections import defaultdict
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from django.db.models import Count, Q, F, ExpressionWrapper, FloatField
from django.db.models.functions import TruncDate, TruncHour
from django.utils import timezone
from datetime import timedelta, datetime
import json
# Third-Party
from django.db.models import Prefetch
import jwt
import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

# Django
from django.conf import settings
from django.contrib.auth import authenticate
from django.core.mail import EmailMessage, send_mail
from django.core.mail.backends.smtp import EmailBackend
from django.db import ProgrammingError, transaction
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

# Django Tenants
from django_tenants.utils import get_public_schema_name, tenant_context

# Django REST Framework
from rest_framework import generics, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, NotFound, PermissionDenied, ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from rest_framework_simplejwt.tokens import RefreshToken

# Core App - Models
from core.models import Branch, Domain, Tenant, TenantConfig

# Users App - Models
from users.models import CustomUser  # Imported specifically from users app

# Local App - Models
from .models import (
    BlockedIP,
    ClientProfile,
    CustomUser,
    Document,
    DocumentAcknowledgment,
    DocumentPermission,
    DocumentVersion,
    DrivingRiskAssessment,
    EducationDetail,
    EmploymentDetail,
    Group,
    GroupMembership,
    InsuranceVerification,
    InvestmentDetail,
    LegalWorkEligibility,
    OtherUserDocuments,
    PasswordResetToken,
    ProfessionalQualification,
    ProofOfAddress,
    ReferenceCheck,
    RSAKeyPair,
    UserActivity,
    UserProfile,
    UserSession,
    WithdrawalDetail,
)

# Local App - Serializers
from .serializers import (
    AdminUserCreateSerializer,    BlockedIPSerializer,TransactionSerializer,
    ClientCreateSerializer, ClientDetailSerializer, ClientProfileSerializer,
    CustomUserListSerializer, CustomUserSerializer, DocumentAcknowledgmentSerializer,
    DocumentSerializer, DocumentVersionSerializer,  DrivingRiskAssessmentSerializer, EducationDetailSerializer,
    EmploymentDetailSerializer,GroupMembershipSerializer,GroupSerializer, InsuranceVerificationSerializer,
    InvestmentDetailSerializer, LegalWorkEligibilitySerializer,OtherUserDocumentsSerializer, PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer, ProfessionalQualificationSerializer,
    ProofOfAddressSerializer, ReferenceCheckSerializer, UserAccountActionSerializer, UserActivitySerializer,
    UserBranchUpdateSerializer, UserCreateSerializer, UserDocumentAccessSerializer, UserImpersonateSerializer,
    UserPasswordRegenerateSerializer, UserSessionSerializer,
    WithdrawalDetailSerializer,  get_tenant_id_from_jwt,   get_user_data_from_jwt,
)

# Auth Service - Utilities & Serializers
from auth_service.utils.cache import delete_cache_key, delete_tenant_cache, get_cache_key
from auth_service.utils.jwt_rsa import issue_rsa_jwt, validate_rsa_jwt
from auth_service.views import CustomUserMinimalSerializer

# Utilities
from utils.supabase import upload_file_dynamic
from .utils import get_daily_usage

# Logger
logger = logging.getLogger("users")


class CustomPagination(PageNumberPagination):
    page_size = 20  # Adjust as needed

    def get_next_link(self):
        """Override to use gateway base URL."""
        if not self.page.has_next():
            return None
        gateway_url = getattr(settings, 'GATEWAY_URL', None)
        if not gateway_url:
            return super().get_next_link()  # Fallback to default

        request = self.request
        # Build base path from current request (e.g., /api/user/users/)
        path = request.path
        # Get query params, update 'page', preserve others
        query_params = request.query_params.copy()
        query_params['page'] = self.page.next_page_number()
        query_string = urlencode(query_params, doseq=True)

        # Reconstruct full URL with gateway scheme/host
        parsed_gateway = urlparse(gateway_url)
        full_url = f"{parsed_gateway.scheme}://{parsed_gateway.netloc}{path}?{query_string}"
        return full_url

    def get_previous_link(self):
        """Override to use gateway base URL."""
        if not self.page.has_previous():
            return None
        gateway_url = getattr(settings, 'GATEWAY_URL', None)
        if not gateway_url:
            return super().get_previous_link()  # Fallback to default

        request = self.request
        path = request.path
        query_params = request.query_params.copy()
        query_params['page'] = self.page.previous_page_number()
        query_string = urlencode(query_params, doseq=True)

        parsed_gateway = urlparse(gateway_url)
        full_url = f"{parsed_gateway.scheme}://{parsed_gateway.netloc}{path}?{query_string}"
        return full_url

    def get_paginated_response(self, data):
        """Ensure the full response uses overridden links."""
        response = super().get_paginated_response(data)
        gateway_url = getattr(settings, 'GATEWAY_URL', None)
        if gateway_url:
            response['next'] = self.get_next_link()
            response['previous'] = self.get_previous_link()
        return response



# utils/tenant_helpers.py   (or at the top of your views file)
# utils/tenant_helpers.py
from collections import defaultdict
from django_tenants.utils import get_public_schema_name, tenant_context
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
import logging

logger = logging.getLogger(__name__)

def get_tenant_domains(tenant):
    """
    Return primary domain and list of all domains for a tenant.
    Uses correct reverse relation: 'domains'
    """
    primary = tenant.domains.filter(is_primary=True).first()
    all_domains = list(tenant.domains.values_list("domain", flat=True))
    return {
        "primary_domain": primary.domain if primary else None,
        "all_domains": sorted(all_domains),
    }


def get_root_admin(tenant):
    try:
        with tenant_context(tenant):
            admin = (
                CustomUser.objects.filter(tenant=tenant, role="root-admin")
                .select_related("profile")
                .first()
            )
            if admin:
                return {
                    "id": admin.id,
                    "email": admin.email,
                    "first_name": admin.first_name,
                    "last_name": admin.last_name,
                    "role": admin.role,
                }
    except Exception as exc:
        logger.error(f"Failed to fetch root-admin for {tenant.schema_name}: {exc}")
    return None



@method_decorator(cache_page(60 * 5), name='dispatch')   # 5-minute cache
class AllTenantsUsersListView(generics.ListAPIView):
    """
    PUBLIC endpoint – returns **all** users from **every** client tenant.
    No authentication required.
    """
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AnonRateThrottle]          # 100 req/min per IP
    serializer_class = CustomUserListSerializer

    def list(self, request, *args, **kwargs):
        cache_key = "public_all_tenants_users"
        data = cache.get(cache_key)
        if data:
            return Response(data)

        EXCLUDED_SCHEMAS = {get_public_schema_name(), 'auth-service'}

        tenants_data = defaultdict(
            lambda: {
                "users": [], "unique_id": None, "name": None,
                "primary_domain": None, "all_domains": [], "status": None,
                "root_admin": None, "created_at": None,
            }
        )

        # ---- 1. Fetch client tenants -------------------------------------------------
        tenants = (
            Tenant.objects.prefetch_related('domains')
            .exclude(schema_name__in=EXCLUDED_SCHEMAS)
        )
        total_tenants = tenants.count()

        # ---- 2. Iterate over tenants ------------------------------------------------
        for tenant in tenants:
            try:
                # users inside the tenant schema
                with tenant_context(tenant):
                    users = CustomUser.objects.filter(tenant=tenant) \
                        .select_related("profile", "tenant", "branch")

                    tenants_data[tenant.schema_name]["users"].extend(users)

                # tenant meta (still in public schema)
                tenants_data[tenant.schema_name].update(
                    {
                        "unique_id": str(tenant.unique_id) if tenant.unique_id else None,
                        "name": tenant.name,
                        "status": tenant.status,
                        "created_at": tenant.created_at.isoformat() if tenant.created_at else None,
                    }
                )
                tenants_data[tenant.schema_name].update(get_tenant_domains(tenant))
                tenants_data[tenant.schema_name]["root_admin"] = get_root_admin(tenant)

            except Exception as exc:
                logger.error(f"Error processing tenant {tenant.schema_name}: {exc}")
                continue

        # ---- 3. Serialize -----------------------------------------------------------
        grouped = {}
        for schema, data in tenants_data.items():
            users_list = sorted(data["users"], key=lambda u: u.email)
            grouped[schema] = {
                "unique_id": data["unique_id"],
                "name": data["name"],
                "primary_domain": data["primary_domain"],
                "all_domains": data["all_domains"],
                "status": data["status"],
                "root_admin": data["root_admin"],
                "count": len(users_list),
                "created_at": data["created_at"],
                "users": self.get_serializer(
                    users_list, many=True, context=self.get_serializer_context()
                ).data,
            }

        sorted_tenants = sorted(grouped.items())

        response_data = {
            "tenants": [
                {
                    "schema_name": schema,
                    "name": info["name"],
                    "primary_domain": info["primary_domain"],
                    "all_domains": info["all_domains"],
                    "status": info["status"],
                    "root_admin": info["root_admin"],
                    "unique_id": info["unique_id"],
                    "count": info["count"],
                    "created_at": info["created_at"],
                    "users": info["users"],
                }
                for schema, info in sorted_tenants
            ],
            "total_count": sum(info["count"] for info in grouped.values()),
            "total_tenants": total_tenants,
        }

        # cache the heavy result
        cache.set(cache_key, response_data, timeout=60 * 5)
        return Response(response_data)

@method_decorator(cache_page(60 * 5), name='dispatch')
class AllTenantNamesUsersListView(generics.ListAPIView):
    """
    PUBLIC paginated endpoint – same payload as above but with DRF pagination.
    """
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AnonRateThrottle]
    serializer_class = CustomUserListSerializer
    pagination_class = CustomPagination

    def list(self, request, *args, **kwargs):
        cache_key = "public_all_tenants_users_paginated"
        data = cache.get(cache_key)
        if data:
            return Response(data)

        EXCLUDED_SCHEMAS = {get_public_schema_name(), 'auth-service'}

        tenants_data = defaultdict(
            lambda: {
                "users": [], "unique_id": None, "name": None,
                "primary_domain": None,
                "all_domains": [], "status": None,
                "root_admin": None, "created_at": None,
            }
        )

        tenants = (
            Tenant.objects.prefetch_related('domains')
            .exclude(schema_name__in=EXCLUDED_SCHEMAS)
        )
        total_tenants = tenants.count()

        for tenant in tenants:
            try:
                with tenant_context(tenant):
                    users = CustomUser.objects.filter(tenant=tenant) \
                        .prefetch_related("profile", "tenant", "branch")
                    tenants_data[tenant.schema_name]["users"].extend(users)

                tenants_data[tenant.schema_name].update(
                    {
                        "unique_id": str(tenant.unique_id) if tenant.unique_id else None,
                        "name": tenant.name,
                        "status": tenant.status,
                        "created_at": tenant.created_at.isoformat() if tenant.created_at else None,
                    }
                )
                tenants_data[tenant.schema_name].update(get_tenant_domains(tenant))
                tenants_data[tenant.schema_name]["root_admin"] = get_root_admin(tenant)

            except Exception as exc:
                logger.error(f"Error processing tenant {tenant.schema_name}: {exc}")
                continue

        grouped = {}
        for schema, data in tenants_data.items():
            users_list = sorted(data["users"], key=lambda u: u.email)
            grouped[schema] = {
                "unique_id": data["unique_id"],
                "name": data["name"],
                "primary_domain": data["primary_domain"],
                "all_domains": data["all_domains"],
                "status": data["status"],
                "root_admin": data["root_admin"],
                "count": len(users_list),
                "created_at": data["created_at"],
                "users": self.get_serializer(
                    users_list, many=True, context=self.get_serializer_context()
                ).data,
            }

        sorted_tenants = sorted(grouped.items())
        tenants_list = [
            {
                "schema_name": schema,
                "name": info["name"],
                "primary_domain": info["primary_domain"],
                "all_domains": info["all_domains"],
                "status": info["status"],
                "root_admin": info["root_admin"],
                "unique_id": info["unique_id"],
                "count": info["count"],
                "created_at": info["created_at"],
                "users": info["users"],
            }
            for schema, info in sorted_tenants
        ]

        # ---- Pagination ------------------------------------------------------------
        page = self.paginate_queryset(tenants_list)
        total_users = sum(info["count"] for info in grouped.values())

        payload = {
            "tenants": page or tenants_list,
            "total_count": total_users,
            "total_tenants": total_tenants,
        }

        if page is not None:
            payload = self.get_paginated_response(payload).data

        cache.set(cache_key, payload, timeout=60 * 5)
        return Response(payload)


class TermsAndConditionsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        tenant = request.user.tenant
        with tenant_context(tenant):
            user = request.user
            if user.has_accepted_terms:
                logger.info(f"User {user.email} has already accepted terms and conditions.")
                return Response(
                    {"status": "success", "message": "Terms and conditions already accepted."},
                    status=status.HTTP_200_OK,
                )

            user.has_accepted_terms = True
            user.save()
            logger.info(f"User {user.email} accepted terms and conditions for tenant {tenant.schema_name}.")
            return Response(
                {"status": "success", "message": "Terms and conditions accepted successfully."},
                status=status.HTTP_200_OK,
            )


class UserPasswordRegenerateView(APIView):
    def post(self, request, user_id=None):
        # Accept user_id from URL or request data
        if user_id is None:
            user_id = request.data.get("user_id")
        if not user_id:
            return Response({"detail": "user_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = CustomUser.objects.get(id=user_id)
        except CustomUser.DoesNotExist:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        # Generate a strong password
        alphabet = string.ascii_letters + string.digits + string.punctuation
        password = "".join(secrets.choice(alphabet) for _ in range(20))

        user.set_password(password)
        user.save()

        return Response({"user_id": user.id, "email": user.email, "new_password": password}, status=status.HTTP_200_OK)


class PasswordResetRequestView(generics.GenericAPIView):
    serializer_class = PasswordResetRequestSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        logger.info(f"Processing password reset request with data: {request.data}")

        # Validate serializer
        serializer = self.get_serializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            logger.error(f"Serializer validation failed: {serializer.errors}")
            return Response({"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data["email"]
        ip_address = request.META.get("REMOTE_ADDR")
        user_agent = request.META.get("HTTP_USER_AGENT", "")
        logger.info(f"Processing password reset for email: {email}")

        # Extract tenant using email domain
        try:
            email_domain = email.split('@')[1]
            logger.debug(f"Email domain: {email_domain}")
            domain = Domain.objects.filter(domain=email_domain).first()
            if not domain:
                logger.error(f"No domain found for email domain: {email_domain}")
                UserActivity.objects.create(
                    user=None,
                    tenant=Tenant.objects.first(),
                    action="password_reset_request",
                    performed_by=None,
                    details={"reason": f"No tenant found for email domain: {email_domain}"},
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False,
                )
                return Response({"error": f"No tenant found for email domain: {email_domain}"}, status=status.HTTP_404_NOT_FOUND)

            tenant = domain.tenant
            logger.info(f"Found tenant: {tenant.schema_name} for email domain: {email_domain}")
        except (ValueError, IndexError) as e:
            logger.error(f"Invalid email format: {email}, error: {str(e)}")
            UserActivity.objects.create(
                user=None,
                tenant=Tenant.objects.first(),
                action="password_reset_request",
                performed_by=None,
                details={"reason": f"Invalid email format: {str(e)}"},
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
            )
            return Response({"error": "Invalid email format"}, status=status.HTTP_400_BAD_REQUEST)

        # Perform DB operations in the tenant schema
        with tenant_context(tenant):
            try:
                user = CustomUser.objects.get(email=email, tenant=tenant)
            except CustomUser.DoesNotExist:
                logger.warning(f"No user found with email {email} in tenant {tenant.schema_name}")
                UserActivity.objects.create(
                    user=None,
                    tenant=tenant,
                    action="password_reset_request",
                    performed_by=None,
                    details={"reason": f"No user found with email {email}"},
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False,
                )
                return Response({"error": "No user found with this email"}, status=status.HTTP_404_NOT_FOUND)

            # Check if user is locked or suspended
            if user.is_locked or user.status == "suspended" or not user.is_active:
                logger.warning(f"User {email} is locked or suspended in tenant {tenant.schema_name}")
                UserActivity.objects.create(
                    user=user,
                    tenant=tenant,
                    action="password_reset_request",
                    performed_by=None,
                    details={"reason": "Account locked or suspended"},
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False,
                )
                return Response({"error": "Account is locked or suspended"}, status=status.HTTP_403_FORBIDDEN)

            # Check if IP is blocked
            if BlockedIP.objects.filter(ip_address=ip_address, tenant=tenant, is_active=True).exists():
                logger.warning(f"IP {ip_address} is blocked for tenant {tenant.schema_name}")
                UserActivity.objects.create(
                    user=user,
                    tenant=tenant,
                    action="password_reset_request",
                    performed_by=None,
                    details={"reason": "IP address blocked"},
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False,
                )
                return Response({"error": "This IP address is blocked"}, status=status.HTTP_403_FORBIDDEN)

            # Create password reset token
            token = str(uuid.uuid4())
            expires_at = timezone.now() + timedelta(hours=1)
            PasswordResetToken.objects.create(
                user=user,
                tenant=tenant,
                token=token,
                expires_at=expires_at
            )
            logger.info(f"Password reset token created for user {email} in tenant {tenant.schema_name}")

            # Send notification to external service
            event_payload = {
                "metadata": {
                    "event_id": str(uuid.uuid4()),
                    "event_type": "user.password.reset.requested",
                    "event_version": "1.0",
                    "created_at": timezone.now().isoformat(),   
                    "source": "auth-service",
                    "tenant_id": str(tenant.unique_id),
                },
                "data": {
                    "user_email": user.email,
                    "user_name": f"{user.first_name} {user.last_name}",
                    "reset_link": token,
                    "ip_address": ip_address,
                    "user_agent": user_agent,
                    "user_id": user.id,
                    "expires_at": expires_at.isoformat(),
                },
            }
            try:
                url = urllib.parse.urljoin(settings.NOTIFICATIONS_SERVICE_URL.rstrip('/') + '/', 'events/')

                response = requests.post(
                    url,
                    json=event_payload,
                    timeout=5
                )
                response.raise_for_status()
                logger.info(f"Notification sent for password reset: {user.email}, Status: {response.status_code}")
            except requests.exceptions.RequestException as e:
                logger.error(f"Failed to send password reset notification for {user.email}: {str(e)}")

            # # Log activity
            # UserActivity.objects.create(
            #     user=user,
            #     tenant=tenant,
            #     action="password_reset_request",
            #     performed_by=None,
            #     details={"token": token},
            #     ip_address=ip_address,
            #     user_agent=user_agent,
            #     success=True,
            # )

        return Response(
            {
                "detail": "Password reset token generated successfully.",
                "tenant_schema": tenant.schema_name,
                "email": email
            },
            status=status.HTTP_200_OK
        )


class PasswordResetConfirmView(generics.GenericAPIView):
    serializer_class = PasswordResetConfirmSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        logger.info(f"Processing password reset confirmation with data: {request.data}")
        
        serializer = self.get_serializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            logger.error(f"Validation failed for password reset confirmation: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        token = serializer.validated_data["token"]
        new_password = serializer.validated_data["new_password"]
        ip_address = request.META.get("REMOTE_ADDR")
        user_agent = request.META.get("HTTP_USER_AGENT", "")

        # The middleware has already set the tenant based on the token
        tenant = request.tenant
        logger.info(f"Processing password reset confirmation in tenant: {tenant.schema_name}")

        try:
            # Token already used?
            reset_token = PasswordResetToken.objects.select_related('user').filter(token=token).first()
            if not reset_token:
                logger.warning(f"Invalid token {token} in schema {tenant.schema_name}")
                UserActivity.objects.create(
                    user=None,
                    tenant=tenant,
                    action="password_reset_confirm",
                    performed_by=None,
                    details={"reason": "Invalid token"},
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False,
                )
                return Response({"detail": "Invalid or expired token."}, status=status.HTTP_400_BAD_REQUEST)

            if reset_token.used:
                logger.warning(f"Token {token} already used in schema {tenant.schema_name}")
                UserActivity.objects.create(
                    user=reset_token.user,
                    tenant=tenant,
                    action="password_reset_confirm",
                    performed_by=None,
                    details={"reason": "Token already used"},
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False,
                )
                return Response({"detail": "This token has already been used."}, status=status.HTTP_400_BAD_REQUEST)

            # Token expired?
            if reset_token.expires_at < timezone.now():
                logger.warning(f"Token {token} expired in schema {tenant.schema_name}")
                UserActivity.objects.create(
                    user=reset_token.user,
                    tenant=tenant,
                    action="password_reset_confirm",
                    performed_by=None,
                    details={"reason": "Token expired"},
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False,
                )
                return Response({"detail": "This token has expired."}, status=status.HTTP_400_BAD_REQUEST)

            user = reset_token.user

            # Additional user checks
            if user.is_locked or user.status == "suspended" or not user.is_active:
                logger.warning(f"User {user.email} is locked or suspended in tenant {tenant.schema_name}")
                UserActivity.objects.create(
                    user=user,
                    tenant=tenant,
                    action="password_reset_confirm",
                    performed_by=None,
                    details={"reason": "Account locked or suspended"},
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False,
                )
                return Response({"detail": "Account is locked or suspended."}, status=status.HTTP_403_FORBIDDEN)

            with transaction.atomic():
                user.set_password(new_password)
                user.last_password_reset = timezone.now()
                user.save()

                reset_token.used = True
                reset_token.save()

                logger.info(f"Password reset successful for user {user.email} in tenant {tenant.schema_name}")

                # Send notification to external service
                event_payload = {
                    "metadata": {
                        "tenant_id": str(tenant.unique_id),
                        "event_type": "auth.password_reset.confirmed",
                        "event_id": str(uuid.uuid4()),
                        "created_at": timezone.now().isoformat(),
                        "source": "auth-service",
                    },
                    "data": {
                        "user_email": user.email,
                        "ip_address": ip_address,
                        "user_agent": user_agent,
                        "timestamp": timezone.now().isoformat(),
                    },
                }
                try:
                    response = requests.post(
                        settings.NOTIFICATIONS_EVENT_URL,
                        json=event_payload,
                        timeout=5
                    )
                    response.raise_for_status()
                    logger.info(f"Notification sent for password reset confirmation: {user.email}, Status: {response.status_code}")
                except requests.exceptions.RequestException as e:
                    logger.error(f"Failed to send password reset confirmation notification for {user.email}: {str(e)}")

                # Log successful activity
                UserActivity.objects.create(
                    user=user,
                    tenant=tenant,
                    action="password_reset_confirm",
                    performed_by=None,
                    details={},
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=True,
                )

            return Response({"detail": "Password reset successfully."}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"Error during password reset confirmation in schema {tenant.schema_name}: {str(e)}")
            UserActivity.objects.create(
                user=None,
                tenant=tenant,
                action="password_reset_confirm",
                performed_by=None,
                details={"reason": f"Internal error: {str(e)}"},
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
            )
            return Response({"detail": "Password reset failed."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserViewSet(viewsets.ModelViewSet):
    queryset = CustomUser.objects.all()
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    def get_base_queryset(self):
        """DRY helper for tenant-filtered queryset with role-based access, excluding clients."""
        tenant = self.request.user.tenant
        user = self.request.user
        with tenant_context(tenant):
            # Exclude users with role='client' to separate them from CustomUser list
            base_qs = CustomUser.objects.filter(tenant=tenant).exclude(role='client')
            if not (user.is_superuser or user.role == "admin"):
                if user.role == "team_manager":
                    pass  # All non-client users in tenant
                elif user.role == "recruiter" and user.branch:
                    base_qs = base_qs.filter(branch=user.branch)
                else:
                    base_qs = base_qs.filter(id=user.id)  # Self only
            return base_qs

    def get_queryset(self):
        """Optimized queryset: Minimal for lists, full prefetch for details."""
        base_qs = self.get_base_queryset()
        tenant_schema = self.request.tenant.schema_name
        if self.action in ['list', 'retrieve'] and settings.CACHE_ENABLED:
            from auth_service.utils.cache import get_cache_key, get_from_cache, set_to_cache
            
            cache_key = get_cache_key(tenant_schema, f'users_{self.action}')
            cached_data = get_from_cache(cache_key)
            if cached_data is not None:
                # For list: Return a mock QS from cached IDs (simple; for full, deserialize)
                if self.action == 'list':
                    # Cache stores list of IDs; reconstruct minimal QS
                    ids = cached_data.get('ids', [])
                    return base_qs.filter(id__in=ids)
                # For retrieve: Cache full serialized data, but return instance
                elif self.action == 'retrieve':
                    pk = self.kwargs.get('pk')
                    # if pk in cached_data:
                    #     # Return the object from cache if exact match
                    #     instance_data = cached_data[pk]
                    #     # Reconstruct instance (simplified; use from_db_value or similar in prod)
                    #     instance = CustomUser(**instance_data)
                    #     return base_qs.filter(id=pk)  # Still query for full object, but cache hit logged

                    if pk in cached_data:
                        return base_qs.filter(id=pk)

            # On miss, build QS and cache serialized version
            if self.action == "list":
                # Light: select_related for basic profile, no deep nests
                qs = base_qs.select_related("profile", "tenant", "branch")
                serialized_qs = list(qs.values('id', 'email', 'first_name', 'last_name', 'role'))  # Minimal
                set_to_cache(cache_key, {'ids': [item['id'] for item in serialized_qs]}, timeout=300)
                return qs
            # Full prefetch for retrieve/update/detail
            qs = base_qs.prefetch_related(
                "profile__professional_qualifications",
                "profile__employment_details",
                "profile__investment_details",
                "profile__withdrawal_details",
                "profile__education_details",
                "profile__reference_checks",
                "profile__proof_of_address",
                "profile__insurance_verifications",
                "profile__driving_risk_assessments",
                "profile__legal_work_eligibilities",
                "profile__other_user_documents",
            )
            if self.action == 'retrieve':
                pk = self.kwargs.get('pk')
                instance = qs.get(pk=pk)
                from .serializers import CustomUserSerializer
                serialized = CustomUserSerializer(instance).data
                set_to_cache(cache_key, {pk: serialized}, timeout=600)
            return qs
        if self.action == "list":
            # Light: select_related for basic profile, no deep nests
            return base_qs.select_related("profile", "tenant", "branch")
        # Full prefetch for retrieve/update/detail
        return base_qs.prefetch_related(
            "profile__professional_qualifications",
            "profile__employment_details",
            "profile__investment_details",
            "profile__withdrawal_details",
            "profile__education_details",
            "profile__reference_checks",
            "profile__proof_of_address",
            "profile__insurance_verifications",
            "profile__driving_risk_assessments",
            "profile__legal_work_eligibilities",
            "profile__other_user_documents",
        )

    def get_serializer_class(self):
        if self.action == "list":
            return CustomUserListSerializer  # Light for lists
        if self.action in ["create", "update", "partial_update", "bulk_create"]:
            return UserCreateSerializer
        if self.action in ["lock", "unlock", "suspend", "activate"]:
            return UserAccountActionSerializer
        if self.action == "impersonate":
            return UserImpersonateSerializer
        return CustomUserSerializer  # Full for retrieve

    def perform_create(self, serializer):
        tenant = self.request.user.tenant
        user = self.request.user
        if self.request.user.role != "admin" and not self.request.user.is_superuser:
            raise ValidationError("Only admins or superusers can create users.")

        # Restrict setting role to 'admin' unless superuser
        if serializer.validated_data.get('role') == 'admin' and not self.request.user.is_superuser:
            raise ValidationError("Cannot set user role to 'admin'.")

        with tenant_context(tenant):
            user_obj = serializer.save()
            logger.info(f"User created: {user_obj.email} (ID: {user_obj.id}) for tenant {tenant.schema_name}")

            # Invalidate user list cache on create
            from auth_service.utils.cache import delete_tenant_cache
            delete_tenant_cache(tenant.schema_name, 'users_list')

            # ✅ SEND NOTIFICATION EVENT AFTER USER CREATION
            logger.info("🎯 Reached user creation success block. Sending user creation event to notification service.")
            try:
                # Generate a unique event ID in the format 'evt-<uuid>'
                event_id = f"evt-{str(uuid.uuid4())[:8]}"
                # Get user agent from request
                user_agent = self.request.META.get("HTTP_USER_AGENT", "Unknown")
                # Define company name (assuming tenant name or a custom field)
                company_name = tenant.name if hasattr(tenant, 'name') else "Unknown Company"
                # Define login link (customize as needed)
                login_link = settings.WEB_PAGE_URL

                # print("login_link")
                # print(login_link)
                # print("login_link")

                logger.info(f"🎯 {login_link}")

                event_payload = {
                    "metadata": {
                        "tenant_id": str(tenant.unique_id),
                        "event_type": "user.account.created",
                        "event_id": event_id,
                        "created_at": timezone.now().isoformat(),
                        "source": "auth-service",
                    },
                    "data": {
                        "user_email": user_obj.email,
                        "company_name": company_name,
                        "temp_password": serializer.validated_data.get("password", ""),
                        "login_link": login_link,
                        "timestamp": timezone.now().isoformat(),
                        "user_agent": user_agent,
                        "user_id": str(user_obj.id),
                    },
                }

                notifications_url = settings.NOTIFICATIONS_SERVICE_URL + "/events/"
                safe_payload = {**event_payload, "data": {**event_payload["data"], "temp_password": "[REDACTED]"}}
                logger.info(f"➡️ POST to {notifications_url} with payload: {safe_payload}")

                response = requests.post(notifications_url, json=event_payload, timeout=5)
                response.raise_for_status()  # Raise if status != 200
                logger.info(f"✅ Notification sent for {user_obj.email}. Status: {response.status_code}, Response: {response.text}")

            except requests.exceptions.RequestException as e:
                logger.warning(f"[❌ Notification Error] Failed to send user creation event for {user_obj.email}: {str(e)}")
            except Exception as e:
                logger.error(f"[❌ Notification Exception] Unexpected error for {user_obj.email}: {str(e)}")

    def update(self, request, *args, **kwargs):
        tenant = request.user.tenant
        user = request.user
        logger.info(f"Raw PATCH request data for tenant {tenant.schema_name}: {dict(request.data)}")
        logger.info(f"FILES in request: {dict(request.FILES)}")
        with tenant_context(tenant):
            instance = self.get_object()
            if not (user.is_superuser or user.role == "admin" or user.id == instance.id):
                raise PermissionDenied("You do not have permission to update this user.")
            serializer = self.get_serializer(instance, data=request.data, partial=True)
            try:
                serializer.is_valid(raise_exception=True)

                # Restrict setting role to 'admin' unless superuser
                if serializer.validated_data.get('role') == 'admin' and not request.user.is_superuser:
                    raise ValidationError("Cannot set user role to 'admin'.")

                logger.info(f"Validated data for user {instance.email}: {serializer.validated_data}")
            except ValidationError as e:
                logger.error(f"Serializer errors for user {instance.email}: {serializer.errors}")
                raise
            self.perform_update(serializer)
            # Invalidate caches on update
            from auth_service.utils.cache import delete_cache_key, get_cache_key
            user_key = get_cache_key(tenant.schema_name, 'customuser', instance.email)
            delete_cache_key(user_key)
            from auth_service.utils.cache import delete_tenant_cache
            delete_tenant_cache(tenant.schema_name, 'users_list')
            logger.info(f"User {instance.email} updated by {user.email} in tenant {tenant.schema_name}")
            return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        tenant = request.user.tenant
        user = request.user
        with tenant_context(tenant):
            instance = self.get_object()
            if not (user.is_superuser or user.role == "admin"):
                raise PermissionDenied("You do not have permission to delete users.")
            self.perform_destroy(instance)
            # Invalidate on delete
            from auth_service.utils.cache import delete_tenant_cache
            delete_tenant_cache(tenant.schema_name, 'users_list')
            logger.info(f"User {instance.email} deleted by {user.email} in tenant {tenant.schema_name}")
            return Response(status=204)

    @action(detail=True, methods=["post"], url_path="lock")
    def lock(self, request, pk=None):
        tenant = request.user.tenant
        with tenant_context(tenant):
            instance = self.get_object()
            if request.data:  # Optional validation if data provided
                serializer = self.get_serializer(data=request.data, context={"request": request, "user": instance})
                serializer.is_valid(raise_exception=True)
            instance.lock_account(reason=request.data.get("reason", "Manual lock"))
            UserActivity.objects.create(
                user=instance,
                tenant=tenant,
                action="account_lock",
                performed_by=request.user,
                details={"reason": "Manual lock"},
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                success=True,
            )
            # Invalidate user cache on lock
            from auth_service.utils.cache import delete_cache_key, get_cache_key
            user_key = get_cache_key(tenant.schema_name, 'customuser', instance.email)
            delete_cache_key(user_key)
            logger.info(f"User {instance.email} locked by {request.user.email} in tenant {tenant.schema_name}")
            return Response(
                {"status": "success", "message": f"User {instance.email} account locked successfully."}, status=200
            )

    @action(detail=True, methods=["post"], url_path="unlock")
    def unlock(self, request, pk=None):
        tenant = request.user.tenant
        with tenant_context(tenant):
            instance = self.get_object()
            if request.data:
                serializer = self.get_serializer(data=request.data, context={"request": request, "user": instance})
                serializer.is_valid(raise_exception=True)
            instance.unlock_account()
            UserActivity.objects.create(
                user=instance,
                tenant=tenant,
                action="account_unlock",
                performed_by=request.user,
                details={},
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                success=True,
            )
            # Invalidate user cache on unlock
            from auth_service.utils.cache import delete_cache_key, get_cache_key
            user_key = get_cache_key(tenant.schema_name, 'customuser', instance.email)
            delete_cache_key(user_key)
            logger.info(f"User {instance.email} unlocked by {request.user.email} in tenant {tenant.schema_name}")
            return Response(
                {"status": "success", "message": f"User {instance.email} account unlocked successfully."}, status=200
            )

    @action(detail=True, methods=["post"], url_path="suspend")
    def suspend(self, request, pk=None):
        tenant = request.user.tenant
        with tenant_context(tenant):
            instance = self.get_object()
            if request.data:
                serializer = self.get_serializer(data=request.data, context={"request": request, "user": instance})
                serializer.is_valid(raise_exception=True)
            instance.suspend_account()
            UserActivity.objects.create(
                user=instance,
                tenant=tenant,
                action="account_suspend",
                performed_by=request.user,
                details={},
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                success=True,
            )
            # Invalidate user cache on suspend
            from auth_service.utils.cache import delete_cache_key, get_cache_key
            user_key = get_cache_key(tenant.schema_name, 'customuser', instance.email)
            delete_cache_key(user_key)
            logger.info(f"User {instance.email} suspended by {request.user.email} in tenant {tenant.schema_name}")
            return Response(
                {"status": "success", "message": f"User {instance.email} account suspended successfully."}, status=200
            )

    @action(detail=True, methods=["post"], url_path="activate")
    def activate(self, request, pk=None):
        tenant = request.user.tenant
        with tenant_context(tenant):
            instance = self.get_object()
            if request.data:
                serializer = self.get_serializer(data=request.data, context={"request": request, "user": instance})
                serializer.is_valid(raise_exception=True)
            instance.activate_account()
            UserActivity.objects.create(
                user=instance,
                tenant=tenant,
                action="account_activate",
                performed_by=request.user,
                details={},
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                success=True,
            )
            # Invalidate user cache on activate
            from auth_service.utils.cache import delete_cache_key, get_cache_key
            user_key = get_cache_key(tenant.schema_name, 'customuser', instance.email)
            delete_cache_key(user_key)
            logger.info(f"User {instance.email} activated by {request.user.email} in tenant {tenant.schema_name}")
            return Response(
                {"status": "success", "message": f"User {instance.email} account activated successfully."}, status=200
            )

    @action(detail=True, methods=["post"], url_path="impersonate")
    def impersonate(self, request, pk=None):
        tenant = self.request.user.tenant
        with tenant_context(tenant):
            target_user = self.get_object()
            if request.data:
                serializer = self.get_serializer(data=request.data, context={"request": request, "user": target_user})
                serializer.is_valid(raise_exception=True)

            try:
                access_payload = {
                    "jti": str(uuid.uuid4()),
                    "sub": target_user.email,
                    "role": target_user.role,
                    "tenant_id": target_user.tenant.id,
                    "tenant_schema": target_user.tenant.schema_name,
                    "has_accepted_terms": target_user.has_accepted_terms,
                    "user": CustomUserMinimalSerializer(target_user).data,
                    "email": target_user.email,
                    "type": "access",
                    "exp": int((timezone.now() + timedelta(minutes=15)).timestamp()),
                    "impersonated_by": request.user.email,
                }
                access_token = issue_rsa_jwt(access_payload, target_user.tenant)

                refresh_jti = str(uuid.uuid4())
                refresh_payload = {
                    "jti": refresh_jti,
                    "sub": target_user.email,
                    "tenant_id": target_user.tenant.id,
                    "type": "refresh",
                    "exp": int((timezone.now() + timedelta(minutes=30)).timestamp()),
                    "impersonated_by": request.user.email,
                }
                refresh_token = issue_rsa_jwt(refresh_payload, target_user.tenant)

                UserActivity.objects.create(
                    user=target_user,
                    tenant=tenant,
                    action="impersonation",
                    performed_by=request.user,
                    details={"access_jti": access_payload["jti"], "refresh_jti": refresh_jti},
                    ip_address=request.META.get("REMOTE_ADDR"),
                    user_agent=request.META.get("HTTP_USER_AGENT", ""),
                    success=True,
                )

                logger.info(
                    f"User {target_user.email} impersonated by {request.user.email} in tenant {tenant.schema_name}"
                )
                return Response(
                    {
                        "status": "success",
                        "message": f"Impersonation token generated for {target_user.email}",
                        "access": access_token,
                        "refresh": refresh_token,
                        "tenant_id": target_user.tenant.id,
                        "tenant_schema": target_user.tenant.schema_name,
                        "user": CustomUserMinimalSerializer(target_user).data,
                    },
                    status=200,
                )
            except Exception as e:
                logger.error(f"Impersonation failed for {target_user.email}: {str(e)}")
                raise ValidationError(f"Failed to generate impersonation tokens: {str(e)}")

    @action(detail=False, methods=["post"], url_path="bulk-create")
    def bulk_create(self, request):
        """
        Bulk create users with their profiles.
        Payload: List of user objects, each with email, password, first_name, last_name, and optional fields.
        """
        tenant = self.request.user.tenant
        user = self.request.user

        # Check permissions
        if not (user.is_superuser or user.role == "admin"):
            logger.warning(
                f"User {user.email} attempted bulk create without permission in tenant {tenant.schema_name}"
            )
            raise PermissionDenied("Only admins or superusers can create users.")

        # Expect a list of user data
        data = request.data
        if not isinstance(data, list):
            logger.error("Bulk create payload must be a list of user objects")
            raise ValidationError({"detail": "Payload must be a list of user objects"})

        results = []
        errors = []
        with tenant_context(tenant):
            with transaction.atomic():
                for index, user_data in enumerate(data):
                    # Ensure role is not 'client' for UserViewSet
                    if user_data.get("role") == "client":
                        logger.error(f"Cannot create client user at index {index} via UserViewSet")
                        errors.append({
                            "index": index,
                            "email": user_data.get("email", "unknown"),
                            "errors": {"role": "Client users cannot be created via this endpoint."}
                        })
                        continue

                    # Restrict setting role to 'admin' unless superuser
                    if user_data.get('role') == 'admin' and not self.request.user.is_superuser:
                        logger.error(f"Cannot set role to admin at index {index} via UserViewSet")
                        errors.append({
                            "index": index,
                            "email": user_data.get("email", "unknown"),
                            "errors": {"role": "Cannot set user role to 'admin'."}
                        })
                        continue

                    serializer = UserCreateSerializer(data=user_data, context={"request": request})
                    try:
                        serializer.is_valid(raise_exception=True)
                        user_obj = serializer.save()
                        logger.info(f"Created user {user_obj.email} in tenant {tenant.schema_name} during bulk create")

                        # Invalidate list cache on bulk create
                        from auth_service.utils.cache import delete_tenant_cache
                        delete_tenant_cache(tenant.schema_name, 'users_list')

                        # ✅ SEND NOTIFICATION EVENT AFTER USER CREATION
                        logger.info(f"🎯 Sending user creation event for {user_obj.email} to notification service.")
                        try:
                            # Generate a unique event ID in the format 'evt-<uuid>'
                            event_id = f"evt-{str(uuid.uuid4())[:8]}"
                            # Get user agent from request
                            user_agent = request.META.get("HTTP_USER_AGENT", "Unknown")
                            # Define company name (assuming tenant name or a custom field)
                            company_name = tenant.name if hasattr(tenant, 'name') else "Unknown Company"
                            # Define login link (customize as needed)
                            login_link = "https://learn.prolianceltd.com/home/login"

                            event_payload = {
                                "metadata": {
                                    "tenant_id": str(tenant.unique_id),
                                    "event_type": "user.account.created",
                                    "event_id": event_id,
                                    "created_at": timezone.now().isoformat(),
                                    "source": "auth-service",
                                },
                                "data": {
                                    "user_email": user_obj.email,
                                    "company_name": company_name,
                                    "temp_password": serializer.validated_data.get("password", ""),
                                    "login_link": login_link,
                                    "timestamp": timezone.now().isoformat(),
                                    "user_agent": user_agent,
                                    "user_id": str(user_obj.id),
                                },
                            }

                            notifications_url = settings.NOTIFICATIONS_SERVICE_URL + "/events/"
                            safe_payload = {**event_payload, "data": {**event_payload["data"], "temp_password": "[REDACTED]"}}
                            logger.info(f"➡️ POST to {notifications_url} with payload: {safe_payload}")

                            response = requests.post(notifications_url, json=event_payload, timeout=5)
                            response.raise_for_status()  # Raise if status != 200
                            logger.info(f"✅ Notification sent for {user_obj.email}. Status: {response.status_code}, Response: {response.text}")

                        except requests.exceptions.RequestException as e:
                            logger.warning(f"[❌ Notification Error] Failed to send user creation event for {user_obj.email}: {str(e)}")
                        except Exception as e:
                            logger.error(f"[❌ Notification Exception] Unexpected error for {user_obj.email}: {str(e)}")

                        results.append(
                            {
                                "status": "success",
                                "email": user_obj.email,
                                "id": user_obj.id,
                                "data": CustomUserSerializer(user_obj).data,
                            }
                        )
                    except ValidationError as e:
                        logger.error(f"Failed to create user at index {index}: {str(e)}")
                        errors.append({"index": index, "email": user_data.get("email", "unknown"), "errors": e.detail})

        # Log the overall result
        logger.info(
            f"Bulk create completed in tenant {tenant.schema_name}: {len(results)} succeeded, {len(errors)} failed"
        )

        # Prepare response
        response_data = {
            "status": "partial_success" if errors else "success",
            "created": results,
            "errors": errors,
            "message": f"Created {len(results)} users, {len(errors)} failed",
        }
        status_code = status.HTTP_201_CREATED if results else status.HTTP_400_BAD_REQUEST
        return Response(response_data, status=status_code)
    

class PublicRegisterView(generics.CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = UserCreateSerializer

    def create(self, request, *args, **kwargs):
        # Use request.data directly for multipart/form-data handling
        data = request.data
        
        # Flatten list values if needed (for single-value fields from FormData)
        flattened_data = {}
        for k, v in data.items():
            if isinstance(v, list) and len(v) == 1:
                flattened_data[k] = v[0]
            else:
                flattened_data[k] = v
        
        tenant_id = flattened_data.get('tenant_id')
        tenant_schema = flattened_data.get('tenant_schema')
        
        if not tenant_id or not tenant_schema:
            return Response(
                {'error': 'tenant_id and tenant_schema are required for public registration.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Use unique_id for UUID lookup instead of id
            tenant = Tenant.objects.get(unique_id=tenant_id, schema_name=tenant_schema)
        except Tenant.DoesNotExist:
            return Response(
                {'error': 'Invalid tenant information.'},
                status=status.HTTP_404_NOT_FOUND
            )

        with tenant_context(tenant):
            # Create a minimal mock user to satisfy serializer requirements
            class SimpleUser:
                def __init__(self):
                    self.id = 'public-system'
                    self.email = 'public@system.com'
                    self.first_name = 'Public'
                    self.last_name = 'Registration'
                    self.role = 'admin'
                    self.tenant = tenant
                    self.is_superuser = False
                
                def is_authenticated(self):
                    return True
                
                def is_anonymous(self):
                    return False

            # Create a modified request object
            # modified_request = type('Request', (), {
            #     'user': SimpleUser(),
            #     'data': request.data,
            #     'FILES': request.FILES,
            #     'META': request.META
            # })()

            modified_request = type('Request', (), {
                'user': SimpleUser(),
                'data': request.data,
                'FILES': request.FILES,
                'META': request.META,
                'headers': request.headers if hasattr(request, 'headers') else {},  # ✅ Add this
            })()


            # Prepopulate required profile nested fields with empty lists to satisfy serializer
            profile_data = {
                'professional_qualifications': [],
                'employment_details': [],
                'education_details': [],
                'reference_checks': [],
                'proof_of_address': [],
                'insurance_verifications': [],
                'driving_risk_assessments': [],
                'legal_work_eligibilities': [],
                'other_user_documents': [],
                # Add other profile fields if needed, e.g., from form
                'work_phone': flattened_data.get('phoneNumber', ''),
                'personal_phone': flattened_data.get('phoneNumber', ''),
                'next_of_kin': flattened_data.get('nextOfKinName', ''),
                'next_of_kin_phone_number': flattened_data.get('nextOfKinPhone', ''),
                'relationship_to_next_of_kin': 'N/A',
                'dob': None if not flattened_data.get('dob', '').strip() else flattened_data.get('dob'),
                'gender': flattened_data.get('sex', ''),
            }
            flattened_data['profile'] = profile_data

            # Use provided email if available; generate only if missing
            if 'email' not in flattened_data:
                # Generate temp email from phone or name
                phone = flattened_data.get('phoneNumber', '')
                name = f"{flattened_data.get('firstName', '')}.{flattened_data.get('surname', '')}".lower()
                base_email = f"{name.replace(' ', '')}@{tenant_schema}.temp.com"
                email = base_email
                counter = 1
                while CustomUser.objects.filter(email=email).exists():
                    email = f"{name.replace(' ', '')}_{counter}@{tenant_schema}.temp.com"
                    counter += 1
                flattened_data['email'] = email
            else:
                provided_email = flattened_data['email']
                if CustomUser.objects.filter(email=provided_email).exists():
                    return Response(
                        {'error': 'The provided email address already exists. Please use a different email.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                logger.info(f"Using provided email: {provided_email} for public registration")

            if 'password' not in flattened_data:
                # Generate temp password
                temp_password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
                flattened_data['password'] = temp_password
            if 'first_name' not in flattened_data:
                flattened_data['first_name'] = flattened_data.get('firstName', '')
            if 'last_name' not in flattened_data:
                flattened_data['last_name'] = flattened_data.get('surname', '')
            if 'username' not in flattened_data:
                flattened_data['username'] = f"{flattened_data['first_name'][:3]}{flattened_data['last_name'][:3]}{random.randint(100,999)}".lower()

            # Use the modified request in serializer context
            serializer = self.get_serializer(data=flattened_data, context={'request': modified_request})
            serializer.is_valid(raise_exception=True)
            
            # For public registration, default role to 'user' or 'investor' based on context
            if 'role' not in serializer.validated_data:
                serializer.validated_data['role'] = 'user'
            
            user_obj = serializer.save()
            logger.info(f"Public user created: {user_obj.email} (ID: {user_obj.id}) for tenant {tenant.schema_name}")

            # Send notification event
            try:
                event_id = f"evt-{str(uuid.uuid4())[:8]}"
                user_agent = request.META.get("HTTP_USER_AGENT", "Unknown")
                company_name = tenant.name if hasattr(tenant, 'name') else "Unknown Company"
                login_link = settings.WEB_PAGE_URL

                event_payload = {
                    "metadata": {
                        "tenant_id": str(tenant.unique_id),
                        "event_type": "user.account.created",
                        "event_id": event_id,
                        "created_at": timezone.now().isoformat(),
                        "source": "auth-service",
                    },
                    "data": {
                        "user_email": user_obj.email,
                        "company_name": company_name,
                        "temp_password": flattened_data['password'],
                        "login_link": login_link,
                        "timestamp": timezone.now().isoformat(),
                        "user_agent": user_agent,
                        "user_id": str(user_obj.id),
                    },
                }

                notifications_url = settings.NOTIFICATIONS_SERVICE_URL + "/events/"
                safe_payload = {**event_payload, "data": {**event_payload["data"], "temp_password": "[REDACTED]"}}
                logger.info(f"➡️ POST to {notifications_url} with payload: {safe_payload}")

                response = requests.post(notifications_url, json=event_payload, timeout=5)
                response.raise_for_status()
                logger.info(f"✅ Public registration notification sent for {user_obj.email}. Status: {response.status_code}")

            except Exception as e:
                logger.warning(f"[❌ Notification Error] Failed to send public registration event for {user_obj.email}: {str(e)}")

            return Response({
                'status': 'success',
                'message': 'Account created successfully!',
                'user_id': user_obj.id,
                'email': user_obj.email,
                'temp_password': flattened_data['password'],
                'login_link': settings.WEB_PAGE_URL
            }, status=status.HTTP_201_CREATED)
            

class UsersViewSetNoPagination(viewsets.ModelViewSet):
    queryset = CustomUser.objects.all()
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_base_queryset(self):
        """DRY helper for tenant-filtered queryset with role-based access, excluding clients."""
        tenant = self.request.user.tenant
        user = self.request.user
        with tenant_context(tenant):
            # Exclude users with role='client' to separate them from CustomUser list
            base_qs = CustomUser.objects.filter(tenant=tenant).exclude(role='client')
            if not (user.is_superuser or user.role == "admin"):
                if user.role == "team_manager":
                    pass  # All non-client users in tenant
                elif user.role == "recruiter" and user.branch:
                    base_qs = base_qs.filter(branch=user.branch)
                else:
                    base_qs = base_qs.filter(id=user.id)  # Self only
            return base_qs

    def get_queryset(self):
        """Optimized queryset: Minimal for lists, full prefetch for details."""
        base_qs = self.get_base_queryset()
        tenant_schema = self.request.tenant.schema_name
        if self.action in ['list', 'retrieve'] and settings.CACHE_ENABLED:
            from auth_service.utils.cache import get_cache_key, get_from_cache, set_to_cache
            
            cache_key = get_cache_key(tenant_schema, f'users_{self.action}')
            cached_data = get_from_cache(cache_key)
            if cached_data is not None:
                # For list: Return a mock QS from cached IDs (simple; for full, deserialize)
                if self.action == 'list':
                    # Cache stores list of IDs; reconstruct minimal QS
                    ids = cached_data.get('ids', [])
                    return base_qs.filter(id__in=ids)
                # For retrieve: Cache full serialized data, but return instance
                elif self.action == 'retrieve':
                    pk = self.kwargs.get('pk')
                    # if pk in cached_data:
                    #     # Return the object from cache if exact match
                    #     instance_data = cached_data[pk]
                    #     # Reconstruct instance (simplified; use from_db_value or similar in prod)
                    #     instance = CustomUser(**instance_data)
                    #     return base_qs.filter(id=pk)  # Still query for full object, but cache hit logged

                    if pk in cached_data:
                        return base_qs.filter(id=pk)

            # On miss, build QS and cache serialized version
            if self.action == "list":
                # Light: select_related for basic profile, no deep nests
                qs = base_qs.select_related("profile", "tenant", "branch")
                serialized_qs = list(qs.values('id', 'email', 'first_name', 'last_name', 'role'))  # Minimal
                set_to_cache(cache_key, {'ids': [item['id'] for item in serialized_qs]}, timeout=300)
                return qs
            # Full prefetch for retrieve/update/detail
            qs = base_qs.prefetch_related(
                "profile__professional_qualifications",
                "profile__employment_details",
                "profile__education_details",
                "profile__reference_checks",
                "profile__proof_of_address",
                "profile__insurance_verifications",
                "profile__driving_risk_assessments",
                "profile__legal_work_eligibilities",
                "profile__other_user_documents",
            )
            if self.action == 'retrieve':
                pk = self.kwargs.get('pk')
                instance = qs.get(pk=pk)
                from .serializers import CustomUserSerializer
                serialized = CustomUserSerializer(instance).data
                set_to_cache(cache_key, {pk: serialized}, timeout=600)
            return qs
        if self.action == "list":
            # Light: select_related for basic profile, no deep nests
            return base_qs.select_related("profile", "tenant", "branch")
        # Full prefetch for retrieve/update/detail
        return base_qs.prefetch_related(
            "profile__professional_qualifications",
            "profile__employment_details",
            "profile__education_details",
            "profile__reference_checks",
            "profile__proof_of_address",
            "profile__insurance_verifications",
            "profile__driving_risk_assessments",
            "profile__legal_work_eligibilities",
            "profile__other_user_documents",
        )

    def get_serializer_class(self):
        if self.action == "list":
            return CustomUserListSerializer  # Light for lists
        if self.action in ["create", "update", "partial_update", "bulk_create"]:
            return UserCreateSerializer
        if self.action in ["lock", "unlock", "suspend", "activate"]:
            return UserAccountActionSerializer
        if self.action == "impersonate":
            return UserImpersonateSerializer
        return CustomUserSerializer  # Full for retrieve

    def perform_create(self, serializer):
        tenant = self.request.user.tenant
        user = self.request.user
        if self.request.user.role != "admin" and not self.request.user.is_superuser:
            raise ValidationError("Only admins or superusers can create users.")

        # Restrict setting role to 'admin' unless superuser
        if serializer.validated_data.get('role') == 'admin' and not self.request.user.is_superuser:
            raise ValidationError("Cannot set user role to 'admin'.")

        with tenant_context(tenant):
            user_obj = serializer.save()
            logger.info(f"User created: {user_obj.email} (ID: {user_obj.id}) for tenant {tenant.schema_name}")

            # Invalidate user list cache on create
            from auth_service.utils.cache import delete_tenant_cache
            delete_tenant_cache(tenant.schema_name, 'users_list')

            # ✅ SEND NOTIFICATION EVENT AFTER USER CREATION
            logger.info("🎯 Reached user creation success block. Sending user creation event to notification service.")
            try:
                # Generate a unique event ID in the format 'evt-<uuid>'
                event_id = f"evt-{str(uuid.uuid4())[:8]}"
                # Get user agent from request
                user_agent = self.request.META.get("HTTP_USER_AGENT", "Unknown")
                # Define company name (assuming tenant name or a custom field)
                company_name = tenant.name if hasattr(tenant, 'name') else "Unknown Company"
                # Define login link (customize as needed)
                login_link = settings.WEB_PAGE_URL

                # print("login_link")
                # print(login_link)
                # print("login_link")

                logger.info(f"🎯 {login_link}")

                event_payload = {
                    "metadata": {
                        "tenant_id": str(tenant.unique_id),
                        "event_type": "user.account.created",
                        "event_id": event_id,
                        "created_at": timezone.now().isoformat(),
                        "source": "auth-service",
                    },
                    "data": {
                        "user_email": user_obj.email,
                        "company_name": company_name,
                        "temp_password": serializer.validated_data.get("password", ""),
                        "login_link": login_link,
                        "timestamp": timezone.now().isoformat(),
                        "user_agent": user_agent,
                        "user_id": str(user_obj.id),
                    },
                }

                notifications_url = settings.NOTIFICATIONS_SERVICE_URL + "/events/"
                safe_payload = {**event_payload, "data": {**event_payload["data"], "temp_password": "[REDACTED]"}}
                logger.info(f"➡️ POST to {notifications_url} with payload: {safe_payload}")

                response = requests.post(notifications_url, json=event_payload, timeout=5)
                response.raise_for_status()  # Raise if status != 200
                logger.info(f"✅ Notification sent for {user_obj.email}. Status: {response.status_code}, Response: {response.text}")

            except requests.exceptions.RequestException as e:
                logger.warning(f"[❌ Notification Error] Failed to send user creation event for {user_obj.email}: {str(e)}")
            except Exception as e:
                logger.error(f"[❌ Notification Exception] Unexpected error for {user_obj.email}: {str(e)}")

    def update(self, request, *args, **kwargs):
        tenant = request.user.tenant
        user = request.user
        logger.info(f"Raw PATCH request data for tenant {tenant.schema_name}: {dict(request.data)}")
        logger.info(f"FILES in request: {dict(request.FILES)}")
        with tenant_context(tenant):
            instance = self.get_object()
            if not (user.is_superuser or user.role == "admin" or user.id == instance.id):
                raise PermissionDenied("You do not have permission to update this user.")
            serializer = self.get_serializer(instance, data=request.data, partial=True)
            try:
                serializer.is_valid(raise_exception=True)

                # Restrict setting role to 'admin' unless superuser
                if serializer.validated_data.get('role') == 'admin' and not request.user.is_superuser:
                    raise ValidationError("Cannot set user role to 'admin'.")

                logger.info(f"Validated data for user {instance.email}: {serializer.validated_data}")
            except ValidationError as e:
                logger.error(f"Serializer errors for user {instance.email}: {serializer.errors}")
                raise
            self.perform_update(serializer)
            # Invalidate caches on update
            from auth_service.utils.cache import delete_cache_key, get_cache_key
            user_key = get_cache_key(tenant.schema_name, 'customuser', instance.email)
            delete_cache_key(user_key)
            from auth_service.utils.cache import delete_tenant_cache
            delete_tenant_cache(tenant.schema_name, 'users_list')
            logger.info(f"User {instance.email} updated by {user.email} in tenant {tenant.schema_name}")
            return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        tenant = request.user.tenant
        user = request.user
        with tenant_context(tenant):
            instance = self.get_object()
            if not (user.is_superuser or user.role == "admin"):
                raise PermissionDenied("You do not have permission to delete users.")
            self.perform_destroy(instance)
            # Invalidate on delete
            from auth_service.utils.cache import delete_tenant_cache
            delete_tenant_cache(tenant.schema_name, 'users_list')
            logger.info(f"User {instance.email} deleted by {user.email} in tenant {tenant.schema_name}")
            return Response(status=204)

    @action(detail=True, methods=["post"], url_path="lock")
    def lock(self, request, pk=None):
        tenant = request.user.tenant
        with tenant_context(tenant):
            instance = self.get_object()
            if request.data:  # Optional validation if data provided
                serializer = self.get_serializer(data=request.data, context={"request": request, "user": instance})
                serializer.is_valid(raise_exception=True)
            instance.lock_account(reason=request.data.get("reason", "Manual lock"))
            UserActivity.objects.create(
                user=instance,
                tenant=tenant,
                action="account_lock",
                performed_by=request.user,
                details={"reason": "Manual lock"},
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                success=True,
            )
            # Invalidate user cache on lock
            from auth_service.utils.cache import delete_cache_key, get_cache_key
            user_key = get_cache_key(tenant.schema_name, 'customuser', instance.email)
            delete_cache_key(user_key)
            logger.info(f"User {instance.email} locked by {request.user.email} in tenant {tenant.schema_name}")
            return Response(
                {"status": "success", "message": f"User {instance.email} account locked successfully."}, status=200
            )

    @action(detail=True, methods=["post"], url_path="unlock")
    def unlock(self, request, pk=None):
        tenant = request.user.tenant
        with tenant_context(tenant):
            instance = self.get_object()
            if request.data:
                serializer = self.get_serializer(data=request.data, context={"request": request, "user": instance})
                serializer.is_valid(raise_exception=True)
            instance.unlock_account()
            UserActivity.objects.create(
                user=instance,
                tenant=tenant,
                action="account_unlock",
                performed_by=request.user,
                details={},
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                success=True,
            )
            # Invalidate user cache on unlock
            from auth_service.utils.cache import delete_cache_key, get_cache_key
            user_key = get_cache_key(tenant.schema_name, 'customuser', instance.email)
            delete_cache_key(user_key)
            logger.info(f"User {instance.email} unlocked by {request.user.email} in tenant {tenant.schema_name}")
            return Response(
                {"status": "success", "message": f"User {instance.email} account unlocked successfully."}, status=200
            )

    @action(detail=True, methods=["post"], url_path="suspend")
    def suspend(self, request, pk=None):
        tenant = request.user.tenant
        with tenant_context(tenant):
            instance = self.get_object()
            if request.data:
                serializer = self.get_serializer(data=request.data, context={"request": request, "user": instance})
                serializer.is_valid(raise_exception=True)
            instance.suspend_account()
            UserActivity.objects.create(
                user=instance,
                tenant=tenant,
                action="account_suspend",
                performed_by=request.user,
                details={},
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                success=True,
            )
            # Invalidate user cache on suspend
            from auth_service.utils.cache import delete_cache_key, get_cache_key
            user_key = get_cache_key(tenant.schema_name, 'customuser', instance.email)
            delete_cache_key(user_key)
            logger.info(f"User {instance.email} suspended by {request.user.email} in tenant {tenant.schema_name}")
            return Response(
                {"status": "success", "message": f"User {instance.email} account suspended successfully."}, status=200
            )

    @action(detail=True, methods=["post"], url_path="activate")
    def activate(self, request, pk=None):
        tenant = request.user.tenant
        with tenant_context(tenant):
            instance = self.get_object()
            if request.data:
                serializer = self.get_serializer(data=request.data, context={"request": request, "user": instance})
                serializer.is_valid(raise_exception=True)
            instance.activate_account()
            UserActivity.objects.create(
                user=instance,
                tenant=tenant,
                action="account_activate",
                performed_by=request.user,
                details={},
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                success=True,
            )
            # Invalidate user cache on activate
            from auth_service.utils.cache import delete_cache_key, get_cache_key
            user_key = get_cache_key(tenant.schema_name, 'customuser', instance.email)
            delete_cache_key(user_key)
            logger.info(f"User {instance.email} activated by {request.user.email} in tenant {tenant.schema_name}")
            return Response(
                {"status": "success", "message": f"User {instance.email} account activated successfully."}, status=200
            )

    @action(detail=True, methods=["post"], url_path="impersonate")
    def impersonate(self, request, pk=None):
        tenant = self.request.user.tenant
        with tenant_context(tenant):
            target_user = self.get_object()
            if request.data:
                serializer = self.get_serializer(data=request.data, context={"request": request, "user": target_user})
                serializer.is_valid(raise_exception=True)

            try:
                access_payload = {
                    "jti": str(uuid.uuid4()),
                    "sub": target_user.email,
                    "role": target_user.role,
                    "tenant_id": target_user.tenant.id,
                    "tenant_schema": target_user.tenant.schema_name,
                    "has_accepted_terms": target_user.has_accepted_terms,
                    "user": CustomUserMinimalSerializer(target_user).data,
                    "email": target_user.email,
                    "type": "access",
                    "exp": int((timezone.now() + timedelta(minutes=15)).timestamp()),
                    "impersonated_by": request.user.email,
                }
                access_token = issue_rsa_jwt(access_payload, target_user.tenant)

                refresh_jti = str(uuid.uuid4())
                refresh_payload = {
                    "jti": refresh_jti,
                    "sub": target_user.email,
                    "tenant_id": target_user.tenant.id,
                    "type": "refresh",
                    "exp": int((timezone.now() + timedelta(minutes=30)).timestamp()),
                    "impersonated_by": request.user.email,
                }
                refresh_token = issue_rsa_jwt(refresh_payload, target_user.tenant)

                UserActivity.objects.create(
                    user=target_user,
                    tenant=tenant,
                    action="impersonation",
                    performed_by=request.user,
                    details={"access_jti": access_payload["jti"], "refresh_jti": refresh_jti},
                    ip_address=request.META.get("REMOTE_ADDR"),
                    user_agent=request.META.get("HTTP_USER_AGENT", ""),
                    success=True,
                )

                logger.info(
                    f"User {target_user.email} impersonated by {request.user.email} in tenant {tenant.schema_name}"
                )
                return Response(
                    {
                        "status": "success",
                        "message": f"Impersonation token generated for {target_user.email}",
                        "access": access_token,
                        "refresh": refresh_token,
                        "tenant_id": target_user.tenant.id,
                        "tenant_schema": target_user.tenant.schema_name,
                        "user": CustomUserMinimalSerializer(target_user).data,
                    },
                    status=200,
                )
            except Exception as e:
                logger.error(f"Impersonation failed for {target_user.email}: {str(e)}")
                raise ValidationError(f"Failed to generate impersonation tokens: {str(e)}")

    @action(detail=False, methods=["post"], url_path="bulk-create")
    def bulk_create(self, request):
        """
        Bulk create users with their profiles.
        Payload: List of user objects, each with email, password, first_name, last_name, and optional fields.
        """
        tenant = self.request.user.tenant
        user = self.request.user

        # Check permissions
        if not (user.is_superuser or user.role == "admin"):
            logger.warning(
                f"User {user.email} attempted bulk create without permission in tenant {tenant.schema_name}"
            )
            raise PermissionDenied("Only admins or superusers can create users.")

        # Expect a list of user data
        data = request.data
        if not isinstance(data, list):
            logger.error("Bulk create payload must be a list of user objects")
            raise ValidationError({"detail": "Payload must be a list of user objects"})

        results = []
        errors = []
        with tenant_context(tenant):
            with transaction.atomic():
                for index, user_data in enumerate(data):
                    # Ensure role is not 'client' for UserViewSet
                    if user_data.get("role") == "client":
                        logger.error(f"Cannot create client user at index {index} via UserViewSet")
                        errors.append({
                            "index": index,
                            "email": user_data.get("email", "unknown"),
                            "errors": {"role": "Client users cannot be created via this endpoint."}
                        })
                        continue

                    # Restrict setting role to 'admin' unless superuser
                    if user_data.get('role') == 'admin' and not self.request.user.is_superuser:
                        logger.error(f"Cannot set role to admin at index {index} via UserViewSet")
                        errors.append({
                            "index": index,
                            "email": user_data.get("email", "unknown"),
                            "errors": {"role": "Cannot set user role to 'admin'."}
                        })
                        continue

                    serializer = UserCreateSerializer(data=user_data, context={"request": request})
                    try:
                        serializer.is_valid(raise_exception=True)
                        user_obj = serializer.save()
                        logger.info(f"Created user {user_obj.email} in tenant {tenant.schema_name} during bulk create")

                        # Invalidate list cache on bulk create
                        from auth_service.utils.cache import delete_tenant_cache
                        delete_tenant_cache(tenant.schema_name, 'users_list')

                        # ✅ SEND NOTIFICATION EVENT AFTER USER CREATION
                        logger.info(f"🎯 Sending user creation event for {user_obj.email} to notification service.")
                        try:
                            # Generate a unique event ID in the format 'evt-<uuid>'
                            event_id = f"evt-{str(uuid.uuid4())[:8]}"
                            # Get user agent from request
                            user_agent = request.META.get("HTTP_USER_AGENT", "Unknown")
                            # Define company name (assuming tenant name or a custom field)
                            company_name = tenant.name if hasattr(tenant, 'name') else "Unknown Company"
                            # Define login link (customize as needed)
                            login_link = "https://learn.prolianceltd.com/home/login"

                            event_payload = {
                                "metadata": {
                                    "tenant_id": str(tenant.unique_id),
                                    "event_type": "user.account.created",
                                    "event_id": event_id,
                                    "created_at": timezone.now().isoformat(),
                                    "source": "auth-service",
                                },
                                "data": {
                                    "user_email": user_obj.email,
                                    "company_name": company_name,
                                    "temp_password": serializer.validated_data.get("password", ""),
                                    "login_link": login_link,
                                    "timestamp": timezone.now().isoformat(),
                                    "user_agent": user_agent,
                                    "user_id": str(user_obj.id),
                                },
                            }

                            notifications_url = settings.NOTIFICATIONS_SERVICE_URL + "/events/"
                            safe_payload = {**event_payload, "data": {**event_payload["data"], "temp_password": "[REDACTED]"}}
                            logger.info(f"➡️ POST to {notifications_url} with payload: {safe_payload}")

                            response = requests.post(notifications_url, json=event_payload, timeout=5)
                            response.raise_for_status()  # Raise if status != 200
                            logger.info(f"✅ Notification sent for {user_obj.email}. Status: {response.status_code}, Response: {response.text}")

                        except requests.exceptions.RequestException as e:
                            logger.warning(f"[❌ Notification Error] Failed to send user creation event for {user_obj.email}: {str(e)}")
                        except Exception as e:
                            logger.error(f"[❌ Notification Exception] Unexpected error for {user_obj.email}: {str(e)}")

                        results.append(
                            {
                                "status": "success",
                                "email": user_obj.email,
                                "id": user_obj.id,
                                "data": CustomUserSerializer(user_obj).data,
                            }
                        )
                    except ValidationError as e:
                        logger.error(f"Failed to create user at index {index}: {str(e)}")
                        errors.append({"index": index, "email": user_data.get("email", "unknown"), "errors": e.detail})

        # Log the overall result
        logger.info(
            f"Bulk create completed in tenant {tenant.schema_name}: {len(results)} succeeded, {len(errors)} failed"
        )

        # Prepare response
        response_data = {
            "status": "partial_success" if errors else "success",
            "created": results,
            "errors": errors,
            "message": f"Created {len(results)} users, {len(errors)} failed",
        }
        status_code = status.HTTP_201_CREATED if results else status.HTTP_400_BAD_REQUEST
        return Response(response_data, status=status_code)
    

class LoginAttemptViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = UserActivity.objects.filter(action="login")
    serializer_class = UserActivitySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    def get_queryset(self):
        tenant = self.request.user.tenant
        user = self.request.user
        with tenant_context(tenant):
            if not (user.is_superuser or user.role == "admin"):
                raise PermissionDenied("Only admins or superusers can view login attempts.")

            queryset = UserActivity.objects.filter(tenant=tenant, action="login")

            email = self.request.query_params.get("email")
            ip_address = self.request.query_params.get("ip_address")
            date_from = self.request.query_params.get("date_from")
            date_to = self.request.query_params.get("date_to")
            success = self.request.query_params.get("success")

            if email:
                queryset = queryset.filter(user__email__icontains=email)
            if ip_address:
                queryset = queryset.filter(ip_address=ip_address)
            if date_from:
                queryset = queryset.filter(timestamp__gte=date_from)
            if date_to:
                queryset = queryset.filter(timestamp__lte=date_to)
            if success is not None:
                queryset = queryset.filter(success=(success.lower() == "true"))

            return queryset.order_by("-timestamp")


class BlockedIPViewSet(viewsets.ModelViewSet):
    queryset = BlockedIP.objects.all()
    serializer_class = BlockedIPSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    def get_queryset(self):
        tenant = self.request.user.tenant
        user = self.request.user
        with tenant_context(tenant):
            if not (user.is_superuser or user.role == "admin"):
                raise PermissionDenied("Only admins or superusers can manage blocked IPs.")
            return BlockedIP.objects.filter(tenant=tenant).order_by("-blocked_at")

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user.tenant, blocked_by=self.request.user, is_active=True)
        UserActivity.objects.create(
            user=None,
            tenant=self.request.user.tenant,
            action="ip_block",
            performed_by=self.request.user,
            details={"ip_address": serializer.validated_data["ip_address"]},
            ip_address=self.request.META.get("REMOTE_ADDR"),
            user_agent=self.request.META.get("HTTP_USER_AGENT", ""),
            success=True,
        )
        logger.info(
            f"IP {serializer.validated_data['ip_address']} blocked by {self.request.user.email} in tenant {self.request.user.tenant.schema_name}"
        )

    def perform_update(self, serializer):
        serializer.save(blocked_by=self.request.user)
        logger.info(
            f"IP {serializer.validated_data['ip_address']} updated by {self.request.user.email} in tenant {self.request.user.tenant.schema_name}"
        )

    @action(detail=True, methods=["post"], url_path="unblock")
    def unblock(self, request, pk=None):
        tenant = request.user.tenant
        with tenant_context(tenant):
            ip = self.get_object()
            if not (request.user.is_superuser or request.user.role == "admin"):
                raise PermissionDenied("Only admins or superusers can unblock IPs.")
            ip.is_active = False
            ip.save()
            UserActivity.objects.create(
                user=None,
                tenant=tenant,
                action="ip_unblock",
                performed_by=request.user,
                details={"ip_address": ip.ip_address},
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                success=True,
            )
            logger.info(f"IP {ip.ip_address} unblock by {request.user.email} in tenant {tenant.schema_name}")
            return Response(
                {"status": "success", "message": f"IP {ip.ip_address} unblocked successfully."},
                status=status.HTTP_200_OK,
            )


class EnhancedUserActivityViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = UserActivity.objects.all()
    serializer_class = UserActivitySerializer
    permission_classes = [AllowAny]
    pagination_class = CustomPagination
    
    def get_queryset(self):
        tenant = self.request.user.tenant
        user = self.request.user
        
        if not (user.is_superuser or user.role in ["admin", "team_manager"]):
            raise PermissionDenied("Only admins or team managers can view activity logs.")
        
        queryset = UserActivity.objects.filter(tenant=tenant)
        
        # Apply comprehensive filtering
        queryset = self._apply_advanced_filters(queryset)
        
        return queryset.select_related('user', 'performed_by', 'tenant').order_by("-timestamp")

    def _apply_advanced_filters(self, queryset):
        """Apply comprehensive filtering with support for multiple values"""
        params = self.request.query_params
        
        # Action type filter (supports multiple actions)
        actions = params.getlist("action") or params.getlist("action[]")
        if actions:
            queryset = queryset.filter(action__in=actions)
        
        # User filter (email or ID)
        user_filter = params.get("user")
        if user_filter:
            queryset = queryset.filter(
                Q(user__email__icontains=user_filter) |
                Q(user__id__icontains=user_filter)
            )
        
        # Performed by filter
        performed_by = params.get("performed_by")
        if performed_by:
            queryset = queryset.filter(
                Q(performed_by__email__icontains=performed_by) |
                Q(performed_by__id__icontains=performed_by)
            )
        
        # Date range filter
        date_from = params.get("date_from")
        date_to = params.get("date_to")
        if date_from:
            try:
                date_from = timezone.make_aware(datetime.strptime(date_from, "%Y-%m-%d"))
                queryset = queryset.filter(timestamp__gte=date_from)
            except ValueError:
                pass
        if date_to:
            try:
                date_to = timezone.make_aware(datetime.strptime(date_to, "%Y-%m-%d"))
                date_to = date_to + timedelta(days=1)  # Include entire end day
                queryset = queryset.filter(timestamp__lt=date_to)
            except ValueError:
                pass
        
        # Success status filter
        success = params.get("success")
        if success is not None:
            queryset = queryset.filter(success=(success.lower() == "true"))
        
        # IP address filter
        ip_address = params.get("ip_address")
        if ip_address:
            queryset = queryset.filter(ip_address=ip_address)
        
        # Search in details (basic text search)
        search = params.get("search")
        if search:
            queryset = queryset.filter(
                Q(action__icontains=search) |
                Q(user__email__icontains=search) |
                Q(performed_by__email__icontains=search) |
                Q(ip_address__icontains=search) |
                Q(details__icontains=search)
            )
        
        return queryset

    @action(detail=False, methods=['get'], url_path='dashboard-stats')
    def dashboard_stats(self, request):
        """Get comprehensive dashboard statistics"""
        tenant = request.user.tenant
        days = int(request.query_params.get('days', 7))  # Default to 7 days
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Base queryset for the period
        activities = UserActivity.objects.filter(
            tenant=tenant,
            timestamp__gte=start_date,
            timestamp__lte=end_date
        )
        
        # Key metrics
        total_activities = activities.count()
        successful_activities = activities.filter(success=True).count()
        failed_activities = activities.filter(success=False).count()
        
        # User engagement metrics
        active_users_count = activities.values('user').distinct().count()
        performing_users_count = activities.values('performed_by').distinct().count()
        
        # Success rate calculation
        success_rate = round((successful_activities / total_activities * 100), 2) if total_activities > 0 else 0
        
        # Activity by type (top 10)
        activities_by_type = activities.values('action').annotate(
            count=Count('id'),
            success_count=Count('id', filter=Q(success=True)),
            failure_count=Count('id', filter=Q(success=False))
        ).annotate(
            success_rate=ExpressionWrapper(
                F('success_count') * 100.0 / F('count'),
                output_field=FloatField()
            )
        ).order_by('-count')[:10]
        
        # Top active users
        top_active_users = activities.filter(user__isnull=False).values(
            'user__id', 'user__email', 'user__first_name', 'user__last_name', 'user__role'
        ).annotate(
            activity_count=Count('id'),
            last_activity=Count('timestamp')
        ).order_by('-activity_count')[:10]
        
        # Daily activity trend
        daily_activity = activities.annotate(
            date=TruncDate('timestamp')
        ).values('date').annotate(
            count=Count('id'),
            success_count=Count('id', filter=Q(success=True)),
            failure_count=Count('id', filter=Q(success=False))
        ).order_by('date')
        
        # Hourly activity pattern (for the last 24 hours)
        twenty_four_hours_ago = timezone.now() - timedelta(hours=24)
        hourly_activity = activities.filter(
            timestamp__gte=twenty_four_hours_ago
        ).annotate(
            hour=TruncHour('timestamp')
        ).values('hour').annotate(
            count=Count('id')
        ).order_by('hour')
        
        # Security metrics
        security_actions = ['login_failed', 'account_lock', 'ip_block', 'password_reset_request']
        security_events = activities.filter(action__in=security_actions).count()
        failed_logins = activities.filter(action='login_failed').count()
        
        return Response({
            'period': {
                'start_date': start_date,
                'end_date': end_date,
                'days': days
            },
            'summary_metrics': {
                'total_activities': total_activities,
                'successful_activities': successful_activities,
                'failed_activities': failed_activities,
                'success_rate': success_rate,
                'active_users': active_users_count,
                'performing_users': performing_users_count,
                'security_events': security_events,
                'failed_logins': failed_logins
            },
            'activities_by_type': list(activities_by_type),
            'top_active_users': list(top_active_users),
            'daily_activity_trend': list(daily_activity),
            'hourly_activity_pattern': list(hourly_activity),
        })

    @action(detail=False, methods=['get'], url_path='security-events')
    def security_events(self, request):
        """Get security-related events with advanced filtering"""
        tenant = request.user.tenant
        days = int(request.query_params.get('days', 30))
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        security_actions = [
            'login', 'login_failed', 'account_lock', 'account_unlock', 
            'ip_block', 'ip_unblock', 'password_reset_request',
            'password_reset_confirm', 'impersonation'
        ]
        
        events = UserActivity.objects.filter(
            tenant=tenant,
            action__in=security_actions,
            timestamp__gte=start_date,
            timestamp__lte=end_date
        ).select_related('user', 'performed_by').order_by('-timestamp')
        
        # Apply additional filters if provided
        action_filter = request.query_params.get('security_action')
        if action_filter:
            events = events.filter(action=action_filter)
        
        success_filter = request.query_params.get('success')
        if success_filter is not None:
            events = events.filter(success=(success_filter.lower() == 'true'))
        
        page = self.paginate_queryset(events)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(events, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='user-activity-report')
    def user_activity_report(self, request):
        """Generate detailed user activity report"""
        tenant = request.user.tenant
        user_id = request.query_params.get('user_id')
        days = int(request.query_params.get('days', 30))
        
        if not user_id:
            return Response(
                {"error": "user_id parameter is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        try:
            user = CustomUser.objects.get(id=user_id, tenant=tenant)
        except CustomUser.DoesNotExist:
            return Response(
                {"error": "User not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # User's activities
        user_activities = UserActivity.objects.filter(
            tenant=tenant,
            user=user,
            timestamp__gte=start_date,
            timestamp__lte=end_date
        ).order_by('-timestamp')
        
        # Activities performed by the user
        performed_activities = UserActivity.objects.filter(
            tenant=tenant,
            performed_by=user,
            timestamp__gte=start_date,
            timestamp__lte=end_date
        ).order_by('-timestamp')
        
        # Summary statistics
        total_user_activities = user_activities.count()
        total_performed_activities = performed_activities.count()
        
        # Activity type breakdown
        activity_breakdown = user_activities.values('action').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Daily activity pattern
        daily_pattern = user_activities.annotate(
            date=TruncDate('timestamp')
        ).values('date').annotate(
            count=Count('id')
        ).order_by('date')
        
        # Most common actions
        top_actions = user_activities.values('action').annotate(
            count=Count('id')
        ).order_by('-count')[:5]
        
        return Response({
            'user_info': {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'role': user.role
            },
            'period': {
                'start_date': start_date,
                'end_date': end_date,
                'days': days
            },
            'summary': {
                'total_activities_as_subject': total_user_activities,
                'total_activities_as_performer': total_performed_activities,
                'average_daily_activities': round(total_user_activities / days, 2) if days > 0 else 0
            },
            'activity_breakdown': list(activity_breakdown),
            'daily_activity_pattern': list(daily_pattern),
            'top_actions': list(top_actions),
            'recent_activities': UserActivitySerializer(
                user_activities[:10], many=True, context={'request': request}
            ).data
        })


    @action(detail=False, methods=['get'], url_path='system-health')
    def system_health(self, request):
        """Get system health metrics based on activity patterns"""
        
        # Check if user is authenticated first
        if not request.user or not request.user.is_authenticated:
            return Response(
                {'error': 'Authentication required'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Check if user has tenant access
        if not hasattr(request.user, 'tenant') or not request.user.tenant:
            return Response(
                {'error': 'No tenant associated with user'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        tenant = request.user.tenant
        
        # Last 24 hours for real-time health
        twenty_four_hours_ago = timezone.now() - timedelta(hours=24)
        one_hour_ago = timezone.now() - timedelta(hours=1)
        
        recent_activities = UserActivity.objects.filter(
            tenant=tenant,
            timestamp__gte=twenty_four_hours_ago
        )
        
        # Error rate in last hour
        recent_errors = recent_activities.filter(
            timestamp__gte=one_hour_ago,
            success=False
        ).count()
        recent_total = recent_activities.filter(
            timestamp__gte=one_hour_ago
        ).count()
        recent_error_rate = round((recent_errors / recent_total * 100), 2) if recent_total > 0 else 0
        
        # Failed login rate
        failed_logins = recent_activities.filter(
            action='login_failed',
            timestamp__gte=one_hour_ago
        ).count()
        total_logins = recent_activities.filter(
            action='login',
            timestamp__gte=one_hour_ago
        ).count()
        login_failure_rate = round((failed_logins / total_logins * 100), 2) if total_logins > 0 else 0
        
        # Activity volume trends
        current_hour = timezone.now().replace(minute=0, second=0, microsecond=0)
        previous_hour = current_hour - timedelta(hours=1)
        
        current_hour_activities = recent_activities.filter(
            timestamp__gte=current_hour
        ).count()
        previous_hour_activities = recent_activities.filter(
            timestamp__gte=previous_hour,
            timestamp__lt=current_hour
        ).count()
        
        activity_trend = "stable"
        if previous_hour_activities > 0:
            change = ((current_hour_activities - previous_hour_activities) / previous_hour_activities) * 100
            if change > 20:
                activity_trend = "increasing"
            elif change < -20:
                activity_trend = "decreasing"
        
        # System status based on metrics
        system_status = "healthy"
        if recent_error_rate > 10 or login_failure_rate > 30:
            system_status = "degraded"
        if recent_error_rate > 25 or login_failure_rate > 50:
            system_status = "unhealthy"
        
        return Response({
            'timestamp': timezone.now(),
            'system_status': system_status,
            'metrics': {
                'recent_error_rate': recent_error_rate,
                'login_failure_rate': login_failure_rate,
                'current_hour_activities': current_hour_activities,
                'previous_hour_activities': previous_hour_activities,
                'activity_trend': activity_trend,
                'failed_logins_last_hour': failed_logins
            },
            'thresholds': {
                'error_rate_warning': 10,
                'error_rate_critical': 25,
                'login_failure_warning': 30,
                'login_failure_critical': 50
            }
        })


    @action(detail=False, methods=['get'], url_path='export')
    def export_activities(self, request):
        """Export activities to CSV format"""
        tenant = request.user.tenant
        
        if not (request.user.is_superuser or request.user.role == "admin"):
            raise PermissionDenied("Only admins can export activity logs.")
        
        # Get filtered queryset
        queryset = self.get_queryset()
        
        # Limit to last 30 days for performance
        thirty_days_ago = timezone.now() - timedelta(days=30)
        queryset = queryset.filter(timestamp__gte=thirty_days_ago)
        
        # Apply additional export filters
        export_format = request.query_params.get('format', 'json')
        limit = int(request.query_params.get('limit', 1000))
        
        if limit > 10000:  # Safety limit
            limit = 10000
        
        queryset = queryset[:limit]
        
        if export_format == 'csv':
            import csv
            from django.http import HttpResponse
            
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="activities_{timezone.now().date()}.csv"'
            
            writer = csv.writer(response)
            writer.writerow([
                'Timestamp', 'Action', 'User Email', 'Performed By', 
                'IP Address', 'Success', 'Details'
            ])
            
            for activity in queryset:
                writer.writerow([
                    activity.timestamp,
                    activity.action,
                    activity.user.email if activity.user else 'N/A',
                    activity.performed_by.email if activity.performed_by else 'N/A',
                    activity.ip_address,
                    activity.success,
                    json.dumps(activity.details)[:500]  # Limit details length
                ])
            
            return response
        
        else:  # JSON format
            serializer = self.get_serializer(queryset, many=True)
            return Response({
                'export_info': {
                    'exported_at': timezone.now(),
                    'total_records': queryset.count(),
                    'format': 'json',
                    'period': 'last_30_days'
                },
                'activities': serializer.data
            })




class UserPasswordRegenerateView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserPasswordRegenerateSerializer

    def post(self, request, *args, **kwargs):
        tenant = request.user.tenant
        with tenant_context(tenant):
            serializer = self.get_serializer(data=request.data, context={"request": request})
            serializer.is_valid(raise_exception=True)
            email = serializer.validated_data["email"]
            user = CustomUser.objects.get(email=email)

            characters = string.ascii_letters + string.digits + string.punctuation
            new_password = "".join(secrets.choice(characters) for _ in range(12))
            user.set_password(new_password)
            user.last_password_reset = timezone.now()
            user.save()

            logger.info(f"Password reset for user {user.email} by {request.user.email} in tenant {tenant.schema_name}")

            return Response(
                {
                    "status": "success",
                    "message": f"Password reset successfully for {user.email}.",
                    "user_email": user.email,
                    "new_password": new_password,
                },
                status=status.HTTP_200_OK,
            )



class GenericDetailView(APIView):
    permission_classes = [IsAdminUser]
    model = None
    serializer_class = None
    lookup_field = 'id'
    model_name = None

    def get_user_profile(self, request):
        """Retrieve the UserProfile based on user_id from request or default to authenticated user."""
        user_id = request.data.get('user_id') or request.query_params.get('user_id')
        try:
            with tenant_context(request.user.tenant):
                if user_id:
                    target_user = CustomUser.objects.get(id=user_id, tenant=request.user.tenant)
                    user_profile, _ = UserProfile.objects.get_or_create(user=target_user)
                else:
                    user_profile, _ = UserProfile.objects.get_or_create(user=request.user)
                return user_profile
        except CustomUser.DoesNotExist:
            logger.error(f"User with id {user_id} not found in tenant {request.user.tenant}")
            return None

    def get_object(self, obj_id, user_profile):
        """Retrieve the object and ensure it belongs to the specified user profile."""
        try:
            with tenant_context(self.request.user.tenant):
                obj = self.model.objects.get(**{self.lookup_field: obj_id, 'user_profile': user_profile})
                return obj
        except self.model.DoesNotExist:
            logger.error(f"{self.model_name} with id {obj_id} not found for user profile {user_profile.id}")
            return None

    def patch(self, request, obj_id):
        """Update an existing instance by ID."""
        try:
            user_profile = self.get_user_profile(request)
            if not user_profile:
                return Response(
                    {"status": "error", "message": "Target user not found."},
                    status=status.HTTP_404_NOT_FOUND
                )

            instance = self.get_object(obj_id, user_profile)
            if not instance:
                return Response(
                    {"status": "error", "message": f"{self.model_name} not found."},
                    status=status.HTTP_404_NOT_FOUND
                )

            serializer = self.serializer_class(instance, data=request.data, partial=True, context={"request": request})
            if serializer.is_valid():
                serializer.save()
                logger.info(f"{self.model_name} {obj_id} updated successfully for user profile {user_profile.id}")
                return Response(
                    {
                        "status": "success",
                        "message": f"{self.model_name} updated successfully.",
                        "data": serializer.data
                    },
                    status=status.HTTP_200_OK
                )
            else:
                logger.error(f"Validation error updating {self.model_name} {obj_id}: {serializer.errors}")
                return Response(
                    {"status": "error", "message": serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            logger.error(f"Error updating {self.model_name} {obj_id}: {str(e)}")
            return Response(
                {"status": "error", "message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request):
        """Create a new instance for the specified or authenticated user."""
        try:
            user_profile = self.get_user_profile(request)
            if not user_profile:
                return Response(
                    {"status": "error", "message": "Target user not found."},
                    status=status.HTTP_404_NOT_FOUND
                )

            serializer = self.serializer_class(data=request.data, context={"request": request})
            if serializer.is_valid():
                serializer.save(user_profile=user_profile)
                logger.info(f"New {self.model_name} created for user profile {user_profile.id}")
                return Response(
                    {
                        "status": "success",
                        "message": f"{self.model_name} created successfully.",
                        "data": serializer.data
                    },
                    status=status.HTTP_201_CREATED
                )
            else:
                logger.error(f"Validation error creating {self.model_name}: {serializer.errors}")
                return Response(
                    {"status": "error", "message": serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            logger.error(f"Error creating {self.model_name} for user profile: {str(e)}")
            return Response(
                {"status": "error", "message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# Specific views for each model
class ProfessionalQualificationView(GenericDetailView):
    model = ProfessionalQualification
    serializer_class = ProfessionalQualificationSerializer
    model_name = "Professional Qualification"

class InvestmentDetailView(GenericDetailView):
    model = InvestmentDetail
    serializer_class = InvestmentDetailSerializer
    model_name = "Investment Detail"

class WithdrawalDetailView(GenericDetailView):
    model = WithdrawalDetail
    serializer_class = WithdrawalDetailSerializer
    model_name = "Withdrawal Detail"

class EmploymentDetailView(GenericDetailView):
    model = EmploymentDetail
    serializer_class = EmploymentDetailSerializer
    model_name = "Employment Detail"

class EducationDetailView(GenericDetailView):
    model = EducationDetail
    serializer_class = EducationDetailSerializer
    model_name = "Education Detail"

class ReferenceCheckView(GenericDetailView):
    model = ReferenceCheck
    serializer_class = ReferenceCheckSerializer
    model_name = "Reference Check"

class ProofOfAddressView(GenericDetailView):
    model = ProofOfAddress
    serializer_class = ProofOfAddressSerializer
    model_name = "Proof of Address"

class InsuranceVerificationView(GenericDetailView):
    model = InsuranceVerification
    serializer_class = InsuranceVerificationSerializer
    model_name = "Insurance Verification"

class DrivingRiskAssessmentView(GenericDetailView):
    model = DrivingRiskAssessment
    serializer_class = DrivingRiskAssessmentSerializer
    model_name = "Driving Risk Assessment"

class LegalWorkEligibilityView(GenericDetailView):
    model = LegalWorkEligibility
    serializer_class = LegalWorkEligibilitySerializer
    model_name = "Legal Work Eligibility"

class OtherUserDocumentsView(GenericDetailView):
    model = OtherUserDocuments
    serializer_class = OtherUserDocumentsSerializer
    model_name = "Other User Document"


class AdminUserCreateView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        serializer = AdminUserCreateSerializer(data=request.data)
        if serializer.is_valid():
            try:
                user = serializer.save()
                refresh = RefreshToken.for_user(user)
                logger.info(f"Admin user created: {user.email} for tenant {user.tenant.schema_name}")

                # ✅ SEND NOTIFICATION EVENT AFTER ADMIN USER CREATION
                logger.info("🎯 Reached admin user creation success block. Sending user creation event to notification service.")
                try:
                    # Generate a unique event ID in the format 'evt-<uuid>'
                    event_id = f"evt-{str(uuid.uuid4())[:8]}"
                    # Get user agent from request
                    user_agent = request.META.get("HTTP_USER_AGENT", "Unknown")
                    # Define company name (assuming tenant name or a custom field)
                    company_name = user.tenant.name if hasattr(user.tenant, 'name') else "Unknown Company"
                    # Define login link (customize as needed)
                   

                    login_link = settings.WEB_PAGE_URL
                    # print("login_link")
                    # print(login_link)
                    # print("login_link")

                    logger.info(f"🎯 {login_link}")
                    event_payload = {
                        "metadata": {
                            "tenant_id": str(user.tenant.unique_id),
                            "event_type": "user.account.created",
                            "event_id": event_id,
                            "created_at": timezone.now().isoformat(),
                            "source": "auth-service",
                        },
                        "data": {
                            "user_email": user.email,
                            "company_name": company_name,
                            "temp_password": serializer.validated_data.get("password", ""),
                            "login_link": login_link,
                            "timestamp": timezone.now().isoformat(),
                            "login_link": login_link,
                            "user_agent": user_agent,
                            "user_id": str(user.id),
                        },
                    }

                    notifications_url = settings.NOTIFICATIONS_SERVICE_URL + "/events/"
                    safe_payload = {**event_payload, "data": {**event_payload["data"], "temp_password": "[REDACTED]"}}
                    logger.info(f"➡️ POST to {notifications_url} with payload: {safe_payload}")

                    response = requests.post(notifications_url, json=event_payload, timeout=5)
                    response.raise_for_status()  # Raise if status != 200
                    logger.info(f"✅ Notification sent for {user.email}. Status: {response.status_code}, Response: {response.text}")

                except requests.exceptions.RequestException as e:
                    logger.warning(f"[❌ Notification Error] Failed to send user creation event for {user.email}: {str(e)}")
                except Exception as e:
                    logger.error(f"[❌ Notification Exception] Unexpected error for {user.email}: {str(e)}")

                return Response(
                    {
                        "status": "success",
                        "message": f"Admin user {user.email} created successfully.",
                        "data": {
                            "username": user.username,
                            "email": user.email,
                            "first_name": user.first_name,
                            "last_name": user.last_name,
                            "job_role": user.job_role,
                            "tenant_id": user.tenant.id,
                            "tenant_schema": user.tenant.schema_name,
                            "branch": user.branch.name if user.branch else None,
                            # 'refresh': str(refresh),
                            # 'access': str(refresh.access_token),
                        },
                    },
                    status=status.HTTP_201_CREATED,
                )
            except Exception as e:
                logger.error(f"Error creating admin user: {str(e)}")
                return Response({"status": "error", "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        logger.error(f"Validation error: {serializer.errors}")
        return Response({"status": "error", "message": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


class UserBranchUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def get_tenant_from_token(self, request):
        try:
            if hasattr(request, "tenant") and request.tenant:
                logger.debug(f"Tenant from request: {request.tenant.schema_name}")
                return request.tenant
            if hasattr(request.user, "tenant") and request.user.tenant:
                logger.debug(f"Tenant from user: {request.user.tenant.schema_name}")
                return request.user.tenant
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                logger.warning("No valid Bearer token provided")
                raise ValueError("Invalid token format")
            token = auth_header.split(" ")[1]
            decoded_token = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            tenant_id = decoded_token.get("tenant_id")
            schema_name = decoded_token.get("tenant_schema")
            if tenant_id:
                tenant = Tenant.objects.get(id=tenant_id)
                logger.debug(f"Tenant extracted from token by ID: {tenant.schema_name}")
                return tenant
            elif schema_name:
                tenant = Tenant.objects.get(schema_name=schema_name)
                logger.debug(f"Tenant extracted from token by schema: {tenant.schema_name}")
                return tenant
            else:
                logger.warning("No tenant_id or schema_name in token")
                raise ValueError("Tenant not specified in token")
        except Tenant.DoesNotExist:
            logger.error("Tenant not found")
            raise serializers.ValidationError("Tenant not found")
        except jwt.InvalidTokenError:
            logger.error("Invalid JWT token")
            raise serializers.ValidationError("Invalid token")
        except Exception as e:
            logger.error(f"Error extracting tenant: {str(e)}")
            raise serializers.ValidationError(f"Error extracting tenant: {str(e)}")

    def patch(self, request, user_id):
        tenant = self.get_tenant_from_token(request)
        with tenant_context(tenant):
            try:
                user = CustomUser.objects.get(id=user_id, tenant=tenant)
            except CustomUser.DoesNotExist:
                logger.error(f"User with ID {user_id} not found for tenant {tenant.schema_name}")
                return Response(
                    {"status": "error", "message": f"User with ID {user_id} not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Check permissions: Only admins, superusers, or team managers can update branch
            if not (request.user.is_superuser or request.user.role == "admin" or request.user.role == "team_manager"):
                logger.warning(
                    f"Unauthorized branch update attempt by user {request.user.email} for user {user.email}"
                )
                return Response(
                    {"status": "error", "message": "Only admins or team managers can update user branch"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            serializer = UserBranchUpdateSerializer(
                user, data=request.data, context={"request": request}, partial=True
            )
            if serializer.is_valid():
                try:
                    with transaction.atomic():
                        serializer.save()
                        logger.info(
                            f"User {user.email} assigned to branch {user.branch.name if user.branch else 'None'} for tenant {tenant.schema_name}"
                        )
                        return Response(
                            {
                                "status": "success",
                                "message": f"User {user.email} branch updated successfully",
                                "data": CustomUserSerializer(user, context={"request": request}).data,
                            },
                            status=status.HTTP_200_OK,
                        )
                except Exception as e:
                    logger.error(
                        f"Error updating branch for user {user.email} in tenant {tenant.schema_name}: {str(e)}"
                    )
                    return Response(
                        {"status": "error", "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
            logger.error(f"Validation error for user {user.email} in tenant {tenant.schema_name}: {serializer.errors}")
            return Response({"status": "error", "message": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


# New view for listing all users in a tenant
class TenantUsersListView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    def get_tenant_from_token(self, request):
        try:
            if hasattr(request, "tenant") and request.tenant:
                logger.debug(f"Tenant from request: {request.tenant.schema_name}")
                return request.tenant
            if hasattr(request.user, "tenant") and request.user.tenant:
                logger.debug(f"Tenant from user: {request.user.tenant.schema_name}")
                return request.user.tenant
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                logger.warning("No valid Bearer token provided")
                raise ValueError("Invalid token format")
            token = auth_header.split(" ")[1]
            decoded_token = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            tenant_id = decoded_token.get("tenant_id")
            schema_name = decoded_token.get("tenant_schema")
            if tenant_id:
                tenant = Tenant.objects.get(id=tenant_id)
                logger.debug(f"Tenant extracted from token by ID: {tenant.schema_name}")
                return tenant
            elif schema_name:
                tenant = Tenant.objects.get(schema_name=schema_name)
                logger.debug(f"Tenant extracted from token by schema: {tenant.schema_name}")
                return tenant
            else:
                logger.warning("No tenant_id or schema_name in token")
                raise ValueError("Tenant not specified in token")
        except Tenant.DoesNotExist:
            logger.error("Tenant not found")
            raise serializers.ValidationError("Tenant not found")
        except jwt.InvalidTokenError:
            logger.error("Invalid JWT token")
            raise serializers.ValidationError("Invalid token")
        except Exception as e:
            logger.error(f"Error extracting tenant: {str(e)}")
            raise serializers.ValidationError(f"Error extracting tenant: {str(e)}")

    def get(self, request):
        tenant = self.get_tenant_from_token(request)
        with tenant_context(tenant):
            if not (request.user.is_superuser or request.user.role == "admin" or request.user.role == "team_manager"):
                return Response(
                    {"status": "error", "message": "Only admins or team managers can list all tenant users"},
                    status=status.HTTP_403_FORBIDDEN,
                )
            users = CustomUser.objects.filter(tenant=tenant).prefetch_related(
                "profile__professional_qualifications",
                "profile__employment_details",
                "profile__education_details",
                "profile__reference_checks",
                "profile__proof_of_address",
                "profile__insurance_verifications",
                "profile__driving_risk_assessments",
                "profile__legal_work_eligibilities",
                "profile__other_user_documents",
            )
            serializer = CustomUserSerializer(users, many=True, context={"request": request})
            return Response(
                {
                    "status": "success",
                    "message": f"Retrieved {users.count()} users for tenant {tenant.schema_name}",
                    "data": serializer.data,
                },
                status=status.HTTP_200_OK,
            )


class BranchUsersListView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    def get(self, request, branch_id):
        tenant = self.get_tenant_from_token(request)
        with tenant_context(tenant):
            branch = Branch.objects.get(id=branch_id, tenant=tenant)
            if not (
                request.user.is_superuser
                or request.user.role == "admin"
                or request.user.role == "team_manager"
                or (request.user.role == "recruiter" and request.user.branch == branch)
            ):
                return Response(
                    {
                        "status": "error",
                        "message": "Only admins, team managers, or recruiters assigned to this branch can list users",
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
            users = CustomUser.objects.filter(tenant=tenant, branch=branch).prefetch_related(
                "profile__professional_qualifications",
                "profile__employment_details",
                "profile__education_details",
                "profile__reference_checks",
                "profile__proof_of_address",
                "profile__insurance_verifications",
                "profile__driving_risk_assessments",
                "profile__legal_work_eligibilities",
                "profile__other_user_documents",
            )
            serializer = CustomUserSerializer(users, many=True, context={"request": request})
            return Response(
                {
                    "status": "success",
                    "message": f"Retrieved {users.count()} users for branch {branch.name}",
                    "data": serializer.data,
                },
                status=status.HTTP_200_OK,
            )


class UserSessionViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    def get_tenant(self, request):
        # Adjust this if you have a different way to get tenant
        return getattr(request, "tenant", getattr(request.user, "tenant", None))

    @action(detail=True, methods=["patch", "put"], url_path="edit")
    def edit_session(self, request, pk=None):
        """
        Allows the user to edit their own session's login_time and logout_time.
        """
        tenant = self.get_tenant(request)
        with tenant_context(tenant):
            try:
                session = UserSession.objects.get(pk=pk, user=request.user)
            except UserSession.DoesNotExist:
                return Response({"detail": "Session not found."}, status=404)

            login_time = request.data.get("login_time")
            logout_time = request.data.get("logout_time")

            if login_time:
                try:
                    session.login_time = timezone.make_aware(timezone.datetime.fromisoformat(login_time))
                except Exception:
                    return Response({"detail": "Invalid login_time format. Use ISO 8601."}, status=400)
            if logout_time:
                try:
                    session.logout_time = timezone.make_aware(timezone.datetime.fromisoformat(logout_time))
                except Exception:
                    return Response({"detail": "Invalid logout_time format. Use ISO 8601."}, status=400)

            session.save()
            return Response(UserSessionSerializer(session).data, status=200)

    @action(detail=False, methods=["post"], url_path="clock-in")
    def clock_in(self, request):
        tenant = self.get_tenant(request)
        with tenant_context(tenant):
            # Prevent multiple open sessions
            open_session = UserSession.objects.filter(user=request.user, logout_time__isnull=True).last()
            if open_session:
                return Response({"detail": "You already have an open session. Please clock out first."}, status=400)
            ip = request.META.get("REMOTE_ADDR")
            user_agent = request.META.get("HTTP_USER_AGENT", "")
            session = UserSession.objects.create(
                user=request.user,
                login_time=timezone.now(),
                date=timezone.now().date(),
                ip_address=ip,
                user_agent=user_agent,
            )
            return Response({"detail": "Clocked in.", "session_id": session.id}, status=201)

    @action(detail=False, methods=["post"], url_path="clock-out")
    def clock_out(self, request):
        tenant = self.get_tenant(request)
        with tenant_context(tenant):
            session = UserSession.objects.filter(user=request.user, logout_time__isnull=True).last()
            if not session:
                return Response({"detail": "No open session found."}, status=400)
            session.logout_time = timezone.now()
            session.save()
            return Response({"detail": "Clocked out.", "duration": session.duration}, status=200)

    @action(detail=False, methods=["get"], url_path="daily-history")
    def daily_history(self, request):
        tenant = self.get_tenant(request)
        date_str = request.query_params.get("date")
        if date_str:
            try:
                date = timezone.datetime.strptime(date_str, "%Y-%m-%d").date()
            except Exception:
                return Response({"detail": "Invalid date format. Use YYYY-MM-DD."}, status=400)
        else:
            date = timezone.now().date()
        with tenant_context(tenant):
            sessions = UserSession.objects.filter(user=request.user, date=date)
            total = get_daily_usage(request.user, date)
            # You need to implement UserSessionSerializer
            data = UserSessionSerializer(sessions, many=True).data
            return Response({"sessions": data, "total_time": total}, status=200)





class ClientViewSet(viewsets.ModelViewSet):
    queryset = CustomUser.objects.filter(role="client").prefetch_related("client_profile")
    serializer_class = ClientDetailSerializer
    pagination_class = CustomPagination

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant = self.request.user.tenant
        user = self.request.user
        with tenant_context(tenant):
            if user.is_superuser or user.role == "admin":
                return CustomUser.objects.filter(tenant=tenant, role="client").prefetch_related("client_profile")
            elif user.role == "team_manager":
                return CustomUser.objects.filter(tenant=tenant, role="client").prefetch_related("client_profile")
            elif user.role == "recruiter" and user.branch:
                return CustomUser.objects.filter(tenant=tenant, role="client", branch=user.branch).prefetch_related(
                    "client_profile"
                )
            else:
                return CustomUser.objects.filter(tenant=tenant, id=user.id, role="client").prefetch_related(
                    "client_profile"
                )

    def get_serializer_class(self):
        if self.action == "create":
            return ClientCreateSerializer
        if self.action == "bulk_create":
            return ClientCreateSerializer  # Use the same for bulk
        return ClientDetailSerializer  # Use for retrieve, update, partial_update

    def perform_create(self, serializer):
        tenant = self.request.user.tenant
        if not (self.request.user.is_superuser or self.request.user.role == "admin"):
            raise PermissionDenied("Only admins or superusers can create clients.")
        with tenant_context(tenant):
            serializer.save()

    def update(self, request, *args, **kwargs):
        tenant = request.user.tenant
        user = request.user
        with tenant_context(tenant):
            instance = self.get_object()
            if not (user.is_superuser or user.role == "admin" or user.id == instance.id):
                raise PermissionDenied("You do not have permission to update this client.")
            serializer = self.get_serializer(instance, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
            return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        tenant = request.user.tenant
        user = request.user
        with tenant_context(tenant):
            instance = self.get_object()
            if not (user.is_superuser or user.role == "admin"):
                raise PermissionDenied("You do not have permission to delete clients.")
            self.perform_destroy(instance)
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["post"], url_path="bulk-create")
    def bulk_create(self, request):
        """
        Bulk create clients with their profiles.
        Payload: List of client objects, each with email, first_name, last_name, and nested profile data.
        """
        tenant = self.request.user.tenant
        user = self.request.user

        # Check permissions
        if not (user.is_superuser or user.role == "admin"):
            logger.warning(
                f"User {user.email} attempted bulk create without permission in tenant {tenant.schema_name}"
            )
            raise PermissionDenied("Only admins or superusers can create clients.")

        # Expect a list of client data
        data = request.data
        if not isinstance(data, list):
            logger.error("Bulk create payload must be a list of client objects")
            raise ValidationError({"detail": "Payload must be a list of client objects"})

        results = []
        errors = []
        with tenant_context(tenant):
            with transaction.atomic():
                for index, client_data in enumerate(data):
                    # Ensure role is 'client'
                    client_data["role"] = "client"
                    serializer = ClientCreateSerializer(data=client_data, context={"request": request})
                    try:
                        serializer.is_valid(raise_exception=True)
                        client_obj = serializer.save()
                        logger.info(f"Created client {client_obj.email} in tenant {tenant.schema_name} during bulk create")

                        # Invalidate relevant caches if any (adapt as needed for clients)
                        # from auth_service.utils.cache import delete_tenant_cache
                        # delete_tenant_cache(tenant.schema_name, 'clients_list')

                        results.append(
                            {
                                "status": "success",
                                "email": client_obj.email,
                                "id": client_obj.id,
                                "data": ClientDetailSerializer(client_obj).data,
                            }
                        )
                    except ValidationError as e:
                        logger.error(f"Failed to create client at index {index}: {str(e)}")
                        errors.append({"index": index, "email": client_data.get("email", "unknown"), "errors": e.detail})

        # Log the overall result
        logger.info(
            f"Bulk client create completed in tenant {tenant.schema_name}: {len(results)} succeeded, {len(errors)} failed"
        )

        # Prepare response
        response_data = {
            "status": "partial_success" if errors else "success",
            "created": results,
            "errors": errors,
            "message": f"Created {len(results)} clients, {len(errors)} failed",
        }
        status_code = status.HTTP_201_CREATED if results else status.HTTP_400_BAD_REQUEST
        return Response(response_data, status=status_code)


@csrf_exempt
def token_view(request):
    if request.method != "POST":
        return HttpResponse(status=405)
    try:
        body = json.loads(request.body.decode() or "{}")
        email = body.get("email")
        password = body.get("password")
        if not email or not password:
            return JsonResponse({"error": "Email and password required"}, status=400)
        user = authenticate(email=email, password=password)
        if not user or not user.tenant:
            return JsonResponse({"error": "Invalid credentials or tenant"}, status=401)
        payload = {
            "sub": user.email,
            "role": user.role,
            "tenant_id": user.tenant.id,
        }
        token = issue_rsa_jwt(payload, user.tenant)
        return JsonResponse({"access_token": token})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@csrf_exempt
def protected_view(request):
    auth = request.META.get("HTTP_AUTHORIZATION", "")
    if not auth.startswith("Bearer "):
        return JsonResponse({"error": "Missing token"}, status=401)
    token = auth.split(" ", 1)[1].strip()
    try:
        claims = validate_rsa_jwt(token)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=401)
    return JsonResponse({"hello": claims.get("sub"), "claims": claims})


def pem_to_jwk(public_pem, kid):
    import json

    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    pubkey = serialization.load_pem_public_key(public_pem.encode(), backend=default_backend())
    numbers = pubkey.public_numbers()
    n = (
        base64.urlsafe_b64encode(numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big"))
        .rstrip(b"=")
        .decode("utf-8")
    )
    e = (
        base64.urlsafe_b64encode(numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, "big"))
        .rstrip(b"=")
        .decode("utf-8")
    )
    return {
        "kty": "RSA",
        "use": "sig",
        "kid": kid,
        "alg": "RS256",
        "n": n,
        "e": e,
    }


def jwks_view(request, tenant_id):
    try:
        tenant = Tenant.objects.get(id=tenant_id)
    except Tenant.DoesNotExist:
        return JsonResponse({"error": "Tenant not found"}, status=404)
    keys = RSAKeyPair.objects.filter(tenant=tenant, active=True)
    jwks = {"keys": [pem_to_jwk(k.public_key_pem, k.kid) for k in keys]}
    return JsonResponse(jwks)


def generate_rsa_keypair(key_size=2048):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=key_size)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = (
        private_key.public_key()
        .public_bytes(encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode("utf-8")
    )
    return private_pem, public_pem





class RSAKeyPairCreateView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        tenant_id = request.data.get("tenant_id")
        schema_name = request.data.get("schema_name")

        # Validate input
        if not tenant_id and not schema_name:
            logger.error("No tenant_id or schema_name provided in request")
            return Response(
                {"status": "error", "message": "Either tenant_id or schema_name is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # ✅ Fetch tenant
            if tenant_id:
                tenant = Tenant.objects.get(id=tenant_id)
            else:
                tenant = Tenant.objects.get(schema_name=schema_name)

            # ✅ Get tenant's primary domain (safe lookup)
            primary_domain_obj = Domain.objects.filter(tenant=tenant, is_primary=True).first()
            primary_domain = primary_domain_obj.domain if primary_domain_obj else None

            # ✅ Generate RSA key pair
            private_pem, public_pem = generate_rsa_keypair()

            # ✅ Create key pair inside tenant schema context
            with tenant_context(tenant):
                keypair = RSAKeyPair.objects.create(
                    tenant=tenant,
                    private_key_pem=private_pem,
                    public_key_pem=public_pem,
                    active=True,
                )
                logger.info(f"RSAKeyPair created for tenant: {tenant.schema_name}, kid: {keypair.kid}")

            # ✅ Success response
            return Response(
                {
                    "status": "success",
                    "message": f"RSAKeyPair created successfully for tenant {tenant.schema_name}",
                    "data": {
                        "tenant_id": tenant.id,
                        "tenant_schema": tenant.schema_name,
                        "tenant_domain": primary_domain,
                        "kid": keypair.kid,
                        "public_key": public_pem,
                    },
                },
                status=status.HTTP_201_CREATED,
            )

        except Tenant.DoesNotExist:
            logger.error(f"Tenant not found: tenant_id={tenant_id}, schema_name={schema_name}")
            return Response(
                {"status": "error", "message": "Tenant not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            logger.error(f"Error creating RSAKeyPair: {str(e)}")
            return Response(
                {"status": "error", "message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )



# class RSAKeyPairCreateView(APIView):
#     """
#     Create an RSA key pair for a tenant (by tenant_id or schema_name).
#     Returns tenant metadata (domains, root-admin) in the same format as list views.
#     Restricted to superusers only.
#     """
#     permission_classes = [IsAdminUser]

#     def post(self, request):
#         tenant_id = request.data.get("tenant_id")
#         schema_name = request.data.get("schema_name")

#         # === Input Validation ===
#         if not tenant_id and not schema_name:
#             logger.error("RSAKeyPair create: No tenant_id or schema_name provided")
#             return Response(
#                 {
#                     "status": "error",
#                     "message": "Either 'tenant_id' or 'schema_name' is required",
#                 },
#                 status=status.HTTP_400_BAD_REQUEST,
#             )

#         try:
#             # === Fetch Tenant (public schema) ===
#             if tenant_id:
#                 tenant = Tenant.objects.get(id=tenant_id)
#             else:
#                 tenant = Tenant.objects.get(schema_name=schema_name)

#             # === Get Domains & Root Admin (using shared helpers) ===
#             domains = get_tenant_domains(tenant)
#             root_admin = get_root_admin(tenant)

#             # === Generate RSA Key Pair ===
#             private_pem, public_pem = generate_rsa_keypair()

#             # === Create Key Pair inside tenant schema ===
#             with tenant_context(tenant):
#                 keypair = RSAKeyPair.objects.create(
#                     tenant=tenant,
#                     private_key_pem=private_pem,
#                     public_key_pem=public_pem,
#                     active=True,
#                 )
#                 logger.info(
#                     f"RSAKeyPair created for tenant: {tenant.schema_name}, kid: {keypair.kid}"
#                 )

#             # === Build Consistent Response ===
#             response_data = {
#                 "status": "success",
#                 "message": f"RSAKeyPair created successfully for tenant '{tenant.name}'",
#                 "data": {
#                     "tenant_id": tenant.id,
#                     "tenant_schema": tenant.schema_name,
#                     "tenant_name": tenant.name,
#                     "unique_id": str(tenant.unique_id) if tenant.unique_id else None,
#                     "primary_domain": domains["primary_domain"],
#                     "all_domains": domains["all_domains"],
#                     "status": tenant.status,
#                     "root_admin": root_admin,
#                     "kid": keypair.kid,
#                     "public_key": public_pem,
#                     "created_at": keypair.created_at.isoformat(),
#                 },
#             }

#             return Response(response_data, status=status.HTTP_201_CREATED)

#         except Tenant.DoesNotExist:
#             logger.error(f"Tenant not found: tenant_id={tenant_id}, schema_name={schema_name}")
#             return Response(
#                 {"status": "error", "message": "Tenant not found"},
#                 status=status.HTTP_404_NOT_FOUND,
#             )

#         except Exception as e:
#             logger.error(f"Unexpected error in RSAKeyPairCreateView: {str(e)}", exc_info=True)
#             return Response(
#                 {"status": "error", "message": "Failed to create RSA key pair"},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             )


class GroupViewSet(viewsets.ModelViewSet):
    queryset = Group.objects.all()
    serializer_class = GroupSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant = self.request.user.tenant
        return Group.objects.filter(tenant=tenant)

    def perform_create(self, serializer):
        if not (self.request.user.is_superuser or self.request.user.role == "admin"):
            raise PermissionDenied("Only admins or superusers can create groups.")
        serializer.save()

    def perform_update(self, serializer):
        if not (self.request.user.is_superuser or self.request.user.role == "admin"):
            raise PermissionDenied("Only admins or superusers can update groups.")
        serializer.save()

    def perform_destroy(self, instance):
        if not (self.request.user.is_superuser or self.request.user.role == "admin"):
            raise PermissionDenied("Only admins or superusers can delete groups.")
        instance.delete()

    @action(detail=True, methods=["get"], url_path="members")
    def get_members(self, request, pk=None):
        group = self.get_object()
        memberships = GroupMembership.objects.filter(group=group, tenant=request.user.tenant)
        serializer = GroupMembershipSerializer(memberships, many=True, context={"request": request})
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="add-member")
    def add_member(self, request, pk=None):
        if not (request.user.is_superuser or request.user.role == "admin"):
            raise PermissionDenied("Only admins or superusers can add members to groups.")

        group = self.get_object()
        user_id = request.data.get("user_id")

        try:
            with tenant_context(request.user.tenant):
                user = CustomUser.objects.get(id=user_id, tenant=request.user.tenant)
                if GroupMembership.objects.filter(group=group, user=user).exists():
                    return Response(
                        {"error": "User is already a member of this group."}, status=status.HTTP_400_BAD_REQUEST
                    )

                membership = GroupMembership.objects.create(group=group, user=user, tenant=request.user.tenant)
                serializer = GroupMembershipSerializer(membership, context={"request": request})
                return Response(serializer.data, status=status.HTTP_201_CREATED)
        except CustomUser.DoesNotExist:
            return Response(
                {"error": "User not found or does not belong to this tenant."}, status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=["post"], url_path="remove-member")
    def remove_member(self, request, pk=None):
        if not (request.user.is_superuser or request.user.role == "admin"):
            raise PermissionDenied("Only admins or superusers can remove members from groups.")

        group = self.get_object()
        user_id = request.data.get("user_id")

        try:
            with tenant_context(request.user.tenant):
                membership = GroupMembership.objects.get(group=group, user__id=user_id, tenant=request.user.tenant)
                membership.delete()
                return Response(status=status.HTTP_204_NO_CONTENT)
        except GroupMembership.DoesNotExist:
            return Response({"error": "User is not a member of this group."}, status=status.HTTP_404_NOT_FOUND)




class DocumentListCreateView(APIView):
    def get(self, request):
        try:
            tenant_uuid = get_tenant_id_from_jwt(request)
            documents = Document.objects.filter(tenant_id=tenant_uuid)
            serializer = DocumentSerializer(documents, many=True, context={"request": request})
            logger.info(f"Retrieved {documents.count()} documents for tenant {tenant_uuid}")
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error listing documents for tenant {tenant_uuid}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request):
        try:
            serializer = DocumentSerializer(data=request.data, context={'request': request})
            logger.info(f"{request.data}")
            if serializer.is_valid():
                document = serializer.save()
                logger.info(f"Document created: {document.title} for tenant {serializer.validated_data['tenant_id']}")
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            logger.error(f"Validation error: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error creating document: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class DocumentDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request, id):
        try:
            tenant_uuid = get_tenant_id_from_jwt(request)
            document = Document.objects.get(id=id, tenant_id=tenant_uuid)
            serializer = DocumentSerializer(document, context={"request": request})
            logger.info(f"Retrieved document {document.title} for tenant {tenant_uuid}")
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Document.DoesNotExist:
            logger.error(f"Document not found for tenant {tenant_uuid}")
            return Response({"detail": "Document not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error retrieving document for tenant {tenant_uuid}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def patch(self, request, id):
        try:
            tenant_uuid = get_tenant_id_from_jwt(request)
            document = Document.objects.get(id=id, tenant_id=tenant_uuid)
            serializer = DocumentSerializer(document, data=request.data, partial=True, context={"request": request})
            if serializer.is_valid():
                serializer.save()
                logger.info(f"Document updated: {document.title} for tenant {tenant_uuid}, version {document.version}")
                return Response(serializer.data, status=status.HTTP_200_OK)
            logger.error(f"Validation error for tenant {tenant_uuid}: {serializer.errors}")
            return Response({"detail": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        except Document.DoesNotExist:
            logger.error(f"Document not found for tenant {tenant_uuid}")
            return Response({"detail": "Document not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error updating document for tenant {tenant_uuid}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, id):
        try:
            tenant_uuid = get_tenant_id_from_jwt(request)
            document = Document.objects.get(id=id, tenant_id=tenant_uuid)
            document.delete()
            logger.info(f"Document deleted: {document.title} for tenant {tenant_uuid}")
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Document.DoesNotExist:
            logger.error(f"Document not found for tenant {tenant_uuid}")
            return Response({"detail": "Document not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error deleting document for tenant {tenant_uuid}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class DocumentVersionListView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request, document_id):
        try:
            tenant_uuid = get_tenant_id_from_jwt(request)
            document = Document.objects.get(id=document_id, tenant_id=tenant_uuid)
            versions = DocumentVersion.objects.filter(document=document)
            serializer = DocumentVersionSerializer(versions, many=True, context={"request": request})
            logger.info(f"Retrieved {versions.count()} versions for document {document.title} in tenant {tenant_uuid}")
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Document.DoesNotExist:
            logger.error(f"Document not found for tenant {tenant_uuid}")
            return Response({"detail": "Document not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error retrieving versions for document {document_id} in tenant {tenant_uuid}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class DocumentAcknowledgeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, document_id):
        try:
            tenant_uuid = get_tenant_id_from_jwt(request)
            current_user = get_user_data_from_jwt(request)
            document = Document.objects.get(id=document_id, tenant_id=tenant_uuid)
            if DocumentAcknowledgment.objects.filter(document=document, user_id=current_user['id'], tenant_id=tenant_uuid).exists():
                return Response(
                    {"detail": "You have already acknowledged this document"}, status=status.HTTP_400_BAD_REQUEST
                )
            acknowledgment = DocumentAcknowledgment.objects.create(
                document=document,
                user_id=str(current_user['id']),
                email=current_user['email'],
                first_name=current_user['first_name'],
                last_name=current_user['last_name'],
                role=current_user['job_role'],
                tenant_id=tenant_uuid,
            )
            serializer = DocumentAcknowledgmentSerializer(acknowledgment)
            logger.info(
                f"Document {document.title} acknowledged by {current_user['email']} in tenant {tenant_uuid}"
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Document.DoesNotExist:
            logger.error(f"Document not found for tenant {tenant_uuid}")
            return Response({"detail": "Document not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error acknowledging document for tenant {tenant_uuid}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class DocumentAcknowledgmentsListView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request, document_id):
        try:
            tenant_uuid = get_tenant_id_from_jwt(request)
            document = Document.objects.get(id=document_id, tenant_id=tenant_uuid)
            acknowledgments = DocumentAcknowledgment.objects.filter(document=document, tenant_id=tenant_uuid).order_by('-acknowledged_at')
            serializer = DocumentAcknowledgmentSerializer(acknowledgments, many=True, context={"request": request})
            logger.info(f"Retrieved {acknowledgments.count()} acknowledgments for document {document.title} in tenant {tenant_uuid}")
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Document.DoesNotExist:
            logger.error(f"Document not found for tenant {tenant_uuid}")
            return Response({"detail": "Document not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error retrieving acknowledgments for document {document_id} in tenant {tenant_uuid}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserDocumentAccessView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        user_identifier = request.query_params.get('user_id') or request.query_params.get('email')
        if not user_identifier:
            return Response({"detail": "Either 'user_id' or 'email' query parameter is required."}, status=status.HTTP_400_BAD_REQUEST)

        tenant_uuid = get_tenant_id_from_jwt(request)
        try:
            if request.query_params.get('user_id'):
                permissions = DocumentPermission.objects.filter(user_id=user_identifier, tenant_id=tenant_uuid).select_related('document')
            else:
                permissions = DocumentPermission.objects.filter(email=user_identifier, tenant_id=tenant_uuid).select_related('document')
            serializer = UserDocumentAccessSerializer(permissions, many=True, context={"request": request})
            if not permissions.exists():
                return Response({"detail": "No access found for the specified user."}, status=status.HTTP_404_NOT_FOUND)
            logger.info(f"Retrieved {len(permissions)} documents for user {user_identifier} in tenant {tenant_uuid}")
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error retrieving user document access for tenant {tenant_uuid}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class TransactionView(APIView):
    def post(self, request):
        serializer = TransactionSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            result = serializer.create(serializer.validated_data)
            return Response(result, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)