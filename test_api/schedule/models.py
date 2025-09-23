from django.db import models
from django.utils import timezone
import logging
from activitylog.models import ActivityLog

logger = logging.getLogger('schedule')

class Schedule(models.Model):
    id = models.AutoField(primary_key=True)
    tenant_id = models.CharField(max_length=36, blank=False, null=False)
    tenant_name = models.CharField(max_length=255, blank=True, null=True, help_text="Tenant name for reference")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    location = models.TextField(blank=True, null=True)
    is_all_day = models.BooleanField(default=False)
    creator_id = models.CharField(max_length=36, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['start_time']
        indexes = [
            models.Index(fields=['tenant_id'], name='idx_schedule_tenant'),
            models.Index(fields=['creator_id', 'start_time'], name='idx_schedule_creator_start'),
        ]

    def __str__(self):
        return f"{self.title} ({self.start_time} - {self.end_time}) (Tenant: {self.tenant_id})"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        activity_type = 'schedule_created' if is_new else 'schedule_updated'
        ActivityLog.objects.create(
            tenant_id=self.tenant_id,
            tenant_name=self.tenant_name,
            user_id=self.creator_id,
            activity_type=activity_type,
            details=f'Schedule "{self.title}" {"created" if is_new else "updated"}',
            status='success'
        )
        logger.info(f"[Tenant {self.tenant_id}] Schedule {self.id} {'created' if is_new else 'updated'} by user {self.creator_id}")

    def delete(self, *args, **kwargs):
        ActivityLog.objects.create(
            tenant_id=self.tenant_id,
            tenant_name=self.tenant_name,
            user_id=self.creator_id,
            activity_type='schedule_deleted',
            details=f'Schedule "{self.title}" deleted',
            status='success'
        )
        logger.info(f"[Tenant {self.tenant_id}] Schedule {self.id} deleted by user {self.creator_id}")
        super().delete(*args, **kwargs)

class ScheduleParticipant(models.Model):
    schedule = models.ForeignKey(
        Schedule,
        on_delete=models.CASCADE,
        related_name='participants'
    )
    user_id = models.CharField(max_length=36, blank=True, null=True)
    group_id = models.CharField(max_length=36, blank=True, null=True)
    is_optional = models.BooleanField(default=False)
    response_status = models.CharField(
        max_length=20,
        choices=(
            ('pending', 'Pending'),
            ('accepted', 'Accepted'),
            ('declined', 'Declined'),
            ('tentative', 'Tentative'),
        ),
        default='pending'
    )
    read = models.BooleanField(default=False)

    class Meta:
        unique_together = [['schedule', 'user_id'], ['schedule', 'group_id']]
        indexes = [
            models.Index(fields=['schedule', 'user_id'], name='idx_participant_user'),
        ]

    def __str__(self):
        participant = self.user_id or self.group_id or 'Unknown'
        return f"Participant: {participant} for {self.schedule} (Tenant: {self.schedule.tenant_id})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if 'response_status' in kwargs.get('update_fields', []) or 'read' in kwargs.get('update_fields', []):
            activity_type = 'schedule_response' if 'response_status' in kwargs.get('update_fields', []) else 'schedule_read'
            details = (
                f'Responded "{self.response_status}" to schedule "{self.schedule.title}"'
                if activity_type == 'schedule_response'
                else f'Marked schedule "{self.schedule.title}" as read'
            )
            ActivityLog.objects.create(
                tenant_id=self.schedule.tenant_id,
                tenant_name=self.schedule.tenant_name,
                user_id=self.user_id,
                activity_type=activity_type,
                details=details,
                status='success'
            )
            logger.info(f"[Tenant {self.schedule.tenant_id}] ScheduleParticipant {self.id} updated: {details}")