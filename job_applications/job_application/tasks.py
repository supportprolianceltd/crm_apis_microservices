import os
import requests
import mimetypes
import tempfile
import logging
from datetime import date
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from django.db import connection
from job_application.models import JobApplication
from utils.screen import parse_resume, screen_resume, extract_resume_fields
from utils.email_utils import send_screening_notification

logger = logging.getLogger('job_applications')

@shared_task(bind=True, max_retries=3)
def auto_screen_all_applications(self):
    try:
        today = timezone.now().date()
        logger.info(f"Starting auto_screen_all_applications task for date: {today}")

        url = f"{settings.TALENT_ENGINE_URL}/api/talent-engine/requisitions/public/published/"
        try:
            logger.info(f"Fetching requisitions from {url}")
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            logger.info(f"Received {data.get('count', 0)} requisitions")
        except Exception as e:
            logger.error(f"Failed to fetch published requisitions: {str(e)}")
            raise self.retry(exc=e, countdown=60)

        if not data.get("results"):
            logger.warning("No published requisitions found.")
            return

        for requisition in data.get("results", []):
            deadline_str = requisition.get("deadline_date")
            if not deadline_str:
                logger.info(f"Skipping requisition {requisition['id']} (no deadline date)")
                continue

            try:
                deadline_date = date.fromisoformat(deadline_str)
            except ValueError:
                logger.error(f"Invalid deadline date format for requisition {requisition['id']}: {deadline_str}")
                continue

            logger.info(f"Checking requisition {requisition['id']}: deadline_date={deadline_date}, today={today}")
            if deadline_date != today:
                logger.info(f"Skipping requisition {requisition['id']} (deadline {deadline_date} != {today})")
                continue

            job_requisition_id = requisition["id"]
            document_type = "resume"
            num_candidates = requisition.get("num_of_applications", 0)

            # Force evaluation of queryset here to avoid "cursor already closed"
            applications_queryset = JobApplication.active_objects.filter(
                job_requisition_id=str(job_requisition_id),
                resume_status=True
            )
            applications = list(applications_queryset)
            logger.info(f"Found {len(applications)} applications for requisition {job_requisition_id}")

            if not applications:
                logger.warning(f"No eligible applications for requisition {job_requisition_id}")
                continue

            # Build list of dicts to pass to Celery
            applications_data = [
                {"application_id": app.id, "file_url": app.get_resume_url()} for app in applications
            ]

            logger.info(f"Triggering screening for requisition {job_requisition_id} with {len(applications_data)} applications")

            # Pass only raw data (not model instances) to Celery
            screen_resumes_task.delay(
                job_requisition_id,
                document_type,
                num_candidates,
                applications_data,
                requisition
            )
            
    except Exception as e:
        logger.error(f"Unexpected error in auto_screen_all_applications: {str(e)}")
        raise self.retry(exc=e, countdown=120)

@shared_task(bind=True, max_retries=3)
def screen_resumes_task(self, job_requisition_id, document_type, num_candidates, applications_data, job_requisition):
    try:
        logger.info(f"Starting screen_resumes_task for job_requisition_id: {job_requisition_id}")
        
        # Convert document type to lowercase for comparison
        document_type_lower = document_type.lower()
        
        # Get allowed document types from requisition
        allowed_docs = [doc.lower() for doc in (job_requisition.get('documents_required') or [])]
        
        # Check if document type is valid
        if document_type_lower not in allowed_docs and document_type_lower not in ['resume', 'curriculum vitae (cv)']:
            logger.error(f"Invalid document type: {document_type}")
            return

        # Get applications to process
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
                    # Find the document with the matching type
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

                # Download the file
                headers = {"Authorization": f"Bearer {settings.SUPABASE_KEY}"}
                response = requests.get(file_url, headers=headers, timeout=10)
                if response.status_code != 200:
                    app.screening_status = 'failed'
                    app.screening_score = 0.0
                    app.save()
                    return {"app": app, "success": False, "error": f"Failed to download resume from {file_url}"}

                # Determine file extension
                content_type = response.headers.get('content-type', '')
                file_ext = mimetypes.guess_extension(content_type) or os.path.splitext(file_url)[1] or '.pdf'
                
                # Save to temporary file
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

        # Prepare job requirements for screening
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
                # Parse resume
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
                        "error": f"Failed to parse resume for file: {file_url}",
                        "success": False
                    }
                    
                # Screen resume
                score = screen_resume(resume_text, job_requirements)
                resume_data = extract_resume_fields(resume_text)
                employment_gaps = resume_data.get("employment_gaps", [])
                
                # Update application
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

        # Process all applications
        results = []
        for result in download_results:
            results.append(parse_and_screen(result, job_requirements))

        # Separate successful and failed screenings
        shortlisted = [r for r in results if r.get("success")]
        failed_applications = [r for r in results if not r.get("success")]

        # Sort by score and select top candidates
        shortlisted.sort(key=lambda x: x['score'], reverse=True)
        final_shortlisted = shortlisted[:num_candidates]
        shortlisted_ids = {item['application_id'] for item in final_shortlisted}

        # Update application statuses and send notifications
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
                    tenant_id = applications_data_map.get(app_id_str, {}).get('tenant_id')
                    send_screening_notification(
                        shortlisted_app,
                        tenant_id=tenant_id,
                        event_type=event_type,
                        employment_gaps=employment_gaps,
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
                send_screening_notification(rejected_app, tenant_id=tenant_id, event_type="job_application.rejected")

        logger.info(f"Screening complete for job requisition {job_requisition_id}")

        # Automatically close the requisition via public endpoint
        #UPDATE THIS CLOSE REQUISITION TO OCCUR IN BATCH PROCESSING, SEND IT AS A LIST SO THE REQUISITION SERVICE UPDATE IN A SINGLE BATCH.
        # close_url = f"{settings.TALENT_ENGINE_URL}/api/talent-engine/requisitions/public/close/"
      
        close_url = f"{settings.TALENT_ENGINE_URL}/api/talent-engine/requisitions/public/close/batch/"

        try:
            batch_payload = {"job_requisition_ids": [job_requisition_id]}  # add more if needed
            close_resp = requests.post(close_url, json=batch_payload, timeout=10)
            if close_resp.status_code == 200:
                logger.info(f"Job requisitions closed via batch endpoint: {batch_payload['job_requisition_ids']}")
            else:
                logger.warning(f"Failed to close job requisitions: {close_resp.text}")
        except Exception as e:
            logger.error(f"Error closing job requisitions via batch endpoint: {str(e)}")

            
    except Exception as e:
        logger.error(f"Unexpected error in screen_resumes_task: {str(e)}")
        raise self.retry(exc=e, countdown=120)