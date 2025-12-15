import json
import logging
from typing import Optional, Dict, Any
from kafka import KafkaProducer
from django.conf import settings

logger = logging.getLogger('auth_service.kafka')

class AuthServiceKafkaProducer:
    """
    Unified Kafka producer for auth service events.
    Combines functionality from both existing producer implementations.
    """

    def __init__(self):
        self._producer: Optional[KafkaProducer] = None

    @property
    def producer(self) -> KafkaProducer:
        """Lazy initialization of Kafka producer"""
        if self._producer is None:
            self._producer = KafkaProducer(
                bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                acks='all',  # Wait for all replicas to acknowledge
                retries=5,  # Retry on failure
                retry_backoff_ms=1000,  # Backoff between retries
                max_in_flight_requests_per_connection=1,  # Ensure ordering
                enable_idempotence=True,  # Ensure exactly-once delivery
            )
            logger.info("Kafka producer initialized")
        return self._producer

    def send_event(self, topic: str, event_data: Dict[str, Any]) -> bool:
        """
        Send an event to Kafka topic.

        Args:
            topic: Kafka topic name
            event_data: Event data dictionary

        Returns:
            bool: True if sent successfully, False otherwise
        """
        try:
            # Send the event
            future = self.producer.send(topic, event_data)

            # Wait for confirmation with timeout
            future.get(timeout=10)

            event_type = event_data.get('event_type', 'unknown')
            logger.info(f"✅ Event sent to {topic}: {event_type}")

            return True

        except Exception as e:
            event_type = event_data.get('event_type', 'unknown')
            logger.error(f"❌ Failed to send event {event_type} to {topic}: {str(e)}")
            return False

    def flush(self):
        """Flush pending messages"""
        if self._producer:
            self._producer.flush()

    def close(self):
        """Close the producer"""
        if self._producer:
            self._producer.close()
            self._producer = None
            logger.info("Kafka producer closed")

# Global instance for backward compatibility
_producer_instance = AuthServiceKafkaProducer()

def get_kafka_producer() -> AuthServiceKafkaProducer:
    """Get the global Kafka producer instance"""
    return _producer_instance

def publish_event(topic: str, event_data: Dict[str, Any]) -> bool:
    """
    Publish an event to Kafka (backward compatibility function).

    Args:
        topic: Kafka topic name
        event_data: Event data dictionary

    Returns:
        bool: True if sent successfully, False otherwise
    """
    return _producer_instance.send_event(topic, event_data)

# For backward compatibility with class-based usage
class AuthServiceProducer(AuthServiceKafkaProducer):
    """Alias for backward compatibility"""
    pass