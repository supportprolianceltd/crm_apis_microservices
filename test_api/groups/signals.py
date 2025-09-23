from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.conf import settings
import logging
import requests
from .models import Group, GroupMembership
from activitylog.models import ActivityLog

logger = logging.getLogger('groups')

def get_tenant_name(tenant_id):
    """Helper function to fetch tenant name from auth-service."""
    try:
        tenant_response = requests.get(
            f"{settings.AUTH_SERVICE_URL}/api/tenant/tenants/{tenant_id}/",
            headers={'Authorization': f'Bearer {settings.INTERNAL_AUTH_TOKEN}'}
        )
        if tenant_response.status_code == 200:
            tenant_data = tenant_response.json()
            return tenant_data.get('name')
        logger.error(f"Failed to fetch tenant {tenant_id} from auth_service")
        return None
    except Exception as e:
        logger.error(f"Error fetching tenant name for {tenant_id}: {str(e)}")
        return None

@receiver(post_save, sender=Group)
def log_group_activity(sender, instance, created, **kwargs):
    tenant_name = instance.tenant_name or get_tenant_name(instance.tenant_id)
    activity_type = 'group_created' if created else 'group_updated'
    ActivityLog.objects.create(
        tenant_id=instance.tenant_id,
        tenant_name=tenant_name,
        activity_type=activity_type,
        details=f'Group "{instance.name}" was {"created" if created else "updated"}',
        status='success'
    )
    logger.info(f"[Tenant {instance.tenant_id}] Group {instance.id} {'created' if created else 'updated'}: {instance.name}")

@receiver(post_delete, sender=Group)
def log_group_deletion(sender, instance, **kwargs):
    tenant_name = instance.tenant_name or get_tenant_name(instance.tenant_id)
    ActivityLog.objects.create(
        tenant_id=instance.tenant_id,
        tenant_name=tenant_name,
        activity_type='group_deleted',
        details=f'Group "{instance.name}" was deleted',
        status='system'
    )
    logger.info(f"[Tenant {instance.tenant_id}] Group {instance.id} deleted: {instance.name}")

@receiver(post_save, sender=GroupMembership)
def log_membership_activity(sender, instance, created, **kwargs):
    tenant_name = instance.group.tenant_name or get_tenant_name(instance.group.tenant_id)
    activity_type = 'group_member_added' if created else 'group_member_updated'
    ActivityLog.objects.create(
        tenant_id=instance.group.tenant_id,
        tenant_name=tenant_name,
        user_id=instance.user_id,
        activity_type=activity_type,
        details=f'User {instance.user_id} {"added to" if created else "membership updated in"} group "{instance.group.name}"',
        status='success'
    )
    logger.info(
        f"[Tenant {instance.group.tenant_id}] GroupMembership {instance.id} {'created' if created else 'updated'}: "
        f"User {instance.user_id} in group {instance.group.name}"
    )

@receiver(post_delete, sender=GroupMembership)
def log_membership_removal(sender, instance, **kwargs):
    tenant_name = instance.group.tenant_name or get_tenant_name(instance.group.tenant_id)
    ActivityLog.objects.create(
        tenant_id=instance.group.tenant_id,
        tenant_name=tenant_name,
        user_id=instance.user_id,
        activity_type='group_member_removed',
        details=f'User {instance.user_id} removed from group "{instance.group.name}"',
        status='system'
    )
    logger.info(
        f"[Tenant {instance.group.tenant_id}] GroupMembership {instance.id} deleted: "
        f"User {instance.user_id} from group {instance.group.name}"
    )