from django.db import models
import logging

logger = logging.getLogger('activitylog')  # Updated logger name for consistency

class ActivityLog(models.Model):
    STATUS_CHOICES = (
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('pending', 'Pending'),
        ('in-progress', 'In Progress'),
    )

    id = models.AutoField(primary_key=True)  # Changed to AutoField for simplicity
    tenant_id = models.CharField(max_length=36, blank=False, null=False)  # Store Tenant ID
    tenant_name = models.CharField(max_length=255, blank=True, null=True, help_text="Tenant name for reference")
    user_id = models.CharField(max_length=36, blank=True, null=True)  # Store User ID from auth-service
    activity_type = models.CharField(max_length=50)
    details = models.TextField()
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    device_info = models.CharField(max_length=200, blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='success')

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Activity Log'
        verbose_name_plural = 'Activity Logs'
        indexes = [
            models.Index(fields=['tenant_id', 'status'], name='idx_activitylog_tenant_status'),
            models.Index(fields=['user_id', 'timestamp'], name='idx_activitylog_user_timestamp'),
        ]

    def __str__(self):
        return f"{self.activity_type} - {self.user_id or 'System'} (Tenant: {self.tenant_id})"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        logger.info(f"ActivityLog {self.id} {'created' if is_new else 'updated'} for tenant {self.tenant_id}")