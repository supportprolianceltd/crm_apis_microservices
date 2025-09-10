from rest_framework import serializers
from core.models import Tenant, Domain, Module, TenantConfig, Branch
from django.utils import timezone
from django.db import transaction
from django.conf import settings
from django_tenants.utils import tenant_context

import logging
import re
import uuid
import os
import mimetypes
import json

from utils.storage import get_storage_service
from core.email_default_templates import default_templates
from kafka import KafkaProducer

logger = logging.getLogger('core')


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



# class TenantSerializer(serializers.ModelSerializer):
#     logo_file = serializers.FileField(write_only=True, required=False)
#     domains = DomainSerializer(many=True, read_only=True, source='domain_set')  # Adjust source if needed

#     class Meta:
#         model = Tenant
#         fields = [
#             'id', 'name', 'title', 'schema_name', 'created_at', 'logo', 'logo_file',
#             'email_host', 'email_port', 'email_use_ssl', 'email_host_user',
#             'email_host_password', 'default_from_email', 'about_us', 'domains'
#         ]
#         read_only_fields = ['id', 'created_at', 'schema_name', 'logo']

#     def validate_name(self, value):
#         if not re.match(r'^[a-zA-Z0-9\s\'-]+$', value):
#             raise serializers.ValidationError("Tenant name can only contain letters, numbers, spaces, apostrophes, or hyphens.")
#         return value

#     def validate_schema_name(self, value):
#         if not re.match(r'^[a-z0-9_]+$', value):
#             raise serializers.ValidationError("Schema name can only contain lowercase letters, numbers, or underscores.")
#         if Tenant.objects.filter(schema_name=value).exists():
#             raise serializers.ValidationError("Schema name already exists.")
#         return value

#     def validate_domain(self, value):
#         if not re.match(r'^[a-zA-Z0-9\-\.]+$', value):
#             raise serializers.ValidationError("Invalid domain name.")
#         if Domain.objects.filter(domain=value).exists():
#             raise serializers.ValidationError(f"Domain '{value}' already exists.")
#         return value

#     def validate_logo_file(self, value):
#         allowed_types = ['image/png', 'image/jpeg', 'image/jpg', 'image/gif']
#         if value.content_type not in allowed_types:
#             raise serializers.ValidationError("Only image files are allowed for logo.")
#         max_size = 5 * 1024 * 1024  # 5 MB
#         if value.size > max_size:
#             raise serializers.ValidationError("Logo file size exceeds 5 MB limit.")
#         return value

#     def create(self, validated_data):
#         logo_file = validated_data.pop('logo_file', None)
#         if logo_file:
#             file_ext = os.path.splitext(logo_file.name)[1]
#             filename = f"{uuid.uuid4()}{file_ext}"
#             folder_path = f"tenant_logos/{timezone.now().strftime('%Y/%m/%d')}"
#             path = f"{folder_path}/{filename}"
#             content_type = mimetypes.guess_type(logo_file.name)[0]
#             storage = get_storage_service()
#             storage.upload_file(logo_file, path, content_type or 'application/octet-stream')
#             file_url = storage.get_public_url(path)
#             validated_data['logo'] = file_url
#         domain_name = validated_data.pop('domain')
#         schema_name = validated_data.get('schema_name') or validated_data['name'].lower().replace(' ', '_').replace('-', '_')
#         validated_data['schema_name'] = schema_name
#         logger.info(f"Creating tenant with name: {validated_data['name']}, schema_name: {schema_name}, domain: {domain_name}")
#         try:
#             with transaction.atomic():
#                 tenant = Tenant.objects.create(**validated_data)
#                 logger.info(f"Tenant created: {tenant.id}, schema_name: {tenant.schema_name}")
#                 domain = Domain.objects.create(tenant=tenant, domain=domain_name, is_primary=True)
#                 logger.info(f"Domain created: {domain.domain} for tenant {tenant.id}")

#                 # Use imported default_templates
#                 TenantConfig.objects.create(
#                     tenant=tenant,
#                     email_templates=default_templates
#                 )
#                 logger.info(f"TenantConfig created for tenant {tenant.id} with default email templates")

#                 # Create default modules
#                 default_modules = [
#                     'Talent Engine', 'Compliance', 'Training', 'Care Coordination',
#                     'Workforce', 'Analytics', 'Integrations', 'Assets Management', 'Payroll'
#                 ]
#                 for module_name in default_modules:
#                     Module.objects.create(name=module_name, tenant=tenant)
#                 logger.info(f"Modules created for tenant {tenant.id}")

#                 try:
#                     domains = tenant.domain_set.all()
#                     logger.info(f"Domains for tenant {tenant.id}: {[d.domain for d in domains]}")
#                 except AttributeError as e:
#                     logger.error(f"domain_set access failed: {str(e)}")
#                     domains = Domain.objects.filter(tenant=tenant)
#                     logger.info(f"Fallback domains for tenant {tenant.id}: {[d.domain for d in domains]}")
#                 return tenant
#         except Exception as e:
#             logger.error(f"Failed to create tenant or domain: {str(e)}")
#             raise


#     def update(self, instance, validated_data):
#         logo_file = self.context['request'].FILES.get('logo') or validated_data.pop('logo', None)
#         if logo_file:
#             file_ext = os.path.splitext(logo_file.name)[1]
#             filename = f"{uuid.uuid4()}{file_ext}"
#             folder_path = f"tenant_logos/{timezone.now().strftime('%Y/%m/%d')}"
#             path = f"{folder_path}/{filename}"
#             content_type = mimetypes.guess_type(logo_file.name)[0]
#             storage = get_storage_service()
#             storage.upload_file(logo_file, path, content_type or 'application/octet-stream')
#             file_url = storage.get_public_url(path)
#             instance.logo = file_url  # Directly update the instance

