import uuid
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.models import Tenant
from users.models import CustomUser


class Event(models.Model):
    VISIBILITY_CHOICES = [
        ('private', 'Private'),
        ('public', 'Public'),
        ('specific_users', 'Specific Users'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    location = models.CharField(max_length=255, blank=True)
    meeting_link = models.URLField(max_length=500, blank=True, null=True, help_text="Optional link for virtual meetings (Zoom, Teams, Google Meet, etc.)")
    creator = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='created_events')
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    visibility = models.CharField(max_length=20, choices=VISIBILITY_CHOICES, default='private')
    participants = models.ManyToManyField(CustomUser, related_name='events', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_updated_by_id = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        ordering = ['-start_datetime']
        indexes = [
            models.Index(fields=['tenant', 'creator', 'start_datetime']),
            models.Index(fields=['tenant', 'start_datetime', 'end_datetime']),
            models.Index(fields=['tenant', 'visibility']),
        ]

    def __str__(self):
        return f"{self.title} - {self.creator.email}"

    def is_visible_to_user(self, user):
        """Check if the event is visible to a specific user."""
        if self.visibility == 'public':
            return True
        if self.creator == user:
            return True
        if self.visibility == 'specific_users' and self.participants.filter(id=user.id).exists():
            return True
        return False