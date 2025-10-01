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


# job_applications/views.py
from django.db import connection
from django.http import JsonResponse


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


import os
import tempfile
import mimetypes
import io
import gzip
import zipfile
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
import requests
from django.db import transaction, connection
from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from celery.result import AsyncResult
import logging

from .models import JobApplication
from .serializers import SimpleMessageSerializer
from utils.screen import (
    parse_resume, 
    screen_resume, 
    extract_resume_fields
)
from utils.email_utils import (
    send_screening_notification
)
from .tasks import process_large_resume_batch

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """
    Circuit breaker pattern to prevent cascading failures
    """
    def __init__(self, failure_threshold=5, recovery_timeout=60, expected_exceptions=()):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exceptions = expected_exceptions
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        
    def __call__(self, func):
        def wrapper(*args, **kwargs):
            if self.state == "OPEN":
                if self._is_ready_for_retry():
                    self.state = "HALF_OPEN"
                    logger.info(f"Circuit breaker moving to HALF_OPEN state")
                else:
                    raise Exception(f"Circuit breaker is OPEN. Service unavailable.")
            
            try:
                result = func(*args, **kwargs)
                self._record_success()
                return result
            except self.expected_exceptions as e:
                self._record_failure()
                raise e
                
        return wrapper
    
    def _record_success(self):
        """Record successful call and reset circuit"""
        self.failure_count = 0
        self.last_failure_time = None
        if self.state == "HALF_OPEN":
            self.state = "CLOSED"
            logger.info(f"Circuit breaker reset to CLOSED state")
    
    def _record_failure(self):
        """Record failed call and potentially open circuit"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")
    
    def _is_ready_for_retry(self):
        """Check if enough time has passed to allow a retry"""
        if self.last_failure_time is None:
            return True
            
        return (time.time() - self.last_failure_time) > self.recovery_timeout


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




class ResumeScreeningView(APIView):
    """
    Enhanced Resume Screening View with Circuit Breaker and Better Error Handling
    """
    serializer_class = SimpleMessageSerializer
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    # Constants
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    MAX_SYNC_PROCESSING = 10  # Reduced from 50 to prevent timeouts
    MAX_WORKERS = 5  # Reduced from 10 to manage resources better
    DOWNLOAD_TIMEOUT = (30, 300)  # (connect_timeout, read_timeout)

    # Circuit breaker for external service calls
    download_circuit_breaker = CircuitBreaker(
        failure_threshold=3, 
        recovery_timeout=300,
        expected_exceptions=(requests.RequestException,)
    )

    def post(self, request, job_requisition_id):
        """
        Screen resumes for a job requisition with enhanced error handling
        """
        try:
            # Validate database connection
            self._check_database_connection()

            # Extract JWT payload from middleware
            jwt_payload = getattr(request, 'jwt_payload', {})
            tenant_id = jwt_payload.get('tenant_unique_id')
            role = jwt_payload.get('role')
            branch = jwt_payload.get('user', {}).get('branch')

            if not tenant_id:
                return Response(
                    {"detail": "Tenant ID not found in token."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Parse request data
            document_type = request.data.get('document_type')
            applications_data = request.data.get('applications', [])
            num_candidates = request.data.get('number_of_candidates', 0)
            
            # Validate number of candidates
            try:
                num_candidates = int(num_candidates)
                if num_candidates < 0:
                    return Response(
                        {"detail": "Number of candidates must be non-negative."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except (TypeError, ValueError):
                num_candidates = 0

            # Get job requisition with timeout
            job_requisition = self._get_job_requisition_safe(job_requisition_id, request)
            if not job_requisition:
                return Response(
                    {"detail": "Job requisition not found."}, 
                    status=status.HTTP_404_NOT_FOUND
                )

            # Validate document type
            if not document_type:
                return Response(
                    {"detail": "Document type is required."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Validate document type against requisition
            document_validation = self._validate_document_type(document_type, job_requisition)
            if not document_validation["valid"]:
                return Response(
                    {"detail": document_validation["message"]},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Fetch applications if none provided
            if not applications_data:
                applications_data = self._fetch_applications_from_db(
                    job_requisition_id, tenant_id, role, branch
                )
                if not applications_data:
                    return Response(
                        {"detail": "No applications found for screening."},
                        status=status.HTTP_404_NOT_FOUND
                    )

            logger.info(f"Initiating resume screening for {len(applications_data)} applications")

            # Process synchronously for very small batches, asynchronously for others
            if len(applications_data) <= self.MAX_SYNC_PROCESSING:
                return self._process_synchronously(
                    request, job_requisition_id, job_requisition, tenant_id, 
                    role, branch, document_type, applications_data, num_candidates
                )
            else:
                # Process large batches asynchronously
                return self._process_asynchronously(
                    job_requisition_id, tenant_id, document_type, 
                    applications_data, num_candidates, role, branch, request
                )

        except Exception as e:
            logger.error(f"Error initiating resume screening: {str(e)}", exc_info=True)
            return Response({
                "error": "Failed to initiate resume screening",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _check_database_connection(self):
        """Verify database connection is alive"""
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except Exception as e:
            logger.error(f"Database connection error: {str(e)}")
            raise Exception("Database connection unavailable")

    def _get_job_requisition_safe(self, job_requisition_id, request):
        """Safely get job requisition with timeout handling"""
        try:
            return get_job_requisition_by_id(job_requisition_id, request)
        except requests.Timeout:
            logger.error(f"Timeout fetching job requisition {job_requisition_id}")
            raise Exception("Service timeout while fetching job requisition")
        except Exception as e:
            logger.error(f"Error fetching job requisition {job_requisition_id}: {str(e)}")
            raise Exception(f"Failed to fetch job requisition: {str(e)}")

    def _validate_document_type(self, document_type, job_requisition):
        """Validate document type against job requisition requirements"""
        document_type_lower = document_type.lower()
        allowed_docs = [doc.lower() for doc in (job_requisition.get('documents_required') or [])]
        allowed_docs.extend(['resume', 'curriculum vitae (cv)', 'cv'])
        
        if document_type_lower not in allowed_docs:
            return {
                "valid": False,
                "message": f"Invalid document type: {document_type}. Allowed types: {', '.join(allowed_docs)}"
            }
        
        return {"valid": True}

    def _fetch_applications_from_db(self, job_requisition_id, tenant_id, role, branch):
        """Fetch applications from database with role-based filtering"""
        try:
            applications = JobApplication.active_objects.filter(
                job_requisition_id=job_requisition_id,
                tenant_id=tenant_id,
                resume_status=True
            )
            
            # Apply role-based filtering
            if role == 'recruiter' and branch:
                applications = applications.filter(branch=branch)
            elif branch:
                applications = applications.filter(branch=branch)
                
            # Use iterator to prevent memory issues with large querysets
            applications_data = []
            for app in applications.iterator():
                applications_data.append({
                    "application_id": str(app.id),
                    "full_name": app.full_name,
                    "email": app.email
                })
                
            logger.info(f"Fetched {len(applications_data)} applications from database")
            return applications_data
            
        except Exception as e:
            logger.error(f"Error fetching applications from database: {str(e)}")
            raise Exception(f"Failed to fetch applications: {str(e)}")

    def _process_asynchronously(self, job_requisition_id, tenant_id, document_type, 
                              applications_data, num_candidates, role, branch, request):
        """Process large batches asynchronously using Celery"""
        try:
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
            logger.error(f"Error starting async task: {str(e)}")
            raise Exception(f"Failed to start background processing: {str(e)}")

    def _process_synchronously(self, request, job_requisition_id, job_requisition, tenant_id, 
                             role, branch, document_type, applications_data, num_candidates):
        """
        Process resume screening synchronously for small batches with transaction management
        """
        try:
            document_type_lower = document_type.lower()
            
            # Get application objects with proper filtering
            applications = self._get_applications_queryset(
                job_requisition_id, tenant_id, role, branch, applications_data
            )
            
            applications_list = list(applications)
            if not applications_list:
                return Response(
                    {"detail": "No valid applications found for processing."},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Download resumes using thread pool with circuit breaker
            download_results = []
            with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
                future_to_app = {
                    executor.submit(
                        self._download_resume_safe,
                        app,
                        applications_data,
                        document_type_lower
                    ): app for app in applications_list
                }
                
                for future in concurrent.futures.as_completed(future_to_app):
                    try:
                        result = future.result(timeout=300)  # 5-minute timeout per download
                        download_results.append(result)
                    except concurrent.futures.TimeoutError:
                        app = future_to_app[future]
                        logger.error(f"Download timeout for application {app.id}")
                        download_results.append({
                            "app": app,
                            "success": False,
                            "error": "Download timeout"
                        })

            # Process screening with job requirements
            job_requirements = self._get_job_requirements(job_requisition)
            results = []
            
            with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
                future_to_result = {
                    executor.submit(
                        self._parse_and_screen_safe,
                        result, 
                        job_requirements,
                        document_type
                    ): result for result in download_results
                }
                
                for future in concurrent.futures.as_completed(future_to_result):
                    try:
                        result = future.result(timeout=300)  # 5-minute timeout per processing
                        results.append(result)
                    except concurrent.futures.TimeoutError:
                        logger.error("Processing timeout for resume screening")
                        results.append({
                            "success": False,
                            "error": "Processing timeout"
                        })

            # Process results and send emails
            final_response = self._process_screening_results(
                results, applications_list, job_requisition, num_candidates, tenant_id
            )
            
            return Response(final_response, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Synchronous processing failed: {str(e)}", exc_info=True)
            return Response({
                "error": "Synchronous processing failed",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _get_applications_queryset(self, job_requisition_id, tenant_id, role, branch, applications_data):
        """Get applications queryset with proper filtering"""
        if applications_data:
            application_ids = [app['application_id'] for app in applications_data]
            applications = JobApplication.active_objects.filter(
                job_requisition_id=job_requisition_id,
                tenant_id=tenant_id,
                id__in=application_ids,
                resume_status=True
            )
        else:
            applications = JobApplication.active_objects.filter(
                job_requisition_id=job_requisition_id,
                tenant_id=tenant_id,
                resume_status=True
            )

        # Apply role-based filtering
        if role == 'recruiter' and branch:
            applications = applications.filter(branch=branch)
        elif branch:
            applications = applications.filter(branch=branch)
            
        return applications

    @download_circuit_breaker
    def _download_resume_safe(self, app, applications_data, document_type_lower):
        """
        Download resume with circuit breaker and enhanced error handling
        """
        temp_file_path = None
        try:
            # Get file information
            file_info = self._get_resume_file_info(app, applications_data, document_type_lower)
            if not file_info:
                return {
                    "app": app,
                    "success": False,
                    "error": f"No {document_type_lower} document found",
                }

            file_url, compression, original_name = file_info

            # Download file with timeout and size limits
            headers = {"Authorization": f"Bearer {os.environ.get('SUPABASE_KEY', '')}"}
            response = requests.get(
                file_url, 
                headers=headers, 
                timeout=self.DOWNLOAD_TIMEOUT, 
                stream=True
            )
            
            logger.debug(f"Download response for app {app.id}: status={response.status_code}")
            
            if response.status_code != 200:
                return {
                    "app": app,
                    "success": False,
                    "error": f"Failed to download resume, status: {response.status_code}",
                }

            # Stream download with size validation
            file_content = b''
            for chunk in response.iter_content(chunk_size=8192):
                file_content += chunk
                if len(file_content) > self.MAX_FILE_SIZE:
                    raise Exception(f"File size exceeds limit: {len(file_content)} bytes")
                    
            # Handle compression
            file_content = self._handle_compression_safe(file_content, compression, file_url, original_name, app.id)
            if file_content is None:
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
            temp_file_path = temp_file.name
            
            return {
                "app": app,
                "success": True,
                "temp_file_path": temp_file_path,
                "file_url": file_url,
                "original_name": original_name
            }
            
        except requests.exceptions.Timeout:
            logger.error(f"Download timeout for app {app.id}")
            return {
                "app": app,
                "success": False,
                "error": "Download timeout",
            }
        except requests.exceptions.ConnectionError:
            logger.error(f"Connection error for app {app.id}")
            return {
                "app": app,
                "success": False,
                "error": "Connection error",
            }
        except Exception as e:
            logger.error(f"Download failed for app {app.id}: {str(e)}")
            # Clean up temp file if created
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except:
                    pass
            return {
                "app": app,
                "success": False,
                "error": f"Download error: {str(e)}",
            }

    def _get_resume_file_info(self, app, applications_data, document_type_lower):
        """Extract resume file information from application data or documents"""
        # Try to get from applications_data first
        app_data = next((item for item in applications_data if item.get('application_id') == str(app.id)), None)
        if app_data and 'file_url' in app_data:
            return (
                app_data['file_url'],
                app_data.get('compression'),
                app_data.get('original_name', 'resume.pdf')
            )
        
        # Fall back to application documents
        if hasattr(app, 'documents') and app.documents:
            cv_doc = next(
                (doc for doc in app.documents if doc.get('document_type', '').lower() == document_type_lower),
                None
            )
            if cv_doc:
                return (
                    cv_doc.get('file_url'),
                    cv_doc.get('compression'),
                    cv_doc.get('original_name', 'resume.pdf')
                )
        
        return None

    def _handle_compression_safe(self, file_content, compression, file_url, original_name, app_id):
        """Handle file compression with comprehensive error handling"""
        try:
            # Detect compression if not provided
            if not compression:
                compression = self._detect_compression_format(file_content)
            
            # Handle different compression formats
            if compression == 'gzip' or file_url.endswith('.gz'):
                return self._handle_gzip_compression(file_content, app_id)
            elif compression == 'zip' or file_url.endswith('.zip'):
                return self._handle_zip_compression(file_content, app_id)
            elif compression == 'bzip2' or (file_content[:3] == b'BZh'):
                return self._handle_bzip2_compression(file_content, app_id)
            else:
                # No compression or unknown format
                return file_content
                
        except Exception as e:
            logger.error(f"Compression handling failed for app {app_id}: {str(e)}")
            return None

    def _handle_gzip_compression(self, file_content, app_id):
        """Handle GZIP compression"""
        try:
            decompressed = gzip.decompress(file_content)
            logger.info(f"Successfully decompressed GZIP file for app {app_id}")
            return decompressed
        except Exception as e:
            logger.error(f"GZIP decompression failed for app {app_id}: {str(e)}")
            # Check if it's actually GZIP
            if file_content[:2] == b'\x1f\x8b':
                raise Exception("File appears to be GZIP but decompression failed")
            return file_content

    def _handle_zip_compression(self, file_content, app_id):
        """Handle ZIP compression"""
        try:
            with zipfile.ZipFile(io.BytesIO(file_content)) as zip_file:
                # Look for resume files
                resume_files = []
                for name in zip_file.namelist():
                    if any(ext in name.lower() for ext in ['.pdf', '.doc', '.docx', '.txt', '.rtf']):
                        resume_files.append(name)
                
                if resume_files:
                    # Prefer PDF files
                    for preferred_ext in ['.pdf', '.docx', '.doc', '.txt', '.rtf']:
                        for name in resume_files:
                            if name.lower().endswith(preferred_ext):
                                with zip_file.open(name) as f:
                                    content = f.read()
                                    logger.info(f"Extracted {name} from ZIP for app {app_id}")
                                    return content
                    
                    # Fallback to first resume file
                    with zip_file.open(resume_files[0]) as f:
                        content = f.read()
                        logger.info(f"Extracted first resume file {resume_files[0]} from ZIP for app {app_id}")
                        return content
                else:
                    # If no obvious resume file, use first file
                    if zip_file.namelist():
                        with zip_file.open(zip_file.namelist()[0]) as f:
                            content = f.read()
                            logger.info(f"Extracted first file {zip_file.namelist()[0]} from ZIP for app {app_id}")
                            return content
                    else:
                        raise Exception("ZIP file is empty")
        except Exception as e:
            logger.error(f"ZIP decompression failed for app {app_id}: {str(e)}")
            return None

    def _handle_bzip2_compression(self, file_content, app_id):
        """Handle BZIP2 compression"""
        try:
            import bz2
            decompressed = bz2.decompress(file_content)
            logger.info(f"Successfully decompressed BZIP2 file for app {app_id}")
            return decompressed
        except Exception as e:
            logger.error(f"BZIP2 decompression failed for app {app_id}: {str(e)}")
            return None

    def _detect_compression_format(self, file_content):
        """Detect compression format from magic numbers"""
        if len(file_content) < 4:
            return None
            
        magic_numbers = {
            b'\x1f\x8b': 'gzip',
            b'PK\x03\x04': 'zip',
            b'BZh': 'bzip2',
            b'\xfd7zXZ': 'xz',
            b'\x50\x4b\x03\x04': 'zip',
            b'\x50\x4b\x05\x06': 'zip',
            b'\x50\x4b\x07\x08': 'zip',
        }
        
        for magic, format_name in magic_numbers.items():
            if file_content.startswith(magic):
                return format_name
        
        return None

    def _get_job_requirements(self, job_requisition):
        """Extract job requirements from requisition data"""
        return (
            (job_requisition.get('job_description') or '') + ' ' +
            (job_requisition.get('qualification_requirement') or '') + ' ' +
            (job_requisition.get('experience_requirement') or '') + ' ' +
            (job_requisition.get('knowledge_requirement') or '')
        ).strip()

    def _parse_and_screen_safe(self, result, job_requirements, document_type):
        """Parse resume and screen with comprehensive error handling"""
        app = result["app"]
        temp_file_path = result.get("temp_file_path")
        
        try:
            if not result["success"]:
                return {
                    "application_id": str(app.id),
                    "full_name": app.full_name,
                    "email": app.email,
                    "error": result["error"],
                    "success": False
                }

            # Parse resume text
            resume_text = parse_resume(temp_file_path)
            
            # Clean up temporary file immediately after parsing
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except Exception as e:
                    logger.warning(f"Failed to delete temp file {temp_file_path}: {str(e)}")
                
            if not resume_text:
                with transaction.atomic():
                    app.screening_status = 'failed'
                    app.screening_score = 0.0
                    app.save()
                return {
                    "application_id": str(app.id),
                    "full_name": app.full_name,
                    "email": app.email,
                    "error": "Failed to parse resume",
                    "success": False
                }

            # Screen resume and extract fields
            score = screen_resume(resume_text, job_requirements)
            resume_data = extract_resume_fields(resume_text, result.get("original_name", ""))
            employment_gaps = resume_data.get("employment_gaps", [])
            
            # Update application with screening results
            with transaction.atomic():
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
            logger.error(f"Processing failed for app {app.id}: {str(e)}")
            # Clean up temporary file in case of error
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except:
                    pass
                    
            with transaction.atomic():
                app.screening_status = 'failed'
                app.screening_score = 0.0
                app.save()
                
            return {
                "application_id": str(app.id),
                "full_name": app.full_name,
                "email": app.email,
                "error": f"Processing error: {str(e)}",
                "success": False
            }

    def _process_screening_results(self, results, applications, job_requisition, num_candidates, tenant_id):
        """Process screening results and send notifications with transaction safety"""
        try:
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
                    with transaction.atomic():
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
                        
                        try:
                            send_screening_notification(
                                applicant=applicant_data,
                                tenant_id=tenant_id,
                                event_type=event_type,
                                employment_gaps=employment_gaps
                            )
                        except Exception as e:
                            logger.error(f"Failed to send notification for app {app_id_str}: {str(e)}")
                else:
                    # Update to rejected
                    with transaction.atomic():
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
                    
                    try:
                        send_screening_notification(
                            applicant=rejected_app, 
                            tenant_id=tenant_id, 
                            event_type="candidate.rejected"
                        )
                    except Exception as e:
                        logger.error(f"Failed to send rejection notification for app {app_id_str}: {str(e)}")

            return {
                "detail": f"Screened {len(shortlisted)} applications, shortlisted {len(final_shortlisted)} candidates.",
                "shortlisted_candidates": final_shortlisted,
                "failed_applications": failed_applications,
                "number_of_candidates": num_candidates,
                "document_type": "resume"
            }
            
        except Exception as e:
            logger.error(f"Error processing screening results: {str(e)}")
            raise Exception(f"Failed to process screening results: {str(e)}")




class ScreeningTaskStatusView(APIView):
    """
    Enhanced Check status of async screening tasks with circuit breaker
    """
    
    def get(self, request, task_id):
        try:
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
            
        except Exception as e:
            logger.error(f"Error checking task status {task_id}: {str(e)}")
            return Response({
                'error': 'Failed to check task status',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


