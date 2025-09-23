from rest_framework import serializers
from django.conf import settings
import requests
import logging
import jwt
from drf_spectacular.utils import extend_schema_field
from .models import Message, MessageRecipient, MessageAttachment, MessageType
from utils.storage import get_storage_service
import uuid

logger = logging.getLogger('messaging')

def get_tenant_id_from_jwt(request):
    auth_header = request.META.get("HTTP_AUTHORIZATION", "")
    if not auth_header.startswith("Bearer "):
        raise serializers.ValidationError("No valid Bearer token provided.")
    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        return payload.get("tenant_unique_id")
    except Exception:
        raise serializers.ValidationError("Invalid JWT token.")

class MessageTypeSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(read_only=True)
    tenant_domain = serializers.SerializerMethodField()

    class Meta:
        model = MessageType
        fields = ["id", "tenant_id", "tenant_name", "tenant_domain", "value", "label", "created_at", "updated_at"]
        read_only_fields = ["id", "tenant_id", "tenant_name", "created_at", "updated_at"]

    def validate_value(self, value):
        if not value.isidentifier():
            raise serializers.ValidationError("Value may contain only letters, digits, and underscores.")
        return value.lower()

    def validate(self, data):
        request = self.context.get('request')
        tenant_id = get_tenant_id_from_jwt(request)
        if 'tenant_id' in data and data['tenant_id'] != tenant_id:
            raise serializers.ValidationError({"tenant_id": "Tenant ID mismatch."})
        data['tenant_id'] = tenant_id
        return data

    def create(self, validated_data):
        request = self.context.get('request')
        tenant_id = get_tenant_id_from_jwt(request)
        validated_data['tenant_id'] = tenant_id
        tenant_name = None
        try:
            tenant_response = requests.get(
                f"{settings.AUTH_SERVICE_URL}/api/tenant/tenants/{tenant_id}/",
                headers={'Authorization': request.META.get("HTTP_AUTHORIZATION", "")}
            )
            if tenant_response.status_code == 200:
                tenant_data = tenant_response.json()
                tenant_name = tenant_data.get('name')
        except Exception as e:
            logger.error(f"Error fetching tenant name for {tenant_id}: {str(e)}")
        if tenant_name:
            validated_data['tenant_name'] = tenant_name
        return MessageType.objects.create(**validated_data)

    def update(self, instance, validated_data):
        tenant_id = get_tenant_id_from_jwt(self.context.get('request'))
        validated_data['tenant_id'] = tenant_id
        if not instance.tenant_name:
            try:
                tenant_response = requests.get(
                    f"{settings.AUTH_SERVICE_URL}/api/tenant/tenants/{tenant_id}/",
                    headers={'Authorization': self.context['request'].META.get("HTTP_AUTHORIZATION", "")}
                )
                if tenant_response.status_code == 200:
                    tenant_data = tenant_response.json()
                    validated_data['tenant_name'] = tenant_data.get('name')
            except Exception as e:
                logger.error(f"Error fetching tenant name for {tenant_id}: {str(e)}")
        return super().update(instance, validated_data)

    @extend_schema_field({'type': 'string', 'example': 'example.com'})
    def get_tenant_domain(self, obj):
        try:
            tenant_response = requests.get(
                f'{settings.AUTH_SERVICE_URL}/api/tenant/tenants/{obj.tenant_id}/',
                headers={'Authorization': f'Bearer {self.context["request"].META.get("HTTP_AUTHORIZATION", "").split(" ")[1]}'}
            )
            if tenant_response.status_code == 200:
                tenant_data = tenant_response.json()
                domains = tenant_data.get('domains', [])
                primary_domain = next((d['domain'] for d in domains if d.get('is_primary')), None)
                return primary_domain
            logger.error(f"Failed to fetch tenant {obj.tenant_id} from auth_service")
        except Exception as e:
            logger.error(f"Error fetching tenant domain for {obj.tenant_id}: {str(e)}")
        return None

class MessageAttachmentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = MessageAttachment
        fields = ["id", "message", "file", "file_url", "original_filename", "uploaded_at"]
        read_only_fields = ["original_filename", "uploaded_at", "file_url"]

    def get_file_url(self, obj):
        storage_type = getattr(settings, 'STORAGE_TYPE', 'local').lower()
        if storage_type == 'local' and obj.file:
            return obj.file.url
        return obj.file_url

    def create(self, validated_data):
        file_obj = validated_data.pop("file", None)
        original_filename = validated_data.get("original_filename", None)
        tenant_id = get_tenant_id_from_jwt(self.context["request"])
        if file_obj:
            file_name = f"messaging/{tenant_id}/{uuid.uuid4().hex}_{file_obj.name}"
            storage_type = getattr(settings, 'STORAGE_TYPE', 'local').lower()
            if storage_type == 'local':
                validated_data["file"] = file_name
                validated_data["original_filename"] = original_filename or file_obj.name
            else:
                storage_service = get_storage_service(storage_type)
                upload_success = storage_service.upload_file(
                    file_obj, file_name, getattr(file_obj, "content_type", "application/octet-stream")
                )
                if not upload_success:
                    raise serializers.ValidationError("Failed to upload attachment")
                validated_data["file"] = None
                validated_data["file_url"] = storage_service.get_public_url(file_name)
                validated_data["original_filename"] = original_filename or file_obj.name
        return MessageAttachment.objects.create(**validated_data)

class MessageRecipientSerializer(serializers.ModelSerializer):
    recipient_details = serializers.SerializerMethodField()
    recipient_group_name = serializers.SerializerMethodField()

    class Meta:
        model = MessageRecipient
        fields = ["id", "message", "recipient_id", "recipient_details", "recipient_group_id", "recipient_group_name", "group_member_id", "read", "read_at"]
        read_only_fields = ["recipient_id", "recipient_group_id", "group_member_id", "read", "read_at"]

    @extend_schema_field({
        'type': 'object',
        'properties': {
            'email': {'type': 'string'},
            'first_name': {'type': 'string'},
            'last_name': {'type': 'string'},
            'job_role': {'type': 'string'}
        }
    })
    def get_recipient_details(self, obj):
        user_id = obj.recipient_id or obj.group_member_id
        if user_id:
            try:
                user_response = requests.get(
                    f'{settings.AUTH_SERVICE_URL}/api/user/users/{user_id}/',
                    headers={'Authorization': f'Bearer {self.context["request"].META.get("HTTP_AUTHORIZATION", "").split(" ")[1]}'}
                )
                if user_response.status_code == 200:
                    user_data = user_response.json()
                    return {
                        'email': user_data.get('email', ''),
                        'first_name': user_data.get('first_name', ''),
                        'last_name': user_data.get('last_name', ''),
                        'job_role': user_data.get('job_role', '')
                    }
                logger.error(f"Failed to fetch user {user_id} from auth_service")
            except Exception as e:
                logger.error(f"Error fetching recipient details for {user_id}: {str(e)}")
        return None

    @extend_schema_field({'type': 'string', 'example': 'Group Name'})
    def get_recipient_group_name(self, obj):
        if obj.recipient_group_id:
            try:
                group_response = requests.get(
                    f'{settings.AUTH_SERVICE_URL}/api/tenant/groups/{obj.recipient_group_id}/',
                    headers={'Authorization': f'Bearer {self.context["request"].META.get("HTTP_AUTHORIZATION", "").split(" ")[1]}'}
                )
                if group_response.status_code == 200:
                    return group_response.json().get('name', '')
                logger.error(f"Failed to fetch group {obj.recipient_group_id} from auth_service")
            except Exception as e:
                logger.error(f"Error fetching group name for {obj.recipient_group_id}: {str(e)}")
        return None

