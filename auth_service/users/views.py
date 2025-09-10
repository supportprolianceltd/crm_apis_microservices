import base64
import json
import jwt
import logging
import secrets
import string
import uuid

from datetime import datetime, timedelta, timezone
from cryptography.hazmat.primitives import serialization

from django.conf import settings
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.db import transaction, connection, ProgrammingError
from django.db.models import Count, Q
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from django_filters.rest_framework import DjangoFilterBackend

from rest_framework import serializers, viewsets, generics, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, NotFound, APIException
from rest_framework.filters import SearchFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from django_tenants.utils import tenant_context

from auth_service.utils.jwt_rsa import validate_rsa_jwt, issue_rsa_jwt
from .utils import get_daily_usage
from .models import (
    RSAKeyPair,
    ClientProfile,
    PasswordResetToken,
    ProofOfAddress,
    InsuranceVerification,
    DrivingRiskAssessment,
    LegalWorkEligibility,
    UserSession,
    FailedLogin,
    BlockedIP,
    VulnerabilityAlert,
    ComplianceReport,
    CustomUser,
    UserActivity,
)

from .serializers import (
    FailedLoginSerializer,
    BlockedIPSerializer,
    VulnerabilityAlertSerializer,
    ComplianceReportSerializer,
    AdminUserCreateSerializer,
    UserActivitySerializer,
    CustomUserSerializer,
    ClientCreateSerializer,
    ClientProfileSerializer,
    ClientDetailSerializer,
    UserCreateSerializer,
    PasswordResetConfirmSerializer,
    UserBranchUpdateSerializer,
    PasswordResetRequestSerializer,
    UserSessionSerializer,
)

from core.models import Tenant, Branch, TenantConfig
from users.models import CustomUser

logger = logging.getLogger('auth_service')



class CustomPagination(PageNumberPagination):
    page_size = 20

class TenantBaseView:
    """Base view to extract tenant from request."""
    @property
    def tenant(self):
        return getattr(self.request, 'tenant', getattr(self.request.user, 'tenant', None))



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



