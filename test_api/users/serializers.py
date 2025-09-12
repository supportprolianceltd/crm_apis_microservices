from rest_framework import serializers
from django_tenants.utils import tenant_context
from .models import CustomUser, UserActivity, FailedLogin, BlockedIP, VulnerabilityAlert, ComplianceReport, PasswordResetToken
from core.models import Module
from django.utils import timezone
import logging
from utils.storage import get_storage_service
import uuid

logger = logging.getLogger(__name__)

class CustomUserSerializer(serializers.ModelSerializer):
    last_login = serializers.DateTimeField(format="%Y-%m-%d %H:%M", read_only=True)
    class Meta:
        model = CustomUser
        fields = "__all__"
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def validate_password(self, value):
        if len(value) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters long")
        return value  # Do not hash here; hashing is handled in create_user

class AdminUserCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = '__all__'
        extra_kwargs = {'password': {'write_only': True}}

    def validate_email(self, value):
        if CustomUser.objects.filter(email=value, tenant=self.context['request'].tenant, is_deleted=False).exists():
            raise serializers.ValidationError("Email already exists")
        return value

    def create(self, validated_data):
        tenant = self.context['request'].tenant
        user = CustomUser.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            role=validated_data.get('role', 'carer'),
            tenant=tenant,
            status='active',
            is_locked=False
        )
        return user

class UserActivitySerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()
    timestamp = serializers.DateTimeField(format="%Y-%m-%d %H:%M")

    class Meta:
        model = UserActivity
        fields = '__all__'

class FailedLoginSerializer(serializers.ModelSerializer):
    class Meta:
        model = FailedLogin
        fields = ['id', 'ip_address', 'username', 'timestamp', 'attempts', 'status']

class BlockedIPSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlockedIP
        fields = ['id', 'ip_address', 'action', 'reason', 'timestamp']
        read_only_fields = ['id', 'timestamp']

    def validate_ip_address(self, value):
        import re
        ipv4_pattern = r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
        ipv6_pattern = r'^([0-9a-fA-F]{1,4}:){7,7}[0-9a-fA-F]{1,4}$'
        if not (re.match(ipv4_pattern, value) or re.match(ipv6_pattern, value)):
            raise serializers.ValidationError("Invalid IP address format")
        return value

class VulnerabilityAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = VulnerabilityAlert
        fields = ['id', 'severity', 'title', 'component', 'detected', 'status']

class ComplianceReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComplianceReport
        fields = ['id', 'type', 'status', 'last_audit', 'next_audit']

class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        tenant = self.context['request'].tenant
        with tenant_context(tenant):
            if not CustomUser.objects.filter(email=value, tenant=tenant).exists():
                raise serializers.ValidationError(f"No user found with email '{value}' for this tenant.")
        return value

class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField(required=True)
    new_password = serializers.CharField(write_only=True, min_length=8, required=True)

    def validate_token(self, value):
        tenant = self.context['request'].tenant
        with tenant_context(tenant):
            try:
                reset_token = PasswordResetToken.objects.get(token=value, tenant=tenant)
                if reset_token.expires_at < timezone.now():
                    raise serializers.ValidationError("This token has expired.")
                if reset_token.used:
                    raise serializers.ValidationError("This token has already been used.")
            except PasswordResetToken.DoesNotExist:
                raise serializers.ValidationError("Invalid token.")
        return value

    def validate_new_password(self, value):
        if not any(c.isupper() for c in value) or not any(c.isdigit() for c in value):
            raise serializers.ValidationError("Password must contain at least one uppercase letter and one number.")
        return value



class UserSerializer(serializers.ModelSerializer):
    profile_picture = serializers.ImageField(required=False, allow_null=True, use_url=False, write_only=True)
    profile_picture_url = serializers.SerializerMethodField(read_only=True)
    phone = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    title = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    bio = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    facebook_link = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    twitter_link = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    linkedin_link = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    password = serializers.CharField(write_only=True, required=True)  # Password is required for registration
    last_login = serializers.DateTimeField(format="%Y-%m-%d %H:%M", read_only=True)

    class Meta:
        model = CustomUser
        fields = [
            'id', 'email', 'first_name', 'last_name', 'role', 'status', 'is_locked', 'is_active',
            'date_joined', 'last_login', 'phone', 'title', 'bio', 'facebook_link', 'login_attempts',
            'twitter_link', 'linkedin_link', 'profile_picture', 'profile_picture_url', 'password', 'tenant', 'student_id'
        ]
        read_only_fields = ['id', 'date_joined', 'last_login', 'is_active', 'tenant']

    def get_profile_picture_url(self, instance):
        if instance.profile_picture:
            print("Profile picture value:", instance.profile_picture)
            storage_service = get_storage_service()
            url = storage_service.get_public_url(instance.profile_picture)
            print("Generated URL:", url)
            return url
        return None

    def validate(self, data):
        if 'password' in data and data['password'] and len(data['password']) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters long")
        if 'email' in data:
            tenant = self.context['request'].tenant
            with tenant_context(tenant):
                qs = CustomUser.objects.filter(email=data['email'], tenant=tenant, is_deleted=False)
                # Exclude self when updating
                if self.instance:
                    qs = qs.exclude(pk=self.instance.pk)
                if qs.exists():
                    raise serializers.ValidationError("Email already exists")
        return data

    def create(self, validated_data):
        profile_picture_file = validated_data.pop('profile_picture', None)
        user = CustomUser.objects.create_user(
            **validated_data
        )
        if profile_picture_file:
            file_name = f"profile_pics/{user.id}/{uuid.uuid4().hex}_{profile_picture_file.name}"
            storage_service = get_storage_service()
            try:
                storage_service.upload_file(profile_picture_file, file_name, content_type=profile_picture_file.content_type)
                user.profile_picture = file_name
                user.save()
            except Exception as e:
                logger.error(f"Failed to upload profile picture: {str(e)}")
                raise serializers.ValidationError("Failed to upload profile picture")
        return user

    def update(self, instance, validated_data):
        profile_picture_file = validated_data.pop('profile_picture', None)
        if profile_picture_file:
            storage_service = get_storage_service()
            if instance.profile_picture:
                try:
                    storage_service.delete_file(instance.profile_picture)
                except Exception as e:
                    logger.error(f"Error deleting old profile picture: {e}")
            file_name = f"profile_pics/{instance.id}/{uuid.uuid4().hex}_{profile_picture_file.name}"
            try:
                storage_service.upload_file(profile_picture_file, file_name, content_type=profile_picture_file.content_type)
                instance.profile_picture = file_name
                instance.save()
            except Exception as e:
                logger.error(f"Failed to upload profile picture: {str(e)}")
                raise serializers.ValidationError("Failed to upload profile picture")
        return super().update(instance, validated_data)

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        # Remove the raw profile_picture field from output
        rep.pop('profile_picture', None)
        return rep