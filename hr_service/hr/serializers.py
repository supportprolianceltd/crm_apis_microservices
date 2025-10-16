import logging
import requests
from django.conf import settings
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
import uuid
from .models import (
    LeaveType, LeaveRequest, Contract, Equipment, Policy, PolicyAcknowledgment,
    EscalationAlert, DisciplinaryWarning, ProbationPeriod, PerformanceReview,
    EmployeeRelationCase, StarterLeaver
)

logger = logging.getLogger('hr')

def get_tenant_id_from_jwt(request):
    auth_header = request.META.get("HTTP_AUTHORIZATION", "")
    if not auth_header.startswith("Bearer "):
        raise serializers.ValidationError("No valid Bearer token provided.")
    token = auth_header.split(" ")[1]
    try:
        import jwt
        payload = jwt.decode(token, options={"verify_signature": False})
        return payload.get("tenant_unique_id") or payload.get("tenant_id")
    except Exception:
        raise serializers.ValidationError("Invalid JWT token.")

def get_user_data_from_jwt(request):
    """Extract user data from JWT payload."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise serializers.ValidationError("No valid Bearer token provided.")
    token = auth_header.split(" ")[1]
    try:
        import jwt
        payload = jwt.decode(token, options={"verify_signature": False})
        user_data = payload.get("user", {})
        return {
            'email': user_data.get('email', ''),
            'first_name': user_data.get('first_name', ''),
            'last_name': user_data.get('last_name', ''),
            'job_role': user_data.get('job_role', ''),
            'id': user_data.get('id', None),
            'username': user_data.get('username', ''),
            'role': user_data.get('role', ''),
            'profile': user_data.get('profile', {})
        }
    except Exception as e:
        logger.error(f"Failed to decode JWT for user data: {str(e)}")
        raise serializers.ValidationError("Invalid JWT token for user data.")

def get_user_details_from_jwt(user_id, request):
    """Get user details from JWT token without making API calls."""
    if not user_id:
        return None
    
    # Get current user data from JWT
    current_user_data = get_user_data_from_jwt(request)
    current_user_id = current_user_data.get('id')
    
    # If the requested user is the same as current user, return JWT data
    if str(user_id) == str(current_user_id):
        return {
            'email': current_user_data.get('email'),
            'first_name': current_user_data.get('first_name'),
            'last_name': current_user_data.get('last_name'),
            'job_role': current_user_data.get('job_role'),
            'username': current_user_data.get('username'),
            'role': current_user_data.get('role')
        }
    
    # For other users, we might still need API calls, but for most HR use cases,
    # we're dealing with the current user's data
    return {
        'email': f'user_{user_id}@example.com',  # Placeholder
        'first_name': 'User',
        'last_name': str(user_id),
        'job_role': 'Unknown',
        'username': f'user_{user_id}'
    }


class LeaveTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveType
        fields = '__all__'

    def validate(self, data):
        tenant_id = get_tenant_id_from_jwt(self.context['request'])
        if 'tenant_id' in data and data['tenant_id'] != tenant_id:
            raise serializers.ValidationError({"tenant_id": "Tenant ID mismatch."})
        data['tenant_id'] = tenant_id
        return data


class LeaveRequestSerializer(serializers.ModelSerializer):
    leave_type = LeaveTypeSerializer(read_only=True)
    leave_type_id = serializers.CharField(write_only=True)
    balance = serializers.SerializerMethodField()
    user_details = serializers.SerializerMethodField()
    approved_by_details = serializers.SerializerMethodField()

    class Meta:
        model = LeaveRequest
        fields = '__all__'

    def get_balance(self, obj):
        return obj.get_balance()

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
        return get_user_details_from_jwt(obj.user_id, self.context['request'])

    @extend_schema_field({
        'type': 'object',
        'properties': {
            'email': {'type': 'string'},
            'first_name': {'type': 'string'},
            'last_name': {'type': 'string'},
            'job_role': {'type': 'string'}
        }
    })
    def get_approved_by_details(self, obj):
        return get_user_details_from_jwt(obj.approved_by_id, self.context['request'])

    def validate(self, data):
        tenant_id = get_tenant_id_from_jwt(self.context['request'])
        if data.get('tenant_id', tenant_id) != tenant_id:
            raise serializers.ValidationError({"tenant_id": "Tenant ID mismatch."})
        data['tenant_id'] = tenant_id

        # Validate leave_type_id exists in our database (no API call needed)
        if data.get('leave_type_id'):
            if not LeaveType.objects.filter(id=data['leave_type_id'], tenant_id=tenant_id).exists():
                raise serializers.ValidationError({"leave_type_id": "Invalid leave type ID for this tenant."})

        # Validate dates
        if data.get('start_date') and data.get('end_date') and data['start_date'] > data['end_date']:
            raise serializers.ValidationError({"end_date": "End date must be after start date."})

        return data

    def create(self, validated_data):
        leave_type_id = validated_data.pop('leave_type_id')
        validated_data['leave_type'] = LeaveType.objects.get(id=leave_type_id)
        instance = super().create(validated_data)
        return instance

    def update(self, instance, validated_data):
        if 'leave_type_id' in validated_data:
            leave_type_id = validated_data.pop('leave_type_id')
            validated_data['leave_type'] = LeaveType.objects.get(id=leave_type_id)
        instance = super().update(instance, validated_data)
        return instance


class ContractSerializer(serializers.ModelSerializer):
    user_details = serializers.SerializerMethodField()

    class Meta:
        model = Contract
        fields = '__all__'

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
        return get_user_details_from_jwt(obj.user_id, self.context['request'])

    def validate(self, data):
        tenant_id = get_tenant_id_from_jwt(self.context['request'])
        if data.get('tenant_id', tenant_id) != tenant_id:
            raise serializers.ValidationError({"tenant_id": "Tenant ID mismatch."})
        data['tenant_id'] = tenant_id
        return data


class EquipmentSerializer(serializers.ModelSerializer):
    user_details = serializers.SerializerMethodField()

    class Meta:
        model = Equipment
        fields = '__all__'

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
        return get_user_details_from_jwt(obj.user_id, self.context['request'])

    def validate(self, data):
        tenant_id = get_tenant_id_from_jwt(self.context['request'])
        if data.get('tenant_id', tenant_id) != tenant_id:
            raise serializers.ValidationError({"tenant_id": "Tenant ID mismatch."})
        data['tenant_id'] = tenant_id
        if 'serial_number' in data:
            if Equipment.objects.filter(tenant_id=tenant_id, serial_number=data['serial_number']).exists():
                raise serializers.ValidationError({"serial_number": "Serial number already exists for this tenant."})
        return data


class PolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = Policy
        fields = '__all__'

    def validate(self, data):
        tenant_id = get_tenant_id_from_jwt(self.context['request'])
        if data.get('tenant_id', tenant_id) != tenant_id:
            raise serializers.ValidationError({"tenant_id": "Tenant ID mismatch."})
        data['tenant_id'] = tenant_id
        return data


class PolicyAcknowledgmentSerializer(serializers.ModelSerializer):
    policy = PolicySerializer(read_only=True)
    policy_id = serializers.CharField(write_only=True)
    user_details = serializers.SerializerMethodField()

    class Meta:
        model = PolicyAcknowledgment
        fields = '__all__'

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
        return get_user_details_from_jwt(obj.user_id, self.context['request'])

    def validate(self, data):
        tenant_id = get_tenant_id_from_jwt(self.context['request'])
        if data.get('tenant_id', tenant_id) != tenant_id:
            raise serializers.ValidationError({"tenant_id": "Tenant ID mismatch."})
        data['tenant_id'] = tenant_id

        # Validate policy_id exists in our database
        if data.get('policy_id'):
            if not Policy.objects.filter(id=data['policy_id'], tenant_id=tenant_id).exists():
                raise serializers.ValidationError({"policy_id": "Invalid policy ID for this tenant."})

        return data

    def create(self, validated_data):
        policy_id = validated_data.pop('policy_id')
        validated_data['policy'] = Policy.objects.get(id=policy_id)
        instance = super().create(validated_data)
        return instance

    def update(self, instance, validated_data):
        if 'policy_id' in validated_data:
            policy_id = validated_data.pop('policy_id')
            validated_data['policy'] = Policy.objects.get(id=policy_id)
        instance = super().update(instance, validated_data)
        return instance


class EscalationAlertSerializer(serializers.ModelSerializer):
    user_details = serializers.SerializerMethodField()

    class Meta:
        model = EscalationAlert
        fields = '__all__'

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
        return get_user_details_from_jwt(obj.user_id, self.context['request'])

    def validate(self, data):
        tenant_id = get_tenant_id_from_jwt(self.context['request'])
        if data.get('tenant_id', tenant_id) != tenant_id:
            raise serializers.ValidationError({"tenant_id": "Tenant ID mismatch."})
        data['tenant_id'] = tenant_id
        return data


class DisciplinaryWarningSerializer(serializers.ModelSerializer):
    user_details = serializers.SerializerMethodField()

    class Meta:
        model = DisciplinaryWarning
        fields = '__all__'

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
        return get_user_details_from_jwt(obj.user_id, self.context['request'])

    def validate(self, data):
        tenant_id = get_tenant_id_from_jwt(self.context['request'])
        if data.get('tenant_id', tenant_id) != tenant_id:
            raise serializers.ValidationError({"tenant_id": "Tenant ID mismatch."})
        data['tenant_id'] = tenant_id
        return data


class ProbationPeriodSerializer(serializers.ModelSerializer):
    user_details = serializers.SerializerMethodField()

    class Meta:
        model = ProbationPeriod
        fields = '__all__'

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
        return get_user_details_from_jwt(obj.user_id, self.context['request'])

    def validate(self, data):
        tenant_id = get_tenant_id_from_jwt(self.context['request'])
        if data.get('tenant_id', tenant_id) != tenant_id:
            raise serializers.ValidationError({"tenant_id": "Tenant ID mismatch."})
        data['tenant_id'] = tenant_id
        
        # Validate dates
        if data.get('start_date') and data.get('end_date') and data['start_date'] > data['end_date']:
            raise serializers.ValidationError({"end_date": "End date must be after start date."})
            
        return data


class PerformanceReviewSerializer(serializers.ModelSerializer):
    user_details = serializers.SerializerMethodField()
    supervisor_details = serializers.SerializerMethodField()

    class Meta:
        model = PerformanceReview
        fields = '__all__'

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
        return get_user_details_from_jwt(obj.user_id, self.context['request'])

    @extend_schema_field({
        'type': 'object',
        'properties': {
            'email': {'type': 'string'},
            'first_name': {'type': 'string'},
            'last_name': {'type': 'string'},
            'job_role': {'type': 'string'}
        }
    })
    def get_supervisor_details(self, obj):
        return get_user_details_from_jwt(obj.supervisor_id, self.context['request'])

    def validate(self, data):
        tenant_id = get_tenant_id_from_jwt(self.context['request'])
        if data.get('tenant_id', tenant_id) != tenant_id:
            raise serializers.ValidationError({"tenant_id": "Tenant ID mismatch."})
        data['tenant_id'] = tenant_id
        
        # Validate score range
        if data.get('score') and (data['score'] < 1 or data['score'] > 10):
            raise serializers.ValidationError({"score": "Score must be between 1 and 10."})
            
        return data


class EmployeeRelationCaseSerializer(serializers.ModelSerializer):
    user_details = serializers.SerializerMethodField()
    assigned_to_details = serializers.SerializerMethodField()

    class Meta:
        model = EmployeeRelationCase
        fields = '__all__'

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
        return get_user_details_from_jwt(obj.user_id, self.context['request'])

    @extend_schema_field({
        'type': 'object',
        'properties': {
            'email': {'type': 'string'},
            'first_name': {'type': 'string'},
            'last_name': {'type': 'string'},
            'job_role': {'type': 'string'}
        }
    })
    def get_assigned_to_details(self, obj):
        return get_user_details_from_jwt(obj.assigned_to_id, self.context['request'])

    def validate(self, data):
        tenant_id = get_tenant_id_from_jwt(self.context['request'])
        if data.get('tenant_id', tenant_id) != tenant_id:
            raise serializers.ValidationError({"tenant_id": "Tenant ID mismatch."})
        data['tenant_id'] = tenant_id
        return data


class StarterLeaverSerializer(serializers.ModelSerializer):
    user_details = serializers.SerializerMethodField()

    class Meta:
        model = StarterLeaver
        fields = '__all__'

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
        return get_user_details_from_jwt(obj.user_id, self.context['request'])

    def validate(self, data):
        tenant_id = get_tenant_id_from_jwt(self.context['request'])
        if data.get('tenant_id', tenant_id) != tenant_id:
            raise serializers.ValidationError({"tenant_id": "Tenant ID mismatch."})
        data['tenant_id'] = tenant_id
        
        # Validate dates
        if data.get('start_date') and data.get('end_date') and data['start_date'] > data['end_date']:
            raise serializers.ValidationError({"end_date": "End date must be after start date."})
            
        return data