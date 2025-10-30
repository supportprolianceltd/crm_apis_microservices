from .base_handler import BaseHandler
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import json
import logging

logger = logging.getLogger('notifications.channels.inapp')

class InAppHandler(BaseHandler):
    async def send(self, recipient: str, content: dict, context: dict) -> dict:
        try:
            # Render content
            title = content.get('title', '').format(**context)
            body = content.get('body', '').format(**context)
            data = content.get('data', context)  # Merge context
            
            channel_layer = get_channel_layer()
            if not channel_layer:
                return {'success': False, 'error': 'Channel layer not configured', 'response': None}
            
            # Broadcast to tenant group (recipient could be user_id or 'tenant_all')
            group_name = f"tenant_{self.tenant_id}" if recipient == 'all' else f"user_{recipient}_{self.tenant_id}"
            
            await channel_layer.group_send(
                group_name,
                {
                    'type': 'inapp_notification',
                    'title': title,
                    'body': body,
                    'data': data,
                }
            )
            
            return {'success': True, 'response': {'group': group_name}}
            
        except Exception as e:
            logger.error(f"In-app send error for tenant {self.tenant_id} to {recipient}: {str(e)}")
            return {'success': False, 'error': str(e), 'response': None}