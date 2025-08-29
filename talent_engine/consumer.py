# talent_engine/talent_engine/consumer.py
import os
import json

# Set DJANGO_SETTINGS_MODULE early
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "talent_engine.settings")

# Initialize Django before any Django-related imports
import django
django.setup()

# Now safe to import Django modules
from kafka import KafkaConsumer
from django.conf import settings
from django.db import connection

def create_or_update_tenant(data):
    tenant_id = data.get("id")
    name = data.get("name")
    schema_name = data.get("schema_name")
    
    with connection.cursor() as cursor:
        cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
    
    tenant, created = TenantRef.objects.get_or_create(
        id=tenant_id,
        defaults={"name": name, "schema_name": schema_name}
    )
    if not created:
        tenant.name = name
        tenant.schema_name = schema_name
        tenant.save()

def consume_kafka_messages():
    consumer = KafkaConsumer(
        settings.KAFKA_TOPICS["tenant"],
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        auto_offset_reset="latest",
        enable_auto_commit=True,
        group_id="talent_engine_tenant_group",
        value_deserializer=lambda x: json.loads(x.decode("utf-8"))
    )
    
    for message in consumer:
        data = message.value
        if message.topic == settings.KAFKA_TOPICS["tenant"]:
            create_or_update_tenant(data)
        print(f"Processed message from {message.topic}: {data}")

if __name__ == "__main__":
    consume_kafka_messages()
