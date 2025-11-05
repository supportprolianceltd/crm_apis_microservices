# talent_engine/talent_engine/consumer.py
import os
import json
import django
import logging
from kafka import KafkaConsumer

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'talent_engine.settings')
django.setup()

from jobRequisitions.models import JobRequisition

# Configure logging to output to console
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('talent_engine')

KAFKA_BOOTSTRAP_SERVERS = os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092')

consumer = KafkaConsumer(
    'job_application_events',
    bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
    group_id='talent_engine_group'
)

logger.info("Kafka consumer started and listening on topic 'job_application_events'...")

for message in consumer:
    logger.info(f"Received Kafka message: {message.value}")
    data = message.value
    tenant_id = data.get('tenant_id')
    job_requisition_id = data.get('job_requisition_id')
    event = data.get('event')
    if tenant_id and job_requisition_id and event == "job_application_created":
        try:
            job_requisition = JobRequisition.active_objects.get(id=job_requisition_id, tenant_id=tenant_id)
            job_requisition.num_of_applications = (job_requisition.num_of_applications or 0) + 1
            job_requisition.save(update_fields=['num_of_applications'])
            logger.info(
                f"SUCCESS: num_of_applications updated for requisition {job_requisition_id} (tenant {tenant_id}) to {job_requisition.num_of_applications}"
            )
        except JobRequisition.DoesNotExist:
            logger.error(
                f"FAILED: JobRequisition {job_requisition_id} not found for tenant {tenant_id}"
            )
        except Exception as e:
            logger.error(
                f"FAILED: Error updating num_of_applications for requisition {job_requisition_id} (tenant {tenant_id}): {str(e)}"
            )
    else:
        logger.warning(
            f"IGNORED: Message missing tenant_id, job_requisition_id, or event type. Data: {data}"
        )
