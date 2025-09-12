# from kafka import KafkaConsumer
# import json
# from django.conf import settings
# from django.db import connection
# from django_tenants.utils import schema_context
# import logging

# logger = logging.getLogger(__name__)

# def consume_tenant_events():
#     consumer = KafkaConsumer(
#         'tenant-events',
#         bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
#         value_deserializer=lambda v: json.loads(v.decode('utf-8')),
#         auto_offset_reset='earliest',  # Or 'latest' depending on needs
#         group_id='lms-tenant-consumers'  # Unique group per service
#     )

#     for message in consumer:
#         event = message.value
#         if event.get('event_type') == 'tenant_created':
#             schema_name = event['schema_name']
#             try:
#                 # Create schema in this service's DB
#                 with connection.cursor() as cursor:
#                     cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name};")
                
#                 # Optionally create a Tenant model instance if your service uses one
#                 # from your_models import Tenant
#                 # Tenant.objects.create(schema_name=schema_name, name=event['name'], ...)

#                 # Run migrations on the new schema (if using django-tenants)
#                 # This assumes you have a management command or call migrations programmatically
#                 from django.core.management import call_command
#                 call_command('migrate_schemas', schema_name=schema_name, interactive=False)

#                 logger.info(f"Created schema {schema_name} for tenant {event['tenant_id']}")
#             except Exception as e:
#                 logger.error(f"Failed to create schema {schema_name}: {str(e)}")

# if __name__ == '__main__':
#     consume_tenant_events()
import os
import django
import json
from kafka import KafkaConsumer
from django.core.management import call_command
from django_tenants.utils import schema_context, get_tenant_model

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'your_project.settings')
django.setup()

consumer = KafkaConsumer(
    'tenant-events',
    bootstrap_servers='kafka:9092',
    value_deserializer=lambda m: json.loads(m.decode('utf-8'))
)

print("Kafka consumer started. Waiting for tenant-created events...")

for message in consumer:
    event = message.value
    if event.get('event_type') == 'tenant_created':
        schema_name = event['schema_name']
        tenant_id = event['tenant_id']
        tenant_model = get_tenant_model()

        try:
            tenant = tenant_model.objects.get(schema_name=schema_name)
            print(f"Tenant found: {tenant.name} (schema: {schema_name})")

            # Step 1: Run makemigrations for all apps
            print("Running makemigrations...")
            call_command('makemigrations', 'token_blacklist', 'users', 'courses', 'forum', 'groups', 'messaging', 'payments', 'schedule', 'ai_chat', 'carts', 'activitylog')

            # Step 2: Apply shared migrations (once)
            print("Running migrate_schemas --shared...")
            call_command('migrate_schemas', shared=True)

            # Step 3: Migrate only this tenant schema
            print(f"Running migrate_schemas for schema: {schema_name}...")
            call_command('migrate_schemas', schema_name=schema_name)

            print(f"✅ Tenant {schema_name} successfully migrated.")

        except tenant_model.DoesNotExist:
            print(f"❌ Tenant with schema {schema_name} not found.")
        except Exception as e:
            print(f"❌ Error during migration for tenant {schema_name}: {e}")
