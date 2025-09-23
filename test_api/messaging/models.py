from django.db import models
from django.utils import timezone
import logging
from activitylog.models import ActivityLog

logger = logging.getLogger('messaging')

class MessageType(models.Model):
    id = models.AutoField(primary_key=True)
    tenant_id = models.CharField(max_length=36, blank=False, null=False)
    tenant_name = models.CharField(max_length=255, blank=True, null=True, help_text="Tenant name for reference")
    value = models.CharField(max_length=50, unique=True)
    label = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['label']
        indexes = [
            models.Index(fields=['tenant_id'], name='idx_msgtype_tenant'),
        ]

    def __str__(self):
        return f"{self.label} (Tenant: {self.tenant_id})"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        activity_type = 'message_type_created' if is_new else 'message_type_updated'
        ActivityLog.objects.create(
            tenant_id=self.tenant_id,
            tenant_name=self.tenant_name,
            activity_type=activity_type,
            details=f'Message type "{self.label}" {"created" if is_new else "updated"}',
            status='success'
        )
        logger.info(f"MessageType {self.id} {'created' if is_new else 'updated'} for tenant {self.tenant_id}")

class Message(models.Model):
    STATUS_CHOICES = (
        ('sent', 'Sent'),
        ('draft', 'Draft'),
    )
    
    id = models.AutoField(primary_key=True)
    tenant_id = models.CharField(max_length=36, blank=False, null=False)
    tenant_name = models.CharField(max_length=255, blank=True, null=True, help_text="Tenant name for reference")
    message_type = models.ForeignKey(
        MessageType,
        on_delete=models.PROTECT,
        related_name='messages'
    )
    sender_id = models.CharField(max_length=36, blank=True, null=True)
    subject = models.CharField(max_length=200)
    content = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='sent')
    parent_message = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='replies'
    )
    is_forward = models.BooleanField(default=False)

    class Meta:
        ordering = ['-sent_at']
        indexes = [
            models.Index(fields=['tenant_id', 'status'], name='idx_message_tenant_status'),
            models.Index(fields=['sender_id', 'sent_at'], name='idx_message_sender_sent'),
        ]

    def __str__(self):
        return f"{self.sender_id or 'System'}: {self.subject} (Tenant: {self.tenant_id})"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        activity_type = 'message_created' if is_new else 'message_updated'
        ActivityLog.objects.create(
            tenant_id=self.tenant_id,
            tenant_name=self.tenant_name,
            user_id=self.sender_id,
            activity_type=activity_type,
            details=f'Message "{self.subject}" {"created" if is_new else "updated"}',
            status='success'
        )
        logger.info(f"Message {self.id} {'created' if is_new else 'updated'} for tenant {self.tenant_id}")

    def delete(self, *args, **kwargs):
        ActivityLog.objects.create(
            tenant_id=self.tenant_id,
            tenant_name=self.tenant_name,
            user_id=self.sender_id,
            activity_type='message_deleted',
            details=f'Message "{self.subject}" deleted',
            status='success'
        )
        logger.info(f"Message {self.id} deleted for tenant {self.tenant_id}")
        super().delete(*args, **kwargs)

class MessageRecipient(models.Model):
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name='recipients'
    )
    recipient_id = models.CharField(max_length=36, blank=True, null=True)
    recipient_group_id = models.CharField(max_length=36, blank=True, null=True)
    group_member_id = models.CharField(max_length=36, blank=True, null=True, help_text="For group messages, tracks individual member")
    read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    deleted = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['message', 'recipient_id'],
                name='unique_user_recipient'
            ),
            models.UniqueConstraint(
                fields=['message', 'recipient_group_id', 'group_member_id'],
                name='unique_group_member_recipient'
            ),
        ]
        indexes = [
            models.Index(fields=['message', 'recipient_id'], name='idx_msgrecipient_recipient'),
        ]

    def __str__(self):
        recipient = self.recipient_id or (self.recipient_group_id + ':' + self.group_member_id if self.group_member_id else self.recipient_group_id or 'Unknown')
        return f"Recipient: {recipient} for {self.message}"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if not is_new and 'read' in kwargs.get('update_fields', []):
            if self.read:
                ActivityLog.objects.create(
                    tenant_id=self.message.tenant_id,
                    tenant_name=self.message.tenant_name,
                    user_id=self.recipient_id or self.group_member_id,
                    activity_type='message_read',
                    details=f'Marked message "{self.message.subject}" as read',
                    status='success'
                )
                logger.info(f"MessageRecipient {self.id} marked as read for tenant {self.message.tenant_id}")

class MessageAttachment(models.Model):
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name='attachments'
    )
    file = models.URLField(blank=True)
    file_url = models.URLField(blank=True, null=True)  # For remote storage
    original_filename = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Attachment for {self.message.subject} (Tenant: {self.message.tenant_id})"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            ActivityLog.objects.create(
                tenant_id=self.message.tenant_id,
                tenant_name=self.message.tenant_name,
                user_id=self.message.sender_id,
                activity_type='message_attachment_added',
                details=f'Added attachment "{self.original_filename}" to message "{self.message.subject}"',
                status='success'
            )
            logger.info(f"MessageAttachment {self.id} created for tenant {self.message.tenant_id}")