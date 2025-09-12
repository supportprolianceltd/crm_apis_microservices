from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.core.exceptions import ValidationError
import logging
import uuid
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils.translation import gettext as _
from django_tenants.utils import tenant_context
from groups.models import Group, GroupMembership, Role
import random

logger = logging.getLogger(__name__)

class CustomUserManager(BaseUserManager):
    
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Users must have an email address')
        email = self.normalize_email(email)
        if 'role' not in extra_fields:
            extra_fields['role'] = 'carer'  # Default role
        if 'status' not in extra_fields:
            extra_fields['status'] = 'active'  # Default to active
        user = self.model(email=email, **extra_fields)
        if password:
            self.validate_password(password)
            user.set_password(password)
        user.save(using=self._db)
        UserActivity.objects.create(
            user=user,
            activity_type='user_management',
            details=f'New user created with email: {email}',
            status='success'
        )
        return user


    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'admin')
        extra_fields.setdefault('status', 'active')
        extra_fields.setdefault('is_locked', False)
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        user = self.create_user(email, password, **extra_fields)
        UserActivity.objects.create(
            user=user,
            activity_type='user_management',
            details=f'New superuser created with email: {email}',
            status='success'
        )
        return user

    def validate_password(self, password):
        if len(password) < 8:
            raise ValidationError(
                _("Password must be at least 8 characters long."),
                code='password_too_short',
            )



def profile_picture_upload_path(instance, filename):
    # Store profile pictures in a user-specific directory
    return f'profile_pics/{instance.id}/{filename}'

class CustomUser(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=30, blank=True)
    role = models.CharField(max_length=20, blank=True, help_text="User role code (e.g., admin, instructor)")
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(null=True, blank=True)
    is_locked = models.BooleanField(default=False)
    status = models.CharField(max_length=20, default='pending')
    tenant = models.ForeignKey('core.Tenant', on_delete=models.CASCADE, null=True)
    is_deleted = models.BooleanField(default=False)
    login_attempts = models.PositiveIntegerField(default=0)
    phone = models.CharField(max_length=20, blank=True, null=True)
    title = models.CharField(max_length=100, blank=True)
    bio = models.TextField(blank=True)
    facebook_link = models.URLField(blank=True)
    twitter_link = models.URLField(blank=True)
    linkedin_link = models.URLField(blank=True)
    profile_picture = models.CharField(max_length=255, blank=True, null=True)
    student_id = models.CharField(max_length=20, unique=True, blank=True, null=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    def save(self, *args, **kwargs):
        created = not self.pk
        # Generate or increment student_id if role is learners and it's missing
        if self.role == "learners" and not self.student_id and self.tenant:
            prefix = (self.tenant.name[:3] if self.tenant.name else "TEN").upper()
            base_prefix = f"{prefix}-"
            existing_ids = (
                CustomUser.objects.filter(student_id__startswith=base_prefix)
                .values_list("student_id", flat=True)
            )
            max_number = 0
            for sid in existing_ids:
                try:
                    number = int(sid.split('-')[-1])
                    if number > max_number:
                        max_number = number
                except (IndexError, ValueError):
                    continue
            new_student_id = f"{prefix}-{str(max_number + 1).zfill(5)}"
            self.student_id = new_student_id

        # Prevent saving a student with empty student_id
        if self.role == "student" and not self.student_id:
            raise ValidationError("Student ID must be set for student users.")

        super().save(*args, **kwargs)

        # Generate student ID for students
        if created or kwargs.get('update_fields', None) in (None, ['role']):
            self.sync_group_memberships()


    def sync_group_memberships(self):
        """Sync user with system groups based on their role."""
        from django.db import connection
        from groups.models import Group, GroupMembership, Role
        tenant = connection.tenant
        if not tenant:
            return
        with tenant_context(tenant):
            system_groups = Group.objects.filter(is_system=True)
            for group in system_groups:
                should_be_member = group.role.code == self.role
                membership_exists = GroupMembership.objects.filter(user=self, group=group).exists()
                if should_be_member and not membership_exists:
                    GroupMembership.objects.create(
                        user=self,
                        group=group,
                        role=group.role,
                        is_active=True,
                        is_primary=(self.role == group.role.code)
                    )
                    # Log activity
                    UserActivity.objects.create(
                        user=self,
                        activity_type='group_membership_added',
                        details=f'User added to group {group.name} via role sync',
                        status='success'
                    )
                elif not should_be_member and membership_exists:
                    GroupMembership.objects.filter(user=self, group=group).delete()
                    # Log activity
                    UserActivity.objects.create(
                        user=self,
                        activity_type='group_membership_removed',
                        details=f'User removed from group {group.name} via role sync',
                        status='success'
                    )

    def __str__(self):
        return self.email

    def update_profile(self, updated_fields):
        for field, value in updated_fields.items():
            setattr(self, field, value)
        self.save()

    def lock_account(self, reason):
        self.is_locked = True
        self.save()
        UserActivity.objects.create(
            user=self,
            activity_type='account_locked',
            details=reason,
            status='success'
        )

    def unlock_account(self, reason):
        self.is_locked = False
        self.save()
        UserActivity.objects.create(
            user=self,
            activity_type='account_unlocked',
            details=reason,
            status='success'
        )

    def suspend_account(self, reason):
        self.status = 'suspended'
        self.save()
        UserActivity.objects.create(
            user=self,
            activity_type='account_suspended',
            details=reason,
            status='success'
        )

    def activate_account(self):
        self.status = 'active'
        self.save()
        UserActivity.objects.create(
            user=self,
            activity_type='account_activated',
            details='Account activated',
            status='success'
        )

        
    def reset_login_attempts(self):
        self.login_attempts = 0
        self.last_login = timezone.now()
        self.save()
        UserActivity.objects.create(
            user=self,
            activity_type='login_attempts_reset',
            details='Login attempts reset by admin',
            status='success'
        )

    def increment_login_attempts(self):
        self.login_attempts += 1
        if self.login_attempts >= 5:
            self.is_locked = True
            UserActivity.objects.create(
                user=self,
                activity_type='account_locked',
                details='Account locked due to excessive login attempts',
                status='system'
            )
        self.save()

    def delete_account(self, reason):
        self.is_deleted = True
        self.is_active = False
        self.save()
        UserActivity.objects.create(
            user=self,
            activity_type='account_deleted',
            details=reason,
            status='success'
        )

  

    # In your CustomUser model:
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def is_anonymous(self):
        return False  # Or implement your logic

    @property
    def is_authenticated(self):
        return True   # Or implement your logic

    class Meta:
        verbose_name = _('User')
        verbose_name_plural = _('Users')


class UserProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    modules = models.ManyToManyField('core.Module', blank=True)

    def __str__(self):
        return f"Profile for {self.user.email}"




class UserActivity(models.Model):
    STATUS_CHOICES = (
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('pending', 'Pending'),
        ('in-progress', 'In Progress'),
        ('system', 'System'),
    )
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='activities',
        blank=True,
        null=True
    )
    activity_type = models.CharField(max_length=50)
    details = models.TextField()
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    device_info = models.CharField(max_length=200, blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='success'
    )

    class Meta:
        verbose_name = _('Activity Log')
        verbose_name_plural = _('Activity Logs')
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['user', 'activity_type']),
            models.Index(fields=['activity_type', 'status']),
        ]

    def __str__(self):
        user_info = self.user.email if self.user else 'System'
        return f"{user_info} - {self.activity_type} ({self.timestamp})"

    def save(self, *args, **kwargs):
        if not self.id:
            self.timestamp = timezone.now()
        super().save(*args, **kwargs)




