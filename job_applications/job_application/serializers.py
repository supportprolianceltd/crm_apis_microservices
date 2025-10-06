import pytz
import uuid
import os
import mimetypes
from django.utils import timezone
from django.core.validators import URLValidator
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .models import JobApplication, Schedule
import logging
import requests
from utils.supabase import upload_file_dynamic
from django.db import IntegrityError
import pytz
import logging
import requests
from django.utils import timezone
from django.core.validators import URLValidator
from rest_framework import serializers
from .models import JobApplication, Schedule
import uuid
import jwt

logger = logging.getLogger('job_applications')



def get_tenant_id_from_jwt(request):
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise serializers.ValidationError("No valid Bearer token provided.")
    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        return payload.get("tenant_unique_id")
    except Exception as e:
        logger.error(f"Invalid JWT token: {str(e)}")
        raise serializers.ValidationError("Invalid JWT token.")


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
    


# class DocumentSerializer(serializers.Serializer):
#     document_type = serializers.CharField(max_length=50)
#     file = serializers.FileField(write_only=True)
#     file_url = serializers.SerializerMethodField(read_only=True)
#     uploaded_at = serializers.DateTimeField(read_only=True, default=timezone.now)

#     def get_file_url(self, obj):
#         return obj.get('file_url', None)

#     def validate_file(self, value):
#         allowed_types = [
#             'application/pdf',
#             'application/msword',
#             'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
#         ]
#         if value.content_type not in allowed_types:
#             raise serializers.ValidationError(
#                 f"Invalid file type: {value.content_type}. Only PDF and Word (.doc, .docx) files are allowed."
#             )
#         max_size = 50 * 1024 * 1024
#         if value.size > max_size:
#             raise serializers.ValidationError(f"File size exceeds 50 MB limit.")
#         return value

#     def validate_document_type(self, value):
#         job_requisition = self.context.get('job_requisition')
#         if not job_requisition:
#             raise serializers.ValidationError("Job requisition context is missing.")
#         # FIX: Use .get() for dict
#         documents_required = job_requisition.get('documents_required', [])
#         if not value:
#             raise serializers.ValidationError("Document type is required.")
#         try:
#             uuid.UUID(value)
#             return value
#         except ValueError:
#             pass
#         if value.lower() in ['resume', 'curriculum vitae (cv)']:
#             return value
#         if documents_required and value not in documents_required:
#             raise serializers.ValidationError(
#                 f"Invalid document type: {value}. Must be one of {documents_required} or 'Curriculum Vitae (CV)'.",
#             )
#         return value


class DocumentSerializer(serializers.Serializer):
    document_type = serializers.CharField()
    file = serializers.FileField(required=False, allow_null=True)
    file_url = serializers.CharField(required=False, allow_blank=True)
    uploaded_at = serializers.CharField(required=False, allow_blank=True, allow_null=True)  # Changed to CharField
    original_name = serializers.CharField(required=False, allow_blank=True)
    compression = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate(self, data):
        if not data.get('file') and not data.get('file_url'):
            raise serializers.ValidationError({"file": "Either a file or file_url must be provided."})
        if data.get('file_url'):
            validate_url = URLValidator()
            try:
                validate_url(data['file_url'])
            except serializers.ValidationError:
                raise serializers.ValidationError({"file_url": "Invalid URL format."})
        # Ensure uploaded_at is a string
        if data.get('uploaded_at'):
            if isinstance(data['uploaded_at'], str):
                try:
                    # Validate ISO format
                    from datetime import datetime
                    datetime.fromisoformat(data['uploaded_at'].replace('Z', '+00:00'))
                except ValueError:
                    raise serializers.ValidationError({"uploaded_at": "Invalid ISO datetime format."})
            else:
                # Convert datetime to ISO string
                data['uploaded_at'] = data['uploaded_at'].isoformat()
        return data

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['document_type'] = instance.get('document_type', '')
        data['file_url'] = instance.get('file_url', '')
        data['uploaded_at'] = instance.get('uploaded_at', '') if instance.get('uploaded_at') else ''
        data['original_name'] = instance.get('original_name', '')
        data['compression'] = instance.get('compression', None)
        return data

class ComplianceDocumentSerializer(serializers.Serializer):
    file_url = serializers.CharField(allow_blank=True, required=False, allow_null=True)
    uploaded_at = serializers.DateTimeField(allow_null=True, required=False)


# class ComplianceStatusSerializer(serializers.Serializer):
#     id = serializers.CharField()
#     name = serializers.CharField()
#     description = serializers.CharField(allow_blank=True)
#     required = serializers.BooleanField(default=False)
#     status = serializers.CharField(default='pending')
#     checked_by = serializers.CharField(allow_null=True)
#     checked_at = serializers.DateTimeField(allow_null=True)
#     notes = serializers.CharField(allow_blank=True)
#     document = serializers.DictField(allow_null=True)

#     def to_representation(self, instance):
#         # Include all fields from the instance, not just the defined ones
#         data = super().to_representation(instance)
#         for key, value in instance.items():
#             if key not in data:
#                 data[key] = value
#         return data

class ComplianceStatusSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField(allow_blank=True)
    required = serializers.BooleanField(default=False)
    status = serializers.CharField(default='pending')
    checked_by = serializers.CharField(allow_null=True)
    checked_at = serializers.DateTimeField(allow_null=True)
    notes = serializers.CharField(allow_blank=True)
    documents = serializers.ListField(
        child=serializers.DictField(), allow_empty=True, required=False
    )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        for key, value in instance.items():
            if key not in data:
                data[key] = value
        return data


# class PublicJobApplicationSerializer(serializers.ModelSerializer):
#     documents = DocumentSerializer(many=True, required=False)
#     compliance_status = ComplianceStatusSerializer(many=True, required=False)
#     job_requisition_id = serializers.CharField()
#     tenant_id = serializers.CharField(required=False)
#     # first_name = serializers.CharField(required=False, allow_null=True)
#     # last_name = serializers.CharField(required=False, allow_null=True)
#     resume_url = serializers.CharField(read_only=True)
#     cover_letter_url = serializers.CharField(read_only=True)

#     class Meta:
#         model = JobApplication
#         fields = [
#             'id', 'tenant_id', 'job_requisition_id', 'full_name',
#             'email', 'phone', 'date_of_birth', 'resume_url', 'cover_letter_url', 'source',
#             'application_date', 'current_stage', 'status', 'qualification', 'experience',
#             'knowledge_skill', 'cover_letter', 'documents', 'compliance_status',
#             'disposition_reason', 'is_deleted',
#         ]
#         read_only_fields = [
#             'id', 'resume_url', 'cover_letter_url', 'is_deleted', 'applied_at', 'created_at', 'updated_at'
#         ]

#     def validate(self, data):
#         if not data.get('job_requisition_id'):
#             raise serializers.ValidationError({"job_requisition_id": "This field is required."})
#         if not data.get('email'):
#             raise serializers.ValidationError({"email": "This field is required."})
#         # first_name and last_name are now optional and nullable
#         return data

#     def create(self, validated_data):
#         resume_file = self.context['request'].FILES.get('resume')
#         cover_letter_file = self.context['request'].FILES.get('cover_letter')
#         documents_data = validated_data.pop('documents', [])
#         compliance_status = validated_data.pop('compliance_status', [])
#         # Set tenant_id from payload/context if present
#         validated_data['tenant_id'] = validated_data.get('tenant_id', None)

#         # Handle document uploads
#         documents = []
#         for doc_data in documents_data:
#             file = doc_data['file']
#             file_ext = os.path.splitext(file.name)[1]
#             filename = f"{uuid.uuid4()}{file_ext}"
#             folder_path = f"application_documents/{timezone.now().strftime('%Y/%m/%d')}"
#             path = f"{folder_path}/{filename}"
#             content_type = mimetypes.guess_type(file.name)[0] or 'application/octet-stream'
#             public_url = upload_file_dynamic(file, path, content_type)
#             documents.append({
#                 'document_type': doc_data['document_type'],
#                 'file_path': path,
#                 'file_url': public_url,
#                 'uploaded_at': timezone.now().isoformat()
#             })
#         validated_data['documents'] = documents

#         application = JobApplication.objects.create(**validated_data)

#         # Upload resume
#         if resume_file:
#             ext = resume_file.name.split('.')[-1]
#             file_name = f"resumes/{application.tenant_id}/{application.id}_{uuid.uuid4()}.{ext}"
#             content_type = getattr(resume_file, 'content_type', 'application/octet-stream')
#             public_url = upload_file_dynamic(resume_file, file_name, content_type)
#             application.resume_url = public_url

#         # Upload cover letter
#         if cover_letter_file:
#             ext = cover_letter_file.name.split('.')[-1]
#             file_name = f"cover_letters/{application.tenant_id}/{application.id}_{uuid.uuid4()}.{ext}"
#             content_type = getattr(cover_letter_file, 'content_type', 'application/octet-stream')
#             public_url = upload_file_dynamic(cover_letter_file, file_name, content_type)
#             application.cover_letter_url = public_url

#         application.save()
#         return application

#     def update(self, instance, validated_data):
#         resume_file = self.context['request'].FILES.get('resume')
#         cover_letter_file = self.context['request'].FILES.get('cover_letter')
#         documents_data = validated_data.pop('documents', [])
#         compliance_status = validated_data.pop('compliance_status', None)

#         # Handle document uploads
#         if documents_data:
#             existing_documents = instance.documents or []
#             for doc_data in documents_data:
#                 file = doc_data['file']
#                 file_ext = os.path.splitext(file.name)[1]
#                 filename = f"{uuid.uuid4()}{file_ext}"
#                 folder_path = f"application_documents/{timezone.now().strftime('%Y/%m/%d')}"
#                 path = f"{folder_path}/{filename}"
#                 content_type = mimetypes.guess_type(file.name)[0] or 'application/octet-stream'
#                 public_url = upload_file_dynamic(file, path, content_type)
#                 doc_data['file_url'] = public_url
#                 doc_data['uploaded_at'] = timezone.now().isoformat()
#                 existing_documents.append(doc_data)
#             validated_data['documents'] = existing_documents

