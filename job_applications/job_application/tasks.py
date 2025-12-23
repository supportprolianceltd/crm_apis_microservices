import os
import time
import tempfile
import logging
import mimetypes
import numpy as np
import requests
import concurrent.futures

from celery import shared_task, group, chord
from celery.result import allow_join_result

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import JobApplication  # Fixed import (was .models)
from utils.screen import (
    screen_resume,
    screen_resume_batch,
    parse_resume,
    extract_resume_fields
)
from utils.email_utils import send_screening_notification

logger = logging.getLogger('job_applications')


def _append_status_history(app, new_status, automated=True, reason='Status update'):
    """
    Helper: Append status change to history (from original codebase).
    """
    if app.status != new_status:
        history_entry = {
            'status': new_status,
            'timestamp': timezone.now().isoformat(),
            'automated': automated,
            'reason': reason
        }
        if automated:
            history_entry['changed_by'] = {'system': 'daily_background_vetting'}
        
        if app.status_history:
            app.status_history.append(history_entry)
        else:
            app.status_history = [history_entry]

def _update_applications_without_notifications(shortlisted_candidates, job_requisition_id, num_candidates):
    """
    Adapted from _update_applications_and_queue_emails: Update statuses/history, but NO emails/notifications.
    """
    try:
        shortlisted_ids = {item['application_id'] for item in shortlisted_candidates}
        applications = JobApplication.active_objects.filter(job_requisition_id=job_requisition_id)
        
        with transaction.atomic():
            for app in applications:
                app_id_str = str(app.id)
                new_status = None
                if app_id_str in shortlisted_ids:
                    new_status = 'shortlisted'
                    _append_status_history(app, new_status, automated=True, reason='Automated by daily background vetting')
                    logger.info(f"Shortlisted app {app_id_str} (score: {app.screening_score})")
                else:
                    new_status = 'rejected'
                    _append_status_history(app, new_status, automated=True, reason='Automated by daily background vetting')
                    logger.info(f"Rejected app {app_id_str} (score: {app.screening_score})")
                
                if new_status:
                    app.status = new_status
                    app.current_stage = 'screening'
                    app.save(update_fields=['status', 'current_stage', 'status_history'])
        
        logger.info(f"Updated statuses for {len(shortlisted_candidates)} shortlisted / {applications.count() - len(shortlisted_candidates)} rejected")
        
    except Exception as e:
        logger.error(f"Error updating application statuses: {str(e)}")
        raise

def _fetch_all_open_requisitions():
    """
    Fetch all open published requisitions via API (global, cross-tenant).
    Uses /upcoming/public/jobs/ endpoint (your working URL) and handles pagination.
    """
    all_requisitions = []
    next_url = f"{settings.TALENT_ENGINE_URL}/api/talent-engine/requisitions/upcoming/public/jobs/"
    headers = {}  # Public endpoint, no auth needed

    while next_url:
        try:
            resp = requests.get(next_url, headers=headers, timeout=30)
            if resp.status_code != 200:
                logger.error(f"Failed to fetch upcoming requisitions: {resp.status_code} - {resp.text}")
                break
            
            data = resp.json()
            results = data.get('results', [])
            all_requisitions.extend(results)
            
            next_url = data.get('next')
            logger.info(f"Fetched {len(results)} requisitions from page; next: {bool(next_url)}")
        except Exception as e:
            logger.error(f"Error fetching requisitions page: {str(e)}")
            break
    
    # Filter for deadline ahead (already handled by endpoint, but double-check)
    today = timezone.now().date()
    filtered_requisitions = [
        req for req in all_requisitions
        if req.get('is_deleted', False) is False and req.get('deadline_date') and 
        timezone.datetime.strptime(req['deadline_date'], '%Y-%m-%d').date() >= today
    ]
    
    logger.info(f"Total open requisitions fetched: {len(filtered_requisitions)}")
    return filtered_requisitions

