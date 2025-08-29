import pytz
import uuid
import os
from django.conf import settings
from django.utils import timezone
from django.core.validators import URLValidator
from rest_framework import serializers
from .models import JobApplication, Schedule
import logging
from lumina_care.supabase_client import supabase
import mimetypes
import io

logger = logging.getLogger('job_applications')




class DocumentSerializer(serializers.Serializer):
    document_type = serializers.CharField(max_length=50)
    file = serializers.FileField(write_only=True)
    file_url = serializers.SerializerMethodField(read_only=True)
    uploaded_at = serializers.DateTimeField(read_only=True, default=timezone.now)

    def get_file_url(self, obj):
        file_url = obj.get('file_url', None)
        if file_url:
            return file_url
        return None

    def validate_file(self, value):
        allowed_types = [
            'application/pdf',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        ]
        if value.content_type not in allowed_types:
            raise serializers.ValidationError(
                f"Invalid file type: {value.content_type}. Only PDF and Word (.doc, .docx) files are allowed."
            )
        max_size = 50 * 1024 * 1024
        if value.size > max_size:
            raise serializers.ValidationError(f"File size exceeds 50 MB limit.")
        return value
    
    def validate_document_type(self, value):
        job_requisition = self.context.get('job_requisition')
        if not job_requisition:
            raise serializers.ValidationError("Job requisition context is missing.")
        documents_required = job_requisition.documents_required or []
        if not value:
            raise serializers.ValidationError("Document type is required.")
        try:
            uuid.UUID(value)
            return value
        except ValueError:
            pass
        if value.lower() in ['resume', 'curriculum vitae (cv)']:  # Allow "Curriculum Vitae (CV)" explicitly
            return value
        if documents_required and value not in documents_required:
            raise serializers.ValidationError(
                f"Invalid document type: {value}. Must be one of {documents_required} or 'Curriculum Vitae (CV)'."
            )
        return value

    # def validate_document_type(self, value):
    #     job_requisition = self.context.get('job_requisition')
    #     if not job_requisition:
    #         raise serializers.ValidationError("Job requisition context is missing.")
    #     documents_required = job_requisition.documents_required or []
    #     if not value:
    #         raise serializers.ValidationError("Document type is required.")
    #     try:
    #         uuid.UUID(value)
    #         return value
    #     except ValueError:
    #         pass
    #     if value.lower() == 'resume':
    #         return value
    #     if documents_required and value not in documents_required:
    #         raise serializers.ValidationError(
    #             f"Invalid document type: {value}. Must be one of {documents_required} or 'resume'."
    #         )
    #     return value


class ComplianceDocumentSerializer(serializers.Serializer):
    file_url = serializers.CharField(allow_blank=True, required=False, allow_null=True)
    uploaded_at = serializers.DateTimeField(allow_null=True, required=False)


class ComplianceStatusSerializer(serializers.Serializer):
    id = serializers.CharField(allow_blank=True, required=False, allow_null=True)
    name = serializers.CharField(allow_blank=True, required=False, allow_null=True)
    description = serializers.CharField(allow_blank=True, required=False, allow_null=True)
    required = serializers.BooleanField(required=False)
    status = serializers.CharField(allow_blank=True, required=False, allow_null=True)
    checked_by = serializers.CharField(allow_blank=True, required=False, allow_null=True)
    checked_at = serializers.DateTimeField(allow_null=True, required=False)
    notes = serializers.CharField(allow_blank=True, required=False, allow_null=True)
    document = ComplianceDocumentSerializer(required=False, allow_null=True)