#         if compliance_status is not None:
#             validated_data['compliance_status'] = compliance_status

#         instance = super().update(instance, validated_data)

#         # Upload resume if provided
#         if resume_file:
#             ext = resume_file.name.split('.')[-1]
#             file_name = f"resumes/{instance.tenant_id}/{instance.id}_{uuid.uuid4()}.{ext}"
#             content_type = getattr(resume_file, 'content_type', 'application/octet-stream')
#             public_url = upload_file_dynamic(resume_file, file_name, content_type)
#             instance.resume_url = public_url

#         # Upload cover letter if provided
#         if cover_letter_file:
#             ext = cover_letter_file.name.split('.')[-1]
#             file_name = f"cover_letters/{instance.tenant_id}/{instance.id}_{uuid.uuid4()}.{ext}"
#             content_type = getattr(cover_letter_file, 'content_type', 'application/octet-stream')
#             public_url = upload_file_dynamic(cover_letter_file, file_name, content_type)
#             instance.cover_letter_url = public_url

#         instance.save()
#         return instance

#     def to_representation(self, instance):
#         data = super().to_representation(instance)
#         if 'compliance_status' in data:
#             data['compliance_status'] = [
#                 {
#                     'id': item.get('id', ''),
#                     'name': item.get('name', ''),
#                     'description': item.get('description', ''),
#                     'required': item.get('required', False),
#                     'status': item.get('status', 'pending'),
#                     'checked_by': item.get('checked_by', None),
#                     'checked_at': item.get('checked_at', None),
#                     'notes': item.get('notes', ''),
#                     'document': item.get('document', {'file_url': '', 'uploaded_at': ''})
#                 } for item in data['compliance_status']
#             ]
#         return data


