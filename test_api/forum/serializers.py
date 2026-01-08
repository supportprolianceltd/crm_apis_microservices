from rest_framework import serializers
from django.conf import settings
import requests
import logging
from drf_spectacular.utils import extend_schema_field
from .models import Forum, ForumPost, ModerationQueue
from activitylog.models import ActivityLog

logger = logging.getLogger('forum')

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

class ForumPostSerializer(serializers.ModelSerializer):
    author_details = serializers.SerializerMethodField()
    moderated_by_details = serializers.SerializerMethodField()
    tenant_domain = serializers.SerializerMethodField()
    tenant_name = serializers.CharField(read_only=True)
    author_id = serializers.CharField(write_only=True, required=False, allow_null=True)
    moderated_by_id = serializers.CharField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = ForumPost
        fields = [
            'id', 'tenant_id', 'tenant_name', 'tenant_domain', 'forum', 'author_id', 'author_details',
            'content', 'created_at', 'updated_at', 'is_approved', 'moderated_at', 'moderated_by_id',
            'moderated_by_details'
        ]
        read_only_fields = [
            'id', 'tenant_id', 'tenant_name', 'created_at', 'updated_at', 'moderated_at',
            'author_details', 'moderated_by_details'
        ]

    def validate(self, data):
        request = self.context.get('request')
        tenant_id = get_tenant_id_from_jwt(request)
        if 'tenant_id' in data and data['tenant_id'] != tenant_id:
            raise serializers.ValidationError({"tenant_id": "Tenant ID mismatch."})
        data['tenant_id'] = tenant_id
        return data

    @extend_schema_field({
        'type': 'object',
        'properties': {
            'email': {'type': 'string'},
            'first_name': {'type': 'string'},
            'last_name': {'type': 'string'},
            'job_role': {'type': 'string'}
        }
    })
    def get_author_details(self, obj):
        if obj.author_id:
            try:
                user_response = requests.get(
                    f'{settings.AUTH_SERVICE_URL}/api/user/users/{obj.author_id}/',
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
                logger.error(f"Failed to fetch user {obj.author_id} from auth_service")
            except Exception as e:
                logger.error(f"Error fetching author details for {obj.author_id}: {str(e)}")
        return None

    @extend_schema_field({
        'type': 'object',
        'properties': {
            'email': {'type': 'string'},
            'first_name': {'type': 'string'},
            'last_name': {'type': 'string'},
            'job_role': {'type': 'string'}
        }
    })
    def get_moderated_by_details(self, obj):
        if obj.moderated_by_id:
            try:
                user_response = requests.get(
                    f'{settings.AUTH_SERVICE_URL}/api/user/users/{obj.moderated_by_id}/',
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
                logger.error(f"Failed to fetch user {obj.moderated_by_id} from auth_service")
            except Exception as e:
                logger.error(f"Error fetching moderated_by details for {obj.moderated_by_id}: {str(e)}")
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
        validated_data['author_id'] = request.jwt_payload.get('user', {}).get('id')
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
        validated_data['moderated_by_id'] = request.jwt_payload.get('user', {}).get('id')
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

class ForumSerializer(serializers.ModelSerializer):
    group_details = serializers.SerializerMethodField()
    created_by_details = serializers.SerializerMethodField()
    tenant_domain = serializers.SerializerMethodField()
    tenant_name = serializers.CharField(read_only=True)
    created_by_id = serializers.CharField(write_only=True, required=False)
    group_ids = serializers.ListField(child=serializers.CharField(), write_only=True, required=False)
    posts = ForumPostSerializer(many=True, read_only=True, default=[])
    post_count = serializers.SerializerMethodField()

    class Meta:
        model = Forum
        fields = [
            'id', 'tenant_id', 'tenant_name', 'tenant_domain', 'title', 'description',
            'group_ids', 'group_details', 'is_active', 'created_at', 'updated_at',
            'created_by_id', 'created_by_details', 'posts', 'post_count'
        ]
        read_only_fields = [
            'id', 'tenant_id', 'tenant_name', 'created_at', 'updated_at', 'posts',
            'created_by_details', 'group_details'
        ]

    def validate(self, data):
        request = self.context.get('request')
        tenant_id = get_tenant_id_from_jwt(request)
        if 'tenant_id' in data and data['tenant_id'] != tenant_id:
            raise serializers.ValidationError({"tenant_id": "Tenant ID mismatch."})
        data['tenant_id'] = tenant_id
        if 'group_ids' in data:
            for group_id in data['group_ids']:
                try:
                    group_response = requests.get(
                        f'{settings.AUTH_SERVICE_URL}/api/tenant/groups/{group_id}/',
                        headers={'Authorization': f'Bearer {request.META.get("HTTP_AUTHORIZATION", "").split(" ")[1]}'}
                    )
                    if group_response.status_code != 200:
                        raise serializers.ValidationError({"group_ids": f"Invalid group ID: {group_id}"})
                    group_data = group_response.json()
                    if group_data['tenant_unique_id'] != tenant_id:
                        raise serializers.ValidationError({"group_ids": f"Group {group_id} does not belong to tenant {tenant_id}"})
                except Exception as e:
                    logger.error(f"Error validating group {group_id}: {str(e)}")
                    raise serializers.ValidationError({"group_ids": f"Error validating group {group_id}"})
        return data

    def get_post_count(self, obj):
        return obj.posts.count()

    @extend_schema_field({
        'type': 'array',
        'items': {
            'type': 'object',
            'properties': {
                'id': {'type': 'string'},
                'name': {'type': 'string'}
            }
        }
    })
    def get_group_details(self, obj):
        if obj.group_ids:
            try:
                group_details = []
                for group_id in obj.group_ids:
                    group_response = requests.get(
                        f'{settings.AUTH_SERVICE_URL}/api/tenant/groups/{group_id}/',
                        headers={'Authorization': f'Bearer {self.context["request"].META.get("HTTP_AUTHORIZATION", "").split(" ")[1]}'}
                    )
                    if group_response.status_code == 200:
                        group_data = group_response.json()
                        group_details.append({
                            'id': group_id,
                            'name': group_data.get('name', '')
                        })
                    else:
                        logger.error(f"Failed to fetch group {group_id} from auth_service")
                return group_details
            except Exception as e:
                logger.error(f"Error fetching group details for {obj.group_ids}: {str(e)}")
        return []

    @extend_schema_field({
        'type': 'object',
        'properties': {
            'email': {'type': 'string'},
            'first_name': {'type': 'string'},
            'last_name': {'type': 'string'},
            'job_role': {'type': 'string'}
        }
    })
    def get_created_by_details(self, obj):
        if obj.created_by_id:
            try:
                user_response = requests.get(
                    f'{settings.AUTH_SERVICE_URL}/api/user/users/{obj.created_by_id}/',
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
                logger.error(f"Failed to fetch user {obj.created_by_id} from auth_service")
            except Exception as e:
                logger.error(f"Error fetching created_by details for {obj.created_by_id}: {str(e)}")
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
        validated_data['created_by_id'] = request.jwt_payload.get('user', {}).get('id')
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

class ModerationQueueSerializer(serializers.ModelSerializer):
    reported_by_details = serializers.SerializerMethodField()
    moderated_by_details = serializers.SerializerMethodField()
    tenant_domain = serializers.SerializerMethodField()
    tenant_name = serializers.CharField(read_only=True)
    reported_by_id = serializers.CharField(write_only=True, required=False, allow_null=True)
    moderated_by_id = serializers.CharField(write_only=True, required=False, allow_null=True)
    content_snippet = serializers.SerializerMethodField()

    class Meta:
        model = ModerationQueue
        fields = [
            'id', 'tenant_id', 'tenant_name', 'tenant_domain', 'content_type', 'content_id',
            'content', 'reported_by_id', 'reported_by_details', 'reason', 'status',
            'moderation_notes', 'moderated_by_id', 'moderated_by_details', 'created_at',
            'updated_at', 'content_snippet'
        ]
        read_only_fields = [
            'id', 'tenant_id', 'tenant_name', 'created_at', 'updated_at', 'content_snippet',
            'reported_by_details', 'moderated_by_details'
        ]

    def get_content_snippet(self, obj):
        return obj.content[:100] + ('...' if len(obj.content) > 100 else '')

    def validate(self, data):
        request = self.context.get('request')
        tenant_id = get_tenant_id_from_jwt(request)
        if 'tenant_id' in data and data['tenant_id'] != tenant_id:
            raise serializers.ValidationError({"tenant_id": "Tenant ID mismatch."})
        data['tenant_id'] = tenant_id
        return data

    @extend_schema_field({
        'type': 'object',
        'properties': {
            'email': {'type': 'string'},
            'first_name': {'type': 'string'},
            'last_name': {'type': 'string'},
            'job_role': {'type': 'string'}
        }
    })
    def get_reported_by_details(self, obj):
        if obj.reported_by_id:
            try:
                user_response = requests.get(
                    f'{settings.AUTH_SERVICE_URL}/api/user/users/{obj.reported_by_id}/',
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
                logger.error(f"Failed to fetch user {obj.reported_by_id} from auth_service")
            except Exception as e:
                logger.error(f"Error fetching reported_by details for {obj.reported_by_id}: {str(e)}")
        return None

    @extend_schema_field({
        'type': 'object',
        'properties': {
            'email': {'type': 'string'},
            'first_name': {'type': 'string'},
            'last_name': {'type': 'string'},
            'job_role': {'type': 'string'}
        }
    })
    def get_moderated_by_details(self, obj):
        if obj.moderated_by_id:
            try:
                user_response = requests.get(
                    f'{settings.AUTH_SERVICE_URL}/api/user/users/{obj.moderated_by_id}/',
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
                logger.error(f"Failed to fetch user {obj.moderated_by_id} from auth_service")
            except Exception as e:
                logger.error(f"Error fetching moderated_by details for {obj.moderated_by_id}: {str(e)}")
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
        validated_data['reported_by_id'] = request.jwt_payload.get('user', {}).get('id')
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
        validated_data['moderated_by_id'] = request.jwt_payload.get('user', {}).get('id')
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