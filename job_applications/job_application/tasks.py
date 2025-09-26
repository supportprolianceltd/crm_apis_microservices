# import os
# import requests
# import mimetypes
# import tempfile
# import logging
# from datetime import date
# from celery import shared_task
# from django.conf import settings
# from django.utils import timezone
# from django.db import connection
# from job_application.models import JobApplication
# from utils.screen import parse_resume, screen_resume, extract_resume_fields
# from utils.email_utils import send_screening_notification

# logger = logging.getLogger('job_applications')

# @shared_task(bind=True, max_retries=3)
# def auto_screen_all_applications(self):
#     try:
#         today = timezone.now().date()
#         logger.info(f"Starting auto_screen_all_applications task for date: {today}")

#         url = f"{settings.TALENT_ENGINE_URL}/api/talent-engine/requisitions/public/published/"
#         try:
#             logger.info(f"Fetching requisitions from {url}")
#             resp = requests.get(url, timeout=10)
#             resp.raise_for_status()
#             data = resp.json()
#             logger.info(f"Received {data.get('count', 0)} requisitions")
#         except Exception as e:
#             logger.error(f"Failed to fetch published requisitions: {str(e)}")
#             raise self.retry(exc=e, countdown=60)

#         if not data.get("results"):
#             logger.warning("No published requisitions found.")
#             return

#         for requisition in data.get("results", []):
#             deadline_str = requisition.get("deadline_date")
#             if not deadline_str:
#                 logger.info(f"Skipping requisition {requisition['id']} (no deadline date)")
#                 continue

#             try:
#                 deadline_date = date.fromisoformat(deadline_str)
#             except ValueError:
#                 logger.error(f"Invalid deadline date format for requisition {requisition['id']}: {deadline_str}")
#                 continue

#             logger.info(f"Checking requisition {requisition['id']}: deadline_date={deadline_date}, today={today}")
#             if deadline_date != today:
#                 logger.info(f"Skipping requisition {requisition['id']} (deadline {deadline_date} != {today})")
#                 continue

#             job_requisition_id = requisition["id"]
#             document_type = "resume"
#             num_candidates = requisition.get("num_of_applications", 0)

#             # Force evaluation of queryset here to avoid "cursor already closed"
#             applications_queryset = JobApplication.active_objects.filter(
#                 job_requisition_id=str(job_requisition_id),
#                 resume_status=True
#             )
#             applications = list(applications_queryset)
#             logger.info(f"Found {len(applications)} applications for requisition {job_requisition_id}")

#             if not applications:
#                 logger.warning(f"No eligible applications for requisition {job_requisition_id}")
#                 continue

#             # Build list of dicts to pass to Celery
#             applications_data = [
#                 {"application_id": app.id, "file_url": app.get_resume_url()} for app in applications
#             ]

#             logger.info(f"Triggering screening for requisition {job_requisition_id} with {len(applications_data)} applications")

#             # Pass only raw data (not model instances) to Celery
#             screen_resumes_task.delay(
#                 job_requisition_id,
#                 document_type,
#                 num_candidates,
#                 applications_data,
#                 requisition
#             )
            
#     except Exception as e:
#         logger.error(f"Unexpected error in auto_screen_all_applications: {str(e)}")
#         raise self.retry(exc=e, countdown=120)

# @shared_task(bind=True, max_retries=3)
# def screen_resumes_task(self, job_requisition_id, document_type, num_candidates, applications_data, job_requisition):
#     try:
#         logger.info(f"Starting screen_resumes_task for job_requisition_id: {job_requisition_id}")
        
#         # Convert document type to lowercase for comparison
#         document_type_lower = document_type.lower()
        
#         # Get allowed document types from requisition
#         allowed_docs = [doc.lower() for doc in (job_requisition.get('documents_required') or [])]
        
#         # Check if document type is valid
#         if document_type_lower not in allowed_docs and document_type_lower not in ['resume', 'curriculum vitae (cv)']:
#             logger.error(f"Invalid document type: {document_type}")
#             return

#         # Get applications to process
#         if not applications_data:
#             applications = JobApplication.active_objects.filter(
#                 job_requisition_id=job_requisition_id,
#                 resume_status=True
#             )
#         else:
#             application_ids = [app['application_id'] for app in applications_data]
#             applications = JobApplication.active_objects.filter(
#                 job_requisition_id=job_requisition_id,
#                 id__in=application_ids,
#                 resume_status=True
#             )

