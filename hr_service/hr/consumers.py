import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import PerformanceReview

class PerformanceConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.tenant_id = self.scope['url_route']['kwargs']['tenant_id']
        self.group_name = f"performance_{self.tenant_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        # Update performance (e.g., new review)
        await self.save_review(data)

    @database_sync_to_async
    def save_review(self, data):
        # Save PerformanceReview
        review = PerformanceReview.objects.create(
            tenant_id=self.tenant_id, user_id=data['user_id'],
            review_date=data['date'], score=data['score'], feedback=data['feedback']
        )
        return review.id

    async def performance_update(self, event):
        """Broadcast new performance data (Step 3)."""
        await self.send(text_data=json.dumps({
            'type': 'performance_update',
            'review_id': event['review_id'],
            'user_id': event['user_id'],
            'score': event['score']
        }))


