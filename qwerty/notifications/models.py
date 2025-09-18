from django.db import models

# Create your models here.
# models.py for notifications
class Notification(models.Model):
    tenant_id = models.CharField(max_length=100)
    user_id = models.CharField(max_length=100)
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    type = models.CharField(max_length=50, default="system")  # or "message", "alert", etc.
    created_at = models.DateTimeField(auto_now_add=True)
