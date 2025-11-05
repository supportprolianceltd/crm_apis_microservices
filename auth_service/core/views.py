# core/views.py
import jwt
import logging
from django_tenants.utils import get_public_schema_name
from django.conf import settings
from django.db import transaction, connection
from django_tenants.utils import tenant_context, schema_context
from cryptography.hazmat.primitives import serialization
from core.utils.kafka_producer import publish_event
from core.utils.notifications import send_notification_event
from django.db.models import Count
from django.utils import timezone
from django.db.models import Q
from django.core.exceptions import PermissionDenied
from rest_framework import viewsets, status, serializers, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.decorators import action
from datetime import timedelta
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from users.models import RSAKeyPair
from core.models import (
    Tenant, Domain, Module, TenantConfig, Branch, GlobalActivity
)
from .serializers import (
    TenantSerializer, ModuleSerializer, TenantConfigSerializer, 
    BranchSerializer, PublicTenantSerializer, GlobalActivitySerializer
)
from django.db.models import Prefetch

logger = logging.getLogger(__name__)

class CustomPagination(PageNumberPagination):
    page_size = 20

    def get_next_link(self):
        if not self.page.has_next():
            return None
        gateway_url = getattr(settings, 'GATEWAY_URL', None)
        if not gateway_url:
            return super().get_next_link()

        request = self.request
        path = request.path
        query_params = request.query_params.copy()
        query_params['page'] = self.page.next_page_number()
        query_string = urlencode(query_params, doseq=True)

        parsed_gateway = urlparse(gateway_url)
        full_url = f"{parsed_gateway.scheme}://{parsed_gateway.netloc}{path}?{query_string}"
        return full_url

    def get_previous_link(self):
        if not self.page.has_previous():
            return None
        gateway_url = getattr(settings, 'GATEWAY_URL', None)
        if not gateway_url:
            return super().get_previous_link()

        request = self.request
        path = request.path
        query_params = request.query_params.copy()
        query_params['page'] = self.page.previous_page_number()
        query_string = urlencode(query_params, doseq=True)

        parsed_gateway = urlparse(gateway_url)
        full_url = f"{parsed_gateway.scheme}://{parsed_gateway.netloc}{path}?{query_string}"
        return full_url

    def get_paginated_response(self, data):
        response = super().get_paginated_response(data)
        gateway_url = getattr(settings, 'GATEWAY_URL', None)
        if gateway_url:
            response['next'] = self.get_next_link()
            response['previous'] = self.get_previous_link()
        return response

class IsSuperUser(IsAuthenticated):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.is_superuser

class BranchListCreateView(generics.ListCreateAPIView):
    serializer_class = BranchSerializer
    permission_classes = [IsAuthenticated]

    def get_tenant(self, request):
        try:
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

    def get_queryset(self):
        tenant = self.get_tenant(self.request)
        connection.set_schema(tenant.schema_name)
        with connection.cursor() as cursor:
            cursor.execute("SHOW search_path;")
            search_path = cursor.fetchone()[0]
            logger.debug(f"Database search_path: {search_path}")
        with tenant_context(tenant):
            return Branch.objects.filter(tenant=tenant)

    def perform_create(self, serializer):
        tenant = self.get_tenant(self.request)
        try:
            with tenant_context(tenant):
                with transaction.atomic():
                    branch = serializer.save()
                    logger.info(f"Branch created: {branch.name} for tenant {tenant.schema_name}")
        except Exception as e:
            logger.error(f"Error creating branch for tenant {tenant.schema_name}: {str(e)}")
            raise serializers.ValidationError(f"Error creating branch: {str(e)}")

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.get_queryset()
            serializer = self.get_serializer(queryset, many=True)
            logger.info(f"Retrieved {queryset.count()} branches for tenant {request.user.tenant.schema_name}")
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error listing branches for tenant {request.user.tenant.schema_name}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class BranchDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = BranchSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'

    def get_tenant(self, request):
        try:
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

    def get_queryset(self):
        tenant = self.get_tenant(self.request)
        connection.set_schema(tenant.schema_name)
        with connection.cursor() as cursor:
            cursor.execute("SHOW search_path;")
            search_path = cursor.fetchone()[0]
            logger.debug(f"Database search_path: {search_path}")
        with tenant_context(tenant):
            return Branch.objects.filter(tenant=tenant)

    def perform_update(self, serializer):
        tenant = self.get_tenant(self.request)
        try:
            with tenant_context(tenant):
                with transaction.atomic():
                    branch = serializer.save()
                    logger.info(f"Branch updated: {branch.name} for tenant {tenant.schema_name}")
        except Exception as e:
            logger.error(f"Error updating branch for tenant {tenant.schema_name}: {str(e)}")
            raise serializers.ValidationError(f"Error updating branch: {str(e)}")

    def perform_destroy(self, instance):
        tenant = self.get_tenant(self.request)
        try:
            with tenant_context(tenant):
                with transaction.atomic():
                    instance.delete()
                    logger.info(f"Branch deleted: {instance.name} for tenant {tenant.schema_name}")
        except Exception as e:
            logger.error(f"Error deleting branch for tenant {tenant.schema_name}: {str(e)}")
            raise serializers.ValidationError(f"Error deleting branch: {str(e)}")

