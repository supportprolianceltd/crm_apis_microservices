# Standard library
import base64
import json
import logging
import secrets
import string
import uuid
from datetime import datetime, timedelta

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from core.models import Tenant
from users.models import RSAKeyPair
from django_tenants.utils import tenant_context
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

logger = logging.getLogger('users')

# Standard library
from django.db import transaction
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from core.models import Domain, Branch
from django_tenants.utils import tenant_context
from rest_framework import serializers
from utils.supabase import upload_file_dynamic
import json

# Local App - Models
from .models import (
    CustomUser,
    UserSession,
    UserProfile,
    ProfessionalQualification,
    EmploymentDetail,
    EducationDetail,
    ReferenceCheck,
    OtherUserDocuments,
    PasswordResetToken,
    ProofOfAddress,
    InsuranceVerification,
    DrivingRiskAssessment,
    LegalWorkEligibility,
    ClientProfile,
    BlockedIP,
    UserActivity,
)

import logging
import uuid
from datetime import timedelta
from django_tenants.utils import tenant_context
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from auth_service.views import CustomUserMinimalSerializer  # Assuming this is your minimal user serializer
from auth_service.utils.jwt_rsa import issue_rsa_jwt  # Assuming this is your JWT issuer

from .models import CustomUser, UserActivity
from .serializers import (
    CustomUserListSerializer, CustomUserSerializer, UserCreateSerializer,
    UserAccountActionSerializer, UserImpersonateSerializer
)
from core.models import Branch  # If needed for branch filters





# Django
from django.core.mail.backends.smtp import EmailBackend
from django.conf import settings
from django.contrib.auth import authenticate
from django.core.mail import EmailMessage, send_mail
from django.db import transaction, ProgrammingError
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

# Django Tenants
from django_tenants.utils import tenant_context

from rest_framework import viewsets, status, serializers, generics, serializers
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, NotFound, APIException
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework_simplejwt.tokens import RefreshToken

# Third-party
import jwt
from cryptography.hazmat.primitives import serialization

# App-specific
from auth_service.views import CustomUserMinimalSerializer
from auth_service.utils.jwt_rsa import validate_rsa_jwt, issue_rsa_jwt
from .utils import get_daily_usage

from .models import (
    CustomUser,RSAKeyPair,
    UserSession,
    PasswordResetToken,
    
    BlockedIP,
    UserActivity,
    ClientProfile,
    ProofOfAddress,
    InsuranceVerification,
    DrivingRiskAssessment,
    LegalWorkEligibility,
)

from .serializers import (
    CustomUserSerializer,
    UserAccountActionSerializer,
    UserCreateSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    AdminUserCreateSerializer,
    UserBranchUpdateSerializer,
    UserSessionSerializer,
    ClientCreateSerializer,
    ClientDetailSerializer,
    UserPasswordRegenerateSerializer,
    BlockedIPSerializer,
    UserActivitySerializer,
    UserImpersonateSerializer,
    ClientProfileSerializer,
)

from core.models import Tenant, Branch, TenantConfig
from users.models import CustomUser  # Only needed if used as a separate import

# Logger
logger = logging.getLogger('users')


class CustomPagination(PageNumberPagination):
    page_size = 20


class TermsAndConditionsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        tenant = request.user.tenant
        with tenant_context(tenant):
            user = request.user
            if user.has_accepted_terms:
                logger.info(f"User {user.email} has already accepted terms and conditions.")
                return Response({
                    "status": "success",
                    "message": "Terms and conditions already accepted."
                }, status=status.HTTP_200_OK)

            user.has_accepted_terms = True
            user.save()
            logger.info(f"User {user.email} accepted terms and conditions for tenant {tenant.schema_name}.")
            return Response({
                "status": "success",
                "message": "Terms and conditions accepted successfully."
            }, status=status.HTTP_200_OK)
        