@shared_task
def daily_background_cv_vetting():
    """
    Daily background task: Full re-screening with status updates (shortlist/reject) across all open requisitions/tenants.
    Overrides prior results. No notifications.
    """
    task_start_time = time.perf_counter()
    logger.info("🚀 Starting daily background CV vetting with full workflow")
    
    try:
        # Step 1: Fetch open requisitions via public API (full details included)
        open_requisitions = _fetch_all_open_requisitions()
        
        if not open_requisitions:
            logger.info("No open requisitions found")
            return {"processed_requisitions": 0, "total_applications_vetted": 0}
        
        results = {
            "processed_requisitions": 0,
            "total_applications_vetted": 0,
            "shortlisted_count": 0,
            "rejected_count": 0
        }
        
        for req in open_requisitions:
            req_id = req['id']
            logger.info(f"Processing requisition {req_id}")
            
            # Step 2: Fetch applications (global, cross-tenant)
            applications = JobApplication.active_objects.filter(
                job_requisition_id=req_id,
                resume_status=True
            ).iterator()
            
            applications_list = list(applications)
            app_count = len(applications_list)
            logger.info(f"Found {app_count} applications with resumes for {req_id}")
            
            if not applications_list:
                logger.info(f"No applications for {req_id}, skipping")
                continue
            
            applications_data = [
                {"application_id": str(app.id), "full_name": app.full_name, "email": app.email}
                for app in applications_list
            ]
            
            # Step 3: Job requirements (from list response—no detail fetch needed)
            job_requirements = (
                f"{req.get('job_description', '')} "
                f"{req.get('qualification_requirement', '')} "
                f"{req.get('experience_requirement', '')} "
                f"{req.get('knowledge_requirement', '')}"
            ).strip()
            
            logger.info(f"Extracted requirements length for {req_id}: {len(job_requirements)} chars")
            
            if not job_requirements:
                logger.warning(f"No requirements for {req_id}, skipping")
                continue
            
            # num_candidates from req (default 5)
            num_candidates = req.get('number_of_candidates', 5)
            
            # Step 4: Vetting batch
            task = process_vetting_batch.delay(
                req_id, job_requirements, applications_data, num_candidates
            )
            with allow_join_result():
                vetting_result = task.get(timeout=1800)
            
            # Step 5: Update statuses (no notifs)
            shortlisted_candidates = vetting_result.get('shortlisted_candidates', [])
            _update_applications_without_notifications(shortlisted_candidates, req_id, num_candidates)
            
            # Aggregate
            results["processed_requisitions"] += 1
            results["total_applications_vetted"] += app_count
            results["shortlisted_count"] += len(shortlisted_candidates)
            results["rejected_count"] += app_count - len(shortlisted_candidates)
            
            logger.info(f"Req {req_id}: {len(shortlisted_candidates)} shortlisted from {app_count}")
        
        task_end_time = time.perf_counter()
        total_time = task_end_time - task_start_time
        results["total_time_seconds"] = round(total_time, 2)
        logger.info(f"📊 Daily vetting summary: {results}")
        return results
        
    except Exception as e:
        logger.error(f"Daily vetting failed: {str(e)}", exc_info=True)
        return {"status": "error", "detail": str(e)}



# @shared_task(bind=True, max_retries=3, soft_time_limit=1800, time_limit=3600)
# def process_vetting_batch(self, job_requisition_id, job_requirements, applications_data, num_candidates):
#     """
#     Updated: Score, normalize, return shortlisted for status updates. No notifs.
#     """
#     batch_start_time = time.perf_counter()
#     try:
#         logger.info(f"Vetting batch: {len(applications_data)} apps for req {job_requisition_id}")
        
#         application_ids = [app['application_id'] for app in applications_data]
#         applications = JobApplication.active_objects.filter(id__in=application_ids, resume_status=True)
#         applications_list = list(applications)
#         applications_map = {str(app.id): app for app in applications_list}
        
#         resume_texts = []
#         raw_results = []
#         for app_data in applications_data:
#             app = applications_map.get(app_data['application_id'])
#             if not app:
#                 continue
            
#             resume_text = (
#                 f"{app.qualification or ''} "
#                 f"{app.experience or ''} "
#                 f"{app.knowledge_skill or ''} "
#                 f"{app.cover_letter or ''}"
#             ).strip()
            
