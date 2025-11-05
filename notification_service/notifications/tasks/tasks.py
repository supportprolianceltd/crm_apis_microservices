from celery import shared_task
from notifications.models import NotificationRecord, NotificationStatus, FailureReason
from notifications.orchestrator.dispatcher import Dispatcher
from notifications.orchestrator.validator import validate_tenant_and_channel
from notifications.orchestrator.logger import log_event
from notifications.utils.status_codes import FAILURE_CODES
from notifications.utils.exceptions import NotificationFailedError
from notifications.utils.kafka_producer import NotificationProducer  # New
import asyncio
import logging
import json
from notifications.models import Campaign, CampaignStatus
from django.conf import settings

logger = logging.getLogger('notifications.tasks')


from celery import group  # Add
from notifications.models import Campaign, NotificationStatus
from notifications.orchestrator.logger import log_event
import logging

logger = logging.getLogger('notifications.tasks')

@shared_task
def send_bulk_campaign_task(campaign_id: str):
    campaign = Campaign.objects.get(id=campaign_id)
    campaign.status = CampaignStatus.SENDING.value
    campaign.save()

    # Create sub-tasks for each recipient
    sub_tasks = group(
        send_notification_task.s(
            str(NotificationRecord.objects.create(
                tenant_id=campaign.tenant_id,
                channel=campaign.channel,
                recipient=r['recipient'],
                content=campaign.content or {},  # Or from template
                context=r.get('context', {})
            ).id),
            campaign.channel,
            r['recipient'],
            campaign.content or {},
            r.get('context', {})
        )
        for r in campaign.recipients
    )

    # Execute group
    result = sub_tasks.delay()
    result.save()  # Track for progress

    # On completion (use chord for callback if needed)
    # For now, poll or use beat to update status
    # TODO: Implement callback to increment sent_count and set COMPLETED

    log_event('bulk_started', campaign_id, {'total': len(campaign.recipients)})
    logger.info(f"Bulk campaign {campaign_id} started with {len(campaign.recipients)} recipients")

# Optional: Callback task
@shared_task(bind=True)
def update_campaign_completion(self, campaign_id: str, results: list):
    campaign = Campaign.objects.get(id=campaign_id)
    successes = sum(1 for r in results if r.successful())
    campaign.sent_count = successes
    campaign.status = CampaignStatus.COMPLETED.value if successes == campaign.total_recipients else CampaignStatus.FAILED.value
    campaign.save()
    log_event('bulk_completed', campaign_id, {'sent': successes})


@shared_task(bind=True, max_retries=3)
def send_notification_task(self, record_id: str, channel: str, recipient: str, content: dict, context: dict):
    record = NotificationRecord.objects.get(id=record_id)
    record.status = NotificationStatus.RETRYING.value
    record.save()

    producer = NotificationProducer()

    try:
        creds = validate_tenant_and_channel(record.tenant_id, channel)
        handler = Dispatcher.get_handler(channel, record.tenant_id, creds)
        
        result = asyncio.run(handler.send(recipient, content, context))
        
        if result['success']:
            record.status = NotificationStatus.SUCCESS.value
            record.provider_response = json.dumps(result['response'])
            record.sent_at = timezone.now()
            log_event('sent', record_id, result)
            
            # Produce Kafka event
            producer.send_event(
                settings.KAFKA_TOPICS['notification_events'],
                {
                    'event_type': 'notification_sent',
                    'notification_id': str(record_id),
                    'tenant_id': str(record.tenant_id),
                    'channel': channel,
                    'recipient': recipient,
                    'timestamp': record.sent_at.isoformat()
                }
            )
        else:
            record.status = NotificationStatus.FAILED.value
            record.failure_reason = FailureReason.UNKNOWN_ERROR.value
            record.provider_response = result['error']
            raise NotificationFailedError(result['error'])
        
        record.save()
        
    except Exception as exc:
        record.retry_count += 1
        if record.retry_count >= record.max_retries:
            record.status = NotificationStatus.FAILED.value
            record.failure_reason = FailureReason.UNKNOWN_ERROR.value
            log_event('failed', record_id, {'error': str(exc)})
            
            # Produce failure event
            producer.send_event(
                settings.KAFKA_TOPSTRAP_SERVERS,
                {
                    'event_type': 'notification_failed',
                    'notification_id': str(record_id),
                    'tenant_id': str(record.tenant_id),
                    'error': str(exc),
                    'timestamp': timezone.now().isoformat()
                }
            )
        else:
            self.retry(countdown=60 * (2 ** record.retry_count), exc=exc)
        record.save()



@shared_task
def process_error_task(record_id: str):
    # Handle dead-letter or final errors (e.g., notify tenant admin)
    logger.warning(f"Final error processing for {record_id}")
    # TODO: Integrate with tenant notification for alerts