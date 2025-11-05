import uuid
import json
import secrets  # For unique_id generation
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django_tenants.utils import tenant_context
from core.models import Tenant
from users.models import CustomUser
from django.core.files.base import ContentFile
from io import BytesIO
import qrcode
from PIL import Image
from django.conf import settings
from textblob import TextBlob
from django.db.models.signals import post_save
from django.dispatch import receiver

def generate_qr_image(data_url, size=10):
    """Generate QR code image as bytes."""
    qr = qrcode.QRCode(version=1, box_size=size, border=4)
    qr.add_data(data_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    return buffer.getvalue()

class ReviewSettings(models.Model):
    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name='review_settings')
    enable_anonymous = models.BooleanField(default=True)
    max_attachments = models.PositiveIntegerField(default=3, validators=[MinValueValidator(1)])
    approval_required = models.BooleanField(default=True)
    custom_fields = models.JSONField(default=dict, blank=True)  # e.g., {"industry": ["Healthcare", "Education"]}
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Review Settings for {self.tenant.name}"

    class Meta:
        db_table = 'reviews_reviewsettings'

class QRCode(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='qrcodes')
    unique_id = models.CharField(max_length=32, unique=True, db_index=True)  # Short ID for URLs
    qr_data = models.TextField()  # JSON: {"url": "https://.../submit?qr_id=...", "description": "..."}
    image_url = models.URLField(blank=True)  # Stored via upload_file_dynamic
    scan_count = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    actual_scan_count = models.PositiveIntegerField(default=0, help_text="Number of times the QR code was actually scanned and form loaded")




    def increment_actual_scan(self):
        """Increment the actual scan count (called on QR URL access)."""
        self.actual_scan_count += 1
        self.save(update_fields=['actual_scan_count', 'updated_at'])  # Also update timestamp for auditing


    def save(self, *args, **kwargs):
        if not self.unique_id:
            self.unique_id = secrets.token_urlsafe(16)
        if not self.image_url:
            # Generate and upload QR image
            qr_url = json.loads(self.qr_data)['url']
            img_bytes = generate_qr_image(qr_url)
            file_name = f"qr_{self.unique_id}.png"
            from utils.supabase import upload_file_dynamic
            self.image_url = upload_file_dynamic(
                ContentFile(img_bytes), file_name, "image/png"
            )
        super().save(*args, **kwargs)

    def increment_scan(self):
        self.scan_count += 1
        self.save(update_fields=['scan_count'])

    def __str__(self):
        return f"QR {self.unique_id} for {self.tenant.name}"

    class Meta:
        db_table = 'reviews_qrcode'
        indexes = [models.Index(fields=['tenant', 'is_active', 'created_at'])]

class Review(models.Model):
    RATING_CHOICES = [(i, str(i)) for i in range(1, 6)]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='reviews')
    qr_code = models.ForeignKey(QRCode, on_delete=models.SET_NULL, null=True, related_name='reviews')
    reviewer_user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='given_reviews')  # If authenticated
    reviewer_name = models.CharField(max_length=255, blank=True)
    reviewer_email = models.EmailField(blank=True)
    rating = models.PositiveIntegerField(choices=RATING_CHOICES, validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField()
    is_anonymous = models.BooleanField(default=True)
    is_approved = models.BooleanField(default=False)
    attachments = models.JSONField(default=list, blank=True)  # List of {"url": "...", "name": "..."}
    submitted_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_reviews')
    sentiment_score = models.FloatField(null=True, blank=True)  # -1.0 to +1.0
    sentiment_subjectivity = models.FloatField(null=True, blank=True)  # 0.0 to 1.0

    def compute_sentiment(self):
        """Compute sentiment using TextBlob."""
        if not self.comment.strip():
            return None, None
        blob = TextBlob(self.comment)
        return blob.sentiment.polarity, blob.sentiment.subjectivity

    def save(self, *args, **kwargs):
        if self.pk is None:  # New instance
            polarity, subjectivity = self.compute_sentiment()
            self.sentiment_score = polarity
            self.sentiment_subjectivity = subjectivity
        super().save(*args, **kwargs)

    def approve(self, approver):
        self.is_approved = True
        self.approved_at = timezone.now()
        self.approved_by = approver
        self.save(update_fields=['is_approved', 'approved_at', 'approved_by'])
        if self.qr_code:
            self.qr_code.increment_scan()

    def __str__(self):
        return f"Review {self.id} for {self.tenant.name} (Rating: {self.rating})"

    class Meta:
        db_table = 'reviews_review'
        ordering = ['-submitted_at']
        indexes = [
            models.Index(fields=['tenant', 'is_approved', 'submitted_at']),
            models.Index(fields=['qr_code', 'submitted_at']),
        ]

# Optional: Signal for retroactive computation on existing reviews
@receiver(post_save, sender=Review)
def update_sentiment_on_save(sender, instance, **kwargs):
    if instance.comment and (instance.sentiment_score is None or kwargs.get('update_fields') is None):
        polarity, subjectivity = instance.compute_sentiment()
        instance.sentiment_score = polarity
        instance.sentiment_subjectivity = subjectivity
        instance.save(update_fields=['sentiment_score', 'sentiment_subjectivity'])