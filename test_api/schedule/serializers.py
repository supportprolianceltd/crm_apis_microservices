from rest_framework import serializers
from django.conf import settings
import requests
import logging
import jwt
from drf_spectacular.utils import extend_schema_field
from .models import Schedule, ScheduleParticipant

logger = logging.getLogger('schedule')

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

class ScheduleParticipantSerializer(serializers.ModelSerializer):
    user_details = serializers.SerializerMethodField()
    group_name = serializers.SerializerMethodField()

    class Meta:
        model = ScheduleParticipant
        fields = ['id', 'user_id', 'user_details', 'group_id', 'group_name', 'is_optional', 'response_status', 'read']
        read_only_fields = ['user_id', 'group_id', 'read']

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

    @extend_schema_field({'type': 'string', 'example': 'Group Name'})
    def get_group_name(self, obj):
        if obj.group_id:
            try:
                group_response = requests.get(
                    f'{settings.AUTH_SERVICE_URL}/api/tenant/groups/{obj.group_id}/',
                    headers={'Authorization': f'Bearer {self.context["request"].META.get("HTTP_AUTHORIZATION", "").split(" ")[1]}'}
                )
                if group_response.status_code == 200:
                    return group_response.json().get('name', '')
                logger.error(f"Failed to fetch group {obj.group_id} from auth_service")
            except Exception as e:
                logger.error(f"Error fetching group name for {obj.group_id}: {str(e)}")
        return None

class ScheduleSerializer(serializers.ModelSerializer):
    creator_details = serializers.SerializerMethodField()
    participants = ScheduleParticipantSerializer(many=True, read_only=True)
    participant_user_ids = serializers.ListField(child=serializers.CharField(), write_only=True, required=False)
    participant_group_ids = serializers.ListField(child=serializers.CharField(), write_only=True, required=False)
    tenant_name = serializers.CharField(read_only=True)
    tenant_domain = serializers.SerializerMethodField()

    class Meta:
        model = Schedule
        fields = [
            'id', 'tenant_id', 'tenant_name', 'tenant_domain', 'title', 'description', 'start_time', 'end_time',
            'location', 'is_all_day', 'creator_id', 'creator_details', 'created_at', 'updated_at',
            'participants', 'participant_user_ids', 'participant_group_ids'
        ]
        read_only_fields = ['tenant_id', 'tenant_name', 'creator_id', 'created_at', 'updated_at', 'participants']

    def validate(self, data):
        request = self.context.get('request')
        tenant_id = get_tenant_id_from_jwt(request)
        if 'tenant_id' in data and data['tenant_id'] != tenant_id:
            raise serializers.ValidationError({"tenant_id": "Tenant ID mismatch."})
        data['tenant_id'] = tenant_id

        # Validate participant_user_ids
        for user_id in data.get('participant_user_ids', []):
            try:
                user_response = requests.get(
                    f'{settings.AUTH_SERVICE_URL}/api/user/users/{user_id}/',
                    headers={'Authorization': f'Bearer {request.META.get("HTTP_AUTHORIZATION", "").split(" ")[1]}'}
                )
                if user_response.status_code != 200:
                    raise serializers.ValidationError({"participant_user_ids": f"Invalid user ID: {user_id}"})
            except Exception as e:
                logger.error(f"Error validating user {user_id}: {str(e)}")
                raise serializers.ValidationError({"participant_user_ids": f"Error validating user ID: {user_id}"})

        # Validate participant_group_ids
        for group_id in data.get('participant_group_ids', []):
            try:
                group_response = requests.get(
                    f'{settings.AUTH_SERVICE_URL}/api/tenant/groups/{group_id}/',
                    headers={'Authorization': f'Bearer {request.META.get("HTTP_AUTHORIZATION", "").split(" ")[1]}'}
                )
                if group_response.status_code != 200:
                    raise serializers.ValidationError({"participant_group_ids": f"Invalid group ID: {group_id}"})
                group_data = group_response.json()
                if group_data.get('tenant_unique_id') != tenant_id:
                    raise serializers.ValidationError({"participant_group_ids": f"Group {group_id} does not belong to tenant {tenant_id}"})
            except Exception as e:
                logger.error(f"Error validating group {group_id}: {str(e)}")
                raise serializers.ValidationError({"participant_group_ids": f"Error validating group ID: {group_id}"})

        if data['start_time'] > data['end_time']:
            raise serializers.ValidationError("End time must be after start time")
        return data

    def create(self, validated_data):
        request = self.context.get('request')
        tenant_id = get_tenant_id_from_jwt(request)
        validated_data['tenant_id'] = tenant_id
        validated_data['creator_id'] = request.jwt_payload.get('user', {}).get('id')
        participant_user_ids = validated_data.pop('participant_user_ids', [])
        participant_group_ids = validated_data.pop('participant_group_ids', [])
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

        schedule = Schedule.objects.create(**validated_data)
        for user_id in participant_user_ids:
            ScheduleParticipant.objects.create(schedule=schedule, user_id=user_id)
        for group_id in participant_group_ids:
            ScheduleParticipant.objects.create(schedule=schedule, group_id=group_id)
        return schedule

    def update(self, instance, validated_data):
        tenant_id = get_tenant_id_from_jwt(self.context.get('request'))
        validated_data['tenant_id'] = tenant_id
        validated_data['creator_id'] = self.context['request'].jwt_payload.get('user', {}).get('id')
        participant_user_ids = validated_data.pop('participant_user_ids', None)
        participant_group_ids = validated_data.pop('participant_group_ids', None)
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
        if participant_user_ids is not None:
            current_users = set(instance.participants.filter(user_id__isnull=False).values_list('user_id', flat=True))
            new_users = set(participant_user_ids)
            instance.participants.filter(user_id__in=current_users - new_users).delete()
            for user_id in new_users - current_users:
                ScheduleParticipant.objects.create(schedule=instance, user_id=user_id)
        if participant_group_ids is not None:
            current_groups = set(instance.participants.filter(group_id__isnull=False).values_list('group_id', flat=True))
            new_groups = set(participant_group_ids)
            instance.participants.filter(group_id__in=current_groups - new_groups).delete()
            for group_id in new_groups - current_groups:
                ScheduleParticipant.objects.create(schedule=instance, group_id=group_id)
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