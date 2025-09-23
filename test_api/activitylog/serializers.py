from rest_framework import serializers
from django.conf import settings
import requests
import logging
from rest_framework.exceptions import ValidationError
from drf_spectacular.utils import extend_schema_field
from .models import ActivityLog

logger = logging.getLogger('activitylog')

def get_tenant_id_from_jwt(request):
    auth_header = request.META.get("HTTP_AUTHORIZATION", "")
    if not auth_header.startswith("Bearer "):
        raise ValidationError("No valid Bearer token provided.")
    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        return payload.get("tenant_unique_id")
    except Exception:
        raise ValidationError("Invalid JWT token.")

class ActivityLogSerializer(serializers.ModelSerializer):
    user_email = serializers.SerializerMethodField()
    user_details = serializers.SerializerMethodField()
    tenant_domain = serializers.SerializerMethodField()
    tenant_name = serializers.CharField(read_only=True)

    class Meta:
        model = ActivityLog
        fields = [
            'id', 'tenant_id', 'tenant_name', 'tenant_domain', 'user_id', 'user_email', 'user_details',
            'activity_type', 'details', 'ip_address', 'device_info', 'timestamp', 'status'
        ]
        read_only_fields = ['id', 'tenant_id', 'tenant_name', 'user_id', 'timestamp']

    def validate_status(self, value):
        if value not in dict(ActivityLog.STATUS_CHOICES):
            raise serializers.ValidationError(
                f"Invalid status. Must be one of: {', '.join(dict(ActivityLog.STATUS_CHOICES).keys())}"
            )
        return value

    def validate(self, data):
        request = self.context.get('request')
        tenant_id = get_tenant_id_from_jwt(request)
        if 'tenant_id' in data and data['tenant_id'] != tenant_id:
            raise serializers.ValidationError({"tenant_id": "Tenant ID mismatch."})
        data['tenant_id'] = tenant_id  # Inject tenant_id
        return data

    @extend_schema_field({
        'type': 'string',
        'example': 'user@example.com'
    })
    def get_user_email(self, obj):
        if obj.user_id:
            try:
                user_response = requests.get(
                    f'{settings.AUTH_SERVICE_URL}/api/user/users/{obj.user_id}/',
                    headers={'Authorization': f'Bearer {self.context["request"].META.get("HTTP_AUTHORIZATION", "").split(" ")[1]}'}
                )
                if user_response.status_code == 200:
                    return user_response.json().get('email', '')
                logger.error(f"Failed to fetch user {obj.user_id} from auth_service")
            except Exception as e:
                logger.error(f"Error fetching user email for {obj.user_id}: {str(e)}")
        return ''

    @extend_schema_field({
        'type': 'object',
        'properties': {
            'email': {'type': 'string'},
            'first_name': {'type': 'string'},
            'last_name': {'type': 'string'},
            'job_role': {'type': 'string'}
        }
    })
    def get_user_details(self, obj):
        if obj.user_id:
            try:
                user_response = requests.get(
                    f'{settings.AUTH_SERVICE_URL}/api/user/users/{obj.user_id}/',
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
                logger.error(f"Failed to fetch user {obj.user_id} from auth_service")
            except Exception as e:
                logger.error(f"Error fetching user details for {obj.user_id}: {str(e)}")
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
        validated_data['user_id'] = request.jwt_payload.get('user', {}).get('id')

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

        return super().create(validated_data)