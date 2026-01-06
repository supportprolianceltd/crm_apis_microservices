# core/models.py (updated with GlobalUser model fixed for reverse accessor clashes)

import uuid
import logging
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from django_tenants.models import TenantMixin, DomainMixin
from django_tenants.utils import tenant_context, get_public_schema_name
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager, Group, Permission
from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)

class Tenant(TenantMixin):
    # NEW: Suspension status field
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('suspended', 'Suspended'),
        ('overdue', 'Overdue'),
    ]
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='active',
        help_text="Tenant suspension status"
    )

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

    # 🎨 Tenant branding colors
    color_validator = RegexValidator(
        regex=r'^#(?:[0-9a-fA-F]{3}){1,2}$',
        message="Color must be a valid hex code (e.g. #FF0000)"
    )

    primary_color = models.CharField(
        max_length=7,
        validators=[color_validator],
        default="#FF0000",
        help_text="Tenant primary theme color in HEX format"
    )

    secondary_color = models.CharField(
        max_length=7,
        validators=[color_validator],
        default="#FADBD8",
        help_text="Tenant secondary theme color in HEX format"
    )

    # 🏦 Investment & Company Settings
    account_name = models.CharField(max_length=255, blank=True, null=True, help_text="Bank account name")
    bank_name = models.CharField(max_length=255, blank=True, null=True, help_text="Bank name")
    account_number = models.CharField(max_length=50, blank=True, null=True, help_text="Bank account number")
    
    # 📈 ROI Settings
    roi_percent = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=40.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Annual ROI percentage"
    )
    
    roi_frequency = models.CharField(
        max_length=20,
        choices=[
            ('Monthly', 'Monthly'),
            ('On Demand', 'On Demand'),
        ],
        default='Monthly',
        help_text="ROI payment frequency"
    )
    
    min_withdrawal_months = models.PositiveIntegerField(
        default=4,
        help_text="Minimum months before principal withdrawal"
    )
    
    # 🔢 Policy Settings
    unique_policy_prefix = models.CharField(
        max_length=10, 
        default='APP',
        help_text="Prefix for unique policy numbers"
    )
    
    next_policy_number = models.PositiveIntegerField(
        default=200000,
        help_text="Next available policy number"
    )
    
    # 📋 KYC Settings
    KYC_METHOD_CHOICES = [
        ('passport', 'Passport Only'),
        ('passport_utility', 'Passport + Utility Bill'),
        ('passport_id', 'Passport + Government ID'),
        ('passport_utility_id', 'Passport + Utility Bill + Government ID'),
        ('custom', 'Other (specify)'),
    ]
    
    kyc_method = models.CharField(
        max_length=20,
        choices=KYC_METHOD_CHOICES,
        default='passport',
        help_text="KYC verification requirements"
    )
    
    kyc_custom = models.TextField(
        blank=True, 
        null=True,
        help_text="Custom KYC requirements description"
    )

    auto_create_schema = True

    def save(self, *args, **kwargs):
        # Auto-generate schema_name if not provided
        if not self.schema_name or self.schema_name.strip() == '':
            self.schema_name = self.name.lower().replace(' ', '_').replace('-', '_')

        # Auto-generate organizational_id (handle deleted tenants by finding max existing ID)
        if not self.organizational_id:
            with transaction.atomic():
                # Find the highest existing organizational_id number
                existing_ids = Tenant.objects.exclude(organizational_id__isnull=True).values_list('organizational_id', flat=True)
                max_num = 0
                for org_id in existing_ids:
                    if org_id and org_id.startswith('TEN-'):
                        try:
                            num = int(org_id.split('-')[1])
                            if num > max_num:
                                max_num = num
                        except (IndexError, ValueError):
                            continue
                
                # Increment from the highest existing number
                next_num = max_num + 1
                self.organizational_id = f"TEN-{str(next_num).zfill(4)}"

        logger.info(
            f"Saving tenant {self.name} with schema: {self.schema_name}, Org ID: {self.organizational_id}"
        )
        super().save(*args, **kwargs)

    def get_next_policy_number(self):
        """Get next policy number and increment"""
        next_num = self.next_policy_number
        self.next_policy_number += 1
        self.save(update_fields=['next_policy_number'])
        return f"{self.unique_policy_prefix}{next_num}"

    def get_kyc_requirements(self):
        """Get formatted KYC requirements"""
        if self.kyc_method == 'custom':
            return self.kyc_custom or "Custom KYC requirements"
        return dict(self.KYC_METHOD_CHOICES).get(self.kyc_method, "Passport Only")

    def __str__(self):
        return f"{self.name} ({self.schema_name})"

    class Meta:
        db_table = 'core_tenant'


class Domain(DomainMixin):
    pass  # Uses Tenant FK by default


class Branch(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='branches')
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=255, blank=True)
    is_head_office = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('tenant', 'name')

    def __str__(self):
        return f"{self.tenant.name} - {self.name}"


class Module(models.Model):
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.name} ({'Active' if self.is_active else 'Inactive'})"


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
    module = models.ForeignKey(Module, on_delete=models.CASCADE)
    can_view = models.BooleanField(default=False)
    can_create = models.BooleanField(default=False)
    can_edit = models.BooleanField(default=False)
    can_delete = models.BooleanField(default=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('role', 'module', 'tenant')

    def __str__(self):
        return f"{self.role} - {self.module.name} ({self.tenant.name})"


class AIDecisionLog(models.Model):
    decision_type = models.CharField(max_length=100)
    confidence_score = models.FloatField()
    model_version = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.decision_type} (Score: {self.confidence_score}) - {self.tenant.name}"