class PublicJobApplicationSerializer(serializers.ModelSerializer):
    documents = DocumentSerializer(many=True, required=False)
    compliance_status = ComplianceStatusSerializer(many=True, required=False)
    job_requisition_id = serializers.CharField()
    tenant_id = serializers.CharField(required=False)
    resume_url = serializers.CharField(read_only=True)
    cover_letter_url = serializers.CharField(read_only=True)

    class Meta:
        model = JobApplication
        fields = [
            'id', 'tenant_id', 'job_requisition_id', 'full_name',
            'email', 'phone', 'date_of_birth', 'resume_url', 'cover_letter_url', 'source',
            'application_date', 'current_stage', 'status', 'qualification', 'experience',
            'knowledge_skill', 'cover_letter', 'documents', 'compliance_status',
            'disposition_reason', 'is_deleted',
        ]
        read_only_fields = [
            'id', 'resume_url', 'cover_letter_url', 'is_deleted', 'applied_at', 'created_at', 'updated_at'
        ]

    def validate(self, data):
        if not data.get('job_requisition_id'):
            raise serializers.ValidationError({"job_requisition_id": "This field is required."})
        if not data.get('email'):
            raise serializers.ValidationError({"email": "This field is required."})
        return data

    def create(self, validated_data):
        resume_file = self.context['request'].FILES.get('resume')
        cover_letter_file = self.context['request'].FILES.get('cover_letter')
        documents_data = validated_data.pop('documents', [])
        compliance_status = validated_data.pop('compliance_status', [])

        documents = []
        for doc_data in documents_data:
            if doc_data.get('file_url'):
                documents.append({
                    'document_type': doc_data['document_type'],
                    'file_path': doc_data.get('file_path', ''),
                    'file_url': doc_data['file_url'],
                    'uploaded_at': doc_data.get('uploaded_at', timezone.now().isoformat()),
                    'original_name': doc_data.get('original_name', ''),
                    'compression': doc_data.get('compression', None)
                })
            else:
                file = doc_data.get('file')
                if not file:
                    raise serializers.ValidationError({"documents": f"No file or file_url provided for document {doc_data['document_type']}"})
                file_ext = os.path.splitext(file.name)[1]
                filename = f"{uuid.uuid4()}{file_ext}"
                folder_path = f"application_documents/{timezone.now().strftime('%Y/%m/%d')}"
                path = f"{folder_path}/{filename}"
                content_type = mimetypes.guess_type(file.name)[0] or 'application/octet-stream'
                public_url = upload_file_dynamic(file, path, content_type)
                documents.append({
                    'document_type': doc_data['document_type'],
                    'file_path': path,
                    'file_url': public_url,
                    'uploaded_at': timezone.now().isoformat(),  # Ensure string
                    'original_name': file.name,
                    'compression': None
                })
        validated_data['documents'] = documents

        application = JobApplication.objects.create(**validated_data)

        if resume_file:
            ext = resume_file.name.split('.')[-1]
            file_name = f"resumes/{application.tenant_id}/{application.id}_{uuid.uuid4()}.{ext}"
            content_type = getattr(resume_file, 'content_type', 'application/octet-stream')
            public_url = upload_file_dynamic(resume_file, file_name, content_type)
            application.resume_url = public_url

        if cover_letter_file:
            ext = cover_letter_file.name.split('.')[-1]
            file_name = f"cover_letters/{application.tenant_id}/{application.id}_{uuid.uuid4()}.{ext}"
            content_type = getattr(cover_letter_file, 'content_type', 'application/octet-stream')
            public_url = upload_file_dynamic(cover_letter_file, file_name, content_type)
            application.cover_letter_url = public_url

        application.save()
        return application

    def update(self, instance, validated_data):
        resume_file = self.context['request'].FILES.get('resume')
        cover_letter_file = self.context['request'].FILES.get('cover_letter')
        documents_data = validated_data.pop('documents', [])
        compliance_status = validated_data.pop('compliance_status', None)

        if documents_data:
            existing_documents = instance.documents or []
            for doc_data in documents_data:
                if doc_data.get('file_url'):
                    existing_documents.append({
                        'document_type': doc_data['document_type'],
                        'file_path': doc_data.get('file_path', ''),
                        'file_url': doc_data['file_url'],
                        'uploaded_at': doc_data.get('uploaded_at', timezone.now().isoformat()),
                        'original_name': doc_data.get('original_name', ''),
                        'compression': doc_data.get('compression', None)
                    })
                else:
                    file = doc_data.get('file')
                    if not file:
                        raise serializers.ValidationError({"documents": f"No file or file_url provided for document {doc_data['document_type']}"})
                    file_ext = os.path.splitext(file.name)[1]
                    filename = f"{uuid.uuid4()}{file_ext}"
                    folder_path = f"application_documents/{timezone.now().strftime('%Y/%m/%d')}"
                    path = f"{folder_path}/{filename}"
                    content_type = mimetypes.guess_type(file.name)[0] or 'application/octet-stream'
                    public_url = upload_file_dynamic(file, path, content_type)
                    existing_documents.append({
                        'document_type': doc_data['document_type'],
                        'file_path': path,
                        'file_url': public_url,
                        'uploaded_at': timezone.now().isoformat(),  # Ensure string
                        'original_name': file.name,
                        'compression': None
                    })
            validated_data['documents'] = existing_documents

        if compliance_status is not None:
            validated_data['compliance_status'] = compliance_status

        instance = super().update(instance, validated_data)

        if resume_file:
            ext = resume_file.name.split('.')[-1]
            file_name = f"resumes/{instance.tenant_id}/{instance.id}_{uuid.uuid4()}.{ext}"
            content_type = getattr(resume_file, 'content_type', 'application/octet-stream')
            public_url = upload_file_dynamic(resume_file, file_name, content_type)
            instance.resume_url = public_url

        if cover_letter_file:
            ext = cover_letter_file.name.split('.')[-1]
            file_name = f"cover_letters/{instance.tenant_id}/{instance.id}_{uuid.uuid4()}.{ext}"
            content_type = getattr(cover_letter_file, 'content_type', 'application/octet-stream')
            public_url = upload_file_dynamic(cover_letter_file, file_name, content_type)
            instance.cover_letter_url = public_url

        instance.save()
        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if 'compliance_status' in data:
            data['compliance_status'] = [
                {
                    'id': item.get('id', ''),
                    'name': item.get('name', ''),
                    'description': item.get('description', ''),
                    'required': item.get('required', False),
                    'status': item.get('status', 'pending'),
                    'checked_by': item.get('checked_by', None),
                    'checked_at': item.get('checked_at', None),
                    'notes': item.get('notes', ''),
                    'document': item.get('document', {'file_url': '', 'uploaded_at': ''})
                } for item in data['compliance_status']
            ]
        return data



# class JobApplicationSerializer(serializers.ModelSerializer):
#     documents = DocumentSerializer(many=True, required=False)
#     compliance_status = ComplianceStatusSerializer(many=True, required=False)
#     job_requisition_id = serializers.CharField()
#     branch_id = serializers.CharField(allow_null=True, required=False)
#     tenant_id = serializers.CharField(read_only=True)
#     resume_url = serializers.CharField(read_only=True)
#     cover_letter_url = serializers.CharField(read_only=True)
#     hired_by = serializers.JSONField(read_only=True)

#     class Meta:
#         model = JobApplication
#         fields = "__all__"
#         read_only_fields = [
#             'id', 'tenant_id', 'resume_url', 'cover_letter_url', 'is_deleted', 'applied_at', 'created_at', 'updated_at', 'hired_by'
#         ]

#     def validate(self, data):
#         request = self.context['request']
#         tenant_id = get_tenant_id_from_jwt(request)

#         # Validate job_application_id for updates
#         if self.instance is None and 'job_application_id' in data:
#             job_app = JobApplication.objects.filter(id=data['job_application_id']).first()
#             if not job_app:
#                 raise serializers.ValidationError({"job_application_id": "Invalid job application ID."})
#             if str(job_app.tenant_id) != str(tenant_id):
#                 raise serializers.ValidationError({"job_application_id": "Job application does not belong to this tenant."})