# UserViewSet with advanced filtering/statistics
class UserViewSet(TenantBaseView, viewsets.ModelViewSet):
    serializer_class = CustomUserSerializer  # Use your serializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    pagination_class = CustomPagination
    filter_backends = []  # Add DjangoFilterBackend, SearchFilter if installed
    filterset_fields = ['role', 'status', 'is_locked']
    search_fields = ['first_name', 'last_name', 'email']

    def get_queryset(self):
        tenant = self.request.tenant
        with tenant_context(tenant):
            queryset = CustomUser.objects.filter(tenant=tenant, is_deleted=False).select_related('tenant')
            role = self.request.query_params.get('role')
            status = self.request.query_params.get('status')
            is_locked = self.request.query_params.get('is_locked')
            search = self.request.query_params.get('search')
            date_from = self.request.query_params.get('date_from')
            date_to = self.request.query_params.get('date_to')
            if role and role != 'all':
                queryset = queryset.filter(role=role)
            if status and status != 'all':
                queryset = queryset.filter(status=status)
            if is_locked is not None:
                queryset = queryset.filter(is_locked=is_locked.lower() == 'true')
            if search:
                queryset = queryset.filter(
                    Q(first_name__icontains=search) |
                    Q(last_name__icontains=search) |
                    Q(email__icontains=search)
                )
            if date_from:
                try:
                    queryset = queryset.filter(date_joined__gte=datetime.fromisoformat(date_from))
                except ValueError:
                    logger.warning(f"[{tenant.schema_name}] Invalid date_from format: {date_from}")
                    raise serializers.ValidationError("Invalid date_from format")
            if date_to:
                try:
                    queryset = queryset.filter(date_joined__lte=datetime.fromisoformat(date_to))
                except ValueError:
                    logger.warning(f"[{tenant.schema_name}] Invalid date_to format: {date_to}")
                    raise serializers.ValidationError("Invalid date_to format")
            logger.debug(f"[{tenant.schema_name}] User query: {queryset.query}")
            return queryset.order_by('-date_joined')

    def create(self, request, *args, **kwargs):
        tenant = request.tenant
        if request.user.role != 'admin' and not request.user.is_superuser:
            logger.warning(f"[{tenant.schema_name}] Non-admin user {request.user.email} attempted to create user")
            return Response({"detail": "Only admins or superusers can create users"}, status=status.HTTP_403_FORBIDDEN)
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except serializers.ValidationError as e:
            logger.error(f"[{tenant.schema_name}] User creation validation failed: {str(e)}")
            raise
        with tenant_context(tenant), transaction.atomic():
            user = serializer.save()
            UserActivity.objects.create(
                user=user,
                activity_type='user_created',
                details=f'User "{user.email}" created by {request.user.email}',
                status='success'
            )
            logger.info(f"[{tenant.schema_name}] User created: {user.email}")
            return Response({
                'detail': 'User created successfully',
                'data': serializer.data
            }, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        tenant = request.tenant
        user = self.get_object()
        serializer = self.get_serializer(user, data=request.data, partial=kwargs.get('partial', False))
        try:
            serializer.is_valid(raise_exception=True)
        except serializers.ValidationError as e:
            logger.error(f"[{tenant.schema_name}] User update validation failed for {user.email}: {serializer.errors}")
            return Response({"detail": "Validation failed", "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        with tenant_context(tenant), transaction.atomic():
            serializer.save()
            UserActivity.objects.create(
                user=user,
                activity_type='user_updated',
                details=f'User "{user.email}" updated by {request.user.email}',
                status='success'
            )
            logger.info(f"[{tenant.schema_name}] User updated: {user.email}")
            return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        tenant = request.tenant
        user = self.get_object()
        if request.user.role != 'admin' and not request.user.is_superuser:
            logger.warning(f"[{tenant.schema_name}] Non-admin user {request.user.email} attempted to delete user {user.email}")
            return Response({"detail": "Only admins or superusers can delete users"}, status=status.HTTP_403_FORBIDDEN)
        with tenant_context(tenant), transaction.atomic():
            user.delete_account(reason="Deleted via API")
            UserActivity.objects.create(
                user=user,
                activity_type='user_deleted',
                details=f'User "{user.email}" soft-deleted by {request.user.email}',
                status='success'
            )
            logger.info(f"[{tenant.schema_name}] User soft-deleted: {user.email}")
            return Response({"detail": "User deleted successfully"}, status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'])
    def lock(self, request, pk=None):
        tenant = request.tenant
        if not (request.user.is_superuser or request.user.role == 'admin'):
            logger.warning(f"[{tenant.schema_name}] Non-admin user {request.user.email} attempted to lock user")
            return Response({"detail": "Only admins or superusers can lock accounts"}, status=status.HTTP_403_FORBIDDEN)
        with tenant_context(tenant):
            user = get_object_or_404(CustomUser, pk=pk, tenant=tenant, is_deleted=False)
            if user.is_locked:
                logger.warning(f"[{tenant.schema_name}] User {user.email} already locked")
                return Response({"detail": "User is already locked"}, status=status.HTTP_400_BAD_REQUEST)
            user.lock_account(reason=f"Account locked by {request.user.email}")
            logger.info(f"[{tenant.schema_name}] User {user.email} locked by {request.user.email}")
            return Response({"detail": f"User {user.email} locked successfully"})

    @action(detail=True, methods=['post'])
    def unlock(self, request, pk=None):
        tenant = request.tenant
        if not (request.user.is_superuser or request.user.role == 'admin'):
            logger.warning(f"[{tenant.schema_name}] Non-admin user {request.user.email} attempted to unlock user")
            return Response({"detail": "Only admins or superusers can unlock accounts"}, status=status.HTTP_403_FORBIDDEN)
        with tenant_context(tenant):
            user = get_object_or_404(CustomUser, pk=pk, tenant=tenant, is_deleted=False)
            if not user.is_locked:
                logger.warning(f"[{tenant.schema_name}] User {user.email} already unlocked")
                return Response({"detail": "User is already unlocked"}, status=status.HTTP_400_BAD_REQUEST)
            user.unlock_account(reason=f"Account unlocked by {request.user.email}")
            logger.info(f"[{tenant.schema_name}] User {user.email} unlocked by {request.user.email}")
            return Response({"detail": f"User {user.email} unlocked successfully"})

    @action(detail=True, methods=['post'])
    def reset_password(self, request, pk=None):
        tenant = request.tenant
        if not (request.user.is_superuser or request.user.role == 'admin'):
            logger.warning(f"[{tenant.schema_name}] Non-admin user {request.user.email} attempted to reset password")
            return Response({"detail": "Only admins or superusers can reset passwords"}, status=status.HTTP_403_FORBIDDEN)
        with tenant_context(tenant):
            user = get_object_or_404(CustomUser, pk=pk, tenant=tenant, is_deleted=False)
            from django.contrib.auth.tokens import default_token_generator
            from django.utils.http import urlsafe_base64_encode
            from django.utils.encoding import force_bytes
            from django.core.mail import send_mail
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            reset_link = f"{request.scheme}://{request.get_host()}/reset-password/{uid}/{token}/"
            send_mail(
                subject='Password Reset Request',
                message=f'Click the following link to reset your password: {reset_link}',
                from_email='no-reply@yourdomain.com',
                recipient_list=[user.email],
                fail_silently=False,
            )
            UserActivity.objects.create(
                user=user,
                activity_type='password_reset_initiated',
                details=f'Password reset initiated by {request.user.email}',
                status='success'
            )
            logger.info(f"[{tenant.schema_name}] Password reset initiated for user {user.email} by {request.user.email}")
            return Response({"detail": f"Password reset email sent to {user.email}"})

    @action(detail=False, methods=['get'])
    def stats(self, request):
        tenant = request.tenant
        with tenant_context(tenant):
            seven_days_ago = timezone.now() - timedelta(days=7)
            one_day_ago = timezone.now() - timedelta(days=1)
            stats = {
                'total_users': CustomUser.objects.count(),
                'active_users': CustomUser.objects.filter(status='active').count(),
                'new_signups': CustomUser.objects.filter(date_joined__gte=seven_days_ago).count(),
                'suspicious_activity': UserActivity.objects.filter(
                    activity_type__in=['login', 'account_suspended'],
                    status='failed',
                    timestamp__gte=seven_days_ago
                ).count(),
                'locked_accounts': CustomUser.objects.filter(is_locked=True).count(),
                'failed_logins': FailedLogin.objects.filter(
                    timestamp__gte=one_day_ago
                ).count(),
                'blocked_ips': BlockedIP.objects.count(),
                'active_alerts': VulnerabilityAlert.objects.filter(status='pending').count(),
                'audit_events': UserActivity.objects.filter(timestamp__gte=seven_days_ago).count(),
                'compliance_status': f"{ComplianceReport.objects.filter(status='compliant').count()}/{ComplianceReport.objects.count()}",
                'data_requests': 0,
            }
            logger.info(f"[{tenant.schema_name}] Dashboard stats retrieved")
            return Response(stats)




 

    @action(detail=True, methods=['post'])
    def impersonate(self, request, pk=None):
        tenant = request.tenant
        if not request.user.is_superuser:
            logger.warning(f"[{tenant.schema_name}] Non-superuser {request.user.email} attempted to impersonate")
            return Response({"detail": "Only superusers can impersonate"}, status=status.HTTP_403_FORBIDDEN)
        with tenant_context(tenant):
            user = get_object_or_404(CustomUser, pk=pk, tenant=tenant, is_deleted=False)
            token = RefreshToken.for_user(user)
            UserActivity.objects.create(
                user=user,
                activity_type='user_impersonated',
                details=f'User "{user.email}" impersonated by {request.user.email}',
                status='success'
            )
            logger.info(f"[{tenant.schema_name}] Superuser {request.user.email} impersonated user {user.email}")
            return Response({'token': str(token.access_token)})

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def change_password(self, request, pk=None):
        class ChangePasswordSerializer(serializers.Serializer):
            old_password = serializers.CharField(required=True)
            new_password = serializers.CharField(required=True, min_length=8)

            def validate_new_password(self, value):
                if not any(c.isupper() for c in value) or not any(c.isdigit() for c in value):
                    raise serializers.ValidationError("Password must contain at least one uppercase letter and one number.")
                return value

        tenant = request.tenant
        user = self.get_object()
        if request.user != user and not request.user.is_superuser and request.user.role != 'admin':
            logger.warning(f"[{tenant.schema_name}] User {request.user.email} attempted to change password for {user.email}")
            return Response({"detail": "You do not have permission to change this user's password"}, status=status.HTTP_403_FORBIDDEN)
        serializer = ChangePasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"detail": "Validation failed", "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        old_password = serializer.validated_data['old_password']
        new_password = serializer.validated_data['new_password']
        if not user.check_password(old_password):
            return Response({"detail": "Old password is incorrect."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            user.set_password(new_password)
            user.save()
            UserActivity.objects.create(
                user=user,
                activity_type='password_changed',
                details=f'User "{user.email}" changed password',
                status='success'
            )
            logger.info(f"[{tenant.schema_name}] User {user.email} changed password")
            return Response({"detail": "Password changed successfully."}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error changing password for user {user.email}: {str(e)}", exc_info=True)
            return Response({"detail": "Failed to change password.", "error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

class FailedLoginViewSet(TenantBaseView, viewsets.ReadOnlyModelViewSet):
    serializer_class = FailedLoginSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['status']
    search_fields = ['ip_address', 'username']

    def get_queryset(self):
        tenant = self.request.tenant
        with tenant_context(tenant):
            return FailedLogin.objects.all().order_by('-timestamp')

class BlockedIPViewSet(TenantBaseView, viewsets.ModelViewSet):
    serializer_class = BlockedIPSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['action']

    def get_queryset(self):
        tenant = self.request.tenant
        with tenant_context(tenant):
            return BlockedIP.objects.all().order_by('-timestamp')

    def perform_create(self, serializer):
        tenant = self.request.tenant
        with tenant_context(tenant):
            if BlockedIP.objects.filter(ip_address=serializer.validated_data['ip_address']).exists():
                raise serializers.ValidationError("This IP is already blocked")
            serializer.save()
            UserActivity.objects.create(
                user=self.request.user,
                activity_type='blocked_ip_added',
                details=f"IP {serializer.validated_data['ip_address']} blocked by {self.request.user.email}",
                status='success'
            )

    @action(detail=False, methods=['post'], url_path='unblock')
    def unblock(self, request):
        tenant = request.tenant
        ip_address = request.data.get('ip_address')
        if not ip_address:
            logger.warning(f"[{tenant.schema_name}] No IP address provided for unblock")
            return Response({"detail": "IP address is required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            with tenant_context(tenant):
                blocked_ip = get_object_or_404(BlockedIP, ip_address=ip_address)
                blocked_ip.delete()
                UserActivity.objects.create(
                    user=self.request.user,
                    activity_type='blocked_ip_removed',
                    details=f"IP {ip_address} unblocked by {self.request.user.email}",
                    status='success'
                )
                logger.info(f"[{tenant.schema_name}] IP {ip_address} unblocked by {self.request.user.email}")
                return Response({"detail": f"IP {ip_address} unblocked successfully"})
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error unblocking IP {ip_address}: {str(e)}", exc_info=True)
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class VulnerabilityAlertViewSet(TenantBaseView, viewsets.ModelViewSet):
    serializer_class = VulnerabilityAlertSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['severity', 'status']
    search_fields = ['title', 'component']

    def get_queryset(self):
        tenant = self.request.tenant
        with tenant_context(tenant):
            return VulnerabilityAlert.objects.all().order_by('-detected')

    def perform_update(self, serializer):
        serializer.save()
        if serializer.validated_data.get('status') == 'resolved':
            UserActivity.objects.create(
                user=self.request.user,
                activity_type='vulnerability_resolved',
                details=f"Vulnerability {serializer.validated_data['title']} resolved by {self.request.user.email}",
                status='success'
            )


class UserActivityViewSet(TenantBaseView, viewsets.ReadOnlyModelViewSet):
    """Retrieve user activity logs for a tenant."""
    serializer_class = UserActivitySerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['activity_type', 'status']
    search_fields = ['user__email', 'details']

    def get_queryset(self):
        tenant = self.request.tenant
        with tenant_context(tenant):
            queryset = UserActivity.objects.filter(user__tenant=tenant).select_related('user').order_by('-timestamp')
            user_id = self.request.query_params.get('user_id')
            if user_id:
                queryset = queryset.filter(user_id=user_id)
            logger.debug(f"[{tenant.schema_name}] User activity query: {queryset.query}")
            return queryset

    def list(self, request, *args, **kwargs):
        tenant = request.tenant
        try:
            queryset = self.get_queryset()
            page = self.paginate_queryset(queryset)
            serializer = self.get_serializer(page if page is not None else queryset, many=True)
            logger.info(f"[{tenant.schema_name}] Retrieved {queryset.count()} user activity records")
            return self.get_paginated_response(serializer.data) if page is not None else Response({
                'detail': f'Retrieved {queryset.count()} user activity record(s)',
                'data': serializer.data
            })
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error listing user activities: {str(e)}", exc_info=True)
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def recent_events(self, request):
        tenant = self.request.tenant
        try:
            with tenant_context(tenant):
                security_types = ['user_login', 'user_logout', 'password_reset_initiated', 'user_impersonated', 'blocked_ip_added', 'blocked_ip_removed', 'vulnerability_resolved']
                queryset = UserActivity.objects.filter(
                    user__tenant=tenant,
                    activity_type__in=security_types
                ).select_related('user').order_by('-timestamp')[:50]
                serializer = self.get_serializer(queryset, many=True)
                logger.info(f"[{tenant.schema_name}] Retrieved recent security events")
                return Response({
                    'detail': f'Retrieved {queryset.count()} recent security events',
                    'data': serializer.data
                })
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error retrieving recent security events: {str(e)}", exc_info=True)
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class TenantUsersListView(APIView):
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



class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tenant = request.tenant
        with tenant_context(tenant):
            serializer = UserSerializer(request.user)
            return Response(serializer.data)


class UserSessionViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

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