class TenantConfig(models.Model):
    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE)
    logo = models.URLField(null=True, blank=True)
    custom_fields = models.JSONField(default=dict)
    email_templates = models.JSONField(default=dict)

    def __str__(self):
        return f"Config for {self.tenant.name}"


class UsernameIndex(models.Model):
    username = models.CharField(max_length=150, unique=True, db_index=True)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    user_id = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = f"{get_public_schema_name()}_usernameindex"  # Explicit public table

    def __str__(self):
        return f"{self.username} → {self.tenant.schema_name}"

    def save(self, *args, **kwargs):
        # Global uniqueness check (public schema)
        if UsernameIndex.objects.filter(username=self.username).exclude(pk=self.pk).exists():
            raise ValueError(f"Username '{self.username}' already exists globally.")
        super().save(*args, **kwargs)


# core/models.py - GlobalUser section only



class GlobalUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        global_user = self.model(email=email, **extra_fields)
        global_user.set_password(password)
        global_user.save(using=self._db)
        return global_user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        return self.create_user(email, password, **extra_fields)

# core/models.py - Enhanced GlobalUser
class GlobalUser(AbstractBaseUser):
    email = models.EmailField(_('email address'), unique=True)
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    username = models.CharField(max_length=150, unique=True, null=True, blank=True)
    role = models.CharField(max_length=20, default='super-admin')
    
    # Authentication fields
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_superuser = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    
    # Track login attempts for security
    login_attempts = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    
    # Terms acceptance
    has_accepted_terms = models.BooleanField(default=False)
    
    objects = GlobalUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    class Meta:
        db_table = 'core_globaluser'
        verbose_name = 'Global User'
        verbose_name_plural = 'Global Users'

    def __str__(self):
        return self.email

    def get_full_name(self):
        return f'{self.first_name} {self.last_name}'.strip()

    def get_short_name(self):
        return self.first_name or self.email

    def has_perm(self, perm, obj=None):
        return self.is_superuser

    def has_perms(self, perm_list, obj=None):
        return self.is_superuser

    def has_module_perms(self, app_label):
        return self.is_superuser

    def is_locked(self):
        if self.locked_until and timezone.now() < self.locked_until:
            return True
        return False

    def reset_login_attempts(self):
        self.login_attempts = 0
        self.locked_until = None
        self.save()

    def increment_login_attempts(self):
        self.login_attempts += 1
        if self.login_attempts >= 5:  # Lock after 5 attempts
            self.locked_until = timezone.now() + timedelta(minutes=30)
        self.save()

class GlobalActivity(models.Model):
    # SOLUTION: Use string references instead of direct imports to break circular dependency
    global_user = models.CharField(
        max_length=36, 
        blank=True, 
        null=True, 
        help_text="Super-admin user ID from public tenant"
    )
    
    affected_tenant = models.ForeignKey(
        Tenant,  # String reference with app name
        on_delete=models.CASCADE, 
        related_name='global_activities'
    )
    
    ACTION_CHOICES = (
        ('platform_user_created', 'Platform User Created'),
        ('platform_user_updated', 'Platform User Updated'),
        ('platform_user_deleted', 'Platform User Deleted'),
        ('tenant_created', 'Tenant Created'),
        ('tenant_updated', 'Tenant Updated'),
        ('tenant_deleted', 'Tenant Deleted'),
        ('tenant_suspended', 'Tenant Suspended'),  # NEW: For suspension
        ('tenant_activated', 'Tenant Activated'),  # NEW: For activation
        ('global_keypair_generated', 'Global Keypair Generated'),
        ('system_backup_created', 'System Backup Created'),
        ('audit_export_requested', 'Audit Export Requested'),
        ('tenant_quota_exceeded', 'Tenant Quota Exceeded'),
        ('global_login_failed', 'Global Login Failed'),
        ('security_alert_triggered', 'Security Alert Triggered'),
    )
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    
    performed_by = models.CharField(
        max_length=36, 
        blank=True, 
        null=True, 
        help_text="User ID who performed the action"
    )
    
    global_correlation_id = models.UUIDField(null=True, blank=True, default=uuid.uuid4)
    
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    success = models.BooleanField(null=True, help_text="Indicates if the action was successful.")

    class Meta:
        verbose_name = "Global Activity"
        verbose_name_plural = "Global Activities"
        db_table = 'core_globalactivity'
        indexes = [
            models.Index(fields=['affected_tenant', 'timestamp']),
            models.Index(fields=['affected_tenant', 'action', 'timestamp']),
            models.Index(fields=['global_user', 'timestamp']),
            models.Index(fields=['performed_by', 'timestamp']),
            models.Index(fields=['success', 'timestamp']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['global_correlation_id']),
        ]
        ordering = ['-timestamp']

    def __str__(self):
        tenant_name = self.affected_tenant.schema_name if self.affected_tenant else 'unknown'
        return f"{self.action} for tenant {tenant_name} at {self.timestamp}"

    def save(self, *args, **kwargs):
        if not self.global_correlation_id:
            self.global_correlation_id = uuid.uuid4()
        super().save(*args, **kwargs)

    # core/models.py - Add to GlobalActivity class

    @classmethod
    def log_platform_action(cls, action, affected_tenant, performed_by_id=None, details=None, request=None):
        """Helper method for consistent global logging"""
        ip_address = request.META.get('REMOTE_ADDR') if request else None
        user_agent = request.META.get('HTTP_USER_AGENT', '') if request else ''
        
        return cls.objects.create(
            global_user=performed_by_id if performed_by_id else None,
            affected_tenant=affected_tenant,
            action=action,
            performed_by=performed_by_id,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent,
            success=True
        )