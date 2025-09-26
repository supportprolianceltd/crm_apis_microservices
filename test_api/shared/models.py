import uuid
import re
import logging
from django.db import models
from django_tenants.models import TenantMixin, DomainMixin

logger = logging.getLogger(__name__)


class Tenant(TenantMixin):
    name = models.CharField(max_length=100)
    title = models.CharField(max_length=150, null=True, blank=True)
    schema_name = models.CharField(max_length=63, unique=True)  # Must be client-supplied
    created_at = models.DateTimeField(auto_now_add=True)

    organizational_id = models.CharField(max_length=20, unique=True)  # Must be client-supplied
    unique_id = models.UUIDField(editable=True, unique=True)  # Must be client-supplied

    # Branding and About Info
    logo = models.URLField(null=True, blank=True)
    about_us = models.TextField(null=True, blank=True)

    # Email Configurations
    email_host = models.CharField(max_length=255, null=True, blank=True)
    email_port = models.IntegerField(null=True, blank=True)
    email_use_ssl = models.BooleanField(default=True)
    email_host_user = models.EmailField(null=True, blank=True)
    email_host_password = models.CharField(max_length=255, null=True, blank=True)
    default_from_email = models.EmailField(null=True, blank=True)

    # Required by django-tenants
    auto_create_schema = True
    auto_drop_schema = False

    def save(self, *args, **kwargs):
        if not self.schema_name:
            raise ValueError("schema_name is required.")
        if not re.match(r'^[a-z0-9_]+$', self.schema_name):
            raise ValueError("schema_name can only contain lowercase letters, numbers, or underscores.")

        if not self.organizational_id:
            raise ValueError("organizational_id is required and must be unique.")

        if not self.unique_id:
            raise ValueError("unique_id is required and must be a valid UUID.")

        logger.info(
            f"Saving tenant: name='{self.name}', schema='{self.schema_name}', "
            f"org_id='{self.organizational_id}', uuid='{self.unique_id}'"
        )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.schema_name})"


class Domain(DomainMixin):
    # Fields inherited:
    # - domain
    # - is_primary
    # - tenant (FK)
    def __str__(self):
        return f"{self.domain} (Primary: {self.is_primary})"
