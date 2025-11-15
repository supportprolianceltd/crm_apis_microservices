import jwt
from rest_framework.exceptions import ValidationError

# talent_engine/serializers.py
import logging
import requests
from django.conf import settings
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
import uuid
from django.utils.text import slugify
from .models import JobRequisition, VideoSession, Participant, Request

logger = logging.getLogger('talent_engine')


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



def get_user_data_from_jwt(request):
    """Extract user data from JWT payload."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise serializers.ValidationError("No valid Bearer token provided.")
    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        user_data = payload.get("user", {})
        return {
            'email': user_data.get('email', ''),
            'first_name': user_data.get('first_name', ''),
            'last_name': user_data.get('last_name', ''),
            'job_role': user_data.get('job_role', ''),
            'id': user_data.get('id', None)
        }
    except Exception as e:
        logger.error(f"Failed to decode JWT for user data: {str(e)}")
        raise serializers.ValidationError("Invalid JWT token for user data.")


def get_user_data_from_request(request):
    """Extract user data from request.jwt_payload set by middleware."""
    jwt_payload = getattr(request, 'jwt_payload', {})
    
    # ✅ User data is at TOP LEVEL of JWT, not nested
    return {
        'id': jwt_payload.get('id'),
        'email': jwt_payload.get('email', ''),
        'first_name': jwt_payload.get('first_name', ''),
        'last_name': jwt_payload.get('last_name', ''),
        'job_role': jwt_payload.get('role', '')  # Using 'role' as job_role
    }

    
class ComplianceItemSerializer(serializers.Serializer):
    id = serializers.UUIDField(required=False, default=uuid.uuid4)
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(max_length=1000, allow_blank=True, default='')
    required = serializers.BooleanField(default=True)
    status = serializers.ChoiceField(choices=['pending', 'completed', 'failed'], default='pending')
    checked_by_id = serializers.CharField(max_length=36, allow_null=True, required=False)
    checked_at = serializers.DateTimeField(allow_null=True, default=None)

    def validate(self, data):
        if data.get('status') in ['completed', 'failed'] and not data.get('checked_by_id'):
            raise serializers.ValidationError("checked_by_id is required when status is completed or failed.")
        if data.get('checked_by_id') and not data.get('checked_at'):
            raise serializers.ValidationError("checked_at is required when checked_by_id is provided.")
        # Validate checked_by_id if provided
        if data.get('checked_by_id'):
            request = self.context['request']
            tenant_id = get_tenant_id_from_jwt(request)
            user_response = requests.get(
                f'{settings.AUTH_SERVICE_URL}/api/user/users/{data["checked_by_id"]}/',
                headers={'Authorization': request.META.get("HTTP_AUTHORIZATION", "")}
            )
            if user_response.status_code != 200:
                raise serializers.ValidationError({"checked_by_id": "Invalid user ID."})
            user_data = user_response.json()
            if user_data.get('tenant_id') != tenant_id:
                raise serializers.ValidationError({"checked_by_id": "User does not belong to this tenant."})
        return data




class JobRequisitionSerializer(serializers.ModelSerializer):
    advert_banner_url = serializers.SerializerMethodField()

    tenant_id = serializers.CharField(max_length=36, read_only=True)
    department_id = serializers.CharField(max_length=36, allow_null=True, required=False)
    requested_by_id = serializers.CharField(max_length=36, read_only=True)
    created_by_id = serializers.CharField(max_length=36, read_only=True)
    updated_by_id = serializers.CharField(max_length=36, read_only=True)
    approved_by_id = serializers.CharField(max_length=36, read_only=True)
    requested_by = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()
    updated_by = serializers.SerializerMethodField()
    approved_by = serializers.SerializerMethodField()
    tenant_domain = serializers.SerializerMethodField()

    class Meta:
        model = JobRequisition
        fields = [
            'id', 'requisition_number', 'num_of_applications', 'job_requisition_code', 'job_application_code', 'tenant_id', 'tenant_domain',
            'department_id', 'title', 'unique_link', 'status', 'role', 'requested_by',
            'requested_by_id', 'created_by', 'created_by_id', 'updated_by', 'updated_by_id', 'approved_by',
            'approved_by_id', 'company_name', 'company_address', 'job_type', 'position_type', 'location_type',
            'job_location', 'interview_location', 'salary_range', 'salary_range_min', 'salary_range_max',
            'job_description', 'requirements', 'qualification_requirement', 'experience_requirement',
            'knowledge_requirement', 'number_of_candidates', 'urgency_level', 'reason', 'comment', 'deadline_date',
            'start_date', 'responsibilities', 'documents_required', 'compliance_checklist', 'last_compliance_check',
            'checked_by', 'advert_banner', 'advert_banner_url', 'requested_date', 'publish_status', 'is_deleted', 'created_at', 'updated_at',
            'approval_workflow', 'current_approval_stage', 'approval_date', 'time_to_fill_days',
            # New fields added
            'requested_by_details', 'created_by_details', 'updated_by_details', 'approved_by_details'
        ]
        read_only_fields = [
            'id', 'requisition_number', 'job_requisition_code', 'job_application_code', 'tenant_id', 'tenant_domain',
            'requested_date', 'is_deleted',
            'created_at', 'updated_at', 'last_compliance_check', 'checked_by',
            'tenant_domain'
        ]

    def get_advert_banner_url(self, obj):
        storage_type = getattr(settings, 'STORAGE_TYPE', 'local').lower()
        if storage_type == 'local':
            if obj.advert_banner:
                return obj.advert_banner.url
            return None
        else:
            # For remote storage, use the public URL field
            return obj.advert_banner_url

    @extend_schema_field({
        'type': 'object',
        'properties': {
            'id': {'type': 'string'},
            'email': {'type': 'string'},
            'first_name': {'type': 'string'},
            'last_name': {'type': 'string'},
            'job_role': {'type': 'string'}
        }
    })
    def get_requested_by(self, obj):
        # Updated: Return stored data—no HTTP call
        return obj.requested_by_details

    @extend_schema_field({
        'type': 'object',
        'properties': {
            'id': {'type': 'string'},
            'email': {'type': 'string'},
            'first_name': {'type': 'string'},
            'last_name': {'type': 'string'},
            'job_role': {'type': 'string'}
        }
    })
    def get_created_by(self, obj):
        # Updated: Return stored data—no HTTP call
        return obj.created_by_details

    @extend_schema_field({
        'type': 'object',
        'properties': {
            'id': {'type': 'string'},
            'email': {'type': 'string'},
            'first_name': {'type': 'string'},
            'last_name': {'type': 'string'},
            'job_role': {'type': 'string'}
        }
    })
    def get_updated_by(self, obj):
        # Updated: Return stored data—no HTTP call
        return obj.updated_by_details

    @extend_schema_field({
        'type': 'object',
        'properties': {
            'id': {'type': 'string'},
            'email': {'type': 'string'},
            'first_name': {'type': 'string'},
            'last_name': {'type': 'string'},
            'job_role': {'type': 'string'}
        }
    })
    def get_approved_by(self, obj):
        # Updated: Return stored data—no HTTP call
        return obj.approved_by_details

    @extend_schema_field(str)
    def get_tenant_domain(self, obj):
        # Updated: Return stored data—no HTTP call
        return obj.tenant_domain

    def validate(self, data):
        tenant_id = get_tenant_id_from_jwt(self.context['request'])

        if data.get('tenant_unique_id', tenant_id) != tenant_id:
            raise serializers.ValidationError({"tenant_unique_id": "Tenant ID mismatch."})
        
        # data['tenant_unique_id'] = tenant_id  # ✅ Inject it into validated data

      

        # logger.info(f"THIS IS THE {data} WE GOT")
        return data

    def validate_requirements(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Requirements must be a list.")
        return value

    def validate_responsibilities(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Responsibilities must be a list.")
        return value

    def validate_compliance_checklist(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("compliance_checklist must be a list.")
        return value

    def validate_documents_required(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Documents required must be a list.")
        return value

    def validate_approval_workflow(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Approval workflow must be a dictionary.")
        return value

    def create(self, validated_data):
        request = self.context['request']
        jwt_payload = getattr(request, 'jwt_payload', {})

        tenant_id = jwt_payload.get('tenant_unique_id')
        tenant_schema = jwt_payload.get('tenant_schema', 'TENANT').upper()[:3]  # e.g., 'PRO'

        if not tenant_id:
            raise serializers.ValidationError("Missing tenant_unique_id in token.")

        validated_data['tenant_id'] = tenant_id  # Inject tenant_id

        # Set user-related fields
        user_data = get_user_data_from_request(request)
        if user_data.get('id'):
            validated_data['requested_by_id'] = str(user_data['id'])
            validated_data['created_by_id'] = str(user_data['id'])
            validated_data['requested_by_details'] = user_data
            validated_data['created_by_details'] = user_data
            validated_data['updated_by_details'] = user_data

        validated_data['tenant_domain'] = jwt_payload.get('tenant_domain')
        validated_data['tenant_schema'] = jwt_payload.get('tenant_schema')

        # Get the latest requisition for this tenant to generate a sequential number
        latest_requisition = JobRequisition.objects.filter(
            tenant_id=tenant_id,
            id__startswith=tenant_schema
        ).order_by('-created_at').first()

        # Determine the next number
        if latest_requisition:
            try:
                last_number = int(latest_requisition.id.split('-')[-1])
            except (IndexError, ValueError):
                last_number = 0
        else:
            last_number = 0

        next_number = str(last_number + 1).zfill(4)  # e.g., 0001

        # Generate codes
        requisition_id = f"{tenant_schema}-{next_number}"
        job_requisition_code = f"{tenant_schema}-JR-{next_number}"
        job_application_code = f"{tenant_schema}-JA-{next_number}"

        # Build unique_link with correct prefix
        title_slug = slugify(validated_data.get('title', ''))
        unique_suffix = uuid.uuid4().hex[:8]
        unique_link = f"{tenant_id}-{tenant_schema}-{title_slug}-{unique_suffix}"

        # Assign all generated fields
        validated_data['id'] = requisition_id
        validated_data['job_requisition_code'] = job_requisition_code
        validated_data['job_application_code'] = job_application_code
        validated_data['unique_link'] = unique_link

        # Handle advert_banner
        advert_banner_file = validated_data.pop('advert_banner', None)

        # Save the instance
        instance = super().create(validated_data)

        # Handle file upload if needed
        self._handle_advert_banner_upload(instance, advert_banner_file)

        return instance
    
    def update(self, instance, validated_data):
        request = self.context.get('request')
     
        if request:
            user_data = get_user_data_from_request(request)
            if user_data.get('id'):
                validated_data['updated_by_id'] = str(user_data['id'])
                validated_data['updated_by_details'] = user_data

                # Handle approved_by if status is approved
                if 'status' in validated_data and validated_data['status'] == 'approved':
                    validated_data['approved_by_id'] = str(user_data['id'])
                    validated_data['approved_by_details'] = user_data

        if 'tenant_id' in validated_data:
            validated_data['tenant_id'] = str(validated_data['tenant_id'])

        # compliance_checklist = validated_data.pop('compliance_checklist', None)
        advert_banner_file = validated_data.pop('advert_banner', None)
        instance = super().update(instance, validated_data)

        # if compliance_checklist is not None:
        #     # Directly assign the validated list
        #     instance.compliance_checklist = compliance_checklist
        #     instance.save(update_fields=['compliance_checklist'])

        self._handle_advert_banner_upload(instance, advert_banner_file)
        return instance
    
    def _handle_advert_banner_upload(self, instance, advert_banner_file):
        if advert_banner_file:
            from utils.storage import get_storage_service
            import uuid
            ext = advert_banner_file.name.split('.')[-1]
            file_name = f"advert_banners/{instance.tenant_id}/{instance.id}_{uuid.uuid4()}.{ext}"
            content_type = getattr(advert_banner_file, 'content_type', 'application/octet-stream')
            storage_type = getattr(settings, 'STORAGE_TYPE', 'local').lower()
            if storage_type == 'local':
                instance.advert_banner.save(file_name, advert_banner_file, save=True)
            else:
                storage = get_storage_service(storage_type)
                upload_success = storage.upload_file(advert_banner_file, file_name, content_type)
                if not upload_success:
                    raise serializers.ValidationError({"advert_banner": "Failed to upload advert banner."})
                public_url = storage.get_public_url(file_name)
                instance.advert_banner_url = public_url  # <-- Save to advert_banner_url
                instance.advert_banner = None            # <-- Clear advert_banner field
                instance.save(update_fields=["advert_banner_url", "advert_banner"])






class JobRequisitionBulkCreateSerializer(serializers.Serializer):
    """
    Bulk create serializer for NEW job requisitions only
    """
    # Only include fields that should be set by the user for NEW creations
    title = serializers.CharField(max_length=255)
    job_type = serializers.ChoiceField(choices=JobRequisition.JOB_TYPE_CHOICES, default='full_time')
    position_type = serializers.ChoiceField(choices=JobRequisition.POSITION_TYPE_CHOICES, default='permanent')
    location_type = serializers.ChoiceField(choices=JobRequisition.LOCATION_TYPE_CHOICES, default='on_site')
    job_description = serializers.CharField(allow_blank=True, required=False, default='')
    requirements = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    number_of_candidates = serializers.IntegerField(allow_null=True, required=False)
    urgency_level = serializers.ChoiceField(choices=JobRequisition.URGENCY_LEVEL_CHOICES, default='medium')
    
    # Add other fields that you want to allow in bulk creation
    company_name = serializers.CharField(max_length=255, allow_blank=True, required=False, default='')
    company_address = serializers.CharField(allow_blank=True, required=False, default='')
    job_location = serializers.CharField(allow_blank=True, required=False, default='')
    salary_range = serializers.CharField(max_length=255, allow_blank=True, required=False, default='')
    qualification_requirement = serializers.CharField(allow_blank=True, required=False, default='')
    experience_requirement = serializers.CharField(allow_blank=True, required=False, default='')
    knowledge_requirement = serializers.CharField(allow_blank=True, required=False, default='')
    reason = serializers.CharField(allow_blank=True, required=False, default='')
    comment = serializers.CharField(allow_blank=True, required=False, default='')
    deadline_date = serializers.DateField(allow_null=True, required=False)
    start_date = serializers.DateField(allow_null=True, required=False)
    responsibilities = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    documents_required = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    compliance_checklist = serializers.ListField(child=serializers.DictField(), required=False, default=list)

    # Status field for new requisitions (default to 'draft' or 'pending')
    status = serializers.ChoiceField(choices=JobRequisition.STATUS_CHOICES, default='draft')
    role = serializers.ChoiceField(choices=JobRequisition.ROLE_CHOICES, default='staff')

    def create(self, validated_data_list):
        """
        Handle bulk creation of NEW job requisitions only
        """
        # When many=True, validated_data is a list of dictionaries
        if not isinstance(validated_data_list, list):
            validated_data_list = [validated_data_list]
        
        request = self.context.get('request')
        jwt_payload = getattr(request, 'jwt_payload', {}) if request else {}
        tenant_id = jwt_payload.get('tenant_unique_id')
        user_data = get_user_data_from_request(request) if request else {}
        user_id = user_data.get('id')
        role = jwt_payload.get('role')
        # branch = jwt_payload.get('user', {}).get('branch')

        if not tenant_id or not user_id:
            raise serializers.ValidationError("Missing tenant_unique_id or user_id in token.")

        requisitions = []

        for item_data in validated_data_list:
            # Remove any fields that should be auto-generated
            # Don't include id, unique_link, created_at, updated_at, etc.
            requisition_data = {
                'title': item_data.get('title'),
                'job_type': item_data.get('job_type', 'full_time'),
                'position_type': item_data.get('position_type', 'permanent'),
                'location_type': item_data.get('location_type', 'on_site'),
                'job_description': item_data.get('job_description', ''),
                'requirements': item_data.get('requirements', []),
                'number_of_candidates': item_data.get('number_of_candidates'),
                'urgency_level': item_data.get('urgency_level', 'medium'),
                'company_name': item_data.get('company_name', ''),
                'company_address': item_data.get('company_address', ''),
                'job_location': item_data.get('job_location', ''),
                'salary_range': item_data.get('salary_range', ''),
                'qualification_requirement': item_data.get('qualification_requirement', ''),
                'experience_requirement': item_data.get('experience_requirement', ''),
                'knowledge_requirement': item_data.get('knowledge_requirement', ''),
                'reason': item_data.get('reason', ''),
                'comment': item_data.get('comment', ''),
                'deadline_date': item_data.get('deadline_date'),
                'start_date': item_data.get('start_date'),
                'responsibilities': item_data.get('responsibilities', []),
                'documents_required': item_data.get('documents_required', []),
                'compliance_checklist': item_data.get('compliance_checklist', []),
                'status': item_data.get('status', 'draft'),
                'role': item_data.get('role', 'staff'),
                'tenant_id': tenant_id,
                'requested_by_id': user_id,
                'requested_by_details': user_data,
                'created_by_details': user_data,
                'updated_by_details': user_data
            }
            
            # Create the requisition instance (ID will be auto-generated in save())
            requisition = JobRequisition(**requisition_data)
            requisitions.append(requisition)

        # Save each requisition individually to trigger the save() method
        # This ensures IDs, unique_links, and codes are generated properly
        created_requisitions = []
        for requisition in requisitions:
            try:
                requisition.save()  # This will generate the ID and other auto fields
                created_requisitions.append(requisition)
            except Exception as e:
                logger.error(f"Failed to create requisition {requisition.title}: {str(e)}")
                # Continue with other requisitions even if one fails

        if not created_requisitions:
            raise serializers.ValidationError("Failed to create any requisitions")

        return created_requisitions





class ParticipantSerializer(serializers.ModelSerializer):
    user_id = serializers.CharField(max_length=36, read_only=True)
    candidate_email = serializers.EmailField(read_only=True)
    username = serializers.SerializerMethodField()
    first_name = serializers.SerializerMethodField()
    last_name = serializers.SerializerMethodField()

    class Meta:
        model = Participant
        fields = [
            'id', 'session', 'user_id', 'username', 'first_name', 'last_name',
            'candidate_email', 'is_muted', 'is_camera_on', 'joined_at', 'left_at'
        ]
        read_only_fields = ['id', 'user_id', 'username', 'first_name', 'last_name', 'candidate_email', 'joined_at', 'left_at']

    @extend_schema_field(str)
    def get_username(self, obj):
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
                logger.error(f"Error fetching username for {obj.user_id}: {str(e)}")
        return obj.candidate_email or ''

    @extend_schema_field(str)
    def get_first_name(self, obj):
        if obj.user_id:
            try:
                user_response = requests.get(
                    f'{settings.AUTH_SERVICE_URL}/api/user/users/{obj.user_id}/',
                    headers={'Authorization': f'Bearer {self.context["request"].META.get("HTTP_AUTHORIZATION", "").split(" ")[1]}'}
                )
                if user_response.status_code == 200:
                    return user_response.json().get('first_name', '')
                logger.error(f"Failed to fetch user {obj.user_id} from auth_service")
            except Exception as e:
                logger.error(f"Error fetching first_name for {obj.user_id}: {str(e)}")
        return ''

    @extend_schema_field(str)
    def get_last_name(self, obj):
        if obj.user_id:
            try:
                user_response = requests.get(
                    f'{settings.AUTH_SERVICE_URL}/api/user/users/{obj.user_id}/',
                    headers={'Authorization': f'Bearer {self.context["request"].META.get("HTTP_AUTHORIZATION", "").split(" ")[1]}'}
                )
                if user_response.status_code == 200:
                    return user_response.json().get('last_name', '')
                logger.error(f"Failed to fetch user {obj.user_id} from auth_service")
            except Exception as e:
                logger.error(f"Error fetching last_name for {obj.user_id}: {str(e)}")
        return ''

    def validate(self, data):
        tenant_id = self.context['request'].tenant_id
        session = data.get('session')
        if session and session.tenant_id != tenant_id:
            raise serializers.ValidationError({"session": "Session does not belong to this tenant."})
        return data




class VideoSessionSerializer(serializers.ModelSerializer):
    job_application_id = serializers.CharField(max_length=20)
    tenant_id = serializers.CharField(max_length=36, read_only=True)
    participants = ParticipantSerializer(many=True, read_only=True)
    job_application_details = serializers.SerializerMethodField()

    class Meta:
        model = VideoSession
        fields = [
            'id', 'job_application_id', 'job_application_details', 'tenant_id', 'created_at', 'ended_at',
            'is_active', 'recording_url', 'meeting_id', 'scores', 'notes', 'tags', 'participants'
        ]
        read_only_fields = ['id', 'tenant_id', 'created_at', 'ended_at', 'is_active', 'recording_url', 'meeting_id', 'participants']

    @extend_schema_field({
        'type': 'object',
        'properties': {
            'id': {'type': 'string'},
            'email': {'type': 'string'},
            'tenant_id': {'type': 'string'},
          
        }
    })
    def get_job_application_details(self, obj):
        try:
            job_app_response = requests.get(
                f'{settings.JOB_APPLICATIONS_URL}/api/applications/{obj.job_application_id}/',
                headers={'Authorization': f'Bearer {self.context["request"].META.get("HTTP_AUTHORIZATION", "").split(" ")[1]}'}
            )
            if job_app_response.status_code == 200:
                return job_app_response.json()
            logger.error(f"Failed to fetch job application {obj.job_application_id} from job_applications")
        except Exception as e:
            logger.error(f"Error fetching job application details for {obj.job_application_id}: {str(e)}")
        return None

    def validate_job_application_id(self, value):
        tenant_id = self.context['request'].tenant_id
        job_app_response = requests.get(
            f'{settings.JOB_APPLICATIONS_URL}/api/applications/{value}/',
            headers={'Authorization': f'Bearer {self.context["request"].META.get("HTTP_AUTHORIZATION", "").split(" ")[1]}'}
        )
        if job_app_response.status_code != 200:
            raise serializers.ValidationError("Invalid job application ID.")
        job_app_data = job_app_response.json()
        if job_app_data['tenant_id'] != tenant_id:
            raise serializers.ValidationError("Job application does not belong to this tenant.")
        return value

    def validate_scores(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Scores must be a dictionary.")
        required_keys = ['technical', 'communication', 'problemSolving']
        for key in required_keys:
            if key not in value or not isinstance(value[key], int) or not (0 <= value[key] <= 5):
                raise serializers.ValidationError(f"Scores must include {key} with a value between 0 and 5.")
        return value

    def validate_tags(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Tags must be a list of strings.")
        return value

    def validate(self, data):
        tenant_id = self.context['request'].tenant_id
        if data.get('tenant_id', tenant_id) != tenant_id:
            raise serializers.ValidationError({"tenant_id": "Tenant ID mismatch."})
        return data



               
class RequestSerializer(serializers.ModelSerializer):
    tenant_id = serializers.CharField(max_length=36, read_only=True)
    branch_id = serializers.CharField(max_length=36, allow_null=True, required=False)
    requested_by_id = serializers.CharField(max_length=36, read_only=True)
    approved_by_id = serializers.CharField(max_length=36, read_only=True)
    cancelled_by_id = serializers.CharField(max_length=36, read_only=True)
    rejected_by_id = serializers.CharField(max_length=36, read_only=True)
    requested_by = serializers.SerializerMethodField()
    approved_by = serializers.SerializerMethodField()
    cancelled_by = serializers.SerializerMethodField()
    rejected_by = serializers.SerializerMethodField()
    branch_name = serializers.SerializerMethodField()
    
    # File fields for dynamic handling
    supporting_document = serializers.FileField(write_only=True, required=False, allow_null=True)
    supporting_document_url = serializers.CharField(read_only=True)
    additional_attachment = serializers.FileField(write_only=True, required=False, allow_null=True)
    additional_attachment_url = serializers.CharField(read_only=True)

    class Meta:
        model = Request
        fields = [
            'id', 'tenant_id', 'branch_id', 'branch_name', 'requested_by', 'requested_by_id',
            'approved_by', 'approved_by_id', 'cancelled_by', 'cancelled_by_id',
            'rejected_by', 'rejected_by_id', 'request_type', 'title', 'description', 'status',
            'comment', 'created_at', 'updated_at', 'is_deleted',
            
            # File attachments
            'supporting_document', 'supporting_document_url',
            'additional_attachment', 'additional_attachment_url',
            
            # Material Request Fields
            'item_name', 'material_type', 'request_id', 'item_specification',
            'quantity_needed', 'priority', 'reason_for_request', 'needed_date',
            
            # Leave Request Fields
            'leave_category', 'number_of_days', 'start_date', 'resumption_date',
            'region_of_stay', 'address_during_leave', 'contact_phone_number',
            'additional_information',
            
            # Service Request Fields
            'service_type', 'service_description', 'priority_level',
            'desired_completion_date', 'requester_name', 'requester_department',
            'requester_contact_info', 'special_instructions'
        ]
        read_only_fields = [
            'id', 'tenant_id', 'requested_by_id', 'approved_by_id', 'cancelled_by_id',
            'rejected_by_id', 'requested_by_details', 'approved_by_details', 'cancelled_by_details',
            'rejected_by_details', 'created_at', 'updated_at', 'is_deleted', 'branch_name',
            'request_id', 'supporting_document_url', 'additional_attachment_url'
        ]

    def get_requested_by(self, obj):
        # Prefer stored details if available
        if obj.requested_by_details:
            return {
                'email': obj.requested_by_details.get('email', ''),
                'first_name': obj.requested_by_details.get('first_name', ''),
                'last_name': obj.requested_by_details.get('last_name', ''),
                'job_role': obj.requested_by_details.get('job_role', '')
            }

        if not obj.requested_by_id:
            return None

        try:
            jwt_payload = getattr(self.context['request'], 'jwt_payload', {})
            current_user_id = jwt_payload.get('user', {}).get('id')
            
            if str(current_user_id) == str(obj.requested_by_id):
                user_data = jwt_payload.get('user', {})
                return {
                    'email': user_data.get('email', ''),
                    'first_name': user_data.get('first_name', ''),
                    'last_name': user_data.get('last_name', ''),
                    'job_role': user_data.get('job_role', '')
                }
            
            # Fallback to database if user is not the current user
            from .models import CustomUser
            try:
                user = CustomUser.objects.get(id=obj.requested_by_id, tenant_id=jwt_payload.get('tenant_unique_id'))
                return {
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'job_role': user.job_role
                }
            except CustomUser.DoesNotExist:
                logger.warning(f"User {obj.requested_by_id} not found in database")
                return None
        except Exception as e:
            logger.error(f"Error fetching requested_by {obj.requested_by_id}: {str(e)}")
            return None

    def get_approved_by(self, obj):
        if obj.approved_by_id and obj.approved_by_details:
            return {
                'email': obj.approved_by_details.get('email', ''),
                'first_name': obj.approved_by_details.get('first_name', ''),
                'last_name': obj.approved_by_details.get('last_name', ''),
                'job_role': obj.approved_by_details.get('job_role', '')
            }
        return None

    def get_cancelled_by(self, obj):
        if obj.cancelled_by_id and obj.cancelled_by_details:
            return {
                'email': obj.cancelled_by_details.get('email', ''),
                'first_name': obj.cancelled_by_details.get('first_name', ''),
                'last_name': obj.cancelled_by_details.get('last_name', ''),
                'job_role': obj.cancelled_by_details.get('job_role', '')
            }
        return None

    def get_rejected_by(self, obj):
        if obj.rejected_by_id and obj.rejected_by_details:
            return {
                'email': obj.rejected_by_details.get('email', ''),
                'first_name': obj.rejected_by_details.get('first_name', ''),
                'last_name': obj.rejected_by_details.get('last_name', ''),
                'job_role': obj.rejected_by_details.get('job_role', '')
            }
        return None

    def get_branch_name(self, obj):
        if obj.branch_id:
            try:
                auth_header = self.context['request'].META.get('HTTP_AUTHORIZATION', '')
                if auth_header:
                    branch_response = requests.get(
                        f'{settings.AUTH_SERVICE_URL}/api/tenant/branches/{obj.branch_id}/',
                        headers={'Authorization': auth_header},
                        timeout=5
                    )
                    if branch_response.status_code == 200:
                        return branch_response.json().get('name', '')
            except Exception as e:
                logger.error(f"Error fetching branch name for {obj.branch_id}: {str(e)}")
        return None

    def validate(self, data):
        jwt_payload = getattr(self.context['request'], 'jwt_payload', {})
        tenant_id = jwt_payload.get('tenant_unique_id')
        
        if not tenant_id:
            raise serializers.ValidationError({"tenant_id": "Tenant ID not found in request."})
        
        # Validate branch if provided
        if data.get('branch_id'):
            try:
                auth_header = self.context['request'].META.get('HTTP_AUTHORIZATION', '')
                if auth_header:
                    branch_response = requests.get(
                        f'{settings.AUTH_SERVICE_URL}/api/tenant/branches/{data["branch_id"]}/',
                        headers={'Authorization': auth_header},
                        timeout=5
                    )
                    if branch_response.status_code != 200:
                        raise serializers.ValidationError({"branch_id": "Invalid branch ID."})
                    
                    branch_data = branch_response.json()
                    if branch_data.get('tenant_id') != tenant_id:
                        raise serializers.ValidationError({"branch_id": "Branch does not belong to this tenant."})
            except requests.RequestException:
                raise serializers.ValidationError({"branch_id": "Unable to validate branch."})
        
        # Request type specific validations
        request_type = data.get('request_type')
        
        if request_type == 'material':
            if not data.get('item_name'):
                raise serializers.ValidationError({"item_name": "Item name is required for material requests."})
            if not data.get('quantity_needed') or data['quantity_needed'] <= 0:
                raise serializers.ValidationError({"quantity_needed": "Valid quantity is required for material requests."})
        
        elif request_type == 'leave':
            if not data.get('start_date'):
                raise serializers.ValidationError({"start_date": "Start date is required for leave requests."})
            if not data.get('resumption_date'):
                raise serializers.ValidationError({"resumption_date": "Resumption date is required for leave requests."})
            if data.get('start_date') and data.get('resumption_date'):
                if data['start_date'] >= data['resumption_date']:
                    raise serializers.ValidationError({"resumption_date": "Resumption date must be after start date."})
        
        elif request_type == 'service':
            if not data.get('service_description'):
                raise serializers.ValidationError({"service_description": "Description is required for service requests."})
        
        return data

    def create(self, validated_data):
        jwt_payload = getattr(self.context['request'], 'jwt_payload', {})
        
        # Handle file uploads
        supporting_document = validated_data.pop('supporting_document', None)
        additional_attachment = validated_data.pop('additional_attachment', None)
        
        # Create request instance - DON'T pass tenant_id and requested_by_id again
        # They are already in validated_data from the view
        instance = Request.objects.create(**validated_data)
        
        # Handle file uploads after instance creation
        self._handle_file_upload(instance, 'supporting_document', supporting_document)
        self._handle_file_upload(instance, 'additional_attachment', additional_attachment)
        
        logger.info(f"Request created: {instance.title} for tenant {instance.tenant_id} by user {instance.requested_by_id}")
        return instance

    def update(self, instance, validated_data):
        # Handle file uploads for update
        supporting_document = validated_data.pop('supporting_document', None)
        additional_attachment = validated_data.pop('additional_attachment', None)
        
        # Update instance
        instance = super().update(instance, validated_data)
        
        # Handle file uploads
        if supporting_document is not None:
            self._handle_file_upload(instance, 'supporting_document', supporting_document)
        if additional_attachment is not None:
            self._handle_file_upload(instance, 'additional_attachment', additional_attachment)
        
        return instance

    def _handle_file_upload(self, instance, field_name, file):
        """Handle dynamic file upload similar to JobRequisition"""
        if file:
            from utils.storage import get_storage_service
            import uuid
            
            ext = file.name.split('.')[-1]
            file_name = f"request_{field_name}/{instance.tenant_id}/{instance.id}_{uuid.uuid4()}.{ext}"
            content_type = getattr(file, 'content_type', 'application/octet-stream')
            storage_type = getattr(settings, 'STORAGE_TYPE', 'local').lower()
            
            if storage_type == 'local':
                getattr(instance, field_name).save(file_name, file, save=True)
            else:
                storage = get_storage_service(storage_type)
                upload_success = storage.upload_file(file, file_name, content_type)
                if not upload_success:
                    raise serializers.ValidationError({field_name: f"Failed to upload {field_name}."})
                
                public_url = storage.get_public_url(file_name)
                url_field = f"{field_name}_url"
                setattr(instance, url_field, public_url)
                
                # Clear the FileField for remote storage
                setattr(instance, field_name, None)
                instance.save(update_fields=[field_name, url_field])

    def perform_create(self, serializer):
        jwt_payload = getattr(self.request, 'jwt_payload', {})
        tenant_id = jwt_payload.get('tenant_unique_id')
        
        # ✅ Get user_id from top level (not nested)
        user_id = jwt_payload.get('id')
        role = jwt_payload.get('role')
        
        if not user_id:
            logger.error(f"User ID not found in JWT payload: {jwt_payload}")
            raise serializers.ValidationError("User ID not found in token")
        
        # ✅ Build user details from top-level JWT fields
        requested_by_details = {
            'id': user_id,
            'email': jwt_payload.get('email', ''),
            'first_name': jwt_payload.get('first_name', ''),
            'last_name': jwt_payload.get('last_name', ''),
            'job_role': jwt_payload.get('role', '')
        }
        
        serializer.save(
            tenant_id=tenant_id,
            requested_by_id=user_id,
            requested_by_details=requested_by_details
        )



# talent_engine/serializers.py
class PublicJobRequisitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobRequisition
        fields = [
            'id', 'requisition_number', 'tenant_id', 'job_requisition_code', 'job_application_code',
            'title', 'unique_link', 'status', 'job_type', 'position_type', 'location_type',
            'job_description', 'requirements', 'qualification_requirement', 'experience_requirement',
            'knowledge_requirement', 'urgency_level', 'reason', 'deadline_date', 'num_of_applications',
            'start_date', 'responsibilities',  'advert_banner', 'publish_status','compliance_checklist',
            'approval_workflow', 'current_approval_stage', 'approval_date', 'time_to_fill_days', 'number_of_candidates'
        ]
        read_only_fields = [
            'id', 'requisition_number', 'job_requisition_code', 'job_application_code',
             'is_deleted', 
        ]
