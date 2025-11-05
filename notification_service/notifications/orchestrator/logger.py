from notifications.models import AuditLog
from notifications.utils.context import get_tenant_context
import logging

logger = logging.getLogger('notifications.orchestrator')

def log_event(event: str, notification_id: str, details: dict, request=None):
    context = get_tenant_context(request)
    AuditLog.objects.create(
        tenant_id=context['tenant_id'],
        notification_id=notification_id,
        event=event,
        details=details,
        user_id=context['user_id']
    )
    logger.info(f"Audit: {event} for notification {notification_id} - {details}")