#         logger.info(f"Screening {applications.count()} applications for job_requisition_id: {job_requisition_id}")
        
#         if not applications.exists():
#             logger.warning("No applications with resume_status=True found.")
#             return

#         def download_resume(app, app_data, document_type_lower):
#             try:
#                 if app_data and 'file_url' in app_data:
#                     file_url = app_data['file_url']
#                 else:
#                     # Find the document with the matching type
#                     cv_doc = next(
#                         (doc for doc in app.documents if doc['document_type'].lower() == document_type_lower),
#                         None
#                     )
#                     if not cv_doc:
#                         app.screening_status = 'failed'
#                         app.screening_score = 0.0
#                         app.save()
#                         return {"app": app, "success": False, "error": f"No {document_type} document found"}
#                     file_url = cv_doc['file_url']

#                 # Download the file
#                 headers = {"Authorization": f"Bearer {settings.SUPABASE_KEY}"}
#                 response = requests.get(file_url, headers=headers, timeout=10)
#                 if response.status_code != 200:
#                     app.screening_status = 'failed'
#                     app.screening_score = 0.0
#                     app.save()
#                     return {"app": app, "success": False, "error": f"Failed to download resume from {file_url}"}

#                 # Determine file extension
#                 content_type = response.headers.get('content-type', '')
#                 file_ext = mimetypes.guess_extension(content_type) or os.path.splitext(file_url)[1] or '.pdf'
                
#                 # Save to temporary file
#                 temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_ext)
#                 temp_file.write(response.content)
#                 temp_file.close()
#                 temp_file_path = temp_file.name
                
#                 return {"app": app, "success": True, "temp_file_path": temp_file_path, "file_url": file_url}
#             except Exception as e:
#                 app.screening_status = 'failed'
#                 app.screening_score = 0.0
#                 app.save()
#                 return {"app": app, "success": False, "error": f"Download error: {str(e)}"}

#         # Download resumes
#         download_results = []
#         applications_list = list(applications)
#         applications_data_map = {str(a['application_id']): a for a in applications_data}
        
#         for app in applications_list:
#             result = download_resume(app, applications_data_map.get(str(app.id)), document_type_lower)
#             download_results.append(result)

#         # Prepare job requirements for screening
#         job_requirements = (
#             (job_requisition.get('job_description') or '') + ' ' +
#             (job_requisition.get('qualification_requirement') or '') + ' ' +
#             (job_requisition.get('experience_requirement') or '') + ' ' +
#             (job_requisition.get('knowledge_requirement') or '')
#         ).strip()

#         def parse_and_screen(result, job_requirements):
#             app = result["app"]
#             if not result["success"]:
#                 return {
#                     "application_id": str(app.id),
#                     "full_name": app.full_name,
#                     "email": app.email,
#                     "error": result["error"],
#                     "success": False
#                 }
                
#             temp_file_path = result["temp_file_path"]
#             file_url = result.get("file_url", "")
            
#             try:
#                 # Parse resume
#                 resume_text = parse_resume(temp_file_path)
                
#                 # Clean up temporary file
#                 if temp_file_path and os.path.exists(temp_file_path):
#                     os.unlink(temp_file_path)
                    
#                 if not resume_text:
#                     app.screening_status = 'failed'
#                     app.screening_score = 0.0
#                     app.save()
#                     return {
#                         "application_id": str(app.id),
#                         "full_name": app.full_name,
#                         "email": app.email,
#                         "error": f"Failed to parse resume for file: {file_url}",
#                         "success": False
#                     }
                    
#                 # Screen resume
#                 score = screen_resume(resume_text, job_requirements)
#                 resume_data = extract_resume_fields(resume_text)
#                 employment_gaps = resume_data.get("employment_gaps", [])
                
#                 # Update application
#                 app.screening_status = 'processed'
#                 app.screening_score = score
#                 app.employment_gaps = employment_gaps
#                 app.save()
                
#                 return {
#                     "application_id": str(app.id),
#                     "full_name": app.full_name,
#                     "email": app.email,
#                     "score": score,
#                     "screening_status": app.screening_status,
#                     "employment_gaps": employment_gaps,
#                     "success": True
#                 }
#             except Exception as e:
#                 app.screening_status = 'failed'
#                 app.screening_score = 0.0
#                 app.save()
#                 if temp_file_path and os.path.exists(temp_file_path):
#                     os.unlink(temp_file_path)
#                 return {
#                     "application_id": str(app.id),
#                     "full_name": app.full_name,
#                     "email": app.email,
#                     "error": f"Screening error for file: {file_url} - {str(e)}",
#                     "success": False
#                 }