#             if resume_text:
#                 resume_texts.append(resume_text)
#                 raw_results.append({
#                     "application_id": app_data['application_id'],
#                     "full_name": app_data['full_name'],
#                     "email": app_data['email'],
#                     "resume_text": resume_text,
#                     "employment_gaps": getattr(app, 'employment_gaps', []),
#                     "success": True,
#                     "app_obj": app  # Temp for update
#                 })
#             else:
#                 raw_results.append({
#                     "application_id": app_data['application_id'],
#                     "full_name": app_data['full_name'],
#                     "email": app_data['email'],
#                     "error": "No resume data",
#                     "success": False,
#                     "app_obj": app
#                 })
        
#         # Score and override
#         shortlisted_candidates = []
#         if resume_texts:
#             scores = screen_resume_batch(resume_texts, job_requirements)
#             scores_array = np.array(scores)
#             min_score, max_score = scores_array.min(), scores_array.max()
#             if max_score > min_score:
#                 normalized_scores = (scores_array - min_score) / (max_score - min_score) * 100
#             else:
#                 normalized_scores = scores_array * 100
            
#             success_idx = 0
#             now = timezone.now().isoformat()
#             with transaction.atomic():
#                 for result in raw_results:
#                     if result['success']:
#                         score = round(float(normalized_scores[success_idx]), 2)
#                         app = result['app_obj']
#                         app.screening_status = [{'status': 'processed', 'score': score, 'updated_at': now}]
#                         app.screening_score = score
#                         if not result['employment_gaps']:
#                             resume_data = extract_resume_fields(result['resume_text'])
#                             app.employment_gaps = resume_data.get("employment_gaps", [])
#                         app.save(update_fields=['screening_status', 'screening_score', 'employment_gaps'])
                        
#                         result['score'] = score
#                         success_idx += 1
#                         logger.info(f"Vetted {result['application_id']}: score={score}")
#                     else:
#                         app = result['app_obj']
#                         if app:
#                             app.screening_status = [{'status': 'failed', 'score': 0.0, 'updated_at': now, 'error': result.get('error') }]
#                             app.screening_score = 0.0
#                             app.save(update_fields=['screening_status', 'screening_score'])
#                         result['score'] = 0.0
#                         logger.warning(f"Vetting failed for {result['application_id']}: {result.get('error')}")
            
#             # Sort successful and select top
#             successful = [r for r in raw_results if r['success']]
#             successful.sort(key=lambda x: x['score'], reverse=True)
#             shortlisted_candidates = successful[:num_candidates]
        
#         batch_end_time = time.perf_counter()
#         batch_time = batch_end_time - batch_start_time
        
#         logger.info(f"Vetting complete: {len(shortlisted_candidates)} shortlisted in {batch_time:.2f}s")
        
#         return {
#             "shortlisted_candidates": shortlisted_candidates,
#             "vetted_count": len(raw_results),
#             "batch_time_seconds": round(batch_time, 2)
#         }
        
