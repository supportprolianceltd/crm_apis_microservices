from celery import shared_task
from django.conf import settings
from job_application.models import JobApplication
from job_applications.celery_task import screen_resumes_task
import requests
import logging
from datetime import date
from django.utils import timezone

logger = logging.getLogger('job_applications')

@shared_task
def auto_screen_all_applications():
    # Use timezone-aware date
    today = timezone.now().date().isoformat()
    logger.info(f"Starting auto_screen_all_applications task for date: {today}")

    # Fetch all published requisitions
    url = f"{settings.TALENT_ENGINE_URL}/api/talent-engine/requisitions/public/published/"
    try:
        logger.info(f"Fetching requisitions from {url}")
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        logger.info(f"Received {data.get('count', 0)} requisitions")
    except Exception as e:
        logger.error(f"Failed to fetch published requisitions: {str(e)}")
        return

    if not data.get("results"):
        logger.warning("No published requisitions found.")
        return

    for requisition in data.get("results", []):
        deadline_date = requisition.get("deadline_date")
        logger.info(f"Checking requisition {requisition['id']}: deadline_date={deadline_date}, today={today}")
        if deadline_date != today:
            logger.info(f"Skipping requisition {requisition['id']} (deadline {deadline_date} != {today})")
            continue

        job_requisition_id = requisition["id"]
        document_type = "resume"  # Or requisition['documents_required'][0] if available
        num_candidates = requisition.get("num_of_applications", 0)

        applications = JobApplication.active_objects.filter(
            job_requisition_id=job_requisition_id,
            resume_status=True
        )
        logger.info(f"Found {applications.count()} applications for requisition {job_requisition_id}")

        if not applications.exists():
            logger.warning(f"No eligible applications for requisition {job_requisition_id}")
            continue

        applications_data = [
            {"application_id": app.id, "file_url": app.get_resume_url()} for app in applications
        ]

        logger.info(f"Triggering screening for requisition {job_requisition_id} with {len(applications_data)} applications")
        screen_resumes_task.delay(
            job_requisition_id,
            document_type,
            num_candidates,
            applications_data,
            requisition
        )