#         # Process all applications
#         results = []
#         for result in download_results:
#             results.append(parse_and_screen(result, job_requirements))

#         # Separate successful and failed screenings
#         shortlisted = [r for r in results if r.get("success")]
#         failed_applications = [r for r in results if not r.get("success")]

#         # Sort by score and select top candidates
#         shortlisted.sort(key=lambda x: x['score'], reverse=True)
#         final_shortlisted = shortlisted[:num_candidates]
#         shortlisted_ids = {item['application_id'] for item in final_shortlisted}

#         # Update application statuses and send notifications
#         for app in applications:
#             app_id_str = str(app.id)
#             if app_id_str in shortlisted_ids:
#                 app.status = 'shortlisted'
#                 app.save()
#                 shortlisted_app = next((item for item in final_shortlisted if item['application_id'] == app_id_str), None)
#                 if shortlisted_app:
#                     shortlisted_app['job_requisition_id'] = job_requisition['id']
#                     shortlisted_app['status'] = 'shortlisted'
#                     employment_gaps = shortlisted_app.get('employment_gaps', [])
#                     event_type = "candidate.shortlisted.gaps" if employment_gaps else "candidate.shortlisted"
#                     tenant_id = applications_data_map.get(app_id_str, {}).get('tenant_id')
#                     send_screening_notification(
#                         shortlisted_app,
#                         tenant_id=tenant_id,
#                         event_type=event_type,
#                         employment_gaps=employment_gaps,
#                     )
#             else:
#                 app.status = 'rejected'
#                 app.save()
#                 rejected_app = {
#                     "application_id": app_id_str,
#                     "full_name": app.full_name,
#                     "email": app.email,
#                     "job_requisition_id": job_requisition['id'],
#                     "status": "rejected",
#                     "score": getattr(app, "screening_score", None)
#                 }
#                 send_screening_notification(rejected_app, tenant_id=tenant_id, event_type="candidate.rejected")

#         logger.info(f"Screening complete for job requisition {job_requisition_id}")

#         # Automatically close the requisition via public endpoint
#         #UPDATE THIS CLOSE REQUISITION TO OCCUR IN BATCH PROCESSING, SEND IT AS A LIST SO THE REQUISITION SERVICE UPDATE IN A SINGLE BATCH.
#         # close_url = f"{settings.TALENT_ENGINE_URL}/api/talent-engine/requisitions/public/close/"
      
#         close_url = f"{settings.TALENT_ENGINE_URL}/api/talent-engine/requisitions/public/close/batch/"

#         try:
#             batch_payload = {"job_requisition_ids": [job_requisition_id]}  # add more if needed
#             close_resp = requests.post(close_url, json=batch_payload, timeout=10)
#             if close_resp.status_code == 200:
#                 logger.info(f"Job requisitions closed via batch endpoint: {batch_payload['job_requisition_ids']}")
#             else:
#                 logger.warning(f"Failed to close job requisitions: {close_resp.text}")
#         except Exception as e:
#             logger.error(f"Error closing job requisitions via batch endpoint: {str(e)}")

            
#     except Exception as e:
#         logger.error(f"Unexpected error in screen_resumes_task: {str(e)}")
#         raise self.retry(exc=e, countdown=120)
    


# tasks.py
import os
import time
import logging
import tempfile
import requests
import mimetypes
from celery import shared_task, group, chord
from celery.result import allow_join_result
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from job_application.models import JobApplication
from utils.screen import parse_resume, screen_resume, extract_resume_fields
from utils.email_utils import send_screening_notification

logger = logging.getLogger('job_applications')

def get_job_requisition_by_id(job_requisition_id, authorization_header=""):
    """Get job requisition with authorization support for tasks"""
    try:
        headers = {'Authorization': authorization_header} if authorization_header else {}
        response = requests.get(
            f"{settings.TALENT_ENGINE_URL}/api/talent-engine/requisitions/{job_requisition_id}/",
            headers=headers,
            timeout=10
        )
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        logger.error(f"Error fetching job requisition in task: {str(e)}")
        return None

