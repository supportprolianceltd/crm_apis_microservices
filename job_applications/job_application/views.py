import logging
import os
import uuid
import requests
import tempfile
import mimetypes

from django.conf import settings
from django.utils import timezone
from django.db import transaction

from .permissions import IsMicroserviceAuthenticated
from rest_framework import generics, status
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import JobApplication, Schedule
from .serializers import (
    JobApplicationSerializer, ScheduleSerializer, ComplianceStatusSerializer, SimpleMessageSerializer
)
from utils.screen import parse_resume, screen_resume, extract_resume_fields
from .tenant_utils import resolve_tenant_from_unique_link

logger = logging.getLogger('job_applications')

def get_job_requisition_by_id(job_requisition_id, request):
    resp = requests.get(
        f"{settings.TALENT_ENGINE_URL}/api/talent-engine/requisitions/{job_requisition_id}/",
        headers={'Authorization': request.META.get("HTTP_AUTHORIZATION", "")}
    )
    if resp.status_code == 200:
        return resp.json()
    return None

def get_branch_by_id(branch_id, request):
    resp = requests.get(
        f"{settings.AUTH_SERVICE_URL}/api/tenant/branches/{branch_id}/",
        headers={'Authorization': request.META.get("HTTP_AUTHORIZATION", "")}
    )
    if resp.status_code == 200:
        return resp.json()
    return None

def get_tenant_by_id(tenant_id, request):
    resp = requests.get(
        f"{settings.AUTH_SERVICE_URL}/api/tenant/tenants/{tenant_id}/",
        headers={'Authorization': request.META.get("HTTP_AUTHORIZATION", "")}
    )
    if resp.status_code == 200:
        return resp.json()
    return None


