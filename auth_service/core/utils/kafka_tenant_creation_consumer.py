from kafka import KafkaConsumer
import json

consumer = KafkaConsumer(
    'tenant-created',
    bootstrap_servers=['kafka:9092'],  # Match your settings
    auto_offset_reset='earliest',
    enable_auto_commit=True,
    group_id='tenant-consumers',
    value_deserializer=lambda x: json.loads(x.decode('utf-8'))
)

for message in consumer:
    event = message.value
    if event['event_type'] == 'tenant_created':
        # Process tenant_data, e.g., setup resources for the new tenant
        print(f"New tenant: {event['data']['name']}")