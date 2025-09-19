import json
from kafka import KafkaProducer
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def get_kafka_producer():
    return KafkaProducer(
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode('utf-8'),
        acks='all',  # Wait for all replicas to acknowledge
        retries=5,  # Retry on failure
        retry_backoff_ms=1000  # Backoff between retries
    )

def publish_event(topic, event_data):
    producer = get_kafka_producer()
    try:
        future = producer.send(topic, event_data)
        future.get(timeout=10)  # Block until confirmed or timeout
        logger.info(f"Event published to {topic}: {event_data}")
    except Exception as e:
        logger.error(f"Failed to publish event to {topic}: {str(e)}")
        # Optionally raise or handle (e.g., queue for retry)
    finally:
        producer.flush()
        producer.close()