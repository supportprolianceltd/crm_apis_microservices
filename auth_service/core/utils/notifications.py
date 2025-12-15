import requests
from django.conf import settings
import logging
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

def send_notification_event(event_data):
    """
    Send an event to the notification service via HTTP POST.
    """
    # Combine NOTIFICATIONS_SERVICE_URL with /tenants endpoint
    notification_url = urljoin(settings.NOTIFICATIONS_SERVICE_URL, 'tenants/')
    try:
        response = requests.post(
            notification_url,
            json=event_data,
            timeout=10  # Timeout after 10 seconds
        )
        response.raise_for_status()  # Raise an exception for 4xx/5xx status codes
        logger.info(f"Notification sent successfully to {notification_url}: {event_data}")
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send notification to {notification_url}: {str(e)}")
        # Optionally raise or handle (e.g., queue for retry)
        return None