class JobApplicationSerializer(serializers.ModelSerializer):
    documents = DocumentSerializer(many=True, required=False)
    job_requisition_id = serializers.CharField(source='job_requisition.id', read_only=True)
    job_requisition_title = serializers.CharField(source='job_requisition.title', read_only=True)
    tenant_schema = serializers.CharField(source='tenant.schema_name', read_only=True)
    compliance_status = ComplianceStatusSerializer(many=True, required=False)

    branch = serializers.SlugRelatedField(slug_field='name', read_only=True, allow_null=True)

    class Meta:
        model = JobApplication
        fields = [
            'id', 'tenant', 'tenant_schema', 'branch', 'job_requisition', 'job_requisition_id',
            'job_requisition_title', 'date_of_birth', 'full_name', 'email', 'phone',
            'qualification', 'experience', 'screening_status', 'screening_score',
            'knowledge_skill', 'cover_letter', 'resume_status', 'employment_gaps',
            'status', 'source', 'documents', 'compliance_status', 'interview_location',
            'is_deleted', 'applied_at', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'tenant', 'tenant_schema', 'job_requisition_id', 'job_requisition_title',
            'is_deleted', 'applied_at', 'created_at', 'updated_at', 'branch'
        ]

    def validate(self, data):
        tenant = self.context['request'].tenant
        job_requisition = self.context.get('job_requisition')
        instance = self.instance  # Get the existing instance for updates

        if not job_requisition:
            raise serializers.ValidationError("Job requisition is required.")
        if not job_requisition.publish_status:
            raise serializers.ValidationError("This job is not published.")

        documents_required = job_requisition.documents_required or []
        documents_data = data.get('documents', [])
        existing_documents = instance.documents if instance else []

        # Get existing document types
        existing_types = {doc['document_type'] for doc in existing_documents}
        provided_types = {doc['document_type'] for doc in documents_data}

        # Combine existing and provided document types
        all_provided_types = existing_types.union(provided_types)

        # Check for missing required documents
        missing_docs = [doc for doc in documents_required if doc not in all_provided_types]
        if missing_docs:
            raise serializers.ValidationError(
                f"Missing required documents: {', '.join(missing_docs)}."
            )

        return data

    def create(self, validated_data):
        documents_data = validated_data.pop('documents', [])
        compliance_status = validated_data.pop('compliance_status', [])
        tenant = self.context['request'].tenant
        validated_data['tenant'] = tenant
        user = self.context['request'].user
        if user.is_authenticated and user.role == 'recruiter' and user.branch:
            validated_data['branch'] = user.branch
        logger.debug(f"Creating application for tenant: {tenant.schema_name}, job_requisition: {validated_data['job_requisition'].title}")

        documents = []
        #FOR SUPERBASE FILE HANDLING
        for doc_data in documents_data:
            file = doc_data['file']
            file_ext = os.path.splitext(file.name)[1]
            filename = f"{uuid.uuid4()}{file_ext}"
            folder_path = f"application_documents/{timezone.now().strftime('%Y/%m/%d')}"
            path = f"{folder_path}/{filename}"
            content_type = mimetypes.guess_type(file.name)[0]

            # Upload to Supabase
            supabase.storage.from_(settings.SUPABASE_BUCKET).upload(
                path, file.read(), {"content-type": content_type or 'application/octet-stream'}
            )
            file_url = supabase.storage.from_(settings.SUPABASE_BUCKET).get_public_url(path)

            documents.append({
                'document_type': doc_data['document_type'],
                'file_path': path,
                'file_url': file_url,
                'uploaded_at': timezone.now().isoformat()
            })
        #FOR SUPERBASE FILE HANDLING

        validated_data['documents'] = documents
        logger.debug(f"Documents to be saved: {documents}")
        application = JobApplication.objects.create(**validated_data)
        application.initialize_compliance_status(validated_data['job_requisition'])
        logger.info(f"Application created: {application.id} for {application.full_name}")
        return application


    # def update(self, instance, validated_data):
    #     documents_data = validated_data.pop('documents', [])
    #     compliance_status = validated_data.pop('compliance_status', None)
    #     job_requisition = instance.job_requisition

    #     if documents_data:
    #         existing_documents = instance.documents or []
    #         for doc_data in documents_data:
    #             file = doc_data['file']
    #             document_type = doc_data['document_type']

    #             folder_path = os.path.join('compliance_documents', timezone.now().strftime('%Y/%m/%d'))
    #             full_folder_path = os.path.join(settings.MEDIA_ROOT, folder_path)
    #             os.makedirs(full_folder_path, exist_ok=True)
    #             file_extension = os.path.splitext(file.name)[1]
    #             filename = f"{uuid.uuid4()}{file_extension}"
    #             upload_path = os.path.join(folder_path, filename).replace('\\', '/')
    #             full_upload_path = os.path.join(settings.MEDIA_ROOT, upload_path)
    #             logger.debug(f"Saving file to full_upload_path: {full_upload_path}")

    #             try:


    #                 with open(full_upload_path, 'wb+') as destination:
    #                     for chunk in file.chunks():
    #                         destination.write(chunk)



    #                 logger.debug(f"File saved successfully: {full_upload_path}")
    #             except Exception as e:
    #                 logger.error(f"Failed to save file {full_upload_path}: {str(e)}")
    #                 raise serializers.ValidationError(f"Failed to save file: {str(e)}")

    #             file_url = f"/media/{upload_path.lstrip('/')}"
    #             doc_data['file_url'] = file_url
    #             doc_data['uploaded_at'] = timezone.now().isoformat()
    #             existing_documents.append(doc_data)

    #         validated_data['documents'] = existing_documents

    #     if compliance_status is not None:
    #         validated_data['compliance_status'] = compliance_status

    #     return super().update(instance, validated_data)


