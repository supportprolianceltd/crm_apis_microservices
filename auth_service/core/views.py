# core/views.py
import jwt
import logging
from django_tenants.utils import get_public_schema_name
from django.conf import settings
from django.db import transaction, connection
from django_tenants.utils import tenant_context, schema_context
from cryptography.hazmat.primitives import serialization
from auth_service.utils.kafka_producer import publish_event
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
from .constants import (
    ErrorMessages, LogMessages, EventTypes, ResponseKeys, ResponseStatuses,
    ResponseMessages, EmailTemplates, DefaultTemplateKeys, JWTKeys, Headers,
    Algorithms, QueryParams, RequestDataKeys, KafkaEventKeys, NotificationKeys,
    StatusValues, SchemaNames, KafkaTopics, JWTDecodeOptions, DefaultReasons,
    OrderingFields, FieldNames, SQLQueries, AttributeNames, ActionNames,
    URLParams, LookupFields, ContextKeys, DetailsKeys, URLPaths
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
        query_params[QueryParams.PAGE] = self.page.next_page_number()
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
        query_params[QueryParams.PAGE] = self.page.previous_page_number()
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
            if hasattr(request.user, AttributeNames.TENANT) and getattr(request.user, AttributeNames.TENANT):
                logger.debug(LogMessages.TENANT_FROM_USER.format(request.user.tenant.schema_name))
                return request.user.tenant
            auth_header = request.headers.get(Headers.AUTHORIZATION, '')
            if not auth_header.startswith(Headers.BEARER_PREFIX):
                logger.warning(ErrorMessages.NO_VALID_BEARER_TOKEN)
                raise ValueError(ErrorMessages.INVALID_TOKEN_FORMAT)
            token = auth_header.split(' ')[1]
            decoded_token = jwt.decode(token, settings.SECRET_KEY, algorithms=[Algorithms.HS256])
            tenant_id = decoded_token.get(JWTKeys.TENANT_ID)
            schema_name = decoded_token.get(JWTKeys.TENANT_SCHEMA)
            if tenant_id:
                tenant = Tenant.objects.get(id=tenant_id)
                logger.debug(LogMessages.TENANT_EXTRACTED_BY_ID.format(tenant.schema_name))
                return tenant
            elif schema_name:
                tenant = Tenant.objects.get(schema_name=schema_name)
                logger.debug(LogMessages.TENANT_EXTRACTED_BY_SCHEMA.format(tenant.schema_name))
                return tenant
            else:
                logger.warning(LogMessages.NO_TENANT_IN_TOKEN)
                raise ValueError(ErrorMessages.TENANT_NOT_SPECIFIED_IN_TOKEN)
        except Tenant.DoesNotExist:
            logger.error(ErrorMessages.TENANT_NOT_FOUND)
            raise serializers.ValidationError(ErrorMessages.TENANT_NOT_FOUND)
        except jwt.InvalidTokenError:
            logger.error(ErrorMessages.INVALID_TOKEN)
            raise serializers.ValidationError(ErrorMessages.INVALID_TOKEN)
        except Exception as e:
            logger.error(ErrorMessages.ERROR_EXTRACTING_TENANT.format(str(e)))
            raise serializers.ValidationError(ErrorMessages.ERROR_EXTRACTING_TENANT.format(str(e)))

    def get_queryset(self):
        tenant = self.get_tenant(self.request)
        connection.set_schema(tenant.schema_name)
        with connection.cursor() as cursor:
            cursor.execute(SQLQueries.SHOW_SEARCH_PATH)
            search_path = cursor.fetchone()[0]
            logger.debug(LogMessages.DATABASE_SEARCH_PATH.format(search_path))
        with tenant_context(tenant):
            return Branch.objects.filter(tenant=tenant)

    def perform_create(self, serializer):
        tenant = self.get_tenant(self.request)
        try:
            with tenant_context(tenant):
                with transaction.atomic():
                    branch = serializer.save()
                    logger.info(LogMessages.BRANCH_CREATED.format(branch.name, tenant.schema_name))
        except Exception as e:
            logger.error(LogMessages.ERROR_CREATING_BRANCH.format(tenant.schema_name, str(e)))
            raise serializers.ValidationError(ErrorMessages.ERROR_CREATING_BRANCH.format(str(e)))

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.get_queryset()
            serializer = self.get_serializer(queryset, many=True)
            logger.info(LogMessages.BRANCHES_RETRIEVED.format(queryset.count(), getattr(request.user, AttributeNames.TENANT).schema_name))
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(LogMessages.ERROR_LISTING_BRANCHES.format(request.user.tenant.schema_name, str(e)))
            return Response({ResponseKeys.DETAIL: str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class BranchDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = BranchSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = LookupFields.ID

    def get_tenant(self, request):
        try:
            if hasattr(request.user, AttributeNames.TENANT) and getattr(request.user, AttributeNames.TENANT):
                logger.debug(LogMessages.TENANT_FROM_USER.format(request.user.tenant.schema_name))
                return request.user.tenant
            auth_header = request.headers.get(Headers.AUTHORIZATION, '')
            if not auth_header.startswith(Headers.BEARER_PREFIX):
                logger.warning(ErrorMessages.NO_VALID_BEARER_TOKEN)
                raise ValueError(ErrorMessages.INVALID_TOKEN_FORMAT)
            token = auth_header.split(' ')[1]
            decoded_token = jwt.decode(token, settings.SECRET_KEY, algorithms=[Algorithms.HS256])
            tenant_id = decoded_token.get(JWTKeys.TENANT_ID)
            schema_name = decoded_token.get(JWTKeys.TENANT_SCHEMA)
            if tenant_id:
                tenant = Tenant.objects.get(id=tenant_id)
                logger.debug(LogMessages.TENANT_EXTRACTED_BY_ID.format(tenant.schema_name))
                return tenant
            elif schema_name:
                tenant = Tenant.objects.get(schema_name=schema_name)
                logger.debug(LogMessages.TENANT_EXTRACTED_BY_SCHEMA.format(tenant.schema_name))
                return tenant
            else:
                logger.warning(LogMessages.NO_TENANT_IN_TOKEN)
                raise ValueError(ErrorMessages.TENANT_NOT_SPECIFIED_IN_TOKEN)
        except Tenant.DoesNotExist:
            logger.error(ErrorMessages.TENANT_NOT_FOUND)
            raise serializers.ValidationError(ErrorMessages.TENANT_NOT_FOUND)
        except jwt.InvalidTokenError:
            logger.error(ErrorMessages.INVALID_TOKEN)
            raise serializers.ValidationError(ErrorMessages.INVALID_TOKEN)
        except Exception as e:
            logger.error(ErrorMessages.ERROR_EXTRACTING_TENANT.format(str(e)))
            raise serializers.ValidationError(ErrorMessages.ERROR_EXTRACTING_TENANT.format(str(e)))

    def get_queryset(self):
        tenant = self.get_tenant(self.request)
        connection.set_schema(tenant.schema_name)
        with connection.cursor() as cursor:
            cursor.execute(SQLQueries.SHOW_SEARCH_PATH)
            search_path = cursor.fetchone()[0]
            logger.debug(LogMessages.DATABASE_SEARCH_PATH.format(search_path))
        with tenant_context(tenant):
            return Branch.objects.filter(tenant=tenant)

    def perform_update(self, serializer):
        tenant = self.get_tenant(self.request)
        try:
            with tenant_context(tenant):
                with transaction.atomic():
                    branch = serializer.save()
                    logger.info(LogMessages.BRANCH_UPDATED.format(branch.name, tenant.schema_name))
        except Exception as e:
            logger.error(LogMessages.ERROR_UPDATING_BRANCH.format(tenant.schema_name, str(e)))
            raise serializers.ValidationError(ErrorMessages.ERROR_UPDATING_BRANCH.format(str(e)))

    def perform_destroy(self, instance):
        tenant = self.get_tenant(self.request)
        try:
            with tenant_context(tenant):
                with transaction.atomic():
                    instance.delete()
                    logger.info(LogMessages.BRANCH_DELETED.format(instance.name, tenant.schema_name))
        except Exception as e:
            logger.error(LogMessages.ERROR_DELETING_BRANCH.format(tenant.schema_name, str(e)))
            raise serializers.ValidationError(ErrorMessages.ERROR_DELETING_BRANCH.format(str(e)))

class ModuleListView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        tenant = getattr(request.user, AttributeNames.TENANT)
        with tenant_context(tenant):
            modules = Module.objects.filter(is_active=True)
            serializer = ModuleSerializer(modules, many=True, context={ContextKeys.REQUEST: request})
            logger.info(LogMessages.MODULES_RETRIEVED.format(modules.count(), tenant.schema_name))
            return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        tenant = getattr(request.user, AttributeNames.TENANT)
        serializer = ModuleSerializer(data=request.data, context={ContextKeys.REQUEST: request})
        if serializer.is_valid():
            try:
                with tenant_context(tenant):
                    with transaction.atomic():
                        module = serializer.save()
                        logger.info(LogMessages.MODULE_CREATED.format(module.name, tenant.schema_name))
                        return Response(serializer.data, status=status.HTTP_201_CREATED)
            except Exception as e:
                logger.error(LogMessages.ERROR_CREATING_MODULE.format(tenant.schema_name, str(e)))
                return Response({
                    ResponseKeys.STATUS: ResponseStatuses.ERROR,
                    ResponseKeys.MESSAGE: str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        logger.error(LogMessages.VALIDATION_ERROR.format(tenant.schema_name, serializer.errors))
        return Response({
            ResponseKeys.STATUS: ResponseStatuses.ERROR,
            ResponseKeys.MESSAGE: serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

class TenantConfigView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tenant = getattr(request.user, AttributeNames.TENANT)
        with tenant_context(tenant):
            try:
                config = TenantConfig.objects.get(tenant=tenant)
                serializer = TenantConfigSerializer(config)
                logger.info(LogMessages.TENANT_CONFIG_FETCHED.format(tenant.schema_name))
                return Response(serializer.data, status=status.HTTP_200_OK)
            except TenantConfig.DoesNotExist:
                default_templates = {
                    DefaultTemplateKeys.INTERVIEW_SCHEDULING: {
                        'content': EmailTemplates.INTERVIEW_SCHEDULING,
                        'is_auto_sent': False
                    },
                    DefaultTemplateKeys.INTERVIEW_RESCHEDULING: {
                        'content': EmailTemplates.INTERVIEW_RESCHEDULING,
                        'is_auto_sent': False
                    },
                    DefaultTemplateKeys.INTERVIEW_REJECTION: {
                        'content': EmailTemplates.INTERVIEW_REJECTION,
                        'is_auto_sent': False
                    },
                    DefaultTemplateKeys.INTERVIEW_ACCEPTANCE: {
                        'content': EmailTemplates.INTERVIEW_ACCEPTANCE,
                        'is_auto_sent': False
                    },
                    DefaultTemplateKeys.JOB_REJECTION: {
                        'content': EmailTemplates.JOB_REJECTION,
                        'is_auto_sent': False
                    },
                    DefaultTemplateKeys.JOB_ACCEPTANCE: {
                        'content': EmailTemplates.JOB_ACCEPTANCE,
                        'is_auto_sent': False
                    }
                }
                try:
                    with transaction.atomic():
                        config = TenantConfig.objects.create(
                            tenant=tenant,
                            email_templates=default_templates
                        )
                        logger.info(LogMessages.TENANT_CONFIG_CREATED_DEFAULT.format(tenant.schema_name))
                        serializer = TenantConfigSerializer(config)
                        return Response(serializer.data, status=status.HTTP_201_CREATED)
                except Exception as e:
                    logger.error(LogMessages.ERROR_CREATING_TENANT_CONFIG.format(tenant.schema_name, str(e)))
                    return Response(
                        {ResponseKeys.STATUS: ResponseStatuses.ERROR, ResponseKeys.MESSAGE: ErrorMessages.FAILED_TO_CREATE_TENANT_CONFIG},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )

    def patch(self, request):
        tenant = getattr(request.user, AttributeNames.TENANT)
        with tenant_context(tenant):
            try:
                config = TenantConfig.objects.get(tenant=tenant)
                current_templates = config.email_templates or {}
                incoming_templates = request.data.get(RequestDataKeys.EMAIL_TEMPLATES, {})
                updated_templates = { **current_templates, **incoming_templates }
                updated_data = { **request.data, 'email_templates': updated_templates }
                serializer = TenantConfigSerializer(config, data=updated_data, partial=True)
                if serializer.is_valid():
                    serializer.save()
                    logger.info(LogMessages.TENANT_CONFIG_UPDATED.format(tenant.schema_name))
                    return Response(serializer.data, status=status.HTTP_200_OK)
                logger.error(LogMessages.VALIDATION_ERROR.format(tenant.schema_name, serializer.errors))
                return Response({ResponseKeys.STATUS: ResponseStatuses.ERROR, ResponseKeys.MESSAGE: serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
            except TenantConfig.DoesNotExist:
                logger.error(LogMessages.TENANT_CONFIG_NOT_FOUND_LOG.format(tenant.schema_name))
                return Response({ResponseKeys.STATUS: ResponseStatuses.ERROR, ResponseKeys.MESSAGE: ErrorMessages.TENANT_CONFIG_NOT_FOUND}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request):
        tenant = getattr(request.user, AttributeNames.TENANT)
        with tenant_context(tenant):
            try:
                if TenantConfig.objects.filter(tenant=tenant).exists():
                    logger.warning(LogMessages.TENANT_CONFIG_ALREADY_EXISTS_LOG.format(tenant.schema_name))
                    return Response({ResponseKeys.STATUS: ResponseStatuses.ERROR, ResponseKeys.MESSAGE: ErrorMessages.TENANT_CONFIG_ALREADY_EXISTS}, status=status.HTTP_400_BAD_REQUEST)
                serializer = TenantConfigSerializer(data=request.data)
                if serializer.is_valid():
                    serializer.save(tenant=tenant)
                    logger.info(LogMessages.TENANT_CONFIG_CREATED_LOG.format(tenant.schema_name))
                    return Response(serializer.data, status=status.HTTP_201_CREATED)
                logger.error(LogMessages.VALIDATION_ERROR.format(tenant.schema_name, serializer.errors))
                return Response({ResponseKeys.STATUS: ResponseStatuses.ERROR, ResponseKeys.MESSAGE: serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                logger.error(LogMessages.ERROR_CREATING_TENANT_CONFIG_GENERAL.format(tenant.schema_name, str(e)))
                return Response({ResponseKeys.STATUS: ResponseStatuses.ERROR, ResponseKeys.MESSAGE: str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class TenantViewSet(viewsets.ModelViewSet):
    queryset = Tenant.objects.all()
    serializer_class = TenantSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        if self.action == ActionNames.LIST:
            return [IsSuperUser()]
        return [IsAuthenticated()]

    def get_object(self):
        unique_id = self.kwargs.get(URLParams.PK)
        try:
            return Tenant.objects.get(unique_id=unique_id)
        except Tenant.DoesNotExist:
            raise serializers.ValidationError(ErrorMessages.TENANT_NOT_FOUND_BY_UNIQUE_ID)

    def get_tenant(self, request):
        try:
            if hasattr(request.user, AttributeNames.TENANT) and getattr(request.user, AttributeNames.TENANT):
                logger.debug(LogMessages.TENANT_FROM_USER.format(getattr(request.user, AttributeNames.TENANT).schema_name))
                return getattr(request.user, AttributeNames.TENANT)
            auth_header = request.headers.get(Headers.AUTHORIZATION, '')
            if not auth_header.startswith(Headers.BEARER_PREFIX):
                logger.warning(ErrorMessages.NO_VALID_BEARER_TOKEN)
                raise ValueError(ErrorMessages.INVALID_TOKEN_FORMAT)
            token = auth_header.split(' ')[1]
            decoded_token = jwt.decode(token, options={JWTDecodeOptions.VERIFY_SIGNATURE: False})
            tenant_id = decoded_token.get(JWTKeys.TENANT_ID)
            schema_name = decoded_token.get(JWTKeys.TENANT_SCHEMA)
            if not tenant_id and not schema_name:
                logger.warning(LogMessages.NO_TENANT_IN_TOKEN)
                raise ValueError(ErrorMessages.TENANT_NOT_SPECIFIED_IN_TOKEN)

            if tenant_id:
                tenant = Tenant.objects.get(id=tenant_id)
            else:
                tenant = Tenant.objects.get(schema_name=schema_name)

            keypair = RSAKeyPair.objects.filter(tenant=tenant, active=True).first()
            if not keypair:
                logger.error(ErrorMessages.NO_ACTIVE_KEYPAIR.format(tenant.schema_name))
                raise serializers.ValidationError(ErrorMessages.NO_ACTIVE_KEYPAIR.format(""))
            public_key = serialization.load_pem_public_key(keypair.public_key_pem.encode())
            jwt.decode(token, public_key, algorithms=[Algorithms.RS256])

            logger.debug(LogMessages.TENANT_EXTRACTED_FROM_TOKEN.format(tenant.schema_name))
            return tenant
        except Tenant.DoesNotExist:
            logger.error(ErrorMessages.TENANT_NOT_FOUND)
            raise serializers.ValidationError(ErrorMessages.TENANT_NOT_FOUND)
        except jwt.InvalidTokenError:
            logger.error(ErrorMessages.INVALID_TOKEN)
            raise serializers.ValidationError(ErrorMessages.INVALID_TOKEN)
        except Exception as e:
            logger.error(ErrorMessages.ERROR_EXTRACTING_TENANT.format(str(e)))
            raise serializers.ValidationError(ErrorMessages.ERROR_EXTRACTING_TENANT.format(str(e)))

    def get_queryset(self):
        if self.action == ActionNames.LIST:
            logger.debug(LogMessages.RETURNING_ALL_TENANTS)
            return Tenant.objects.all()
        tenant = self.get_tenant(self.request)
        logger.debug(LogMessages.FILTERING_QUERYSET_FOR_TENANT.format(tenant.schema_name))
        connection.set_schema(tenant.schema_name)
        with connection.cursor() as cursor:
            cursor.execute(SQLQueries.SHOW_SEARCH_PATH)
            search_path = cursor.fetchone()[0]
            logger.debug(LogMessages.DATABASE_SEARCH_PATH.format(search_path))
        return Tenant.objects.filter(id=tenant.id)

    def perform_create(self, serializer):
        original_schema = connection.schema_name
        try:
            connection.set_schema(SchemaNames.PUBLIC)
            with transaction.atomic():
                new_tenant = serializer.save()
                logger.info(LogMessages.TENANT_CREATED.format(new_tenant.name, new_tenant.schema_name))

                # ✅ FIX: Log global activity for tenant creation
                GlobalActivity.log_platform_action(
                    action=EventTypes.TENANT_CREATED,
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
                    KafkaTopics.TENANT_EVENTS,
                    {
                        KafkaEventKeys.EVENT_TYPE: EventTypes.TENANT_CREATED,
                        KafkaEventKeys.TENANT_ID: str(new_tenant.unique_id),
                        KafkaEventKeys.DATA: tenant_data
                    }
                )

                # Send notification to notification service
                notification_data = {
                    NotificationKeys.EXTERNAL_ID: str(new_tenant.unique_id),
                    NotificationKeys.ID: str(new_tenant.unique_id),
                    NotificationKeys.NAME: new_tenant.name
                }
                send_notification_event(notification_data)
        except Exception as e:
            logger.error(ErrorMessages.FAILED_TO_CREATE_TENANT.format(str(e)))
            raise serializers.ValidationError(ErrorMessages.FAILED_TO_CREATE_TENANT.format(str(e)))
        finally:
            connection.set_schema(original_schema)

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.get_queryset()
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                logger.info(LogMessages.LISTING_PAGINATED_TENANTS.format([t['id'] for t in serializer.data]))
                return self.get_paginated_response(serializer.data)
            serializer = self.get_serializer(queryset, many=True)
            logger.info(LogMessages.LISTING_ALL_TENANTS.format([t['id'] for t in serializer.data]))
            return Response(serializer.data)
        except Exception as e:
            logger.error(ErrorMessages.ERROR_LISTING_TENANTS.format(str(e)))
            return Response({ResponseKeys.DETAIL: str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def retrieve(self, request, *args, **kwargs):
        tenant = self.get_tenant(request)
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        logger.info(LogMessages.RETRIEVING_TENANT.format(instance.id, tenant.schema_name))
        return Response(serializer.data)

    def perform_destroy(self, instance):
        from users.signals import set_deleting_tenant
        
        tenant = self.get_tenant(self.request)
        user = self.request.user
        
        # Check if user is authorized to delete the tenant
        is_own_tenant = instance.id == tenant.id
        is_proliance_admin = (
            tenant.schema_name.lower() == 'proliance' and 
            hasattr(user, 'role') and 
            user.role in ['root-admin', 'co-admin']
        )
        
        # Allow deletion if: (1) deleting own tenant, OR (2) Proliance admin
        if not is_own_tenant and not is_proliance_admin:
            logger.error(LogMessages.UNAUTHORIZED_DELETE_ATTEMPT.format(instance.id, tenant.id))
            raise serializers.ValidationError(ErrorMessages.NOT_AUTHORIZED_DELETE_TENANT)

        # ✅ FIX: Log global activity for tenant deletion
        with schema_context(SchemaNames.PUBLIC):
            GlobalActivity.log_platform_action(
                action=EventTypes.TENANT_DELETED,
                affected_tenant=instance,
                performed_by_id=str(self.request.user.id) if self.request.user.is_authenticated else None,
                details={
                    DetailsKeys.TENANT_NAME: instance.name,
                    DetailsKeys.SCHEMA_NAME: instance.schema_name
                },
                request=self.request
            )

        # Disable activity logging during tenant deletion to avoid FK violations
        try:
            set_deleting_tenant(True)
            
            # Always delete from the target tenant's own schema
            # Django-Tenants requires deletion to happen in the tenant's schema or public schema
            # But since CustomUser and other models reference Tenant and exist in tenant schemas,
            # we must use the target tenant's schema for proper CASCADE deletion
            with tenant_context(instance):
                instance.delete()
            
            if is_proliance_admin and not is_own_tenant:
                logger.info(f"Proliance admin deleted tenant: {instance.name} ({instance.schema_name})")
            else:
                logger.info(LogMessages.TENANT_DELETED.format(instance.name, instance.schema_name))
        finally:
            # Always reset the flag
            set_deleting_tenant(False)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        instance = self.get_object()
        tenant = self.get_tenant(self.request)
        if instance.id != tenant.id and not self.request.user.is_superuser:
            raise serializers.ValidationError(ErrorMessages.NOT_AUTHORIZED_UPDATE_TENANT)

        # ✅ FIX: Log global activity for tenant update
        with schema_context(SchemaNames.PUBLIC):
            GlobalActivity.log_platform_action(
                action=EventTypes.TENANT_UPDATED,
                affected_tenant=instance,
                performed_by_id=str(self.request.user.id) if self.request.user.is_authenticated else None,
                details={
                    DetailsKeys.TENANT_NAME: instance.name,
                    DetailsKeys.SCHEMA_NAME: instance.schema_name
                },
                request=self.request
            )

        with tenant_context(tenant):
            serializer.save()
        logger.info(LogMessages.TENANT_UPDATED.format(instance.name, tenant.schema_name))

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        tenant = self.get_tenant(request)
        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=partial,
            context={ContextKeys.REQUEST: request}
        )
        serializer.is_valid(raise_exception=True)
        with tenant_context(tenant):
            serializer.save()
        return Response(serializer.data)

    # NEW: Action to suspend a tenant
    @action(detail=True, methods=['post'], url_path='suspend')
    def suspend(self, request, pk=None):
        instance = self.get_object()
        if instance.status == StatusValues.SUSPENDED:
            return Response({ResponseKeys.DETAIL: ResponseMessages.TENANT_ALREADY_SUSPENDED_DETAIL}, status=status.HTTP_400_BAD_REQUEST)

        reason = request.data.get(RequestDataKeys.REASON, DefaultReasons.MANUAL_SUSPENSION)
        try:
            with schema_context(SchemaNames.PUBLIC):  # Log in shared schema
                GlobalActivity.log_platform_action(
                    action=EventTypes.TENANT_SUSPENDED,
                    affected_tenant=instance,
                    performed_by_id=str(request.user.id),
                    details={DetailsKeys.REASON: reason},
                    request=request
                )

            with tenant_context(instance):
                instance.status = StatusValues.SUSPENDED
                instance.save(update_fields=[FieldNames.STATUS])

            logger.info(LogMessages.TENANT_SUSPENDED.format(instance.name, pk, request.user.email))
            return Response({
                ResponseKeys.DETAIL: ResponseMessages.TENANT_SUSPENDED_SUCCESS.format(instance.name),
                ResponseKeys.STATUS: instance.status
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(ErrorMessages.ERROR_SUSPENDING_TENANT.format(pk, str(e)))
            return Response({ResponseKeys.DETAIL: str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # NEW: Action to activate a tenant
    @action(detail=True, methods=['post'], url_path=URLPaths.ACTIVATE)
    def activate(self, request, pk=None):
        instance = self.get_object()
        if instance.status == StatusValues.ACTIVE:
            return Response({ResponseKeys.DETAIL: ResponseMessages.TENANT_ALREADY_ACTIVE_DETAIL}, status=status.HTTP_400_BAD_REQUEST)

        reason = request.data.get(RequestDataKeys.REASON, DefaultReasons.MANUAL_ACTIVATION)
        try:
            with schema_context(SchemaNames.PUBLIC):  # Log in shared schema
                GlobalActivity.log_platform_action(
                    action=EventTypes.TENANT_ACTIVATED,
                    affected_tenant=instance,
                    performed_by_id=str(request.user.id),
                    details={DetailsKeys.REASON: reason},
                    request=request
                )

            with tenant_context(instance):
                instance.status = StatusValues.ACTIVE
                instance.save(update_fields=[FieldNames.STATUS])

            logger.info(LogMessages.TENANT_ACTIVATED.format(instance.name, pk, request.user.email))
            return Response({
                ResponseKeys.DETAIL: ResponseMessages.TENANT_ACTIVATED_SUCCESS.format(instance.name),
                ResponseKeys.STATUS: instance.status
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(ErrorMessages.ERROR_ACTIVATING_TENANT.format(pk, str(e)))
            return Response({ResponseKeys.DETAIL: str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PublicTenantInfoView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, unique_id):
        try:
            tenant = Tenant.objects.get(unique_id=unique_id)
            serializer = PublicTenantSerializer(tenant)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Tenant.DoesNotExist:
            return Response({ResponseKeys.DETAIL: ErrorMessages.TENANT_NOT_FOUND_PUBLIC}, status=status.HTTP_404_NOT_FOUND)

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
            raise PermissionDenied(ErrorMessages.ONLY_SUPERUSERS_VIEW_GLOBAL_LOGS)
        
        queryset = GlobalActivity.objects.all().select_related('affected_tenant').order_by(OrderingFields.TIMESTAMP_DESC)
        
        # Apply filters
        queryset = self._apply_filters(queryset)
        return queryset
    
    def _apply_filters(self, queryset):
        params = self.request.query_params

        # Filter by tenant
        tenant_id = params.get(QueryParams.TENANT_ID)
        if tenant_id:
            queryset = queryset.filter(affected_tenant__unique_id=tenant_id)

        # Filter by action type
        actions = params.getlist(QueryParams.ACTION) or params.getlist(QueryParams.ACTION_ALT)
        if actions:
            queryset = queryset.filter(action__in=actions)

        # Date range
        date_from = params.get(QueryParams.DATE_FROM)
        date_to = params.get(QueryParams.DATE_TO)
        if date_from:
            queryset = queryset.filter(timestamp__gte=date_from)
        if date_to:
            queryset = queryset.filter(timestamp__lte=date_to)

        # Search
        search = params.get(QueryParams.SEARCH)
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
        days = int(request.query_params.get(QueryParams.DAYS, 30))
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
            FieldNames.AFFECTED_TENANT_UNIQUE_ID,
            FieldNames.AFFECTED_TENANT_NAME,
            FieldNames.AFFECTED_TENANT_SCHEMA_NAME
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # Activities by type
        activities_by_type = activities.values(FieldNames.ACTION).annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Most active admins
        active_admins = activities.values(FieldNames.GLOBAL_USER).annotate(
            activity_count=Count('id')
        ).order_by('-activity_count')[:10]
        
        return Response({
            ResponseKeys.PERIOD: {FieldNames.START_DATE: start_date, FieldNames.END_DATE: end_date, FieldNames.DAYS: days},
            ResponseKeys.SUMMARY: {
                FieldNames.TOTAL_ACTIVITIES: total_activities,
                FieldNames.AFFECTED_TENANTS_COUNT: activities.values(FieldNames.AFFECTED_TENANT).distinct().count(),
                FieldNames.ACTIVE_ADMINS_COUNT: activities.values(FieldNames.GLOBAL_USER).distinct().count(),
            },
            ResponseKeys.ACTIVITIES_BY_TENANT: list(activities_by_tenant),
            ResponseKeys.ACTIVITIES_BY_TYPE: list(activities_by_type),
            ResponseKeys.ACTIVE_ADMINS: list(active_admins),
        })
    
    @action(detail=False, methods=['get'], url_path='tenant-activities')
    def tenant_activities(self, request):
        """Get all activities for a specific tenant"""
        tenant_id = request.query_params.get(QueryParams.TENANT_ID)
        if not tenant_id:
            return Response(
                {ResponseKeys.ERROR: ErrorMessages.TENANT_ID_PARAMETER_REQUIRED},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            tenant = Tenant.objects.get(unique_id=tenant_id)
        except Tenant.DoesNotExist:
            return Response(
                {ResponseKeys.ERROR: ErrorMessages.TENANT_NOT_FOUND_GENERAL},
                status=status.HTTP_404_NOT_FOUND
            )
        
        activities = GlobalActivity.objects.filter(affected_tenant=tenant).select_related('affected_tenant').order_by(OrderingFields.TIMESTAMP_DESC)
        
        page = self.paginate_queryset(activities)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(activities, many=True)
        return Response(serializer.data)