class ModuleListView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        tenant = request.user.tenant
        with tenant_context(tenant):
            modules = Module.objects.filter(is_active=True)
            serializer = ModuleSerializer(modules, many=True, context={'request': request})
            logger.info(f"Retrieved {modules.count()} modules for tenant {tenant.schema_name}")
            return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        tenant = request.user.tenant
        serializer = ModuleSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            try:
                with tenant_context(tenant):
                    with transaction.atomic():
                        module = serializer.save()
                        logger.info(f"Module created: {module.name} for tenant {tenant.schema_name}")
                        return Response(serializer.data, status=status.HTTP_201_CREATED)
            except Exception as e:
                logger.error(f"Error creating module for tenant {tenant.schema_name}: {str(e)}")
                return Response({
                    'status': 'error',
                    'message': str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        logger.error(f"Validation error for tenant {tenant.schema_name}: {serializer.errors}")
        return Response({
            'status': 'error',
            'message': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

class TenantConfigView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tenant = request.user.tenant
        with tenant_context(tenant):
            try:
                config = TenantConfig.objects.get(tenant=tenant)
                serializer = TenantConfigSerializer(config)
                logger.info(f"Fetched TenantConfig for tenant {tenant.schema_name}")
                return Response(serializer.data, status=status.HTTP_200_OK)
            except TenantConfig.DoesNotExist:
                default_templates = {
                    'interviewScheduling': {
                        'content': (
                            'Hello [Candidate Name],\n\n'
                            'We\'re pleased to invite you to an interview for the [Position] role at [Company].\n'
                            'Please let us know your availability so we can confirm a convenient time.\n\n'
                            'Best regards,\n[Your Name]'
                        ),
                        'is_auto_sent': False
                    },
                    'interviewRescheduling': {
                        'content': (
                            'Hello [Candidate Name],\n\n'
                            'Due to unforeseen circumstances, we need to reschedule your interview originally set for [Old Date/Time]. '
                            'Kindly share a few alternative slots that work for you.\n\n'
                            'Thanks for your understanding,\n[Your Name]'
                        ),
                        'is_auto_sent': False
                    },
                    'interviewRejection': {
                        'content': (
                            'Hello [Candidate Name],\n\n'
                            'Thank you for taking the time to interview. After careful consideration, '
                            'we have decided not to move forward.\n\n'
                            'Best wishes,\n[Your Name]'
                        ),
                        'is_auto_sent': False
                    },
                    'interviewAcceptance': {
                        'content': (
                            'Hello [Candidate Name],\n\n'
                            'Congratulations! We are moving you to the next stage. We\'ll follow up with next steps.\n\n'
                            'Looking forward,\n[Your Name]'
                        ),
                        'is_auto_sent': False
                    },
                    'jobRejection': {
                        'content': (
                            'Hello [Candidate Name],\n\n'
                            'Thank you for applying. Unfortunately, we\'ve chosen another candidate at this time.\n\n'
                            'Kind regards,\n[Your Name]'
                        ),
                        'is_auto_sent': False
                    },
                    'jobAcceptance': {
                        'content': (
                            'Hello [Candidate Name],\n\n'
                            'We\'re excited to offer you the [Position] role at [Company]! '
                            'Please find the offer letter attached.\n\n'
                            'Welcome aboard!\n[Your Name]'
                        ),
                        'is_auto_sent': False
                    }
                }
                try:
                    with transaction.atomic():
                        config = TenantConfig.objects.create(
                            tenant=tenant,
                            email_templates=default_templates
                        )
                        logger.info(f"Created TenantConfig for tenant {tenant.schema_name} with default email templates")
                        serializer = TenantConfigSerializer(config)
                        return Response(serializer.data, status=status.HTTP_201_CREATED)
                except Exception as e:
                    logger.error(f"Error creating TenantConfig for tenant {tenant.schema_name}: {str(e)}")
                    return Response(
                        {'status': 'error', 'message': 'Failed to create tenant configuration'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )

    def patch(self, request):
        tenant = request.user.tenant
        with tenant_context(tenant):
            try:
                config = TenantConfig.objects.get(tenant=tenant)
                current_templates = config.email_templates or {}
                incoming_templates = request.data.get('email_templates', {})
                updated_templates = { **current_templates, **incoming_templates }
                updated_data = { **request.data, 'email_templates': updated_templates }
                serializer = TenantConfigSerializer(config, data=updated_data, partial=True)
                if serializer.is_valid():
                    serializer.save()
                    logger.info(f"Tenant config updated for tenant {tenant.schema_name}")
                    return Response(serializer.data, status=status.HTTP_200_OK)
                logger.error(f"Validation error for tenant {tenant.schema_name}: {serializer.errors}")
                return Response({'status': 'error', 'message': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
            except TenantConfig.DoesNotExist:
                logger.error(f"Tenant config not found for tenant {tenant.schema_name}")
                return Response({'status': 'error', 'message': 'Tenant config not found'}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request):
        tenant = request.user.tenant
        with tenant_context(tenant):
            try:
                if TenantConfig.objects.filter(tenant=tenant).exists():
                    logger.warning(f"Tenant config already exists for tenant {tenant.schema_name}")
                    return Response({'status': 'error', 'message': 'Tenant config already exists'}, status=status.HTTP_400_BAD_REQUEST)
                serializer = TenantConfigSerializer(data=request.data)
                if serializer.is_valid():
                    serializer.save(tenant=tenant)
                    logger.info(f"Tenant config created for tenant {tenant.schema_name}")
                    return Response(serializer.data, status=status.HTTP_201_CREATED)
                logger.error(f"Validation error for tenant {tenant.schema_name}: {serializer.errors}")
                return Response({'status': 'error', 'message': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                logger.error(f"Error creating tenant config for tenant {tenant.schema_name}: {str(e)}")
                return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class TenantViewSet(viewsets.ModelViewSet):
    queryset = Tenant.objects.all()
    serializer_class = TenantSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        if self.action == 'list':
            return [IsSuperUser()]
        return [IsAuthenticated()]

    def get_object(self):
        unique_id = self.kwargs.get('pk')
        try:
            return Tenant.objects.get(unique_id=unique_id)
        except Tenant.DoesNotExist:
            raise serializers.ValidationError("Tenant not found with this unique ID.")

    def get_tenant(self, request):
        try:
            if hasattr(request.user, 'tenant') and request.user.tenant:
                logger.debug(f"Tenant from user: {request.user.tenant.schema_name}")
                return request.user.tenant
            auth_header = request.headers.get('Authorization', '')
            if not auth_header.startswith('Bearer '):
                logger.warning("No valid Bearer token provided")
                raise ValueError("Invalid token format")
            token = auth_header.split(' ')[1]
            decoded_token = jwt.decode(token, options={"verify_signature": False})
            tenant_id = decoded_token.get('tenant_id')
            schema_name = decoded_token.get('tenant_schema')
            if not tenant_id and not schema_name:
                logger.warning("No tenant_id or schema_name in token")
                raise ValueError("Tenant not specified in token")
            
            if tenant_id:
                tenant = Tenant.objects.get(id=tenant_id)
            else:
                tenant = Tenant.objects.get(schema_name=schema_name)
            
            keypair = RSAKeyPair.objects.filter(tenant=tenant, active=True).first()
            if not keypair:
                logger.error(f"No active RSA keypair found for tenant {tenant.schema_name}")
                raise serializers.ValidationError("No active keypair for tenant")
            public_key = serialization.load_pem_public_key(keypair.public_key_pem.encode())
            jwt.decode(token, public_key, algorithms=["RS256"])
            
            logger.debug(f"Tenant extracted from token: {tenant.schema_name}")
            return tenant
        except Tenant.DoesNotExist:
            logger.error("Tenant not found")
            raise serializers.ValidationError("Tenant not found")
        except jwt.InvalidTokenError:
            logger.error("Invalid JWT token")
            raise serializers.ValidationError("Invalid token")
        except Exception as e:
            logger.error(f"Error extracting tenant: {str(e)}")
            raise serializers.ValidationError(f"Error extracting tenant: {str(e)}")

    def get_queryset(self):
        if self.action == 'list':
            logger.debug("Returning all tenants for list action")
            return Tenant.objects.all()
        tenant = self.get_tenant(self.request)
        logger.debug(f"Filtering queryset for tenant: {tenant.schema_name}")
        connection.set_schema(tenant.schema_name)
        with connection.cursor() as cursor:
            cursor.execute("SHOW search_path;")
            search_path = cursor.fetchone()[0]
            logger.debug(f"Database search_path: {search_path}")
        return Tenant.objects.filter(id=tenant.id)

    def perform_create(self, serializer):
        original_schema = connection.schema_name
        try:
            connection.set_schema('public')
            with transaction.atomic():
                new_tenant = serializer.save()
                logger.info(f"Tenant created: {new_tenant.name} (schema: {new_tenant.schema_name})")
                
                # ✅ FIX: Log global activity for tenant creation
                GlobalActivity.log_platform_action(
                    action='tenant_created',
                    affected_tenant=new_tenant,
                    performed_by_id=str(self.request.user.id) if self.request.user.is_authenticated else None,
                    details={
                        'tenant_name': new_tenant.name,
                        'schema_name': new_tenant.schema_name,
                        'organizational_id': new_tenant.organizational_id
                    },
                    request=self.request
                )
                
                # Publish Kafka event with tenant details
                tenant_data = TenantSerializer(new_tenant).data
                publish_event(
                    settings.KAFKA_TOPIC_TENANT_EVENTS,
                    {
                        'event_type': 'tenant_created',
                        'tenant_id': str(new_tenant.unique_id),
                        'data': tenant_data
                    }
                )
                
                # Send notification to notification service
                notification_data = {
                    'externalId': str(new_tenant.unique_id),
                    'id': str(new_tenant.unique_id),
                    'name': new_tenant.name
                }
                send_notification_event(notification_data)
        except Exception as e:
            logger.error(f"Failed to create tenant: {str(e)}")
            raise serializers.ValidationError(f"Failed to create tenant: {str(e)}")
        finally:
            connection.set_schema(original_schema)

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.get_queryset()
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                logger.info(f"Listing paginated tenants: {[t['id'] for t in serializer.data]}")
                return self.get_paginated_response(serializer.data)
            serializer = self.get_serializer(queryset, many=True)
            logger.info(f"Listing all tenants: {[t['id'] for t in serializer.data]}")
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error listing tenants: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def retrieve(self, request, *args, **kwargs):
        tenant = self.get_tenant(request)
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        logger.info(f"Retrieving tenant: {instance.id} for tenant {tenant.schema_name}")
        return Response(serializer.data)

    def perform_destroy(self, instance):
        tenant = self.get_tenant(self.request)
        if instance.id != tenant.id:
            logger.error(f"Unauthorized delete attempt on tenant {instance.id} by tenant {tenant.id}")
            raise serializers.ValidationError("Not authorized to delete this tenant")
        
        # ✅ FIX: Log global activity for tenant deletion
        with schema_context('public'):
            GlobalActivity.log_platform_action(
                action='tenant_deleted',
                affected_tenant=instance,
                performed_by_id=str(self.request.user.id) if self.request.user.is_authenticated else None,
                details={
                    'tenant_name': instance.name,
                    'schema_name': instance.schema_name
                },
                request=self.request
            )
        
        with tenant_context(tenant):
            instance.delete()
        logger.info(f"Tenant deleted: {instance.name} for tenant {tenant.schema_name}")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        instance = self.get_object()
        tenant = self.get_tenant(self.request)
        if instance.id != tenant.id and not self.request.user.is_superuser:
            raise serializers.ValidationError("Not authorized to update this tenant")
        
        # ✅ FIX: Log global activity for tenant update
        with schema_context('public'):
            GlobalActivity.log_platform_action(
                action='tenant_updated',
                affected_tenant=instance,
                performed_by_id=str(self.request.user.id) if self.request.user.is_authenticated else None,
                details={
                    'tenant_name': instance.name,
                    'schema_name': instance.schema_name
                },
                request=self.request
            )
        
        with tenant_context(tenant):
            serializer.save()
        logger.info(f"Tenant updated: {instance.name} for tenant {tenant.schema_name}")

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        tenant = self.get_tenant(request)
        serializer = self.get_serializer(
            instance, 
            data=request.data, 
            partial=partial, 
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        with tenant_context(tenant):
            serializer.save()
        return Response(serializer.data)

    # NEW: Action to suspend a tenant
    @action(detail=True, methods=['post'], url_path='suspend')
    def suspend(self, request, pk=None):
        instance = self.get_object()
        if instance.status == 'suspended':
            return Response({'detail': 'Tenant is already suspended.'}, status=status.HTTP_400_BAD_REQUEST)
        
        reason = request.data.get('reason', 'Manual suspension')
        try:
            with schema_context('public'):  # Log in shared schema
                GlobalActivity.log_platform_action(
                    action='tenant_suspended',
                    affected_tenant=instance,
                    performed_by_id=str(request.user.id),
                    details={'reason': reason},
                    request=request
                )
            
            with tenant_context(instance):
                instance.status = 'suspended'
                instance.save(update_fields=['status'])
            
            logger.info(f"Tenant suspended: {instance.name} (ID: {pk}) by {request.user.email}")
            return Response({
                'detail': f'Tenant "{instance.name}" suspended successfully.',
                'status': instance.status
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error suspending tenant {pk}: {str(e)}")
            return Response({'detail': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # NEW: Action to activate a tenant
    @action(detail=True, methods=['post'], url_path='activate')
    def activate(self, request, pk=None):
        instance = self.get_object()
        if instance.status == 'active':
            return Response({'detail': 'Tenant is already active.'}, status=status.HTTP_400_BAD_REQUEST)
        
        reason = request.data.get('reason', 'Manual activation')
        try:
            with schema_context('public'):  # Log in shared schema
                GlobalActivity.log_platform_action(
                    action='tenant_activated',
                    affected_tenant=instance,
                    performed_by_id=str(request.user.id),
                    details={'reason': reason},
                    request=request
                )
            
            with tenant_context(instance):
                instance.status = 'active'
                instance.save(update_fields=['status'])
            
            logger.info(f"Tenant activated: {instance.name} (ID: {pk}) by {request.user.email}")
            return Response({
                'detail': f'Tenant "{instance.name}" activated successfully.',
                'status': instance.status
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error activating tenant {pk}: {str(e)}")
            return Response({'detail': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PublicTenantInfoView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, unique_id):
        try:
            tenant = Tenant.objects.get(unique_id=unique_id)
            serializer = PublicTenantSerializer(tenant)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Tenant.DoesNotExist:
            return Response({"detail": "Tenant not found."}, status=status.HTTP_404_NOT_FOUND)

class GlobalActivityViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Global activity logs accessible ONLY by superusers.
    Shows cross-tenant activities performed by platform admins.
    """
    queryset = GlobalActivity.objects.all()
    serializer_class = GlobalActivitySerializer
    permission_classes = [IsSuperUser]  # Changed from AllowAny to IsSuperUser
    pagination_class = CustomPagination
    
    def get_queryset(self):
        # Only superusers can access global logs
        if not self.request.user.is_superuser:
            raise PermissionDenied("Only platform superusers can view global activity logs.")
        
        queryset = GlobalActivity.objects.all().select_related('affected_tenant').order_by('-timestamp')
        
        # Apply filters
        queryset = self._apply_filters(queryset)
        return queryset
    
    def _apply_filters(self, queryset):
        params = self.request.query_params
        
        # Filter by tenant
        tenant_id = params.get('tenant_id')
        if tenant_id:
            queryset = queryset.filter(affected_tenant__unique_id=tenant_id)
        
        # Filter by action type
        actions = params.getlist('action') or params.getlist('action[]')
        if actions:
            queryset = queryset.filter(action__in=actions)
        
        # Date range
        date_from = params.get('date_from')
        date_to = params.get('date_to')
        if date_from:
            queryset = queryset.filter(timestamp__gte=date_from)
        if date_to:
            queryset = queryset.filter(timestamp__lte=date_to)
        
        # Search
        search = params.get('search')
        if search:
            queryset = queryset.filter(
                Q(action__icontains=search) |
                Q(affected_tenant__name__icontains=search) |
                Q(global_user__icontains=search) |
                Q(performed_by__icontains=search)
            )
        
        return queryset
    
    @action(detail=False, methods=['get'], url_path='dashboard-stats')
    def dashboard_stats(self, request):
        """Global dashboard statistics"""
        days = int(request.query_params.get('days', 30))
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        activities = GlobalActivity.objects.filter(
            timestamp__gte=start_date,
            timestamp__lte=end_date
        )
        
        # Total activities
        total_activities = activities.count()
        
        # Activities by tenant
        activities_by_tenant = activities.values(
            'affected_tenant__unique_id',
            'affected_tenant__name',
            'affected_tenant__schema_name'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # Activities by type
        activities_by_type = activities.values('action').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Most active admins
        active_admins = activities.values('global_user').annotate(
            activity_count=Count('id')
        ).order_by('-activity_count')[:10]
        
        return Response({
            'period': {'start_date': start_date, 'end_date': end_date, 'days': days},
            'summary': {
                'total_activities': total_activities,
                'affected_tenants_count': activities.values('affected_tenant').distinct().count(),
                'active_admins_count': activities.values('global_user').distinct().count(),
            },
            'activities_by_tenant': list(activities_by_tenant),
            'activities_by_type': list(activities_by_type),
            'active_admins': list(active_admins),
        })
    
    @action(detail=False, methods=['get'], url_path='tenant-activities')
    def tenant_activities(self, request):
        """Get all activities for a specific tenant"""
        tenant_id = request.query_params.get('tenant_id')
        if not tenant_id:
            return Response(
                {"error": "tenant_id parameter is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            tenant = Tenant.objects.get(unique_id=tenant_id)
        except Tenant.DoesNotExist:
            return Response(
                {"error": "Tenant not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        activities = GlobalActivity.objects.filter(affected_tenant=tenant).select_related('affected_tenant').order_by('-timestamp')
        
        page = self.paginate_queryset(activities)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(activities, many=True)
        return Response(serializer.data)