#     except Exception as e:
#         logger.error(f"Vetting batch failed: {str(e)}")
#         raise self.retry(exc=e, countdown=60 ** self.request.retries)
@shared_task(bind=True, max_retries=3, soft_time_limit=1800, time_limit=3600)
def process_vetting_batch(self, job_requisition_id, job_requirements, applications_data, num_candidates):
    """
    Updated: Score, normalize, return shortlisted for status updates. No notifs.
    """
    batch_start_time = time.perf_counter()
    try:
        logger.info(f"Vetting batch: {len(applications_data)} apps for req {job_requisition_id} (reqs len: {len(job_requirements)})")
        
        application_ids = [app['application_id'] for app in applications_data]
        applications = JobApplication.active_objects.filter(id__in=application_ids, resume_status=True)
        applications_list = list(applications)
        applications_map = {str(app.id): app for app in applications_list}
        
        resume_texts = []
        raw_results = []
        for app_data in applications_data:
            app = applications_map.get(app_data['application_id'])
            if not app:
                continue
            
            resume_text = (
                f"{app.qualification or ''} "
                f"{app.experience or ''} "
                f"{app.knowledge_skill or ''} "
                f"{app.cover_letter or ''}"
            ).strip()
            
            if resume_text:
                resume_texts.append(resume_text)
                raw_results.append({
                    "application_id": app_data['application_id'],
                    "full_name": app_data['full_name'],
                    "email": app_data['email'],
                    "resume_text": resume_text,
                    "employment_gaps": getattr(app, 'employment_gaps', []),
                    "success": True,
                    "app_obj": app  # Temp for update—will strip later
                })
            else:
                raw_results.append({
                    "application_id": app_data['application_id'],
                    "full_name": app_data['full_name'],
                    "email": app_data['email'],
                    "error": "No resume data",
                    "success": False,
                    "app_obj": app
                })
        
        # Score and override
        shortlisted_candidates = []
        if resume_texts:
            scores = screen_resume_batch(resume_texts, job_requirements)
            logger.info(f"Raw scores for {len(scores)} texts: {scores[:3]}...")  # Sample log
            scores_array = np.array(scores)
            min_score, max_score = scores_array.min(), scores_array.max()
            if max_score > min_score:
                normalized_scores = (scores_array - min_score) / (max_score - min_score) * 100
            else:
                normalized_scores = scores_array * 100
            
            success_idx = 0
            now = timezone.now().isoformat()
            with transaction.atomic():
                for result in raw_results:
                    if result['success']:
                        score = round(float(normalized_scores[success_idx]), 2)
                        app = result['app_obj']
                        app.screening_status = [{'status': 'processed', 'score': score, 'updated_at': now}]
                        app.screening_score = score
                        if not result['employment_gaps']:
                            resume_data = extract_resume_fields(result['resume_text'])
                            app.employment_gaps = resume_data.get("employment_gaps", [])
                        app.save(update_fields=['screening_status', 'screening_score', 'employment_gaps'])
                        
                        result['score'] = score
                        success_idx += 1
                        logger.info(f"Vetted {result['application_id']}: score={score}")
                    else:
                        app = result['app_obj']
                        if app:
                            app.screening_status = [{'status': 'failed', 'score': 0.0, 'updated_at': now, 'error': result.get('error') }]
                            app.screening_score = 0.0
                            app.save(update_fields=['screening_status', 'screening_score'])
                        result['score'] = 0.0
                        logger.warning(f"Vetting failed for {result['application_id']}: {result.get('error')}")
            
            # Sort successful and select top
            successful = [r for r in raw_results if r['success']]
            successful.sort(key=lambda x: x['score'], reverse=True)
            shortlisted_candidates = successful[:num_candidates]
        
        # Strip non-serializable 'app_obj' before return (Celery JSON issue)
        for result in raw_results:
            result.pop('app_obj', None)  # Safe remove
        
        batch_end_time = time.perf_counter()
        batch_time = batch_end_time - batch_start_time
        
        logger.info(f"Vetting complete: {len(shortlisted_candidates)} shortlisted in {batch_time:.2f}s")
        
        return {
            "shortlisted_candidates": shortlisted_candidates,  # Now serializable
            "vetted_count": len(raw_results),
            "batch_time_seconds": round(batch_time, 2)
        }
        
    except Exception as e:
        logger.error(f"Vetting batch failed: {str(e)}")
        raise self.retry(exc=e, countdown=60 ** self.request.retries)