class UserPasswordRegenerateView(APIView):
    def post(self, request, user_id=None):
        # Accept user_id from URL or request data
        if user_id is None:
            user_id = request.data.get('user_id')
        if not user_id:
            return Response({'detail': 'user_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = CustomUser.objects.get(id=user_id)
        except CustomUser.DoesNotExist:
            return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Generate a strong password
        alphabet = string.ascii_letters + string.digits + string.punctuation
        password = ''.join(secrets.choice(alphabet) for _ in range(20))

        user.set_password(password)
        user.save()

        return Response({
            'user_id': user.id,
            'email': user.email,
            'new_password': password
        }, status=status.HTTP_200_OK)
    

def configure_email_backend(tenant):
    """
    Configure email backend using tenant settings.
    """
 
    return EmailBackend(
        host=tenant.email_host,
        port=tenant.email_port,
        username=tenant.email_host_user,
        password=tenant.email_host_password,
        use_ssl=tenant.email_use_ssl,
        fail_silently=False
    )

class PasswordResetRequestView(generics.GenericAPIView):
    serializer_class = PasswordResetRequestSerializer
    permission_classes = [AllowAny]

    def get_tenant(self, request):
        try:
            tenant = request.tenant
            if not tenant:
                logger.error("No tenant associated with the request")
                raise serializers.ValidationError("Tenant not found.")
            return tenant
        except Exception as e:
            logger.error(f"Error extracting tenant: {str(e)}")
            raise serializers.ValidationError(f"Error extracting tenant: {str(e)}")

    def post(self, request, *args, **kwargs):
        try:
            tenant = self.get_tenant(request)

            serializer = self.get_serializer(data=request.data, context={'request': request})
            if not serializer.is_valid():
                logger.error(f"Validation failed for password reset request: {serializer.errors}")
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            email = serializer.validated_data['email']
           
            with tenant_context(tenant):
                try:
                    user = CustomUser.objects.get(email=email, tenant=tenant)
                except CustomUser.DoesNotExist:
                    logger.error(f"User with email {email} not found for tenant {tenant.schema_name}")
                    return Response({"detail": f"No user found with email '{email}'."}, status=status.HTTP_404_NOT_FOUND)

                # Validate email configuration
                required_email_fields = ['email_host', 'email_port', 'email_host_user', 'email_host_password', 'default_from_email']
                missing_fields = [field for field in required_email_fields if not getattr(tenant, field)]

                if missing_fields:
                    logger.error(f"Missing email configuration fields for tenant {tenant.schema_name}: {missing_fields}")
                    return Response(
                        {"detail": f"Missing email configuration: {', '.join(missing_fields)}"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                    

                # Generate reset token
                with transaction.atomic():
                    token = str(uuid.uuid4())
                    expires_at = timezone.now() + timedelta(hours=1)  # Token valid for 1 hour
                    PasswordResetToken.objects.create(
                        user=user,
                        tenant=tenant,
                        token=token,
                        expires_at=expires_at
                    )

                    # Get email template
                    try:
                        config = TenantConfig.objects.get(tenant=tenant)
                        email_template = config.email_templates.get('passwordReset', {})
                        template_content = email_template.get('content', '')
                        is_auto_sent = email_template.get('is_auto_sent', True)
                    except TenantConfig.DoesNotExist:
                        logger.warning(f"TenantConfig not found for tenant {tenant.schema_name}")
                        template_content = (
                            'Hello [User Name],\n\n'
                            'You have requested to reset your password for [Company]. '
                            'Please use the following link to reset your password:\n\n'
                            '[Reset Link]\n\n'
                            'This link will expire in 1 hour.\n\n'
                            'Best regards,\n[Your Name]'
                        )
                        is_auto_sent = True

                    # Prepare email content
                    reset_link = f"{settings.WEB_PAGE_URL}{reverse('password_reset_confirm')}?token={token}&email={email}"

                    placeholders = {
                        '[User Name]': user.get_full_name() or user.username,
                        '[Company]': tenant.name,
                        '[Reset Link]': reset_link,
                        '[Your Name]': tenant.name,
                        '[your.email@proliance.com]': tenant.default_from_email,
                    }

                    email_body = template_content
                    for placeholder, value in placeholders.items():
                        email_body = email_body.replace(placeholder, str(value))

                    # Send email
                    if is_auto_sent or not is_auto_sent:
                        try:
                            email_connection = configure_email_backend(tenant)
                            email_subject = f"Password Reset Request for {email}"
                            email = EmailMessage(
                                subject=email_subject,
                                body=email_body,
                                from_email=tenant.default_from_email,
                                to=[user.email],
                                connection=email_connection,
                            )
                            email.send(fail_silently=False)
                        except Exception as email_error:
                            logger.exception(f"Failed to send password reset email to {user.email}: {str(email_error)}")
                            return Response({
                                "detail": "Failed to send password reset email due to invalid email configuration.",
                                "error": str(email_error),
                                "suggestion": "Please check the email settings in the tenant configuration."
                            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            return Response({
                "detail": "Password reset email sent successfully.",
                "token": token
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"Error processing password reset for tenant {tenant.schema_name if tenant else 'unknown'}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class PasswordResetConfirmView(generics.GenericAPIView):
    serializer_class = PasswordResetConfirmSerializer
    permission_classes = [AllowAny]

    def get_tenant(self, request):
        try:
            tenant = request.tenant
            if not tenant:
                logger.error("No tenant associated with the request")
                raise serializers.ValidationError("Tenant not found.")
            return tenant
        except Exception as e:
            logger.error(f"Error extracting tenant: {str(e)}")
            raise serializers.ValidationError(f"Error extracting tenant: {str(e)}")

    def post(self, request, *args, **kwargs):
        try:
            tenant = self.get_tenant(request)
            serializer = self.get_serializer(data=request.data, context={'request': request})
            if not serializer.is_valid():
                logger.error(f"Validation failed for password reset confirmation: {serializer.errors}")
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            token = serializer.validated_data['token']
            new_password = serializer.validated_data['new_password']

            with tenant_context(tenant):
                try:
                    reset_token = PasswordResetToken.objects.get(token=token, tenant=tenant)
                    if reset_token.used:
                        logger.error(f"Token {token} already used for tenant {tenant.schema_name}")
                        return Response({"detail": "This token has already been used."}, status=status.HTTP_400_BAD_REQUEST)
                    if reset_token.expires_at < timezone.now():
                        logger.error(f"Token {token} expired for tenant {tenant.schema_name}")
                        return Response({"detail": "This token has expired."}, status=status.HTTP_400_BAD_REQUEST)

                    user = reset_token.user
                    with transaction.atomic():
                        user.set_password(new_password)
                        user.last_password_reset = timezone.now()  # Update timestamp
                        user.save()
                        reset_token.used = True
                        reset_token.save()
                        logger.info(f"Password reset successfully for user {user.email} in tenant {tenant.schema_name}")

                    return Response({
                        "detail": "Password reset successfully."
                    }, status=status.HTTP_200_OK)

                except PasswordResetToken.DoesNotExist:
                    logger.error(f"Invalid token {token} for tenant {tenant.schema_name}")
                    return Response({"detail": "Invalid token."}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.exception(f"Error confirming password reset for tenant {tenant.schema_name if tenant else 'unknown'}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)



class UserViewSet(ModelViewSet):
    queryset = CustomUser.objects.all()
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    def get_base_queryset(self):
        """DRY helper for tenant-filtered queryset with role-based access."""
        tenant = self.request.user.tenant
        user = self.request.user
        with tenant_context(tenant):
            base_qs = CustomUser.objects.filter(tenant=tenant)
            if not (user.is_superuser or user.role == 'admin'):
                if user.role == 'team_manager':
                    pass  # All users in tenant
                elif user.role == 'recruiter' and user.branch:
                    base_qs = base_qs.filter(branch=user.branch)
                else:
                    base_qs = base_qs.filter(id=user.id)  # Self only
            return base_qs

    def get_queryset(self):
        """Optimized queryset: Minimal for lists, full prefetch for details."""
        base_qs = self.get_base_queryset()
        if self.action == 'list':
            # Light: select_related for basic profile, no deep nests
            return base_qs.select_related('profile', 'tenant', 'branch')
        # Full prefetch for retrieve/update/detail
        return base_qs.prefetch_related(
            'profile__professional_qualifications',
            'profile__employment_details',
            'profile__education_details',
            'profile__reference_checks',
            'profile__proof_of_address',
            'profile__insurance_verifications',
            'profile__driving_risk_assessments',
            'profile__legal_work_eligibilities',
            'profile__other_user_documents',
        )

    def get_serializer_class(self):
        if self.action == 'list':
            return CustomUserListSerializer  # Light for lists
        if self.action in ['create', 'update', 'partial_update']:
            return UserCreateSerializer
        if self.action in ['lock', 'unlock', 'suspend', 'activate']:
            return UserAccountActionSerializer
        if self.action == 'impersonate':
            return UserImpersonateSerializer
        return CustomUserSerializer  # Full for retrieve

    def perform_create(self, serializer):
        tenant = self.request.user.tenant
        if self.request.user.role != 'admin' and not self.request.user.is_superuser:
            raise serializers.ValidationError("Only admins or superusers can create users.")
        with tenant_context(tenant):
            serializer.save()


    def update(self, request, *args, **kwargs):
        tenant = request.user.tenant
        user = request.user
        logger.info(f"Raw PATCH request data for tenant {tenant.schema_name}: {dict(request.data)}")
        logger.info(f"FILES in request: {dict(request.FILES)}")
        with tenant_context(tenant):
            instance = self.get_object()
            if not (user.is_superuser or user.role == 'admin' or user.id == instance.id):
                raise PermissionDenied("You do not have permission to update this user.")
            serializer = self.get_serializer(instance, data=request.data, partial=True)
            try:
                serializer.is_valid(raise_exception=True)
                logger.info(f"Validated data for user {instance.email}: {serializer.validated_data}")
            except serializers.ValidationError as e:
                logger.error(f"Serializer errors for user {instance.email}: {serializer.errors}")
                raise
            self.perform_update(serializer)
            logger.info(f"User {instance.email} updated by {user.email} in tenant {tenant.schema_name}")
            return Response(serializer.data)

            
    def destroy(self, request, *args, **kwargs):
        tenant = request.user.tenant
        user = request.user
        with tenant_context(tenant):
            instance = self.get_object()
            if not (user.is_superuser or user.role == 'admin'):
                raise PermissionDenied("You do not have permission to delete users.")
            self.perform_destroy(instance)
            logger.info(f"User {instance.email} deleted by {user.email} in tenant {tenant.schema_name}")
            return Response(status=204)

    @action(detail=True, methods=['post'], url_path='lock')
    def lock(self, request, pk=None):
        tenant = request.user.tenant
        with tenant_context(tenant):
            instance = self.get_object()
            if request.data:  # Optional validation if data provided
                serializer = self.get_serializer(data=request.data, context={'request': request, 'user': instance})
                serializer.is_valid(raise_exception=True)
            instance.lock_account(reason=request.data.get('reason', 'Manual lock'))
            UserActivity.objects.create(
                user=instance,
                tenant=tenant,
                action='account_lock',
                performed_by=request.user,
                details={'reason': 'Manual lock'},
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                success=True
            )
            logger.info(f"User {instance.email} locked by {request.user.email} in tenant {tenant.schema_name}")
            return Response({
                "status": "success",
                "message": f"User {instance.email} account locked successfully."
            }, status=200)

    @action(detail=True, methods=['post'], url_path='unlock')
    def unlock(self, request, pk=None):
        tenant = request.user.tenant
        with tenant_context(tenant):
            instance = self.get_object()
            if request.data:
                serializer = self.get_serializer(data=request.data, context={'request': request, 'user': instance})
                serializer.is_valid(raise_exception=True)
            instance.unlock_account()
            UserActivity.objects.create(
                user=instance,
                tenant=tenant,
                action='account_unlock',
                performed_by=request.user,
                details={},
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                success=True
            )
            logger.info(f"User {instance.email} unlocked by {request.user.email} in tenant {tenant.schema_name}")
            return Response({
                "status": "success",
                "message": f"User {instance.email} account unlocked successfully."
            }, status=200)

    @action(detail=True, methods=['post'], url_path='suspend')
    def suspend(self, request, pk=None):
        tenant = request.user.tenant
        with tenant_context(tenant):
            instance = self.get_object()
            if request.data:
                serializer = self.get_serializer(data=request.data, context={'request': request, 'user': instance})
                serializer.is_valid(raise_exception=True)
            instance.suspend_account()
            UserActivity.objects.create(
                user=instance,
                tenant=tenant,
                action='account_suspend',
                performed_by=request.user,
                details={},
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                success=True
            )
            logger.info(f"User {instance.email} suspended by {request.user.email} in tenant {tenant.schema_name}")
            return Response({
                "status": "success",
                "message": f"User {instance.email} account suspended successfully."
            }, status=200)

    @action(detail=True, methods=['post'], url_path='activate')
    def activate(self, request, pk=None):
        tenant = request.user.tenant
        with tenant_context(tenant):
            instance = self.get_object()
            if request.data:
                serializer = self.get_serializer(data=request.data, context={'request': request, 'user': instance})
                serializer.is_valid(raise_exception=True)
            instance.activate_account()
            UserActivity.objects.create(
                user=instance,
                tenant=tenant,
                action='account_activate',
                performed_by=request.user,
                details={},
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                success=True
            )
            logger.info(f"User {instance.email} activated by {request.user.email} in tenant {tenant.schema_name}")
            return Response({
                "status": "success",
                "message": f"User {instance.email} account activated successfully."
            }, status=200)

    @action(detail=True, methods=['post'], url_path='impersonate')
    def impersonate(self, request, pk=None):
        tenant = request.user.tenant
        with tenant_context(tenant):
            target_user = self.get_object()
            if request.data:
                serializer = self.get_serializer(data=request.data, context={'request': request, 'user': target_user})
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
                    "exp": int((timezone.now() + timedelta(minutes=15)).timestamp()),  # Verified: ~1757598718 for Sep 11, 2025
                    "impersonated_by": request.user.email
                }
                access_token = issue_rsa_jwt(access_payload, target_user.tenant)

                refresh_jti = str(uuid.uuid4())
                refresh_payload = {
                    "jti": refresh_jti,
                    "sub": target_user.email,
                    "tenant_id": target_user.tenant.id,
                    "type": "refresh",
                    "exp": int((timezone.now() + timedelta(minutes=30)).timestamp()),
                    "impersonated_by": request.user.email
                }
                refresh_token = issue_rsa_jwt(refresh_payload, target_user.tenant)

                UserActivity.objects.create(
                    user=target_user,
                    tenant=tenant,
                    action='impersonation',
                    performed_by=request.user,
                    details={'access_jti': access_payload['jti'], 'refresh_jti': refresh_jti},
                    ip_address=request.META.get('REMOTE_ADDR'),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    success=True
                )

                logger.info(f"User {target_user.email} impersonated by {request.user.email} in tenant {tenant.schema_name}")
                return Response({
                    "status": "success",
                    "message": f"Impersonation token generated for {target_user.email}",
                    "access": access_token,
                    "refresh": refresh_token,
                    "tenant_id": target_user.tenant.id,
                    "tenant_schema": target_user.tenant.schema_name,
                    "user": CustomUserMinimalSerializer(target_user).data
                }, status=200)
            except Exception as e:
                logger.error(f"Impersonation failed for {target_user.email}: {str(e)}")
                raise serializers.ValidationError(f"Failed to generate impersonation tokens: {str(e)}")




class LoginAttemptViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = UserActivity.objects.filter(action='login')
    serializer_class = UserActivitySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    def get_queryset(self):
        tenant = self.request.user.tenant
        user = self.request.user
        with tenant_context(tenant):
            if not (user.is_superuser or user.role == 'admin'):
                raise PermissionDenied("Only admins or superusers can view login attempts.")
            
            queryset = UserActivity.objects.filter(tenant=tenant, action='login')
            
            email = self.request.query_params.get('email')
            ip_address = self.request.query_params.get('ip_address')
            date_from = self.request.query_params.get('date_from')
            date_to = self.request.query_params.get('date_to')
            success = self.request.query_params.get('success')

            if email:
                queryset = queryset.filter(user__email__icontains=email)
            if ip_address:
                queryset = queryset.filter(ip_address=ip_address)
            if date_from:
                queryset = queryset.filter(timestamp__gte=date_from)
            if date_to:
                queryset = queryset.filter(timestamp__lte=date_to)
            if success is not None:
                queryset = queryset.filter(success=(success.lower() == 'true'))

            return queryset.order_by('-timestamp')

class BlockedIPViewSet(viewsets.ModelViewSet):
    queryset = BlockedIP.objects.all()
    serializer_class = BlockedIPSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    def get_queryset(self):
        tenant = self.request.user.tenant
        user = self.request.user
        with tenant_context(tenant):
            if not (user.is_superuser or user.role == 'admin'):
                raise PermissionDenied("Only admins or superusers can manage blocked IPs.")
            return BlockedIP.objects.filter(tenant=tenant).order_by('-blocked_at')

    def perform_create(self, serializer):
        serializer.save(
            tenant=self.request.user.tenant,
            blocked_by=self.request.user,
            is_active=True
        )
        UserActivity.objects.create(
            user=None,
            tenant=self.request.user.tenant,
            action='ip_block',
            performed_by=self.request.user,
            details={'ip_address': serializer.validated_data['ip_address']},
            ip_address=self.request.META.get('REMOTE_ADDR'),
            user_agent=self.request.META.get('HTTP_USER_AGENT', ''),
            success=True
        )
        logger.info(f"IP {serializer.validated_data['ip_address']} blocked by {self.request.user.email} in tenant {self.request.user.tenant.schema_name}")

    def perform_update(self, serializer):
        serializer.save(blocked_by=self.request.user)
        logger.info(f"IP {serializer.validated_data['ip_address']} updated by {self.request.user.email} in tenant {self.request.user.tenant.schema_name}")

    @action(detail=True, methods=['post'], url_path='unblock')
    def unblock(self, request, pk=None):
        tenant = request.user.tenant
        with tenant_context(tenant):
            ip = self.get_object()
            if not (request.user.is_superuser or request.user.role == 'admin'):
                raise PermissionDenied("Only admins or superusers can unblock IPs.")
            ip.is_active = False
            ip.save()
            UserActivity.objects.create(
                user=None,
                tenant=tenant,
                action='ip_unblock',
                performed_by=request.user,
                details={'ip_address': ip.ip_address},
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                success=True
            )
            logger.info(f"IP {ip.ip_address} unblock by {request.user.email} in tenant {tenant.schema_name}")
            return Response({
                "status": "success",
                "message": f"IP {ip.ip_address} unblocked successfully."
            }, status=status.HTTP_200_OK)

class UserActivityViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = UserActivity.objects.all()
    serializer_class = UserActivitySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    def get_queryset(self):
        tenant = self.request.user.tenant
        user = self.request.user
        with tenant_context(tenant):
            if not (user.is_superuser or user.role == 'admin'):
                raise PermissionDenied("Only admins or superusers can view user activity logs.")
            queryset = UserActivity.objects.filter(tenant=tenant)
            action = self.request.query_params.get('action')
            user_email = self.request.query_params.get('user_email')
            date_from = self.request.query_params.get('date_from')
            date_to = self.request.query_params.get('date_to')
            success = self.request.query_params.get('success')

            if action:
                queryset = queryset.filter(action=action)
            if user_email:
                queryset = queryset.filter(user__email__icontains=user_email)
            if date_from:
                queryset = queryset.filter(timestamp__gte=date_from)
            if date_to:
                queryset = queryset.filter(timestamp__lte=date_to)
            if success is not None:
                queryset = queryset.filter(success=(success.lower() == 'true'))

            return queryset.order_by('-timestamp')

class UserPasswordRegenerateView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserPasswordRegenerateSerializer

    def post(self, request, *args, **kwargs):
        tenant = request.user.tenant
        with tenant_context(tenant):
            serializer = self.get_serializer(data=request.data, context={'request': request})
            serializer.is_valid(raise_exception=True)
            email = serializer.validated_data['email']
            user = CustomUser.objects.get(email=email)

            characters = string.ascii_letters + string.digits + string.punctuation
            new_password = ''.join(secrets.choice(characters) for _ in range(12))
            user.set_password(new_password)
            user.last_password_reset = timezone.now()
            user.save()

            try:
                tenant_config = TenantConfig.objects.get(tenant=tenant)
                email_from = tenant_config.email_from or 'no-reply@yourdomain.com'
                email_subject = f"Password Reset for {tenant.name}"
                email_body = (
                    f"Dear {user.first_name or 'User'},\n\n"
                    f"Your password has been reset by an administrator.\n"
                    f"New Password: {new_password}\n\n"
                    f"Please log in and change your password as soon as possible.\n"
                    f"Login URL: {request.build_absolute_uri('/login/')}\n\n"
                    f"If you did not request this, please contact support.\n"
                    f"Best regards,\n{tenant.name} Team"
                )

                send_mail(
                    subject=email_subject,
                    message=email_body,
                    from_email=email_from,
                    recipient_list=[user.email],
                    fail_silently=False,
                    auth_user=tenant_config.email_user,
                    auth_password=tenant_config.email_password,
                    connection=None
                )
                UserActivity.objects.create(
                    user=user,
                    tenant=tenant,
                    action='password_reset',
                    performed_by=request.user,
                    details={},
                    ip_address=request.META.get('REMOTE_ADDR'),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    success=True
                )
                logger.info(f"Password reset email sent to {user.email} for tenant {tenant.schema_name}")
            except TenantConfig.DoesNotExist:
                logger.error(f"No TenantConfig found for tenant {tenant.schema_name}")
                return Response({"error": "Email configuration not set for this tenant"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            except Exception as e:
                logger.error(f"Failed to send password reset email to {user.email}: {str(e)}")
                return Response({"error": f"Failed to send email: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            logger.info(f"Password reset for user {user.email} by {request.user.email} in tenant {tenant.schema_name}")
            return Response({
                "status": "success",
                "message": f"Password reset successfully for {user.email}. An email has been sent with the new password."
            }, status=status.HTTP_200_OK)

# @csrf_exempt
# def token_view(request):
#     if request.method != "POST":
#         return HttpResponse(status=405)
#     try:
#         body = json.loads(request.body.decode() or "{}")
#         email = body.get("email")
#         password = body.get("password")
#         if not email or not password:
#             ip_address = request.META.get('REMOTE_ADDR')
#             user_agent = request.META.get('HTTP_USER_AGENT', '')
#             tenant = Tenant.objects.first()  # Fallback tenant for logging
#             UserActivity.objects.create(
#                 user=None,
#                 tenant=tenant,
#                 action='login',
#                 performed_by=None,
#                 details={'reason': 'Email or password missing'},
#                 ip_address=ip_address,
#                 user_agent=user_agent,
#                 success=False
#             )
#             return JsonResponse({"error": "Email and password required"}, status=400)
        
#         try:
#             domain = email.split('@')[1].lower()
#             tenant = Tenant.objects.get(domain__domain=domain)
#         except (IndexError, Tenant.DoesNotExist):
#             ip_address = request.META.get('REMOTE_ADDR')
#             user_agent = request.META.get('HTTP_USER_AGENT', '')
#             tenant = Tenant.objects.first()  # Fallback tenant for logging
#             UserActivity.objects.create(
#                 user=None,
#                 tenant=tenant,
#                 action='login',
#                 performed_by=None,
#                 details={'reason': f"Invalid tenant for email: {email}"},
#                 ip_address=ip_address,
#                 user_agent=user_agent,
#                 success=False
#             )
#             logger.error(f"Invalid email or tenant not found for email: {email}")
#             return JsonResponse({"error": "Invalid tenant"}, status=400)

#         with tenant_context(tenant):
#             ip_address = request.META.get('REMOTE_ADDR')
#             user_agent = request.META.get('HTTP_USER_AGENT', '')

#             if BlockedIP.objects.filter(ip_address=ip_address, tenant=tenant, is_active=True).exists():
#                 UserActivity.objects.create(
#                     user=None,
#                     tenant=tenant,
#                     action='login',
#                     performed_by=None,
#                     details={'reason': 'IP address blocked'},
#                     ip_address=ip_address,
#                     user_agent=user_agent,
#                     success=False
#                 )
#                 logger.info(f"Blocked IP {ip_address} attempted login for tenant {tenant.schema_name}")
#                 return JsonResponse({"error": "This IP address is blocked"}, status=403)

#             user = CustomUser.objects.filter(email=email).first()
#             if user:
#                 if user.is_locked or user.status == 'suspended' or not user.is_active:
#                     UserActivity.objects.create(
#                         user=user,
#                         tenant=tenant,
#                         action='login',
#                         performed_by=None,
#                         details={'reason': 'Account locked or suspended'},
#                         ip_address=ip_address,
#                         user_agent=user_agent,
#                         success=False
#                     )
#                     return JsonResponse({"error": "Account is locked or suspended"}, status=403)
                
#                 authenticated_user = authenticate(email=email, password=password)
#                 if authenticated_user:
#                     user.reset_login_attempts()
#                     UserActivity.objects.create(
#                         user=user,
#                         tenant=tenant,
#                         action='login',
#                         performed_by=None,
#                         details={},
#                         ip_address=ip_address,
#                         user_agent=user_agent,
#                         success=True
#                     )
#                     payload = {
#                         "sub": user.email,
#                         "role": user.role,
#                         "tenant_id": user.tenant.id,
#                     }
#                     token = issue_rsa_jwt(payload, user.tenant)
#                     return JsonResponse({"access_token": token})
#                 else:
#                     user.increment_login_attempts()
#                     UserActivity.objects.create(
#                         user=user,
#                         tenant=tenant,
#                         action='login',
#                         performed_by=None,
#                         details={'reason': 'Invalid credentials'},
#                         ip_address=ip_address,
#                         user_agent=user_agent,
#                         success=False
#                     )

#                     ten_minutes_ago = timezone.now() - timedelta(minutes=10)
#                     failed_attempts = UserActivity.objects.filter(
#                         action='login',
#                         success=False,
#                         ip_address=ip_address,
#                         tenant=tenant,
#                         timestamp__gte=ten_minutes_ago
#                     ).count()
#                     if failed_attempts >= 10 and not BlockedIP.objects.filter(ip_address=ip_address, tenant=tenant, is_active=True).exists():
#                         BlockedIP.objects.create(
#                             ip_address=ip_address,
#                             tenant=tenant,
#                             reason="Excessive failed login attempts",
#                             blocked_by=None
#                         )
#                         UserActivity.objects.create(
#                             user=None,
#                             tenant=tenant,
#                             action='ip_block',
#                             performed_by=None,
#                             details={'ip_address': ip_address},
#                             ip_address=ip_address,
#                             user_agent=user_agent,
#                             success=True
#                         )
#                         logger.info(f"IP {ip_address} auto-blocked for tenant {tenant.schema_name} due to excessive failed logins")
#                         return JsonResponse({"error": "This IP address has been blocked due to excessive failed login attempts"}, status=403)

#                     return JsonResponse({"error": f"Invalid credentials. {5 - user.login_attempts} attempts remaining."}, status=401)
#             else:
#                 UserActivity.objects.create(
#                     user=None,
#                     tenant=tenant,
#                     action='login',
#                     performed_by=None,
#                     details={'reason': f"User not found for email: {email}"},
#                     ip_address=ip_address,
#                     user_agent=user_agent,
#                     success=False
#                 )

#                 ten_minutes_ago = timezone.now() - timedelta(minutes=10)
#                 failed_attempts = UserActivity.objects.filter(
#                     action='login',
#                     success=False,
#                     ip_address=ip_address,
#                     tenant=tenant,
#                     timestamp__gte=ten_minutes_ago
#                 ).count()
#                 if failed_attempts >= 10 and not BlockedIP.objects.filter(ip_address=ip_address, tenant=tenant, is_active=True).exists():
#                     BlockedIP.objects.create(
#                         ip_address=ip_address,
#                         tenant=tenant,
#                         reason="Excessive failed login attempts",
#                         blocked_by=None
#                     )
#                     UserActivity.objects.create(
#                         user=None,
#                         tenant=tenant,
#                         action='ip_block',
#                         performed_by=None,
#                         details={'ip_address': ip_address},
#                         ip_address=ip_address,
#                         user_agent=user_agent,
#                         success=True
#                     )
#                     logger.info(f"IP {ip_address} auto-blocked for tenant {tenant.schema_name} due to excessive failed logins")
#                     return JsonResponse({"error": "This IP address has been blocked due to excessive failed login attempts"}, status=403)

#                 return JsonResponse({"error": "Invalid credentials"}, status=401)
#     except Exception as e:
#         logger.error(f"Error in token_view: {str(e)}")
#         return JsonResponse({"error": str(e)}, status=400)


class UserCreateView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        logger.debug(f"User creation request for tenant {request.user.tenant.schema_name}: {dict(request.data)}")
        serializer = UserCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            try:
                user = serializer.save()
                refresh = RefreshToken.for_user(user)
                logger.info(f"User created: {user.email} (ID: {user.id}) for tenant {user.tenant.schema_name}")
                return Response({
                    'status': 'success',
                    'message': f"User {user.email} created successfully.",
                    'data': {
                        'id': user.id,
                        'username': user.username,
                        'email': user.email,
                        'first_name': user.first_name,
                        'last_name': user.last_name,
                        'role': user.role,
                        'job_role': user.job_role,
                        'dashboard': user.dashboard,
                        'access_level': user.access_level,
                        'status': user.status,
                        'two_factor': user.two_factor,
                        'tenant_id': user.tenant.id,
                        'tenant_schema': user.tenant.schema_name,
                        'branch': user.branch.name if user.branch else None,
                        'refresh': str(refresh),
                        'access': str(refresh.access_token),
                    }
                }, status=status.HTTP_201_CREATED)
            except Exception as e:
                logger.error(f"Error creating user for tenant {request.user.tenant.schema_name}: {str(e)}")
                return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        logger.error(f"Validation error for tenant {request.user.tenant.schema_name}: {serializer.errors}")
        return Response({'status': 'error', 'message': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)




class AdminUserCreateView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        serializer = AdminUserCreateSerializer(data=request.data)
        if serializer.is_valid():
            try:
                user = serializer.save()
                refresh = RefreshToken.for_user(user)
                logger.info(f"Admin user created: {user.email} for tenant {user.tenant.schema_name}")
                return Response({
                    'status': 'success',
                    'message': f"Admin user {user.email} created successfully.",
                    'data': {
                        'username': user.username,
                        'email': user.email,
                        'first_name': user.first_name,
                        'last_name': user.last_name,
                        'job_role': user.job_role,
                        'tenant_id': user.tenant.id,
                        'tenant_schema': user.tenant.schema_name,
                        'branch': user.branch.name if user.branch else None,
                        # 'refresh': str(refresh),
                        # 'access': str(refresh.access_token),
                    }
                }, status=status.HTTP_201_CREATED)
            except Exception as e:
                logger.error(f"Error creating admin user: {str(e)}")
                return Response({
                    'status': 'error',
                    'message': str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        logger.error(f"Validation error: {serializer.errors}")
        return Response({
            'status': 'error',
            'message': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)




class UserBranchUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def get_tenant_from_token(self, request):
        try:
            if hasattr(request, 'tenant') and request.tenant:
                logger.debug(f"Tenant from request: {request.tenant.schema_name}")
                return request.tenant
            if hasattr(request.user, 'tenant') and request.user.tenant:
                logger.debug(f"Tenant from user: {request.user.tenant.schema_name}")
                return request.user.tenant
            auth_header = request.headers.get('Authorization', '')
            if not auth_header.startswith('Bearer '):
                logger.warning("No valid Bearer token provided")
                raise ValueError("Invalid token format")
            token = auth_header.split(' ')[1]
            decoded_token = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            tenant_id = decoded_token.get('tenant_id')
            schema_name = decoded_token.get('tenant_schema')
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
                    status=status.HTTP_404_NOT_FOUND
                )

            # Check permissions: Only admins, superusers, or team managers can update branch
            if not (request.user.is_superuser or request.user.role == 'admin' or request.user.role == 'team_manager'):
                logger.warning(f"Unauthorized branch update attempt by user {request.user.email} for user {user.email}")
                return Response(
                    {"status": "error", "message": "Only admins or team managers can update user branch"},
                    status=status.HTTP_403_FORBIDDEN
                )

            serializer = UserBranchUpdateSerializer(user, data=request.data, context={'request': request}, partial=True)
            if serializer.is_valid():
                try:
                    with transaction.atomic():
                        serializer.save()
                        logger.info(f"User {user.email} assigned to branch {user.branch.name if user.branch else 'None'} for tenant {tenant.schema_name}")
                        return Response(
                            {
                                "status": "success",
                                "message": f"User {user.email} branch updated successfully",
                                "data": CustomUserSerializer(user, context={'request': request}).data
                            },
                            status=status.HTTP_200_OK
                        )
                except Exception as e:
                    logger.error(f"Error updating branch for user {user.email} in tenant {tenant.schema_name}: {str(e)}")
                    return Response(
                        {"status": "error", "message": str(e)},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
            logger.error(f"Validation error for user {user.email} in tenant {tenant.schema_name}: {serializer.errors}")
            return Response(
                {"status": "error", "message": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

# New view for listing all users in a tenant
class TenantUsersListView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    def get_tenant_from_token(self, request):
        try:
            if hasattr(request, 'tenant') and request.tenant:
                logger.debug(f"Tenant from request: {request.tenant.schema_name}")
                return request.tenant
            if hasattr(request.user, 'tenant') and request.user.tenant:
                logger.debug(f"Tenant from user: {request.user.tenant.schema_name}")
                return request.user.tenant
            auth_header = request.headers.get('Authorization', '')
            if not auth_header.startswith('Bearer '):
                logger.warning("No valid Bearer token provided")
                raise ValueError("Invalid token format")
            token = auth_header.split(' ')[1]
            decoded_token = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            tenant_id = decoded_token.get('tenant_id')
            schema_name = decoded_token.get('tenant_schema')
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
            if not (request.user.is_superuser or request.user.role == 'admin' or request.user.role == 'team_manager'):
                return Response(
                    {"status": "error", "message": "Only admins or team managers can list all tenant users"},
                    status=status.HTTP_403_FORBIDDEN
                )
            users = CustomUser.objects.filter(tenant=tenant).prefetch_related(
                'profile__professional_qualifications',
                'profile__employment_details',
                'profile__education_details',
                'profile__reference_checks',
                'profile__proof_of_address',
                'profile__insurance_verifications',
                'profile__driving_risk_assessments',
                'profile__legal_work_eligibilities',
                'profile__other_user_documents',
            )
            serializer = CustomUserSerializer(users, many=True, context={'request': request})
            return Response({
                "status": "success",
                "message": f"Retrieved {users.count()} users for tenant {tenant.schema_name}",
                "data": serializer.data
            }, status=status.HTTP_200_OK)

class BranchUsersListView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    def get(self, request, branch_id):
        tenant = self.get_tenant_from_token(request)
        with tenant_context(tenant):
            branch = Branch.objects.get(id=branch_id, tenant=tenant)
            if not (request.user.is_superuser or request.user.role == 'admin' or request.user.role == 'team_manager' or
                    (request.user.role == 'recruiter' and request.user.branch == branch)):
                return Response(
                    {"status": "error", "message": "Only admins, team managers, or recruiters assigned to this branch can list users"},
                    status=status.HTTP_403_FORBIDDEN
                )
            users = CustomUser.objects.filter(tenant=tenant, branch=branch).prefetch_related(
                'profile__professional_qualifications',
                'profile__employment_details',
                'profile__education_details',
                'profile__reference_checks',
                'profile__proof_of_address',
                'profile__insurance_verifications',
                'profile__driving_risk_assessments',
                'profile__legal_work_eligibilities',
               'profile__other_user_documents',
            )
            serializer = CustomUserSerializer(users, many=True, context={'request': request})
            return Response({
                "status": "success",
                "message": f"Retrieved {users.count()} users for branch {branch.name}",
                "data": serializer.data
            }, status=status.HTTP_200_OK)




class UserSessionViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    def get_tenant(self, request):
        # Adjust this if you have a different way to get tenant
        return getattr(request, 'tenant', getattr(request.user, 'tenant', None))
    

    @action(detail=True, methods=['patch', 'put'], url_path='edit')
    def edit_session(self, request, pk=None):
        """
        Allows the user to edit their own session's login_time and logout_time.
        """
        tenant = self.get_tenant(request)
        with tenant_context(tenant):
            try:
                session = UserSession.objects.get(pk=pk, user=request.user)
            except UserSession.DoesNotExist:
                return Response({'detail': 'Session not found.'}, status=404)

            login_time = request.data.get('login_time')
            logout_time = request.data.get('logout_time')

            if login_time:
                try:
                    session.login_time = timezone.make_aware(timezone.datetime.fromisoformat(login_time))
                except Exception:
                    return Response({'detail': 'Invalid login_time format. Use ISO 8601.'}, status=400)
            if logout_time:
                try:
                    session.logout_time = timezone.make_aware(timezone.datetime.fromisoformat(logout_time))
                except Exception:
                    return Response({'detail': 'Invalid logout_time format. Use ISO 8601.'}, status=400)

            session.save()
            return Response(UserSessionSerializer(session).data, status=200)

    @action(detail=False, methods=['post'], url_path='clock-in')
    def clock_in(self, request):
        tenant = self.get_tenant(request)
        with tenant_context(tenant):
            # Prevent multiple open sessions
            open_session = UserSession.objects.filter(user=request.user, logout_time__isnull=True).last()
            if open_session:
                return Response({'detail': 'You already have an open session. Please clock out first.'}, status=400)
            ip = request.META.get('REMOTE_ADDR')
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            session = UserSession.objects.create(
                user=request.user,
                login_time=timezone.now(),
                date=timezone.now().date(),
                ip_address=ip,
                user_agent=user_agent
            )
            return Response({'detail': 'Clocked in.', 'session_id': session.id}, status=201)

    @action(detail=False, methods=['post'], url_path='clock-out')
    def clock_out(self, request):
        tenant = self.get_tenant(request)
        with tenant_context(tenant):
            session = UserSession.objects.filter(user=request.user, logout_time__isnull=True).last()
            if not session:
                return Response({'detail': 'No open session found.'}, status=400)
            session.logout_time = timezone.now()
            session.save()
            return Response({'detail': 'Clocked out.', 'duration': session.duration}, status=200)

    @action(detail=False, methods=['get'], url_path='daily-history')
    def daily_history(self, request):
        tenant = self.get_tenant(request)
        date_str = request.query_params.get('date')
        if date_str:
            try:
                date = timezone.datetime.strptime(date_str, "%Y-%m-%d").date()
            except Exception:
                return Response({'detail': 'Invalid date format. Use YYYY-MM-DD.'}, status=400)
        else:
            date = timezone.now().date()
        with tenant_context(tenant):
            sessions = UserSession.objects.filter(user=request.user, date=date)
            total = get_daily_usage(request.user, date)
            # You need to implement UserSessionSerializer
            data = UserSessionSerializer(sessions, many=True).data
            return Response({'sessions': data, 'total_time': total}, status=200)



class ClientViewSet(viewsets.ModelViewSet):
    queryset = CustomUser.objects.filter(role='client').prefetch_related('client_profile')
    serializer_class = ClientDetailSerializer
    pagination_class = CustomPagination
    
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant = self.request.user.tenant
        user = self.request.user
        with tenant_context(tenant):
            if user.is_superuser or user.role == 'admin':
                return CustomUser.objects.filter(tenant=tenant, role='client').prefetch_related('client_profile')
            elif user.role == 'team_manager':
                return CustomUser.objects.filter(tenant=tenant, role='client').prefetch_related('client_profile')
            elif user.role == 'recruiter' and user.branch:
                return CustomUser.objects.filter(tenant=tenant, role='client', branch=user.branch).prefetch_related('client_profile')
            else:
                return CustomUser.objects.filter(tenant=tenant, id=user.id, role='client').prefetch_related('client_profile')

    def get_serializer_class(self):
        if self.action == 'create':
            return ClientCreateSerializer
        return ClientDetailSerializer  # Use for retrieve, update, partial_update

    def perform_create(self, serializer):
        tenant = self.request.user.tenant
        if not (self.request.user.is_superuser or self.request.user.role == 'admin'):
            raise PermissionDenied("Only admins or superusers can create clients.")
        with tenant_context(tenant):
            serializer.save()

    def update(self, request, *args, **kwargs):
        tenant = request.user.tenant
        user = request.user
        with tenant_context(tenant):
            instance = self.get_object()
            if not (user.is_superuser or user.role == 'admin' or user.id == instance.id):
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
            if not (user.is_superuser or user.role == 'admin'):
                raise PermissionDenied("You do not have permission to delete clients.")
            self.perform_destroy(instance)
            return Response(status=status.HTTP_204_NO_CONTENT)
        


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
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.asymmetric import rsa
    import json

    pubkey = serialization.load_pem_public_key(public_pem.encode(), backend=default_backend())
    numbers = pubkey.public_numbers()
    n = base64.urlsafe_b64encode(numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, 'big')).rstrip(b'=').decode('utf-8')
    e = base64.urlsafe_b64encode(numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, 'big')).rstrip(b'=').decode('utf-8')
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
        encryption_algorithm=serialization.NoEncryption()
    ).decode('utf-8')
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode('utf-8')
    return private_pem, public_pem

class RSAKeyPairCreateView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        tenant_id = request.data.get('tenant_id')
        schema_name = request.data.get('schema_name')
        
        # Validate input: either tenant_id or schema_name must be provided
        if not tenant_id and not schema_name:
            logger.error("No tenant_id or schema_name provided in request")
            return Response({
                'status': 'error',
                'message': 'Either tenant_id or schema_name is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Fetch tenant based on tenant_id or schema_name
            if tenant_id:
                tenant = Tenant.objects.get(id=tenant_id)
            else:
                tenant = Tenant.objects.get(schema_name=schema_name)

            # Generate RSA key pair
            private_pem, public_pem = generate_rsa_keypair()

            # Create RSAKeyPair within tenant context
            with tenant_context(tenant):
                keypair = RSAKeyPair.objects.create(
                    tenant=tenant,
                    private_key_pem=private_pem,
                    public_key_pem=public_pem,
                    active=True
                )
                logger.info(f"RSAKeyPair created for tenant: {tenant.schema_name}, kid: {keypair.kid}")

            return Response({
                'status': 'success',
                'message': f'RSAKeyPair created successfully for tenant {tenant.schema_name}',
                'data': {
                    'tenant_id': tenant.id,
                    'tenant_schema': tenant.schema_name,
                    'kid': keypair.kid,
                    'public_key': public_pem
                }
            }, status=status.HTTP_201_CREATED)

        except Tenant.DoesNotExist:
            logger.error(f"Tenant not found: tenant_id={tenant_id}, schema_name={schema_name}")
            return Response({
                'status': 'error',
                'message': 'Tenant not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error creating RSAKeyPair: {str(e)}")
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)