import os
import re
import uuid
import json
import jwt
import mimetypes
import logging
import requests
from drf_spectacular.utils import extend_schema_field

from django.utils import timezone
from django.db import transaction
from django.conf import settings

from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from django_tenants.utils import tenant_context

from kafka import KafkaProducer

from core.models import Tenant, Domain, Module, TenantConfig, Branch, GlobalActivity
from core.email_default_templates import default_templates

from .constants import (
    ErrorMessages, LogMessages, JWTKeys, Headers, Algorithms, StatusValues, JWTDecodeOptions, EventTypes,
    SerializerFields, FilePaths, DefaultModules, KafkaTopics
)
from utils.storage import get_storage_service

# Logger
logger = logging.getLogger(__name__)



def get_tenant_id_from_jwt(request):
    auth_header = request.META.get(Headers.AUTHORIZATION, "")
    if not auth_header.startswith(Headers.BEARER_PREFIX):
        raise ValidationError(ErrorMessages.NO_VALID_BEARER_TOKEN)
    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, options={JWTDecodeOptions.VERIFY_SIGNATURE: False})
        return payload.get(JWTKeys.TENANT_UNIQUE_ID)
    except Exception:
        raise ValidationError(ErrorMessages.INVALID_TOKEN)
    

    import jwt




def get_user_data_from_jwt(request):
    """Extract user data from JWT payload."""
    auth_header = request.headers.get(Headers.AUTHORIZATION, "")
    if not auth_header.startswith(Headers.BEARER_PREFIX):
        raise serializers.ValidationError(ErrorMessages.NO_VALID_BEARER_TOKEN)
    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, options={JWTDecodeOptions.VERIFY_SIGNATURE: False})
        user_data = payload.get(JWTKeys.USER, {})
        return {
            JWTKeys.EMAIL: user_data.get(JWTKeys.EMAIL, ''),
            JWTKeys.FIRST_NAME: user_data.get(JWTKeys.FIRST_NAME, ''),
            JWTKeys.LAST_NAME: user_data.get(JWTKeys.LAST_NAME, ''),
            JWTKeys.JOB_ROLE: user_data.get(JWTKeys.JOB_ROLE, ''),
            JWTKeys.ID: user_data.get(JWTKeys.ID, None)
        }
    except Exception as e:
        logger.error(ErrorMessages.FAILED_TO_DECODE_JWT_USER_DATA.format(str(e)))
        raise serializers.ValidationError(ErrorMessages.INVALID_JWT_TOKEN_FOR_USER_DATA)




class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = SerializerFields.BRANCH_FIELDS
        read_only_fields = SerializerFields.BRANCH_READ_ONLY

    def validate_name(self, value):
        if not re.match(r'^[a-zA-Z0-9\s\-]+$', value):
            raise serializers.ValidationError(ErrorMessages.BRANCH_NAME_INVALID)
        try:
            tenant = self.context['request'].user.tenant
        except AttributeError as e:
            logger.error(ErrorMessages.ERROR_ACCESSING_REQUEST_USER_TENANT.format(str(e)))
            raise serializers.ValidationError(ErrorMessages.TENANT_NOT_FOUND_IN_REQUEST_CONTEXT)
        with tenant_context(tenant):
            if Branch.objects.filter(tenant=tenant, name=value).exists():
                raise serializers.ValidationError(ErrorMessages.BRANCH_ALREADY_EXISTS.format(value))
        return value

    def validate_is_head_office(self, value):
        if value:  # Only validate if is_head_office is True
            try:
                tenant = self.context['request'].user.tenant
            except AttributeError as e:
                logger.error(ErrorMessages.ERROR_ACCESSING_REQUEST_USER_TENANT.format(str(e)))
                raise serializers.ValidationError(ErrorMessages.TENANT_NOT_FOUND_IN_REQUEST_CONTEXT)
            with tenant_context(tenant):
                # Exclude the current instance during updates
                existing_head_office = Branch.objects.filter(
                    tenant=tenant,
                    is_head_office=True
                ).exclude(id=self.instance.id if self.instance else None)
                if existing_head_office.exists():
                    raise serializers.ValidationError(
                        ErrorMessages.ANOTHER_BRANCH_HEAD_OFFICE.format(existing_head_office.first().name)
                    )
        return value

    def validate(self, data):
        try:
            tenant = self.context['request'].user.tenant
        except AttributeError as e:
            logger.error(ErrorMessages.ERROR_ACCESSING_REQUEST_USER_TENANT.format(str(e)))
            raise serializers.ValidationError(ErrorMessages.TENANT_NOT_FOUND_IN_REQUEST_CONTEXT)
        data['tenant'] = tenant  # Set tenant from request context
        return data

    def create(self, validated_data):
        return super().create(validated_data)



