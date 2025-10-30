from kafka import KafkaProducer
from django.conf import settings
import json
import logging

logger = logging.getLogger('notifications.kafka')

class NotificationProducer:
    def __init__(self):
        self.producer = KafkaProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            retries=3,
            acks='all'
        )

    def send_event(self, topic: str, event_data: dict):
        try:
            self.producer.send(topic, event_data)
            self.producer.flush()
            logger.info(f"Produced event to {topic}: {event_data}")
        except Exception as e:
            logger.error(f"Failed to produce to {topic}: {str(e)}")