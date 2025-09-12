# messaging/models.py
from django.db import models
from users.models import CustomUser, UserActivity  # Import UserActivity
from groups.models import Group  

class MessageType(models.Model):
    value = models.CharField(max_length=50, unique=True)
    label = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # Log activity
        if is_new:
            UserActivity.objects.create(
                activity_type='message_type_created',
                details=f'Message type "{self.label}" created',
                status='success'
            )
        else:
            UserActivity.objects.create(
                activity_type='message_type_updated',
                details=f'Message type "{self.label}" updated',
                status='success'
            )

    class Meta:
        ordering = ['label']

    def __str__(self):
        return self.label


class Message(models.Model):
    message_type = models.ForeignKey(
            MessageType,
            on_delete=models.PROTECT,  # Prevent deletion of MessageType if used in messages
            related_name='messages'
        )
    
    STATUS_CHOICES = (
        ('sent', 'Sent'),
        ('draft', 'Draft'),
    )
    
    sender = models.ForeignKey(
        CustomUser, 
        on_delete=models.CASCADE, 
        related_name='sent_messages'
    )
    subject = models.CharField(max_length=200)
    content = models.TextField()

    sent_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='sent'
    )
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
    
    def __str__(self):
        return f"{self.sender.email}: {self.subject}"
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # Log activity
        if is_new:
            activity_type = 'message_created'
            details = f'New message "{self.subject}" created'
        else:
            activity_type = 'message_updated'
            details = f'Message "{self.subject}" updated'
            
        UserActivity.objects.create(
            user=self.sender,
            activity_type=activity_type,
            details=details,
            status='success'
        )

    def delete(self, *args, **kwargs):
        # Log activity before deletion
        UserActivity.objects.create(
            user=self.sender,
            activity_type='message_deleted',
            details=f'Message "{self.subject}" deleted',
            status='success'
        )
        super().delete(*args, **kwargs)


class MessageRecipient(models.Model):
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name='recipients'
    )
    recipient = models.ForeignKey(
        CustomUser,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='received_messages'
    )
    recipient_group = models.ForeignKey(
        Group,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='group_messages'
    )
    group_member = models.ForeignKey(
        CustomUser,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='group_received_messages',
        help_text="For group messages, tracks individual member"
    )
    read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    deleted = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['message', 'recipient'],
                name='unique_user_recipient'
            ),
            models.UniqueConstraint(
                fields=['message', 'recipient_group', 'group_member'],
                name='unique_group_member_recipient'
            ),
        ]

    def __str__(self):
        if self.recipient:
            recipient = self.recipient.email
        elif self.group_member:
            recipient = f"{self.recipient_group.name}:{self.group_member.email}"
        else:
            recipient = self.recipient_group.name if self.recipient_group else "Unknown"
        return f"Recipient: {recipient} for {self.message}"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        # Log activity for read status changes
        if not is_new and 'read' in kwargs.get('update_fields', []):
            if self.read:
                UserActivity.objects.create(
                    user=self.recipient or self.group_member,
                    activity_type='message_read',
                    details=f'Marked message "{self.message.subject}" as read',
                    status='success'
                )

class MessageAttachment(models.Model):
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name='attachments'
    )
    file = models.URLField(blank=True)
    original_filename = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Attachment for {self.message.subject}"
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # Log activity
        if is_new:
            UserActivity.objects.create(
                user=self.message.sender,
                activity_type='message_attachment_added',
                details=f'Added attachment "{self.original_filename}" to message "{self.message.subject}"',
                status='success'
            )

