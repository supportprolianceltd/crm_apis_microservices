from celery import shared_task
from django.conf import settings
from job_application.models import JobApplication
from utils.screen import parse_resume, screen_resume, extract_resume_fields
from utils.email_utils import send_screening_notification
import requests
import mimetypes
import tempfile
import os
import time
import logging

logger = logging.getLogger('job_applications')

def get_job_requisition_by_id(job_requisition_id, auth_header):
    url = f"{settings.TALENT_ENGINE_URL}/api/talent-engine/requisitions/{job_requisition_id}/"
    response = requests.get(url, headers={'Authorization': auth_header}, timeout=10)
    if response.status_code == 200:
        return response.json()
    logger.warning(f"Failed to fetch job requisition {job_requisition_id}: {response.status_code}")
    return None

@shared_task
def screen_resumes_task(job_requisition_id, tenant_id, document_type, num_candidates, applications_data, auth_header):
    job_requisition = get_job_requisition_by_id(job_requisition_id, auth_header)
    if not job_requisition:
        logger.error("Job requisition not found.")
        return

    document_type_lower = document_type.lower()
    allowed_docs = [doc.lower() for doc in (job_requisition.get('documents_required') or [])]
    if document_type_lower not in allowed_docs and document_type_lower not in ['resume', 'curriculum vitae (cv)']:
        logger.error(f"Invalid document type: {document_type}")
        return

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

    logger.info(f"Screening {applications.count()} applications")
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
                shortlisted_app['status'] = 'shortlisted'
                employment_gaps = shortlisted_app.get('employment_gaps', [])
                event_type = "job.application.shortlisted.gaps" if employment_gaps else "job.application.shortlisted"
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
            send_screening_notification(rejected_app, tenant_id, event_type="job.application.rejected")

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