class FailedLogin(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, null=True, blank=True)
    ip_address = models.GenericIPAddressField()
    username = models.CharField(max_length=150)
    timestamp = models.DateTimeField(default=timezone.now)
    attempts = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=(('active', 'Active'), ('blocked', 'Blocked')))

    class Meta:
        indexes = [models.Index(fields=['ip_address', 'timestamp'])]

    def __str__(self):
        return f"Failed login: {self.username} from {self.ip_address} at {self.timestamp}"

class BlockedIP(models.Model):
    ip_address = models.GenericIPAddressField(unique=True)
    reason = models.TextField()
    timestamp = models.DateTimeField(default=timezone.now)
    action = models.CharField(max_length=50, choices=(('auto-blocked', 'Auto-blocked'), ('manual-block', 'Manual Block')))

    class Meta:
        indexes = [models.Index(fields=['ip_address', 'timestamp'])]

    def __str__(self):
        return f"Blocked IP: {self.ip_address} at {self.timestamp}"

class VulnerabilityAlert(models.Model):
    SEVERITY_CHOICES = (
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
    )
    title = models.CharField(max_length=255)
    component = models.CharField(max_length=100)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    detected = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=(('pending', 'Pending'), ('in-progress', 'In Progress'), ('resolved', 'Resolved')))

    class Meta:
        indexes = [models.Index(fields=['severity', 'detected'])]

    def __str__(self):
        return f"{self.severity} - {self.title} ({self.status})"

class ComplianceReport(models.Model):
    type = models.CharField(max_length=50, choices=(('GDPR', 'GDPR'), ('CCPA', 'CCPA'), ('PCI DSS', 'PCI DSS')))
    status = models.CharField(max_length=20, choices=(('compliant', 'Compliant'), ('pending-review', 'Pending Review')))
    last_audit = models.DateField()
    next_audit = models.DateField()
    tenant = models.ForeignKey('core.Tenant', on_delete=models.CASCADE)

    class Meta:
        indexes = [models.Index(fields=['type', 'status'])]

    def __str__(self):
        return f"{self.type} - {self.status}"
    


class PasswordResetToken(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE)
    token = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)

    class Meta:
        unique_together = ('user', 'tenant', 'token')

    def __str__(self):
        return f"Password reset token for {self.user.email} in tenant {self.tenant.schema_name}"
