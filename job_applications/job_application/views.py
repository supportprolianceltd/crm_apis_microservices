# Standard Library
import concurrent.futures
import gzip
import io
import json
import logging
import mimetypes
import os
import re
import tempfile
import time
import uuid
import zipfile
from urllib import request

# Django
from django.conf import settings
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.paginator import Paginator
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

# Celery
from celery.result import AsyncResult

# Kafka
from kafka import KafkaProducer

# Third-Party
import requests

# Django REST Framework
from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from concurrent.futures import ThreadPoolExecutor

# Project Models
from job_application.models import JobApplication, Schedule
from job_application.tasks import process_large_resume_batch
from .tasks import (
    aggregate_screening_results,
    process_large_resume_batch,
    process_resume_chunk
)
# Project Serializers
from .serializers import (
    ComplianceStatusSerializer,
    JobApplicationSerializer,
    PublicJobApplicationSerializer,
    ScheduleSerializer,
    SimpleMessageSerializer,
    get_user_data_from_jwt
)
# Project Utils
from utils.screen import (
    extract_resume_fields,
    parse_resume,
    screen_resume
)
from utils.email_utils import send_screening_notification
from utils.supabase import upload_file_dynamic
from django.http import JsonResponse
from django.views import View
from datetime import datetime


# Logger
logger = logging.getLogger('job_applications')


def get_job_requisition_by_id(job_requisition_id, request):
    try:
        response = requests.get(
            f"{settings.TALENT_ENGINE_URL}/api/talent-engine/requisitions/{job_requisition_id}/",
            headers={'Authorization': request.headers.get('Authorization', '')},
            timeout=10
        )
        if response.status_code == 200:
            return response.json()
        logger.warning(f"Failed to fetch job requisition {job_requisition_id}: {response.status_code}")
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



class HealthCheckView(View):
    def get(self, request):
        health_data = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "service": "job-applications",
            "version": "1.0.0"
        }
        return JsonResponse(health_data)


class CustomPagination(PageNumberPagination):
    page_size = 20

class ResumeParseView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [AllowAny]
    serializer_class = SimpleMessageSerializer

    def post(self, request):
        # logger.info(f"Incoming request content-type: {request.content_type}")
        # logger.info(f"Request FILES keys: {list(request.FILES.keys())}")
        # logger.info(f"Request DATA keys: {list(request.data.keys())}")

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
                extracted_data = extract_resume_fields(resume_text, resume_file.name)
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

# class ResumeScreeningView(APIView):
#     serializer_class = SimpleMessageSerializer
#     parser_classes = [JSONParser, MultiPartParser, FormParser]

#     # Constants
#     MAX_FILE_SIZE = 50 * 1024 * 1024
#     MAX_SYNC_PROCESSING = 50
#     MAX_WORKERS = 10

#     def post(self, request, job_requisition_id):
#         try:
#             jwt_payload = getattr(request, 'jwt_payload', {})
#             tenant_id = jwt_payload.get('tenant_unique_id')
#             role = jwt_payload.get('role')
#             branch = jwt_payload.get('user', {}).get('branch')

#             document_type = request.data.get('document_type')
#             applications_data = request.data.get('applications', [])
#             num_candidates = request.data.get('number_of_candidates', 0)
            
#             try:
#                 num_candidates = int(num_candidates)
#             except (TypeError, ValueError):
#                 num_candidates = 0

#             job_requisition = get_job_requisition_by_id(job_requisition_id, request)
#             if not job_requisition:
#                 return Response({"detail": "Job requisition not found."}, status=status.HTTP_404_NOT_FOUND)

#             if not document_type:
#                 return Response({"detail": "Document type is required."}, status=status.HTTP_400_BAD_REQUEST)

#             document_type_lower = document_type.lower()
#             allowed_docs = [doc.lower() for doc in (job_requisition.get('documents_required') or [])]
#             allowed_docs.extend(['resume', 'curriculum vitae (cv)', 'cv'])
#             if document_type_lower not in allowed_docs:
#                 return Response({"detail": f"Invalid document type: {document_type}"}, status=status.HTTP_400_BAD_REQUEST)

#             # Fetch all applications if none provided
#             if not applications_data:
#                 applications = JobApplication.active_objects.filter(
#                     job_requisition_id=job_requisition_id,
#                     tenant_id=tenant_id,
#                     resume_status=True
#                 )
#                 paginator = Paginator(applications, 20)
#                 applications_data = []
#                 for page_num in paginator.page_range:
#                     page = paginator.page(page_num)
#                     applications_data.extend([{"application_id": str(app.id)} for app in page])
#                 logger.info(f"Fetched {len(applications_data)} applications from database")

#             logger.info(f"Screening {len(applications_data)} applications")

#             # Process synchronously for small batches, asynchronously for large
#             if len(applications_data) <= self.MAX_SYNC_PROCESSING:
#                 return self._process_synchronously(
#                     request, job_requisition_id, job_requisition, tenant_id, 
#                     role, branch, document_type, applications_data, num_candidates
#                 )
            
#             task = process_large_resume_batch.delay(
#                 job_requisition_id=job_requisition_id,
#                 tenant_id=tenant_id,
#                 document_type=document_type,
#                 applications_data=applications_data,
#                 num_candidates=num_candidates,
#                 role=role,
#                 branch=branch,
#                 authorization_header=request.META.get('HTTP_AUTHORIZATION', '')
#             )
            
#             return Response({
#                 "detail": f"Started processing {len(applications_data)} applications asynchronously",
#                 "task_id": task.id,
#                 "status_endpoint": f"{settings.JOB_APPLICATIONS_URL}/api/applications-engine/applications/requisitions/screening/task-status/{task.id}/",
#             }, status=status.HTTP_202_ACCEPTED)

#         except Exception as e:
#             logger.exception(f"Error initiating resume screening: {str(e)}")
#             return Response({
#                 "error": "Failed to initiate screening",
#                 "details": str(e)
#             }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#     def _process_synchronously(self, request, job_requisition_id, job_requisition, tenant_id, 
#                              role, branch, document_type, applications_data, num_candidates):
#         try:
#             document_type_lower = document_type.lower()
            
#             # Filter applications
#             if not applications_data:
#                 applications = JobApplication.active_objects.filter(
#                     job_requisition_id=job_requisition_id,
#                     tenant_id=tenant_id,
#                     resume_status=True
#                 )
#             else:
#                 application_ids = [app['application_id'] for app in applications_data]
#                 applications = JobApplication.active_objects.filter(
#                     job_requisition_id=job_requisition_id,
#                     tenant_id=tenant_id,
#                     id__in=application_ids,
#                     resume_status=True
#                 )

#             if role == 'recruiter' and branch:
#                 applications = applications.filter(branch=branch)
#             elif branch:
#                 applications = applications.filter(branch=branch)

#             applications_list = list(applications)
#             applications_data_map = {str(a['application_id']): a for a in applications_data}

#             # Download resumes
#             download_results = []
#             with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
#                 future_to_app = {
#                     executor.submit(
#                         self._download_resume,
#                         app,
#                         applications_data_map.get(str(app.id)),
#                         document_type_lower
#                     ): app for app in applications_list
#                 }
#                 for future in concurrent.futures.as_completed(future_to_app):
#                     download_results.append(future.result())

#             # Process screening
#             job_requirements = self._get_job_requirements(job_requisition)
#             results = []
            
#             with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
#                 future_to_result = {
#                     executor.submit(
#                         self._parse_and_screen,
#                         result, 
#                         job_requirements,
#                         document_type
#                     ): result for result in download_results
#                 }
#                 for future in concurrent.futures.as_completed(future_to_result):
#                     results.append(future.result())

#             # Process results and send emails
#             final_response = self._process_screening_results(
#                 results, applications_list, job_requisition, num_candidates, tenant_id
#             )
            
#             return Response(final_response, status=status.HTTP_200_OK)

#         except Exception as e:
#             logger.exception(f"Synchronous processing failed: {str(e)}")
#             return Response({
#                 "error": "Synchronous processing failed",
#                 "details": str(e)
#             }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#     def _download_resume(self, app, app_data, document_type_lower):
#         try:
#             if app_data and 'file_url' in app_data:
#                 file_url = app_data['file_url']
#                 compression = app_data.get('compression')
#                 original_name = app_data.get('original_name', 'resume.pdf')
#             else:
#                 cv_doc = next(
#                     (doc for doc in app.documents if doc['document_type'].lower() == document_type_lower),
#                     None
#                 )
#                 if not cv_doc:
#                     app.screening_status = 'failed'
#                     app.screening_score = 0.0
#                     app.save()
#                     return {
#                         "app": app,
#                         "success": False,
#                         "error": f"No {document_type_lower} document found",
#                     }
#                 file_url = cv_doc['file_url']
#                 compression = cv_doc.get('compression')
#                 original_name = cv_doc.get('original_name', 'resume.pdf')

#             headers = {"Authorization": f"Bearer {settings.SUPABASE_KEY}"}
#             response = requests.get(file_url, headers=headers, timeout=30, stream=True)
#             logger.info(f"Download response for app {app.id}: status={response.status_code}")
            
#             if response.status_code != 200:
#                 app.screening_status = 'failed'
#                 app.screening_score = 0.0
#                 app.save()
#                 return {
#                     "app": app,
#                     "success": False,
#                     "error": f"Failed to download resume, status: {response.status_code}",
#                 }

