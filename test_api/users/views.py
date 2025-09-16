import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
import numpy as np
from django.http import HttpResponse
import requests
from django.core.exceptions import ValidationError
from django.db import transaction, connection
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import serializers, viewsets, generics, status
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django_tenants.utils import tenant_context
from .models import (
    FailedLogin, BlockedIP, VulnerabilityAlert,
    ComplianceReport, CustomUser, UserActivity,
)
from .serializers import (
    FailedLoginSerializer, BlockedIPSerializer, VulnerabilityAlertSerializer, ComplianceReportSerializer,
    UserSerializer, AdminUserCreateSerializer, UserActivitySerializer,
)
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser


import logging
import jwt
from django.conf import settings
from django.db import transaction
from rest_framework import viewsets, status, serializers, generics
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from .models import CustomUser
from .serializers import (CustomUserSerializer, PasswordResetConfirmSerializer,
    AdminUserCreateSerializer, PasswordResetRequestSerializer)
from core.models import Tenant, TenantConfig
import uuid
from datetime import timedelta
from django.core.mail import EmailMessage
from django.utils import timezone
from rest_framework.permissions import AllowAny
from .models import CustomUser, PasswordResetToken
from django.urls import reverse
logger = logging.getLogger('users')

logger = logging.getLogger('users')

class TenantBaseView(generics.GenericAPIView):
    """Base view to handle tenant schema setting and logging."""
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        tenant = request.tenant
        if not tenant:
            logger.error("No tenant associated with the request")
            raise generics.ValidationError("Tenant not found.")
        connection.set_schema(tenant.schema_name)
        logger.debug(f"[{tenant.schema_name}] Schema set for request")

class CustomPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response({
            'links': {
                'next': self.get_next_link(),
                'previous': self.get_previous_link()
            },
            'count': self.page.paginator.count,
            'page_size': self.get_page_size(self.request),
            'results': data
        })

