from django.db import models
import logging
from activitylog.models import ActivityLog  # Import for activity logging

logger = logging.getLogger('ai_chat')

class ChatSession(models.Model):
    id = models.AutoField(primary_key=True)  # Changed to AutoField for simplicity
    tenant_id = models.CharField(max_length=36, blank=False, null=False)  # Store Tenant ID
    tenant_name = models.CharField(max_length=255, blank=True, null=True, help_text="Tenant name for reference")
    user_id = models.CharField(max_length=36, blank=True, null=True)  # Store User ID from auth-service
    title = models.CharField(max_length=200, default="Untitled")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant_id', 'user_id'], name='idx_chatsession_tenant_user'),
            models.Index(fields=['created_at'], name='idx_chatsession_created'),
        ]

    def __str__(self):
        return f"{self.title} (Tenant: {self.tenant_id}, User: {self.user_id or 'System'})"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        activity_type = 'chat_session_created' if is_new else 'chat_session_updated'
        ActivityLog.objects.create(
            tenant_id=self.tenant_id,
            tenant_name=self.tenant_name,
            user_id=self.user_id,
            activity_type=activity_type,
            details=f'ChatSession "{self.title}" {"created" if is_new else "updated"}',
            status='success'
        )
        logger.info(f"ChatSession {self.id} {'created' if is_new else 'updated'} for tenant {self.tenant_id} by user {self.user_id}")

    def delete(self, *args, **kwargs):
        ActivityLog.objects.create(
            tenant_id=self.tenant_id,
            tenant_name=self.tenant_name,
            user_id=self.user_id,
            activity_type='chat_session_deleted',
            details=f'ChatSession "{self.title}" deleted',
            status='success'
        )
        logger.info(f"ChatSession {self.id} deleted for tenant {self.tenant_id} by user {self.user_id}")
        super().delete(*args, **kwargs)

class ChatMessage(models.Model):
    id = models.AutoField(primary_key=True)
    tenant_id = models.CharField(max_length=36, blank=False, null=False)  # Store Tenant ID
    tenant_name = models.CharField(max_length=255, blank=True, null=True, help_text="Tenant name for reference")
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    sender = models.CharField(max_length=50)  # e.g., 'user', 'bot'
    text = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['tenant_id', 'session_id'], name='idx_chatmessage_tenant_session'),
            models.Index(fields=['timestamp'], name='idx_chatmessage_timestamp'),
        ]

    def __str__(self):
        return f"Message in {self.session.title} by {self.sender} (Tenant: {self.tenant_id})"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        ActivityLog.objects.create(
            tenant_id=self.tenant_id,
            tenant_name=self.tenant_name,
            user_id=self.session.user_id,
            activity_type='chat_message_created',
            details=f'ChatMessage in session "{self.session.title}" created by {self.sender}',
            status='success'
        )
        logger.info(f"ChatMessage {self.id} created in session {self.session.id} for tenant {self.tenant_id}")