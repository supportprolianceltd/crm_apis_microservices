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
    domain = serializers.CharField(write_only=True, required=True)
    logo_file = serializers.FileField(write_only=True, required=False)
    domains = DomainSerializer(many=True, read_only=True, source='domain_set')

    class Meta:
        model = Tenant
        fields = [
            'id', 'unique_id', 'organizational_id', 'name', 'title', 'schema_name', 'created_at', 'logo', 'logo_file',
            'email_host', 'email_port', 'email_use_ssl', 'email_host_user',
            'email_host_password', 'default_from_email', 'about_us',
            'domain', 'domains'
        ]
        read_only_fields = [
            'id', 'created_at', 'logo'
        ]

    def validate_unique_id(self, value):
        if Tenant.objects.filter(unique_id=value).exists():
            raise serializers.ValidationError("A tenant with this unique_id already exists.")
        return value

    def validate_organizational_id(self, value):
        if Tenant.objects.filter(organizational_id=value).exists():
            raise serializers.ValidationError("A tenant with this organizational_id already exists.")
        return value

    def validate_schema_name(self, value):
        if not re.match(r'^[a-z0-9_]+$', value):
            raise serializers.ValidationError("Schema name can only contain lowercase letters, numbers, or underscores.")
        if Tenant.objects.filter(schema_name=value).exists():
            raise serializers.ValidationError("Schema name already exists.")
        return value
