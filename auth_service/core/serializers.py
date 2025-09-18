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

from core.models import Tenant, Domain, Module, TenantConfig, Branch
from core.email_default_templates import default_templates

from utils.storage import get_storage_service

# Logger
logger = logging.getLogger(__name__)



def get_tenant_id_from_jwt(request):
    auth_header = request.META.get("HTTP_AUTHORIZATION", "")
    if not auth_header.startswith("Bearer "):
        raise ValidationError("No valid Bearer token provided.")
    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        return payload.get("tenant_unique_id")
    except Exception:
        raise ValidationError("Invalid JWT token.")
    
class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = ['id', 'name', 'location', 'is_head_office', 'created_at']
        read_only_fields = ['id', 'created_at']

    def validate_name(self, value):
        if not re.match(r'^[a-zA-Z0-9\s\-]+$', value):
            raise serializers.ValidationError("Branch name can only contain letters, numbers, spaces, or hyphens.")
        try:
            tenant = self.context['request'].user.tenant
        except AttributeError as e:
            logger.error(f"Error accessing request.user.tenant: {str(e)}")
            raise serializers.ValidationError("Tenant not found in request context")
        with tenant_context(tenant):
            if Branch.objects.filter(tenant=tenant, name=value).exists():
                raise serializers.ValidationError(f"Branch '{value}' already exists for this tenant.")
        return value

    def validate_is_head_office(self, value):
        if value:  # Only validate if is_head_office is True
            try:
                tenant = self.context['request'].user.tenant
            except AttributeError as e:
                logger.error(f"Error accessing request.user.tenant: {str(e)}")
                raise serializers.ValidationError("Tenant not found in request context")
            with tenant_context(tenant):
                # Exclude the current instance during updates
                existing_head_office = Branch.objects.filter(
                    tenant=tenant,
                    is_head_office=True
                ).exclude(id=self.instance.id if self.instance else None)
                if existing_head_office.exists():
                    raise serializers.ValidationError(
                        f"Another branch ('{existing_head_office.first().name}') is already set as head office for this tenant."
                    )
        return value

    def validate(self, data):
        try:
            tenant = self.context['request'].user.tenant
        except AttributeError as e:
            logger.error(f"Error accessing request.user.tenant: {str(e)}")
            raise serializers.ValidationError("Tenant not found in request context")
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
        fields = ['id', 'name', 'is_active']
        read_only_fields = ['id']

    def validate_name(self, value):
        if not re.match(r'^[a-zA-Z0-9\s\-]+$', value):
            raise serializers.ValidationError("Module name can only contain letters, numbers, spaces, or hyphens.")
        tenant = self.context['request'].user.tenant
        with tenant_context(tenant):
            if Module.objects.filter(name=value, tenant=tenant).exists():
                raise serializers.ValidationError(f"Module '{value}' already exists for this tenant.")
        return value

    def validate(self, data):
        try:
            tenant = self.context['request'].user.tenant
        except AttributeError as e:
            logger.error(f"Error accessing request.user.tenant: {str(e)}")
            raise serializers.ValidationError("Tenant not found in request context")
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
        fields = ['logo', 'custom_fields', 'email_templates']





