import jwt
from rest_framework.exceptions import ValidationError

# talent_engine/serializers.py
import logging
import requests
from django.conf import settings
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
import uuid
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


# talent_engine/serializers.py
class JobRequisitionSerializer(serializers.ModelSerializer):
    advert_banner_url = serializers.SerializerMethodField()

    tenant_id = serializers.CharField(max_length=36, read_only=True)
    branch_id = serializers.CharField(max_length=36, allow_null=True, required=False)
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
    # compliance_checklist = serializers.SerializerMethodField()
    # compliance_checklist = ComplianceItemSerializer(many=True, required=False)
    branch_name = serializers.SerializerMethodField()

    class Meta:
        model = JobRequisition
        fields = [
            'id', 'requisition_number', 'num_of_applications', 'job_requisition_code', 'job_application_code', 'tenant_id', 'tenant_domain',
            'branch_id', 'branch_name', 'department_id', 'title', 'unique_link', 'status', 'role', 'requested_by',
            'requested_by_id', 'created_by', 'created_by_id', 'updated_by', 'updated_by_id', 'approved_by',
            'approved_by_id', 'company_name', 'company_address', 'job_type', 'position_type', 'location_type',
            'job_location', 'interview_location', 'salary_range', 'salary_range_min', 'salary_range_max',
            'job_description', 'requirements', 'qualification_requirement', 'experience_requirement',
            'knowledge_requirement', 'number_of_candidates', 'urgency_level', 'reason', 'comment', 'deadline_date',
            'start_date', 'responsibilities', 'documents_required', 'compliance_checklist', 'last_compliance_check',
            'checked_by', 'advert_banner', 'advert_banner_url', 'requested_date', 'publish_status', 'is_deleted', 'created_at', 'updated_at',
            'approval_workflow', 'current_approval_stage', 'approval_date', 'time_to_fill_days'
        ]
        read_only_fields = [
            'id', 'requisition_number', 'job_requisition_code', 'job_application_code', 'tenant_id', 'tenant_domain',
            'requested_by_id', 'created_by_id', 'updated_by_id', 'approved_by_id', 'requested_date', 'is_deleted',
            'created_at', 'updated_at', 'branch_name', 'last_compliance_check', 'checked_by'
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
            'email': {'type': 'string'},
            'first_name': {'type': 'string'},
            'last_name': {'type': 'string'},
            'job_role': {'type': 'string'}
        }
    })
    def get_requested_by(self, obj):
        if obj.requested_by_id:
            try:
                user_response = requests.get(
                    f'{settings.AUTH_SERVICE_URL}/api/user/users/{obj.requested_by_id}/',
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
                logger.error(f"Failed to fetch user {obj.requested_by_id} from auth_service")
            except Exception as e:
                logger.error(f"Error fetching requested_by {obj.requested_by_id}: {str(e)}")
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
    def get_created_by(self, obj):
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
                logger.error(f"Error fetching created_by {obj.created_by_id}: {str(e)}")
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
    def get_updated_by(self, obj):
        if obj.updated_by_id:
            try:
                user_response = requests.get(
                    f'{settings.AUTH_SERVICE_URL}/api/user/users/{obj.updated_by_id}/',
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
                logger.error(f"Failed to fetch user {obj.updated_by_id} from auth_service")
            except Exception as e:
                logger.error(f"Error fetching updated_by {obj.updated_by_id}: {str(e)}")
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
    def get_approved_by(self, obj):
        if obj.approved_by_id:
            try:
                user_response = requests.get(
                    f'{settings.AUTH_SERVICE_URL}/api/user/users/{obj.approved_by_id}/',
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
                logger.error(f"Failed to fetch user {obj.approved_by_id} from auth_service")
            except Exception as e:
                logger.error(f"Error fetching approved_by {obj.approved_by_id}: {str(e)}")
        return None

    @extend_schema_field(str)
    def get_tenant_domain(self, obj):
        try:
            tenant_id = get_tenant_id_from_jwt(self.context['request'])
            tenant_response = requests.get(
                f'{settings.AUTH_SERVICE_URL}/api/tenant/tenants/{tenant_id}/',
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


    @extend_schema_field(str)
    def get_branch_name(self, obj):
        if obj.branch_id:
            try:
                branch_response = requests.get(
                    f'{settings.AUTH_SERVICE_URL}/api/tenant/branches/{obj.branch_id}/',
                    headers={'Authorization': f'Bearer {self.context["request"].META.get("HTTP_AUTHORIZATION", "").split(" ")[1]}'}
                )
                if branch_response.status_code == 200:
                    return branch_response.json().get('name', '')
                logger.error(f"Failed to fetch branch {obj.branch_id} from auth_service")
            except Exception as e:
                logger.error(f"Error fetching branch name for {obj.branch_id}: {str(e)}")
        return None



    def validate(self, data):
        tenant_id = get_tenant_id_from_jwt(self.context['request'])

    

        if data.get('tenant_unique_id', tenant_id) != tenant_id:
            raise serializers.ValidationError({"tenant_unique_id": "Tenant ID mismatch."})
        
        # data['tenant_unique_id'] = tenant_id  # ✅ Inject it into validated data

        # Validate branch_id
        if data.get('branch_id'):
            branch_response = requests.get(
                f'{settings.AUTH_SERVICE_URL}/api/tenant/branches/{data["branch_id"]}/',
                headers={'Authorization': f'Bearer {self.context["request"].META.get("HTTP_AUTHORIZATION", "").split(" ")[1]}'}
            )
            if branch_response.status_code != 200:
                raise serializers.ValidationError({"branch_id": "Invalid branch ID."})
            branch_data = branch_response.json()
            if branch_data['tenant_unique_id'] != tenant_id:
                raise serializers.ValidationError({"branch_id": "Branch does not belong to this tenant."})

        # Validate department_id
        if data.get('department_id'):
            dept_response = requests.get(
                f'{settings.AUTH_SERVICE_URL}/api/departments/{data["department_id"]}/',
                headers={'Authorization': f'Bearer {self.context["request"].META.get("HTTP_AUTHORIZATION", "").split(" ")[1]}'}
            )
            if dept_response.status_code != 200:
                raise serializers.ValidationError({"department_id": "Invalid department ID."})
            dept_data = dept_response.json()
            if dept_data['tenant_unique_id'] != tenant_id:
                raise serializers.ValidationError({"department_id": "Department does not belong to this tenant."})

        # logger.info(f"THIS IS THE {data} WE GOT")
        return data




    # def validate_compliance_checklist(self, value):
    #     if not isinstance(value, list):
    #         raise serializers.ValidationError("Compliance checklist must be a list.")
    #     for item in value:
    #         if not isinstance(item, dict) or not item.get("name"):
    #             raise serializers.ValidationError("Each compliance item must be a dictionary with a 'name' field.")
    #         serializer = ComplianceItemSerializer(data=item, context=self.context)
    #         serializer.is_valid(raise_exception=True)
    #     return value

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
        tenant_id = get_tenant_id_from_jwt(self.context['request'])
        validated_data['tenant_id'] = tenant_id  # <- inject here instead of validate()
        logger.info(f"THIS IS THE validated_data recieved in the created method {validated_data} WE GOT")
        # Map 'branch' to 'branch_id' if present
        if 'branch' in validated_data:
            validated_data['branch_id'] = validated_data.pop('branch')
        # Ensure tenant_id is always a string
        if 'tenant_id' in validated_data:
            validated_data['tenant_id'] = str(validated_data['tenant_id'])

        # Fetch tenant name from auth_service
        request = self.context.get('request')
        tenant_name = None
        if request and 'tenant_id' in validated_data:
            try:
                tenant_response = requests.get(
                    f"{settings.AUTH_SERVICE_URL}/api/tenant/tenants/{validated_data['tenant_id']}/",
                    headers={'Authorization': request.META.get("HTTP_AUTHORIZATION", "")}
                )
                if tenant_response.status_code == 200:
                    tenant_data = tenant_response.json()
                    tenant_name = tenant_data.get('name')
            except Exception as e:
                logger.error(f"Error fetching tenant name for {validated_data['tenant_id']}: {str(e)}")
        if tenant_name:
            validated_data['tenant_name'] = tenant_name

        # compliance_checklist = validated_data.pop('compliance_checklist', [])
        advert_banner_file = validated_data.pop('advert_banner', None)
        instance = super().create(validated_data)
        # for item in compliance_checklist:
        #     instance.add_compliance_item(
        #         name=item["name"],
        #         description=item.get("description", ""),
        #         required=item.get("required", True)
        #     )
        # Handle advert_banner upload after instance is created (so instance.id exists)
        self._handle_advert_banner_upload(instance, advert_banner_file)
        return instance

    def update(self, instance, validated_data):
        request = self.context.get('request')
        # logger.info(f"JobRequisition update request data: {getattr(request, 'data', {})}")
        # logger.info(f"advert_banner in request.FILES: {getattr(request, 'FILES', {}).get('advert_banner')}")
        # logger.info(f"advert_banner in validated_data: {validated_data.get('advert_banner')}")

        if 'branch' in validated_data:
            validated_data['branch_id'] = validated_data.pop('branch')
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
        
        jwt_payload = self.context.get('request').jwt_payload if self.context.get('request') else {}
        tenant_id = jwt_payload.get('tenant_unique_id')
        user_id = jwt_payload.get('user', {}).get('id')
        role = jwt_payload.get('role')
        branch = jwt_payload.get('user', {}).get('branch')

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
                'branch_id': branch if role == 'recruiter' and branch else None
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
            'branch_id': {'type': 'string', 'nullable': True}
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
    requested_by = serializers.SerializerMethodField()
    approved_by = serializers.SerializerMethodField()
    branch_name = serializers.SerializerMethodField()

    class Meta:
        model = Request
        fields = [
            'id', 'tenant_id', 'branch_id', 'branch_name', 'requested_by', 'requested_by_id',
            'approved_by', 'approved_by_id', 'request_type', 'title', 'description', 'status',
            'details', 'comment', 'created_at', 'updated_at', 'is_deleted'
        ]
        read_only_fields = [
            'id', 'tenant_id', 'requested_by_id', 'approved_by_id', 'created_at',
            'updated_at', 'is_deleted', 'branch_name'
        ]



    def get_requested_by(self, obj):
        if not obj.requested_by_id:
            logger.warning(f"No requested_by_id for request {obj.id}")
            return None

        try:
            jwt_payload = getattr(self.context['request'], 'jwt_payload', {})
            current_user_id = jwt_payload.get('user', {}).get('id')
            
            if str(current_user_id) == str(obj.requested_by_id):
                user_data = jwt_payload.get('user', {})
                logger.info(f"Using JWT payload for requested_by {obj.requested_by_id}")
                return {
                    'email': user_data.get('email', ''),
                    'first_name': user_data.get('first_name', ''),
                    'last_name': user_data.get('last_name', ''),
                    'job_role': user_data.get('job_role', '')
                }
            
            # Fallback to database if user is not the current user
            from .models import CustomUser  # Adjust import as needed
            try:
                user = CustomUser.objects.get(id=obj.requested_by_id, tenant_id=jwt_payload.get('tenant_unique_id'))
                logger.info(f"Using database for requested_by {obj.requested_by_id}")
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
        """Get approved by user details from stored data"""
        if obj.approved_by_id and obj.approved_by_details:
            return {
                'email': obj.approved_by_details.get('email', ''),
                'first_name': obj.approved_by_details.get('first_name', ''),
                'last_name': obj.approved_by_details.get('last_name', '')
            }
        return None

    def get_branch_name(self, obj):
        """Get branch name from auth service"""
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
        """Validate tenant and branch"""
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
        
        return data

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
            'approval_workflow', 'current_approval_stage', 'approval_date', 'time_to_fill_days'
        ]
        read_only_fields = [
            'id', 'requisition_number', 'job_requisition_code', 'job_application_code',
             'is_deleted', 
        ]