class SocialLoginCallbackView(TenantBaseView, APIView):
    """Handle social login callback and issue JWT tokens."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tenant = request.tenant
        user = request.user
        try:
            with tenant_context(tenant):
                social_account = SocialAccount.objects.get(user=user)
                refresh = RefreshToken.for_user(user)
                logger.info(f"[{tenant.schema_name}] Social login successful for user {user.email}")
                return Response({
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                    'tenant_id': tenant.id,
                    'tenant_schema': tenant.schema_name,
                })
        except SocialAccount.DoesNotExist:
            logger.warning(f"[{tenant.schema_name}] No social account found for user {user.email}")
            return Response({"detail": "Social account not found"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error in social login callback: {str(e)}", exc_info=True)
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



# [Previous imports and other views remain unchanged]

class RegisterView(TenantBaseView, generics.CreateAPIView):
    """Register a new user in the tenant's schema."""
    serializer_class = UserSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        tenant = request.tenant
        if not tenant:
            logger.error("No tenant associated with the request")
            return Response({"detail": "Tenant not found"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data=request.data, context={'request': request})
        try:
            serializer.is_valid(raise_exception=True)
        except serializers.ValidationError as e:
            logger.error(f"[{tenant.schema_name}] User registration validation failed: {e}, data: {request.data}")
            return Response(
                {"detail": "Validation failed", "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            with tenant_context(tenant), transaction.atomic():
                validated_data = serializer.validated_data
                validated_data['tenant'] = tenant  # Ensure tenant is set
                logger.debug(f"[{tenant.schema_name}] Creating user with data: {validated_data}")
                user = serializer.save()
                user.sync_group_memberships()  # Sync user with system groups
                UserActivity.objects.create(
                    user=user,
                    activity_type='user_registered',
                    details=f'User "{user.email}" registered',
                    status='success'
                )
                # Verify password hashing
                logger.debug(f"[{tenant.schema_name}] User {user.email} created with hashed password: {user.password}")
                return Response({
                    'detail': 'User created successfully',
                    'data': serializer.data
                }, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error registering user: {str(e)}, data: {request.data}", exc_info=True)
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        


class UserViewSet(TenantBaseView, viewsets.ModelViewSet):
    """Manage users in the tenant's schema with filtering and statistics."""
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]  # Add parsers
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, SearchFilter]
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
                    queryset = queryset.filter(signup_date__gte=datetime.fromisoformat(date_from))
                except ValueError:
                    logger.warning(f"[{tenant.schema_name}] Invalid date_from format: {date_from}")
                    raise serializers.ValidationError("Invalid date_from format")
            if date_to:
                try:
                    queryset = queryset.filter(signup_date__lte=datetime.fromisoformat(date_to))
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
        print("request.data", request.data)
        serializer = self.get_serializer(user, data=request.data, partial=kwargs.get('partial', False))
        try:
            serializer.is_valid(raise_exception=True)
        except serializers.ValidationError as e:
            print("[SERIALIZER ERROR]", serializer.errors)  # Print errors to console
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
        try:
            with tenant_context(tenant):
                user = get_object_or_404(CustomUser, pk=pk, tenant=tenant, is_deleted=False)
                if user.is_locked:
                    logger.warning(f"[{tenant.schema_name}] User {user.email} already locked")
                    return Response({"detail": "User is already locked"}, status=status.HTTP_400_BAD_REQUEST)
                user.lock_account(reason=f"Account locked by {request.user.email}")
                logger.info(f"[{tenant.schema_name}] User {user.email} locked by {request.user.email}")
                return Response({"detail": f"User {user.email} locked successfully"})
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error locking user with pk {pk}: {str(e)}", exc_info=True)
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def unlock(self, request, pk=None):
        tenant = request.tenant
        if not (request.user.is_superuser or request.user.role == 'admin'):
            logger.warning(f"[{tenant.schema_name}] Non-admin user {request.user.email} attempted to unlock user")
            return Response({"detail": "Only admins or superusers can unlock accounts"}, status=status.HTTP_403_FORBIDDEN)
        try:
            with tenant_context(tenant):
                user = get_object_or_404(CustomUser, pk=pk, tenant=tenant, is_deleted=False)
                if not user.is_locked:
                    logger.warning(f"[{tenant.schema_name}] User {user.email} already unlocked")
                    return Response({"detail": "User is already unlocked"}, status=status.HTTP_400_BAD_REQUEST)
                user.unlock_account(reason=f"Account unlocked by {request.user.email}")
                logger.info(f"[{tenant.schema_name}] User {user.email} unlocked by {request.user.email}")
                return Response({"detail": f"User {user.email} unlocked successfully"})
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error unlocking user with pk {pk}: {str(e)}", exc_info=True)
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def reset_password(self, request, pk=None):
        tenant = request.tenant
        if not (request.user.is_superuser or request.user.role == 'admin'):
            logger.warning(f"[{tenant.schema_name}] Non-admin user {request.user.email} attempted to reset password")
            return Response({"detail": "Only admins or superusers can reset passwords"}, status=status.HTTP_403_FORBIDDEN)
        try:
            with tenant_context(tenant):
                user = get_object_or_404(CustomUser, pk=pk, tenant=tenant, is_deleted=False)
                from django.contrib.auth.tokens import default_token_generator
                from django.utils.http import urlsafe_base64_encode
                from django.utils.encoding import force_bytes
                from django.core.mail import send_mail
                token = default_token_generator.make_token(user)
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                reset_link = f"{request.scheme}://{request.get_host()}/reset-password/{uid}/{token}/"
                print(reset_link)
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
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error resetting password for user with pk {pk}: {str(e)}", exc_info=True)
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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

    @action(detail=False, methods=['get'])
    def role_stats(self, request):
        tenant = request.tenant
        try:
            with tenant_context(tenant):
                roles = CustomUser.objects.filter(tenant=tenant, is_deleted=False).values('role').annotate(
                    total=Count('id'),
                    active=Count('id', filter=Q(status='active')),
                    pending=Count('id', filter=Q(status='pending')),
                    suspended=Count('id', filter=Q(status='suspended')),
                    locked=Count('id', filter=Q(is_locked=True))
                )
                thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
                role_info = {
                    'admin': {'description': 'Full system access', 'permissions': 'Can manage all users, modules, and system settings'},
                    'hr': {'description': 'Manages human resources tasks', 'permissions': 'Can manage staff, job roles, and HR-related modules'},
                    'carer': {'description': 'Provides care services', 'permissions': 'Can access client data and care-related modules'},
                    'client': {'description': 'Receives care services', 'permissions': 'Can view personal care plans and communicate with carers'},
                    'family': {'description': 'Family members of clients', 'permissions': 'Can view client updates and communicate with carers'},
                    'auditor': {'description': 'Audits system activities', 'permissions': 'Can view audit logs and compliance reports'},
                    'tutor': {'description': 'Provides training', 'permissions': 'Can manage training modules and learner progress'},
                    'assessor': {'description': 'Assesses training outcomes', 'permissions': 'Can evaluate assessments and provide feedback'},
                    'iqa': {'description': 'Internal Quality Assurer', 'permissions': 'Can review assessment quality and compliance'},
                    'eqa': {'description': 'External Quality Assurer', 'permissions': 'Can perform external quality checks and audits'}
                }
                result = [
                    {
                        'role': role['role'],
                        'total': role['total'],
                        'active': role['active'],
                        'pending': role['pending'],
                        'suspended': role['suspended'],
                        'locked': role['locked'],
                        'last_30_days': CustomUser.objects.filter(
                            tenant=tenant, is_deleted=False, role=role['role'], signup_date__gte=thirty_days_ago
                        ).count(),
                        'description': role_info.get(role['role'], {}).get('description', ''),
                        'permissions': role_info.get(role['role'], {}).get('permissions', '')
                    } for role in roles
                ]
                logger.info(f"[{tenant.schema_name}] Role stats retrieved")
                return Response(result)
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error retrieving role stats: {str(e)}", exc_info=True)
            return Response({"detail": "Error retrieving role stats"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def bulk_upload(self, request):
        if not request.user.is_authenticated or not (request.user.is_staff or request.user.is_superuser):
            logger.warning(f"[{request.tenant.schema_name}] Non-admin user {request.user.email} attempted bulk upload")
            return Response({"detail": "Only admin users can perform bulk uploads"}, status=status.HTTP_403_FORBIDDEN)

        file = request.FILES.get('file')
        if not file:
            logger.error(f"[{request.tenant.schema_name}] No file provided for bulk upload")
            return Response({"detail": "No file provided"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if not file.name.endswith('.csv'):
                logger.error(f"[{request.tenant.schema_name}] Unsupported file format: {file.name}")
                return Response({"detail": "Unsupported file format. Use CSV."}, status=status.HTTP_400_BAD_REQUEST)

            df = pd.read_csv(file)

            required_columns = ['firstName', 'lastName', 'email', 'password', 'role']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                logger.error(f"[{request.tenant.schema_name}] Missing required columns: {missing_columns}")
                return Response({
                    "detail": f"Missing required columns: {', '.join(missing_columns)}",
                    "required_columns": required_columns,
                    "optional_columns": ['phone', 'title', 'bio', 'status']
                }, status=status.HTTP_400_BAD_REQUEST)

            created_users = []
            errors = []
            created_count = 0

            valid_statuses = ['active', 'pending', 'suspended']

            with transaction.atomic():
                for index, row in df.iterrows():
                    try:
                        row = row.replace({pd.NA: None, np.nan: None, pd.NaT: None})

                        user_status = row.get('status', 'pending')
                        if user_status not in valid_statuses:
                            user_status = 'pending'
                            logger.warning(f"[{request.tenant.schema_name}] Invalid status in row {index + 2}: {row.get('status')}. Using default 'pending'.")

                        user_data = {
                            'first_name': row['firstName'],
                            'last_name': row['lastName'],
                            'email': row['email'],
                            'password': row['password'],
                            'role': row['role'],
                            'phone': row.get('phone'),
                            'title': row.get('title'),
                            'bio': row.get('bio'),
                            'status': user_status,
                            'tenant': request.tenant,
                            'is_locked': False
                        }

                        for field in ['first_name', 'last_name', 'email', 'password', 'role']:
                            if not user_data[field]:
                                raise ValidationError(f"Missing required field: {field}")

                        if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', user_data['email']):
                            raise ValidationError(f"Invalid email format: {user_data['email']}")

                        valid_roles = [r[0] for r in CustomUser.ROLES]
                        if user_data['role'] not in valid_roles:
                            raise ValidationError(f"Invalid role: {user_data['role']}. Must be one of {valid_roles}")

                        if not user_data['status']:
                            user_data['status'] = 'pending'
                            logger.warning(f"[{request.tenant.schema_name}] Status missing in row {index + 2}. Using default 'pending'.")

                        if CustomUser.objects.filter(email=user_data['email'], tenant=request.tenant, is_deleted=False).exists():
                            raise ValidationError(f"Email {user_data['email']} already exists")

                        user = CustomUser.objects.create_user(**user_data)
                        created_users.append({
                            'id': user.id,
                            'email': user.email,
                            'name': user.get_full_name(),
                            'role': user.role,
                            'status': user.status,
                            'is_locked': user.is_locked
                        })
                        created_count += 1
                        logger.info(f"[{request.tenant.schema_name}] Created user: {user.email}")
                    except Exception as e:
                        logger.error(f"[{request.tenant.schema_name}] Error in row {index + 2}: {str(e)}")
                        errors.append({
                            'row': index + 2,
                            'error': str(e),
                            'data': row.to_dict()
                        })

                if errors:
                    logger.error(f"[{request.tenant.schema_name}] Bulk upload failed with {len(errors)} errors")
                    return Response({
                        'detail': f"Failed to create {len(errors)} user(s)",
                        'created_count': created_count,
                        'created_users': created_users,
                        'error_count': len(errors),
                        'errors': errors,
                        'required_columns': required_columns,
                        'optional_columns': ['phone', 'title', 'bio', 'status']
                    }, status=status.HTTP_400_BAD_REQUEST)

                logger.info(f"[{request.tenant.schema_name}] Successfully created {created_count} users")
                return Response({
                    'detail': f"Created {created_count} users successfully",
                    'created_count': created_count,
                    'created_users': created_users,
                    'error_count': 0,
                    'errors': [],
                    'required_columns': required_columns,
                    'optional_columns': ['phone', 'title', 'bio', 'status']
                }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"[{request.tenant.schema_name}] Bulk upload failed: {str(e)}", exc_info=True)
            return Response({"detail": f"Failed to process file: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def impersonate(self, request, pk=None):
        tenant = request.tenant
        if not request.user.is_superuser:
            logger.warning(f"[{tenant.schema_name}] Non-superuser {request.user.email} attempted to impersonate")
            return Response({"detail": "Only superusers can impersonate"}, status=status.HTTP_403_FORBIDDEN)
        try:
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
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error impersonating user with pk {pk}: {str(e)}", exc_info=True)
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def change_password(self, request, pk=None):
        """Allow a user to change their password by providing old and new password. Returns detailed errors on failure."""
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
            # Return all validation errors
            print("[SERIALIZER ERROR]", serializer.errors)  # Print errors to console
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






class UserProfileUpdateView(TenantBaseView, generics.GenericAPIView):
    """Update the authenticated user's profile."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        tenant = request.tenant
        user = request.user
        serializer = UserSerializer(user, data=request.data, partial=True, context={'request': request})
        try:
            serializer.is_valid(raise_exception=True)
        except serializers.ValidationError as e:
            logger.error(f"[{tenant.schema_name}] Profile update validation failed for user {user.email}: {str(e)}")
            raise
        try:
            with tenant_context(tenant), transaction.atomic():
                updated_fields = {k: v for k, v in serializer.validated_data.items() if k in [
                    'first_name', 'last_name', 'phone', 'birth_date', 'profile_picture',
                    'bio', 'facebook_link', 'twitter_link', 'linkedin_link', 'title'
                ]}
                user.update_profile(updated_fields)
                UserActivity.objects.create(
                    user=user,
                    activity_type='profile_updated',
                    details=f'User "{user.email}" updated profile',
                    status='success'
                )
                logger.info(f"[{tenant.schema_name}] Profile updated for user {user.email}")
                return Response({
                    'detail': 'Profile updated successfully',
                    'data': UserSerializer(user, context={'request': request}).data
                })
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error updating profile for user {user.email}: {str(e)}", exc_info=True)
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class UserAccountSuspendView(TenantBaseView, generics.GenericAPIView):
    """Suspend a user account in the tenant's schema."""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request, pk):
        tenant = request.tenant
        try:
            with tenant_context(tenant):
                user = get_object_or_404(CustomUser, pk=pk, tenant=tenant, is_deleted=False)
                if user.status == 'suspended':
                    logger.warning(f"[{tenant.schema_name}] User {user.email} already suspended")
                    return Response({"detail": "User is already suspended"}, status=status.HTTP_400_BAD_REQUEST)
                with transaction.atomic():
                    user.suspend_account(reason=f"Suspended by {request.user.email}")
                    logger.info(f"[{tenant.schema_name}] User {user.email} suspended")
                    return Response({"detail": f"User {user.email} suspended successfully"})
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error suspending user with pk {pk}: {str(e)}", exc_info=True)
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class UserAccountActivateView(TenantBaseView, generics.GenericAPIView):
    """Activate a user account in the tenant's schema."""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request, pk):
        tenant = request.tenant
        try:
            with tenant_context(tenant):
                user = get_object_or_404(CustomUser, pk=pk, tenant=tenant, is_deleted=False)
                if user.status == 'active':
                    logger.warning(f"[{tenant.schema_name}] User {user.email} already active")
                    return Response({"detail": "User is already active"}, status=status.HTTP_400_BAD_REQUEST)
                with transaction.atomic():
                    user.activate_account()
                    logger.info(f"[{tenant.schema_name}] User {user.email} activated")
                    return Response({"detail": f"User {user.email} activated successfully"})
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error activating user with pk {pk}: {str(e)}", exc_info=True)
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class UserAccountBulkDeleteView(TenantBaseView, generics.GenericAPIView):
    """Bulk soft-delete users in the tenant's schema."""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request):
        tenant = request.tenant
        ids = request.data.get('ids', [])
        if not isinstance(ids, list):
            logger.warning(f"[{tenant.schema_name}] Invalid input for bulk delete: ids must be a list")
            return Response({"detail": "ids must be a list"}, status=status.HTTP_400_BAD_REQUEST)
        if not ids:
            logger.warning(f"[{tenant.schema_name}] No user IDs provided for bulk delete")
            return Response({"detail": "No user IDs provided"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            with tenant_context(tenant), transaction.atomic():
                users = CustomUser.objects.filter(id__in=ids, tenant=tenant, is_deleted=False)
                if not users.exists():
                    logger.warning(f"[{tenant.schema_name}] No active users found for IDs {ids}")
                    return Response({"detail": "No active users found"}, status=status.HTTP_404_NOT_FOUND)
                deleted_count = 0
                for user in users:
                    user.delete_account(reason=f"Bulk deleted by {request.user.email}")
                    deleted_count += 1
                logger.info(f"[{tenant.schema_name}] Soft-deleted {deleted_count} users")
                return Response({"detail": f"Soft-deleted {deleted_count} user(s)"})
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error during bulk delete of users: {str(e)}", exc_info=True)
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



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




class ComplianceReportViewSet(TenantBaseView, viewsets.ModelViewSet):  # Changed to ModelViewSet
    serializer_class = ComplianceReportSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['type', 'status']

    def get_queryset(self):
        tenant = self.request.tenant
        with tenant_context(tenant):
            return ComplianceReport.objects.filter(tenant=tenant).order_by('type')

    @action(detail=True, methods=['get'], url_path='generate')
    def generate_report(self, request, pk=None):
        tenant = request.tenant
        try:
            with tenant_context(tenant):
                report = get_object_or_404(ComplianceReport, pk=pk, tenant=tenant)
                buffer = BytesIO()
                doc = SimpleDocTemplate(buffer, pagesize=letter)
                styles = getSampleStyleSheet()
                elements = []

                elements.append(Paragraph(f"Compliance Report: {report.type}", styles['Title']))
                elements.append(Spacer(1, 12))
                elements.append(Paragraph(f"Status: {report.status}", styles['Normal']))
                elements.append(Spacer(1, 12))
                elements.append(Paragraph(f"Last Audit: {report.lastAudit or 'N/A'}", styles['Normal']))
                elements.append(Spacer(1, 12))
                elements.append(Paragraph(f"Next Audit: {report.nextAudit or 'N/A'}", styles['Normal']))
                elements.append(Spacer(1, 12))
                elements.append(Paragraph(f"Details: {report.details or 'No details available'}", styles['Normal']))

                doc.build(elements)
                buffer.seek(0)
                logger.info(f"[{tenant.schema_name}] Generated compliance report for {report.type}")
                return HttpResponse(buffer, content_type='application/pdf', headers={'Content-Disposition': f'attachment; filename=compliance_report_{pk}.pdf'})
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error generating report for pk {pk}: {str(e)}", exc_info=True)
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'], url_path='schedule')
    def schedule_audit(self, request, pk=None):
        tenant = request.tenant
        audit_date = request.data.get('audit_date')
        if not audit_date:
            logger.warning(f"[{tenant.schema_name}] No audit date provided for schedule")
            return Response({"detail": "Audit date is required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            with tenant_context(tenant):
                report = get_object_or_404(ComplianceReport, pk=pk, tenant=tenant)
                from datetime import datetime
                try:
                    parsed_date = datetime.strptime(audit_date, '%Y-%m-%d').date()
                except ValueError:
                    logger.warning(f"[{tenant.schema_name}] Invalid audit date format: {audit_date}")
                    return Response({"detail": "Invalid date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)
                report.nextAudit = parsed_date
                report.save()
                UserActivity.objects.create(
                    user=self.request.user,
                    activity_type='audit_scheduled',
                    details=f"Audit scheduled for {report.type} on {audit_date} by {self.request.user.email}",
                    status='success'
                )
                logger.info(f"[{tenant.schema_name}] Audit scheduled for {report.type} on {audit_date}")
                return Response({"detail": f"Audit scheduled for {audit_date}"})
        except Exception as e:
            logger.error(f"[{tenant.schema_name}] Error scheduling audit for pk {pk}: {str(e)}", exc_info=True)
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




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

                    # print("token")
                    # print(token)
                    # print("token")
                    # Get email template
                    try:
                        config = TenantConfig.objects.get(tenant=tenant)
                        email_template = config.email_templates.get('passwordReset', {})
                        template_content = email_template.get('content', '')
                        is_auto_sent = email_template.get('is_auto_sent', True)

                        # print("template_content")
                        # print(template_content)
                        # print("template_content")


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
                    #reset_link = f"{settings.WEB_PAGE_URL}{reverse('password_reset_confirm')}?token={token}"

                    reset_link = f"{settings.WEB_PAGE_URL}{reverse('password_reset_confirm')}?token={token}&email={email}"

                    placeholders = {
                        '[User Name]': user.get_full_name() or user.username,
                        '[Company]': tenant.name,
                        '[Reset Link]': reset_link,
                        '[Your Name]': tenant.name,
                        '[your.email@proliance.com]': tenant.default_from_email,
                    }

                    # print(placeholders)

                    email_body = template_content
                    for placeholder, value in placeholders.items():
                        email_body = email_body.replace(placeholder, str(value))

                    # Send email
                    if is_auto_sent or not is_auto_sent:
                        try:
                            email_connection = configure_email_backend(tenant)
                            # print(tenant.email_host)
                            # print(tenant.email_port)
                            # print(tenant.email_use_ssl)
                            # print(tenant.email_host_user)
                            # print(tenant.email_host_password)
                            # print(email_body)
                            # logger.info(f"Email configuration for tenant {tenant.schema_name} user {email}: "
                            #             f"host={tenant.email_host}, "
                            #             f"port={tenant.email_port}, "
                            #             f"use_ssl={tenant.email_use_ssl}, "
                            #             f"host_user={tenant.email_host_user}, "
                            #             f"host_password={'*' * len(tenant.email_host_password) if tenant.email_host_password else None}, "
                            #             f"default_from_email={tenant.default_from_email}")

                            email_subject = f"Password Reset Request for {email}"
                            # print(f"Password reset email sent to {user.email} for tenant {tenant.schema_name}")
                            # print(f"{token}")
                            # print(email_connection)
                            # print(email_body)
                            # print(reset_link)
                            email = EmailMessage(
                                subject=email_subject,
                                body=email_body,
                                from_email=tenant.default_from_email,
                                to=[user.email],
                                connection=email_connection,
                            )
                            # email.content_subtype = 'html'
                            email.send(fail_silently=False)
                            #logger.info(f"Password reset email sent to {user.email} for tenant {tenant.schema_name}")
                            # print(f"Password reset email sent to {user.email} for tenant {tenant.schema_name}")
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

# New view for listing all users in a tenant
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
            # Check permissions: Only admins, superusers, or team managers can list all tenant users
            if not (request.user.is_superuser or request.user.role == 'admin' or request.user.role == 'team_manager'):
                logger.warning(f"Unauthorized tenant users list attempt by user {request.user.email}")
                return Response(
                    {"status": "error", "message": "Only admins or team managers can list all tenant users"},
                    status=status.HTTP_403_FORBIDDEN
                )

            try:
                users = CustomUser.objects.filter(tenant=tenant)
                serializer = CustomUserSerializer(users, many=True, context={'request': request})
                logger.info(f"Retrieved {users.count()} users for tenant {tenant.schema_name}")
                return Response(
                    {
                        "status": "success",
                        "message": f"Retrieved {users.count()} users for tenant {tenant.schema_name}",
                        "data": serializer.data
                    },
                    status=status.HTTP_200_OK
                )
            except Exception as e:
                logger.error(f"Error listing users for tenant {tenant.schema_name}: {str(e)}")
                return Response(
                    {"status": "error", "message": str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )


class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tenant = request.tenant
        with tenant_context(tenant):
            serializer = UserSerializer(request.user)
            return Response(serializer.data)



class ProfilePictureView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        tenant = request.tenant
        with tenant_context(tenant):
            user = CustomUser.objects.get(pk=pk, id=request.user.id)
            if 'profile_picture' in request.FILES:
                user.profile_picture = request.FILES['profile_picture']
                user.save()
                return Response({'status': 'Profile picture updated'}, status=status.HTTP_200_OK)
            return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)