class DomainSerializer(serializers.ModelSerializer):
    class Meta:
        model = Domain
        fields = '__all__'


class ModuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Module
        fields = SerializerFields.MODULE_FIELDS
        read_only_fields = SerializerFields.MODULE_READ_ONLY

    def validate_name(self, value):
        if not re.match(r'^[a-zA-Z0-9\s\-]+$', value):
            raise serializers.ValidationError(ErrorMessages.MODULE_NAME_INVALID)
        tenant = self.context['request'].user.tenant
        with tenant_context(tenant):
            if Module.objects.filter(name=value, tenant=tenant).exists():
                raise serializers.ValidationError(ErrorMessages.MODULE_ALREADY_EXISTS.format(value))
        return value

    def validate(self, data):
        try:
            tenant = self.context['request'].user.tenant
        except AttributeError as e:
            logger.error(ErrorMessages.ERROR_ACCESSING_REQUEST_USER_TENANT.format(str(e)))
            raise serializers.ValidationError(ErrorMessages.TENANT_NOT_FOUND_IN_REQUEST_CONTEXT)
        data['tenant'] = tenant  # Set tenant from request context
        return data

class EmailTemplateSerializer(serializers.Serializer):
    content = serializers.CharField()
    is_auto_sent = serializers.BooleanField(default=False)


class TenantConfigSerializer(serializers.ModelSerializer):
    email_templates = serializers.DictField(
        child=EmailTemplateSerializer(),
        required=False
    )

    class Meta:
        model = TenantConfig
        fields = SerializerFields.TENANT_CONFIG_FIELDS



