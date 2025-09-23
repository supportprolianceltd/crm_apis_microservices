import os
import uuid
import mimetypes
from datetime import timezone
import re
from rest_framework import serializers
from django.db import transaction
from kafka import KafkaProducer
from django.conf import settings
import json
import logging
from .models import Tenant, Domain
# Assume you have a get_storage_service function for uploads
from utils.storage import get_storage_service



logger = logging.getLogger(__name__)

class DomainSerializer(serializers.ModelSerializer):
    class Meta:
        model = Domain
        fields = ['domain', 'is_primary']

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
                tenant = Tenant.objects.create(**validated_data)
                Domain.objects.create(tenant=tenant, domain=domain_name, is_primary=True)

                if logo_file:
                    file_ext = os.path.splitext(logo_file.name)[1]
                    filename = f"{uuid.uuid4()}{file_ext}"
                    folder_path = f"tenant_logos/{timezone.now().strftime('%Y/%m/%d')}"
                    path = f"{folder_path}/{filename}"
                    content_type = mimetypes.guess_type(logo_file.name)[0]
                    storage = get_storage_service()  # Assume implemented
                    storage.upload_file(logo_file, path, content_type or 'application/octet-stream')
                    tenant.logo = storage.get_public_url(path)
                    tenant.save()
                    logger.info(f"Uploaded logo for tenant {tenant.id}")

                # Optional: Create default configs/modules as in auth

                # Publish event (if LMS also creates tenants independently)
                producer = KafkaProducer(
                    bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
                    value_serializer=lambda v: json.dumps(v).encode('utf-8')
                )
                event_data = {
                    'event_type': 'tenant_created',
                    'tenant_id': str(tenant.unique_id),
                    'data': self.data  # Or serialize again
                }
                producer.send('tenant-events', event_data)
                producer.flush()

                return tenant
        except Exception as e:
            logger.error(f"Tenant creation failed: {str(e)}")
            raise serializers.ValidationError(f"Tenant creation failed: {str(e)}")

  