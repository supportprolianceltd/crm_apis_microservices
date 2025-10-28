# hr/rewards_penalties/serializers.py
from datetime import timezone
import jwt
import logging
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.text import slugify
import uuid
from rest_framework import generics, status
from rest_framework.response import Response
from django.conf import settings
from .models import Reward, Penalty, validate_details_json, Status, RewardType, PenaltyType

logger = logging.getLogger('hr_rewards_penalties')

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

def get_user_data_from_jwt(request):
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise serializers.ValidationError("No valid Bearer token provided.")
    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        user_data = payload.get("user", {})
        return {
            'id': user_data.get('id', ''),
            'email': user_data.get('email', ''),
            'first_name': user_data.get('first_name', ''),
            'last_name': user_data.get('last_name', ''),
            'job_role': user_data.get('job_role', ''),
            'department': user_data.get('department', '')
        }
    except Exception as e:
        logger.error(f"Failed to decode JWT for user data: {str(e)}")
        raise serializers.ValidationError("Invalid JWT token for user data.")

class BaseRewardsPenaltySerializer(serializers.ModelSerializer):
    tenant_id = serializers.UUIDField(read_only=True)
    tenant_domain = serializers.CharField(read_only=True)
    employee_details = serializers.JSONField(validators=[validate_details_json])
    created_by_details = serializers.JSONField(read_only=True, validators=[validate_details_json])
    updated_by_details = serializers.JSONField(read_only=True, validators=[validate_details_json])
    approver_details = serializers.JSONField(read_only=True, validators=[validate_details_json])
    checked_by_details = serializers.JSONField(read_only=True, validators=[validate_details_json])
    evidence_file_url = serializers.SerializerMethodField()

    class Meta:
        fields = [
            'id', 'code', 'tenant_id', 'tenant_domain', 'employee_details',
            'date_issued', 'effective_date', 'reason', 'description', 'status',
            'approver_id', 'approver_details', 'created_by_id', 'created_by_details',
            'updated_by_id', 'updated_by_details', 'is_deleted', 'created_at', 'updated_at',
            'compliance_checklist', 'last_compliance_check', 'checked_by_id', 'checked_by_details',
            'approval_workflow', 'current_approval_stage', 'approval_date', 'evidence_file',
            'evidence_file_url', 'notes', 'is_public', 'impact_assessment', 'custom_fields',
            'issuing_authority'
        ]
        read_only_fields = [
            'id', 'code', 'tenant_id', 'tenant_domain', 'created_by_id', 'created_by_details',
            'updated_by_id', 'updated_by_details', 'approver_id', 'approver_details',
            'checked_by_id', 'checked_by_details', 'is_deleted', 'created_at', 'updated_at',
            'last_compliance_check', 'approval_date', 'evidence_file_url'
        ]

    def get_evidence_file_url(self, obj):
        storage_type = getattr(settings, 'STORAGE_TYPE', 'local').lower()
        if storage_type == 'local':
            if obj.evidence_file:
                return obj.evidence_file.url
            return None
        else:
            return obj.evidence_file_url

    @extend_schema_field({
        'type': 'object',
        'properties': {
            'id': {'type': 'string'}, 'email': {'type': 'string'}, 'first_name': {'type': 'string'},
            'last_name': {'type': 'string'}, 'job_role': {'type': 'string'}, 'department': {'type': 'string'}
        }
    })
    def get_employee_details(self, obj):
        return obj.employee_details

    def validate(self, data):
        tenant_id = get_tenant_id_from_jwt(self.context['request'])
        if data.get('tenant_id', tenant_id) != tenant_id:
            raise serializers.ValidationError({"tenant_id": "Tenant ID mismatch."})
        return data

    def validate_compliance_checklist(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Compliance checklist must be a list.")
        return value

    def validate_approval_workflow(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Approval workflow must be a dictionary.")
        return value

    def validate_impact_assessment(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Impact assessment must be a dictionary.")
        return value

    def validate_custom_fields(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Custom fields must be a dictionary.")
        return value

    def _handle_evidence_upload(self, instance, evidence_file):
        if evidence_file:
            from utils.storage import get_storage_service
            import uuid
            ext = evidence_file.name.split('.')[-1]
            file_name = f"evidence/{instance.tenant_id}/{instance.id}_{uuid.uuid4()}.{ext}"
            content_type = getattr(evidence_file, 'content_type', 'application/octet-stream')
            storage_type = getattr(settings, 'STORAGE_TYPE', 'local').lower()
            if storage_type == 'local':
                instance.evidence_file.save(file_name, evidence_file, save=True)
            else:
                storage = get_storage_service(storage_type)
                upload_success = storage.upload_file(evidence_file, file_name, content_type)
                if not upload_success:
                    raise serializers.ValidationError({"evidence_file": "Failed to upload evidence file."})
                public_url = storage.get_public_url(file_name)
                instance.evidence_file_url = public_url
                instance.evidence_file = None
                instance.save(update_fields=["evidence_file_url", "evidence_file"])

class RewardSerializer(BaseRewardsPenaltySerializer):
    type = serializers.ChoiceField(choices=[(tag.value, tag.name) for tag in RewardType])
    value_type = serializers.ChoiceField(choices=[('monetary', 'Monetary'), ('points', 'Points')])

    class Meta(BaseRewardsPenaltySerializer.Meta):
        model = Reward
        fields = BaseRewardsPenaltySerializer.Meta.fields + [
            'type', 'value', 'value_type', 'duration_days', 'announcement_channel',
            'follow_up_required', 'follow_up_date'
        ]

    def create(self, validated_data):
        request = self.context['request']
        jwt_payload = getattr(request, 'jwt_payload', {})
        tenant_id = jwt_payload.get('tenant_unique_id')
        tenant_schema = jwt_payload.get('tenant_schema', 'HR').upper()[:3]
        if not tenant_id:
            raise serializers.ValidationError("Missing tenant_unique_id in token.")

        validated_data['tenant_id'] = tenant_id
        instance = Reward(**validated_data)
        instance.generate_code(tenant_schema)
        
        # Add this block to set created_by fields from JWT
        user_data = get_user_data_from_jwt(request)
        instance.created_by_id = user_data['id']  # Will be str(e.g., '1'); handle UUID conversion if needed (see notes below)
        instance.created_by_details = user_data
        
        # Optionally set tenant_domain if needed (it's null in the failing row but allowed)
        instance.tenant_domain = jwt_payload.get('tenant_domain', '')
        
        evidence_file = validated_data.pop('evidence_file', None)
        instance.save()
        self._handle_evidence_upload(instance, evidence_file)
        return instance

    # def create(self, validated_data):
    #     request = self.context['request']
    #     jwt_payload = getattr(request, 'jwt_payload', {})
    #     tenant_id = jwt_payload.get('tenant_unique_id')
    #     tenant_schema = jwt_payload.get('tenant_schema', 'HR').upper()[:3]
    #     if not tenant_id:
    #         raise serializers.ValidationError("Missing tenant_unique_id in token.")

    #     validated_data['tenant_id'] = tenant_id
    #     instance = Reward(**validated_data)
    #     instance.generate_code(tenant_schema)
    #     evidence_file = validated_data.pop('evidence_file', None)
    #     instance.save()
    #     self._handle_evidence_upload(instance, evidence_file)
    #     return instance

    def update(self, instance, validated_data):
        evidence_file = validated_data.pop('evidence_file', None)
        instance = super().update(instance, validated_data)
        self._handle_evidence_upload(instance, evidence_file)
        return instance


class PenaltySerializer(BaseRewardsPenaltySerializer):
    type = serializers.ChoiceField(choices=[(tag.value, tag.name) for tag in PenaltyType])
    severity_level = serializers.ChoiceField(choices=[(1, 'Low'), (2, 'Medium'), (3, 'High')])

    class Meta(BaseRewardsPenaltySerializer.Meta):
        model = Penalty
        fields = BaseRewardsPenaltySerializer.Meta.fields + [
            'type', 'severity_level', 'duration_days', 'end_date', 'probation_period_months',
            'corrective_action_plan', 'escalation_history', 'legal_compliance_notes'
        ]

    def create(self, validated_data):
        request = self.context['request']
        jwt_payload = getattr(request, 'jwt_payload', {})
        tenant_id = jwt_payload.get('tenant_unique_id')
        tenant_schema = jwt_payload.get('tenant_schema', 'HR').upper()[:3]
        if not tenant_id:
            raise serializers.ValidationError("Missing tenant_unique_id in token.")

        validated_data['tenant_id'] = tenant_id
        instance = Penalty(**validated_data)  # <-- Fixed: Change 'Reward' to 'Penalty'
        instance.generate_code(tenant_schema)
        
        # Set created_by fields from JWT (as already implemented)
        user_data = get_user_data_from_jwt(request)
        instance.created_by_id = user_data['id']
        instance.created_by_details = user_data
        
        # Set tenant_domain
        instance.tenant_domain = jwt_payload.get('tenant_domain', '')
        
        # Add full_clean for Penalty-specific validation (e.g., suspension duration)
        instance.full_clean()
        
        evidence_file = validated_data.pop('evidence_file', None)
        instance.save()
        self._handle_evidence_upload(instance, evidence_file)
        return instance

    def update(self, instance, validated_data):
        evidence_file = validated_data.pop('evidence_file', None)
        instance = super().update(instance, validated_data)
        instance.full_clean()  # Re-validate on update
        self._handle_evidence_upload(instance, evidence_file)
        return instance