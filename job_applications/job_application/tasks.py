import os
import time
import logging
import tempfile
import requests
import mimetypes
import gzip
import io
import numpy as np
from celery import shared_task, group, chord
from celery.result import allow_join_result
from django.conf import settings
from django.db import transaction
from django.utils import timezone
import concurrent.futures
from job_application.models import JobApplication

from utils.screen import parse_resume, screen_resume, extract_resume_fields, screen_resume_batch
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
                job_requirements={
                    'description': (job_requisition.get('job_description') or ''),
                    'qualifications': (job_requisition.get('qualification_requirement') or ''),
                    'experience': (job_requisition.get('experience_requirement') or ''),
                    'skills': (job_requisition.get('knowledge_requirement') or '')
                }
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
                        branch=None, authorization_header="", job_requirements=None):
    """
    Process a chunk of applications with batch scoring and normalization
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
        resume_texts = []
        temp_file_paths = []
        document_type_lower = document_type.lower()
        
        # Build file info for each application
        file_infos = []
        for app in applications_list:
            app_data = applications_data_map.get(str(app.id))
            if app_data and 'file_url' in app_data:
                file_url = app_data['file_url']
                compression = app_data.get('compression')
                original_name = app_data.get('original_name', 'resume.pdf')
            else:
                cv_doc = next(
                    (doc for doc in app.documents if doc['document_type'].lower() == document_type_lower),
                    None
                )
                if cv_doc:
                    file_url = cv_doc['file_url']
                    compression = cv_doc.get('compression')
                    original_name = cv_doc.get('original_name', 'resume.pdf')
                else:
                    file_url = None

            if file_url:
                file_infos.append({
                    "application_id": str(app.id),
                    "full_name": app.full_name,
                    "email": app.email,
                    "file_url": file_url,
                    "compression": compression,
                    "original_name": original_name
                })
            else:
                # If no file URL, create failed result
                results.append({
                    "application_id": str(app.id),
                    "full_name": app.full_name,
                    "email": app.email,
                    "error": f"No {document_type_lower} document found",
                    "success": False
                })

        # Step 1: Download and parse resumes in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_info = {
                executor.submit(
                    _download_and_parse_resume,
                    file_info["application_id"],
                    file_info["full_name"],
                    file_info["email"],
                    file_info["file_url"],
                    file_info["compression"],
                    file_info["original_name"],
                    document_type_lower
                ): file_info for file_info in file_infos
            }
            for future in concurrent.futures.as_completed(future_to_info):
                result = future.result()
                if result["success"]:
                    resume_texts.append(result["resume_text"])
                    temp_file_paths.append(result["temp_file_path"])
                results.append(result)

        # Step 2: Batch score resumes
        if resume_texts:
            # Use the updated screen_resume function that handles batch processing
            scores = screen_resume_batch(resume_texts, job_requirements)
            
            # Min-max normalization
            import numpy as np
            scores_array = np.array(scores)
            min_score, max_score = scores_array.min(), scores_array.max()
            if max_score > min_score:
                normalized_scores = (scores_array - min_score) / (max_score - min_score) * 100
            else:
                normalized_scores = scores_array * 100  # Avoid division by zero
            
            # Update results with scores
            success_idx = 0
            for result in results:
                if result['success']:
                    result['score'] = round(float(normalized_scores[success_idx]), 2)
                    result['screening_status'] = 'processed'
                    success_idx += 1

        # Step 3: Update applications with scores
        applications_map = {str(app.id): app for app in applications_list}
        for result in results:
            app = applications_map.get(result['application_id'])
            if app and result['success']:
                app.screening_status = 'processed'
                app.screening_score = result['score']
                app.employment_gaps = result['employment_gaps']
                app.save()
            elif app:
                app.screening_status = 'failed'
                app.screening_score = 0.0
                app.save()
            
            # Clean up temporary file
            if result.get('temp_file_path') and os.path.exists(result['temp_file_path']):
                os.unlink(result['temp_file_path'])

        # Return only serializable data
        serializable_results = []
        for result in results:
            serializable_result = {
                "application_id": result["application_id"],
                "full_name": result["full_name"],
                "email": result["email"],
                "success": result["success"]
            }
            if result["success"]:
                serializable_result.update({
                    "score": result.get("score", 0),
                    "screening_status": result.get("screening_status", "processed"),
                    "employment_gaps": result.get("employment_gaps", [])
                })
            else:
                serializable_result["error"] = result.get("error", "Unknown error")
            
            serializable_results.append(serializable_result)

        return {
            'chunk_index': chunk_index,
            'results': serializable_results,
            'processed_count': len(results)
        }
        
    except Exception as e:
        logger.error(f"Chunk {chunk_index} processing failed: {str(e)}")
        raise self.retry(exc=e, countdown=30)
    
    
def _download_and_parse_resume(application_id, full_name, email, file_url, compression, original_name, document_type_lower):
    try:
        headers = {"Authorization": f"Bearer {settings.SUPABASE_KEY}"}
        response = requests.get(file_url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            return {
                "application_id": application_id,
                "full_name": full_name,
                "email": email,
                "error": f"Download failed: HTTP {response.status_code}",
                "success": False
            }

        # Handle compressed files
        content_type = response.headers.get('content-type', '')
        file_content = response.content

        if compression == 'gzip' or file_url.endswith('.gz'):
            try:
                file_content = gzip.decompress(file_content)
                content_type = mimetypes.guess_type(original_name)[0] or 'application/pdf'
            except Exception as e:
                return {
                    "application_id": application_id,
                    "full_name": full_name,
                    "email": email,
                    "error": f"Decompression error: {str(e)}",
                    "success": False
                }

        # Save to temporary file for parsing
        file_ext = mimetypes.guess_extension(content_type) or '.pdf'
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_ext)
        temp_file.write(file_content)
        temp_file.close()
        temp_file_path = temp_file.name

        # Parse resume - REMOVE is_compressed parameter
        resume_text = parse_resume(temp_file_path)
        
        if not resume_text:
            return {
                "application_id": application_id,
                "full_name": full_name,
                "email": email,
                "error": "Failed to parse resume",
                "success": False
            }

        # Extract fields
        resume_data = extract_resume_fields(resume_text, resume_filename=original_name)
        employment_gaps = resume_data.get("employment_gaps", [])
        
        return {
            "application_id": application_id,
            "full_name": full_name,
            "email": email,
            "resume_text": resume_text,
            "employment_gaps": employment_gaps,
            "temp_file_path": temp_file_path,
            "success": True
        }
        
    except Exception as e:
        return {
            "application_id": application_id,
            "full_name": full_name,
            "email": email,
            "error": f"Processing error: {str(e)}",
            "success": False
        }


@shared_task(bind=True, max_retries=2, soft_time_limit=1800, time_limit=3600)
def aggregate_screening_results(self, chunk_results, job_requisition_id, tenant_id, 
                              num_candidates, document_type, authorization_header=""):
    """
    Aggregate results from all chunks, update statuses, and send email notifications
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
        
        # Update application statuses and send notifications
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
    try:
        shortlisted_ids = {item['application_id'] for item in shortlisted_candidates}
        applications = JobApplication.active_objects.filter(
            job_requisition_id=job_requisition_id,
            tenant_id=tenant_id
        )
        
        with transaction.atomic():
            for app in applications:
                app_id_str = str(app.id)
                if app_id_str in shortlisted_ids:
                    app.status = 'shortlisted'
                    app.save()
                    shortlisted_app = next(
                        (item for item in shortlisted_candidates if item['application_id'] == app_id_str), 
                        None
                    )
                    if shortlisted_app:
                        applicant_data = {
                            "email": shortlisted_app['email'],
                            "full_name": shortlisted_app['full_name'],
                            "application_id": shortlisted_app['application_id'],
                            "job_requisition_id": job_requisition_id,
                            "status": "shortlisted",
                            "score": shortlisted_app.get('score'),
                            "explanation": shortlisted_app.get('explanation')
                        }
                        employment_gaps = shortlisted_app.get('employment_gaps', [])
                        event_type = "candidate.shortlisted.gaps" if employment_gaps else "candidate.shortlisted"
                        try:
                            send_screening_notification(
                                applicant=applicant_data,
                                tenant_id=tenant_id,
                                event_type=event_type,
                                employment_gaps=employment_gaps
                            )
                            logger.info(f"Sent shortlisted email to {shortlisted_app['email']}")
                        except Exception as e:
                            logger.warning(f"Retrying notification for {shortlisted_app['email']} due to: {str(e)}")
                            # Retry once after a delay
                            time.sleep(5)
                            send_screening_notification(
                                applicant=applicant_data,
                                tenant_id=tenant_id,
                                event_type=event_type,
                                employment_gaps=employment_gaps
                            )
                else:
                    app.status = 'rejected'
                    app.save()
                    applicant_data = {
                        "email": app.email,
                        "full_name": app.full_name,
                        "application_id": app_id_str,
                        "job_requisition_id": job_requisition_id,
                        "status": "rejected",
                        "score": getattr(app, "screening_score", None)
                    }
                    try:
                        send_screening_notification(
                            applicant=applicant_data,
                            tenant_id=tenant_id,
                            event_type="candidate.rejected"
                        )
                        logger.info(f"Sent rejection email to {app.email}")
                    except Exception as e:
                        logger.warning(f"Retrying notification for {app.email} due to: {str(e)}")
                        time.sleep(5)
                        send_screening_notification(
                            applicant=applicant_data,
                            tenant_id=tenant_id,
                            event_type="candidate.rejected"
                        )
    except Exception as e:
        logger.error(f"Error updating applications and sending emails: {str(e)}")
        raise