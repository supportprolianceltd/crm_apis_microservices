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
from .tasks import (
    process_large_resume_batch
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
from .tasks import process_large_resume_batch, _append_status_history, send_notification_task

logger = logging.getLogger(__name__)

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




class GlobalApplicationsByRequisitionView(APIView):
    """
    Internal view to fetch all applications for a requisition (cross-tenant, for future use).
    No auth required.
    """
    permission_classes = []

    def get(self, request, job_requisition_id):
        applications = JobApplication.active_objects.filter(
            job_requisition_id=job_requisition_id,
            resume_status=True
        )
        serializer = JobApplicationSerializer(applications, many=True)
        return Response({
            "count": applications.count(),
            "results": serializer.data
        }, status=status.HTTP_200_OK)
    

class HealthCheckView(View):
    def get(self, request):
        health_data = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "service": "job-applications",
            "version": "1.0.0"
        }
        return JsonResponse(health_data)


# class CustomPagination(PageNumberPagination):
#     page_size = 20


from rest_framework.pagination import PageNumberPagination
from django.conf import settings
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

class CustomPagination(PageNumberPagination):
    page_size = 50  # Adjust as needed

    def get_next_link(self):
        """Override to use gateway base URL."""
        if not self.page.has_next():
            return None
        gateway_url = getattr(settings, 'GATEWAY_URL', None)
        if not gateway_url:
            return super().get_next_link()  # Fallback to default

        request = self.request
        # Build base path from current request (e.g., /api/user/users/)
        path = request.path
        # Get query params, update 'page', preserve others
        query_params = request.query_params.copy()
        query_params['page'] = self.page.next_page_number()
        query_string = urlencode(query_params, doseq=True)

        # Reconstruct full URL with gateway scheme/host
        parsed_gateway = urlparse(gateway_url)
        full_url = f"{parsed_gateway.scheme}://{parsed_gateway.netloc}{path}?{query_string}"
        return full_url

    def get_previous_link(self):
        """Override to use gateway base URL."""
        if not self.page.has_previous():
            return None
        gateway_url = getattr(settings, 'GATEWAY_URL', None)
        if not gateway_url:
            return super().get_previous_link()  # Fallback to default

        request = self.request
        path = request.path
        query_params = request.query_params.copy()
        query_params['page'] = self.page.previous_page_number()
        query_string = urlencode(query_params, doseq=True)

        parsed_gateway = urlparse(gateway_url)
        full_url = f"{parsed_gateway.scheme}://{parsed_gateway.netloc}{path}?{query_string}"
        return full_url

    def get_paginated_response(self, data):
        """Ensure the full response uses overridden links."""
        response = super().get_paginated_response(data)
        gateway_url = getattr(settings, 'GATEWAY_URL', None)
        if gateway_url:
            response['next'] = self.get_next_link()
            response['previous'] = self.get_previous_link()
        return response



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
    Enhanced Resume Screening View with Better Error Handling
    """
    serializer_class = SimpleMessageSerializer
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    # Constants
    MAX_SYNC_PROCESSING = 10  # Reduced from 50 to prevent timeouts
    MAX_WORKERS = 5  # Reduced from 10 to manage resources better

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

            # Always fetch applications from database
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
        total_start_time = time.perf_counter()
        per_app_timings = []  # To collect per-app times for response
        try:
            # Get application objects with proper filtering
            applications = self._get_applications_queryset(
                job_requisition_id, tenant_id, role, branch, applications_data
            )
            
            applications_list = list(applications)
            if not applications_list:
                total_end_time = time.perf_counter()
                total_time = total_end_time - total_start_time
                return Response({
                    "detail": "No valid applications found for processing.",
                    "timing_summary": {
                        "total_screening_time_seconds": round(total_time, 2),
                        "applications_processed": 0,
                        "per_application_timings": []
                    }
                }, status=status.HTTP_404_NOT_FOUND)

            # Process screening with job requirements
            job_requirements = self._get_job_requirements(job_requisition)
            results = []
            
            with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
                future_to_app = {
                    executor.submit(
                        self._screen_from_model_safe,
                        app, 
                        job_requirements,
                        document_type
                    ): app for app in applications_list
                }
                
                for future in concurrent.futures.as_completed(future_to_app):
                    try:
                        result = future.result(timeout=300)  # 5-minute timeout per processing
                        results.append(result)
                        # Collect per-app timing if available
                        if 'total_vetting_time' in result:
                            per_app_timings.append(result['total_vetting_time'])
                    except concurrent.futures.TimeoutError:
                        app = future_to_app[future]
                        logger.error("Processing timeout for resume screening")
                        results.append({
                            "application_id": str(app.id),
                            "full_name": app.full_name,
                            "email": app.email,
                            "success": False,
                            "error": "Processing timeout"
                        })

            # Process results and queue emails
            final_response_base = self._process_screening_results(
                results, applications_list, job_requisition, num_candidates, tenant_id
            )
            
            total_end_time = time.perf_counter()
            total_time = total_end_time - total_start_time
            
            # Enhanced visible logging for total time
            # Enhanced visible logging for total time
            logger.warning("=" * 80)
            logger.warning(f"🚀 SYNCHRONOUS SCREENING COMPLETED 🚀")
            logger.warning(f"📊 TOTAL TIME FOR {len(applications_list)} APPLICATIONS: {total_time:.2f} SECONDS")
            logger.warning(f"⏱️  AVERAGE PER APPLICATION: {total_time / len(applications_list):.2f} SECONDS" if applications_list else "⏱️  AVERAGE PER APPLICATION: N/A")

            if per_app_timings:
                times = [t['total_seconds'] for t in per_app_timings]
                logger.warning(f"📈 PER-APP TIMINGS SUMMARY: MIN={min(times):.2f}s, MAX={max(times):.2f}s, AVG={sum(times)/len(times):.2f}s")
            else:
                logger.warning("📈 PER-APP TIMINGS SUMMARY: No successful vetting")
            logger.warning("=" * 80)
            
            # Add timing to response
            final_response = final_response_base.copy()
            final_response["timing_summary"] = {
                "total_screening_time_seconds": round(total_time, 2),
                "applications_processed": len(applications_list),
                "per_application_timings": per_app_timings,  # List of dicts with app_id and time
                "average_per_application_seconds": round(total_time / len(applications_list), 2) if applications_list else 0
            }
            
            return Response(final_response, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Synchronous processing failed: {str(e)}", exc_info=True)
            total_end_time = time.perf_counter()
            total_time = total_end_time - total_start_time
            logger.warning("=" * 80)
            logger.warning(f"💥 SYNCHRONOUS SCREENING FAILED 💥")
            logger.warning(f"⏱️  TOTAL ELAPSED TIME: {total_time:.2f} SECONDS")
            logger.warning("=" * 80)
            return Response({
                "error": "Synchronous processing failed",
                "details": str(e),
                "timing_summary": {
                    "total_screening_time_seconds": round(total_time, 2),
                    "applications_processed": 0,
                    "per_application_timings": []
                }
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

    def _get_job_requirements(self, job_requisition):
        """Extract job requirements from requisition data"""
        return (
            (job_requisition.get('job_description') or '') + ' ' +
            (job_requisition.get('qualification_requirement') or '') + ' ' +
            (job_requisition.get('experience_requirement') or '') + ' ' +
            (job_requisition.get('knowledge_requirement') or '')
        ).strip()

    def _screen_from_model_safe(self, app, job_requirements, document_type):
        """Screen resume using model fields with comprehensive error handling"""
        processing_start = time.perf_counter()
        
        try:
            # Construct resume text from model fields
            resume_text = (
                f"{app.qualification or ''} "
                f"{app.experience or ''} "
                f"{app.knowledge_skill or ''} "
                f"{app.cover_letter or ''}"
            ).strip()
            
            if not resume_text:
                now = timezone.now().isoformat()
                with transaction.atomic():
                    app.screening_status = [{'status': 'failed', 'score': 0.0, 'updated_at': now, 'error': 'No resume data available in model fields'}]
                    app.screening_score = 0.0
                    app.save(update_fields=['screening_status', 'screening_score'])
                processing_end = time.perf_counter()
                processing_time = processing_end - processing_start
                total_time = processing_time
                total_vetting_time = {
                    "application_id": str(app.id),
                    "total_seconds": round(total_time, 2),
                    "processing_seconds": round(processing_time, 2),
                    "status": "no_data"
                }
                logger.warning(f"📄 NO DATA - App {app.id}: TOTAL {total_time:.2f}s (PROC: {processing_time:.2f}s)")
                return {
                    "application_id": str(app.id),
                    "full_name": app.full_name,
                    "email": app.email,
                    "error": "No resume data available in model fields",
                    "success": False,
                    "total_vetting_time": total_vetting_time
                }

            # Screen resume
            score = screen_resume(resume_text, job_requirements)
            employment_gaps = getattr(app, 'employment_gaps', [])
            now = timezone.now().isoformat()
            
            # Update application with screening results
            with transaction.atomic():
                app.screening_status = [{'status': 'processed', 'score': score, 'updated_at': now}]
                app.screening_score = score
                if not employment_gaps:  # Only set if empty
                    app.employment_gaps = employment_gaps
                app.save(update_fields=['screening_status', 'screening_score', 'employment_gaps'])
            
            processing_end = time.perf_counter()
            processing_time = processing_end - processing_start
            total_time = processing_time
            total_vetting_time = {
                "application_id": str(app.id),
                "total_seconds": round(total_time, 2),
                "processing_seconds": round(processing_time, 2),
                "status": "success"
            }
            logger.info(f"✅ VETTING SUCCESS - App {app.id} (Score: {score:.1f}): TOTAL {total_time:.2f}s (PROC: {processing_time:.2f}s)")
            
            return {
                "application_id": str(app.id),
                "full_name": app.full_name,
                "email": app.email,
                "score": score,
                "screening_status": 'processed',
                "employment_gaps": employment_gaps,
                "success": True,
                "total_vetting_time": total_vetting_time
            }
            
        except Exception as e:
            logger.error(f"Processing failed for app {app.id}: {str(e)}")
            now = timezone.now().isoformat()        
            with transaction.atomic():
                app.screening_status = [{'status': 'failed', 'score': 0.0, 'updated_at': now, 'error': f"Processing error: {str(e)}"}]
                app.screening_score = 0.0
                app.save(update_fields=['screening_status', 'screening_score'])
            processing_end = time.perf_counter()
            processing_time = processing_end - processing_start
            total_time = processing_time
            total_vetting_time = {
                "application_id": str(app.id),
                "total_seconds": round(total_time, 2),
                "processing_seconds": round(processing_time, 2),
                "status": "processing_error"
            }
            logger.warning(f"⚠️  VETTING ERROR - App {app.id} ({str(e)[:50]}...): TOTAL {total_time:.2f}s (PROC: {processing_time:.2f}s)")
                
            return {
                "application_id": str(app.id),
                "full_name": app.full_name,
                "email": app.email,
                "error": f"Processing error: {str(e)}",
                "success": False,
                "total_vetting_time": total_vetting_time
            }
        
    
    def _process_screening_results(self, results, applications, job_requisition, num_candidates, tenant_id):
        """Process screening results and queue notifications with transaction safety"""
        try:
            shortlisted = [r for r in results if r.get("success")]
            failed_applications = [r for r in results if not r.get("success")]

            # Handle case where all screenings failed
            if not shortlisted and failed_applications:
                return {
                    "detail": "All resume screenings failed.",
                    "failed_applications": failed_applications,
                    "document_type": "resume",
                    "timing_summary": {
                        "total_screening_time_seconds": 0,
                        "applications_processed": 0,
                        "per_application_timings": []
                    }
                }

            # Sort by score and select top candidates
            shortlisted.sort(key=lambda x: x['score'], reverse=True)
            final_shortlisted = shortlisted[:num_candidates] if num_candidates > 0 else shortlisted
            shortlisted_ids = {item['application_id'] for item in final_shortlisted}

            # Update application statuses and queue emails
            for app in applications:
                app_id_str = str(app.id)
                if app_id_str in shortlisted_ids:
                    # Update to shortlisted
                    new_status = 'shortlisted'
                    _append_status_history(app, new_status, automated=True, reason='Automated by resume screening')
                    with transaction.atomic():
                        app.status = new_status
                        app.current_stage = 'screening'  # Sync stage after screening
                        app.save(update_fields=['status', 'current_stage', 'status_history'])
                    
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
                        
                        # Queue notification with employment gaps info if any
                        employment_gaps = shortlisted_app.get('employment_gaps', [])
                        event_type = "candidate.shortlisted.gaps" if employment_gaps else "candidate.shortlisted"
                        
                        send_notification_task.delay(
                            applicant_data=applicant_data,
                            tenant_id=tenant_id,
                            event_type=event_type,
                            employment_gaps=employment_gaps
                        )
                        logger.info(f"Queued shortlisted notification for {applicant_data['email']}")
                else:
                    # Update to rejected
                    new_status = 'rejected'
                    _append_status_history(app, new_status, automated=True, reason='Automated by resume screening')
                    with transaction.atomic():
                        app.status = new_status
                        app.current_stage = 'screening'  # Sync stage after screening
                        app.save(update_fields=['status', 'current_stage', 'status_history'])
                    
                    # Queue rejection notification
                    rejected_app = {
                        "email": app.email,
                        "full_name": app.full_name,
                        "application_id": app_id_str,
                        "job_requisition_id": job_requisition['id'],
                        "status": "rejected",
                        "score": getattr(app, "screening_score", None)
                    }
                    
                    send_notification_task.delay(
                        applicant_data=rejected_app, 
                        tenant_id=tenant_id, 
                        event_type="candidate.rejected"
                    )
                    logger.info(f"Queued rejection notification for {rejected_app['email']}")

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
    
    def get_permissions(self):
        return [AllowAny()]

    def get_queryset(self):
        try:
            # Close any stale connections first
            from django.db import close_old_connections
            close_old_connections()
            
            jwt_payload = getattr(self.request, 'jwt_payload', {})
            tenant_id = jwt_payload.get('tenant_unique_id')
            role = jwt_payload.get('role')
            branch = jwt_payload.get('user', {}).get('branch')
            job_requisition_id = self.kwargs['job_requisition_id']
            
            if not tenant_id:
                logger.error("No tenant_id in token")
                return JobApplication.active_objects.none()
            
            # Create a fresh queryset
            queryset = JobApplication.active_objects.filter(
                job_requisition_id=job_requisition_id,
                tenant_id=tenant_id
            )
            
            if role == 'recruiter' and branch:
                queryset = queryset.filter(branch=branch)
            elif branch:
                queryset = queryset.filter(branch=branch)
            
            return queryset.order_by('-created_at')
            
        except Exception as e:
            logger.error(f"Error in get_queryset: {str(e)}")
            # Return empty queryset on error
            return JobApplication.active_objects.none()



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
        # FIX: Use request.jwt_payload instead of self.request.jwt_payload
        tenant_id = jwt_payload.get('tenant_unique_id')
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



# class ComplianceStatusUpdateView(APIView):
#     permission_classes = [AllowAny]  # Temporary for testing; replace with IsAuthenticated in production
#     parser_classes = [JSONParser]

#     def post(self, request, job_application_id):
#         # Extract item_id from request body
#         item_id = request.data.get('item_id')
#         if not item_id:
#             logger.warning("No item_id provided in request data")
#             return Response({"detail": "Item ID is required."}, status=status.HTTP_400_BAD_REQUEST)

#         # Extract user data from JWT
#         try:
#             user_data = get_user_data_from_jwt(request)
#             user_id = user_data.get('id')
#             branch = user_data.get('branch')  # May be null based on JWT
#             checked_by = {
#                 'email': user_data.get('email', ''),
#                 'first_name': user_data.get('first_name', ''),
#                 'last_name': user_data.get('last_name', ''),
#                 'job_role': user_data.get('job_role', '')
#             }
#         except Exception as e:
#             logger.error(f"Failed to extract user data from JWT: {str(e)}")
#             return Response({"detail": "Invalid JWT token for user data."}, status=status.HTTP_401_UNAUTHORIZED)

#         if not user_id:
#             logger.warning("No user.id found in JWT payload for status update")
#             return Response({"detail": "Authentication required for status update."}, status=status.HTTP_401_UNAUTHORIZED)

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

#         # Fetch the job application
#         try:
#             application = JobApplication.active_objects.get(id=job_application_id)
#         except JobApplication.DoesNotExist:
#             logger.warning(f"Job application not found: {job_application_id}")
#             return Response({"detail": "Job application not found."}, status=status.HTTP_404_NOT_FOUND)

#         # Check branch authorization if branch is provided
#         if branch and application.branch_id != branch:
#             try:
#                 from .models import Branch  # Adjust import based on your project
#                 branch_exists = Branch.objects.filter(id=application.branch_id, tenant_id=application.tenant_id).exists()
#                 if not branch_exists:
#                     logger.warning(f"Invalid branch {application.branch_id} for application {job_application_id}")
#                     return Response({"detail": "Invalid branch for this application."}, status=status.HTTP_403_FORBIDDEN)
#                 if str(application.branch_id) != str(branch):
#                     logger.warning(f"User not authorized to access application {job_application_id} for branch {branch}")
#                     return Response({"detail": "Not authorized to access this application."}, status=status.HTTP_403_FORBIDDEN)
#             except ImportError:
#                 logger.warning(f"Branch validation skipped: No Branch model available for branch_id {application.branch_id}")
#                 # Optionally raise an error if branch validation is critical
#                 # return Response({"detail": "Branch validation not supported without local Branch model."}, status=status.HTTP_400_BAD_REQUEST)

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
#                 if 'status' in update_data:
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

        # NEW: Wrap entire DB logic in atomic() + explicit tenant_context to prevent cursor issues
        try:
            with transaction.atomic():
                # Ensure tenant context (from request or middleware)
                tenant = getattr(request, 'tenant', None)
                if tenant:
                    with tenant_context(tenant):
                        return self._perform_update(job_application_id, item_id, update_data, checked_by, branch, request)
                else:
                    logger.error("No tenant context available")
                    return Response({"detail": "Tenant context missing."}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Transaction failed in ComplianceStatusUpdateView: {str(e)}")
            if "cursor" in str(e).lower():
                logger.error("Cursor closed error - check connection pooling or schema switching")
            return Response({"detail": "Database operation failed."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _perform_update(self, job_application_id, item_id, update_data, checked_by, branch, request):
        # Fetch the job application (now inside atomic)
        try:
            application = JobApplication.active_objects.get(id=job_application_id)
        except JobApplication.DoesNotExist:
            logger.warning(f"Job application not found: {job_application_id}")
            raise JobApplication.DoesNotExist  # Re-raise for atomic rollback

        # Check branch authorization if branch is provided
        if branch and application.branch_id != branch:
            try:
                branch_exists = Branch.objects.filter(id=application.branch_id, tenant_id=application.tenant_id).exists()
                if not branch_exists:
                    logger.warning(f"Invalid branch {application.branch_id} for application {job_application_id}")
                    raise PermissionDenied("Invalid branch for this application.")
                if str(application.branch_id) != str(branch):
                    logger.warning(f"User not authorized to access application {job_application_id} for branch {branch}")
                    raise PermissionDenied("Not authorized to access this application.")
            except ImportError:
                logger.warning(f"Branch validation skipped: No Branch model available for branch_id {application.branch_id}")

        # Update compliance_status
        updated_compliance_status = application.compliance_status.copy() if application.compliance_status else []
        item_updated = False

        for item in updated_compliance_status:
            if str(item.get('id')) == str(item_id):
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
            raise ValueError(f"Compliance item {item_id} not found.")

        # Save the updated application (inside atomic)
        application.compliance_status = updated_compliance_status
        application.save()
        logger.info(f"Job application {job_application_id} saved with updated compliance status")

        serializer = JobApplicationSerializer(application, context={'request': request})
        return Response({
            "detail": "Compliance status updated successfully.",
            "compliance_item": next((item for item in serializer.data['compliance_status'] if str(item['id']) == str(item_id)), None)
        }, status=status.HTTP_200_OK)


# class ApplicantComplianceUploadView(APIView):
#     permission_classes = [AllowAny]
#     parser_classes = (MultiPartParser, FormParser, JSONParser)

#     def post(self, request, job_application_id):
#         return self._handle_upload(request, job_application_id)

#     def _handle_upload(self, request, job_application_id):
#         logger.info(f"Request data: {request.data}")
#         unique_link = request.data.get('unique_link')
#         email = request.data.get('email')
#         names = request.data.getlist('names', [])  # List of compliance item names, optional
#         files = request.FILES.getlist('documents', [])  # List of uploaded files, optional

#         # Validate required fields
#         if not unique_link:
#             return Response({"detail": "Missing job requisition unique link."}, status=status.HTTP_400_BAD_REQUEST)
#         if not email:
#             return Response({"detail": "Missing email."}, status=status.HTTP_400_BAD_REQUEST)

#         # Extract tenant_id from unique_link
#         try:
#             parts = unique_link.split('-')
#             if len(parts) < 6:
#                 return Response({"detail": "Invalid unique link format."}, status=status.HTTP_400_BAD_REQUEST)
#             tenant_id = '-'.join(parts[:5])
#         except Exception as e:
#             logger.error(f"Error extracting tenant_id from {unique_link}: {str(e)}")
#             return Response({"detail": "Failed to extract tenant ID."}, status=status.HTTP_400_BAD_REQUEST)

#         # Fetch job requisition
#         try:
#             requisition_url = f"{settings.TALENT_ENGINE_URL}/api/talent-engine/requisitions/by-link/{unique_link}/"
#             resp = requests.get(requisition_url)
#             if resp.status_code != 200:
#                 return Response({"detail": "Invalid job requisition."}, status=status.HTTP_400_BAD_REQUEST)
#             job_requisition = resp.json()
#         except Exception as e:
#             logger.error(f"Error fetching job requisition: {str(e)}")
#             return Response({"detail": "Unable to fetch job requisition."}, status=status.HTTP_502_BAD_GATEWAY)

#         # Retrieve job application
#         try:
#             application = JobApplication.active_objects.get(
#                 id=job_application_id,
#                 tenant_id=tenant_id,
#                 job_requisition_id=job_requisition['id'],
#                 email=email
#             )
#         except JobApplication.DoesNotExist:
#             return Response({"detail": "Job application not found."}, status=status.HTTP_404_NOT_FOUND)

#         # Initialize or update compliance_status with checklist items
#         checklist = job_requisition.get('compliance_checklist', [])
#         if not application.compliance_status or len(application.compliance_status) == 0:
#             application.compliance_status = []
#         # Ensure all checklist items are in compliance_status
#         checklist_names = {item['name'] for item in checklist}
#         existing_names = {item['name'] for item in application.compliance_status}
#         for item in checklist:
#             name = item.get('name', '')
#             if not name or name in existing_names:
#                 continue
#             generated_id = f"compliance-{slugify(name)}"
#             application.compliance_status.append({
#                 'id': generated_id,
#                 'name': name,
#                 'description': item.get('description', ''),
#                 'required': item.get('required', True),
#                 'requires_document': item.get('requires_document', True),
#                 'status': 'pending',
#                 'checked_by': None,
#                 'checked_at': None,
#                 'notes': '',
#                 'document': [],  # Initialize as list to support multiple documents
#                 'metadata': {}
#             })
#         application.save()
#         application.refresh_from_db()

#         # If no compliance checklist, return success
#         if not checklist:
#             return Response({
#                 "detail": "No compliance items required for this requisition.",
#                 "compliance_status": application.compliance_status
#             }, status=status.HTTP_200_OK)

#         # Map compliance item names to their details
#         compliance_checklist = {item['name']: item for item in application.compliance_status}

#         # Validate provided names against checklist
#         for name in names:
#             if name not in checklist_names:
#                 return Response({"detail": f"Invalid compliance item name: {name}. Must match checklist."}, 
#                                status=status.HTTP_400_BAD_REQUEST)

#         # Collect additional fields (excluding reserved fields)
#         reserved_fields = {'unique_link', 'email', 'names', 'documents'}
#         additional_fields = {}
#         for key in request.data:
#             if key not in reserved_fields:
#                 value = request.data.getlist(key)[0] if isinstance(request.data.get(key), list) else request.data.get(key)
#                 additional_fields[key] = value
#         logger.info(f"Additional fields: {additional_fields}")

#         # Group files by compliance item name
#         documents_data = []
#         storage_type = getattr(settings, 'STORAGE_TYPE', 'supabase').lower()

#         # Create a mapping of names to their corresponding files
#         name_to_files = {}
#         for i, name in enumerate(names):
#             if i < len(files):
#                 if name not in name_to_files:
#                     name_to_files[name] = []
#                 name_to_files[name].append(files[i])

#         # Upload documents for each name
#         for name, file_list in name_to_files.items():
#             item = compliance_checklist[name]
#             for file in file_list:
#                 file_ext = os.path.splitext(file.name)[1]
#                 filename = f"{uuid.uuid4()}{file_ext}"
#                 folder_path = f"compliance_documents/{timezone.now().strftime('%Y/%m/%d')}"
#                 file_path = f"{folder_path}/{filename}"
#                 content_type = mimetypes.guess_type(file.name)[0] or 'application/octet-stream'

#                 try:
#                     public_url = upload_file_dynamic(file, file_path, content_type, storage_type)
#                     documents_data.append({
#                         'file_url': public_url,
#                         'uploaded_at': timezone.now().isoformat(),
#                         'doc_id': item['id'],
#                         'name': name
#                     })
#                 except Exception as e:
#                     logger.error(f"Failed to upload document for {name}: {str(e)}")
#                     return Response({"detail": f"Failed to upload document: {str(e)}"}, 
#                                    status=status.HTTP_400_BAD_REQUEST)

#         # Update compliance status
#         updated_compliance_status = []
#         for item in application.compliance_status:
#             item_updated = False
#             # Collect all documents for this item
#             item_documents = [doc for doc in documents_data if doc['doc_id'] == item['id']]
#             # Check if this item is in the provided names to apply additional_fields
#             if item['name'] in names:
#                 # Merge existing metadata with new additional_fields
#                 existing_metadata = item.get('metadata', {})
#                 updated_metadata = {**existing_metadata, **additional_fields}
#                 if item_documents:
#                     # Document uploaded
#                     updated_item = {
#                         'id': item['id'],
#                         'name': item['name'],
#                         'description': item.get('description', ''),
#                         'required': item.get('required', True),
#                         'requires_document': item.get('requires_document', True),
#                         'status': 'uploaded',
#                         'checked_by': item.get('checked_by'),
#                         'checked_at': item.get('checked_at'),
#                         'notes': item.get('notes', ''),
#                         'document': [{'file_url': doc['file_url'], 'uploaded_at': doc['uploaded_at']} for doc in item_documents],
#                         'metadata': updated_metadata
#                     }
#                     updated_compliance_status.append(updated_item)
#                     item_updated = True
#                     logger.info(f"Updated compliance item {item['id']} with {len(item_documents)} document(s) and metadata")
#                 else:
#                     # No document, treat as metadata submission
#                     # Always set to 'submitted' if metadata is present (submit=true)
#                     new_status = 'submitted' if 'submit' in updated_metadata else item.get('status', 'pending')
#                     updated_item = {
#                         'id': item['id'],
#                         'name': item['name'],
#                         'description': item.get('description', ''),
#                         'required': item.get('required', True),
#                         'requires_document': item.get('requires_document', True),
#                         'status': new_status,
#                         'checked_by': item.get('checked_by'),
#                         'checked_at': item.get('checked_at'),
#                         'notes': item.get('notes', ''),
#                         'document': item.get('document', []),
#                         'metadata': updated_metadata
#                     }
#                     updated_compliance_status.append(updated_item)
#                     item_updated = True
#                     logger.info(f"Updated compliance item {item['id']} with metadata (status set to '{new_status}')")
            
#             # If not updated, keep the item as is
#             if not item_updated:
#                 updated_compliance_status.append(item)

#         # Save the updated application
#         with transaction.atomic():
#             application.compliance_status = updated_compliance_status
#             application.save()

#         # Refresh the instance to get the latest data
#         application.refresh_from_db()

#         return Response({
#             "detail": "Compliance items processed successfully.",
#             "compliance_status": application.compliance_status
#         }, status=status.HTTP_200_OK)



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
            return Response({"detail": "Missing email."}, status=status.HTTP_400_BAD_GATEWAY)

        # Extract tenant_id from unique_link
        try:
            parts = unique_link.split('-')
            if len(parts) < 6:
                return Response({"detail": "Invalid unique link format."}, status=status.HTTP_400_BAD_REQUEST)
            tenant_id = '-'.join(parts[:5])
        except Exception as e:
            logger.error(f"Error extracting tenant_id from {unique_link}: {str(e)}")
            return Response({"detail": "Failed to extract tenant ID."}, status=status.HTTP_400_BAD_REQUEST)

        # NEW: Fetch job requisition OUTSIDE atomic (external call)
        try:
            requisition_url = f"{settings.TALENT_ENGINE_URL}/api/talent-engine/requisitions/by-link/{unique_link}/"
            resp = requests.get(requisition_url)
            if resp.status_code != 200:
                return Response({"detail": "Invalid job requisition."}, status=status.HTTP_400_BAD_REQUEST)
            job_requisition = resp.json()
        except Exception as e:
            logger.error(f"Error fetching job requisition: {str(e)}")
            return Response({"detail": "Unable to fetch job requisition."}, status=status.HTTP_502_BAD_GATEWAY)

        # Collect additional fields (excluding reserved fields)
        reserved_fields = {'unique_link', 'email', 'names', 'documents'}
        additional_fields = {}
        for key in request.data:
            if key not in reserved_fields:
                value = request.data.getlist(key)[0] if isinstance(request.data.get(key), list) else request.data.get(key)
                additional_fields[key] = value
        logger.info(f"Additional fields: {additional_fields}")

        # NEW: Wrap DB + upload logic in atomic() + tenant_context
        try:
            with transaction.atomic():
                # Ensure tenant context
                tenant = getattr(request, 'tenant', None)
                if not tenant or str(tenant.id) != tenant_id:
                    # Resolve tenant if mismatch (from tenant_id)
                    from core.models import Tenant
                    tenant = Tenant.objects.get(id=tenant_id)
                with tenant_context(tenant):
                    return self._process_compliance(job_application_id, email, job_requisition, names, files, additional_fields, tenant)
        except Exception as e:
            logger.error(f"Transaction failed in ApplicantComplianceUploadView: {str(e)}")
            if "cursor" in str(e).lower():
                logger.error("Cursor closed error - check connection pooling or schema switching")
            return Response({"detail": "Database operation failed."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _process_compliance(self, job_application_id, email, job_requisition, names, files, additional_fields, tenant):
        # Retrieve job application (inside atomic)
        try:
            application = JobApplication.active_objects.get(
                id=job_application_id,
                tenant_id=tenant.id,
                job_requisition_id=job_requisition['id'],
                email=email
            )
        except JobApplication.DoesNotExist:
            raise JobApplication.DoesNotExist  # For rollback

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
        # REMOVED: application.save() here - defer to end

        # If no compliance checklist, return success
        if not checklist:
            application.save()  # Safe single save
            return Response({
                "detail": "No compliance items required for this requisition.",
                "compliance_status": application.compliance_status
            }, status=status.HTTP_200_OK)

        # Map compliance item names to their details
        compliance_checklist = {item['name']: item for item in application.compliance_status}

        # Validate provided names against checklist
        for name in names:
            if name not in checklist_names:
                raise ValueError(f"Invalid compliance item name: {name}. Must match checklist.")

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

        # Upload documents for each name (inside atomic, but uploads are non-DB)
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
                    raise ValueError(f"Failed to upload document: {str(e)}")

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
                    # Always set to 'submitted' if metadata is present (submit=true)
                    new_status = 'submitted' if 'submit' in updated_metadata else item.get('status', 'pending')
                    updated_item = {
                        'id': item['id'],
                        'name': item['name'],
                        'description': item.get('description', ''),
                        'required': item.get('required', True),
                        'requires_document': item.get('requires_document', True),
                        'status': new_status,
                        'checked_by': item.get('checked_by'),
                        'checked_at': item.get('checked_at'),
                        'notes': item.get('notes', ''),
                        'document': item.get('document', []),
                        'metadata': updated_metadata
                    }
                    updated_compliance_status.append(updated_item)
                    item_updated = True
                    logger.info(f"Updated compliance item {item['id']} with metadata (status set to '{new_status}')")
            
            # If not updated, keep the item as is
            if not item_updated:
                updated_compliance_status.append(item)

        # Save the updated application (single save at end)
        application.compliance_status = updated_compliance_status
        application.save()
        logger.info(f"Job application {job_application_id} saved with updated compliance status")

        return Response({
            "detail": "Compliance items processed successfully.",
            "compliance_status": application.compliance_status  # Use in-memory post-save data
        }, status=status.HTTP_200_OK)