#             file_content = response.content
#             content_type = response.headers.get('content-type', '')
            
#             # Check file size
#             if len(file_content) > self.MAX_FILE_SIZE:
#                 logger.error(f"File too large for app {app.id}: {len(file_content)} bytes")
#                 app.screening_status = 'failed'
#                 app.screening_score = 0.0
#                 app.save()
#                 return {
#                     "app": app,
#                     "success": False,
#                     "error": f"File too large ({len(file_content)} bytes)",
#                 }

#             # Enhanced compression handling
#             file_content = self._handle_compression(file_content, compression, file_url, original_name, app.id)
#             if file_content is None:
#                 app.screening_status = 'failed'
#                 app.screening_score = 0.0
#                 app.save()
#                 return {
#                     "app": app,
#                     "success": False,
#                     "error": "Failed to decompress file",
#                 }

#             file_ext = mimetypes.guess_extension(content_type) or '.pdf'
#             temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_ext)
#             temp_file.write(file_content)
#             temp_file.close()
            
#             return {
#                 "app": app,
#                 "success": True,
#                 "temp_file_path": temp_file.name,
#                 "file_url": file_url,
#                 "original_name": original_name
#             }
            
#         except Exception as e:
#             logger.error(f"Download failed for app {app.id}: {str(e)}")
#             app.screening_status = 'failed'
#             app.screening_score = 0.0
#             app.save()
#             return {
#                 "app": app,
#                 "success": False,
#                 "error": f"Download error: {str(e)}",
#             }

#     def _handle_compression(self, file_content, compression, file_url, original_name, app_id):
#         """Handle various compression formats"""
#         try:
#             # Detect compression from magic numbers if not explicitly provided
#             if not compression:
#                 compression = self._detect_compression_format(file_content)
            
#             # GZIP compression
#             if compression == 'gzip' or file_url.endswith('.gz'):
#                 try:
#                     decompressed = gzip.decompress(file_content)
#                     logger.info(f"Successfully decompressed GZIP file for app {app_id}")
#                     return decompressed
#                 except Exception as e:
#                     logger.warning(f"GZIP decompression failed for app {app_id}: {str(e)}")
#                     # Try to detect if it's actually compressed
#                     if file_content[:2] == b'\x1f\x8b':  # GZIP magic number
#                         raise Exception("File appears to be GZIP but decompression failed")
#                     # Otherwise, assume it's not actually compressed
#                     return file_content
            
#             # ZIP compression
#             elif compression == 'zip' or file_url.endswith('.zip'):
#                 try:
#                     with zipfile.ZipFile(io.BytesIO(file_content)) as zip_file:
#                         # Try to find a resume file in the zip
#                         resume_files = []
#                         for name in zip_file.namelist():
#                             if any(ext in name.lower() for ext in ['.pdf', '.doc', '.docx', '.txt', '.rtf']):
#                                 resume_files.append(name)
                        
#                         if resume_files:
#                             # Prefer PDF files, then Word, then others
#                             for preferred_ext in ['.pdf', '.docx', '.doc', '.txt', '.rtf']:
#                                 for name in resume_files:
#                                     if name.lower().endswith(preferred_ext):
#                                         with zip_file.open(name) as f:
#                                             content = f.read()
#                                             logger.info(f"Extracted {name} from ZIP for app {app_id}")
#                                             return content
                            
#                             # Fallback to first resume file
#                             with zip_file.open(resume_files[0]) as f:
#                                 content = f.read()
#                                 logger.info(f"Extracted first resume file {resume_files[0]} from ZIP for app {app_id}")
#                                 return content
#                         else:
#                             # If no obvious resume file found, use the first file
#                             if zip_file.namelist():
#                                 with zip_file.open(zip_file.namelist()[0]) as f:
#                                     content = f.read()
#                                     logger.info(f"Extracted first file {zip_file.namelist()[0]} from ZIP for app {app_id}")
#                                     return content
#                             else:
#                                 raise Exception("ZIP file is empty")
#                 except Exception as e:
#                     logger.error(f"ZIP decompression failed for app {app_id}: {str(e)}")
#                     return None
            
#             # BZIP2 compression
#             elif compression == 'bzip2' or (file_content[:3] == b'BZh'):
#                 try:
#                     import bz2
#                     decompressed = bz2.decompress(file_content)
#                     logger.info(f"Successfully decompressed BZIP2 file for app {app_id}")
#                     return decompressed
#                 except Exception as e:
#                     logger.error(f"BZIP2 decompression failed for app {app_id}: {str(e)}")
#                     return None
            
#             # No compression or unknown format
#             else:
#                 return file_content
                
#         except Exception as e:
#             logger.error(f"Compression handling failed for app {app_id}: {str(e)}")
#             return None

#     def _detect_compression_format(self, file_content):
#         """Detect compression format from magic numbers"""
#         if len(file_content) < 4:
#             return None
            
#         magic_numbers = {
#             b'\x1f\x8b': 'gzip',
#             b'PK\x03\x04': 'zip',
#             b'BZh': 'bzip2',
#             b'\xfd7zXZ': 'xz',
#             b'\x50\x4b\x03\x04': 'zip',  # Another ZIP signature
#             b'\x50\x4b\x05\x06': 'zip',  # Empty ZIP
#             b'\x50\x4b\x07\x08': 'zip',  # Spanned ZIP
#         }
        
#         for magic, format_name in magic_numbers.items():
#             if file_content.startswith(magic):
#                 return format_name
        
#         return None

#     def _get_job_requirements(self, job_requisition):
#         return (
#             (job_requisition.get('job_description') or '') + ' ' +
#             (job_requisition.get('qualification_requirement') or '') + ' ' +
#             (job_requisition.get('experience_requirement') or '') + ' ' +
#             (job_requisition.get('knowledge_requirement') or '')
#         ).strip()

#     def _parse_and_screen(self, result, job_requirements, document_type):
#         app = result["app"]
#         if not result["success"]:
#             # Enhanced error reporting for compression issues
#             error_msg = result["error"]
#             if any(term in error_msg.lower() for term in ['compress', 'decompress', 'gzip', 'zip']):
#                 error_msg = f"Compression error: {error_msg}"
                
#             return {
#                 "application_id": str(app.id),
#                 "full_name": app.full_name,
#                 "email": app.email,
#                 "error": error_msg,
#                 "success": False
#             }

#         temp_file_path = result["temp_file_path"]
#         original_name = result.get("original_name", "")
#         try:
#             resume_text = parse_resume(temp_file_path)
            
#             if temp_file_path and os.path.exists(temp_file_path):
#                 os.unlink(temp_file_path)
                
#             if not resume_text:
#                 app.screening_status = 'failed'
#                 app.screening_score = 0.0
#                 app.save()
#                 return {
#                     "application_id": str(app.id),
#                     "full_name": app.full_name,
#                     "email": app.email,
#                     "error": f"Failed to parse resume",
#                     "success": False
#                 }

#             score = screen_resume(resume_text, job_requirements)
#             resume_data = extract_resume_fields(resume_text, original_name)
#             employment_gaps = resume_data.get("employment_gaps", [])
            
#             app.screening_status = 'processed'
#             app.screening_score = score
#             app.employment_gaps = employment_gaps
#             app.save()
            
#             return {
#                 "application_id": str(app.id),
#                 "full_name": app.full_name,
#                 "email": app.email,
#                 "score": score,
#                 "screening_status": app.screening_status,
#                 "employment_gaps": employment_gaps,
#                 "success": True
#             }
            
#         except Exception as e:
#             logger.error(f"Processing failed for app {app.id}: {str(e)}")
#             app.screening_status = 'failed'
#             app.screening_score = 0.0
#             app.save()
#             if temp_file_path and os.path.exists(temp_file_path):
#                 os.unlink(temp_file_path)
#             return {
#                 "application_id": str(app.id),
#                 "full_name": app.full_name,
#                 "email": app.email,
#                 "error": f"Processing error: {str(e)}",
#                 "success": False
#             }

#     def _process_screening_results(self, results, applications, job_requisition, num_candidates, tenant_id):
#         shortlisted = [r for r in results if r.get("success")]
#         failed_applications = [r for r in results if not r.get("success")]

#         if not shortlisted and failed_applications:
#             return {
#                 "detail": "All resume screenings failed.",
#                 "failed_applications": failed_applications,
#                 "document_type": "resume"
#             }

#         shortlisted.sort(key=lambda x: x['score'], reverse=True)
#         final_shortlisted = shortlisted[:num_candidates] if num_candidates > 0 else shortlisted
#         shortlisted_ids = {item['application_id'] for item in final_shortlisted}

#         # Update application statuses and send emails
#         for app in applications:
#             app_id_str = str(app.id)
#             if app_id_str in shortlisted_ids:
#                 app.status = 'shortlisted'
#                 app.save()
#                 shortlisted_app = next((item for item in final_shortlisted if item['application_id'] == app_id_str), None)
#                 if shortlisted_app:
#                     applicant_data = {
#                         "email": shortlisted_app['email'],
#                         "full_name": shortlisted_app['full_name'],
#                         "application_id": shortlisted_app['application_id'],
#                         "job_requisition_id": job_requisition['id'],
#                         "status": "shortlisted",
#                         "score": shortlisted_app.get('score')
#                     }
                    
