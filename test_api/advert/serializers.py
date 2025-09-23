from rest_framework import serializers
from django.conf import settings
import requests
import logging
from datetime import datetime
from drf_spectacular.utils import extend_schema_field
from .models import Advert
from activitylog.models import ActivityLog
from django.http import QueryDict

logger = logging.getLogger('advert')

def get_tenant_id_from_jwt(request):
    auth_header = request.META.get("HTTP_AUTHORIZATION", "")
    if not auth_header.startswith("Bearer "):
        raise serializers.ValidationError("No valid Bearer token provided.")
    token = auth_header.split(" ")[1]
    try:
        import jwt
        payload = jwt.decode(token, options={"verify_signature": False})
        return payload.get("tenant_unique_id")
    except Exception:
        raise serializers.ValidationError("Invalid JWT token.")

class AdvertSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(required=False, allow_null=True, allow_empty_file=True)
    image_url = serializers.SerializerMethodField()
    creator_details = serializers.SerializerMethodField()
    tenant_domain = serializers.SerializerMethodField()
    tenant_name = serializers.CharField(read_only=True)
    creator_id = serializers.CharField(read_only=True)

    class Meta:
        model = Advert
        fields = [
            'id', 'tenant_id', 'tenant_name', 'tenant_domain', 'title', 'content', 'link', 'image',
            'image_url', 'start_date', 'end_date', 'status', 'priority', 'target',
            'creator_id', 'creator_details', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'tenant_id', 'tenant_name', 'creator_id', 'created_at', 'updated_at', 'image_url'
        ]
        extra_kwargs = {
            'start_date': {'required': True},
            'end_date': {'required': True},
        }

    def validate(self, data):
        logger.debug(f"Validation data: {data}")
        request = self.context.get('request')
        tenant_id = get_tenant_id_from_jwt(request)
        if 'tenant_id' in data and data['tenant_id'] != tenant_id:
            raise serializers.ValidationError({"tenant_id": "Tenant ID mismatch."})
        if data['start_date'] > data['end_date']:
            raise serializers.ValidationError("End date must be after start date")
        return data

    def to_internal_value(self, data):
        logger.debug(f"Raw incoming data: {data}")
        # Handle both form data and JSON data
        if isinstance(data, QueryDict):
            data = data.dict()
        # Convert date strings to datetime objects if needed
        if 'start_date' in data and isinstance(data['start_date'], str):
            try:
                data['start_date'] = datetime.fromisoformat(data['start_date'])
            except (ValueError, TypeError) as e:
                logger.error(f"Error parsing start_date: {e}")
                pass
        if 'end_date' in data and isinstance(data['end_date'], str):
            try:
                data['end_date'] = datetime.fromisoformat(data['end_date'])
            except (ValueError, TypeError) as e:
                logger.error(f"Error parsing end_date: {e}")
                pass
        logger.debug(f"Processed data before super(): {data}")
        result = super().to_internal_value(data)
        logger.debug(f"Result from super().to_internal_value(): {result}")
        return result

    @extend_schema_field({
        'type': 'string',
        'example': 'https://storage.example.com/adverts/tenant_id/image.jpg'
    })
    def get_image_url(self, obj):
        storage_type = getattr(settings, 'STORAGE_TYPE', 'local').lower()
        if storage_type == 'local':
            return obj.image.url if obj.image else None
        return obj.image_url

    @extend_schema_field({
        'type': 'object',
        'properties': {
            'email': {'type': 'string'},
            'first_name': {'type': 'string'},
            'last_name': {'type': 'string'},
            'job_role': {'type': 'string'}
        }
    })
    def get_creator_details(self, obj):
        if obj.creator_id:
            try:
                user_response = requests.get(
                    f'{settings.AUTH_SERVICE_URL}/api/user/users/{obj.creator_id}/',
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
                logger.error(f"Failed to fetch user {obj.creator_id} from auth_service")
            except Exception as e:
                logger.error(f"Error fetching creator details for {obj.creator_id}: {str(e)}")
        return None

    @extend_schema_field({
        'type': 'string',
        'example': 'example.com'
    })
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

    def create(self, validated_data):
        request = self.context.get('request')
        tenant_id = get_tenant_id_from_jwt(request)
        validated_data['tenant_id'] = tenant_id
        validated_data['creator_id'] = request.jwt_payload.get('user', {}).get('id')

        # Fetch tenant name from auth_service
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

        image_file = validated_data.pop('image', None)
        instance = super().create(validated_data)
        self._handle_image_upload(instance, image_file)
        return instance

    def update(self, instance, validated_data):
        request = self.context.get('request')
        tenant_id = get_tenant_id_from_jwt(request)
        validated_data['tenant_id'] = tenant_id
        validated_data['creator_id'] = request.jwt_payload.get('user', {}).get('id')

        # Fetch tenant name if not already set
        if not instance.tenant_name:
            try:
                tenant_response = requests.get(
                    f"{settings.AUTH_SERVICE_URL}/api/tenant/tenants/{tenant_id}/",
                    headers={'Authorization': request.META.get("HTTP_AUTHORIZATION", "")}
                )
                if tenant_response.status_code == 200:
                    tenant_data = tenant_response.json()
                    validated_data['tenant_name'] = tenant_data.get('name')
            except Exception as e:
                logger.error(f"Error fetching tenant name for {tenant_id}: {str(e)}")

        image_file = validated_data.pop('image', None)
        instance = super().update(instance, validated_data)
        self._handle_image_upload(instance, image_file)
        return instance

    def _handle_image_upload(self, instance, image_file):
        if image_file:
            from utils.storage import get_storage_service
            import uuid
            ext = image_file.name.split('.')[-1]
            file_name = f"adverts/{instance.tenant_id}/{instance.id}_{uuid.uuid4()}.{ext}"
            content_type = getattr(image_file, 'content_type', 'application/octet-stream')
            storage_type = getattr(settings, 'STORAGE_TYPE', 'local').lower()
            if storage_type == 'local':
                instance.image.save(file_name, image_file, save=True)
            else:
                storage = get_storage_service(storage_type)
                upload_success = storage.upload_file(image_file, file_name, content_type)
                if not upload_success:
                    raise serializers.ValidationError({"image": "Failed to upload image."})
                public_url = storage.get_public_url(file_name)
                instance.image_url = public_url
                instance.image = None
                instance.save(update_fields=["image_url", "image"])