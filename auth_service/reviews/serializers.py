from asyncio.log import logger
import json
from django.conf import settings
from rest_framework import serializers
from .models import Review, QRCode, ReviewSettings
from django.utils import timezone
from utils.supabase import upload_file_dynamic
from django.core.files.base import ContentFile
from users.serializers import CustomUserSerializer  # Minimal if needed
import qrcode
from cryptography.fernet import Fernet

from io import BytesIO


def generate_qr_image(data_url, size=10):
    qr = qrcode.QRCode(version=1, box_size=size, border=4)
    qr.add_data(data_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    return buffer.getvalue()

class AttachmentSerializer(serializers.Serializer):
    url = serializers.URLField()
    name = serializers.CharField(max_length=255)


class ReviewCreateSerializer(serializers.ModelSerializer):
    rating = serializers.IntegerField(min_value=1, max_value=5)
    attachments = serializers.ListField(child=serializers.FileField(), required=False, write_only=True)

    class Meta:
        model = Review
        fields = ['reviewer_name', 'reviewer_email', 'rating', 'comment', 'is_anonymous', 'attachments']
        extra_kwargs = {
            'comment': {'max_length': 1000},
        }

    def validate(self, data):
        tenant = self.context.get('tenant')
        if tenant:
            try:
                settings_obj = tenant.review_settings  # Try access
                attachments = data.get('attachments', [])
                if len(attachments) > settings_obj.max_attachments:
                    raise serializers.ValidationError(
                        f'Maximum {settings_obj.max_attachments} attachments allowed.'
                    )
            except ReviewSettings.DoesNotExist:  # FIXED: Graceful handling
                logger.warning(f"⚠️ No ReviewSettings for tenant {tenant.unique_id} during validation; using defaults")
                # Defaults: No attachment check (allow up to 3 implicitly), proceed
                pass
        return data

    def create(self, validated_data):
        attachments_data = validated_data.pop('attachments', [])
        attachments = []
        for file in attachments_data:
            content_type = file.content_type
            name = file.name
            url = upload_file_dynamic(file, name, content_type)
            attachments.append({'url': url, 'name': name})
        validated_data['attachments'] = attachments

        # Set tenant and QR from context
        validated_data['tenant_id'] = self.context['tenant'].id
        validated_data['qr_code_id'] = self.context.get('qr_code').id if self.context.get('qr_code') else None

        review = super().create(validated_data)

        # Auto-approve: Handle missing settings here too
        try:
            settings_obj = review.tenant.review_settings
            if not settings_obj.approval_required:
                review.is_approved = True
                review.approved_at = timezone.now()
                review.save(update_fields=['is_approved', 'approved_at'])
                if review.qr_code:
                    review.qr_code.increment_scan()
        except ReviewSettings.DoesNotExist:
            logger.warning(f"⚠️ No ReviewSettings for auto-approval; defaulting to require approval")
            # Default: Require approval (no auto-approve)
            pass
        return review
    
# class ReviewCreateSerializer(serializers.ModelSerializer):
#     rating = serializers.IntegerField(min_value=1, max_value=5)
#     attachments = serializers.ListField(child=serializers.FileField(), required=False, write_only=True)

#     class Meta:
#         model = Review
#         fields = ['reviewer_name', 'reviewer_email', 'rating', 'comment', 'is_anonymous', 'attachments']
#         extra_kwargs = {
#             'comment': {'max_length': 1000},
#         }

#     def validate(self, data):
#         tenant = self.context.get('tenant')
#         if tenant:
#             settings_obj = tenant.review_settings
#             attachments = data.get('attachments', [])
#             if len(attachments) > settings_obj.max_attachments:
#                 raise serializers.ValidationError(
#                     f'Maximum {settings_obj.max_attachments} attachments allowed.'
#                 )
#         return data

#     def create(self, validated_data):
#         attachments_data = validated_data.pop('attachments', [])
#         attachments = []
#         for file in attachments_data:
#             content_type = file.content_type
#             name = file.name
#             url = upload_file_dynamic(file, name, content_type)
#             attachments.append({'url': url, 'name': name})
#         validated_data['attachments'] = attachments

#         # Set tenant and QR from context (from QR ID in request)
#         validated_data['tenant_id'] = self.context['tenant'].id
#         validated_data['qr_code_id'] = self.context.get('qr_code').id if self.context.get('qr_code') else None

#         review = super().create(validated_data)

#         # Auto-approve if no moderation required
#         settings_obj = review.tenant.review_settings
#         if not settings_obj.approval_required:
#             review.is_approved = True
#             review.approved_at = timezone.now()
#             # approved_by remains None for auto-approval
#             review.save(update_fields=['is_approved', 'approved_at'])
#             if review.qr_code:
#                 review.qr_code.increment_scan()
#         return review


class ReviewSerializer(serializers.ModelSerializer):
    reviewer_user = CustomUserSerializer(read_only=True)
    attachments = AttachmentSerializer(many=True, read_only=True)
    sentiment_score = serializers.FloatField(read_only=True)
    sentiment_subjectivity = serializers.FloatField(read_only=True)

    class Meta:
        model = Review
        fields = '__all__'
        read_only_fields = ['id', 'tenant', 'qr_code', 'submitted_at', 'approved_at', 'approved_by', 'reviewer_user']

class QRCodeSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only=True)
    tenant = serializers.PrimaryKeyRelatedField(read_only=True)
    actual_scan_count = serializers.IntegerField(read_only=True)  # New: Add this

    class Meta:
        model = QRCode
        fields = '__all__'
        read_only_fields = ['id', 'unique_id', 'image_url', 'scan_count', 'actual_scan_count', 'tenant', 'qr_data']  # Updated: Include new field

    def create(self, validated_data):
        from secrets import token_urlsafe
        
        tenant = self.context['request'].user.tenant
        description = validated_data.pop('description', 'Scan to review')
        
        # Pre-generate unique_id
        unique_id = token_urlsafe(16)
        
        # Encrypt tenant_id and qr_id - FIX: Convert UUID to string
        fernet = Fernet(settings.QR_ENCRYPTION_KEY.encode())
        payload = json.dumps({
            "tenant_id": str(tenant.unique_id),  # Convert UUID to string
            "qr_id": unique_id
        }).encode('utf-8')
        token = fernet.encrypt(payload).decode('utf-8')  # URL-safe base64
        
        # Encrypted URL
        encrypted_url = f"{settings.REVIEWS_QR_BASE_URL}/submit?token={token}"
        validated_data.update({
            'unique_id': unique_id,
            'tenant_id': tenant.id,  # Use PK (int) for create
            'qr_data': json.dumps({'url': encrypted_url, 'description': description}),
            'image_url': 'https://dummy-placeholder.com/skip-upload'  # Dummy to skip model upload
        })
        
        # Create and save (model runs but skips upload)
        qr = QRCode.objects.create(**validated_data)
        qr.refresh_from_db()  # Ensure all fields loaded
        
        # Update to real
        qr.qr_data = json.dumps({'url': encrypted_url, 'description': description})
        
        # Generate QR image with encrypted URL
        img_bytes = generate_qr_image(encrypted_url)
        file_name = f"qr_{unique_id}.png"
        qr.image_url = upload_file_dynamic(img_bytes, file_name, "image/png")
        
        qr.save(update_fields=['qr_data', 'image_url'])
        return qr

class ReviewSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewSettings
        fields = '__all__'
        read_only_fields = ['tenant', 'created_at', 'updated_at']