#         # Update other fields
#         for attr, value in validated_data.items():
#             setattr(instance, attr, value)
#         instance.save()
#         return instance


#     def to_representation(self, instance):
#         data = super().to_representation(instance)
#         logo_path = instance.logo
#         if logo_path:
#             # If logo_path is already a URL, use it. Otherwise, generate public URL from storage utils.
#             if logo_path.startswith('http'):
#                 data['logo'] = logo_path
#             else:
#                 storage = get_storage_service()
#                 data['logo'] = storage.get_public_url(logo_path)
#         else:
#             data['logo'] = ""
#         return data

class TenantSerializer(serializers.ModelSerializer):
    logo_file = serializers.FileField(write_only=True, required=False)
    domains = DomainSerializer(many=True, read_only=True, source='domain_set')  # Adjust source if needed

    class Meta:
        model = Tenant
        fields = [
            'id', 'name', 'title', 'schema_name', 'created_at', 'logo', 'logo_file',
            'email_host', 'email_port', 'email_use_ssl', 'email_host_user',
            'email_host_password', 'default_from_email', 'about_us', 'domains'
        ]
        read_only_fields = ['id', 'created_at', 'schema_name', 'logo']

    def validate_name(self, value):
        if not re.match(r'^[a-zA-Z0-9\s\'-]+$', value):
            raise serializers.ValidationError("Tenant name can only contain letters, numbers, spaces, apostrophes, or hyphens.")
        return value

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
        logger.info(f"Creating tenant with name: {validated_data['name']}, schema_name: {schema_name}, domain: {domain_name}")
        try:
            with transaction.atomic():
                tenant = Tenant.objects.create(**validated_data)
                logger.info(f"Tenant created: {tenant.id}, schema_name: {tenant.schema_name}")
                domain = Domain.objects.create(tenant=tenant, domain=domain_name, is_primary=True)
                logger.info(f"Domain created: {domain.domain} for tenant {tenant.id}")

                # Handle logo file upload
                if logo_file:
                    file_ext = os.path.splitext(logo_file.name)[1]
                    filename = f"{uuid.uuid4()}{file_ext}"
                    folder_path = f"tenant_logos/{timezone.now().strftime('%Y/%m/%d')}"
                    path = f"{folder_path}/{filename}"
                    content_type = mimetypes.guess_type(logo_file.name)[0]
                    storage = get_storage_service()
                    storage.upload_file(logo_file, path, content_type or 'application/octet-stream')
                    file_url = storage.get_public_url(path)
                    tenant.logo = file_url
                    tenant.save()
                    logger.info(f"Logo uploaded for tenant {tenant.id}: {file_url}")

                # Create default TenantConfig with email templates
                TenantConfig.objects.create(
                    tenant=tenant,
                    email_templates=default_templates
                )
                logger.info(f"TenantConfig created for tenant {tenant.id} with default email templates")

                # Create default modules
                default_modules = [
                    'Talent Engine', 'Compliance', 'Training', 'Care Coordination',
                    'Workforce', 'Analytics', 'Integrations', 'Assets Management', 'Payroll'
                ]
                for module_name in default_modules:
                    Module.objects.create(name=module_name, tenant=tenant)
                logger.info(f"Modules created for tenant {tenant.id}")

                # Publish Kafka event
                try:
                    producer = KafkaProducer(
                        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
                        value_serializer=lambda v: json.dumps(v).encode('utf-8')
                    )
                    event_data = {
                        'event_type': 'tenant_created',
                        'tenant_id': str(tenant.id),  # Use str for JSON compatibility
                        'schema_name': tenant.schema_name,
                        'name': tenant.name,
                        'title': tenant.title,
                        'email_host': tenant.email_host,
                        'domains': [d.domain for d in tenant.domain_set.all()],
                    }
                    producer.send('tenant-events', event_data)
                    producer.flush()
                    logger.info(f"Published tenant_created event for tenant {tenant.id} to Kafka")
                except Exception as e:
                    logger.error(f"Failed to publish Kafka event for tenant {tenant.id}: {str(e)}")
                    # Log error but don't raise to avoid rolling back tenant creation

                # Log domains
                try:
                    domains = tenant.domain_set.all()
                    logger.info(f"Domains for tenant {tenant.id}: {[d.domain for d in domains]}")
                except AttributeError as e:
                    logger.error(f"domain_set access failed: {str(e)}")
                    domains = Domain.objects.filter(tenant=tenant)
                    logger.info(f"Fallback domains for tenant {tenant.id}: {[d.domain for d in domains]}")

                return tenant
        except Exception as e:
            logger.error(f"Failed to create tenant or domain: {str(e)}")
            raise

    def update(self, validated_data):
        logo_file = self.context['request'].FILES.get('logo') or validated_data.pop('logo', None)
        if logo_file:
            file_ext = os.path.splitext(logo_file.name)[1]
            filename = f"{uuid.uuid4()}{file_ext}"
            folder_path = f"tenant_logos/{timezone.now().strftime('%Y/%m/%d')}"
            path = f"{folder_path}/{filename}"
            content_type = mimetypes.guess_type(logo_file.name)[0]
            storage = get_storage_service()
            storage.upload_file(logo_file, path, content_type or 'application/octet-stream')
            file_url = storage.get_public_url(path)
            instance.logo = file_url  # Directly update the instance

        # Update other fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        logo_path = instance.logo
        if logo_path:
            # If logo_path is already a URL, use it. Otherwise, generate public URL from storage utils.
            if logo_path.startswith('http'):
                data['logo'] = logo_path
            else:
                storage = get_storage_service()
                data['logo'] = storage.get_public_url(logo_path)
        else:
            data['logo'] = ""
        return data