#         # Validate branch_id (local database or skip if optional)
#         if data.get('branch_id'):
#             # Assuming a Branch model exists in the local database
#             try:
#                 from .models import Branch  # Adjust import based on your project structure
#                 branch = Branch.objects.filter(id=data['branch_id'], tenant_id=tenant_id).first()
#                 if not branch:
#                     raise serializers.ValidationError({"branch_id": "Invalid branch ID or branch does not belong to this tenant."})
#             except ImportError:
#                 # If no Branch model exists, skip validation or handle differently
#                 logger.warning(f"Branch validation skipped: No Branch model available for branch_id {data['branch_id']}")
#                 # Alternatively, fail validation if branch_id is critical
#                 # raise serializers.ValidationError({"branch_id": "Branch validation not supported without local Branch model."})

#         # Validate status transition
#         if 'status' in data and self.instance:
#             current_status = self.instance.status
#             new_status = data['status']
#             if current_status == 'interviewed' and new_status == 'hired':
#                 # Ensure hired_by will be set in update method
#                 pass
#             elif new_status == 'hired' and current_status != 'interviewed':
#                 raise serializers.ValidationError({"status": "Status can only transition to 'hired' from 'interviewed'."})

#         return data

#     def create(self, validated_data):
#         resume_file = self.context['request'].FILES.get('resume')
#         cover_letter_file = self.context['request'].FILES.get('cover_letter')
#         documents_data = validated_data.pop('documents', [])
#         compliance_status = validated_data.pop('compliance_status', [])
#         validated_data['tenant_id'] = get_tenant_id_from_jwt(self.context['request'])

#         documents = []
#         for doc_data in documents_data:
#             file = doc_data['file']
#             file_ext = os.path.splitext(file.name)[1]
#             filename = f"{uuid.uuid4()}{file_ext}"
#             folder_path = f"application_documents/{timezone.now().strftime('%Y/%m/%d')}"
#             path = f"{folder_path}/{filename}"
#             content_type = mimetypes.guess_type(file.name)[0] or 'application/octet-stream'
#             public_url = upload_file_dynamic(file, path, content_type)
#             documents.append({
#                 'document_type': doc_data['document_type'],
#                 'file_path': path,
#                 'file_url': public_url,
#                 'uploaded_at': timezone.now().isoformat()
#             })
#         validated_data['documents'] = documents

#         application = JobApplication.objects.create(**validated_data)

#         if resume_file:
#             ext = resume_file.name.split('.')[-1]
#             file_name = f"resumes/{application.tenant_id}/{application.id}_{uuid.uuid4()}.{ext}"
#             content_type = getattr(resume_file, 'content_type', 'application/octet-stream')
#             public_url = upload_file_dynamic(resume_file, file_name, content_type)
#             application.resume_url = public_url

#         if cover_letter_file:
#             ext = cover_letter_file.name.split('.')[-1]
#             file_name = f"cover_letters/{application.tenant_id}/{application.id}_{uuid.uuid4()}.{ext}"
#             content_type = getattr(cover_letter_file, 'content_type', 'application/octet-stream')
#             public_url = upload_file_dynamic(cover_letter_file, file_name, content_type)
#             application.cover_letter_url = public_url

#         application.save()
#         return application

#     def update(self, instance, validated_data):
#         resume_file = self.context['request'].FILES.get('resume')
#         cover_letter_file = self.context['request'].FILES.get('cover_letter')
#         documents_data = validated_data.pop('documents', [])
#         compliance_status = validated_data.pop('compliance_status', None)

#         # Check if status is changing to 'hired' from 'interviewed'
#         if 'status' in validated_data and validated_data['status'] == 'hired' and instance.status == 'interviewed':
#             user_data = get_user_data_from_jwt(self.context['request'])
#             if not user_data['id']:
#                 logger.warning("No user.id found in JWT payload for hired_by update")
#                 raise serializers.ValidationError({"detail": "Authentication required for status update to 'hired'."})
            
#             validated_data['hired_by'] = {
#                 'email': user_data['email'],
#                 'first_name': user_data['first_name'],
#                 'last_name': user_data['last_name'],
#                 'job_role': user_data['job_role']
#             }

#         if documents_data:
#             existing_documents = instance.documents or []
#             for doc_data in documents_data:
#                 file = doc_data['file']
#                 file_ext = os.path.splitext(file.name)[1]
#                 filename = f"{uuid.uuid4()}{file_ext}"
#                 folder_path = f"application_documents/{timezone.now().strftime('%Y/%m/%d')}"
#                 path = f"{folder_path}/{filename}"
#                 content_type = mimetypes.guess_type(file.name)[0] or 'application/octet-stream'
#                 public_url = upload_file_dynamic(file, path, content_type)
#                 doc_data['file_url'] = public_url
#                 doc_data['uploaded_at'] = timezone.now().isoformat()
#                 existing_documents.append(doc_data)
#             validated_data['documents'] = existing_documents

#         if compliance_status is not None:
#             validated_data['compliance_status'] = compliance_status

#         instance = super().update(instance, validated_data)

#         if resume_file:
#             ext = resume_file.name.split('.')[-1]
#             file_name = f"resumes/{instance.tenant_id}/{instance.id}_{uuid.uuid4()}.{ext}"
#             content_type = getattr(resume_file, 'content_type', 'application/octet-stream')
#             public_url = upload_file_dynamic(resume_file, file_name, content_type)
#             instance.resume_url = public_url

