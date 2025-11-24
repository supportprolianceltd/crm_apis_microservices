# core/signals.py
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django_tenants.utils import tenant_context
from .models import UsernameIndex
import logging
from users.models import CustomUser
from .models import (
    Tenant, Domain, Module, TenantConfig, Branch, GlobalActivity, GlobalUser
)
from django_tenants.utils import get_public_schema_name
from .constants import FieldNames


logger = logging.getLogger('core')


@receiver(post_save, sender=CustomUser)
@receiver(post_save, sender=GlobalUser)  # Add GlobalUser support
def sync_username_index(sender, instance, created, **kwargs):
    """Sync username to global index for both CustomUser and GlobalUser"""
    if created or (not created and kwargs.get('update_fields') and FieldNames.USERNAME in kwargs['update_fields']):
        if not instance.username:
            return
            
        # Determine tenant based on model type
        if isinstance(instance, GlobalUser):
            # GlobalUser belongs to public tenant
            public_tenant = Tenant.objects.get(schema_name=get_public_schema_name())
            tenant = public_tenant
            user_id = instance.id
        else:
            # CustomUser uses its tenant
            tenant = instance.tenant
            user_id = instance.id
        
        # Check global uniqueness
        existing = UsernameIndex.objects.filter(**{FieldNames.USERNAME: instance.username}).exclude(
            **{FieldNames.USER_ID: user_id, FieldNames.TENANT: tenant}
        ).first()
        
        if existing:
            logger.error(f"Username '{instance.username}' already exists in tenant '{existing.tenant.schema_name}'")
            raise ValueError(f"Username '{instance.username}' already exists globally.")
        
        # Upsert in public schema
        UsernameIndex.objects.update_or_create(
            **{FieldNames.USERNAME: instance.username},
            defaults={FieldNames.TENANT: tenant, FieldNames.USER_ID: user_id}
        )
        logger.info(f"Username index synced: '{instance.username}' → {tenant.schema_name}")

@receiver(pre_delete, sender=CustomUser)
@receiver(pre_delete, sender=GlobalUser)  # Add GlobalUser support
def remove_username_index(sender, instance, **kwargs):
    if isinstance(instance, GlobalUser):
        public_tenant = Tenant.objects.get(schema_name=get_public_schema_name())
        UsernameIndex.objects.filter(**{FieldNames.USERNAME: instance.username, FieldNames.TENANT: public_tenant}).delete()
    else:
        UsernameIndex.objects.filter(**{FieldNames.USERNAME: instance.username, FieldNames.TENANT: instance.tenant}).delete()
    logger.info(f"Username index removed for '{instance.username}'")


@receiver(pre_delete, sender=CustomUser)
def remove_username_index(sender, instance, **kwargs):
    UsernameIndex.objects.filter(**{FieldNames.USERNAME: instance.username, FieldNames.TENANT: instance.tenant}).delete()
    logger.info(f"Username index removed for '{instance.username}'")