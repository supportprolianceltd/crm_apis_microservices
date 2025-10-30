from rest_framework.decorators import api_view
from rest_framework.response import Response
from notifications.orchestrator.dispatcher import Dispatcher
from notifications.models import NotificationRecord

@api_view(['POST'])
def webhook_trigger(request):
    payload = request.data
    tenant_id = payload.get('tenant_id')
    channel = payload.get('channel')
    recipient = payload.get('recipient')
    content = payload.get('content', {})
    context = payload.get('context', {})
    
    # Validate & create record
    record = NotificationRecord.objects.create(
        tenant_id=tenant_id, channel=channel, recipient=recipient,
        content=content, context=context
    )
    
    # Enqueue
    from notifications.tasks import send_notification_task
    send_notification_task.delay(str(record.id), channel, recipient, content, context)
    
    return Response({'id': str(record.id), 'status': 'queued'})