class TenantSerializer(serializers.ModelSerializer):
    domain = serializers.CharField(write_only=True, required=True)  # Accept domain in POST
    logo_file = serializers.FileField(write_only=True, required=False)
    domains = DomainSerializer(many=True, read_only=True, source='domain_set')  # List domains in response

    class Meta:
        model = Tenant
        fields = [
            'id', 'unique_id', 'organizational_id', 'name', 'title', 'schema_name', 'created_at', 'logo', 'logo_file',
            'email_host', 'email_port', 'email_use_ssl', 'email_host_user',
            'email_host_password', 'default_from_email', 'about_us',
            'domain',  # for write
            'domains'  # for read
        ]
        
        read_only_fields = [
            'id', 'unique_id', 'organizational_id',
            'created_at', 'schema_name', 'logo'
        ]

    def validate_schema_name(self, value):
        if not re.match(r'^[a-z0-9_]+$', value):
            raise serializers.ValidationError("Schema name can only contain lowercase letters, numbers, or underscores.")
        if Tenant.objects.filter(schema_name=value).exists():
            raise serializers.ValidationError("Schema name already exists.")
        return value

    def validate_domain(self, value):
        if not re.match(r'^[a-zA-Z0-9\-\.]+$', value):
            raise serializers.ValidationError("Invalid domain name.")
        if Domain.objects.filter(domain=value).exists():
            raise serializers.ValidationError(f"Domain '{value}' already exists.")
        return value

    def validate_logo_file(self, value):
        allowed_types = ['image/png', 'image/jpeg', 'image/jpg', 'image/gif']
        if value.content_type not in allowed_types:
            raise serializers.ValidationError("Only image files are allowed for logo.")
        max_size = 5 * 1024 * 1024  # 5 MB
        if value.size > max_size:
            raise serializers.ValidationError("Logo file size exceeds 5 MB limit.")
        return value

    def create(self, validated_data):
        logo_file = validated_data.pop('logo_file', None)
        domain_name = validated_data.pop('domain')
        schema_name = validated_data.get('schema_name') or validated_data['name'].lower().replace(' ', '_').replace('-', '_')
        validated_data['schema_name'] = schema_name

        logger.info(f"Creating tenant: {validated_data['name']} | Schema: {schema_name} | Domain: {domain_name}")

        try:
            with transaction.atomic():
                # Create tenant
                tenant = Tenant.objects.create(**validated_data)

                # Create primary domain
                Domain.objects.create(tenant=tenant, domain=domain_name, is_primary=True)

                # Upload logo if provided
                if logo_file:
                    file_ext = os.path.splitext(logo_file.name)[1]
                    filename = f"{uuid.uuid4()}{file_ext}"
                    folder_path = f"tenant_logos/{timezone.now().strftime('%Y/%m/%d')}"
                    path = f"{folder_path}/{filename}"
                    content_type = mimetypes.guess_type(logo_file.name)[0]
                    storage = get_storage_service()
                    storage.upload_file(logo_file, path, content_type or 'application/octet-stream')
                    tenant.logo = storage.get_public_url(path)
                    tenant.save()
                    logger.info(f"Uploaded logo for tenant {tenant.id}")

                # Create tenant config
                TenantConfig.objects.create(
                    tenant=tenant,
                    email_templates=default_templates
                )

                # Create default modules
                default_modules = [
                    'Talent Engine', 'Compliance', 'Training', 'Care Coordination',
                    'Workforce', 'Analytics', 'Integrations', 'Assets Management', 'Payroll'
                ]
                for module_name in default_modules:
                    Module.objects.create(name=module_name, tenant=tenant)
                logger.info(f"Created modules for tenant {tenant.id}")

                # Send Kafka event
                try:
                    producer = KafkaProducer(
                        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
                        value_serializer=lambda v: json.dumps(v).encode('utf-8')
                    )
                    event_data = {
                        'event_type': 'tenant_created',
                        'tenant_id': str(tenant.id),
                        'schema_name': tenant.schema_name,
                        'name': tenant.name,
                        'title': tenant.title,
                        'email_host': tenant.email_host,
                        'domains': [d.domain for d in tenant.domain_set.all()],
                    }
                    producer.send('tenant-events', event_data)
                    producer.flush()
                    logger.info(f"Sent tenant_created event for tenant {tenant.id}")
                except Exception as e:
                    logger.error(f"Kafka publish failed: {str(e)}")

                return tenant

        except Exception as e:
            logger.error(f"Tenant creation failed: {str(e)}")
            raise serializers.ValidationError(f"Tenant creation failed: {str(e)}")

            
    def update(self, instance, validated_data):
        request = self.context.get('request')

        # Handle logo file if uploaded
        logo_file = request.FILES.get('logo') if request else None
        if logo_file:
            file_ext = os.path.splitext(logo_file.name)[1]
            filename = f"{uuid.uuid4()}{file_ext}"
            folder_path = f"tenant_logos/{timezone.now().strftime('%Y/%m/%d')}"
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
        fields = ['name', 'title', 'logo']


