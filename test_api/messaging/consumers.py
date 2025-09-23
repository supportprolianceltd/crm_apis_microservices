import json
import logging
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils import timezone
from .models import MessageRecipient
from .serializers import get_tenant_id_from_jwt

logger = logging.getLogger("messaging.socket")

class MessageConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        jwt_payload = getattr(self.scope.get('user'), 'jwt_payload', {})
        self.user_id = jwt_payload.get('user', {}).get('id')
        self.tenant_id = jwt_payload.get('tenant_unique_id')
        if not self.user_id or not self.tenant_id:
            logger.error("Missing user_id or tenant_id in JWT payload")
            await self.close()
            return
        self.group_name = f"{self.tenant_id}_user_{self.user_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        logger.debug(f"[Tenant {self.tenant_id}] WebSocket connected for user {self.user_id}")

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
            logger.debug(f"[Tenant {self.tenant_id}] WebSocket disconnected for user {self.user_id}")

    async def receive(self, text_data):
        data = json.loads(text_data)
        if data.get("type") == "mark_as_read":
            await self.mark_message_as_read(data.get("message_id"))

    async def new_message(self, event):
        await self.send(text_data=json.dumps({"type": "new_message", "message": event["message"]}))

    async def message_read(self, event):
        await self.send(text_data=json.dumps({"type": "message_read", "message_id": event["message_id"], "reader_id": event["reader_id"]}))

    @database_sync_to_async
    def mark_message_as_read(self, message_id: str | int | None):
        if not message_id:
            return
        try:
            updated = MessageRecipient.objects.filter(
                message_id=message_id, recipient_id=self.user_id
            ).update(read=True, read_at=timezone.now())
            logger.debug(f"[Tenant {self.tenant_id}] User {self.user_id} marked message {message_id} as read ({updated} rows updated)")
        except Exception as exc:
            logger.exception(f"[Tenant {self.tenant_id}] Failed to mark message {message_id} as read: {exc}")