#                     employment_gaps = shortlisted_app.get('employment_gaps', [])
#                     event_type = "candidate.shortlisted.gaps" if employment_gaps else "candidate.shortlisted"
                    
#                     send_screening_notification(
#                         applicant=applicant_data,
#                         tenant_id=tenant_id,
#                         event_type=event_type,
#                         employment_gaps=employment_gaps
#                     )
#             else:
#                 app.status = 'rejected'
#                 app.save()
                
#                 rejected_app = {
#                     "email": app.email,
#                     "full_name": app.full_name,
#                     "application_id": app_id_str,
#                     "job_requisition_id": job_requisition['id'],
#                     "status": "rejected",
#                     "score": getattr(app, "screening_score", None)
#                 }
                
#                 send_screening_notification(
#                     applicant=rejected_app, 
#                     tenant_id=tenant_id, 
#                     event_type="candidate.rejected"
#                 )

#         return {
#             "detail": f"Screened {len(shortlisted)} applications, shortlisted {len(final_shortlisted)} candidates.",
#             "shortlisted_candidates": final_shortlisted,
#             "failed_applications": failed_applications,
#             "number_of_candidates": num_candidates,
#             "document_type": "resume"
#         }


class ResumeScreeningView(APIView):
    serializer_class = SimpleMessageSerializer
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    # Constants
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    MAX_SYNC_PROCESSING = 50
    MAX_WORKERS = 10

    def post(self, request, job_requisition_id):
        """
        Screen resumes for a job requisition
        Can process synchronously for small batches or asynchronously for large batches
        """
        try:
            # Extract JWT payload from middleware
            jwt_payload = getattr(request, 'jwt_payload', {})
            tenant_id = jwt_payload.get('tenant_unique_id')
            role = jwt_payload.get('role')
            branch = jwt_payload.get('user', {}).get('branch')

            # Parse request data
            document_type = request.data.get('document_type')
            applications_data = request.data.get('applications', [])
            num_candidates = request.data.get('number_of_candidates', 0)
            
            # Validate number of candidates
            try:
                num_candidates = int(num_candidates)
            except (TypeError, ValueError):
                num_candidates = 0

            # Get job requisition
            job_requisition = get_job_requisition_by_id(job_requisition_id, request)
            if not job_requisition:
                return Response({"detail": "Job requisition not found."}, status=status.HTTP_404_NOT_FOUND)

            # Validate document type
            if not document_type:
                return Response({"detail": "Document type is required."}, status=status.HTTP_400_BAD_REQUEST)

            document_type_lower = document_type.lower()
            allowed_docs = [doc.lower() for doc in (job_requisition.get('documents_required') or [])]
            allowed_docs.extend(['resume', 'curriculum vitae (cv)', 'cv'])
            if document_type_lower not in allowed_docs:
                return Response({"detail": f"Invalid document type: {document_type}"}, status=status.HTTP_400_BAD_REQUEST)

            # Fetch all applications if none provided
            if not applications_data:
                applications = JobApplication.active_objects.filter(
                    job_requisition_id=job_requisition_id,
                    tenant_id=tenant_id,
                    resume_status=True
                )
                paginator = Paginator(applications, 20)
                applications_data = []
                for page_num in paginator.page_range:
                    page = paginator.page(page_num)
                    applications_data.extend([{"application_id": str(app.id)} for app in page])
                print(f"Fetched {len(applications_data)} applications from database")

            print(f"Screening {len(applications_data)} applications")

            # Process synchronously for small batches, asynchronously for large
            if len(applications_data) <= self.MAX_SYNC_PROCESSING:
                return self._process_synchronously(
                    request, job_requisition_id, job_requisition, tenant_id, 
                    role, branch, document_type, applications_data, num_candidates
                )
            
            # Process large batches asynchronously
            task = process_large_resume_batch.delay(
                job_requisition_id=job_requisition_id,
                tenant_id=tenant_id,
                document_type=document_type,
                applications_data=applications_data,
                num_candidates=num_candidates,
                role=role,
                branch=branch,
                authorization_header=request.META.get('HTTP_AUTHORIZATION', '')
            )
            
            return Response({
                "detail": f"Started processing {len(applications_data)} applications asynchronously",
                "task_id": task.id,
                "status_endpoint": f"/api/applications-engine/applications/requisitions/screening/task-status/{task.id}/",
            }, status=status.HTTP_202_ACCEPTED)

        except Exception as e:
            print(f"Error initiating resume screening: {str(e)}")
            return Response({
                "error": "Failed to initiate screening",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _process_synchronously(self, request, job_requisition_id, job_requisition, tenant_id, 
                             role, branch, document_type, applications_data, num_candidates):
        """
        Process resume screening synchronously for small batches
        """
        try:
            document_type_lower = document_type.lower()
            
            # Filter applications based on provided data or fetch all
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

            # Apply role-based filtering
            if role == 'recruiter' and branch:
                applications = applications.filter(branch=branch)
            elif branch:
                applications = applications.filter(branch=branch)

            applications_list = list(applications)
            applications_data_map = {str(app['application_id']): app for app in applications_data}

            # Download resumes using thread pool
            download_results = []
            with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
                future_to_app = {
                    executor.submit(
                        self._download_resume,
                        app,
                        applications_data_map.get(str(app.id)),
                        document_type_lower
                    ): app for app in applications_list
                }
                for future in concurrent.futures.as_completed(future_to_app):
                    download_results.append(future.result())

            # Process screening with job requirements
            job_requirements = self._get_job_requirements(job_requisition)
            results = []
            
            with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
                future_to_result = {
                    executor.submit(
                        self._parse_and_screen,
                        result, 
                        job_requirements,
                        document_type
                    ): result for result in download_results
                }
                for future in concurrent.futures.as_completed(future_to_result):
                    results.append(future.result())

            # Process results and send emails
            final_response = self._process_screening_results(
                results, applications_list, job_requisition, num_candidates, tenant_id
            )
            
            return Response(final_response, status=status.HTTP_200_OK)

        except Exception as e:
            print(f"Synchronous processing failed: {str(e)}")
            return Response({
                "error": "Synchronous processing failed",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _download_resume(self, app, app_data, document_type_lower):
        """
        Download and decompress resume file
        """
        try:
            # Get file information from app_data or application documents
            if app_data and 'file_url' in app_data:
                file_url = app_data['file_url']
                compression = app_data.get('compression')
                original_name = app_data.get('original_name', 'resume.pdf')
            else:
                # Find the document in application documents
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
                        "error": f"No {document_type_lower} document found",
                    }
                file_url = cv_doc['file_url']
                compression = cv_doc.get('compression')
                original_name = cv_doc.get('original_name', 'resume.pdf')

            # Download file from storage
            headers = {"Authorization": f"Bearer {os.environ.get('SUPABASE_KEY', '')}"}
            response = requests.get(file_url, headers=headers, timeout=60, stream=True)
            print(f"Download response for app {app.id}: status={response.status_code}")
            
            if response.status_code != 200:
                app.screening_status = 'failed'
                app.screening_score = 0.0
                app.save()
                return {
                    "app": app,
                    "success": False,
                    "error": f"Failed to download resume, status: {response.status_code}",
                }

            # Stream download to avoid memory issues
            file_content = b''
            for chunk in response.iter_content(chunk_size=8192):
                file_content += chunk
                
            # Check file size
            if len(file_content) > self.MAX_FILE_SIZE:
                print(f"File too large for app {app.id}: {len(file_content)} bytes")
                app.screening_status = 'failed'
                app.screening_score = 0.0
                app.save()
                return {
                    "app": app,
                    "success": False,
                    "error": f"File too large ({len(file_content)} bytes)",
                }

            # Handle compression
            file_content = self._handle_compression(file_content, compression, file_url, original_name, app.id)
            if file_content is None:
                app.screening_status = 'failed'
                app.screening_score = 0.0
                app.save()
                return {
                    "app": app,
                    "success": False,
                    "error": "Failed to decompress file",
                }

            # Create temporary file
            content_type = response.headers.get('content-type', '')
            file_ext = mimetypes.guess_extension(content_type) or '.pdf'
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_ext)
            temp_file.write(file_content)
            temp_file.close()
            
            return {
                "app": app,
                "success": True,
                "temp_file_path": temp_file.name,
                "file_url": file_url,
                "original_name": original_name
            }
            
        except requests.exceptions.Timeout:
            print(f"Download timeout for app {app.id}")
            app.screening_status = 'failed'
            app.screening_score = 0.0
            app.save()
            return {
                "app": app,
                "success": False,
                "error": "Download timeout",
            }
        except Exception as e:
            print(f"Download failed for app {app.id}: {str(e)}")
            app.screening_status = 'failed'
            app.screening_score = 0.0
            app.save()
            return {
                "app": app,
                "success": False,
                "error": f"Download error: {str(e)}",
            }

    def _handle_compression(self, file_content, compression, file_url, original_name, app_id):
        """
        Handle various compression formats
        """
        try:
            # Detect compression from magic numbers if not explicitly provided
            if not compression:
                compression = self._detect_compression_format(file_content)
            
            # GZIP compression
            if compression == 'gzip' or file_url.endswith('.gz'):
                try:
                    decompressed = gzip.decompress(file_content)
                    print(f"Successfully decompressed GZIP file for app {app_id}")
                    return decompressed
                except Exception as e:
                    print(f"GZIP decompression failed for app {app_id}: {str(e)}")
                    # Try to detect if it's actually compressed
                    if file_content[:2] == b'\x1f\x8b':  # GZIP magic number
                        raise Exception("File appears to be GZIP but decompression failed")
                    # Otherwise, assume it's not actually compressed
                    return file_content
            
            # ZIP compression
            elif compression == 'zip' or file_url.endswith('.zip'):
                try:
                    with zipfile.ZipFile(io.BytesIO(file_content)) as zip_file:
                        # Try to find a resume file in the zip
                        resume_files = []
                        for name in zip_file.namelist():
                            if any(ext in name.lower() for ext in ['.pdf', '.doc', '.docx', '.txt', '.rtf']):
                                resume_files.append(name)
                        
                        if resume_files:
                            # Prefer PDF files, then Word, then others
                            for preferred_ext in ['.pdf', '.docx', '.doc', '.txt', '.rtf']:
                                for name in resume_files:
                                    if name.lower().endswith(preferred_ext):
                                        with zip_file.open(name) as f:
                                            content = f.read()
                                            print(f"Extracted {name} from ZIP for app {app_id}")
                                            return content
                            
                            # Fallback to first resume file
                            with zip_file.open(resume_files[0]) as f:
                                content = f.read()
                                print(f"Extracted first resume file {resume_files[0]} from ZIP for app {app_id}")
                                return content
                        else:
                            # If no obvious resume file found, use the first file
                            if zip_file.namelist():
                                with zip_file.open(zip_file.namelist()[0]) as f:
                                    content = f.read()
                                    print(f"Extracted first file {zip_file.namelist()[0]} from ZIP for app {app_id}")
                                    return content
                            else:
                                raise Exception("ZIP file is empty")
                except Exception as e:
                    print(f"ZIP decompression failed for app {app_id}: {str(e)}")
                    return None
            
            # BZIP2 compression
            elif compression == 'bzip2' or (file_content[:3] == b'BZh'):
                try:
                    import bz2
                    decompressed = bz2.decompress(file_content)
                    print(f"Successfully decompressed BZIP2 file for app {app_id}")
                    return decompressed
                except Exception as e:
                    print(f"BZIP2 decompression failed for app {app_id}: {str(e)}")
                    return None
            
            # No compression or unknown format
            else:
                return file_content
                
        except Exception as e:
            print(f"Compression handling failed for app {app_id}: {str(e)}")
            return None

    def _detect_compression_format(self, file_content):
        """
        Detect compression format from magic numbers
        """
        if len(file_content) < 4:
            return None
            
        magic_numbers = {
            b'\x1f\x8b': 'gzip',
            b'PK\x03\x04': 'zip',
            b'BZh': 'bzip2',
            b'\xfd7zXZ': 'xz',
            b'\x50\x4b\x03\x04': 'zip',  # Another ZIP signature
            b'\x50\x4b\x05\x06': 'zip',  # Empty ZIP
            b'\x50\x4b\x07\x08': 'zip',  # Spanned ZIP
        }
        
        for magic, format_name in magic_numbers.items():
            if file_content.startswith(magic):
                return format_name
        
        return None

    def _get_job_requirements(self, job_requisition):
        """
        Extract job requirements from requisition data
        """
        return (
            (job_requisition.get('job_description') or '') + ' ' +
            (job_requisition.get('qualification_requirement') or '') + ' ' +
            (job_requisition.get('experience_requirement') or '') + ' ' +
            (job_requisition.get('knowledge_requirement') or '')
        ).strip()

    def _parse_and_screen(self, result, job_requirements, document_type):
        """
        Parse resume and screen against job requirements
        """
        app = result["app"]
        if not result["success"]:
            # Enhanced error reporting for compression issues
            error_msg = result["error"]
            if any(term in error_msg.lower() for term in ['compress', 'decompress', 'gzip', 'zip']):
                error_msg = f"Compression error: {error_msg}"
                
            return {
                "application_id": str(app.id),
                "full_name": app.full_name,
                "email": app.email,
                "error": error_msg,
                "success": False
            }

        temp_file_path = result["temp_file_path"]
        original_name = result.get("original_name", "")
        try:
            # Parse resume text
            resume_text = parse_resume(temp_file_path)
            
            # Clean up temporary file
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
                    "error": f"Failed to parse resume",
                    "success": False
                }

            # Screen resume and extract fields
            score = screen_resume(resume_text, job_requirements)
            resume_data = extract_resume_fields(resume_text, original_name)
            employment_gaps = resume_data.get("employment_gaps", [])
            
            # Update application with screening results
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
            print(f"Processing failed for app {app.id}: {str(e)}")
            app.screening_status = 'failed'
            app.screening_score = 0.0
            app.save()
            # Clean up temporary file in case of error
            if temp_file_path and os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
            return {
                "application_id": str(app.id),
                "full_name": app.full_name,
                "email": app.email,
                "error": f"Processing error: {str(e)}",
                "success": False
            }

    def _process_screening_results(self, results, applications, job_requisition, num_candidates, tenant_id):
        """
        Process screening results and send notifications
        """
        shortlisted = [r for r in results if r.get("success")]
        failed_applications = [r for r in results if not r.get("success")]

        # Handle case where all screenings failed
        if not shortlisted and failed_applications:
            return {
                "detail": "All resume screenings failed.",
                "failed_applications": failed_applications,
                "document_type": "resume"
            }

        # Sort by score and select top candidates
        shortlisted.sort(key=lambda x: x['score'], reverse=True)
        final_shortlisted = shortlisted[:num_candidates] if num_candidates > 0 else shortlisted
        shortlisted_ids = {item['application_id'] for item in final_shortlisted}

        # Update application statuses and send emails
        for app in applications:
            app_id_str = str(app.id)
            if app_id_str in shortlisted_ids:
                # Update to shortlisted
                app.status = 'shortlisted'
                app.save()
                
                # Find shortlisted application data
                shortlisted_app = next((item for item in final_shortlisted if item['application_id'] == app_id_str), None)
                if shortlisted_app:
                    applicant_data = {
                        "email": shortlisted_app['email'],
                        "full_name": shortlisted_app['full_name'],
                        "application_id": shortlisted_app['application_id'],
                        "job_requisition_id": job_requisition['id'],
                        "status": "shortlisted",
                        "score": shortlisted_app.get('score')
                    }
                    
                    # Send notification with employment gaps info if any
                    employment_gaps = shortlisted_app.get('employment_gaps', [])
                    event_type = "candidate.shortlisted.gaps" if employment_gaps else "candidate.shortlisted"
                    
                    send_screening_notification(
                        applicant=applicant_data,
                        tenant_id=tenant_id,
                        event_type=event_type,
                        employment_gaps=employment_gaps
                    )
            else:
                # Update to rejected
                app.status = 'rejected'
                app.save()
                
                # Send rejection notification
                rejected_app = {
                    "email": app.email,
                    "full_name": app.full_name,
                    "application_id": app_id_str,
                    "job_requisition_id": job_requisition['id'],
                    "status": "rejected",
                    "score": getattr(app, "screening_score", None)
                }
                
                send_screening_notification(
                    applicant=rejected_app, 
                    tenant_id=tenant_id, 
                    event_type="candidate.rejected"
                )

        return {
            "detail": f"Screened {len(shortlisted)} applications, shortlisted {len(final_shortlisted)} candidates.",
            "shortlisted_candidates": final_shortlisted,
            "failed_applications": failed_applications,
            "number_of_candidates": num_candidates,
            "document_type": "resume"
        }


class ScreeningTaskStatusView(APIView):
    """
    Check status of async screening tasks
    """
    
    def get(self, request, task_id):
        task_result = AsyncResult(task_id)
        
        response_data = {
            'task_id': task_id,
            'status': task_result.status,
            'result': None
        }
        
        if task_result.ready():
            if task_result.successful():
                response_data['result'] = task_result.result
            else:
                response_data['error'] = str(task_result.result)
        
        return Response(response_data)
    


class JobApplicationCreatePublicView(generics.CreateAPIView):
    serializer_class = PublicJobApplicationSerializer
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def create(self, request, *args, **kwargs):
        # Normalize list-based fields to strings
        def normalize_field(value):
            if isinstance(value, list) and value:
                return value[0]
            return value

        unique_link = normalize_field(request.data.get('unique_link') or request.data.get('job_requisition_unique_link'))
        if not unique_link:
            logger.warning("Missing job requisition unique link in request")
            return Response({"detail": "Missing job requisition unique link."}, status=status.HTTP_400_BAD_REQUEST)

        # Extract tenant_id from unique_link
        try:
            parts = unique_link.split('-')
            if len(parts) < 5:
                logger.warning(f"Invalid unique_link format: {unique_link}")
                return Response({"detail": "Invalid unique link format."}, status=status.HTTP_400_BAD_REQUEST)
            tenant_id = '-'.join(parts[:5])
        except Exception as e:
            logger.error(f"Error extracting tenant_id from link: {str(e)}")
            return Response({"detail": "Failed to extract tenant ID."}, status=status.HTTP_400_BAD_REQUEST)

        # Fetch job requisition from Talent Engine
        requisition_url = f"{settings.TALENT_ENGINE_URL}/api/talent-engine/requisitions/by-link/{unique_link}/"
        try:
            resp = requests.get(requisition_url)
            logger.info(f"Requisition fetch for link: {unique_link}, status: {resp.status_code}")
            if resp.status_code != 200:
                try:
                    error_detail = resp.json().get('detail', 'Invalid job requisition.')
                except Exception:
                    error_detail = 'Invalid job requisition.'
                logger.error(f"Failed to fetch requisition: {error_detail}")
                return Response({"detail": error_detail}, status=status.HTTP_400_BAD_REQUEST)
            job_requisition = resp.json()
        except Exception as e:
            logger.error(f"Error fetching job requisition: {str(e)}")
            return Response({"detail": "Unable to fetch job requisition."}, status=status.HTTP_502_BAD_GATEWAY)

        # Prepare payload, normalizing list-based fields
        payload = {key: normalize_field(value) for key, value in request.data.items()}
        payload['job_requisition_id'] = job_requisition['id']
        payload['tenant_id'] = tenant_id

        # Extract and compress documents from multipart form
        documents = []
        i = 0
        while f'documents[{i}][document_type]' in request.data and f'documents[{i}][file]' in request.FILES:
            document_type = normalize_field(request.data.get(f'documents[{i}][document_type]')).lower()
            file_obj = request.FILES.get(f'documents[{i}][file]')
            original_name = file_obj.name
            content_type = file_obj.content_type
            folder_path = f"application_documents/{timezone.now().strftime('%Y/%m/%d')}"
            file_name = f"{folder_path}/{uuid.uuid4()}{os.path.splitext(original_name)[1]}"

            # Compress file if it's a resume or CV
            if document_type in ['resume', 'curriculum vitae (cv)']:
                try:
                    file_content = file_obj.read()
                    compressed_file = io.BytesIO()
                    with gzip.GzipFile(fileobj=compressed_file, mode='wb') as gz:
                        gz.write(file_content)
                    compressed_file.seek(0)
                    file_name += '.gz'
                    content_type = 'application/gzip'
                    compressed_file_obj = InMemoryUploadedFile(
                        file=compressed_file,
                        field_name=f'documents[{i}][file]',
                        name=file_name,
                        content_type=content_type,
                        size=len(compressed_file.getvalue()),
                        charset=None
                    )
                except Exception as e:
                    logger.error(f"Compression failed for file {original_name}: {str(e)}")
                    return Response({"detail": f"Failed to compress file {original_name}"}, status=status.HTTP_400_BAD_REQUEST)
            else:
                compressed_file_obj = file_obj
                file_name = f"{folder_path}/{uuid.uuid4()}{os.path.splitext(original_name)[1]}"

            # Upload file to storage
            try:
                file_url = upload_file_dynamic(compressed_file_obj, file_name, content_type)
                logger.info(f"Uploaded file {file_name} to {file_url}")
            except Exception as e:
                logger.error(f"Upload failed for file {file_name}: {str(e)}")
                return Response({"detail": f"Failed to upload file {file_name}"}, status=status.HTTP_400_BAD_REQUEST)

            documents.append({
                'document_type': document_type,
                'file_url': file_url,
                'original_name': original_name,
                'compression': 'gzip' if document_type in ['resume', 'curriculum vitae (cv)'] else None,
                'uploaded_at': timezone.now().isoformat()
            })
            i += 1

        if documents:
            payload['documents'] = documents

        logger.info(f"Full POST payload: {payload}")

        # Validate serializer
        serializer = self.get_serializer(data=payload, context={'request': request, 'job_requisition': job_requisition})
        if not serializer.is_valid():
            logger.error(f"Validation errors: {serializer.errors}")
            return Response({
                "detail": "Validation error",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        # Prevent duplicate application
        email = payload.get('email')
        job_requisition_id = job_requisition['id']
        if JobApplication.objects.filter(email=email, job_requisition_id=job_requisition_id).exists():
            logger.warning(f"Duplicate application attempt by email: {email} for requisition: {job_requisition_id}")
            return Response({"detail": "You have already applied for this job"}, status=status.HTTP_400_BAD_REQUEST)

        # Save the application
        self.perform_create(serializer)

        # Increment num_of_applications
        increment_url = f"{settings.TALENT_ENGINE_URL}/api/talent-engine/requisitions/public/update-applications/{unique_link}/"
        try:
            resp = requests.post(increment_url)
            if resp.status_code != 200:
                logger.warning(f"Failed to increment num_of_applications for unique_link {unique_link}: {resp.status_code}, {resp.text}")
            else:
                logger.info(f"Successfully incremented num_of_applications for unique_link {unique_link}")
        except Exception as e:
            logger.error(f"Error calling increment endpoint for unique_link {unique_link}: {str(e)}")

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
            logger.info(f"Published Kafka job application event for requisition {job_requisition['id']}")
        except Exception as e:
            logger.error(f"Kafka publish error: {str(e)}")

        return Response(serializer.data, status=status.HTTP_201_CREATED)

class JobApplicationListCreateView(generics.ListCreateAPIView):
    serializer_class = JobApplicationSerializer
    pagination_class = CustomPagination
    parser_classes = (MultiPartParser, FormParser)

    def get_permissions(self):
        if self.request.method == 'POST':
            return [AllowAny()]
        return [AllowAny()]  # TODO: Use IsAuthenticated in production

    def get_queryset(self):
        request = self.request
        tenant_id = request.jwt_payload.get('tenant_unique_id')

        if not tenant_id:
            logger.warning("Tenant unique ID not found in token")
            return JobApplication.objects.none()

        branch_id = request.query_params.get('branch_id')
        queryset = JobApplication.active_objects.filter(tenant_id=tenant_id)

        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)

        if hasattr(request.user, 'branch') and request.user.branch and not branch_id:
            queryset = queryset.filter(branch=request.user.branch)

        return queryset.order_by('-created_at')

    def check_permissions(self, request):
        logger.info(f"Permission check for {request.user} - authenticated: {getattr(request.user, 'is_authenticated', None)}")
        return super().check_permissions(request)

class JobApplicationDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = JobApplicationSerializer
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    lookup_field = 'id'

    def get_queryset(self):
        jwt_payload = getattr(self.request, 'jwt_payload', {})
        tenant_id = jwt_payload.get('tenant_unique_id')
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
            return Response({"detail": str(e)}, status=500)

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
            return Response({"detail": str(e)}, status=500)

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            self.perform_destroy(instance)
            return Response(status=204)
        except Exception as e:
            logger.exception(f"Error deleting job application: {str(e)}")
            return Response({"detail": str(e)}, status=500)

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
    """
    Retrieve a job application and its schedules using email and unique_link query params.
    Example URL:
    /api/applications-engine/applications/code/PRO-JA-0001/email/chinedu.okeke@example.com/with-schedules/schedules/?unique_link=40c4a578-8f39-4f20-827a-c71b209190c3-PRO-senior-backend-engineer-c8d27a86
    """
    serializer_class = SimpleMessageSerializer  # Replace if needed

    def get(self, request, *args, **kwargs):
        email = kwargs.get('email') 
        unique_link = request.query_params.get('unique_link')

        if not email or not unique_link:
            return Response(
                {"detail": "Both 'email' and 'unique_link' are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Extract tenant_id from UUID-style prefix (first 5 segments)
        try:
            parts = unique_link.split('-')
            if len(parts) < 5:
                return Response({"detail": "Invalid unique link format."}, status=status.HTTP_400_BAD_REQUEST)
            tenant_id = '-'.join(parts[:5])
        except Exception as e:
            logger.error(f"Error extracting tenant_id from link: {str(e)}")
            return Response({"detail": "Failed to extract tenant ID."}, status=status.HTTP_400_BAD_REQUEST)

        # Fetch job requisition from Talent Engine
        requisition_url = f"{settings.TALENT_ENGINE_URL}/api/talent-engine/requisitions/by-link/{unique_link}/"
        try:
            resp = requests.get(requisition_url)
            if resp.status_code != 200:
                error_detail = resp.json().get('detail', 'Invalid job requisition.') if resp.content else 'Invalid job requisition.'
                return Response({"detail": error_detail}, status=status.HTTP_400_BAD_REQUEST)
            job_requisition = resp.json()
        except Exception as e:
            logger.error(f"Error fetching job requisition: {str(e)}")
            return Response({"detail": "Unable to fetch job requisition."}, status=status.HTTP_502_BAD_GATEWAY)

        # Fetch job application by email + tenant_id + job requisition
        try:
            job_application = JobApplication.active_objects.get(
                tenant_id=tenant_id,
                email=email,
                job_requisition_id=job_requisition['id']
            )
        except JobApplication.DoesNotExist:
            return Response({"detail": "Job application not found."}, status=status.HTTP_404_NOT_FOUND)
        except JobApplication.MultipleObjectsReturned:
            return Response({"detail": "Multiple job applications found. Please contact support."}, status=status.HTTP_400_BAD_REQUEST)

        job_application_serializer = JobApplicationSerializer(job_application)

        # Fetch schedules for this application
        # schedules = Schedule.active_objects.filter(
        #     tenant_id=tenant_id,
        #     job_application=job_application
        # )

        # Fetch schedules for this application
        schedules = Schedule.active_objects.filter(
            tenant_id=tenant_id,
            job_application_id=job_application.id
        )
 
        if request.user.is_authenticated and getattr(request.user, 'role', None) == 'recruiter' and getattr(request.user, 'branch', None):
            schedules = schedules.filter(branch=request.user.branch)

        schedule_serializer = ScheduleSerializer(schedules, many=True)

        response_data = {
            'job_application': job_application_serializer.data,
            'job_requisition': job_requisition,
            'schedules': schedule_serializer.data,
            'schedule_count': schedules.count()
        }

        logger.info(f"Retrieved job application for email {email} and tenant {tenant_id}")
        return Response(response_data, status=status.HTTP_200_OK)

class JobApplicationsByRequisitionView(generics.ListAPIView):
    serializer_class = JobApplicationSerializer
    pagination_class = CustomPagination
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    # permission_classes = [IsAuthenticated]
    def get_permissions(self):
        return [AllowAny()]  # Temporary for testing

    def get_queryset(self):
        jwt_payload = getattr(self.request, 'jwt_payload', {})
        tenant_id = self.request.jwt_payload.get('tenant_unique_id')
        #tenant_id = str(jwt_payload.get('tenant_id')) if jwt_payload.get('tenant_id') is not None else None
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
    # permission_classes = [IsAuthenticated]

    def get(self, request):
        jwt_payload = getattr(request, 'jwt_payload', {})
        tenant_id = self.request.jwt_payload.get('tenant_unique_id')
        #tenant_id = str(jwt_payload.get('tenant_id')) if jwt_payload.get('tenant_id') is not None else None
        role = jwt_payload.get('role')
        branch = jwt_payload.get('user', {}).get('branch')

        if not tenant_id:
            return Response({"detail": "tenant_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        # ---------- Fetch paginated results ----------
        all_job_requisitions = []
        next_url = f"{settings.TALENT_ENGINE_URL}/api/talent-engine/requisitions/"
        headers = {'Authorization': request.META.get("HTTP_AUTHORIZATION", "")}
        params = {'tenant_id': tenant_id, 'publish_status': True}

        while next_url:
            try:
                resp = requests.get(next_url, headers=headers, params=params if next_url.endswith('/requisitions/') else {})
                data = resp.json()
            except requests.RequestException as e:
                print(f"Request failed: {e}")
                return Response({"detail": "Error fetching job requisitions."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            except ValueError:
                print("Invalid JSON response from requisition service.")
                return Response({"detail": "Invalid response format."}, status=500)

            if resp.status_code != 200:
                print(f"Failed to fetch job requisitions: {resp.status_code} - {resp.text}")
                return Response({"detail": "Failed to fetch job requisitions."}, status=resp.status_code)

            results = data.get('results', [])
            all_job_requisitions.extend(results)
            next_url = data.get('next')

        # ---------- Process requisitions ----------
        response_data = []

        for job_requisition in all_job_requisitions:
            if not isinstance(job_requisition, dict):
                print(f"Invalid job requisition: {job_requisition}")
                continue

            job_requisition_id = job_requisition.get('id')
            if not job_requisition_id:
                print(f"Missing job requisition ID: {job_requisition}")
                continue

            # Fetch shortlisted applications
            applications = JobApplication.active_objects.filter(
                tenant_id=tenant_id,
                job_requisition_id=job_requisition_id,
                status='shortlisted'
            )
            if branch:
                applications = applications.filter(branch=branch)

            application_serializer = JobApplicationSerializer(applications, many=True)

            # Add schedules to each application
            enhanced_applications = []
            for app_data in application_serializer.data:
                application_id = app_data['id']
                schedules = Schedule.active_objects.filter(
                    tenant_id=tenant_id,
                    job_application_id=application_id
                )
                if branch:
                    schedules = schedules.filter(branch=branch)

                schedule_serializer = ScheduleSerializer(schedules, many=True)
                app_data['scheduled'] = schedules.exists()
                app_data['schedules'] = schedule_serializer.data
                enhanced_applications.append(app_data)

            # Total applications
            total_applications = JobApplication.active_objects.filter(
                tenant_id=tenant_id,
                job_requisition_id=job_requisition_id
            )
            if branch:
                total_applications = total_applications.filter(branch=branch)

            response_data.append({
                'job_requisition': job_requisition,
                'shortlisted_applications': enhanced_applications,
                'shortlisted_count': applications.count(),
                'total_applications': total_applications.count()
            })

        # Sort by created_at descending
        response_data.sort(key=lambda x: x['job_requisition'].get('created_at', ''), reverse=True)
        return Response(response_data, status=status.HTTP_200_OK)

class PublishedPublicJobRequisitionsWithShortlistedApplicationsView(APIView):
    serializer_class = SimpleMessageSerializer 
    # permission_classes = [AllowAny]

    def get(self, request):
        jwt_payload = getattr(request, 'jwt_payload', {})
        tenant_id = self.request.jwt_payload.get('tenant_unique_id')
        #tenant_id = str(jwt_payload.get('tenant_id')) if jwt_payload.get('tenant_id') is not None else None
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
    # permission_classes = [IsAuthenticated]

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
        tenant_id = self.request.jwt_payload.get('tenant_unique_id')
        #tenant_id = str(jwt_payload.get('tenant_id')) if jwt_payload.get('tenant_id') is not None else None
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
    pagination_class = CustomPagination
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def get_queryset(self):
        jwt_payload = getattr(self.request, 'jwt_payload', {})
        tenant_id = jwt_payload.get('tenant_unique_id')
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
        jwt_payload = getattr(request, 'jwt_payload', {})
        tenant_id = self.request.jwt_payload.get('tenant_unique_id')

        if not tenant_id:
            logger.error("Tenant schema or ID missing from token")
            return Response({"error": "Tenant schema or ID missing from token"}, status=status.HTTP_401_UNAUTHORIZED)

        data = request.data.copy()
        serializer = self.get_serializer(data=data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        schedule = serializer.save()  # Calls create method in serializer

        # Send notification after successful schedule creation
        try:
            job_app = JobApplication.objects.filter(id=schedule.job_application_id).first()
            if not job_app:
                logger.error(f"Job application {schedule.job_application_id} not found for schedule {schedule.id}")
            else:
                notification_payload = {
                    "application_id": str(schedule.job_application_id),
                    "full_name": job_app.full_name,
                    "email": job_app.email,
                    "job_requisition_id": str(job_app.job_requisition_id),
                    "status": schedule.status,
                    "interview_start_date_time": schedule.interview_start_date_time.isoformat(),
                    "interview_end_date_time": schedule.interview_end_date_time.isoformat() if schedule.interview_end_date_time else None,
                    "meeting_mode": schedule.meeting_mode,
                    "meeting_link": schedule.meeting_link,
                    "interview_address": schedule.interview_address,
                    "message": schedule.message,
                    "timezone": schedule.timezone,
                    "schedule_id": str(schedule.id)
                }
                send_screening_notification(
                    notification_payload,
                    tenant_id=tenant_id,
                    event_type="interview.scheduled"
                )
                logger.info(f"Schedule creation notification sent for schedule {schedule.id}, job application {schedule.job_application_id}")
        except Exception as e:
            logger.error(f"Failed to send schedule creation notification for schedule {schedule.id}: {str(e)}")

        return Response(serializer.data, status=status.HTTP_201_CREATED)

class ScheduleDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ScheduleSerializer
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    lookup_field = 'id'

    def get_permissions(self):
        return [AllowAny()]  # Temporary for testing

    def get_queryset(self):
        jwt_payload = getattr(self.request, 'jwt_payload', {})
        tenant_id = jwt_payload.get('tenant_unique_id')
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

            # Send notification after successful schedule update
            try:
                job_app = JobApplication.objects.filter(id=instance.job_application_id).first()
                if not job_app:
                    logger.error(f"Job application {instance.job_application_id} not found for schedule {instance.id}")
                else:
                    notification_payload = {
                        "application_id": str(instance.job_application_id),
                        "full_name": job_app.full_name,
                        "email": job_app.email,
                        "job_requisition_id": str(job_app.job_requisition_id),
                        "status": instance.status,
                        "interview_start_date_time": instance.interview_start_date_time.isoformat(),
                        "interview_end_date_time": instance.interview_end_date_time.isoformat() if instance.interview_end_date_time else None,
                        "meeting_mode": instance.meeting_mode,
                        "meeting_link": instance.meeting_link,
                        "interview_address": instance.interview_address,
                        "message": instance.message,
                        "timezone": instance.timezone,
                        "schedule_id": str(instance.id),
                        "cancellation_reason": instance.cancellation_reason
                    }
                    send_screening_notification(
                        notification_payload,
                        tenant_id=instance.tenant_id,
                        event_type="interview.scheduled"
                    )
                    logger.info(f"Schedule update notification sent for schedule {instance.id}, job application {instance.job_application_id}")
            except Exception as e:
                logger.error(f"Failed to send schedule update notification for schedule {instance.id}: {str(e)}")

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
        #tenant_id = self.request.jwt_payload.get('tenant_unique_id')
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
        tenant_id = self.request.jwt_payload.get('tenant_unique_id')
        #tenant_id = str(jwt_payload.get('tenant_id')) if jwt_payload.get('tenant_id') is not None else None
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
        tenant_id = self.request.jwt_payload.get('tenant_unique_id')
        #tenant_id = str(jwt_payload.get('tenant_id')) if jwt_payload.get('tenant_id') is not None else None
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
        tenant_id = self.request.jwt_payload.get('tenant_unique_id')
       # tenant_id = str(jwt_payload.get('tenant_id')) if jwt_payload.get('tenant_id') is not None else None
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

# Assuming JobApplication and JobApplicationSerializer are defined elsewhere

# class ComplianceStatusUpdateView(APIView):
#     permission_classes = [AllowAny]  # Temporary for testing; replace with IsAuthenticated in production
#     parser_classes = [JSONParser]

#     def post(self, request, job_application_id):
#         # Extract item_id from request body
#         item_id = request.data.get('item_id')
#         if not item_id:
#             logger.warning("No item_id provided in request data")
#             return Response({"detail": "Item ID is required."}, status=status.HTTP_400_BAD_REQUEST)

#         # Extract JWT payload for authorization
#         jwt_payload = getattr(request, 'jwt_payload', {})
#         logger.info(f"JWT payload: {jwt_payload}")  # Log payload for debugging
#         role = jwt_payload.get('role')
#         branch = jwt_payload.get('user', {}).get('branch')
#         user_id = jwt_payload.get('user', {}).get('id')  # Extract user_id from user.id

#         # Validate update data
#         update_data = {k: v for k, v in request.data.items() if k != 'item_id'}
#         if not update_data or not isinstance(update_data, dict):
#             logger.warning("No update data provided or invalid format")
#             return Response({"detail": "Update data must be a dictionary with fields to update."}, status=status.HTTP_400_BAD_REQUEST)

#         # Define valid fields
#         valid_fields = ['status', 'notes', 'description', 'required', 'checked_by', 'checked_at']
#         invalid_fields = [field for field in update_data if field not in valid_fields]
#         if invalid_fields:
#             logger.warning(f"Invalid fields provided: {invalid_fields}")
#             return Response({"detail": f"Invalid fields: {invalid_fields}. Must be one of {valid_fields}."}, status=status.HTTP_400_BAD_REQUEST)

#         # Validate status if provided
#         if 'status' in update_data and update_data['status'] not in ['pending', 'uploaded', 'accepted', 'rejected']:
#             logger.warning(f"Invalid status provided: {update_data['status']}")
#             return Response({"detail": "Invalid status. Must be 'pending', 'uploaded', 'accepted', or 'rejected'."}, status=status.HTTP_400_BAD_REQUEST)

#         # Fetch user details for checked_by when updating status
#         checked_by = None
#         if 'status' in update_data:
#             if not user_id:
#                 logger.warning("No user.id found in JWT payload for status update")
#                 return Response({"detail": "Authentication required for status update."}, status=status.HTTP_401_UNAUTHORIZED)
#             try:
#                 user_response = requests.get(
#                     f'{settings.AUTH_SERVICE_URL}/api/user/users/{user_id}/',
#                     headers={'Authorization': f'Bearer {request.META.get("HTTP_AUTHORIZATION", "").split(" ")[1] if request.META.get("HTTP_AUTHORIZATION") else ""}'}
#                 )
#                 if user_response.status_code == 200:
#                     user_data = user_response.json()
#                     checked_by = {
#                         'email': user_data.get('email', ''),
#                         'first_name': user_data.get('first_name', ''),
#                         'last_name': user_data.get('last_name', ''),
#                         'job_role': user_data.get('job_role', '')
#                     }
#                 else:
#                     logger.error(f"Failed to fetch user {user_id} from auth_service: {user_response.status_code}")
#                     return Response({"detail": "Failed to fetch user details."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
#             except Exception as e:
#                 logger.error(f"Error fetching user {user_id}: {str(e)}")
#                 return Response({"detail": "Error fetching user details."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#         # Fetch the job application
#         try:
#             application = JobApplication.active_objects.get(id=job_application_id)
#         except JobApplication.DoesNotExist:
#             logger.warning(f"Job application not found: {job_application_id}")
#             return Response({"detail": "Job application not found."}, status=status.HTTP_404_NOT_FOUND)

#         # Check branch authorization if branch is provided
#         if branch and application.branch_id != branch:
#             logger.warning(f"User not authorized to access application {job_application_id} for branch {branch}")
#             return Response({"detail": "Not authorized to access this application."}, status=status.HTTP_403_FORBIDDEN)

#         # Update compliance_status
#         updated_compliance_status = application.compliance_status.copy() if application.compliance_status else []
#         item_updated = False

#         for item in updated_compliance_status:
#             if str(item.get('id')) == str(item_id):
#                 if not item.get('document') and 'status' in update_data and update_data['status'] in ['accepted', 'rejected']:
#                     logger.warning(f"No document found for compliance item {item_id} in application {job_application_id}")
#                     return Response({"detail": "No document found for this compliance item."}, status=status.HTTP_400_BAD_REQUEST)
#                 # Update all provided fields
#                 for field_name, field_value in update_data.items():
#                     item[field_name] = field_value
#                 # Set checked_by and checked_at if status is updated
#                 if 'status' in update_data and checked_by:
#                     item['checked_by'] = checked_by
#                     item['checked_at'] = timezone.now().isoformat()
#                 item_updated = True
#                 logger.info(f"Updated compliance item {item_id} in application {job_application_id} with fields {list(update_data.keys())}")
#                 break

#         if not item_updated:
#             logger.warning(f"Compliance item {item_id} not found in application {job_application_id}")
#             return Response({"detail": f"Compliance item {item_id} not found."}, status=status.HTTP_404_NOT_FOUND)

#         # Save the updated application
#         with transaction.atomic():
#             application.compliance_status = updated_compliance_status
#             application.save()
#             logger.info(f"Job application {job_application_id} saved with updated compliance status")

#         serializer = JobApplicationSerializer(application, context={'request': request})
#         return Response({
#             "detail": "Compliance status updated successfully.",
#             "compliance_item": next((item for item in serializer.data['compliance_status'] if str(item['id']) == str(item_id)), None)
#         }, status=status.HTTP_200_OK)



class ComplianceStatusUpdateView(APIView):
    permission_classes = [AllowAny]  # Temporary for testing; replace with IsAuthenticated in production
    parser_classes = [JSONParser]

    def post(self, request, job_application_id):
        # Extract item_id from request body
        item_id = request.data.get('item_id')
        if not item_id:
            logger.warning("No item_id provided in request data")
            return Response({"detail": "Item ID is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Extract user data from JWT
        try:
            user_data = get_user_data_from_jwt(request)
            user_id = user_data.get('id')
            branch = user_data.get('branch')  # May be null based on JWT
            checked_by = {
                'email': user_data.get('email', ''),
                'first_name': user_data.get('first_name', ''),
                'last_name': user_data.get('last_name', ''),
                'job_role': user_data.get('job_role', '')
            }
        except Exception as e:
            logger.error(f"Failed to extract user data from JWT: {str(e)}")
            return Response({"detail": "Invalid JWT token for user data."}, status=status.HTTP_401_UNAUTHORIZED)

        if not user_id:
            logger.warning("No user.id found in JWT payload for status update")
            return Response({"detail": "Authentication required for status update."}, status=status.HTTP_401_UNAUTHORIZED)

        # Validate update data
        update_data = {k: v for k, v in request.data.items() if k != 'item_id'}
        if not update_data or not isinstance(update_data, dict):
            logger.warning("No update data provided or invalid format")
            return Response({"detail": "Update data must be a dictionary with fields to update."}, status=status.HTTP_400_BAD_REQUEST)

        # Define valid fields
        valid_fields = ['status', 'notes', 'description', 'required', 'checked_by', 'checked_at']
        invalid_fields = [field for field in update_data if field not in valid_fields]
        if invalid_fields:
            logger.warning(f"Invalid fields provided: {invalid_fields}")
            return Response({"detail": f"Invalid fields: {invalid_fields}. Must be one of {valid_fields}."}, status=status.HTTP_400_BAD_REQUEST)

        # Validate status if provided
        if 'status' in update_data and update_data['status'] not in ['pending', 'uploaded', 'accepted', 'rejected']:
            logger.warning(f"Invalid status provided: {update_data['status']}")
            return Response({"detail": "Invalid status. Must be 'pending', 'uploaded', 'accepted', or 'rejected'."}, status=status.HTTP_400_BAD_REQUEST)

        # Fetch the job application
        try:
            application = JobApplication.active_objects.get(id=job_application_id)
        except JobApplication.DoesNotExist:
            logger.warning(f"Job application not found: {job_application_id}")
            return Response({"detail": "Job application not found."}, status=status.HTTP_404_NOT_FOUND)

        # Check branch authorization if branch is provided
        if branch and application.branch_id != branch:
            try:
                from .models import Branch  # Adjust import based on your project
                branch_exists = Branch.objects.filter(id=application.branch_id, tenant_id=application.tenant_id).exists()
                if not branch_exists:
                    logger.warning(f"Invalid branch {application.branch_id} for application {job_application_id}")
                    return Response({"detail": "Invalid branch for this application."}, status=status.HTTP_403_FORBIDDEN)
                if str(application.branch_id) != str(branch):
                    logger.warning(f"User not authorized to access application {job_application_id} for branch {branch}")
                    return Response({"detail": "Not authorized to access this application."}, status=status.HTTP_403_FORBIDDEN)
            except ImportError:
                logger.warning(f"Branch validation skipped: No Branch model available for branch_id {application.branch_id}")
                # Optionally raise an error if branch validation is critical
                # return Response({"detail": "Branch validation not supported without local Branch model."}, status=status.HTTP_400_BAD_REQUEST)

        # Update compliance_status
        updated_compliance_status = application.compliance_status.copy() if application.compliance_status else []
        item_updated = False

        for item in updated_compliance_status:
            if str(item.get('id')) == str(item_id):
                if not item.get('document') and 'status' in update_data and update_data['status'] in ['accepted', 'rejected']:
                    logger.warning(f"No document found for compliance item {item_id} in application {job_application_id}")
                    return Response({"detail": "No document found for this compliance item."}, status=status.HTTP_400_BAD_REQUEST)
                # Update all provided fields
                for field_name, field_value in update_data.items():
                    item[field_name] = field_value
                # Set checked_by and checked_at if status is updated
                if 'status' in update_data:
                    item['checked_by'] = checked_by
                    item['checked_at'] = timezone.now().isoformat()
                item_updated = True
                logger.info(f"Updated compliance item {item_id} in application {job_application_id} with fields {list(update_data.keys())}")
                break

        if not item_updated:
            logger.warning(f"Compliance item {item_id} not found in application {job_application_id}")
            return Response({"detail": f"Compliance item {item_id} not found."}, status=status.HTTP_404_NOT_FOUND)

        # Save the updated application
        with transaction.atomic():
            application.compliance_status = updated_compliance_status
            application.save()
            logger.info(f"Job application {job_application_id} saved with updated compliance status")

        serializer = JobApplicationSerializer(application, context={'request': request})
        return Response({
            "detail": "Compliance status updated successfully.",
            "compliance_item": next((item for item in serializer.data['compliance_status'] if str(item['id']) == str(item_id)), None)
        }, status=status.HTTP_200_OK)




class ApplicantComplianceUploadView(APIView):
    permission_classes = [AllowAny]
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def post(self, request, job_application_id):
        return self._handle_upload(request, job_application_id)

    def _handle_upload(self, request, job_application_id):
        logger.info(f"Request data: {request.data}")
        unique_link = request.data.get('unique_link')
        email = request.data.get('email')
        names = request.data.getlist('names', [])  # List of compliance item names, optional
        files = request.FILES.getlist('documents', [])  # List of uploaded files, optional

        # Validate required fields
        if not unique_link:
            return Response({"detail": "Missing job requisition unique link."}, status=status.HTTP_400_BAD_REQUEST)
        if not email:
            return Response({"detail": "Missing email."}, status=status.HTTP_400_BAD_REQUEST)

        # Extract tenant_id from unique_link
        try:
            parts = unique_link.split('-')
            if len(parts) < 6:
                return Response({"detail": "Invalid unique link format."}, status=status.HTTP_400_BAD_REQUEST)
            tenant_id = '-'.join(parts[:5])
        except Exception as e:
            logger.error(f"Error extracting tenant_id from {unique_link}: {str(e)}")
            return Response({"detail": "Failed to extract tenant ID."}, status=status.HTTP_400_BAD_REQUEST)

        # Fetch job requisition
        try:
            requisition_url = f"{settings.TALENT_ENGINE_URL}/api/talent-engine/requisitions/by-link/{unique_link}/"
            resp = requests.get(requisition_url)
            if resp.status_code != 200:
                return Response({"detail": "Invalid job requisition."}, status=status.HTTP_400_BAD_REQUEST)
            job_requisition = resp.json()
        except Exception as e:
            logger.error(f"Error fetching job requisition: {str(e)}")
            return Response({"detail": "Unable to fetch job requisition."}, status=status.HTTP_502_BAD_GATEWAY)

        # Retrieve job application
        try:
            application = JobApplication.active_objects.get(
                id=job_application_id,
                tenant_id=tenant_id,
                job_requisition_id=job_requisition['id'],
                email=email
            )
        except JobApplication.DoesNotExist:
            return Response({"detail": "Job application not found."}, status=status.HTTP_404_NOT_FOUND)

        # Initialize or update compliance_status with checklist items
        checklist = job_requisition.get('compliance_checklist', [])
        if not application.compliance_status or len(application.compliance_status) == 0:
            application.compliance_status = []
        # Ensure all checklist items are in compliance_status
        checklist_names = {item['name'] for item in checklist}
        existing_names = {item['name'] for item in application.compliance_status}
        for item in checklist:
            name = item.get('name', '')
            if not name or name in existing_names:
                continue
            generated_id = f"compliance-{slugify(name)}"
            application.compliance_status.append({
                'id': generated_id,
                'name': name,
                'description': item.get('description', ''),
                'required': item.get('required', True),
                'requires_document': item.get('requires_document', True),
                'status': 'pending',
                'checked_by': None,
                'checked_at': None,
                'notes': '',
                'document': [],  # Initialize as list to support multiple documents
                'metadata': {}
            })
        application.save()
        application.refresh_from_db()

        # If no compliance checklist, return success
        if not checklist:
            return Response({
                "detail": "No compliance items required for this requisition.",
                "compliance_status": application.compliance_status
            }, status=status.HTTP_200_OK)

        # Map compliance item names to their details
        compliance_checklist = {item['name']: item for item in application.compliance_status}

        # Validate provided names against checklist
        for name in names:
            if name not in checklist_names:
                return Response({"detail": f"Invalid compliance item name: {name}. Must match checklist."}, 
                               status=status.HTTP_400_BAD_REQUEST)

        # Collect additional fields (excluding reserved fields)
        reserved_fields = {'unique_link', 'email', 'names', 'documents'}
        additional_fields = {}
        for key in request.data:
            if key not in reserved_fields:
                value = request.data.getlist(key)[0] if isinstance(request.data.get(key), list) else request.data.get(key)
                additional_fields[key] = value
        logger.info(f"Additional fields: {additional_fields}")

        # Group files by compliance item name
        documents_data = []
        storage_type = getattr(settings, 'STORAGE_TYPE', 'supabase').lower()

        # Create a mapping of names to their corresponding files
        name_to_files = {}
        for i, name in enumerate(names):
            if i < len(files):
                if name not in name_to_files:
                    name_to_files[name] = []
                name_to_files[name].append(files[i])

        # Upload documents for each name
        for name, file_list in name_to_files.items():
            item = compliance_checklist[name]
            for file in file_list:
                file_ext = os.path.splitext(file.name)[1]
                filename = f"{uuid.uuid4()}{file_ext}"
                folder_path = f"compliance_documents/{timezone.now().strftime('%Y/%m/%d')}"
                file_path = f"{folder_path}/{filename}"
                content_type = mimetypes.guess_type(file.name)[0] or 'application/octet-stream'

                try:
                    public_url = upload_file_dynamic(file, file_path, content_type, storage_type)
                    documents_data.append({
                        'file_url': public_url,
                        'uploaded_at': timezone.now().isoformat(),
                        'doc_id': item['id'],
                        'name': name
                    })
                except Exception as e:
                    logger.error(f"Failed to upload document for {name}: {str(e)}")
                    return Response({"detail": f"Failed to upload document: {str(e)}"}, 
                                   status=status.HTTP_400_BAD_REQUEST)

        # Update compliance status
        updated_compliance_status = []
        for item in application.compliance_status:
            item_updated = False
            # Collect all documents for this item
            item_documents = [doc for doc in documents_data if doc['doc_id'] == item['id']]
            # Check if this item is in the provided names to apply additional_fields
            if item['name'] in names:
                # Merge existing metadata with new additional_fields
                existing_metadata = item.get('metadata', {})
                updated_metadata = {**existing_metadata, **additional_fields}
                if item_documents:
                    # Document uploaded
                    updated_item = {
                        'id': item['id'],
                        'name': item['name'],
                        'description': item.get('description', ''),
                        'required': item.get('required', True),
                        'requires_document': item.get('requires_document', True),
                        'status': 'uploaded',
                        'checked_by': item.get('checked_by'),
                        'checked_at': item.get('checked_at'),
                        'notes': item.get('notes', ''),
                        'document': [{'file_url': doc['file_url'], 'uploaded_at': doc['uploaded_at']} for doc in item_documents],
                        'metadata': updated_metadata
                    }
                    updated_compliance_status.append(updated_item)
                    item_updated = True
                    logger.info(f"Updated compliance item {item['id']} with {len(item_documents)} document(s) and metadata")
                else:
                    # No document, treat as metadata submission
                    updated_item = {
                        'id': item['id'],
                        'name': item['name'],
                        'description': item.get('description', ''),
                        'required': item.get('required', True),
                        'requires_document': item.get('requires_document', True),
                        'status': 'submitted' if not item.get('requires_document', True) else item.get('status', 'pending'),
                        'checked_by': item.get('checked_by'),
                        'checked_at': item.get('checked_at'),
                        'notes': item.get('notes', ''),
                        'document': item.get('document', []),
                        'metadata': updated_metadata
                    }
                    updated_compliance_status.append(updated_item)
                    item_updated = True
                    logger.info(f"Updated compliance item {item['id']} with metadata")
            
            # If not updated, keep the item as is
            if not item_updated:
                updated_compliance_status.append(item)

        # Save the updated application
        with transaction.atomic():
            application.compliance_status = updated_compliance_status
            application.save()

        # Refresh the instance to get the latest data
        application.refresh_from_db()

        return Response({
            "detail": "Compliance items processed successfully.",
            "compliance_status": application.compliance_status
        }, status=status.HTTP_200_OK)