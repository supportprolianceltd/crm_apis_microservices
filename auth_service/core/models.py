from django_tenants.models import TenantMixin, DomainMixin
import logging
import uuid
from django_tenants.models import TenantMixin
from django.db import models, transaction
from django.db import models
from django_tenants.utils import tenant_context
from django.utils import timezone
from django.db import models
from django_tenants.models import TenantMixin, DomainMixin
from django.utils.translation import gettext_lazy as _
from django_tenants.utils import get_public_schema_name


logger = logging.getLogger('core')


class Tenant(TenantMixin):
    name = models.CharField(max_length=100)
    title = models.CharField(max_length=150, null=True, blank=True)
    schema_name = models.CharField(max_length=63, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # ✅ NEW FIELDS
    organizational_id = models.CharField(max_length=20, unique=True, blank=True, null=True)
    unique_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, null=True)

    # Other existing fields3
    logo = models.URLField(null=True, blank=True)
    email_host = models.CharField(max_length=255, null=True, blank=True)
    email_port = models.IntegerField(null=True, blank=True)
    email_use_ssl = models.BooleanField(default=True)
    email_host_user = models.EmailField(null=True, blank=True)
    email_host_password = models.CharField(max_length=255, null=True, blank=True)
    default_from_email = models.EmailField(null=True, blank=True)
    about_us = models.TextField(null=True, blank=True)

    auto_create_schema = True

    def save(self, *args, **kwargs):
        # Set schema_name from name if not already set
        if not self.schema_name or self.schema_name.strip() == '':
            self.schema_name = self.name.lower().replace(' ', '_').replace('-', '_')

        # Generate organizational_id if not already set
        if not self.organizational_id:
            with transaction.atomic():
                last_id = Tenant.objects.all().count() + 1
                self.organizational_id = f"TEN-{str(last_id).zfill(4)}"

        logger.info(f"Saving tenant {self.name} with schema: {self.schema_name}, Org ID: {self.organizational_id}")
        super().save(*args, **kwargs)


class Domain(DomainMixin):
    tenant = models.ForeignKey('core.Tenant', related_name='domain_set', on_delete=models.CASCADE)


class Branch(models.Model):
    tenant = models.ForeignKey('Tenant', on_delete=models.CASCADE, related_name='branches')
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=255, blank=True)  # For interview locations
    is_head_office = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('tenant', 'name')

    def __str__(self):
        return f"{self.tenant.name} - {self.name}"

class Module(models.Model):
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    tenant = models.ForeignKey('Tenant', on_delete=models.CASCADE)

class RolePermission(models.Model):
    role = models.CharField(max_length=20, choices=[
        ('admin', 'Admin'),
        ('hr', 'HR'),
        ('carer', 'Carer'),
        ('client', 'Client'),
        ('family', 'Family'),
        ('auditor', 'Auditor'),
        ('tutor', 'Tutor'),
        ('assessor', 'Assessor'),
        ('iqa', 'IQA'),
        ('eqa', 'EQA'),
        ('recruiter', 'Recruiter'),
        ('team_manager', 'Team Manager'),
    ])
    module = models.ForeignKey('Module', on_delete=models.CASCADE)
    can_view = models.BooleanField(default=False)
    can_create = models.BooleanField(default=False)
    can_edit = models.BooleanField(default=False)
    can_delete = models.BooleanField(default=False)
    tenant = models.ForeignKey('Tenant', on_delete=models.CASCADE)

class AIDecisionLog(models.Model):
    decision_type = models.CharField(max_length=100)
    confidence_score = models.FloatField()
    model_version = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    tenant = models.ForeignKey('Tenant', on_delete=models.CASCADE)

class TenantConfig(models.Model):
    tenant = models.OneToOneField('Tenant', on_delete=models.CASCADE)
    logo = models.URLField(null=True, blank=True)  # Store Supabase public URL
    custom_fields = models.JSONField(default=dict)
    email_templates = models.JSONField(default=dict)





# NEW: Shared UsernameIndex for global uniqueness
class UsernameIndex(models.Model):
    username = models.CharField(max_length=150, unique=True, db_index=True)  # Global unique
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    user_id = models.PositiveIntegerField()  # Denormalized user PK (for quick ref)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = f"{get_public_schema_name()}.core_usernameindex"  # Explicit public table

    def __str__(self):
        return f"{self.username} → {self.tenant.schema_name}"

    def save(self, *args, **kwargs):
        # Auto-sync on update (e.g., if username changes)
        if self.pk:  # Update
            old = UsernameIndex.objects.get(pk=self.pk)
            if old.username != self.username:
                # Handle rename: Ensure no conflict
                if UsernameIndex.objects.filter(username=self.username).exclude(pk=self.pk).exists():
                    raise ValueError(f"Username '{self.username}' already exists globally.")
        super().save(*args, **kwargs)