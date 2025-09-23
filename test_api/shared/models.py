# shared/models.py - Add unique constraint to unique_id
import uuid
import re
import logging
from django.db import models, transaction
from django_tenants.models import TenantMixin, DomainMixin

logger = logging.getLogger(__name__)

class Tenant(TenantMixin):
    name = models.CharField(max_length=100)
    title = models.CharField(max_length=150, null=True, blank=True)
    schema_name = models.CharField(max_length=63, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    organizational_id = models.CharField(max_length=20, unique=True, blank=True, null=True)
    unique_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, null=True)

    logo = models.URLField(null=True, blank=True)
    email_host = models.CharField(max_length=255, null=True, blank=True)
    email_port = models.IntegerField(null=True, blank=True)
    email_use_ssl = models.BooleanField(default=True)
    email_host_user = models.EmailField(null=True, blank=True)
    email_host_password = models.CharField(max_length=255, null=True, blank=True)
    default_from_email = models.EmailField(null=True, blank=True)
    about_us = models.TextField(null=True, blank=True)

    auto_create_schema = True
    auto_drop_schema = False

    def save(self, *args, **kwargs):
        if not self.schema_name or self.schema_name.strip() == '':
            self.schema_name = self.name.lower().replace(' ', '_').replace('-', '_')

        if not re.match(r'^[a-z0-9_]+$', self.schema_name):
            raise ValueError("Schema name can only contain lowercase letters, numbers, or underscores.")

        if not self.organizational_id:
            with transaction.atomic():
                last_id = Tenant.objects.all().count() + 1
                self.organizational_id = f"TEN-{str(last_id).zfill(4)}"

        logger.info(f"Saving tenant {self.name} with schema: {self.schema_name}, Org ID: {self.organizational_id}")
        super().save(*args, **kwargs)

class Domain(DomainMixin):
    pass