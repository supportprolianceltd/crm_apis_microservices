import json
import logging
import uuid
from channels.generic.websocket import AsyncWebsocketConsumer
from django_tenants.utils import tenant_context


logger = logging.getLogger('talent_engine')

class SignalingConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.tenant = self.scope['tenant']
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        self.client_id = self.scope['user'].id or str(uuid.uuid4())
        self.group_name = f"session_{self.session_id}"

        if not self.tenant:
            logger.error("No tenant associated with WebSocket connection")
            await self.close()
            return

        with tenant_context(self.tenant):
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()
            logger.info(f"Client {self.client_id} connected to session {self.session_id} in tenant {self.tenant.schema_name}")

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            with tenant_context(self.tenant):
                await self.channel_layer.group_discard(self.group_name, self.channel_name)
                logger.info(f"Client {self.client_id} disconnected from session {self.session_id} in tenant {self.tenant.schema_name}")

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            data['client_id'] = self.client_id
            with tenant_context(self.tenant):
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        'type': 'signal_message',
                        'message': data
                    }
                )
                logger.info(f"Signaling message for session {self.session_id} from {self.client_id} in tenant {self.tenant.schema_name}")
        except Exception as e:
            logger.error(f"Signaling error in session {self.session_id}: {str(e)}")

    async def signal_message(self, event):
        message = event['message']
        await self.send(text_data=json.dumps(message))