@shared_task(bind=True, max_retries=3, soft_time_limit=3600, time_limit=7200)
def process_large_resume_batch(self, job_requisition_id, tenant_id, document_type, 
                             applications_data, num_candidates, role=None, branch=None,
                             authorization_header=""):
    """
    Process large batches of resumes using parallel chunks with original email function
    """
    try:
        logger.info(f"Starting large batch processing for {len(applications_data)} applications")
        
        # Get job requisition for requirements
        job_requisition = get_job_requisition_by_id(job_requisition_id, authorization_header)
        if not job_requisition:
            raise Exception("Job requisition not found")
        
        # Split into manageable chunks (20 applications per chunk)
        chunk_size = 20
        chunks = [applications_data[i:i + chunk_size] 
                 for i in range(0, len(applications_data), chunk_size)]
        
        # Create subtasks for each chunk
        subtasks = []
        for i, chunk in enumerate(chunks):
            subtask = process_resume_chunk.s(
                job_requisition_id=job_requisition_id,
                tenant_id=tenant_id,
                document_type=document_type,
                applications_chunk=chunk,
                chunk_index=i,
                total_chunks=len(chunks),
                role=role,
                branch=branch,
                authorization_header=authorization_header,
                job_requirements=(
                    (job_requisition.get('job_description') or '') + ' ' +
                    (job_requisition.get('qualification_requirement') or '') + ' ' +
                    (job_requisition.get('experience_requirement') or '') + ' ' +
                    (job_requisition.get('knowledge_requirement') or '')
                ).strip()
            )
            subtasks.append(subtask)
        
        # Use chord to process chunks in parallel and then aggregate results
        callback = aggregate_screening_results.s(
            job_requisition_id=job_requisition_id,
            tenant_id=tenant_id,
            num_candidates=num_candidates,
            document_type=document_type,
            authorization_header=authorization_header
        )
        
        result = chord(subtasks)(callback)
        
        # Wait for result with timeout
        with allow_join_result():
            final_result = result.get(timeout=3600)
            
        logger.info(f"Completed large batch processing for {len(applications_data)} applications")
        return final_result
        
    except Exception as e:
        logger.error(f"Large batch processing failed: {str(e)}")
        raise self.retry(exc=e, countdown=60)

@shared_task(bind=True, max_retries=2, soft_time_limit=1800, time_limit=3600)
def process_resume_chunk(self, job_requisition_id, tenant_id, document_type, 
                        applications_chunk, chunk_index, total_chunks, role=None, 
                        branch=None, authorization_header="", job_requirements=""):
    """
    Process a chunk of applications
    """
    try:
        logger.info(f"Processing chunk {chunk_index + 1}/{total_chunks} with {len(applications_chunk)} applications")
        
        # Filter applications for this chunk
        application_ids = [app['application_id'] for app in applications_chunk]
        applications = JobApplication.active_objects.filter(
            job_requisition_id=job_requisition_id,
            tenant_id=tenant_id,
            id__in=application_ids,
            resume_status=True
        )
        
        if role == 'recruiter' and branch:
            applications = applications.filter(branch=branch)
        elif branch:
            applications = applications.filter(branch=branch)
        
        applications_list = list(applications)
        applications_data_map = {str(a['application_id']): a for a in applications_chunk}
        
        results = []
        document_type_lower = document_type.lower()
        
        # Process each application in the chunk
        for app in applications_list:
            result = _process_single_application(
                app, applications_data_map.get(str(app.id)), 
                document_type_lower, job_requirements
            )
            results.append(result)
        
        return {
            'chunk_index': chunk_index,
            'results': results,
            'processed_count': len(results)
        }
        
    except Exception as e:
        logger.error(f"Chunk {chunk_index} processing failed: {str(e)}")
        raise self.retry(exc=e, countdown=30)

def _process_single_application(app, app_data, document_type_lower, job_requirements):
    """Process a single application (download + screen)"""
    try:
        # Download resume
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
                    "application_id": str(app.id),
                    "full_name": app.full_name,
                    "email": app.email,
                    "error": f"No {document_type_lower} document found",
                    "success": False
                }
            file_url = cv_doc['file_url']

        headers = {"Authorization": f"Bearer {settings.SUPABASE_KEY}"}
        response = requests.get(file_url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            app.screening_status = 'failed'
            app.screening_score = 0.0
            app.save()
            return {
                "application_id": str(app.id),
                "full_name": app.full_name,
                "email": app.email,
                "error": f"Download failed: HTTP {response.status_code}",
                "success": False
            }

        # Save to temporary file
        content_type = response.headers.get('content-type', '')
        file_ext = mimetypes.guess_extension(content_type) or '.pdf'
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_ext)
        temp_file.write(response.content)
        temp_file.close()
        temp_file_path = temp_file.name

        # Parse and screen
        resume_text = parse_resume(temp_file_path)
        
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
                "error": "Failed to parse resume",
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
        logger.error(f"Application {app.id} processing failed: {str(e)}")
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

