from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.conf import settings
from enum import Enum
import uuid
import json
from django.db.models import JSONField
import logging

logger = logging.getLogger('notifications')

class ChannelType(Enum):
    EMAIL = 'email'
    SMS = 'sms'
    PUSH = 'push'
    INAPP = 'inapp'

class NotificationStatus(Enum):
    PENDING = 'pending'
    SUCCESS = 'success'
    FAILED = 'failed'
    RETRYING = 'retrying'

class FailureReason(Enum):
    AUTH_ERROR = 'auth_error'
    NETWORK_ERROR = 'network_error'
    PROVIDER_ERROR = 'provider_error'
    CONTENT_ERROR = 'content_error'
    UNKNOWN_ERROR = 'unknown_error'

class SoftDeleteQuerySet(models.query.QuerySet):
    def delete(self):
        self.update(is_deleted=True, deleted_at=timezone.now())

class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).filter(is_deleted=False)

    def all_with_deleted(self):
        return super().get_queryset()

    def deleted_set(self):
        return super().get_queryset().filter(is_deleted=True)

def validate_template_content(value):
    if not isinstance(value, dict):
        raise ValidationError("Template content must be a dictionary with 'subject' or 'body'.")
    return value

class TenantCredentials(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant_id = models.UUIDField(db_index=True)
    channel = models.CharField(max_length=10, choices=[(tag.value, tag.name) for tag in ChannelType])
    credentials = JSONField()  # e.g., {'smtp_host': '...', 'username': '...'} - encrypted separately
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = SoftDeleteManager()

    class Meta:
        unique_together = [('tenant_id', 'channel')]
        indexes = [models.Index(fields=['tenant_id', 'channel'])]

class NotificationTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant_id = models.UUIDField(db_index=True)
    name = models.CharField(max_length=255)
    channel = models.CharField(max_length=10, choices=[(tag.value, tag.name) for tag in ChannelType])
    content = JSONField(validators=[validate_template_content])  # e.g., {'subject': 'Hi {{name}}', 'body': '...'}
    placeholders = JSONField(default=list)  # e.g., ['{{candidate_name}}', '{{interview_date}}']
    version = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = SoftDeleteManager()

    class Meta:
        indexes = [models.Index(fields=['tenant_id', 'name', 'channel'])]

class NotificationRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant_id = models.UUIDField(db_index=True)
    channel = models.CharField(max_length=10, choices=[(tag.value, tag.name) for tag in ChannelType])
    recipient = models.CharField(max_length=500)  # email, phone, token, etc.
    template_id = models.UUIDField(null=True, blank=True)  # Optional template
    context = JSONField(default=dict)  # Placeholders: {'candidate_name': 'John'}
    status = models.CharField(max_length=10, choices=[(tag.value, tag.name) for tag in NotificationStatus], default=NotificationStatus.PENDING.value)
    failure_reason = models.CharField(max_length=20, choices=[(tag.value, tag.name) for tag in FailureReason], blank=True, null=True)
    provider_response = models.TextField(blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    max_retries = models.PositiveIntegerField(default=3)
    sent_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = SoftDeleteManager()

    class Meta:
        indexes = [
            models.Index(fields=['tenant_id', 'status']),
            models.Index(fields=['tenant_id', 'created_at']),
            models.Index(fields=['status', 'retry_count']),
        ]

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=['is_deleted', 'deleted_at'])

class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant_id = models.UUIDField(db_index=True)
    notification_id = models.UUIDField()  # FK to NotificationRecord
    event = models.CharField(max_length=100)  # e.g., 'sent', 'failed', 'retry'
    details = JSONField(default=dict)
    timestamp = models.DateTimeField(auto_now_add=True)
    user_id = models.UUIDField(null=True, blank=True)  # Who triggered

    class Meta:
        indexes = [models.Index(fields=['tenant_id', 'timestamp'])]
        ordering = ['-timestamp']



class CampaignStatus(Enum):
    DRAFT = 'draft'
    SCHEDULED = 'scheduled'
    SENDING = 'sending'
    COMPLETED = 'completed'
    FAILED = 'failed'

class Campaign(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant_id = models.UUIDField(db_index=True)
    name = models.CharField(max_length=255)
    channel = models.CharField(max_length=10, choices=[(tag.value, tag.name) for tag in ChannelType])
    template_id = models.UUIDField(null=True, blank=True)  # Or inline content
    content = JSONField(validators=[validate_template_content], null=True, blank=True)
    recipients = JSONField(default=list)  # List of {'recipient': '...', 'context': {...}}
    total_recipients = models.PositiveIntegerField(default=0)
    sent_count = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=10, choices=[(tag.value, tag.name) for tag in CampaignStatus], default=CampaignStatus.DRAFT.value)
    schedule_time = models.DateTimeField(null=True, blank=True)  # For beat scheduling
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = SoftDeleteManager()

    class Meta:
        indexes = [models.Index(fields=['tenant_id', 'status'])]