@shared_task
def auto_screen_all_applications():
    """
    Automatically screen all pending applications for open job requisitions at midnight.
    This task is scheduled via Celery Beat.
    """
    logger.info("Starting auto-screen-all-applications task")
    try:
        # Fetch all open job requisitions (assuming auth header; adjust if needed)
        headers = {'Authorization': f"Bearer {getattr(settings, 'JWT_SECRET_KEY', '')}"}
        response = requests.get(
            f"{settings.TALENT_ENGINE_URL}/api/talent-engine/requisitions/",
            headers=headers,
            timeout=30
        )
        if response.status_code != 200:
            logger.error(f"Failed to fetch open requisitions: {response.status_code} - {response.text}")
            return {"status": "error", "detail": "Failed to fetch requisitions"}

        requisitions = response.json()
        open_requisitions = [req for req in requisitions if req.get('status') == 'open']

        results = {"processed_requisitions": 0, "total_applications_screened": 0}

        for req in open_requisitions:
            job_requisition_id = req['id']
            logger.info(f"Processing open requisition {job_requisition_id}")

            # Fetch pending applications (those with resume but no screening_status)
            applications = JobApplication.active_objects.filter(
                job_requisition_id=job_requisition_id,
                resume_status=True
            ).exclude(screening_status__isnull=True).exclude(screening_status__0__status="processed")

            if not applications.exists():
                logger.info(f"No pending applications for requisition {job_requisition_id}")
                continue

            applications_data = list(applications.values('id', 'full_name', 'email'))
            num_candidates = req.get('number_of_candidates', 5)  # Default to 5 if not specified

            # Trigger the screening task for this batch
            screen_resumes_task.delay(
                job_requisition_id=job_requisition_id,
                document_type='resume',
                num_candidates=num_candidates,
                applications_data=applications_data,
                job_requisition=req
            )

            results["processed_requisitions"] += 1
            results["total_applications_screened"] += len(applications_data)
            logger.info(f"Queued screening for {len(applications_data)} apps in requisition {job_requisition_id}")

        logger.info(f"Auto-screening completed: {results}")
        return results

    except Exception as e:
        logger.error(f"Auto-screen-all-applications failed: {str(e)}", exc_info=True)
        return {"status": "error", "detail": str(e)}


@shared_task
def screen_resumes_task(job_requisition_id, document_type, num_candidates, applications_data, job_requisition):
    logger.info(f"Starting screen_resumes_task for job_requisition_id: {job_requisition_id}")
    document_type_lower = document_type.lower()
    allowed_docs = [doc.lower() for doc in (job_requisition.get('documents_required') or [])]
    if document_type_lower not in allowed_docs and document_type_lower not in ['resume', 'curriculum vitae (cv)']:
        logger.error(f"Invalid document type: {document_type}")
        return

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

    logger.info(f"Screening {applications.count()} applications for job_requisition_id: {job_requisition_id}")
    if not applications.exists():
        logger.warning("No applications with resume_status=True found.")
        return

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
                    return {"app": app, "success": False, "error": f"No {document_type} document found"}
                file_url = cv_doc['file_url']

            headers = {"Authorization": f"Bearer {settings.SUPABASE_KEY}"}
            response = requests.get(file_url, headers=headers, timeout=10)
            if response.status_code != 200:
                app.screening_status = 'failed'
                app.screening_score = 0.0
                app.save()
                return {"app": app, "success": False, "error": f"Failed to download resume from {file_url}"}

            content_type = response.headers.get('content-type', '')
            file_ext = mimetypes.guess_extension(content_type) or os.path.splitext(file_url)[1] or '.pdf'
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_ext)
            temp_file.write(response.content)
            temp_file.close()
            temp_file_path = temp_file.name
            return {"app": app, "success": True, "temp_file_path": temp_file_path, "file_url": file_url}
        except Exception as e:
            app.screening_status = 'failed'
            app.screening_score = 0.0
            app.save()
            return {"app": app, "success": False, "error": f"Download error: {str(e)}"}

    # Download resumes
    download_results = []
    applications_list = list(applications)
    applications_data_map = {str(a['application_id']): a for a in applications_data}
    for app in applications_list:
        result = download_resume(app, applications_data_map.get(str(app.id)), document_type_lower)
        download_results.append(result)

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
    for result in download_results:
        results.append(parse_and_screen(result, job_requirements))

    shortlisted = [r for r in results if r.get("success")]
    failed_applications = [r for r in results if not r.get("success")]

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
                shortlisted_app['job_requisition_title'] = app.job_requisition_title
                shortlisted_app['status'] = 'shortlisted'
                employment_gaps = shortlisted_app.get('employment_gaps', [])
                event_type = "job.application.shortlisted.gaps" if employment_gaps else "job.application.shortlisted"
                send_screening_notification(
                    shortlisted_app,
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
                "job_requisition_title": app.job_requisition_title,
                "status": "rejected",
                "score": getattr(app, "screening_score", None)
            }
            send_screening_notification(rejected_app, event_type="job.application.rejected")

    logger.info(f"Screening complete for job requisition {job_requisition_id}")

    # Automatically close the requisition via public endpoint
    close_url = f"{settings.TALENT_ENGINE_URL}/api/talent-engine/requisitions/public/close/{job_requisition_id}/"
    try:
        close_resp = requests.post(close_url, timeout=10)
        if close_resp.status_code == 200:
            logger.info(f"Job requisition {job_requisition_id} successfully closed via public endpoint.")
        else:
            logger.warning(f"Failed to close job requisition {job_requisition_id}: {close_resp.text}")
    except Exception as e:
        logger.error(f"Error closing job requisition {job_requisition_id} via public endpoint: {str(e)}")

        


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
    batch_start_time = time.perf_counter()
    per_app_timings = []  # Collect for final aggregation
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
        
        batch_end_time = time.perf_counter()
        total_batch_time = batch_end_time - batch_start_time
        
        # Enhanced visible logging for total time
        logger.warning("=" * 80)
        logger.warning(f"🚀 ASYNCHRONOUS BATCH SCREENING COMPLETED 🚀")
        logger.warning(f"📊 TOTAL TIME FOR {len(applications_data)} APPLICATIONS: {total_batch_time:.2f} SECONDS")
        logger.warning(f"⏱️  AVERAGE PER APPLICATION: {total_batch_time / len(applications_data):.2f} SECONDS")
        if per_app_timings:
            logger.warning(f"📈 PER-APP TIMINGS SUMMARY: MIN={min(per_app_timings):.2f}s, MAX={max(per_app_timings):.2f}s, AVG={sum(per_app_timings)/len(per_app_timings):.2f}s")
        logger.warning("=" * 80)
            
        logger.info(f"Completed large batch processing for {len(applications_data)} applications")
        return final_result
        
    except Exception as e:
        logger.error(f"Large batch processing failed: {str(e)}")
        batch_end_time = time.perf_counter()
        total_batch_time = batch_end_time - batch_start_time
        logger.warning("=" * 80)
        logger.warning(f"💥 ASYNCHRONOUS BATCH SCREENING FAILED 💥")
        logger.warning(f"⏱️  TOTAL ELAPSED TIME: {total_batch_time:.2f} SECONDS")
        logger.warning("=" * 80)
        raise self.retry(exc=e, countdown=60)

