from rest_framework import serializers
from django.conf import settings
import requests
import logging
from drf_spectacular.utils import extend_schema_field
from .models import Role, Group, GroupMembership
from activitylog.models import ActivityLog

logger = logging.getLogger('group_management')

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

class RoleSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(read_only=True)
    tenant_domain = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = ['id', 'tenant_id', 'tenant_name', 'tenant_domain', 'name', 'code', 'description',
                  'permissions', 'is_default', 'is_system', 'is_active']
        read_only_fields = ['id', 'tenant_id', 'tenant_name', 'is_system']

    def validate(self, attrs):
        request = self.context.get('request')
        tenant_id = get_tenant_id_from_jwt(request)
        if 'tenant_id' in attrs and attrs['tenant_id'] != tenant_id:
            raise serializers.ValidationError({"tenant_id": "Tenant ID mismatch."})
        attrs['tenant_id'] = tenant_id
        if self.instance and self.instance.is_system:
            if any(key in attrs for key in ['code', 'is_system']):
                raise serializers.ValidationError("Cannot modify code or system status of system roles")
        return attrs

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

    def update(self, instance, validated_data):
        request = self.context.get('request')
        tenant_id = get_tenant_id_from_jwt(request)
        validated_data['tenant_id'] = tenant_id
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
        return super().update(instance, validated_data)

class GroupMembershipSerializer(serializers.ModelSerializer):
    user_details = serializers.SerializerMethodField()
    role = RoleSerializer(read_only=True)
    user_id = serializers.CharField(write_only=True)
    group_id = serializers.CharField(write_only=True)
    role_id = serializers.CharField(write_only=True, required=False, allow_null=True)
    tenant_name = serializers.CharField(read_only=True)
    tenant_domain = serializers.SerializerMethodField()

    class Meta:
        model = GroupMembership
        fields = ['id', 'tenant_id', 'tenant_name', 'tenant_domain', 'user_id', 'user_details',
                  'group_id', 'role_id', 'role', 'is_active', 'is_primary']
        read_only_fields = ['id', 'tenant_id', 'tenant_name', 'role']

    def validate(self, attrs):
        request = self.context.get('request')
        tenant_id = get_tenant_id_from_jwt(request)
        if 'tenant_id' in attrs and attrs['tenant_id'] != tenant_id:
            raise serializers.ValidationError({"tenant_id": "Tenant ID mismatch."})
        attrs['tenant_id'] = tenant_id

        # Validate user_id
        if 'user_id' in attrs:
            try:
                user_response = requests.get(
                    f'{settings.AUTH_SERVICE_URL}/api/user/users/{attrs["user_id"]}/',
                    headers={'Authorization': f'Bearer {request.META.get("HTTP_AUTHORIZATION", "").split(" ")[1]}'}
                )
                if user_response.status_code != 200:
                    raise serializers.ValidationError({"user_id": "Invalid user ID."})
            except Exception as e:
                logger.error(f"Error validating user_id {attrs['user_id']}: {str(e)}")
                raise serializers.ValidationError({"user_id": "Error validating user ID."})

        # Validate group_id
        if 'group_id' in attrs:
            if not Group.objects.filter(id=attrs['group_id'], tenant_id=tenant_id).exists():
                raise serializers.ValidationError({"group_id": "Invalid group ID or group does not belong to this tenant."})

        # Validate role_id
        if 'role_id' in attrs and attrs['role_id']:
            if not Role.objects.filter(id=attrs['role_id'], tenant_id=tenant_id).exists():
                raise serializers.ValidationError({"role_id": "Invalid role ID or role does not belong to this tenant."})

        return attrs

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

    def update(self, instance, validated_data):
        request = self.context.get('request')
        tenant_id = get_tenant_id_from_jwt(request)
        validated_data['tenant_id'] = tenant_id
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
        return super().update(instance, validated_data)

class GroupSerializer(serializers.ModelSerializer):
    role = RoleSerializer(read_only=True)
    role_id = serializers.CharField(write_only=True, required=False, allow_null=True)
    memberships = GroupMembershipSerializer(many=True, read_only=True)
    tenant_name = serializers.CharField(read_only=True)
    tenant_domain = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = ['id', 'tenant_id', 'tenant_name', 'tenant_domain', 'name', 'description',
                  'role', 'role_id', 'is_active', 'is_system', 'memberships']
        read_only_fields = ['id', 'tenant_id', 'tenant_name', 'is_system', 'memberships']

    def validate(self, attrs):
        request = self.context.get('request')
        tenant_id = get_tenant_id_from_jwt(request)
        if 'tenant_id' in attrs and attrs['tenant_id'] != tenant_id:
            raise serializers.ValidationError({"tenant_id": "Tenant ID mismatch."})
        attrs['tenant_id'] = tenant_id
        if self.instance and self.instance.is_system:
            if any(key in attrs for key in ['name', 'role_id', 'is_system']):
                raise serializers.ValidationError("Cannot modify name, role, or system status of system groups")
        if 'role_id' in attrs and attrs['role_id']:
            if not Role.objects.filter(id=attrs['role_id'], tenant_id=tenant_id).exists():
                raise serializers.ValidationError({"role_id": "Invalid role ID or role does not belong to this tenant."})
        return attrs

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

    def update(self, instance, validated_data):
        request = self.context.get('request')
        tenant_id = get_tenant_id_from_jwt(request)
        validated_data['tenant_id'] = tenant_id
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
        return super().update(instance, validated_data)