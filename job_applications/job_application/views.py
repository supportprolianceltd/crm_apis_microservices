import os
import uuid
import json
import time
import logging
import mimetypes
import tempfile
import requests
import concurrent.futures
from urllib import request
from kafka import KafkaProducer
import re 
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from rest_framework.pagination import PageNumberPagination

from job_application.models import JobApplication, Schedule
from utils.screen import parse_resume, screen_resume, extract_resume_fields
from utils.email_utils import send_screening_notification
from utils.supabase import upload_file_dynamic
from .serializers import (
    JobApplicationSerializer,
    ScheduleSerializer,
    ComplianceStatusSerializer,
    SimpleMessageSerializer,
    PublicJobApplicationSerializer
)

import logging
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


class CustomPagination(PageNumberPagination):
    page_size = 20


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


# FOR LARGER FILES USE MULTI-THREADED FOR THIS FOR  APPLICATIONS UP TO A THOUSAND
# class ResumeScreeningView(APIView):
#     serializer_class = SimpleMessageSerializer
#     parser_classes = [JSONParser, MultiPartParser, FormParser]

#     def post(self, request, job_requisition_id):
#         try:
#             jwt_payload = getattr(request, 'jwt_payload', {})
#             tenant_id = self.request.jwt_payload.get('tenant_unique_id')
#             #tenant_id = str(jwt_payload.get('tenant_id')) if jwt_payload.get('tenant_id') is not None else None
#             role = jwt_payload.get('role')
#             branch = jwt_payload.get('user', {}).get('branch')

#             document_type = request.data.get('document_type')
#             applications_data = request.data.get('applications', [])
#             num_candidates = request.data.get('number_of_candidates')
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
#             if document_type_lower not in allowed_docs and document_type_lower not in ['resume', 'curriculum vitae (cv)']:
#                 return Response({"detail": f"Invalid document type: {document_type}"}, status=status.HTTP_400_BAD_REQUEST)

#             # Filter applications by tenant and branch
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

#             logger.info(f"Screening {applications.count()} applications: {[str(app.id) for app in applications]}")
#             if not applications.exists():
#                 logger.warning("No applications with resume_status=True found for provided IDs and filters.")
#                 return Response({"detail": "No applications with resumes found.", "documentType": document_type}, status=status.HTTP_400_BAD_REQUEST)

#             if role == 'recruiter' and branch:
#                 applications = applications.filter(branch=branch)
#             elif branch:
#                 applications = applications.filter(branch=branch)

#             def download_resume(app, app_data, document_type_lower):
#                 try:
#                     if app_data and 'file_url' in app_data:
#                         file_url = app_data['file_url']
#                     else:
#                         cv_doc = next(
#                             (doc for doc in app.documents if doc['document_type'].lower() == document_type_lower),
#                             None
#                         )
#                         if not cv_doc:
#                             app.screening_status = 'failed'
#                             app.screening_score = 0.0
#                             app.save()
#                             return {
#                                 "app": app,
#                                 "success": False,
#                                 "error": f"No {document_type} document found",
#                             }
#                         file_url = cv_doc['file_url']

#                     logger.info(f"About to download file for app {app.id}: {file_url}")
#                     start_download = time.time()
#                     headers = {"Authorization": f"Bearer {settings.SUPABASE_KEY}"}
#                     try:
#                         response = requests.get(file_url, headers=headers, timeout=10)
#                     except requests.exceptions.Timeout:
#                         app.screening_status = 'failed'
#                         app.screening_score = 0.0
#                         app.save()
#                         return {
#                             "app": app,
#                             "success": False,
#                             "error": f"Resume download timed out after 10 seconds for {file_url}",
#                         }
#                     except requests.exceptions.RequestException as e:
#                         app.screening_status = 'failed'
#                         app.screening_score = 0.0
#                         app.save()
#                         return {
#                             "app": app,
#                             "success": False,
#                             "error": f"Resume download error: {str(e)}",
#                         }
#                     download_time = time.time() - start_download
#                     file_size = len(response.content)
#                     logger.info(f"Downloaded file for app {app.id} in {download_time:.2f}s, size: {file_size} bytes")
#                     if response.status_code != 200:
#                         app.screening_status = 'failed'
#                         app.screening_score = 0.0
#                         app.save()
#                         return {
#                             "app": app,
#                             "success": False,
#                             "error": f"Failed to download resume from {file_url}, status code: {response.status_code}",
#                         }

