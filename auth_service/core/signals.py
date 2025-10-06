from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django_tenants.utils import tenant_context
from .models import UsernameIndex
import logging
from users.models import CustomUser



logger = logging.getLogger('core')


@receiver(post_save, sender=CustomUser)
def sync_username_index(sender, instance, created, **kwargs):
    if created or (not created and kwargs.get('update_fields') and 'username' in kwargs['update_fields']):
        with tenant_context(instance.tenant):
            # Check global uniqueness first (in public schema)
            if UsernameIndex.objects.filter(username=instance.username).exists():
                raise ValueError(f"Username '{instance.username}' already exists in another tenant.")
            
            # Upsert index
            UsernameIndex.objects.update_or_create(
                username=instance.username,
                defaults={'tenant': instance.tenant, 'user_id': instance.id}
            )
            logger.info(f"Username index synced for '{instance.username}' in '{instance.tenant.schema_name}'")

@receiver(pre_delete, sender=CustomUser)
def remove_username_index(sender, instance, **kwargs):
    UsernameIndex.objects.filter(username=instance.username, tenant=instance.tenant).delete()
    logger.info(f"Username index removed for '{instance.username}'")