from .base_handler import BaseHandler
from firebase_admin import credentials, messaging, initialize_app
from notifications.utils.encryption import decrypt_data
import logging

logger = logging.getLogger('notifications.channels.push')

class PushHandler(BaseHandler):
    def __init__(self, tenant_id: str, credentials: dict):
        super().__init__(tenant_id, credentials)
        # Decrypt sensitive creds
        sensitive_fields = ['private_key', 'auth_token']  # Add more if needed
        for field in sensitive_fields:
            if field in self.credentials:
                self.credentials[field] = decrypt_data(self.credentials[field])
        
        # Init Firebase app per tenant (singleton per handler instance)
        cred = credentials.Certificate(self.credentials)
        self.app = initialize_app(cred, name=f'tenant_{tenant_id}')

    async def send(self, recipient: str, content: dict, context: dict) -> dict:
        try:
            # Render title/body with context
            title = content.get('title', '').format(**context)
            body = content.get('body', '').format(**context)
            data = content.get('data', {})  # Custom data payload
            
            # FCM message
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=data,
                token=recipient,  # Device token
                topic=None,  # Or use topic for multicast
            )
            
            response = messaging.send(self.app, message)
            
            return {'success': True, 'response': {'message_id': response}}
            
        except Exception as e:
            logger.error(f"Push send error for tenant {self.tenant_id} to {recipient}: {str(e)}")
            return {'success': False, 'error': str(e), 'response': None}