@shared_task(bind=True, max_retries=2, soft_time_limit=1800, time_limit=3600)
def process_resume_chunk(self, job_requisition_id, tenant_id, document_type, 
                        applications_chunk, chunk_index, total_chunks, role=None, 
                        branch=None, authorization_header="", job_requirements=None):
    """
    Process a chunk of applications with batch scoring and normalization
    """
    chunk_start_time = time.perf_counter()
    chunk_per_app_timings = []
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
        document_type_lower = document_type.lower()
        
        # Construct resume texts from model fields
        for app in applications_list:
            # Construct resume text from model fields
            resume_text = (
                f"{app.qualification or ''} "
                f"{app.experience or ''} "
                f"{app.knowledge_skill or ''} "
                f"{app.cover_letter or ''}"
            ).strip()
            
            if resume_text:
                resume_texts.append(resume_text)
                results.append({
                    "application_id": str(app.id),
                    "full_name": app.full_name,
                    "email": app.email,
                    "resume_text": resume_text,
                    "employment_gaps": getattr(app, 'employment_gaps', []),
                    "success": True
                })
            else:
                # If no data, create failed result
                results.append({
                    "application_id": str(app.id),
                    "full_name": app.full_name,
                    "email": app.email,
                    "error": f"No {document_type_lower} data found in model fields",
                    "success": False
                })

        # Batch score resumes
        if resume_texts:
            # Concatenate requirements into a single string for compatibility with screen_resume_batch
            job_desc = (
                f"{job_requirements.get('description', '')} "
                f"{job_requirements.get('qualifications', '')} "
                f"{job_requirements.get('experience', '')} "
                f"{job_requirements.get('skills', '')}"
            ).strip()
            
            # Use the updated screen_resume function that handles batch processing
            scores = screen_resume_batch(resume_texts, job_desc)
            
            # Min-max normalization
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
                    success_idx += 1
                    # Simulate processing time for batch (negligible for construction)
                    chunk_per_app_timings.append(0.01)  # Placeholder minimal time

        # Step 3: Update applications with scores
        applications_map = {str(app.id): app for app in applications_list}
        now = timezone.now().isoformat()
        with transaction.atomic():
            for result in results:
                app = applications_map.get(result['application_id'])
                if app and result['success']:
                    app.screening_status = [{'status': 'processed', 'score': result['score'], 'updated_at': now}]
                    app.screening_score = result['score']
                    if not getattr(app, 'employment_gaps', []):  # Only set if empty
                        app.employment_gaps = result['employment_gaps']
                    app.save(update_fields=['screening_status', 'screening_score', 'employment_gaps'])
                    logger.info(f"Updated screening for app {app.id}: score={result['score']}, status=processed")
                elif app:
                    app.screening_status = [{'status': 'failed', 'score': 0.0, 'updated_at': now, 'error': result.get('error', 'Unknown error')}]
                    app.screening_score = 0.0
                    app.save(update_fields=['screening_status', 'screening_score'])
                    logger.info(f"Updated screening for app {app.id}: status=failed, score=0.0")

        # Chunk timing summary log
        chunk_end_time = time.perf_counter()
        chunk_time = chunk_end_time - chunk_start_time
        logger.info(f"🏗️  CHUNK {chunk_index + 1}/{total_chunks} COMPLETE: {chunk_time:.2f}s for {len(results)} apps")

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
                    "employment_gaps": result.get("employment_gaps", [])
                })
            else:
                serializable_result["error"] = result.get("error", "Unknown error")
            
            serializable_results.append(serializable_result)

        return {
            'chunk_index': chunk_index,
            'results': serializable_results,
            'processed_count': len(results),
            'chunk_timings': {
                "chunk_time_seconds": round(chunk_time, 2),
                "per_app_timings": chunk_per_app_timings
            }
        }
        
    except Exception as e:
        logger.error(f"Chunk {chunk_index} processing failed: {str(e)}")
        chunk_end_time = time.perf_counter()
        chunk_time = chunk_end_time - chunk_start_time
        logger.warning(f"💥 CHUNK {chunk_index + 1} FAILED: {chunk_time:.2f}s")
        raise self.retry(exc=e, countdown=30)


