from django.db import models
from django.utils import timezone
import logging
from activitylog.models import ActivityLog  # Import ActivityLog for logging

logger = logging.getLogger('advert')

class Advert(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('retired', 'Retired'),
    ]
    
    TARGET_CHOICES = [
        ('all', 'All Users'),
        ('learners', 'Learners Only'),
        ('instructors', 'Instructors Only'),
        ('admins', 'Admins Only'),
    ]
    
    id = models.AutoField(primary_key=True)  # Changed to AutoField for simplicity
    tenant_id = models.CharField(max_length=36, blank=False, null=False)  # Store Tenant ID
    tenant_name = models.CharField(max_length=255, blank=True, null=True, help_text="Tenant name for reference")
    title = models.CharField(max_length=200)
    content = models.TextField()
    link = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='adverts/', blank=True, null=True)
    image_url = models.CharField(max_length=1024, blank=True, null=True)  # For remote storage
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    priority = models.PositiveIntegerField(default=1)
    target = models.CharField(max_length=20, choices=TARGET_CHOICES, default='all')
    creator_id = models.CharField(max_length=36, blank=True, null=True)  # Store User ID from auth-service
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-priority', '-created_at']
        indexes = [
            models.Index(fields=['tenant_id', 'status'], name='idx_advert_tenant_status'),
            models.Index(fields=['creator_id', 'created_at'], name='idx_advert_creator_created'),
        ]

    def __str__(self):
        return f"{self.title} ({self.status}) (Tenant: {self.tenant_id})"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        # Log activity using ActivityLog
        activity_type = 'advert_created' if is_new else 'advert_updated'
        ActivityLog.objects.create(
            tenant_id=self.tenant_id,
            tenant_name=self.tenant_name,
            user_id=self.creator_id,
            activity_type=activity_type,
            details=f'Advert "{self.title}" {"created" if is_new else "updated"}',
            status='success'
        )
        logger.info(f"Advert {self.id} {'created' if is_new else 'updated'} for tenant {self.tenant_id} by user {self.creator_id}")

    def delete(self, *args, **kwargs):
        # Log activity before deletion
        ActivityLog.objects.create(
            tenant_id=self.tenant_id,
            tenant_name=self.tenant_name,
            user_id=self.creator_id,
            activity_type='advert_deleted',
            details=f'Advert "{self.title}" deleted',
            status='success'
        )
        logger.info(f"Advert {self.id} deleted for tenant {self.tenant_id} by user {self.creator_id}")
        super().delete(*args, **kwargs)