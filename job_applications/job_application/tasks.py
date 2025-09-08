#tasks.py

from celery import shared_task
from django.conf import settings
from .models import JobApplication
from job_applications.celery_task import screen_resumes_task
import requests
import logging
from datetime import date

logger = logging.getLogger('job_applications')

@shared_task
def auto_screen_all_applications():
    # Fetch all published requisitions with future deadline (public endpoint)
    url = f"{settings.TALENT_ENGINE_URL}/api/talent-engine/requisitions/public/published/"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.error(f"Failed to fetch published requisitions: {str(e)}")
        return

    today = date.today().isoformat()
    for requisition in data.get("results", []):
        # Only trigger screening if today is the deadline date
        if requisition.get("deadline_date") != today:
            continue

        job_requisition_id = requisition["id"]
        tenant_id = requisition["id"].split('-')[0]  # Adjust if needed
        document_type = "resume"  # Or requisition['documents_required'][0] if available
        num_candidates = requisition.get("number_of_candidates", 0)
        # Get all applications for this requisition
        applications = JobApplication.active_objects.filter(
            job_requisition_id=job_requisition_id,
            tenant_id=tenant_id,
            resume_status=True
        )
        applications_data = [
            {"application_id": app.id, "file_url": app.get_resume_url()} for app in applications
        ]
        # Trigger screening for each requisition
        screen_resumes_task.delay(
            job_requisition_id,
            tenant_id,
            document_type,
            num_candidates,
            applications_data,
            ""  # No auth needed for public endpoint
        )
        logger.info(f"Triggered screening for requisition {job_requisition_id} with {len(applications_data)} applications.")