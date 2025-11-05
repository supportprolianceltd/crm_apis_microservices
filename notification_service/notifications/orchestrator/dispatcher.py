import logging
from notifications.channels.base_handler import BaseHandler
from notifications.channels.email_handler import EmailHandler
from notifications.channels.sms_handler import SMSHandler  # New
from notifications.channels.push_handler import PushHandler
from notifications.channels.inapp_handler import InAppHandler

logger = logging.getLogger('notifications.orchestrator')

class ChannelNotConfiguredError(Exception):
    """Raised when a notification channel handler is not configured."""
    pass


class Dispatcher:
    HANDLERS = {
        'email': EmailHandler,
        'sms': SMSHandler,  # New
        'push': PushHandler,
        'inapp': InAppHandler,
    }

    @classmethod
    def get_handler(cls, channel: str, tenant_id: str, credentials: dict):
        handler_class = cls.HANDLERS.get(channel)
        if not handler_class:
            raise ChannelNotConfiguredError(f"Handler for {channel} not implemented.")
        return handler_class(tenant_id, credentials)
