from django.db import models
from django.utils.translation import gettext as _
from django.core.exceptions import ValidationError
from activitylog.models import ActivityLog
import logging

logger = logging.getLogger('forum')

class Forum(models.Model):
    id = models.AutoField(primary_key=True)
    tenant_id = models.CharField(max_length=36, blank=False, null=False)  # Store Tenant ID
    tenant_name = models.CharField(max_length=255, blank=True, null=True, help_text="Tenant name for reference")
    title = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    group_ids = models.JSONField(default=list, blank=True)  # Store Group IDs from auth-service
    is_active = models.BooleanField(default=True)
    created_by_id = models.CharField(max_length=36, blank=True, null=True)  # Store User ID from auth-service
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['title']
        verbose_name = _('Forum')
        verbose_name_plural = _('Forums')
        indexes = [
            models.Index(fields=['tenant_id', 'is_active'], name='idx_forum_tenant_active'),
            models.Index(fields=['created_by_id', 'created_at'], name='idx_forum_creator_created'),
            
        ]

    def __str__(self):
        return f"{self.title} (Tenant: {self.tenant_id})"

    def clean(self):
        if not self.title:
            raise ValidationError("Forum title cannot be empty")

    def save(self, *args, **kwargs):
        created = not self.pk
        self.full_clean()
        super().save(*args, **kwargs)
        activity_type = 'forum_created' if created else 'forum_updated'
        ActivityLog.objects.create(
            tenant_id=self.tenant_id,
            tenant_name=self.tenant_name,
            user_id=self.created_by_id,
            activity_type=activity_type,
            details=f'Forum "{self.title}" was {"created" if created else "updated"}',
            status='success'
        )
        logger.info(f"Forum {self.id} {'created' if created else 'updated'} for tenant {self.tenant_id} by user {self.created_by_id}")

    def delete(self, *args, **kwargs):
        ActivityLog.objects.create(
            tenant_id=self.tenant_id,
            tenant_name=self.tenant_name,
            user_id=self.created_by_id,
            activity_type='forum_deleted',
            details=f'Forum "{self.title}" was deleted',
            status='success'
        )
        logger.info(f"Forum {self.id} deleted for tenant {self.tenant_id} by user {self.created_by_id}")
        super().delete(*args, **kwargs)

class ForumPost(models.Model):
    id = models.AutoField(primary_key=True)
    tenant_id = models.CharField(max_length=36, blank=False, null=False)  # Store Tenant ID
    tenant_name = models.CharField(max_length=255, blank=True, null=True, help_text="Tenant name for reference")
    forum = models.ForeignKey(
        Forum,
        on_delete=models.CASCADE,
        related_name='posts'
    )
    author_id = models.CharField(max_length=36, blank=True, null=True)  # Store User ID from auth-service
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_approved = models.BooleanField(default=False)
    moderated_at = models.DateTimeField(null=True, blank=True)
    moderated_by_id = models.CharField(max_length=36, blank=True, null=True)  # Store User ID from auth-service

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Forum Post')
        verbose_name_plural = _('Forum Posts')
        indexes = [
            models.Index(fields=['tenant_id', 'is_approved'], name='idx_forumpost_tenant_approved'),
            models.Index(fields=['author_id', 'created_at'], name='idx_forumpost_author_created'),
        ]

    def __str__(self):
        return f"Post in {self.forum.title} by {self.author_id or 'Deleted User'} (Tenant: {self.tenant_id})"

    def save(self, *args, **kwargs):
        created = not self.pk
        super().save(*args, **kwargs)
        if created:
            ActivityLog.objects.create(
                tenant_id=self.tenant_id,
                tenant_name=self.tenant_name,
                user_id=self.author_id,
                activity_type='forum_post_created',
                details=f'Created post in forum "{self.forum.title}"',
                status='success'
            )
            logger.info(f"ForumPost {self.id} created for tenant {self.tenant_id} by user {self.author_id}")

class ModerationQueue(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )

    id = models.AutoField(primary_key=True)
    tenant_id = models.CharField(max_length=36, blank=False, null=False)  # Store Tenant ID
    tenant_name = models.CharField(max_length=255, blank=True, null=True, help_text="Tenant name for reference")
    content_type = models.CharField(max_length=100)  # e.g., 'forum_post', 'comment'
    content_id = models.PositiveIntegerField()
    content = models.TextField()
    reported_by_id = models.CharField(max_length=36, blank=True, null=True)  # Store User ID from auth-service
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    moderation_notes = models.TextField(blank=True)
    moderated_by_id = models.CharField(max_length=36, blank=True, null=True)  # Store User ID from auth-service
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Moderation Queue')
        verbose_name_plural = _('Moderation Queues')
        indexes = [
            models.Index(fields=['tenant_id', 'status'], name='idx_moderation_tenant_status'),
            models.Index(fields=['reported_by_id', 'created_at'], name='idx_mod_rep_cr'),

        ]

    def __str__(self):
        return f"{self.content_type} {self.content_id} - {self.status} (Tenant: {self.tenant_id})"

    def save(self, *args, **kwargs):
        created = not self.pk
        super().save(*args, **kwargs)
        if created:
            ActivityLog.objects.create(
                tenant_id=self.tenant_id,
                tenant_name=self.tenant_name,
                user_id=self.reported_by_id,
                activity_type='moderation_item_created',
                details=f'Reported {self.content_type} {self.content_id}',
                status='success'
            )
            logger.info(f"ModerationQueue {self.id} created for tenant {self.tenant_id} by user {self.reported_by_id}")
        elif self.status != 'pending':
            ActivityLog.objects.create(
                tenant_id=self.tenant_id,
                tenant_name=self.tenant_name,
                user_id=self.moderated_by_id,
                activity_type='moderation_item_updated',
                details=f'Moderated {self.content_type} {self.content_id} as {self.status}',
                status='success'
            )
            logger.info(f"ModerationQueue {self.id} updated for tenant {self.tenant_id} by user {self.moderated_by_id}")