@shared_task(bind=True, max_retries=2, soft_time_limit=1800, time_limit=3600)
def aggregate_screening_results(self, chunk_results, job_requisition_id, tenant_id, 
                              num_candidates, document_type, authorization_header=""):
    """
    Aggregate results from all chunks, update statuses, and send email notifications
    """
    agg_start_time = time.perf_counter()
    all_per_app_timings = []
    try:
        all_results = []
        total_processed = 0
        
        for chunk_result in chunk_results:
            all_results.extend(chunk_result['results'])
            total_processed += chunk_result['processed_count']
            # Aggregate timings from chunks
            if 'chunk_timings' in chunk_result:
                all_per_app_timings.extend(chunk_result['chunk_timings']['per_app_timings'])
        
        # Separate successful and failed
        shortlisted = [r for r in all_results if r.get("success")]
        failed_applications = [r for r in all_results if not r.get("success")]
        
        # Sort and select top candidates
        shortlisted.sort(key=lambda x: x['score'], reverse=True)
        final_shortlisted = shortlisted[:num_candidates] if num_candidates > 0 else shortlisted
        
        # Get job requisition for notifications
        job_requisition = get_job_requisition_by_id(job_requisition_id, authorization_header)
        
        # Update application statuses and queue notifications in background
        _update_applications_and_queue_emails(
            final_shortlisted, job_requisition_id, tenant_id, job_requisition
        )
        
        agg_end_time = time.perf_counter()
        agg_time = agg_end_time - agg_start_time

        result_data = {
            "detail": f"Screened {total_processed} applications using '{document_type}', shortlisted {len(final_shortlisted)} candidates.",
            "shortlisted_candidates": final_shortlisted,
            "failed_applications": failed_applications,
            "number_of_candidates": num_candidates,
            "document_type": document_type,
            "timing_summary": {
                "aggregation_time_seconds": round(agg_time, 2),
                "applications_processed": total_processed,
                "per_application_timings": all_per_app_timings,
                "average_per_application_seconds": round(sum(all_per_app_timings) / len(all_per_app_timings), 2) if all_per_app_timings else 0
            }
        }
        
        logger.info(f"Aggregation completed: {len(final_shortlisted)} shortlisted from {total_processed} applications in {agg_time:.2f}s")
        return result_data
        
    except Exception as e:
        logger.error(f"Result aggregation failed: {str(e)}")
        agg_end_time = time.perf_counter()
        agg_time = agg_end_time - agg_start_time
        logger.warning(f"💥 AGGREGATION FAILED: {agg_time:.2f}s")
        raise self.retry(exc=e, countdown=30)

