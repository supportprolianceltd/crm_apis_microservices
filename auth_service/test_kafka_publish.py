# Manual Kafka test publisher for auth-events topic
import os
import json
from kafka import KafkaProducer

KAFKA_BROKER = os.environ.get('KAFKA_BROKER', 'kafka:9092')  # Adjust if needed
topic = 'auth-events'

producer = KafkaProducer(
    bootstrap_servers=[KAFKA_BROKER],
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

test_event = {
    'event_type': 'user.login.succeeded',
    'tenant_id': '7ac6d583-c421-42bc-b94a-6e31f2bc9e63', # Replace with a real tenant UUID
    'timestamp': '2025-12-15T12:00:00Z',
    'payload': {
        'user_id': 'test-user-id',
        'email': 'support@prolianceltd.com',
        'username': 'support@prolianceltd.com',
        'login_time': '2025-12-15T12:00:00Z',
        'ip_address': '127.0.0.1',
        'user_agent': 'manual-test',
        'login_method': 'email',
        'tenant_name': 'Proliance',
        'tenant_logo': '',
        'tenant_primary_color': '#123456',
        'tenant_secondary_color': '#abcdef',
    }
}

print(f"Publishing test event to {topic} on {KAFKA_BROKER}...")
producer.send(topic, test_event)
producer.flush()
print("Test event published.")