#                     content_type = response.headers.get('content-type', '')
#                     file_ext = mimetypes.guess_extension(content_type) or os.path.splitext(file_url)[1] or '.pdf'
#                     temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_ext)
#                     temp_file.write(response.content)
#                     temp_file.close()
#                     temp_file_path = temp_file.name
#                     logger.info(f"Finished download for app {app.id}")
#                     return {
#                         "app": app,
#                         "success": True,
#                         "temp_file_path": temp_file_path,
#                         "file_url": file_url,
#                     }
#                 except Exception as e:
#                     logger.error(f"Download failed for app {app.id}: {str(e)}")
#                     app.screening_status = 'failed'
#                     app.screening_score = 0.0
#                     app.save()
#                     return {
#                         "app": app,
#                         "success": False,
#                         "error": f"Download error for file: {str(e)}",
#                     }

#             # Step 1: Parallel download all files
#             download_results = []
#             applications_list = list(applications)
#             applications_data_map = {str(a['application_id']): a for a in applications_data}
#             with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
#                 future_to_app = {
#                     executor.submit(
#                         download_resume,
#                         app,
#                         applications_data_map.get(str(app.id)),
#                         document_type_lower
#                     ): app for app in applications_list
#                 }
#                 for future in concurrent.futures.as_completed(future_to_app):
#                     result = future.result()
#                     download_results.append(result)

#             # Step 2: Parallel parse and screen only successfully downloaded files
#             job_requirements = (
#                 (job_requisition.get('job_description') or '') + ' ' +
#                 (job_requisition.get('qualification_requirement') or '') + ' ' +
#                 (job_requisition.get('experience_requirement') or '') + ' ' +
#                 (job_requisition.get('knowledge_requirement') or '')
#             ).strip()

#             def parse_and_screen(result, job_requirements):
#                 app = result["app"]
#                 if not result["success"]:
#                     # If the error is a timeout, return a specific message
#                     error_msg = result["error"]
#                     if "timed out" in error_msg.lower():
#                         error_msg = f"Resume parsing or download timed out. Please try again or check the file."
#                     return {
#                         "application_id": str(app.id),
#                         "full_name": app.full_name,
#                         "email": app.email,
#                         "error": error_msg,
#                         "success": False
#                     }
#                 temp_file_path = result["temp_file_path"]
#                 file_url = result.get("file_url", "")
#                 try:
#                     logger.info(f"About to parse resume for app {app.id}")
#                     start_parse = time.time()
#                     resume_text = parse_resume(temp_file_path)
#                     parse_time = time.time() - start_parse
#                     logger.info(f"Finished parsing resume for app {app.id} in {parse_time:.2f}s")
#                     logger.info(f"Extracted text length for app {app.id}: {len(resume_text) if resume_text else 0}")
#                     logger.debug(f"Resume text sample for app {app.id}: {resume_text[:200] if resume_text else 'No text'}")
#                     if temp_file_path and os.path.exists(temp_file_path):
#                         os.unlink(temp_file_path)
#                     if not resume_text:
#                         app.screening_status = 'failed'
#                         app.screening_score = 0.0
#                         app.save()
#                         return {
#                             "application_id": str(app.id),
#                             "full_name": app.full_name,
#                             "email": app.email,
#                             "error": f"Failed to parse resume for file: {file_url}",
#                             "success": False
#                         }
#                     score = screen_resume(resume_text, job_requirements)
#                     resume_data = extract_resume_fields(resume_text)
#                     employment_gaps = resume_data.get("employment_gaps", [])
#                     app.screening_status = 'processed'
#                     app.screening_score = score
#                     app.employment_gaps = employment_gaps
#                     app.save()
#                     return {
#                         "application_id": str(app.id),
#                         "full_name": app.full_name,
#                         "email": app.email,
#                         "score": score,
#                         "screening_status": app.screening_status,
#                         "employment_gaps": employment_gaps,
#                         "success": True
#                     }
#                 except Exception as e:
#                     logger.error(f"Parsing failed for app {app.id}: {str(e)}")
#                     app.screening_status = 'failed'
#                     app.screening_score = 0.0
#                     app.save()
#                     if temp_file_path and os.path.exists(temp_file_path):
#                         os.unlink(temp_file_path)
#                     return {
#                         "application_id": str(app.id),
#                         "full_name": app.full_name,
#                         "email": app.email,
#                         "error": f"Screening error for file: {file_url} - {str(e)}",
#                         "success": False
#                     }