class MessageSerializer(serializers.ModelSerializer):
    is_read = serializers.SerializerMethodField()
    message_type = serializers.PrimaryKeyRelatedField(queryset=MessageType.objects.all())
    sender_details = serializers.SerializerMethodField()
    recipients = MessageRecipientSerializer(many=True, read_only=True)
    attachments = MessageAttachmentSerializer(many=True, read_only=True)
    parent_message = serializers.PrimaryKeyRelatedField(queryset=Message.objects.all(), allow_null=True, required=False)
    recipient_user_ids = serializers.ListField(child=serializers.CharField(), write_only=True, required=False)
    recipient_group_ids = serializers.ListField(child=serializers.CharField(), write_only=True, required=False)
    tenant_name = serializers.CharField(read_only=True)
    tenant_domain = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            "id", "tenant_id", "tenant_name", "tenant_domain", "sender_id", "sender_details", "subject", "content",
            "message_type", "sent_at", "status", "parent_message", "is_forward", "recipients",
            "attachments", "recipient_user_ids", "recipient_group_ids", "is_read"
        ]
        read_only_fields = ["sender_id", "sent_at", "recipients", "attachments", "tenant_id"]

    def validate(self, data):
        request = self.context.get('request')
        tenant_id = get_tenant_id_from_jwt(request)
        if 'tenant_id' in data and data['tenant_id'] != tenant_id:
            raise serializers.ValidationError({"tenant_id": "Tenant ID mismatch."})
        data['tenant_id'] = tenant_id

        # Validate recipient_user_ids
        for user_id in data.get('recipient_user_ids', []):
            try:
                user_response = requests.get(
                    f'{settings.AUTH_SERVICE_URL}/api/user/users/{user_id}/',
                    headers={'Authorization': f'Bearer {request.META.get("HTTP_AUTHORIZATION", "").split(" ")[1]}'}
                )
                if user_response.status_code != 200:
                    raise serializers.ValidationError({"recipient_user_ids": f"Invalid user ID: {user_id}"})
            except Exception as e:
                logger.error(f"Error validating user {user_id}: {str(e)}")
                raise serializers.ValidationError({"recipient_user_ids": f"Error validating user ID: {user_id}"})

        # Validate recipient_group_ids
        for group_id in data.get('recipient_group_ids', []):
            try:
                group_response = requests.get(
                    f'{settings.AUTH_SERVICE_URL}/api/tenant/groups/{group_id}/',
                    headers={'Authorization': f'Bearer {request.META.get("HTTP_AUTHORIZATION", "").split(" ")[1]}'}
                )
                if group_response.status_code != 200:
                    raise serializers.ValidationError({"recipient_group_ids": f"Invalid group ID: {group_id}"})
                group_data = group_response.json()
                if group_data.get('tenant_unique_id') != tenant_id:
                    raise serializers.ValidationError({"recipient_group_ids": f"Group {group_id} does not belong to tenant {tenant_id}"})
            except Exception as e:
                logger.error(f"Error validating group {group_id}: {str(e)}")
                raise serializers.ValidationError({"recipient_group_ids": f"Error validating group ID: {group_id}"})

        return data

    def create(self, validated_data):
        request = self.context.get('request')
        tenant_id = get_tenant_id_from_jwt(request)
        validated_data['tenant_id'] = tenant_id
        validated_data['sender_id'] = request.jwt_payload.get('user', {}).get('id')
        recipient_user_ids = validated_data.pop("recipient_user_ids", [])
        recipient_group_ids = validated_data.pop("recipient_group_ids", [])
        attachments_data = request.FILES.getlist("attachments")
        tenant_name = None
        try:
            tenant_response = requests.get(
                f"{settings.AUTH_SERVICE_URL}/api/tenant/tenants/{tenant_id}/",
                headers={'Authorization': request.META.get("HTTP_AUTHORIZATION", "")}
            )
            if tenant_response.status_code == 200:
                tenant_data = tenant_response.json()
                tenant_name = tenant_data.get('name')
        except Exception as e:
            logger.error(f"Error fetching tenant name for {tenant_id}: {str(e)}")
        if tenant_name:
            validated_data['tenant_name'] = tenant_name

        message = Message.objects.create(**validated_data)
        recipients = []
        for user_id in recipient_user_ids:
            recipients.append(MessageRecipient(message=message, recipient_id=user_id))
        for group_id in recipient_group_ids:
            try:
                group_response = requests.get(
                    f'{settings.AUTH_SERVICE_URL}/api/tenant/groups/{group_id}/',
                    headers={'Authorization': f'Bearer {request.META.get("HTTP_AUTHORIZATION", "").split(" ")[1]}'}
                )
                if group_response.status_code == 200:
                    group_data = group_response.json()
                    user_ids = group_data.get('members', [])
                    for user_id in user_ids:
                        recipients.append(MessageRecipient(message=message, recipient_group_id=group_id, group_member_id=user_id))
            except Exception as e:
                logger.error(f"Error fetching group members for {group_id}: {str(e)}")
                raise serializers.ValidationError(f"Error processing group {group_id}")
        MessageRecipient.objects.bulk_create(recipients)
        for file_obj in attachments_data:
            file_name = f"messaging/{tenant_id}/{uuid.uuid4().hex}_{file_obj.name}"
            storage_type = getattr(settings, 'STORAGE_TYPE', 'local').lower()
            if storage_type == 'local':
                MessageAttachment.objects.create(
                    message=message,
                    file=file_name,
                    original_filename=file_obj.name
                )
            else:
                storage_service = get_storage_service(storage_type)
                upload_success = storage_service.upload_file(
                    file_obj, file_name, getattr(file_obj, "content_type", "application/octet-stream")
                )
                if not upload_success:
                    raise serializers.ValidationError("Failed to upload attachment")
                MessageAttachment.objects.create(
                    message=message,
                    file=None,
                    file_url=storage_service.get_public_url(file_name),
                    original_filename=file_obj.name
                )
        return message

    def update(self, instance, validated_data):
        tenant_id = get_tenant_id_from_jwt(self.context.get('request'))
        validated_data['tenant_id'] = tenant_id
        validated_data['sender_id'] = self.context['request'].jwt_payload.get('user', {}).get('id')
        attachments_data = self.context["request"].FILES.getlist("attachments")
        if not instance.tenant_name:
            try:
                tenant_response = requests.get(
                    f"{settings.AUTH_SERVICE_URL}/api/tenant/tenants/{tenant_id}/",
                    headers={'Authorization': self.context['request'].META.get("HTTP_AUTHORIZATION", "")}
                )
                if tenant_response.status_code == 200:
                    tenant_data = tenant_response.json()
                    validated_data['tenant_name'] = tenant_data.get('name')
            except Exception as e:
                logger.error(f"Error fetching tenant name for {tenant_id}: {str(e)}")
        instance = super().update(instance, validated_data)
        for file_obj in attachments_data:
            file_name = f"messaging/{tenant_id}/{uuid.uuid4().hex}_{file_obj.name}"
            storage_type = getattr(settings, 'STORAGE_TYPE', 'local').lower()
            if storage_type == 'local':
                MessageAttachment.objects.create(
                    message=instance,
                    file=file_name,
                    original_filename=file_obj.name
                )
            else:
                storage_service = get_storage_service(storage_type)
                upload_success = storage_service.upload_file(
                    file_obj, file_name, getattr(file_obj, "content_type", "application/octet-stream")
                )
                if not upload_success:
                    raise serializers.ValidationError("Failed to upload attachment")
                MessageAttachment.objects.create(
                    message=instance,
                    file=None,
                    file_url=storage_service.get_public_url(file_name),
                    original_filename=file_obj.name
                )
        return instance

    @extend_schema_field({
        'type': 'object',
        'properties': {
            'email': {'type': 'string'},
            'first_name': {'type': 'string'},
            'last_name': {'type': 'string'},
            'job_role': {'type': 'string'}
        }
    })
    def get_sender_details(self, obj):
        if obj.sender_id:
            try:
                user_response = requests.get(
                    f'{settings.AUTH_SERVICE_URL}/api/user/users/{obj.sender_id}/',
                    headers={'Authorization': f'Bearer {self.context["request"].META.get("HTTP_AUTHORIZATION", "").split(" ")[1]}'}
                )
                if user_response.status_code == 200:
                    user_data = user_response.json()
                    return {
                        'email': user_data.get('email', ''),
                        'first_name': user_data.get('first_name', ''),
                        'last_name': user_data.get('last_name', ''),
                        'job_role': user_data.get('job_role', '')
                    }
                logger.error(f"Failed to fetch user {obj.sender_id} from auth_service")
            except Exception as e:
                logger.error(f"Error fetching sender details for {obj.sender_id}: {str(e)}")
        return None

    @extend_schema_field({'type': 'string', 'example': 'example.com'})
    def get_tenant_domain(self, obj):
        try:
            tenant_response = requests.get(
                f'{settings.AUTH_SERVICE_URL}/api/tenant/tenants/{obj.tenant_id}/',
                headers={'Authorization': f'Bearer {self.context["request"].META.get("HTTP_AUTHORIZATION", "").split(" ")[1]}'}
            )
            if tenant_response.status_code == 200:
                tenant_data = tenant_response.json()
                domains = tenant_data.get('domains', [])
                primary_domain = next((d['domain'] for d in domains if d.get('is_primary')), None)
                return primary_domain
            logger.error(f"Failed to fetch tenant {obj.tenant_id} from auth_service")
        except Exception as e:
            logger.error(f"Error fetching tenant domain for {obj.tenant_id}: {str(e)}")
        return None

    def get_is_read(self, obj):
        user_id = self.context["request"].jwt_payload.get('user', {}).get('id')
        mr = obj.recipients.filter(recipient_id=user_id).first()
        return mr.read if mr else False