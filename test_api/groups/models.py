from django.db import models
from django.utils.translation import gettext as _
import logging
from activitylog.models import ActivityLog

logger = logging.getLogger('group_management')

class Role(models.Model):
    id = models.AutoField(primary_key=True)  # Changed to AutoField for simplicity
    tenant_id = models.CharField(max_length=36, blank=False, null=False)  # Store Tenant ID
    tenant_name = models.CharField(max_length=255, blank=True, null=True, help_text="Tenant name for reference")
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    permissions = models.JSONField(default=list)
    is_default = models.BooleanField(default=False)
    is_system = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} (Tenant: {self.tenant_id})"

    class Meta:
        verbose_name = _('Role')
        verbose_name_plural = _('Roles')
        unique_together = ['tenant_id', 'name']
        indexes = [
            models.Index(fields=['tenant_id', 'code'], name='idx_role_tenant_code'),
        ]

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        activity_type = 'role_created' if is_new else 'role_updated'
        ActivityLog.objects.create(
            tenant_id=self.tenant_id,
            tenant_name=self.tenant_name,
            activity_type=activity_type,
            details=f'Role "{self.name}" {"created" if is_new else "updated"}',
            status='success'
        )
        logger.info(f"Role {self.id} {'created' if is_new else 'updated'} for tenant {self.tenant_id}")

    def delete(self, *args, **kwargs):
        ActivityLog.objects.create(
            tenant_id=self.tenant_id,
            tenant_name=self.tenant_name,
            activity_type='role_deleted',
            details=f'Role "{self.name}" deleted',
            status='success'
        )
        logger.info(f"Role {self.id} deleted for tenant {self.tenant_id}")
        super().delete(*args, **kwargs)

class Group(models.Model):
    id = models.AutoField(primary_key=True)
    tenant_id = models.CharField(max_length=36, blank=False, null=False)
    tenant_name = models.CharField(max_length=255, blank=True, null=True, help_text="Tenant name for reference")
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    role_id = models.CharField(max_length=36, blank=True, null=True)  # Store Role ID
    is_active = models.BooleanField(default=True)
    is_system = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} (Tenant: {self.tenant_id})"

    class Meta:
        verbose_name = _('Group')
        verbose_name_plural = _('Groups')
        unique_together = ['tenant_id', 'name']
        indexes = [
            models.Index(fields=['tenant_id', 'is_active'], name='idx_group_tenant_active'),
        ]

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        activity_type = 'group_created' if is_new else 'group_updated'
        ActivityLog.objects.create(
            tenant_id=self.tenant_id,
            tenant_name=self.tenant_name,
            activity_type=activity_type,
            details=f'Group "{self.name}" {"created" if is_new else "updated"}',
            status='success'
        )
        logger.info(f"Group {self.id} {'created' if is_new else 'updated'} for tenant {self.tenant_id}")

    def delete(self, *args, **kwargs):
        ActivityLog.objects.create(
            tenant_id=self.tenant_id,
            tenant_name=self.tenant_name,
            activity_type='group_deleted',
            details=f'Group "{self.name}" deleted',
            status='success'
        )
        logger.info(f"Group {self.id} deleted for tenant {self.tenant_id}")
        super().delete(*args, **kwargs)

class GroupMembership(models.Model):
    id = models.AutoField(primary_key=True)
    tenant_id = models.CharField(max_length=36, blank=False, null=False)
    tenant_name = models.CharField(max_length=255, blank=True, null=True, help_text="Tenant name for reference")
    user_id = models.CharField(max_length=36, blank=True, null=True)  # Store User ID from auth-service
    group_id = models.CharField(max_length=36, blank=True, null=True)  # Store Group ID
    role_id = models.CharField(max_length=36, blank=True, null=True)  # Store Role ID
    is_active = models.BooleanField(default=True)
    is_primary = models.BooleanField(default=False)

    def __str__(self):
        return f"User {self.user_id} in Group {self.group_id} (Tenant: {self.tenant_id})"

    class Meta:
        verbose_name = _('Group Membership')
        verbose_name_plural = _('Group Memberships')
        unique_together = ['tenant_id', 'user_id', 'group_id']
        indexes = [
            models.Index(fields=['tenant_id', 'user_id'], name='idx_membership_tenant_user'),
            models.Index(fields=['tenant_id', 'group_id'], name='idx_membership_tenant_group'),
        ]

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        activity_type = 'group_member_added' if is_new else 'group_membership_updated'
        ActivityLog.objects.create(
            tenant_id=self.tenant_id,
            tenant_name=self.tenant_name,
            user_id=self.user_id,
            activity_type=activity_type,
            details=f'User {self.user_id} {"added to" if is_new else "updated in"} group {self.group_id}',
            status='success'
        )
        logger.info(f"GroupMembership {self.id} {'created' if is_new else 'updated'} for tenant {self.tenant_id}")

    def delete(self, *args, **kwargs):
        ActivityLog.objects.create(
            tenant_id=self.tenant_id,
            tenant_name=self.tenant_name,
            user_id=self.user_id,
            activity_type='group_member_removed',
            details=f'User {self.user_id} removed from group {self.group_id}',
            status='success'
        )
        logger.info(f"GroupMembership {self.id} deleted for tenant {self.tenant_id}")
        super().delete(*args, **kwargs)