#             results = []
#             with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
#                 future_to_result = {
#                     executor.submit(parse_and_screen, result, job_requirements): result for result in download_results
#                 }
#                 for future in concurrent.futures.as_completed(future_to_result):
#                     results.append(future.result())

#             # Separate successful and failed applications
#             shortlisted = [r for r in results if r.get("success")]
#             failed_applications = [r for r in results if not r.get("success")]

#             if not shortlisted and failed_applications:
#                 return Response({
#                     "detail": "All resume screenings failed.",
#                     "failed_applications": failed_applications,
#                     "document_type": document_type
#                 }, status=status.HTTP_400_BAD_REQUEST)

#             shortlisted.sort(key=lambda x: x['score'], reverse=True)
#             final_shortlisted = shortlisted[:num_candidates]
#             shortlisted_ids = {item['application_id'] for item in final_shortlisted}

#             for app in applications:
#                 app_id_str = str(app.id)
#                 if app_id_str in shortlisted_ids:
#                     app.status = 'shortlisted'
#                     app.save()
#                     shortlisted_app = next((item for item in final_shortlisted if item['application_id'] == app_id_str), None)
#                     if shortlisted_app:
#                         shortlisted_app['job_requisition_id'] = job_requisition['id']
#                         shortlisted_app['status'] = 'shortlisted'
#                         employment_gaps = shortlisted_app.get('employment_gaps', [])
#                         event_type = "job.application.shortlisted.gaps" if employment_gaps else "job.application.shortlisted"
#                         send_screening_notification(
#                             shortlisted_app,
#                             tenant_id,
#                             event_type=event_type,
#                             employment_gaps=employment_gaps
#                         )
#                 else:
#                     app.status = 'rejected'
#                     app.save()
#                     rejected_app = {
#                         "application_id": app_id_str,
#                         "full_name": app.full_name,
#                         "email": app.email,
#                         "job_requisition_id": job_requisition['id'],
#                         "status": "rejected",
#                         "score": getattr(app, "screening_score", None)
#                     }
#                     send_screening_notification(rejected_app, tenant_id, event_type="job.application.rejected")

#             return Response({
#                 "detail": f"Screened {len(shortlisted)} applications using '{document_type}', shortlisted {len(final_shortlisted)} candidates.",
#                 "shortlisted_candidates": final_shortlisted,
#                 "failed_applications": failed_applications,
#                 "number_of_candidates": num_candidates,
#                 "document_type": document_type
#             }, status=status.HTTP_200_OK)