#FOR SUPERBASE FILE HANDLING
    def update(self, instance, validated_data):
        documents_data = validated_data.pop('documents', [])
        compliance_status = validated_data.pop('compliance_status', None)
        job_requisition = instance.job_requisition

        if documents_data:
            existing_documents = instance.documents or []
            for doc_data in documents_data:
                file = doc_data['file']
                document_type = doc_data['document_type']

                file_extension = os.path.splitext(file.name)[1]
                unique_filename = f"{uuid.uuid4()}{file_extension}"
                folder_path = timezone.now().strftime('%Y/%m/%d')
                upload_path = f"compliance_documents/{folder_path}/{unique_filename}"

                try:
                    file_like = io.BytesIO(file.read())
                    file_like.seek(0)

                    supabase.storage.from_("your-bucket-name").upload(upload_path, file_like)
                    public_url = supabase.storage.from_("your-bucket-name").get_public_url(upload_path)

                    doc_data['file_url'] = public_url
                    doc_data['uploaded_at'] = timezone.now().isoformat()
                    existing_documents.append(doc_data)

                except Exception as e:
                    logger.error(f"Failed to upload file to Supabase: {str(e)}")
                    raise serializers.ValidationError(f"Supabase upload failed: {str(e)}")

            validated_data['documents'] = existing_documents

        if compliance_status is not None:
            validated_data['compliance_status'] = compliance_status

        return super().update(instance, validated_data)

#FOR SUPERBASE FILE HANDLING

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



class ScheduleSerializer(serializers.ModelSerializer):
    job_application_id = serializers.CharField(source='job_application.id', read_only=True)
    tenant_schema = serializers.CharField(source='tenant.schema_name', read_only=True)
    candidate_name = serializers.CharField(source='job_application.full_name', read_only=True)
    job_requisition_title = serializers.CharField(source='job_application.job_requisition.title', read_only=True)
    branch = serializers.SlugRelatedField(slug_field='name', read_only=True, allow_null=True)

    class Meta:
        model = Schedule
        fields = [
            'id', 'tenant', 'tenant_schema', 'branch', 'job_application', 'job_application_id',
            'candidate_name', 'job_requisition_title', 'interview_start_date_time', 'interview_end_date_time',
            'meeting_mode', 'meeting_link', 'interview_address', 'message', 'timezone',
            'status', 'cancellation_reason', 'is_deleted', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'tenant', 'tenant_schema', 'job_application_id', 'candidate_name',
            'job_requisition_title', 'is_deleted', 'created_at', 'updated_at', 'branch'
        ]

    def validate_timezone(self, value):
        if value not in pytz.all_timezones:
            raise serializers.ValidationError(f"Invalid timezone: {value}. Must be a valid timezone from pytz.all_timezones.")
        return value

    def validate(self, data):
        tenant = self.context['request'].tenant
        job_application = data.get('job_application', getattr(self.instance, 'job_application', None))
        if not job_application:
            logger.error("Job application is required but not provided or found on instance")
            raise serializers.ValidationError("Job application is required.")
        if job_application.status != 'shortlisted':
            raise serializers.ValidationError("Schedules can only be created for shortlisted applicants.")
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
        tenant = self.context['request'].tenant
        user = self.context['request'].user
        validated_data['tenant'] = tenant
        if user.is_authenticated and user.role == 'recruiter' and user.branch:
            validated_data['branch'] = user.branch
        schedule = Schedule.objects.create(**validated_data)
        logger.info(f"Schedule created: {schedule.id} for {schedule.job_application.full_name}")
        return schedule

    def update(self, instance, validated_data):
        if validated_data.get('status') == 'cancelled' and instance.status != 'cancelled' and not validated_data.get('cancellation_reason'):
            raise serializers.ValidationError("Cancellation reason is required when cancelling a schedule.")
        if validated_data.get('status') != 'cancelled':
            validated_data['cancellation_reason'] = None
        return super().update(instance, validated_data)
    


