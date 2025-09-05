import logging
import os
import uuid
import requests
import time
import tempfile
import mimetypes
from kafka import KafkaProducer
import json
from django.conf import settings
from django.utils import timezone
from django.db import transaction
import concurrent.futures

from .permissions import IsMicroserviceAuthenticated
from rest_framework import generics, status
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
import aiohttp
import asyncio
from .models import JobApplication, Schedule
from .serializers import (
    JobApplicationSerializer, ScheduleSerializer, ComplianceStatusSerializer, SimpleMessageSerializer, PublicJobApplicationSerializer
)
from utils.screen import parse_resume, screen_resume, extract_resume_fields
from .tenant_utils import resolve_tenant_from_unique_link

logger = logging.getLogger('job_applications')



def get_job_requisition_by_id(job_requisition_id, request):
    try:
        response = requests.get(
            f"{settings.TALENT_ENGINE_URL}/api/talent-engine/requisitions/{job_requisition_id}/",
            headers={'Authorization': request.headers.get('Authorization', '')},
            timeout=10
        )
        logger.info(f"Response status: {response.status_code}, content: {response.text}")
        if response.status_code == 200:
            return response.json()
        logger.warning(f"Failed to fetch job requisition {job_requisition_id}: {response.status_code} - {response.text}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching job requisition {job_requisition_id}: {str(e)}")
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