@shared_task(bind=True, max_retries=2, soft_time_limit=1800, time_limit=3600)
def aggregate_screening_results(self, chunk_results, job_requisition_id, tenant_id, 
                              num_candidates, document_type, authorization_header=""):
    """
    Aggregate results from all chunks, update statuses, and send email notifications using original function
    """
    try:
        all_results = []
        total_processed = 0
        
        for chunk_result in chunk_results:
            all_results.extend(chunk_result['results'])
            total_processed += chunk_result['processed_count']
        
        # Separate successful and failed
        shortlisted = [r for r in all_results if r.get("success")]
        failed_applications = [r for r in all_results if not r.get("success")]
        
        # Sort and select top candidates
        shortlisted.sort(key=lambda x: x['score'], reverse=True)
        final_shortlisted = shortlisted[:num_candidates] if num_candidates > 0 else shortlisted
        
        # Get job requisition for notifications
        job_requisition = get_job_requisition_by_id(job_requisition_id, authorization_header)
        
        # Update application statuses and send notifications using original function
        _update_applications_and_send_emails(
            final_shortlisted, job_requisition_id, tenant_id, job_requisition
        )
        
        result_data = {
            "detail": f"Screened {total_processed} applications using '{document_type}', shortlisted {len(final_shortlisted)} candidates.",
            "shortlisted_candidates": final_shortlisted,
            "failed_applications": failed_applications,
            "number_of_candidates": num_candidates,
            "document_type": document_type
        }
        
        logger.info(f"Aggregation completed: {len(final_shortlisted)} shortlisted from {total_processed} applications")
        return result_data
        
    except Exception as e:
        logger.error(f"Result aggregation failed: {str(e)}")
        raise self.retry(exc=e, countdown=30)

def _update_applications_and_send_emails(shortlisted_candidates, job_requisition_id, tenant_id, job_requisition):
    """Update application statuses and send email notifications using original function"""
    try:
        shortlisted_ids = {item['application_id'] for item in shortlisted_candidates}
        
        # Get all applications for this requisition
        applications = JobApplication.active_objects.filter(
            job_requisition_id=job_requisition_id,
            tenant_id=tenant_id
        )
        
        with transaction.atomic():
            for app in applications:
                app_id_str = str(app.id)
                if app_id_str in shortlisted_ids:
                    # Update to shortlisted
                    app.status = 'shortlisted'
                    app.save()
                    
                    # Find the shortlisted candidate data
                    shortlisted_app = next(
                        (item for item in shortlisted_candidates if item['application_id'] == app_id_str), 
                        None
                    )
                    if shortlisted_app:
                        # Prepare applicant data for original email function
                        applicant_data = {
                            "email": shortlisted_app['email'],
                            "full_name": shortlisted_app['full_name'],
                            "application_id": shortlisted_app['application_id'],
                            "job_requisition_id": job_requisition_id,
                            "status": "shortlisted",
                            "score": shortlisted_app.get('score')
                        }
                        
                        employment_gaps = shortlisted_app.get('employment_gaps', [])
                        event_type = "candidate.shortlisted.gaps" if employment_gaps else "candidate.shortlisted"
                        
                        # Send shortlisted notification email using original function
                        send_screening_notification(
                            applicant=applicant_data,
                            tenant_id=tenant_id,
                            event_type=event_type,
                            employment_gaps=employment_gaps
                        )
                        logger.info(f"Sent shortlisted email to {shortlisted_app['email']}")
                else:
                    # Update to rejected
                    app.status = 'rejected'
                    app.save()
                    
                    # Prepare applicant data for original email function
                    applicant_data = {
                        "email": app.email,
                        "full_name": app.full_name,
                        "application_id": app_id_str,
                        "job_requisition_id": job_requisition_id,
                        "status": "rejected",
                        "score": getattr(app, "screening_score", None)
                    }
                    
                    # Send rejection notification email using original function
                    send_screening_notification(
                        applicant=applicant_data,
                        tenant_id=tenant_id,
                        event_type="candidate.rejected"
                    )
                    logger.info(f"Sent rejection email to {app.email}")
                    
    except Exception as e:
        logger.error(f"Error updating applications and sending emails: {str(e)}")
        raise