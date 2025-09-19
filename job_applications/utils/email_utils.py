import logging
import uuid
import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger('job_applications')

def send_screening_notification(applicant, tenant_id, event_type, source="job-applications", employment_gaps=None):
    """
    Send a screening notification event to the notification microservice,
    with robust logging and error handling like in CustomTokenSerializer.
    """
    try:
        event_payload = {
            "metadata": {
                "tenant_id": str(tenant_id),
                "event_type": event_type,
                "event_id": str(uuid.uuid4()),
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
                "employment_gaps": employment_gaps or [],
                "timestamp": timezone.now().isoformat(),
                "user_agent": applicant.get("user_agent", "unknown")  # Optional field
            }
        }

        notifications_url = settings.NOTIFICATIONS_SERVICE_URL + "/events/"
        logger.info(f"➡️ POST to {notifications_url} with payload: {event_payload}")

        response = requests.post(notifications_url, json=event_payload, timeout=5)
        response.raise_for_status()

        logger.info(f"✅ Notification sent for {event_type} to {applicant.get('email')}. "
                    f"Status: {response.status_code}, Response: {response.text}")

    except requests.exceptions.RequestException as e:
        logger.warning(f"[❌ Notification Error] Failed to send event for {applicant.get('email')}: {str(e)}")
    except Exception as e:
        logger.error(f"[❌ Notification Exception] Unexpected error for {applicant.get('email')}: {str(e)}")