# core/serializers.py (add these fields to TenantSerializer)
class TenantSerializer(serializers.ModelSerializer):
    domain = serializers.CharField(write_only=True, required=True)
    logo_file = serializers.FileField(write_only=True, required=False)
    domains = DomainSerializer(many=True, read_only=True, source='domain_set')

    class Meta:
        model = Tenant
        fields = SerializerFields.TENANT_FIELDS
        read_only_fields = SerializerFields.TENANT_READ_ONLY

    # NEW: Validation for status field
    def validate_status(self, value):
        if value not in [StatusValues.ACTIVE, StatusValues.SUSPENDED]:
            raise serializers.ValidationError(ErrorMessages.INVALID_STATUS)
        return value

    # Add validation for new fields
    def validate_roi_percent(self, value):
        if value < 0 or value > 100:
            raise serializers.ValidationError(ErrorMessages.ROI_PERCENT_INVALID)
        return value

    def validate_min_withdrawal_months(self, value):
        if value < 1:
            raise serializers.ValidationError(ErrorMessages.MIN_WITHDRAWAL_MONTHS_INVALID)
        return value

    def validate_unique_policy_prefix(self, value):
        if not value.isalnum():
            raise serializers.ValidationError(ErrorMessages.POLICY_PREFIX_INVALID)
        return value.upper()

    def validate_next_policy_number(self, value):
        if value < 1:
            raise serializers.ValidationError(ErrorMessages.NEXT_POLICY_NUMBER_INVALID)
        return value


    def validate_primary_color(self, value):
        if not re.match(r'^#(?:[0-9a-fA-F]{3}){1,2}$', value):
            raise serializers.ValidationError(ErrorMessages.PRIMARY_COLOR_INVALID)
        return value

    def validate_secondary_color(self, value):
        if not re.match(r'^#(?:[0-9a-fA-F]{3}){1,2}$', value):
            raise serializers.ValidationError(ErrorMessages.SECONDARY_COLOR_INVALID)
        return value


    def validate_schema_name(self, value):
        if not re.match(r'^[a-z0-9_]+$', value):
            raise serializers.ValidationError(ErrorMessages.SCHEMA_NAME_INVALID)
        if Tenant.objects.filter(schema_name=value).exists():
            raise serializers.ValidationError(ErrorMessages.SCHEMA_NAME_EXISTS)
        return value

    def validate_domain(self, value):
        if not re.match(r'^[a-zA-Z0-9\-\.]+$', value):
            raise serializers.ValidationError(ErrorMessages.DOMAIN_INVALID)
        if Domain.objects.filter(domain=value).exists():
            raise serializers.ValidationError(ErrorMessages.DOMAIN_EXISTS.format(value))
        return value

    def validate_logo_file(self, value):
        allowed_types = ['image/png', 'image/jpeg', 'image/jpg', 'image/gif']
        if value.content_type not in allowed_types:
            raise serializers.ValidationError(ErrorMessages.LOGO_FILE_INVALID)
        max_size = 5 * 1024 * 1024  # 5 MB
        if value.size > max_size:
            raise serializers.ValidationError(ErrorMessages.LOGO_FILE_SIZE_EXCEEDS)
        return value

 

    def create(self, validated_data):
        logo_file = validated_data.pop('logo_file', None)
        domain_name = validated_data.pop('domain')
        schema_name = validated_data.get('schema_name') or validated_data['name'].lower().replace(' ', '_').replace('-', '_')
        validated_data['schema_name'] = schema_name

        logger.info(LogMessages.CREATING_TENANT.format(validated_data['name'], schema_name, domain_name))

        try:
            with transaction.atomic():
                # Create tenant
                tenant = Tenant.objects.create(**validated_data)

                # Create primary domain
                domain = Domain.objects.create(tenant=tenant, domain=domain_name, is_primary=True)

                # Upload logo if provided
                if logo_file:
                    file_ext = os.path.splitext(logo_file.name)[1]
                    filename = f"{uuid.uuid4()}{file_ext}"
                    folder_path = f"{FilePaths.TENANT_LOGOS_BASE}/{timezone.now().strftime('%Y/%m/%d')}"
                    path = f"{folder_path}/{filename}"
                    content_type = mimetypes.guess_type(logo_file.name)[0]
                    storage = get_storage_service()
                    storage.upload_file(logo_file, path, content_type or 'application/octet-stream')
                    tenant.logo = storage.get_public_url(path)
                    tenant.save()
                    logger.info(LogMessages.UPLOADED_LOGO_FOR_TENANT.format(tenant.id))

                # Create tenant config
                TenantConfig.objects.create(
                    tenant=tenant,
                    email_templates=default_templates
                )

                # Create default modules
                default_modules = DefaultModules.MODULES
                for module_name in default_modules:
                    Module.objects.create(name=module_name, tenant=tenant)
                logger.info(LogMessages.CREATED_MODULES_FOR_TENANT.format(tenant.id))

                # ✅ FIX: Make Kafka publishing async with timeout
                self._publish_tenant_created_async(tenant, domain_name)

                return tenant

        except Exception as e:
            logger.error(ErrorMessages.TENANT_CREATION_FAILED.format(str(e)))
            raise serializers.ValidationError(ErrorMessages.TENANT_CREATION_FAILED.format(str(e)))

    def _publish_tenant_created_async(self, tenant, domain_name):
        """Publish tenant created event asynchronously"""
        import threading
        import time
        
        def publish_event():
            try:
                producer = KafkaProducer(
                    bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
                    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                    # ✅ Add timeout configurations
                    request_timeout_ms=5000,  # 5 second timeout
                    retries=1,  # Only retry once
                )
                event_data = {
                    'event_type': EventTypes.TENANT_CREATED,
                    'tenant_id': str(tenant.id),
                    'schema_name': tenant.schema_name,
                    'name': tenant.name,
                    'title': tenant.title,
                    'email_host': tenant.email_host,
                    'domains': [domain_name],
                }
                # ✅ Send with timeout
                future = producer.send(KafkaTopics.TENANT_EVENTS, event_data)
                future.get(timeout=5)  # 5 second timeout
                producer.flush(timeout=5)
                logger.info(LogMessages.SENT_TENANT_CREATED_EVENT.format(tenant.id))
            except Exception as e:
                logger.error(ErrorMessages.KAFKA_PUBLISH_FAILED_ASYNC.format(str(e)))
        
        # Start async publishing
        thread = threading.Thread(target=publish_event)
        thread.daemon = True  # Daemon thread won't block process exit
        thread.start() 

    def update(self, instance, validated_data):
        request = self.context.get('request')

        # Handle logo file if uploaded
        logo_file = request.FILES.get('logo') if request else None
        if logo_file:
            file_ext = os.path.splitext(logo_file.name)[1]
            filename = f"{uuid.uuid4()}{file_ext}"
            folder_path = f"{FilePaths.TENANT_LOGOS_BASE}/{timezone.now().strftime('%Y/%m/%d')}"
            path = f"{folder_path}/{filename}"
            content_type = mimetypes.guess_type(logo_file.name)[0]
            storage = get_storage_service()
            storage.upload_file(logo_file, path, content_type or 'application/octet-stream')
            instance.logo = storage.get_public_url(path)

        # Update remaining fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance


    def to_representation(self, instance):
        data = super().to_representation(instance)
        logo_path = instance.logo
        if logo_path:
            if logo_path.startswith('http'):
                data['logo'] = logo_path
            else:
                storage = get_storage_service()
                data['logo'] = storage.get_public_url(logo_path)
        else:
            data['logo'] = ""
        return data





class PublicTenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = SerializerFields.PUBLIC_TENANT_FIELDS


# core/serializers.py - Add this

# class GlobalActivitySerializer(serializers.ModelSerializer):
#     global_user = serializers.SerializerMethodField()
#     performed_by = serializers.SerializerMethodField()
#     affected_tenant = serializers.SerializerMethodField()
    
#     class Meta:
#         model = GlobalActivity
#         fields = [
#             'id', 'global_user', 'affected_tenant', 'action',
#             'performed_by', 'timestamp', 'details', 'ip_address',
#             'user_agent', 'success', 'global_correlation_id'
#         ]
    
#     def get_global_user(self, obj):
#         if obj.global_user:
#             return {
#                 'id': obj.global_user.id,
#                 'email': obj.global_user.email,
#                 'first_name': obj.global_user.first_name,
#                 'last_name': obj.global_user.last_name,
#                 'role': obj.global_user.role
#             }
#         return None
    
#     def get_performed_by(self, obj):
#         if obj.performed_by:
#             return {
#                 'id': obj.performed_by.id,
#                 'email': obj.performed_by.email,
#                 'first_name': obj.performed_by.first_name,
#                 'last_name': obj.performed_by.last_name,
#                 'role': obj.performed_by.role
#             }
#         return None
    
#     def get_affected_tenant(self, obj):
#         return {
#             'id': str(obj.affected_tenant.unique_id),
#             'name': obj.affected_tenant.name,
#             'schema_name': obj.affected_tenant.schema_name
#         }

# core/serializers.py - Updated GlobalActivitySerializer


class GlobalActivitySerializer(serializers.ModelSerializer):
    global_user = serializers.SerializerMethodField()
    performed_by = serializers.SerializerMethodField()
    affected_tenant = serializers.SerializerMethodField()
    
    class Meta:
        model = GlobalActivity
        fields = SerializerFields.GLOBAL_ACTIVITY_FIELDS
    
    def get_global_user(self, obj):
        if obj.global_user:
            try:
                # Extract user data from JWT if the request user matches global_user
                user_data = get_user_data_from_jwt(self.context['request'])
                if str(user_data[JWTKeys.ID]) == str(obj.global_user):
                    return {
                        JWTKeys.ID: user_data[JWTKeys.ID],
                        JWTKeys.EMAIL: user_data[JWTKeys.EMAIL],
                        JWTKeys.FIRST_NAME: user_data[JWTKeys.FIRST_NAME],
                        JWTKeys.LAST_NAME: user_data[JWTKeys.LAST_NAME],
                        'role': user_data.get(JWTKeys.JOB_ROLE, '')  # Assuming job_role maps to role
                    }
                logger.warning(ErrorMessages.USER_NOT_FOUND_LOCAL_DB.format(obj.global_user))
                return {'id': obj.global_user}  # Fallback to just ID
            except Exception as e:
                logger.error(ErrorMessages.ERROR_FETCHING_USER.format("global_user", obj.global_user, str(e)))
                return {'id': obj.global_user}  # Fallback to just ID
        return None
    
    def get_performed_by(self, obj):
        if obj.performed_by:
            try:
                # Extract user data from JWT if the request user matches performed_by
                user_data = get_user_data_from_jwt(self.context['request'])
                if str(user_data[JWTKeys.ID]) == str(obj.performed_by):
                    return {
                        JWTKeys.ID: user_data[JWTKeys.ID],
                        JWTKeys.EMAIL: user_data[JWTKeys.EMAIL],
                        JWTKeys.FIRST_NAME: user_data[JWTKeys.FIRST_NAME],
                        JWTKeys.LAST_NAME: user_data[JWTKeys.LAST_NAME],
                        'role': user_data.get(JWTKeys.JOB_ROLE, '')  # Assuming job_role maps to role
                    }
                logger.warning(ErrorMessages.USER_NOT_FOUND_LOCAL_DB.format(obj.performed_by))
                return {'id': obj.performed_by}  # Fallback to just ID
            except Exception as e:
                logger.error(ErrorMessages.ERROR_FETCHING_USER.format("performed_by", obj.performed_by, str(e)))
                return {'id': obj.performed_by}  # Fallback to just ID
        return None
    
    def get_affected_tenant(self, obj):
        return {
            'id': str(obj.affected_tenant.unique_id),
            'name': obj.affected_tenant.name,
            'schema_name': obj.affected_tenant.schema_name,
            'status': obj.affected_tenant.status  # NEW: Include tenant status
        }