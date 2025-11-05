from .base_handler import BaseHandler
from django.core.mail import send_mail
from django.conf import settings
import logging

logger = logging.getLogger('notifications.channels.email')

class EmailHandler(BaseHandler):
    async def send(self, recipient: str, content: dict, context: dict) -> dict:
        try:
            # Render template with context (simple str replace for now)
            subject = content.get('subject', '').format(**context)
            body = content.get('body', '').format(**context)
            
            sent = send_mail(
                subject,
                body,
                self.credentials.get('from_email', settings.DEFAULT_FROM_EMAIL),
                [recipient],
                fail_silently=False,
            )
            
            if sent:
                return {'success': True, 'response': f'Sent to {sent} recipients'}
            else:
                return {'success': False, 'error': 'Send failed', 'response': None}
        except Exception as e:
            logger.error(f"Email send error for tenant {self.tenant_id}: {str(e)}")
            return {'success': False, 'error': str(e), 'response': None}