#         if cover_letter_file:
#             ext = cover_letter_file.name.split('.')[-1]
#             file_name = f"cover_letters/{instance.tenant_id}/{instance.id}_{uuid.uuid4()}.{ext}"
#             content_type = getattr(cover_letter_file, 'content_type', 'application/octet-stream')
#             public_url = upload_file_dynamic(cover_letter_file, file_name, content_type)
#             instance.cover_letter_url = public_url

#         instance.save()
#         return instance

#     def to_representation(self, instance):
#         data = super().to_representation(instance)
#         if 'compliance_status' in data:
#             data['compliance_status'] = [
#                 {
#                     **item,
#                     'document': item.get('document', {'file_url': '', 'uploaded_at': ''})
#                 } for item in data['compliance_status']
#             ]
#         return data




class JobApplicationSerializer(serializers.ModelSerializer):
    documents = DocumentSerializer(many=True, required=False)
    compliance_status = ComplianceStatusSerializer(many=True, required=False)
    job_requisition_id = serializers.CharField()
    branch_id = serializers.CharField(allow_null=True, required=False)
    tenant_id = serializers.CharField(read_only=True)
    resume_url = serializers.CharField(read_only=True)
    cover_letter_url = serializers.CharField(read_only=True)
    hired_by = serializers.JSONField(read_only=True)
    status_history = serializers.JSONField(read_only=True)  # Expose history in responses

    class Meta:
        model = JobApplication
        fields = "__all__"
        read_only_fields = [
            'id', 'tenant_id', 'resume_url', 'cover_letter_url', 'is_deleted', 'applied_at', 'created_at', 'updated_at', 'hired_by', 'status_history'
        ]

    def validate(self, data):
        request = self.context['request']
        tenant_id = get_user_data_from_jwt(request).get('tenant_unique_id')  # Adjusted for JWT

        # Validate job_application_id for updates
        if self.instance is None and 'job_application_id' in data:
            job_app = JobApplication.objects.filter(id=data['job_application_id']).first()
            if not job_app:
                raise serializers.ValidationError({"job_application_id": "Invalid job application ID."})
            if str(job_app.tenant_id) != str(tenant_id):
                raise serializers.ValidationError({"job_application_id": "Job application does not belong to this tenant."})

        # Validate branch_id (local database or skip if optional)
        if data.get('branch_id'):
            # Assuming a Branch model exists in the local database
            try:
                from .models import Branch  # Adjust import based on your project structure
                branch = Branch.objects.filter(id=data['branch_id'], tenant_id=tenant_id).first()
                if not branch:
                    raise serializers.ValidationError({"branch_id": "Invalid branch ID or branch does not belong to this tenant."})
            except ImportError:
                # If no Branch model exists, skip validation or handle differently
                logger.warning(f"Branch validation skipped: No Branch model available for branch_id {data['branch_id']}")
                # Alternatively, fail validation if branch_id is critical
                # raise serializers.ValidationError({"branch_id": "Branch validation not supported without local Branch model."})

        # Validate status transition
        if 'status' in data and self.instance:
            current_status = self.instance.status
            new_status = data['status']
            if current_status == 'interviewed' and new_status == 'hired':
                # Ensure hired_by will be set in update method
                pass
            elif new_status == 'hired' and current_status != 'interviewed':
                raise serializers.ValidationError({"status": "Status can only transition to 'hired' from 'interviewed'."})

        return data

    def create(self, validated_data):
        resume_file = self.context['request'].FILES.get('resume')
        cover_letter_file = self.context['request'].FILES.get('cover_letter')
        documents_data = validated_data.pop('documents', [])
        compliance_status = validated_data.pop('compliance_status', [])
        validated_data['tenant_id'] = get_user_data_from_jwt(self.context['request']).get('tenant_unique_id')

        documents = []
        for doc_data in documents_data:
            file = doc_data['file']
            file_ext = os.path.splitext(file.name)[1]
            filename = f"{uuid.uuid4()}{file_ext}"
            folder_path = f"application_documents/{timezone.now().strftime('%Y/%m/%d')}"
            path = f"{folder_path}/{filename}"
            content_type = mimetypes.guess_type(file.name)[0] or 'application/octet-stream'
            public_url = upload_file_dynamic(file, path, content_type)
            documents.append({
                'document_type': doc_data['document_type'],
                'file_path': path,
                'file_url': public_url,
                'uploaded_at': timezone.now().isoformat()
            })
        validated_data['documents'] = documents
        validated_data['status_history'] = []  # Initialize empty history
        validated_data['screening_status'] = [{'status': 'pending', 'updated_at': timezone.now().isoformat()}]  # Initialize as single array of single dict

        application = JobApplication.objects.create(**validated_data)

        if resume_file:
            ext = resume_file.name.split('.')[-1]
            file_name = f"resumes/{application.tenant_id}/{application.id}_{uuid.uuid4()}.{ext}"
            content_type = getattr(resume_file, 'content_type', 'application/octet-stream')
            public_url = upload_file_dynamic(resume_file, file_name, content_type)
            application.resume_url = public_url

        if cover_letter_file:
            ext = cover_letter_file.name.split('.')[-1]
            file_name = f"cover_letters/{application.tenant_id}/{application.id}_{uuid.uuid4()}.{ext}"
            content_type = getattr(cover_letter_file, 'content_type', 'application/octet-stream')
            public_url = upload_file_dynamic(cover_letter_file, file_name, content_type)
            application.cover_letter_url = public_url

        application.save()
        return application

    def update(self, instance, validated_data):
        resume_file = self.context['request'].FILES.get('resume')
        cover_letter_file = self.context['request'].FILES.get('cover_letter')
        documents_data = validated_data.pop('documents', [])
        compliance_status = validated_data.pop('compliance_status', None)

        # Check if status is changing and log manual change
        if 'status' in validated_data:
            new_status = validated_data['status']
            if new_status != instance.status and new_status in ['shortlisted', 'rejected']:
                user_data = get_user_data_from_jwt(self.context['request'])
                status_history_entry = {
                    'status': new_status,
                    'changed_by': {
                        'user_id': user_data.get('id'),
                        'email': user_data.get('email'),
                        'name': f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip()
                    },
                    'automated': False,
                    'timestamp': timezone.now().isoformat(),
                    'reason': 'Manual status update'
                }
                if instance.status_history:
                    instance.status_history.append(status_history_entry)
                else:
                    instance.status_history = [status_history_entry]
                validated_data['status_history'] = instance.status_history  # Include in update

        # Check if status is changing to 'hired' from 'interviewed'
        if 'status' in validated_data and validated_data['status'] == 'hired' and instance.status == 'interviewed':
            user_data = get_user_data_from_jwt(self.context['request'])
            if not user_data.get('id'):
                logger.warning("No user.id found in JWT payload for hired_by update")
                raise serializers.ValidationError({"detail": "Authentication required for status update to 'hired'."})
            
            validated_data['hired_by'] = {
                'email': user_data['email'],
                'first_name': user_data['first_name'],
                'last_name': user_data['last_name'],
                'job_role': user_data['job_role']
            }

        if documents_data:
            existing_documents = instance.documents or []
            for doc_data in documents_data:
                file = doc_data['file']
                file_ext = os.path.splitext(file.name)[1]
                filename = f"{uuid.uuid4()}{file_ext}"
                folder_path = f"application_documents/{timezone.now().strftime('%Y/%m/%d')}"
                path = f"{folder_path}/{filename}"
                content_type = mimetypes.guess_type(file.name)[0] or 'application/octet-stream'
                public_url = upload_file_dynamic(file, path, content_type)
                doc_data['file_url'] = public_url
                doc_data['uploaded_at'] = timezone.now().isoformat()
                existing_documents.append(doc_data)
            validated_data['documents'] = existing_documents

        if compliance_status is not None:
            validated_data['compliance_status'] = compliance_status

        instance = super().update(instance, validated_data)

        if resume_file:
            ext = resume_file.name.split('.')[-1]
            file_name = f"resumes/{instance.tenant_id}/{instance.id}_{uuid.uuid4()}.{ext}"
            content_type = getattr(resume_file, 'content_type', 'application/octet-stream')
            public_url = upload_file_dynamic(resume_file, file_name, content_type)
            instance.resume_url = public_url

        if cover_letter_file:
            ext = cover_letter_file.name.split('.')[-1]
            file_name = f"cover_letters/{instance.tenant_id}/{instance.id}_{uuid.uuid4()}.{ext}"
            content_type = getattr(cover_letter_file, 'content_type', 'application/octet-stream')
            public_url = upload_file_dynamic(cover_letter_file, file_name, content_type)
            instance.cover_letter_url = public_url

        instance.save()
        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if 'compliance_status' in data:
            data['compliance_status'] = [
                {
                    **item,
                    'document': item.get('document', {'file_url': '', 'uploaded_at': ''})
                } for item in data['compliance_status']
            ]
        return data