class ResumeParseView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [AllowAny]
    serializer_class = SimpleMessageSerializer

    def post(self, request):
        logger.info(f"Incoming request content-type: {request.content_type}")
        logger.info(f"Request FILES keys: {list(request.FILES.keys())}")
        logger.info(f"Request DATA keys: {list(request.data.keys())}")

        try:
            resume_file = request.FILES.get('resume')
            if not resume_file:
                logger.error(f"No resume file found. Available files: {list(request.FILES.keys())}")
                return Response({"detail": "Resume file is required."}, status=status.HTTP_400_BAD_REQUEST)
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                for chunk in resume_file.chunks():
                    temp_file.write(chunk)
                temp_file_path = temp_file.name
            logger.info(f"Temporary resume file saved at: {temp_file_path}")
            resume_text = parse_resume(temp_file_path)
            os.unlink(temp_file_path)
            if not resume_text:
                logger.error(f"Could not extract text from resume. File: {resume_file.name}")
                return Response({"detail": "Could not extract text from resume."}, status=status.HTTP_400_BAD_REQUEST)
            extracted_data = extract_resume_fields(resume_text)
            logger.info(f"Resume parsed successfully for file: {resume_file.name}")
            return Response({
                "detail": "Resume parsed successfully",
                "data": extracted_data
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(f"Error parsing resume: {str(e)} | Request data: {request.data}, FILES: {request.FILES}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




class ResumeScreeningView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    serializer_class = SimpleMessageSerializer  # <-- Add this line

    def post(self, request, job_requisition_id):
        try:
            document_type = request.data.get('document_type')
            applications_data = request.data.get('applications', [])
            num_candidates = request.data.get('number_of_candidates')
            try:
                num_candidates = int(num_candidates)
            except (TypeError, ValueError):
                num_candidates = 0

            job_requisition = get_job_requisition_by_id(job_requisition_id, request)
            if not job_requisition:
                return Response({"detail": "Job requisition not found."}, status=status.HTTP_404_NOT_FOUND)

            if not document_type:
                return Response({"detail": "Document type is required."}, status=status.HTTP_400_BAD_REQUEST)

            document_type_lower = document_type.lower()
            allowed_docs = [doc.lower() for doc in (job_requisition.get('documents_required') or [])]
            if document_type_lower not in allowed_docs and document_type_lower not in ['resume', 'curriculum vitae (cv)']:
                return Response({"detail": f"Invalid document type: {document_type}"}, status=status.HTTP_400_BAD_REQUEST)

            if not applications_data:
                applications = JobApplication.active_objects.filter(
                    job_requisition_id=job_requisition_id,
                    resume_status=True
                )
            else:
                application_ids = [app['application_id'] for app in applications_data]
                applications = JobApplication.active_objects.filter(
                    job_requisition_id=job_requisition_id,
                    id__in=application_ids,
                    resume_status=True
                )

            if request.user.role == 'recruiter' and request.user.branch:
                applications = applications.filter(branch=request.user.branch)

            if not applications.exists():
                return Response({"detail": "No applications with resumes found.", "documentType": document_type}, status=status.HTTP_400_BAD_REQUEST)

            results = []
            failed_applications = []
            for app in applications:
                app_data = next((a for a in applications_data if a['application_id'] == app.id), None)
                if app_data and 'file_url' in app_data:
                    file_url = app_data['file_url']
                else:
                    cv_doc = next(
                        (doc for doc in app.documents if doc['document_type'].lower() == document_type_lower),
                        None
                    )
                    if not cv_doc:
                        app.screening_status = 'failed'
                        app.screening_score = 0.0
                        app.save()
                        failed_applications.append({
                            "application_id": app.id,
                            "full_name": app.full_name,
                            "email": app.email,
                            "error": f"No {document_type} document found"
                        })
                        continue
                    file_url = cv_doc['file_url']

                try:
                    temp_file_path = None
                    if file_url.startswith('http'):
                        headers = {"Authorization": f"Bearer {settings.SUPABASE_KEY}"}
                        response = requests.get(file_url, headers=headers)
                        if response.status_code != 200:
                            app.screening_status = 'failed'
                            app.screening_score = 0.0
                            app.save()
                            failed_applications.append({
                                "application_id": app.id,
                                "full_name": app.full_name,
                                "email": app.email,
                                "error": f"Failed to download resume from {file_url}, status code: {response.status_code}"
                            })
                            continue

                        content_type = response.headers.get('content-type', '')
                        file_ext = mimetypes.guess_extension(content_type) or os.path.splitext(file_url)[1] or '.pdf'
                        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_ext)
                        temp_file.write(response.content)
                        temp_file.close()
                        temp_file_path = temp_file.name
                    else:
                        app.screening_status = 'failed'
                        app.screening_score = 0.0
                        app.save()
                        failed_applications.append({
                            "application_id": app.id,
                            "full_name": app.full_name,
                            "email": app.email,
                            "error": f"Invalid file URL: {file_url}"
                        })
                        continue

                    resume_text = parse_resume(temp_file_path)
                    if temp_file_path and os.path.exists(temp_file_path):
                        os.unlink(temp_file_path)
                    if not resume_text:
                        app.screening_status = 'failed'
                        app.screening_score = 0.0
                        app.save()
                        failed_applications.append({
                            "application_id": app.id,
                            "full_name": app.full_name,
                            "email": app.email,
                            "error": "Failed to parse resume"
                        })
                        continue

                    job_requirements = (
                        (job_requisition.get('job_description') or '') + ' ' +
                        (job_requisition.get('qualification_requirement') or '') + ' ' +
                        (job_requisition.get('experience_requirement') or '') + ' ' +
                        (job_requisition.get('knowledge_requirement') or '')
                    ).strip()

                    score = screen_resume(resume_text, job_requirements)
                    resume_data = extract_resume_fields(resume_text)
                    employment_gaps = resume_data.get("employment_gaps", [])

                    app.screening_status = 'processed'
                    app.screening_score = score
                    app.employment_gaps = employment_gaps
                    app.save()

                    results.append({
                        "application_id": app.id,
                        "full_name": app.full_name,
                        "email": app.email,
                        "score": score,
                        "screening_status": app.screening_status,
                        "employment_gaps": employment_gaps
                    })
                except Exception as e:
                    app.screening_status = 'failed'
                    app.screening_score = 0.0
                    app.save()
                    failed_applications.append({
                        "application_id": app.id,
                        "full_name": app.full_name,
                        "email": app.email,
                        "error": f"Screening error: {str(e)}"
                    })
                    continue

            if not results and failed_applications:
                return Response({
                    "detail": "All resume screenings failed.",
                    "failed_applications": failed_applications,
                    "document_type": document_type
                }, status=status.HTTP_400_BAD_REQUEST)

            results.sort(key=lambda x: x['score'], reverse=True)
            shortlisted = results[:num_candidates]
            shortlisted_ids = {item['application_id'] for item in shortlisted}

            for app in applications:
                if app.id in shortlisted_ids:
                    app.status = 'shortlisted'
                else:
                    app.status = 'rejected'
                app.save()

            return Response({
                "detail": f"Screened {len(results)} applications using '{document_type}', shortlisted {len(shortlisted)} candidates.",
                "shortlisted_candidates": shortlisted,
                "failed_applications": failed_applications,
                "number_of_candidates": num_candidates,
                "document_type": document_type
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"Error screening resumes for JobRequisition {job_requisition_id}: {str(e)}")
            return Response({
                "detail": f"Failed to screen resumes: {str(e)}",
                "document_type": request.data.get('document_type'),
                "error_type": type(e).__name__
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class JobApplicationListCreateView(generics.ListCreateAPIView):
    serializer_class = JobApplicationSerializer
    permission_classes = [IsMicroserviceAuthenticated]
    parser_classes = (MultiPartParser, FormParser)

    def get_queryset(self):
        logger.info(f"request.user: {self.request.user}, is_authenticated: {getattr(self.request.user, 'is_authenticated', None)}")
        tenant_id = self.request.query_params.get('tenant_id')
        branch_id = self.request.query_params.get('branch_id')
        queryset = JobApplication.active_objects.all()
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)
        if hasattr(self.request.user, 'branch') and self.request.user.branch:
            queryset = queryset.filter(branch=self.request.user.branch)
        return queryset.order_by('-created_at')
    

    def check_permissions(self, request):
        logger.info(f"Permission check for {request.user} - authenticated: {getattr(request.user, 'is_authenticated', None)}")
        return super().check_permissions(request)

    def create(self, request, *args, **kwargs):
        job_requisition_id = request.data.get('job_requisition_id')
        job_requisition = get_job_requisition_by_id(job_requisition_id, request)
        if not job_requisition:
            return Response({"detail": "Invalid job requisition."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(data=request.data, context={'request': request, 'job_requisition': job_requisition})
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class JobApplicationDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = JobApplicationSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'

    def get_queryset(self):
        tenant_id = self.request.query_params.get('tenant_id')
        branch_id = self.request.query_params.get('branch_id')
        queryset = JobApplication.active_objects.all()
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)
        if self.request.user.is_authenticated and self.request.user.branch:
            queryset = queryset.filter(branch=self.request.user.branch)
        return queryset

class JobApplicationBulkDeleteView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SimpleMessageSerializer  # <-- Add this line

    def post(self, request):
        ids = request.data.get('ids', [])
        if not ids:
            return Response({"detail": "No IDs provided."}, status=status.HTTP_400_BAD_REQUEST)
        applications = JobApplication.active_objects.filter(id__in=ids)
        if request.user.is_authenticated and request.user.branch:
            applications = applications.filter(branch=request.user.branch)
        count = applications.count()
        if count == 0:
            return Response({"detail": "No applications found."}, status=status.HTTP_404_NOT_FOUND)
        with transaction.atomic():
            for application in applications:
                application.soft_delete()
        return Response({"detail": f"Soft-deleted {count} application(s)."}, status=status.HTTP_200_OK)

class SoftDeletedJobApplicationsView(generics.ListAPIView):
    serializer_class = JobApplicationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = JobApplication.objects.filter(is_deleted=True)
        if self.request.user.is_authenticated and self.request.user.branch:
            queryset = queryset.filter(branch=self.request.user.branch)
        return queryset.order_by('-created_at')

class RecoverSoftDeletedJobApplicationsView(APIView):
    serializer_class = SimpleMessageSerializer 
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ids = request.data.get('ids', [])
        if not ids:
            return Response({"detail": "No application IDs provided."}, status=status.HTTP_400_BAD_REQUEST)
        applications = JobApplication.objects.filter(id__in=ids, is_deleted=True)
        if request.user.is_authenticated and request.user.branch:
            applications = applications.filter(branch=request.user.branch)
        if not applications.exists():
            return Response({"detail": "No soft-deleted applications found."}, status=status.HTTP_404_NOT_FOUND)
        with transaction.atomic():
            for application in applications:
                application.restore()
        return Response({"detail": f"Successfully recovered {applications.count()} application(s)."}, status=status.HTTP_200_OK)

class PermanentDeleteJobApplicationsView(APIView):
    serializer_class = SimpleMessageSerializer 
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ids = request.data.get('ids', [])
        if not ids:
            return Response({"detail": "No application IDs provided."}, status=status.HTTP_400_BAD_REQUEST)
        applications = JobApplication.objects.filter(id__in=ids, is_deleted=True)
        if request.user.is_authenticated and request.user.branch:
            applications = applications.filter(branch=request.user.branch)
        if not applications.exists():
            return Response({"detail": "No soft-deleted applications found."}, status=status.HTTP_404_NOT_FOUND)
        deleted_count = applications.delete()[0]
        return Response({"detail": f"Successfully permanently deleted {deleted_count} application(s)."}, status=status.HTTP_200_OK)

class ScheduleListCreateView(generics.ListCreateAPIView):
    serializer_class = ScheduleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant_id = self.request.query_params.get('tenant_id')
        branch_id = self.request.query_params.get('branch_id')
        queryset = Schedule.active_objects.all()
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)
        if self.request.user.is_authenticated and self.request.user.branch:
            queryset = queryset.filter(branch=self.request.user.branch)
        status_param = self.request.query_params.get('status', None)
        if status_param:
            queryset = queryset.filter(status=status_param)
        return queryset.order_by('-created_at')

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class ScheduleDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ScheduleSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'

    def get_queryset(self):
        tenant_id = self.request.query_params.get('tenant_id')
        branch_id = self.request.query_params.get('branch_id')
        queryset = Schedule.active_objects.all()
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)
        if self.request.user.is_authenticated and self.request.user.branch:
            queryset = queryset.filter(branch=self.request.user.branch)
        return queryset

class ScheduleBulkDeleteView(APIView):
    serializer_class = SimpleMessageSerializer 
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ids = request.data.get('ids', [])
        if not ids:
            return Response({"detail": "No schedule IDs provided."}, status=status.HTTP_400_BAD_REQUEST)
        schedules = Schedule.active_objects.filter(id__in=ids)
        if request.user.is_authenticated and request.user.branch:
            schedules = schedules.filter(branch=request.user.branch)
        if not schedules.exists():
            return Response({"detail": "No schedules found."}, status=status.HTTP_404_NOT_FOUND)
        with transaction.atomic():
            for schedule in schedules:
                schedule.soft_delete()
        return Response({"detail": f"Successfully soft-deleted {schedules.count()} schedule(s)."}, status=status.HTTP_200_OK)

class SoftDeletedSchedulesView(generics.ListAPIView):
    serializer_class = ScheduleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Schedule.objects.filter(is_deleted=True)
        if self.request.user.is_authenticated and self.request.user.branch:
            queryset = queryset.filter(branch=self.request.user.branch)
        return queryset.order_by('-created_at')

class RecoverSoftDeletedSchedulesView(APIView):
    serializer_class = SimpleMessageSerializer 
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ids = request.data.get('ids', [])
        if not ids:
            return Response({"detail": "No schedule IDs provided."}, status=status.HTTP_400_BAD_REQUEST)
        schedules = Schedule.objects.filter(id__in=ids, is_deleted=True)
        if request.user.is_authenticated and request.user.branch:
            schedules = schedules.filter(branch=request.user.branch)
        if not schedules.exists():
            return Response({"detail": "No soft-deleted schedules found."}, status=status.HTTP_404_NOT_FOUND)
        with transaction.atomic():
            for schedule in schedules:
                schedule.restore()
        return Response({"detail": f"Successfully recovered {schedules.count()} schedule(s)."}, status=status.HTTP_200_OK)

class PermanentDeleteSchedulesView(APIView):
    serializer_class = SimpleMessageSerializer 
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ids = request.data.get('ids', [])
        if not ids:
            return Response({"detail": "No schedule IDs provided."}, status=status.HTTP_400_BAD_REQUEST)
        schedules = Schedule.objects.filter(id__in=ids, is_deleted=True)
        if request.user.is_authenticated and request.user.branch:
            schedules = schedules.filter(branch=request.user.branch)
        if not schedules.exists():
            return Response({"detail": "No soft-deleted schedules found."}, status=status.HTTP_404_NOT_FOUND)
        deleted_count = schedules.delete()[0]
        return Response({"detail": f"Successfully permanently deleted {deleted_count} schedule(s)."}, status=status.HTTP_200_OK)

class ComplianceStatusUpdateView(APIView):
    serializer_class = ComplianceStatusSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request, application_id, item_id):
        try:
            application = JobApplication.active_objects.get(id=application_id)
        except JobApplication.DoesNotExist:
            return Response({"detail": "Job application not found."}, status=status.HTTP_404_NOT_FOUND)
        if request.user.branch and application.branch != request.user.branch:
            return Response({"detail": "Not authorized to access this application."}, status=status.HTTP_403_FORBIDDEN)
        status_val = request.data.get('status')
        notes = request.data.get('notes', '')
        if status_val not in ['pending', 'passed', 'failed']:
            return Response({"detail": "Invalid status. Must be 'pending', 'passed', or 'failed'."}, status=status.HTTP_400_BAD_REQUEST)
        updated_item = application.update_compliance_status(
            item_id=item_id,
            status=status_val,
            checked_by=request.user,
            notes=notes
        )
        return Response({
            "detail": "Compliance status updated successfully.",
            "compliance_item": updated_item
        }, status=status.HTTP_200_OK)

class ApplicantComplianceUploadView(APIView):
    serializer_class = SimpleMessageSerializer 
    permission_classes = []

    def put(self, request, job_application_id):
        try:
            application = JobApplication.active_objects.get(id=job_application_id)
        except JobApplication.DoesNotExist:
            return Response({"detail": "Job application not found."}, status=status.HTTP_404_NOT_FOUND)
        files = request.FILES.getlist('documents')
        document_ids = request.POST.getlist('document_ids')
        document_names = request.POST.getlist('document_names')
        if not files or len(files) != len(document_ids) or len(files) != len(document_names):
            return Response({"detail": "Mismatch in documents, document_ids, or document_names."}, status=status.HTTP_400_BAD_REQUEST)
        compliance_checklist = {item['id']: item['name'] for item in (application.compliance_status or [])}
        for doc_id in document_ids:
            if doc_id not in compliance_checklist:
                return Response({"detail": f"Invalid compliance item ID: {doc_id}"}, status=status.HTTP_400_BAD_REQUEST)
        documents_data = []
        for i, (file, doc_id, doc_name) in enumerate(zip(files, document_ids, document_names)):
            folder_path = os.path.join('compliance_documents', timezone.now().strftime('%Y/%m/%d'))
            os.makedirs(os.path.join(settings.MEDIA_ROOT, folder_path), exist_ok=True)
            file_extension = os.path.splitext(file.name)[1]
            filename = f"{uuid.uuid4()}{file_extension}"
            upload_path = os.path.join(folder_path, filename).replace('\\', '/')
            full_upload_path = os.path.join(settings.MEDIA_ROOT, upload_path)
            with open(full_upload_path, 'wb+') as destination:
                for chunk in file.chunks():
                    destination.write(chunk)
            file_url = f"/media/{upload_path.lstrip('/')}"
            documents_data.append({
                'document_type': doc_id,
                'file': file,
                'file_url': file_url,
                'uploaded_at': timezone.now().isoformat()
            })
        updated_compliance_status = application.compliance_status.copy() if application.compliance_status else []
        for doc_id, doc_name, doc_data in zip(document_ids, document_names, documents_data):
            for item in updated_compliance_status:
                if str(item.get('id')) == str(doc_id):
                    item['name'] = compliance_checklist[doc_id]
                    item['document'] = {
                        'file_url': doc_data['file_url'],
                        'uploaded_at': doc_data['uploaded_at']
                    }
                    item['status'] = 'uploaded'
                    item['notes'] = ''
                    break
            else:
                updated_compliance_status.append({
                    'id': doc_id,
                    'name': compliance_checklist[doc_id],
                    'description': '',
                    'required': True,
                    'status': 'uploaded',
                    'checked_by': None,
                    'checked_at': None,
                    'notes': '',
                    'document': {
                        'file_url': doc_data['file_url'],
                        'uploaded_at': doc_data['uploaded_at']
                    }
                })
        with transaction.atomic():
            application.compliance_status = updated_compliance_status
            application.save()
        serializer = JobApplicationSerializer(application, context={'request': request})
        return Response({
            "detail": "Compliance documents uploaded successfully.",
            "compliance_status": serializer.data['compliance_status']
        }, status=status.HTTP_200_OK)

class JobApplicationWithSchedulesView(APIView):
    serializer_class = SimpleMessageSerializer 
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        unique_link = request.query_params.get('unique_link')
        if not unique_link:
            logger.error("No unique_link provided in the request")
            return Response({"detail": "Unique link is required."}, status=status.HTTP_400_BAD_REQUEST)

        # You must implement this function to resolve tenant and job_requisition via API, not ORM
        tenant, job_requisition = resolve_tenant_from_unique_link(unique_link)
        if not tenant or not job_requisition:
            logger.error(f"Invalid or expired unique_link: {unique_link}")
            return Response({"detail": "Invalid or expired job link."}, status=status.HTTP_400_BAD_REQUEST)

        job_application_code = kwargs.get('code')
        email = kwargs.get('email')
        if not job_application_code or not email:
            logger.error("Missing job_application_code or email in request")
            return Response({"detail": "Both job application code and email are required."}, status=status.HTTP_400_BAD_REQUEST)

        # Only use ORM for your own models
        try:
            job_application = JobApplication.active_objects.get(
                job_requisition_id=job_requisition['id'],
                email=email,
                tenant_id=tenant['id']
            )
        except JobApplication.DoesNotExist:
            logger.error(f"JobApplication with code {job_application_code} and email {email} not found for tenant {tenant['id']}")
            return Response({"detail": "Job application not found."}, status=status.HTTP_404_NOT_FOUND)
        except JobApplication.MultipleObjectsReturned:
            logger.error(f"Multiple JobApplications found for code {job_application_code} and email {email} in tenant {tenant['id']}")
            return Response({"detail": "Multiple job applications found. Please contact support."}, status=status.HTTP_400_BAD_REQUEST)

        job_application_serializer = JobApplicationSerializer(job_application)
        schedules = Schedule.active_objects.filter(
            tenant_id=tenant['id'],
            job_application=job_application
        )
        if request.user.is_authenticated and getattr(request.user, 'role', None) == 'recruiter' and getattr(request.user, 'branch', None):
            schedules = schedules.filter(branch=request.user.branch)
        schedule_serializer = ScheduleSerializer(schedules, many=True)

        response_data = {
            'job_application': job_application_serializer.data,
            'job_requisition': job_requisition,  # Already a dict from API
            'schedules': schedule_serializer.data,
            'schedule_count': schedules.count()
        }

        logger.info(f"Retrieved job application with code {job_application_code} and email {email} for tenant {tenant['id']}")
        return Response(response_data, status=status.HTTP_200_OK)

class JobApplicationsByRequisitionView(generics.ListAPIView):
    serializer_class = JobApplicationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        job_requisition_id = self.kwargs['job_requisition_id']
        tenant_id = self.request.query_params.get('tenant_id')
        queryset = JobApplication.active_objects.filter(job_requisition_id=job_requisition_id)
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        if self.request.user.is_authenticated and getattr(self.request.user, 'branch', None):
            queryset = queryset.filter(branch=self.request.user.branch)
        return queryset.order_by('-created_at')

class PublishedJobRequisitionsWithShortlistedApplicationsView(APIView):
    serializer_class = SimpleMessageSerializer 
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tenant_id = request.query_params.get('tenant_id')
        branch_id = request.query_params.get('branch_id')
        if not tenant_id:
            return Response({"detail": "tenant_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Fetch published job requisitions via API
        resp = requests.get(
            f"{settings.TALENT_ENGINE_URL}/api/job-requisitions/",
            params={'tenant_id': tenant_id, 'publish_status': True},
            headers={'Authorization': request.META.get("HTTP_AUTHORIZATION", "")}
        )
        if resp.status_code != 200:
            return Response({"detail": "Failed to fetch job requisitions."}, status=resp.status_code)
        job_requisitions = resp.json()

        response_data = []
        for job_requisition in job_requisitions:
            job_requisition_id = job_requisition['id']
            applications = JobApplication.active_objects.filter(
                tenant_id=tenant_id,
                job_requisition_id=job_requisition_id,
                status='shortlisted'
            )
            if branch_id:
                applications = applications.filter(branch_id=branch_id)
            application_serializer = JobApplicationSerializer(applications, many=True)

            # Add schedule info for each application
            enhanced_applications = []
            for app_data in application_serializer.data:
                application_id = app_data['id']
                schedules = Schedule.active_objects.filter(
                    tenant_id=tenant_id,
                    job_application_id=application_id
                )
                if branch_id:
                    schedules = schedules.filter(branch_id=branch_id)
                schedule_serializer = ScheduleSerializer(schedules, many=True)
                app_data['scheduled'] = schedules.exists()
                app_data['schedules'] = schedule_serializer.data
                enhanced_applications.append(app_data)

            total_applications = JobApplication.active_objects.filter(
                tenant_id=tenant_id,
                job_requisition_id=job_requisition_id
            )
            if branch_id:
                total_applications = total_applications.filter(branch_id=branch_id)
            total_applications = total_applications.count()

            response_data.append({
                'job_requisition': job_requisition,
                'shortlisted_applications': enhanced_applications,
                'shortlisted_count': applications.count(),
                'total_applications': total_applications
            })

        # Sort by created_at descending if present
        response_data.sort(key=lambda x: x['job_requisition'].get('created_at', ''), reverse=True)
        return Response(response_data, status=status.HTTP_200_OK)

class PublishedPublicJobRequisitionsWithShortlistedApplicationsView(APIView):
    serializer_class = SimpleMessageSerializer 
    permission_classes = [AllowAny]

    def get(self, request):
        schema_name = request.query_params.get("schema_name")
        branch_name = request.query_params.get("branch_name")
        if not schema_name:
            return Response({"detail": "Missing schema_name."}, status=status.HTTP_400_BAD_REQUEST)

        # Fetch tenant via API
        tenant_resp = requests.get(
            f"{settings.AUTH_SERVICE_URL}/api/tenant/tenants/by-schema/{schema_name}/"
        )
        if tenant_resp.status_code != 200:
            return Response({"detail": f"Tenant with schema_name {schema_name} not found."}, status=tenant_resp.status_code)
        tenant = tenant_resp.json()

        # Fetch published job requisitions via API
        params = {'tenant_id': tenant['id'], 'publish_status': True}
        if branch_name:
            params['branch_name'] = branch_name
        resp = requests.get(
            f"{settings.TALENT_ENGINE_URL}/api/job-requisitions/",
            params=params
        )
        if resp.status_code != 200:
            return Response({"detail": "Failed to fetch job requisitions."}, status=resp.status_code)
        job_requisitions = resp.json()

        response_data = []
        for job_requisition in job_requisitions:
            shortlisted_count = JobApplication.active_objects.filter(
                tenant_id=tenant['id'],
                job_requisition_id=job_requisition['id'],
                status='shortlisted'
            ).count()
            tenant_data = {
                "logo_url": tenant.get("logo"),
                "about_us": tenant.get("about_us"),
                "title": tenant.get("title"),
            }
            response_data.append({
                'job_requisition': job_requisition,
                'tenant': tenant_data,
                'shortlisted_count': shortlisted_count,
            })

        return Response(response_data, status=status.HTTP_200_OK)



class TimezoneChoicesView(APIView):
    serializer_class = SimpleMessageSerializer 
    permission_classes = [IsAuthenticated]

    def get(self, request):
        timezone_choices = [
            {"value": value, "label": label} for value, label in Schedule.TIMEZONE_CHOICES
        ]
        return Response(timezone_choices, status=status.HTTP_200_OK)


