# users/signals.py (extend your existing file)

import logging
import threading
from django.db.models.signals import post_save, pre_delete
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.utils import timezone
from django.db import transaction
import json  # Add this import
from decimal import Decimal  # Add this for Decimal handling
# In users/signals.py
from .models import (
    CustomUser, UserActivity, InvestmentDetail, WithdrawalDetail,
    UserProfile, Document, GroupMembership  # Add more models as needed
)
from core.models import Tenant
from django_tenants.utils import tenant_context
# Logger
logger = logging.getLogger("users")

# Thread-local storage to track when we're deleting a tenant
_thread_locals = threading.local()

def is_deleting_tenant():
    """Check if we're currently deleting a tenant"""
    return getattr(_thread_locals, 'deleting_tenant', False)

def set_deleting_tenant(value):
    """Set the tenant deletion flag"""
    _thread_locals.deleting_tenant = value

@receiver(post_save, sender=CustomUser)
def log_user_activity(sender, instance, created, **kwargs):
    # Skip logging if we're deleting a tenant
    if is_deleting_tenant():
        return
    
    def _log():
        # Double-check inside the transaction
        if is_deleting_tenant():
            return
            
        tenant = instance.tenant
        action = 'user_created' if created else 'user_updated'
        details = {
            'role': instance.role,
            'status': instance.status,
            'changes': {}  # Populate with diff if updated (see below)
        }
        if not created and kwargs.get('update_fields'):
            details['changes'] = dict(zip(kwargs['update_fields'], [None] * len(kwargs['update_fields'])))  # Simplified diff

        UserActivity.objects.create(
            user=instance if action != 'user_created' else None,  # Anonymous for creation
            tenant=tenant,
            action=action,
            performed_by=instance if not created else None,  # Self for updates
            details=details,
            ip_address=None,  # Signals don't have request; use middleware for IP
            user_agent=None,
            success=True,
        )
    transaction.on_commit(_log)

@receiver(pre_delete, sender=CustomUser)
def log_user_deletion(sender, instance, **kwargs):
    """Log user deletion before the actual deletion to avoid FK constraint violation."""
    # Skip logging if we're deleting a tenant (tenant won't exist for FK)
    if is_deleting_tenant():
        return
    
    # Create activity in a separate transaction to avoid FK issues
    try:
        with transaction.atomic(using='default'):
            UserActivity.objects.create(
                user=None,  # Set to None to avoid FK constraint
                tenant=instance.tenant,
                action='user_deleted',
                performed_by=None,  # Deletion logs post-facto
                details={
                    'deleted_user_id': instance.id,
                    'email': instance.email,
                    'role': instance.role,
                    'status': instance.status
                },
                success=True,
            )
    except Exception as e:
        logger.warning(f"Could not log user deletion for {instance.email}: {str(e)}")

@receiver(post_save, sender=UserProfile)
def log_profile_activity(sender, instance, created, **kwargs):
    # Skip logging if we're deleting a tenant
    if is_deleting_tenant():
        return
    
    def _log():
        if is_deleting_tenant():
            return
            
        UserActivity.objects.create(
            user=instance.user,
            tenant=instance.user.tenant,
            action='profile_updated' if not created else 'profile_created',
            details={'employee_id': instance.employee_id},
            success=True,
        )
    transaction.on_commit(_log)


@receiver(post_save, sender=InvestmentDetail)
def log_investment_activity(sender, instance, created, **kwargs):
    # Skip logging if we're deleting a tenant
    if is_deleting_tenant():
        return
    
    def _safe_convert_value(value):
        """Safely convert Decimal and other types to JSON-serializable formats"""
        if isinstance(value, Decimal):
            return float(value)
        return value

    if created:
        action = 'investment_created'
        details = {
            "investment_amount": _safe_convert_value(instance.investment_amount),
            "roi_rate": _safe_convert_value(instance.roi_rate),
            "custom_roi_rate": _safe_convert_value(instance.custom_roi_rate),
            "remaining_balance": _safe_convert_value(instance.remaining_balance),
            "investment_id": instance.id,
        }
    else:
        action = 'investment_updated'
        details = {
            "investment_amount": _safe_convert_value(instance.investment_amount),
            "roi_rate": _safe_convert_value(instance.roi_rate),
            "custom_roi_rate": _safe_convert_value(instance.custom_roi_rate),
            "remaining_balance": _safe_convert_value(instance.remaining_balance),
            "investment_id": instance.id,
        }

    def _log():
        if is_deleting_tenant():
            return
            
        try:
            # Direct JSON serialization with proper error handling
            UserActivity.objects.create(
                user=instance.user_profile.user,
                tenant=instance.user_profile.user.tenant,
                action=action,
                performed_by=None,  # Or set from request if available
                details=details,
                success=True,
            )
            logger.info(f"Successfully logged {action} for investment {instance.id}")
        except Exception as e:
            logger.error(f"Failed to log {action} for investment {instance.id}: {str(e)}", exc_info=True)

    transaction.on_commit(_log)

@receiver(post_save, sender=WithdrawalDetail)
def log_withdrawal_activity(sender, instance, created, **kwargs):
    # Skip logging if we're deleting a tenant
    if is_deleting_tenant():
        return
    
    def _log():
        if is_deleting_tenant():
            return
            
        action = 'withdrawal_requested' if created else ('withdrawal_approved' if instance.withdrawal_approved else 'withdrawal_updated')
        details = {
            'amount': float(instance.withdrawal_amount),
            'approved_by': instance.withdrawal_approved_by,
            'status': instance.withdrawan,
        }
        UserActivity.objects.create(
            user=instance.user_profile.user,
            tenant=instance.user_profile.user.tenant,
            action=action,
            details=details,
            success=True,
        )
    transaction.on_commit(_log)

# Add similar for other models (e.g., Document, GroupMembership)
@receiver(post_save, sender=Document)
def log_document_activity(sender, instance, created, **kwargs):
    # Skip logging if we're deleting a tenant
    if is_deleting_tenant():
        return
    
    def _log():
        if is_deleting_tenant():
            return
            
        action = 'document_uploaded' if created else 'document_updated'
        UserActivity.objects.create(
            user=None,  # Anonymous if no user tied; link via uploaded_by_id
            tenant=Tenant.objects.get(id=instance.tenant_id),
            action=action,
            details={'title': instance.title, 'version': instance.version},
            success=True,
        )
    transaction.on_commit(_log)

@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    """Log successful user logins with proper performed_by field"""
    # Skip logging if we're deleting a tenant
    if is_deleting_tenant():
        return
    
    UserActivity.objects.create(
        user=user,
        tenant=user.tenant,
        action='login',
        performed_by=user,  # ✅ Always set for login signals
        details={
            'method': 'session_login',
            'user_agent': request.META.get('HTTP_USER_AGENT', '')
        },
        ip_address=request.META.get('REMOTE_ADDR'),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        success=True
    )