class ScheduleSerializer(serializers.ModelSerializer):
    job_application_id = serializers.CharField()
    branch_id = serializers.CharField(allow_null=True, required=False)
    tenant_id = serializers.CharField(read_only=True)
    candidate_name = serializers.SerializerMethodField()
    scheduled_by = serializers.SerializerMethodField()

    class Meta:
        model = Schedule
        fields = [
            'id', 'tenant_id', 'branch_id', 'job_application_id', 'candidate_name',
            'interview_start_date_time', 'interview_end_date_time', 'meeting_mode', 'meeting_link', 'interview_address',
            'message', 'timezone', 'status', 'cancellation_reason', 'is_deleted', 'created_at', 'updated_at',
            'scheduled_by_id', 'scheduled_by',
        ]
        read_only_fields = [
            'id', 'tenant_id', 'candidate_name', 'is_deleted', 'created_at', 'updated_at', 'scheduled_by'
        ]

    def get_candidate_name(self, obj):
        try:
            job_app = JobApplication.objects.filter(id=obj.job_application_id).first()
            if job_app:
                return job_app.full_name
        except Exception as e:
            logger.error(f"Error fetching candidate name for {obj.job_application_id}: {str(e)}")
        return None

    def get_scheduled_by(self, obj):
        if obj.scheduled_by_id:
            try:
                # Extract user data from JWT if the request user matches scheduled_by_id
                user_data = get_user_data_from_jwt(self.context['request'])
                if str(user_data['id']) == str(obj.scheduled_by_id):
                    return {
                        'id': user_data['id'],
                        'email': user_data['email'],
                        'first_name': user_data['first_name'],
                        'last_name': user_data['last_name']
                    }
              
                logger.warning(f"User {obj.scheduled_by_id} not found in local database")
                return None
            except Exception as e:
                logger.error(f"Error fetching scheduled_by {obj.scheduled_by_id}: {str(e)}")
                return None
        logger.warning(f"No scheduled_by_id provided for schedule {obj.id}")
        return None

    def validate_timezone(self, value):
        if value not in pytz.all_timezones:
            raise serializers.ValidationError(f"Invalid timezone: {value}. Must be a valid timezone from pytz.all_timezones.")
        return value

    def validate(self, data):
        request = self.context['request']
        tenant_id = get_tenant_id_from_jwt(request)
        if str(data.get('tenant_id', tenant_id)) != str(tenant_id):
            raise serializers.ValidationError({"tenant_id": "Tenant ID mismatch."})

        # Validate job_application_id
        if data.get('job_application_id'):
            job_app = JobApplication.objects.filter(id=data['job_application_id']).first()
            if not job_app:
                raise serializers.ValidationError({"job_application_id": "Invalid job application ID."})
            if str(job_app.tenant_id) != str(tenant_id):
                raise serializers.ValidationError({"job_application_id": "Job application does not belong to this tenant."})

        # Validate branch_id
        if data.get('branch_id'):
            try:
                from .models import Branch  # Adjust import based on your project structure
                branch = Branch.objects.filter(id=data['branch_id'], tenant_id=tenant_id).first()
                if not branch:
                    raise serializers.ValidationError({"branch_id": "Invalid branch ID or branch does not belong to this tenant."})
            except ImportError:
                logger.warning(f"Branch validation skipped: No Branch model available for branch_id {data['branch_id']}")
                # Alternatively, fail validation if branch_id is critical
                # raise serializers.ValidationError({"branch_id": "Branch validation not supported without local Branch model."})

        # Additional validations
        if data.get('meeting_mode') == 'Virtual' and not data.get('meeting_link'):
            raise serializers.ValidationError("Meeting link is required for virtual interviews.")
        if data.get('meeting_mode') == 'Virtual' and data.get('meeting_link'):
            validate_url = URLValidator()
            try:
                validate_url(data['meeting_link'])
            except serializers.ValidationError:
                logger.error(f"Invalid meeting link URL: {data['meeting_link']}")
                raise serializers.ValidationError("Invalid meeting link URL.")
        if data.get('meeting_mode') == 'Physical' and not data.get('interview_address'):
            raise serializers.ValidationError("Interview address is required for physical interviews.")
        if data.get('status') == 'cancelled' and not data.get('cancellation_reason'):
            raise serializers.ValidationError("Cancellation reason is required for cancelled schedules.")
        if data.get('interview_start_date_time') and data['interview_start_date_time'] <= timezone.now():
            raise serializers.ValidationError("Interview start date and time must be in the future.")
        if data.get('interview_end_date_time') and data.get('interview_start_date_time'):
            if data['interview_end_date_time'] <= data['interview_start_date_time']:
                raise serializers.ValidationError("Interview end date and time must be after start date and time.")
        return data

    def create(self, validated_data):
        validated_data['tenant_id'] = str(get_tenant_id_from_jwt(self.context['request']))
        user_data = get_user_data_from_jwt(self.context['request'])
        user_id = user_data.get('id')
        if user_id:
            validated_data['scheduled_by_id'] = str(user_id)
        else:
            logger.warning("No user_id found in JWT payload for schedule creation")
            raise serializers.ValidationError({"scheduled_by_id": "User ID required for scheduling."})

        try:
            schedule = Schedule.objects.create(**validated_data)
            logger.info(f"Schedule created: {schedule.id} for job_application_id: {schedule.job_application_id} by user: {schedule.scheduled_by_id}")
            return schedule
        except IntegrityError as e:
            logger.error(f"IntegrityError on schedule create: {str(e)}")
            raise serializers.ValidationError({
                "job_application_id": "An active schedule already exists for this job application."
            })

    def update(self, instance, validated_data):
        if validated_data.get('status') == 'cancelled' and instance.status != 'cancelled' and not validated_data.get('cancellation_reason'):
            raise serializers.ValidationError("Cancellation reason is required when cancelling a schedule.")
        if validated_data.get('status') != 'cancelled':
            validated_data['cancellation_reason'] = None
        return super().update(instance, validated_data)
    

    
class SimpleMessageSerializer(serializers.Serializer):
    detail = serializers.CharField()



