import logging
import uuid
import requests
from django.conf import settings
from django.utils import timezone
logger = logging.getLogger('job_applications')


def send_screening_notification(applicant, tenant_id, event_type, source="job-applications", employment_gaps=None):
    """
    Send a notification event to the notification microservice.
    If employment_gaps is provided, include it in the payload.
    """
    payload = {
        "metadata": {
            "tenant_id":  "test-tenant-1",
            "event_type": event_type,
            "event_id": f"evt-{uuid.uuid4()}",
            "created_at": timezone.now().isoformat(),
            "source": source
        },
        "data": {
            "user_email": applicant.get("email"),
            "full_name": applicant.get("full_name"),
            "application_id": applicant.get("application_id"),
            "job_requisition_id": applicant.get("job_requisition_id"),
            "status": applicant.get("status"),
            "score": applicant.get("score", None),
            "has_employment_gaps": bool(employment_gaps),
            "employment_gaps": employment_gaps or []
        }
    }
    try:
        resp = requests.post(f"{settings.NOTIFICATIONS_EVENT_URL}/events/", json=payload, timeout=5)
        logger.info(f"Notification sent for {event_type} to {applicant.get('email')}: {resp.status_code}")
    except Exception as e:
        logger.error(f"Failed to send notification for {applicant.get('email')}: {str(e)}")