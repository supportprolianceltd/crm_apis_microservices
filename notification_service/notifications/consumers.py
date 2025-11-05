import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from notifications.utils.context import get_tenant_context
import logging

logger = logging.getLogger('notifications.consumers')

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        self.tenant_id = self.scope.get('tenant_id')  # From middleware or query
        if self.user.is_anonymous or not self.tenant_id:
            await self.close()
            return
        
        group_name = f"user_{self.user.pk}_{self.tenant_id}"
        await self.channel_layer.group_add(group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        group_name = f"user_{self.user.pk}_{self.tenant_id}"
        await self.channel_layer.group_discard(group_name, self.channel_name)

    async def inapp_notification(self, event):
        await self.send(text_data=json.dumps({
            'title': event['title'],
            'body': event['body'],
            'data': event['data'],
        }))