@shared_task(bind=True, max_retries=3)
def send_notification_task(self, applicant_data, tenant_id, event_type, employment_gaps=None):
    """
    Background task to send screening notifications with retries.
    """
    try:
        send_screening_notification(
            applicant=applicant_data,
            tenant_id=tenant_id,
            event_type=event_type,
            employment_gaps=employment_gaps
        )
        logger.info(f"Sent {event_type} notification to {applicant_data['email']}")
    except Exception as e:
        logger.error(f"Failed to send {event_type} notification to {applicant_data['email']}: {str(e)}")
        raise self.retry(exc=e, countdown=60)

def _append_status_history(app, new_status, automated=True, changed_by=None, reason='Status update'):
    """
    Helper function to append status change to history.
    """
    if app.status != new_status:
        history_entry = {
            'status': new_status,
            'timestamp': timezone.now().isoformat(),
            'automated': automated,
            'reason': reason
        }
        if automated:
            history_entry['changed_by'] = {'system': 'resume_screening'}
        else:
            history_entry['changed_by'] = changed_by or {}
        
        if app.status_history:
            app.status_history.append(history_entry)
        else:
            app.status_history = [history_entry]

def _update_applications_and_queue_emails(shortlisted_candidates, job_requisition_id, tenant_id, job_requisition):
    """
    Update application statuses and queue email notifications in background.
    """
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
                    new_status = 'shortlisted'
                    _append_status_history(app, new_status, automated=True, reason='Automated by resume screening')
                    app.status = new_status
                    app.current_stage = 'screening'  # Sync stage after screening
                    app.save(update_fields=['status', 'current_stage', 'status_history'])
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
                            "job_requisition_title": app.job_requisition_title,
                            "status": "shortlisted",
                            "score": shortlisted_app.get('score'),
                            "explanation": shortlisted_app.get('explanation')
                        }
                        employment_gaps = shortlisted_app.get('employment_gaps', [])
                        event_type = "candidate.shortlisted.gaps" if employment_gaps else "candidate.shortlisted"
                        # Queue notification in background
                        send_notification_task.delay(
                            applicant_data=applicant_data,
                            tenant_id=tenant_id,
                            event_type=event_type,
                            employment_gaps=employment_gaps
                        )
                        logger.info(f"Queued shortlisted notification for {shortlisted_app['email']}")
                else:
                    new_status = 'rejected'
                    _append_status_history(app, new_status, automated=True, reason='Automated by resume screening')
                    app.status = new_status
                    app.current_stage = 'screening'  # Sync stage after screening
                    app.save(update_fields=['status', 'current_stage', 'status_history'])
                    applicant_data = {
                        "email": app.email,
                        "full_name": app.full_name,
                        "application_id": app_id_str,
                        "job_requisition_id": job_requisition_id,
                        "job_requisition_title": app.job_requisition_title,
                        "status": "rejected",
                        "score": getattr(app, "screening_score", None)
                    }
                    # Queue rejection notification in background
                    send_notification_task.delay(
                        applicant_data=applicant_data,
                        tenant_id=tenant_id,
                        event_type="candidate.rejected"
                    )
                    logger.info(f"Queued rejection notification for {app.email}")
    except Exception as e:
        logger.error(f"Error updating applications and queuing emails: {str(e)}")
        raise