#         except requests.exceptions.Timeout as e:
#             logger.error(f"Gateway timeout during resume screening: {str(e)}")
#             return Response({
#                 "error": "Resume screening timed out",
#                 "details": str(e),
#                 "suggestion": "The operation took too long to complete. Please try again later or reduce the number of applications."
#             }, status=status.HTTP_504_GATEWAY_TIMEOUT)
#         except requests.exceptions.ConnectionError as e:
#             logger.error(f"Connection error during resume screening: {str(e)}")
#             return Response({
#                 "error": "Unable to connect to resume screening service",
#                 "details": str(e),
#                 "suggestion": "Please check your network connection or contact support."
#             }, status=status.HTTP_502_BAD_GATEWAY)
#         except requests.exceptions.RequestException as e:
#             logger.error(f"Gateway error during resume screening: {str(e)}")
#             return Response({
#                 "error": "Resume screening gateway error",
#                 "details": str(e),
#                 "suggestion": "There was a network or service error. Please check your connection or contact support if the issue persists."
#             }, status=status.HTTP_502_BAD_GATEWAY)
#         except Exception as e:
#             logger.exception(f"Error screening resumes for JobRequisition {job_requisition_id}: {str(e)}")
#             return Response({
#                 "error": "Internal server error during resume screening",
#                 "details": str(e),
#                 "suggestion": "An unexpected error occurred. Please try again or contact support."
#             }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ResumeScreeningView(APIView):
    serializer_class = SimpleMessageSerializer
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def post(self, request, job_requisition_id):
        try:
            jwt_payload = getattr(request, 'jwt_payload', {})
            tenant_id = self.request.jwt_payload.get('tenant_unique_id')
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
                    try:
                        response = requests.get(file_url, headers=headers, timeout=10)
                    except requests.exceptions.Timeout:
                        app.screening_status = 'failed'
                        app.screening_score = 0.0
                        app.save()
                        return {
                            "app": app,
                            "success": False,
                            "error": f"Resume download timed out after 10 seconds for {file_url}",
                        }
                    except requests.exceptions.RequestException as e:
                        app.screening_status = 'failed'
                        app.screening_score = 0.0
                        app.save()
                        return {
                            "app": app,
                            "success": False,
                            "error": f"Resume download error: {str(e)}",
                        }
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
                    error_msg = result["error"]
                    if "timed out" in error_msg.lower():
                        error_msg = f"Resume parsing or download timed out. Please try again or check the file."
                    return {
                        "application_id": str(app.id),
                        "full_name": app.full_name,
                        "email": app.email,
                        "error": error_msg,
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
                app_id_str = str(app.id)
                if app_id_str in shortlisted_ids:
                    app.status = 'shortlisted'
                    app.save()
                    shortlisted_app = next((item for item in final_shortlisted if item['application_id'] == app_id_str), None)
                    if shortlisted_app:
                        shortlisted_app['job_requisition_id'] = job_requisition['id']
                        shortlisted_app['status'] = 'shortlisted'
                        employment_gaps = shortlisted_app.get('employment_gaps', [])
                        event_type = "job_application.shortlisted.gaps" if employment_gaps else "job_application.shortlisted"
                        send_screening_notification(
                            shortlisted_app,
                            tenant_id,
                            event_type=event_type,
                            employment_gaps=employment_gaps
                        )
                else:
                    app.status = 'rejected'
                    app.save()
                    rejected_app = {
                        "application_id": app_id_str,
                        "full_name": app.full_name,
                        "email": app.email,
                        "job_requisition_id": job_requisition['id'],
                        "status": "rejected",
                        "score": getattr(app, "screening_score", None)
                    }
                    send_screening_notification(rejected_app, tenant_id, event_type="job_application.rejected")

            return Response({
                "detail": f"Screened {len(shortlisted)} applications using '{document_type}', shortlisted {len(final_shortlisted)} candidates.",
                "shortlisted_candidates": final_shortlisted,
                "failed_applications": failed_applications,
                "number_of_candidates": num_candidates,
                "document_type": document_type
            }, status=status.HTTP_200_OK)

        except requests.exceptions.Timeout as e:
            logger.error(f"Gateway timeout during resume screening: {str(e)}")
            return Response({
                "error": "Resume screening timed out",
                "details": str(e),
                "suggestion": "The operation took too long to complete. Please try again later or reduce the number of applications."
            }, status=status.HTTP_504_GATEWAY_TIMEOUT)
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error during resume screening: {str(e)}")
            return Response({
                "error": "Unable to connect to resume screening service",
                "details": str(e),
                "suggestion": "Please check your network connection or contact support."
            }, status=status.HTTP_502_BAD_GATEWAY)
        except requests.exceptions.RequestException as e:
            logger.error(f"Gateway error during resume screening: {str(e)}")
            return Response({
                "error": "Resume screening gateway error",
                "details": str(e),
                "suggestion": "There was a network or service error. Please check your connection or contact support if the issue persists."
            }, status=status.HTTP_502_BAD_GATEWAY)
        except Exception as e:
            logger.exception(f"Error screening resumes for JobRequisition {job_requisition_id}: {str(e)}")
            return Response({
                "error": "Internal server error during resume screening",
                "details": str(e),
                "suggestion": "An unexpected error occurred. Please try again or contact support."
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



# class JobApplicationCreatePublicView(generics.CreateAPIView):
#     serializer_class = PublicJobApplicationSerializer
#     parser_classes = (MultiPartParser, FormParser, JSONParser)

#     def create(self, request, *args, **kwargs):
#         unique_link = request.data.get('unique_link') or request.data.get('job_requisition_unique_link')
#         if not unique_link:
#             return Response({"detail": "Missing job requisition unique link."}, status=status.HTTP_400_BAD_REQUEST)

#         # ✅ Extract tenant_id from UUID-style prefix (first 5 segments)
#         try:
#             parts = unique_link.split('-')
#             if len(parts) < 5:
#                 logger.warning(f"Invalid unique_link format: {unique_link}")
#                 return Response({"detail": "Invalid unique link format."}, status=status.HTTP_400_BAD_REQUEST)
#             tenant_id = '-'.join(parts[:5])
#         except Exception as e:
#             logger.error(f"Error extracting tenant_id from link: {str(e)}")
#             return Response({"detail": "Failed to extract tenant ID."}, status=status.HTTP_400_BAD_REQUEST)

#         # ✅ Fetch job requisition from Talent Engine
#         requisition_url = f"{settings.TALENT_ENGINE_URL}/api/talent-engine/requisitions/by-link/{unique_link}/"
#         try:
#             resp = requests.get(requisition_url)
#             logger.info(f"Requisition fetch for link: {unique_link}, status: {resp.status_code}")
#             if resp.status_code != 200:
#                 try:
#                     error_detail = resp.json().get('detail', 'Invalid job requisition.')
#                 except Exception:
#                     error_detail = 'Invalid job requisition.'
#                 return Response({"detail": error_detail}, status=status.HTTP_400_BAD_REQUEST)
#             job_requisition = resp.json()
#         except Exception as e:
#             logger.error(f"Error fetching job requisition: {str(e)}")
#             return Response({"detail": "Unable to fetch job requisition."}, status=status.HTTP_502_BAD_GATEWAY)

#         # ✅ Prepare payload
#         payload = dict(request.data.items())
#         payload['job_requisition_id'] = job_requisition['id']
#         payload['tenant_id'] = tenant_id

#         # ✅ Extract documents from multipart form
#         documents = []
#         i = 0
#         while f'documents[{i}][document_type]' in request.data and f'documents[{i}][file]' in request.FILES:
#             documents.append({
#                 'document_type': request.data.get(f'documents[{i}][document_type]'),
#                 'file': request.FILES.get(f'documents[{i}][file]')
#             })
#             i += 1
#         if documents:
#             payload['documents'] = documents

#         logger.info(f"Full POST payload: {payload}")

#         # ✅ Validate serializer
#         serializer = self.get_serializer(data=payload, context={'request': request, 'job_requisition': job_requisition})
#         if not serializer.is_valid():
#             logger.error(f"Validation errors: {serializer.errors}")
#             return Response({
#                 "detail": "Validation error",
#                 "errors": serializer.errors
#             }, status=status.HTTP_400_BAD_REQUEST)

#         # ✅ Prevent duplicate application by email for same requisition
#         email = payload.get('email')
#         job_requisition_id = job_requisition['id']
#         if JobApplication.objects.filter(email=email, job_requisition_id=job_requisition_id).exists():
#             logger.warning(f"Duplicate application attempt by email: {email} for requisition: {job_requisition_id}")
#             return Response({
#                 "detail": "You have already applied for this job"
#             }, status=status.HTTP_400_BAD_REQUEST)

#         # ✅ Save
#         self.perform_create(serializer)

#         # ✅ Publish to Kafka
#         try:
#             producer = KafkaProducer(
#                 bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
#                 value_serializer=lambda v: json.dumps(v).encode('utf-8')
#             )
#             kafka_data = {
#                 "tenant_id": tenant_id,
#                 "job_requisition_id": job_requisition['id'],
#                 "event": "job_application_created"
#             }
#             producer.send('job_application_events', kafka_data)
#             producer.flush()
#             logger.info(f"Published Kafka job application event for requisition {job_requisition['id']}")
#         except Exception as e:
#             logger.error(f"Kafka publish error: {str(e)}")

#         return Response(serializer.data, status=status.HTTP_201_CREATED)

import logging
import requests
from django.conf import settings
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework import generics
from .models import JobApplication
from .serializers import PublicJobApplicationSerializer
from kafka import KafkaProducer
import json

logger = logging.getLogger('talent_engine')

class JobApplicationCreatePublicView(generics.CreateAPIView):
    serializer_class = PublicJobApplicationSerializer
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def create(self, request, *args, **kwargs):
        unique_link = request.data.get('unique_link') or request.data.get('job_requisition_unique_link')
        if not unique_link:
            return Response({"detail": "Missing job requisition unique link."}, status=status.HTTP_400_BAD_REQUEST)

        # Extract tenant_id from UUID-style prefix (first 5 segments)
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
                return Response({"detail": error_detail}, status=status.HTTP_400_BAD_REQUEST)
            job_requisition = resp.json()
        except Exception as e:
            logger.error(f"Error fetching job requisition: {str(e)}")
            return Response({"detail": "Unable to fetch job requisition."}, status=status.HTTP_502_BAD_GATEWAY)

        # Prepare payload
        payload = dict(request.data.items())
        payload['job_requisition_id'] = job_requisition['id']
        payload['tenant_id'] = tenant_id

        # Extract documents from multipart form
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

        logger.info(f"Full POST payload: {payload}")

        # Validate serializer
        serializer = self.get_serializer(data=payload, context={'request': request, 'job_requisition': job_requisition})
        if not serializer.is_valid():
            logger.error(f"Validation errors: {serializer.errors}")
            return Response({
                "detail": "Validation error",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        # Prevent duplicate application by email for same requisition
        email = payload.get('email')
        job_requisition_id = job_requisition['id']
        if JobApplication.objects.filter(email=email, job_requisition_id=job_requisition_id).exists():
            logger.warning(f"Duplicate application attempt by email: {email} for requisition: {job_requisition_id}")
            return Response({
                "detail": "You have already applied for this job"
            }, status=status.HTTP_400_BAD_REQUEST)

        # Save the application
        self.perform_create(serializer)

        # Increment num_of_applications by calling the public endpoint
        increment_url = f"{settings.TALENT_ENGINE_URL}/api/talent-engine/requisitions/public/update-applications/{unique_link}/"
        try:
            resp = requests.post(increment_url)
            if resp.status_code != 200:
                logger.warning(f"Failed to increment num_of_applications for unique_link {unique_link}: {resp.status_code}, {resp.text}")
                # Continue despite failure to ensure application creation succeeds
            else:
                logger.info(f"Successfully incremented num_of_applications for unique_link {unique_link}")
        except Exception as e:
            logger.error(f"Error calling increment endpoint for unique_link {unique_link}: {str(e)}")
            # Continue despite failure to ensure application creation succeeds

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
    parser_classes = (MultiPartParser, FormParser, JSONParser)  # <-- Add JSONParser here
    lookup_field = 'id'

    def get_queryset(self):
        jwt_payload = getattr(self.request, 'jwt_payload', {})
        tenant_id = self.request.jwt_payload.get('tenant_unique_id')
        #tenant_id = str(jwt_payload.get('tenant_id')) if jwt_payload.get('tenant_id') is not None else None
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
                    event_type="job_application.schedule.created"
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
                        event_type="job_application.schedule.updated"
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

class ComplianceStatusUpdateView(APIView):
    permission_classes = [AllowAny]  # Temporary for testing; replace with IsAuthenticated in production
    parser_classes = [JSONParser]

    def post(self, request, job_application_id):
        # Extract item_id from request body
        item_id = request.data.get('item_id')
        if not item_id:
            logger.warning("No item_id provided in request data")
            return Response({"detail": "Item ID is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Extract JWT payload for authorization
        jwt_payload = getattr(request, 'jwt_payload', {})
        logger.info(f"JWT payload: {jwt_payload}")  # Log payload for debugging
        role = jwt_payload.get('role')
        branch = jwt_payload.get('user', {}).get('branch')
        user_id = jwt_payload.get('user', {}).get('id')  # Extract user_id from user.id

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

        # Fetch user details for checked_by when updating status
        checked_by = None
        if 'status' in update_data:
            if not user_id:
                logger.warning("No user.id found in JWT payload for status update")
                return Response({"detail": "Authentication required for status update."}, status=status.HTTP_401_UNAUTHORIZED)
            try:
                user_response = requests.get(
                    f'{settings.AUTH_SERVICE_URL}/api/user/users/{user_id}/',
                    headers={'Authorization': f'Bearer {request.META.get("HTTP_AUTHORIZATION", "").split(" ")[1] if request.META.get("HTTP_AUTHORIZATION") else ""}'}
                )
                if user_response.status_code == 200:
                    user_data = user_response.json()
                    checked_by = {
                        'email': user_data.get('email', ''),
                        'first_name': user_data.get('first_name', ''),
                        'last_name': user_data.get('last_name', ''),
                        'job_role': user_data.get('job_role', '')
                    }
                else:
                    logger.error(f"Failed to fetch user {user_id} from auth_service: {user_response.status_code}")
                    return Response({"detail": "Failed to fetch user details."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            except Exception as e:
                logger.error(f"Error fetching user {user_id}: {str(e)}")
                return Response({"detail": "Error fetching user details."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Fetch the job application
        try:
            application = JobApplication.active_objects.get(id=job_application_id)
        except JobApplication.DoesNotExist:
            logger.warning(f"Job application not found: {job_application_id}")
            return Response({"detail": "Job application not found."}, status=status.HTTP_404_NOT_FOUND)

        # Check branch authorization if branch is provided
        if branch and application.branch_id != branch:
            logger.warning(f"User not authorized to access application {job_application_id} for branch {branch}")
            return Response({"detail": "Not authorized to access this application."}, status=status.HTTP_403_FORBIDDEN)

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
                if 'status' in update_data and checked_by:
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
        metadata_data = []
        storage_type = getattr(settings, 'STORAGE_TYPE', 'supabase').lower()

        # Create a mapping of names to their corresponding files
        name_to_files = {}
        for i, name in enumerate(names):
            if i < len(files):
                if name not in name_to_files:
                    name_to_files[name] = []
                name_to_files[name].append(files[i])
            else:
                # No file for this name, treat as metadata
                metadata_data.append({
                    'doc_id': compliance_checklist[name]['id'],
                    'name': name,
                    'metadata': additional_fields
                })

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
            if item_documents:
                updated_item = {
                    'id': item['id'],
                    'name': item['name'],
                    'description': item.get('description', ''),
                    'required': item.get('required', True),
                    'requires_document': item.get('requires_document', True),
                    'status': 'uploaded',
                    'checked_by': item.get('checked_by'),
                    'checked_at': item.get('checked_at'),
                    'notes': '',
                    'document': [{'file_url': doc['file_url'], 'uploaded_at': doc['uploaded_at']} for doc in item_documents],
                    'metadata': item.get('metadata', {})
                }
                updated_compliance_status.append(updated_item)
                item_updated = True
                logger.info(f"Updated compliance item {item['id']} with {len(item_documents)} document(s)")
            
            # Check for metadata updates
            for meta in metadata_data:
                if item['id'] == meta['doc_id']:
                    updated_item = {
                        'id': item['id'],
                        'name': item['name'],
                        'description': item.get('description', ''),
                        'required': item.get('required', True),
                        'requires_document': item.get('requires_document', True),
                        'status': 'submitted',
                        'checked_by': item.get('checked_by'),
                        'checked_at': item.get('checked_at'),
                        'notes': '',
                        'document': item.get('document', []),  # Preserve existing documents
                        'metadata': meta['metadata']
                    }
                    updated_compliance_status.append(updated_item)
                    item_updated = True
                    logger.info(f"Updated compliance item {item['id']} with metadata")
                    break

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