def chunk_list(lst, chunk_size):
    for i in range(0, len(lst), chunk_size):
        yield lst[i:i + chunk_size]

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
            
            logger.info(f"Processing resume file: {resume_file.name}, size: {resume_file.size}")
            
            # Preserve the file extension
            file_extension = os.path.splitext(resume_file.name)[1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
                for chunk in resume_file.chunks():
                    temp_file.write(chunk)
                temp_file_path = temp_file.name
                
            logger.info(f"Temporary resume file saved at: {temp_file_path}")
            
            # Parse resume with timeout
            try:
                resume_text = parse_resume(temp_file_path)
                logger.info(f"Extracted text length: {len(resume_text) if resume_text else 0}")
            except Exception as e:
                logger.error(f"Resume parsing failed: {str(e)}")
                resume_text = ""
            
            os.unlink(temp_file_path)
            
            if not resume_text:
                logger.error(f"Could not extract text from resume. File: {resume_file.name}")
                return Response({"detail": "Could not extract text from resume."}, status=status.HTTP_400_BAD_REQUEST)
                
            # Extract fields with timeout
            try:
                extracted_data = extract_resume_fields(resume_text)
            except Exception as e:
                logger.error(f"Field extraction failed: {str(e)}")
                return Response({"detail": "Failed to extract fields from resume."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
            logger.info(f"Resume parsed successfully for file: {resume_file.name}")
            return Response({
                "detail": "Resume parsed successfully",
                "data": extracted_data
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(f"Error parsing resume: {str(e)} | Request data: {request.data}, FILES: {request.FILES}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class ResumeScreeningView(APIView):
    serializer_class = SimpleMessageSerializer
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def post(self, request, job_requisition_id):
        try:
            jwt_payload = getattr(request, 'jwt_payload', {})
            tenant_id = str(jwt_payload.get('tenant_id')) if jwt_payload.get('tenant_id') is not None else None
            role = jwt_payload.get('role')
            branch = jwt_payload.get('user', {}).get('branch')

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

            # Filter applications by tenant and branch
            if not applications_data:
                applications = JobApplication.active_objects.filter(
                    job_requisition_id=job_requisition_id,
                    tenant_id=tenant_id,
                    resume_status=True
                )
            else:
                application_ids = [app['application_id'] for app in applications_data]
                applications = JobApplication.active_objects.filter(
                    job_requisition_id=job_requisition_id,
                    tenant_id=tenant_id,
                    id__in=application_ids,
                    resume_status=True
                )

            logger.info(f"Screening {applications.count()} applications: {[str(app.id) for app in applications]}")
            if not applications.exists():
                logger.warning("No applications with resume_status=True found for provided IDs and filters.")
                return Response({"detail": "No applications with resumes found.", "documentType": document_type}, status=status.HTTP_400_BAD_REQUEST)

            if role == 'recruiter' and branch:
                applications = applications.filter(branch=branch)
            elif branch:
                applications = applications.filter(branch=branch)

            def download_resume(app, app_data, document_type_lower):
                try:
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
                            return {
                                "app": app,
                                "success": False,
                                "error": f"No {document_type} document found",
                            }
                        file_url = cv_doc['file_url']

                    logger.info(f"About to download file for app {app.id}: {file_url}")
                    start_download = time.time()
                    headers = {"Authorization": f"Bearer {settings.SUPABASE_KEY}"}
                    response = requests.get(file_url, headers=headers, timeout=10)
                    download_time = time.time() - start_download
                    file_size = len(response.content)
                    logger.info(f"Downloaded file for app {app.id} in {download_time:.2f}s, size: {file_size} bytes")
                    if response.status_code != 200:
                        app.screening_status = 'failed'
                        app.screening_score = 0.0
                        app.save()
                        return {
                            "app": app,
                            "success": False,
                            "error": f"Failed to download resume from {file_url}, status code: {response.status_code}",
                        }

                    content_type = response.headers.get('content-type', '')
                    file_ext = mimetypes.guess_extension(content_type) or os.path.splitext(file_url)[1] or '.pdf'
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_ext)
                    temp_file.write(response.content)
                    temp_file.close()
                    temp_file_path = temp_file.name
                    logger.info(f"Finished download for app {app.id}")
                    return {
                        "app": app,
                        "success": True,
                        "temp_file_path": temp_file_path,
                        "file_url": file_url,
                    }
                except Exception as e:
                    logger.error(f"Download failed for app {app.id}: {str(e)}")
                    app.screening_status = 'failed'
                    app.screening_score = 0.0
                    app.save()
                    return {
                        "app": app,
                        "success": False,
                        "error": f"Download error for file: {str(e)}",
                    }

            # Step 1: Parallel download all files
            download_results = []
            applications_list = list(applications)
            applications_data_map = {str(a['application_id']): a for a in applications_data}
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                future_to_app = {
                    executor.submit(
                        download_resume,
                        app,
                        applications_data_map.get(str(app.id)),
                        document_type_lower
                    ): app for app in applications_list
                }
                for future in concurrent.futures.as_completed(future_to_app):
                    result = future.result()
                    download_results.append(result)

            # Step 2: Parallel parse and screen only successfully downloaded files
            job_requirements = (
                (job_requisition.get('job_description') or '') + ' ' +
                (job_requisition.get('qualification_requirement') or '') + ' ' +
                (job_requisition.get('experience_requirement') or '') + ' ' +
                (job_requisition.get('knowledge_requirement') or '')
            ).strip()

            def parse_and_screen(result, job_requirements):
                app = result["app"]
                if not result["success"]:
                    return {
                        "application_id": str(app.id),
                        "full_name": app.full_name,
                        "email": app.email,
                        "error": result["error"],
                        "success": False
                    }
                temp_file_path = result["temp_file_path"]
                file_url = result.get("file_url", "")
                try:
                    logger.info(f"About to parse resume for app {app.id}")
                    start_parse = time.time()
                    resume_text = parse_resume(temp_file_path)
                    parse_time = time.time() - start_parse
                    logger.info(f"Finished parsing resume for app {app.id} in {parse_time:.2f}s")
                    logger.info(f"Extracted text length for app {app.id}: {len(resume_text) if resume_text else 0}")
                    logger.debug(f"Resume text sample for app {app.id}: {resume_text[:200] if resume_text else 'No text'}")
                    if temp_file_path and os.path.exists(temp_file_path):
                        os.unlink(temp_file_path)
                    if not resume_text:
                        app.screening_status = 'failed'
                        app.screening_score = 0.0
                        app.save()
                        return {
                            "application_id": str(app.id),
                            "full_name": app.full_name,
                            "email": app.email,
                            "error": f"Failed to parse resume for file: {file_url}",
                            "success": False
                        }
                    score = screen_resume(resume_text, job_requirements)
                    resume_data = extract_resume_fields(resume_text)
                    employment_gaps = resume_data.get("employment_gaps", [])
                    app.screening_status = 'processed'
                    app.screening_score = score
                    app.employment_gaps = employment_gaps
                    app.save()
                    return {
                        "application_id": str(app.id),
                        "full_name": app.full_name,
                        "email": app.email,
                        "score": score,
                        "screening_status": app.screening_status,
                        "employment_gaps": employment_gaps,
                        "success": True
                    }
                except Exception as e:
                    logger.error(f"Parsing failed for app {app.id}: {str(e)}")
                    app.screening_status = 'failed'
                    app.screening_score = 0.0
                    app.save()
                    if temp_file_path and os.path.exists(temp_file_path):
                        os.unlink(temp_file_path)
                    return {
                        "application_id": str(app.id),
                        "full_name": app.full_name,
                        "email": app.email,
                        "error": f"Screening error for file: {file_url} - {str(e)}",
                        "success": False
                    }

            results = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                future_to_result = {
                    executor.submit(parse_and_screen, result, job_requirements): result for result in download_results
                }
                for future in concurrent.futures.as_completed(future_to_result):
                    results.append(future.result())

            # Separate successful and failed applications
            shortlisted = [r for r in results if r.get("success")]
            failed_applications = [r for r in results if not r.get("success")]

            if not shortlisted and failed_applications:
                return Response({
                    "detail": "All resume screenings failed.",
                    "failed_applications": failed_applications,
                    "document_type": document_type
                }, status=status.HTTP_400_BAD_REQUEST)

            shortlisted.sort(key=lambda x: x['score'], reverse=True)
            final_shortlisted = shortlisted[:num_candidates]
            shortlisted_ids = {item['application_id'] for item in final_shortlisted}

            for app in applications:
                if str(app.id) in shortlisted_ids:
                    app.status = 'shortlisted'
                else:
                    app.status = 'rejected'
                app.save()

            return Response({
                "detail": f"Screened {len(shortlisted)} applications using '{document_type}', shortlisted {len(final_shortlisted)} candidates.",
                "shortlisted_candidates": final_shortlisted,
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


#   class ResumeParseView(APIView):
#     parser_classes = [MultiPartParser, FormParser]
#     permission_classes = [AllowAny]
#     serializer_class = SimpleMessageSerializer

#     def post(self, request):
#         logger.info(f"Incoming request content-type: {request.content_type}")
#         logger.info(f"Request FILES keys: {list(request.FILES.keys())}")
#         logger.info(f"Request DATA keys: {list(request.data.keys())}")

#         try:
#             resume_file = request.FILES.get('resume')
#             if not resume_file:
#                 logger.error(f"No resume file found. Available files: {list(request.FILES.keys())}")
#                 return Response({"detail": "Resume file is required."}, status=status.HTTP_400_BAD_REQUEST)
        
#             logger.info(f"Processing resume file: {resume_file.name}, size: {resume_file.size}")
        
#             # Preserve the file extension
#             file_extension = os.path.splitext(resume_file.name)[1]
#             with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
#                 for chunk in resume_file.chunks():
#                     temp_file.write(chunk)
#                 temp_file_path = temp_file.name
            
#             logger.info(f"Temporary resume file saved at: {temp_file_path}")
        
#             # Parse resume with timeout
#             try:
#                 resume_text = parse_resume(temp_file_path)
#                 logger.info(f"Extracted text length: {len(resume_text) if resume_text else 0}")
#             except Exception as e:
#                 logger.error(f"Resume parsing failed: {str(e)}")
#                 resume_text = ""
        
#             os.unlink(temp_file_path)
        
#             if not resume_text:
#                 logger.error(f"Could not extract text from resume. File: {resume_file.name}")
#                 return Response({"detail": "Could not extract text from resume."}, status=status.HTTP_400_BAD_REQUEST)
            
#             # Extract fields with timeout
#             try:
#                 extracted_data = extract_resume_fields(resume_text)
#             except Exception as e:
#                 logger.error(f"Field extraction failed: {str(e)}")
#                 return Response({"detail": "Failed to extract fields from resume."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
#             logger.info(f"Resume parsed successfully for file: {resume_file.name}")
#             return Response({
#                 "detail": "Resume parsed successfully",
#                 "data": extracted_data
#             }, status=status.HTTP_200_OK)
#         except Exception as e:
#             logger.exception(f"Error parsing resume: {str(e)} | Request data: {request.data}, FILES: {request.FILES}")
#             return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


        
class JobApplicationCreatePublicView(generics.CreateAPIView):
    serializer_class = PublicJobApplicationSerializer
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def create(self, request, *args, **kwargs):
        unique_link = request.data.get('unique_link') or request.data.get('job_requisition_unique_link')
        if not unique_link:
            return Response({"detail": "Missing job requisition unique link."}, status=status.HTTP_400_BAD_REQUEST)

        tenant_id = unique_link.split('-')[0]
        requisition_url = f"{settings.TALENT_ENGINE_URL}/api/talent-engine/requisitions/unique_link/{unique_link}/"
        resp = requests.get(requisition_url)
        logger.info(f"Requisition unique_link: {unique_link}, API status: {resp.status_code}")
        if resp.status_code != 200:
            try:
                error_detail = resp.json().get('detail', 'Invalid job requisition.')
            except Exception:
                error_detail = 'Invalid job requisition.'
            return Response({"detail": error_detail}, status=status.HTTP_400_BAD_REQUEST)
        job_requisition = resp.json()

        payload = dict(request.data.items())
        payload['job_requisition_id'] = job_requisition['id']
        payload['tenant_id'] = tenant_id

        documents = []
        i = 0
        while f'documents[{i}][document_type]' in request.data and f'documents[{i}][file]' in request.FILES:
            documents.append({
                'document_type': request.data.get(f'documents[{i}][document_type]'),
                'file': request.FILES.get(f'documents[{i}][file]')
            })
            i += 1
        if documents:
            payload['documents'] = documents

        logger.info(f"Full POST request payload (dict): {payload}")

        serializer = self.get_serializer(data=payload, context={'request': request, 'job_requisition': job_requisition})
        if not serializer.is_valid():
            logger.error(f"Validation errors: {serializer.errors}")
            return Response({"detail": "Validation error", "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        self.perform_create(serializer)

        # Publish to Kafka
        try:
            producer = KafkaProducer(
                bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            kafka_data = {
                "tenant_id": tenant_id,
                "job_requisition_id": job_requisition['id'],
                "event": "job_application_created"
            }
            producer.send('job_application_events', kafka_data)
            producer.flush()
            logger.info(f"Published job application event to Kafka for requisition {job_requisition['id']}")
        except Exception as e:
            logger.error(f"Failed to publish Kafka event: {str(e)}")

        return Response(serializer.data, status=status.HTTP_201_CREATED)

class JobApplicationListCreateView(generics.ListCreateAPIView):
    serializer_class = JobApplicationSerializer
    parser_classes = (MultiPartParser, FormParser)

    def get_permissions(self):
        if self.request.method == 'POST':
            return [AllowAny()]
        return [AllowAny()]  # Temporary for testing

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

  

class JobApplicationDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = JobApplicationSerializer
    parser_classes = (MultiPartParser, FormParser, JSONParser)  # <-- Add JSONParser here
    lookup_field = 'id'

    def get_queryset(self):
        jwt_payload = getattr(self.request, 'jwt_payload', {})
        tenant_id = str(jwt_payload.get('tenant_id')) if jwt_payload.get('tenant_id') is not None else None
        role = jwt_payload.get('role')
        branch = jwt_payload.get('user', {}).get('branch')
        queryset = JobApplication.active_objects.all()
        if not tenant_id:
            logger.error("No tenant_id in token")
            return JobApplication.active_objects.none()
        queryset = queryset.filter(tenant_id=tenant_id)
        if role == 'recruiter' and branch:
            queryset = queryset.filter(branch=branch)
        elif branch:
            queryset = queryset.filter(branch=branch)
        return queryset.order_by('-created_at')

    def retrieve(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            return Response(self.get_serializer(instance).data)
        except Exception as e:
            logger.exception(f"Error retrieving job application: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def update(self, request, *args, **kwargs):
        try:
            partial = kwargs.pop('partial', False)
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
            return Response(serializer.data)
        except Exception as e:
            logger.exception(f"Error updating job application: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            self.perform_destroy(instance)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            logger.exception(f"Error deleting job application: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class JobApplicationBulkDeleteView(APIView):
    # permission_classes = [IsAuthenticated]
    serializer_class = SimpleMessageSerializer

    def post(self, request):
        ids = request.data.get('ids', [])
        if not ids:
            return Response({"detail": "No IDs provided."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            jwt_payload = getattr(request, 'jwt_payload', {})
            tenant_id = jwt_payload.get('tenant_id')
            role = jwt_payload.get('role')
            branch = jwt_payload.get('branch')
            if not tenant_id:
                return Response({"detail": "No tenant_id in token."}, status=status.HTTP_401_UNAUTHORIZED)
            queryset = JobApplication.active_objects.filter(tenant_id=tenant_id, id__in=ids)
            if role == 'recruiter' and branch:
                queryset = queryset.filter(branch=branch)
            applications = list(queryset)
            count = len(applications)
            if count == 0:
                return Response({"detail": "No applications found."}, status=status.HTTP_404_NOT_FOUND)
            with transaction.atomic():
                for application in applications:
                    application.soft_delete()
            return Response({"detail": f"Soft-deleted {count} application(s)."}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Bulk soft delete failed: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    # permission_classes = [IsAuthenticated]
    def get_permissions(self):
        return [AllowAny()]  # Temporary for testing

    def get_queryset(self):
        jwt_payload = getattr(self.request, 'jwt_payload', {})
        tenant_id = str(jwt_payload.get('tenant_id')) if jwt_payload.get('tenant_id') is not None else None
        role = jwt_payload.get('role')
        branch = jwt_payload.get('user', {}).get('branch')
        job_requisition_id = self.kwargs['job_requisition_id']
        queryset = JobApplication.active_objects.filter(job_requisition_id=job_requisition_id)
        if not tenant_id:
            logger.error("No tenant_id in token")
            return JobApplication.active_objects.none()
        queryset = queryset.filter(tenant_id=tenant_id)
        if role == 'recruiter' and branch:
            queryset = queryset.filter(branch=branch)
        elif branch:
            queryset = queryset.filter(branch=branch)
        return queryset.order_by('-created_at')





class PublishedJobRequisitionsWithShortlistedApplicationsView(APIView):
    serializer_class = SimpleMessageSerializer 
    permission_classes = [IsAuthenticated]

    def get(self, request):
        jwt_payload = getattr(request, 'jwt_payload', {})
        tenant_id = str(jwt_payload.get('tenant_id')) if jwt_payload.get('tenant_id') is not None else None
        role = jwt_payload.get('role')
        branch = jwt_payload.get('user', {}).get('branch')
        if not tenant_id:
            return Response({"detail": "tenant_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Fetch published job requisitions via API
        resp = requests.get(
            f"{settings.TALENT_ENGINE_URL}/api/talent-engine/requisitions/",
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
            if role == 'recruiter' and branch:
                applications = applications.filter(branch=branch)
            elif branch:
                applications = applications.filter(branch=branch)
            application_serializer = JobApplicationSerializer(applications, many=True)

            # Add schedule info for each application
            enhanced_applications = []
            for app_data in application_serializer.data:
                application_id = app_data['id']
                schedules = Schedule.active_objects.filter(
                    tenant_id=tenant_id,
                    job_application_id=application_id
                )
                if role == 'recruiter' and branch:
                    schedules = schedules.filter(branch=branch)
                elif branch:
                    schedules = schedules.filter(branch=branch)
                schedule_serializer = ScheduleSerializer(schedules, many=True)
                app_data['scheduled'] = schedules.exists()
                app_data['schedules'] = schedule_serializer.data
                enhanced_applications.append(app_data)

            total_applications = JobApplication.active_objects.filter(
                tenant_id=tenant_id,
                job_requisition_id=job_requisition_id
            )
            if role == 'recruiter' and branch:
                total_applications = total_applications.filter(branch=branch)
            elif branch:
                total_applications = total_applications.filter(branch=branch)
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
        jwt_payload = getattr(request, 'jwt_payload', {})
        tenant_id = str(jwt_payload.get('tenant_id')) if jwt_payload.get('tenant_id') is not None else None
        role = jwt_payload.get('role')
        branch = jwt_payload.get('user', {}).get('branch')
        if not tenant_id:
            return Response({"detail": "Missing tenant_id in token."}, status=status.HTTP_400_BAD_REQUEST)

        # Fetch tenant via API
        tenant_resp = requests.get(
            f"{settings.AUTH_SERVICE_URL}/api/tenant/tenants/{tenant_id}/",
            headers={'Authorization': request.META.get("HTTP_AUTHORIZATION", "")}
        )
        if tenant_resp.status_code != 200:
            return Response({"detail": f"Tenant with id {tenant_id} not found."}, status=tenant_resp.status_code)
        tenant = tenant_resp.json()

        # Fetch published job requisitions via API
        params = {'tenant_id': tenant_id, 'publish_status': True}
        if branch:
            params['branch_name'] = branch
        resp = requests.get(
            f"{settings.TALENT_ENGINE_URL}/api/talent-engine/requisitions/",
            params=params,
            headers={'Authorization': request.META.get("HTTP_AUTHORIZATION", "")}
        )
        if resp.status_code != 200:
            return Response({"detail": "Failed to fetch job requisitions."}, status=resp.status_code)
        job_requisitions = resp.json()

        response_data = []
        for job_requisition in job_requisitions:
            applications = JobApplication.active_objects.filter(
                tenant_id=tenant_id,
                job_requisition_id=job_requisition['id'],
                status='shortlisted'
            )
            if role == 'recruiter' and branch:
                applications = applications.filter(branch=branch)
            elif branch:
                applications = applications.filter(branch=branch)
            shortlisted_count = applications.count()
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




class SoftDeletedJobApplicationsView(generics.ListAPIView):
    serializer_class = JobApplicationSerializer
    # permission_classes = [IsAuthenticated]

    def get_queryset(self):
        jwt_payload = getattr(self.request, 'jwt_payload', {})
        tenant_id = str(jwt_payload.get('tenant_id')) if jwt_payload.get('tenant_id') is not None else None
        role = jwt_payload.get('role')
        branch = jwt_payload.get('user', {}).get('branch')
        queryset = JobApplication.objects.filter(is_deleted=True)
        if not tenant_id:
            logger.error("No tenant_id in token")
            return JobApplication.objects.none()
        queryset = queryset.filter(tenant_id=tenant_id)
        if role == 'recruiter' and branch:
            queryset = queryset.filter(branch=branch)
        elif branch:
            queryset = queryset.filter(branch=branch)
        return queryset.order_by('-created_at')


class RecoverSoftDeletedJobApplicationsView(APIView):
    serializer_class = SimpleMessageSerializer 
    def get_permissions(self):
        return [AllowAny()]  # Temporary for testing

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
    def get_permissions(self):
        return [AllowAny()]  # Temporary for testing

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
    # permission_classes = [IsAuthenticated]
    def get_permissions(self):
        return [AllowAny()]  # Temporary for testing


    def get_queryset(self):
        jwt_payload = getattr(self.request, 'jwt_payload', {})
        tenant_id = str(jwt_payload.get('tenant_id')) if jwt_payload.get('tenant_id') is not None else None
        role = jwt_payload.get('role')
        branch = jwt_payload.get('user', {}).get('branch')
        queryset = Schedule.active_objects.all()
        if not tenant_id:
            logger.error("No tenant_id in token")
            return Schedule.active_objects.none()
        queryset = queryset.filter(tenant_id=tenant_id)
        if role == 'recruiter' and branch:
            queryset = queryset.filter(branch=branch)
        elif branch:
            queryset = queryset.filter(branch=branch)
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
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    # permission_classes = [IsAuthenticated]
    lookup_field = 'id'
    def get_permissions(self):
        return [AllowAny()]  # Temporary for testing

    def get_queryset(self):
        jwt_payload = getattr(self.request, 'jwt_payload', {})
        tenant_id = str(jwt_payload.get('tenant_id')) if jwt_payload.get('tenant_id') is not None else None
        role = jwt_payload.get('role')
        branch = jwt_payload.get('user', {}).get('branch')
        queryset = Schedule.active_objects.all()
        if not tenant_id:
            logger.error("No tenant_id in token")
            return Schedule.active_objects.none()
        queryset = queryset.filter(tenant_id=tenant_id)
        if role == 'recruiter' and branch:
            queryset = queryset.filter(branch=branch)
        elif branch:
            queryset = queryset.filter(branch=branch)
        return queryset.order_by('-created_at')

    def retrieve(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            return Response(self.get_serializer(instance).data)
        except Exception as e:
            logger.exception(f"Error retrieving schedule: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def update(self, request, *args, **kwargs):
        try:
            partial = kwargs.pop('partial', False)
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
            return Response(serializer.data)
        except Exception as e:
            logger.exception(f"Error updating schedule: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            self.perform_destroy(instance)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            logger.exception(f"Error deleting schedule: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class ScheduleBulkDeleteView(APIView):
    serializer_class = SimpleMessageSerializer 
    # permission_classes = [IsAuthenticated]
    def get_permissions(self):
        return [AllowAny()]  # Temporary for testing


    def post(self, request):
        jwt_payload = getattr(request, 'jwt_payload', {})
        tenant_id = str(jwt_payload.get('tenant_id')) if jwt_payload.get('tenant_id') is not None else None
        role = jwt_payload.get('role')
        branch = jwt_payload.get('user', {}).get('branch')
        ids = request.data.get('ids', [])
        if not ids:
            return Response({"detail": "No schedule IDs provided."}, status=status.HTTP_400_BAD_REQUEST)
        schedules = Schedule.active_objects.filter(id__in=ids)
        if not tenant_id:
            return Response({"detail": "No tenant_id in token."}, status=status.HTTP_400_BAD_REQUEST)
        schedules = schedules.filter(tenant_id=tenant_id)
        if role == 'recruiter' and branch:
            schedules = schedules.filter(branch=branch)
        elif branch:
            schedules = schedules.filter(branch=branch)
        if not schedules.exists():
            return Response({"detail": "No schedules found."}, status=status.HTTP_404_NOT_FOUND)
        with transaction.atomic():
            for schedule in schedules:
                schedule.soft_delete()
        return Response({"detail": f"Successfully soft-deleted {schedules.count()} schedule(s)."}, status=status.HTTP_200_OK)



class SoftDeletedSchedulesView(generics.ListAPIView):
    serializer_class = ScheduleSerializer
    # permission_classes = [IsAuthenticated]
    def get_permissions(self):
        return [AllowAny()]  # Temporary for testing
    
    def get_queryset(self):
        jwt_payload = getattr(self.request, 'jwt_payload', {})
        tenant_id = str(jwt_payload.get('tenant_id')) if jwt_payload.get('tenant_id') is not None else None
        role = jwt_payload.get('role')
        branch = jwt_payload.get('user', {}).get('branch')
        queryset = Schedule.objects.filter(is_deleted=True)
        if not tenant_id:
            return Schedule.objects.none()
        queryset = queryset.filter(tenant_id=tenant_id)
        if role == 'recruiter' and branch:
            queryset = queryset.filter(branch=branch)
        elif branch:
            queryset = queryset.filter(branch=branch)
        return queryset.order_by('-created_at')

class RecoverSoftDeletedSchedulesView(APIView):
    serializer_class = SimpleMessageSerializer 
    # permission_classes = [IsAuthenticated]
    def get_permissions(self):
        return [AllowAny()]  # Temporary for testing
    
    def post(self, request):
        jwt_payload = getattr(request, 'jwt_payload', {})
        tenant_id = str(jwt_payload.get('tenant_id')) if jwt_payload.get('tenant_id') is not None else None
        role = jwt_payload.get('role')
        branch = jwt_payload.get('user', {}).get('branch')
        ids = request.data.get('ids', [])
        if not ids:
            return Response({"detail": "No schedule IDs provided."}, status=status.HTTP_400_BAD_REQUEST)
        schedules = Schedule.objects.filter(id__in=ids, is_deleted=True)
        if not tenant_id:
            return Response({"detail": "No tenant_id in token."}, status=status.HTTP_400_BAD_REQUEST)
        schedules = schedules.filter(tenant_id=tenant_id)
        if role == 'recruiter' and branch:
            schedules = schedules.filter(branch=branch)
        elif branch:
            schedules = schedules.filter(branch=branch)
        if not schedules.exists():
            return Response({"detail": "No soft-deleted schedules found."}, status=status.HTTP_404_NOT_FOUND)
        with transaction.atomic():
            for schedule in schedules:
                schedule.restore()
        return Response({"detail": f"Successfully recovered {schedules.count()} schedule(s)."}, status=status.HTTP_200_OK)

class PermanentDeleteSchedulesView(APIView):
    serializer_class = SimpleMessageSerializer 

    def get_permissions(self):
        return [AllowAny()]  # Temporary for testing

    def post(self, request):
        jwt_payload = getattr(request, 'jwt_payload', {})
        tenant_id = str(jwt_payload.get('tenant_id')) if jwt_payload.get('tenant_id') is not None else None
        role = jwt_payload.get('role')
        branch = jwt_payload.get('user', {}).get('branch')
        ids = request.data.get('ids', [])
        if not ids:
            return Response({"detail": "No schedule IDs provided."}, status=status.HTTP_400_BAD_REQUEST)
        schedules = Schedule.objects.filter(id__in=ids, is_deleted=True)
        if not tenant_id:
            return Response({"detail": "No tenant_id in token."}, status=status.HTTP_400_BAD_REQUEST)
        schedules = schedules.filter(tenant_id=tenant_id)
        if role == 'recruiter' and branch:
            schedules = schedules.filter(branch=branch)
        elif branch:
            schedules = schedules.filter(branch=branch)
        if not schedules.exists():
            return Response({"detail": "No soft-deleted schedules found."}, status=status.HTTP_404_NOT_FOUND)
        deleted_count = schedules.delete()[0]
        return Response({"detail": f"Successfully permanently deleted {deleted_count} schedule(s)."}, status=status.HTTP_200_OK)

class ComplianceStatusUpdateView(APIView):
    serializer_class = ComplianceStatusSerializer
    # permission_classes = [IsAuthenticated]
    def get_permissions(self):
        return [AllowAny()]  # Temporary for testing
    
    def post(self, request, application_id, item_id):
        jwt_payload = getattr(request, 'jwt_payload', {})
        role = jwt_payload.get('role')
        branch = jwt_payload.get('user', {}).get('branch')
        try:
            application = JobApplication.active_objects.get(id=application_id)
        except JobApplication.DoesNotExist:
            return Response({"detail": "Job application not found."}, status=status.HTTP_404_NOT_FOUND)
        if branch and application.branch != branch:
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
    def get_permissions(self):
        return [AllowAny()]  # Temporary for testing

    def put(self, request, job_application_id):
        jwt_payload = getattr(request, 'jwt_payload', {})
        role = jwt_payload.get('role')
        branch = jwt_payload.get('user', {}).get('branch')
        try:
            application = JobApplication.active_objects.get(id=job_application_id)
        except JobApplication.DoesNotExist:
            return Response({"detail": "Job application not found."}, status=status.HTTP_404_NOT_FOUND)
        if branch and application.branch != branch:
            return Response({"detail": "Not authorized to access this application."}, status=status.HTTP_403_FORBIDDEN)
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