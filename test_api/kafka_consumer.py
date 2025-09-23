# lms-service/kafka_consumer.py
import os
import django
from django.conf import settings
from django_tenants.utils import tenant_context, get_tenant_model
import logging
from kafka import KafkaConsumer, KafkaProducer, TopicPartition
import json
from django.core.management import call_command
from django.db import connection
from django.db.utils import IntegrityError, DatabaseError
from jsonschema import validate, ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join('/app/logs', 'consumer.log'))
    ]
)
logger = logging.getLogger('lms_consumer')

logger.debug("Starting kafka_consumer.py")

# Verify environment
logger.debug(f"BASE_DIR: {os.path.dirname(os.path.abspath(__file__))}")
logger.debug(f"DJANGO_SETTINGS_MODULE: {os.environ.get('DJANGO_SETTINGS_MODULE')}")
logger.debug(f"KAFKA_BOOTSTRAP_SERVERS: {os.environ.get('KAFKA_BOOTSTRAP_SERVERS')}")

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'complete_lms.settings')
logger.debug(f"DJANGO_SETTINGS_MODULE set to: {os.environ['DJANGO_SETTINGS_MODULE']}")

try:
    django.setup()
    logger.debug("Django setup completed")
except Exception as e:
    logger.error(f"Failed to setup Django: {str(e)}", exc_info=True)
    raise

# Import models after Django setup
try:
    from shared.models import Tenant, Domain
    logger.debug("Imported Tenant and Domain models")
except Exception as e:
    logger.error(f"Failed to import models: {str(e)}", exc_info=True)
    raise

# Event schema for validation
EVENT_SCHEMA = {
    "type": "object",
    "properties": {
        "event_type": {"type": "string", "enum": ["tenant_created"]},
        "tenant_id": {"type": "string", "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"},
        "data": {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "schema_name": {"type": "string", "pattern": "^[a-z0-9_]+$"},
                "name": {"type": "string"},
                "domains": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "domain": {"type": "string"}
                        },
                        "required": ["domain"]
                    },
                    "minItems": 1
                }
            },
            "required": ["id", "schema_name", "name", "domains"]
        }
    },
    "required": ["event_type", "tenant_id", "data"]
}

def check_topic_exists(producer, topic):
    """Check if a Kafka topic exists."""
    try:
        metadata = producer.partitions_for(topic)
        logger.debug(f"Topic {topic} exists with partitions: {metadata}")
        return True
    except Exception as e:
        logger.error(f"Failed to check topic {topic}: {str(e)}")
        return False

def main():
    logger.debug(f"Connecting to Kafka at {settings.KAFKA_BOOTSTRAP_SERVERS}")
    try:
        consumer = KafkaConsumer(
            'tenant-created',
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            group_id='lms_tenant_consumer',
            value_deserializer=lambda x: json.loads(x.decode('utf-8')),
            auto_offset_reset='earliest',
            enable_auto_commit=False,
            consumer_timeout_ms=10000
        )
        logger.info("Kafka consumer started, listening for tenant-created events...")
    except Exception as e:
        logger.error(f"Failed to start Kafka consumer: {str(e)}", exc_info=True)
        raise

    # DLQ producer
    dlq_producer = KafkaProducer(
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )

    # Verify topic exists
    if not check_topic_exists(dlq_producer, 'tenant-created'):
        logger.error("Topic tenant-created does not exist, exiting...")
        raise Exception("Topic tenant-created not found")

    TenantModel = get_tenant_model()
    logger.debug("Retrieved TenantModel")

    for message in consumer:
        event = message.value
        tenant_id = event.get('tenant_id', 'unknown')
        logger.info(f"Received event: {event}")
        try:
            # Validate event schema
            validate(instance=event, schema=EVENT_SCHEMA)
            logger.debug(f"[Tenant {tenant_id}] Event validated successfully")

            if event['event_type'] == 'tenant_created':
                data = event['data']
                numeric_id = data.get('id')
                schema_name = data['schema_name']
                tenant_name = data['name']
                domain_name = data['domains'][0]['domain']

                # Validate numeric_id
                if not isinstance(numeric_id, int):
                    raise ValueError(f"[Tenant {tenant_id}] Invalid numeric_id: {numeric_id}, expected integer")

                # Idempotency: Check by unique_id (UUID)
                if TenantModel.objects.filter(unique_id=tenant_id).exists():
                    logger.warning(f"[Tenant {tenant_id}] Tenant already exists, skipping creation")
                    consumer.commit()
                    continue

                # Create tenant with retries
                @retry(
                    stop=stop_after_attempt(3),
                    wait=wait_exponential(multiplier=1, min=2, max=10),
                    retry=retry_if_exception_type((IntegrityError, DatabaseError)),
                    before_sleep=lambda retry_state: logger.info(f"[Tenant {tenant_id}] Retrying tenant creation (attempt {retry_state.attempt_number})")
                )
                def create_tenant_with_retry():
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = %s)", [schema_name])
                        schema_exists = cursor.fetchone()[0]
                        if schema_exists:
                            logger.warning(f"[Tenant {tenant_id}] Schema {schema_name} already exists, skipping creation")
                            raise IntegrityError(f"Schema {schema_name} already exists")

                    with transaction.atomic():
                        tenant = TenantModel.objects.create(
                            id=numeric_id,
                            schema_name=schema_name,
                            name=tenant_name,
                            unique_id=tenant_id
                        )
                        Domain.objects.create(
                            domain=domain_name,
                            tenant=tenant,
                            is_primary=True
                        )
                        logger.info(f"[Tenant {tenant_id}] Created tenant record: {tenant_name} (schema: {schema_name})")
                        return tenant

                try:
                    tenant = create_tenant_with_retry()
                except IntegrityError as e:
                    logger.error(f"[Tenant {tenant_id}] Integrity error during creation: {str(e)}")
                    consumer.commit()
                    continue

                # Schema creation
                try:
                    with connection.cursor() as cursor:
                        logger.debug(f"[Tenant {tenant_id}] Creating schema {schema_name}")
                        cursor.execute(f"CREATE SCHEMA {schema_name}")
                except DatabaseError as e:
                    logger.error(f"[Tenant {tenant_id}] Failed to create schema {schema_name}: {str(e)}")
                    TenantModel.objects.filter(unique_id=tenant_id).delete()
                    dlq_producer.send('tenant-dlq', event)
                    dlq_producer.flush()
                    logger.info(f"[Tenant {tenant_id}] Sent failed event to DLQ")
                    consumer.commit()
                    continue

                # Automated migrations with retries
                @retry(
                    stop=stop_after_attempt(3),
                    wait=wait_exponential(multiplier=1, min=2, max=10),
                    retry=retry_if_exception_type(DatabaseError),
                    before_sleep=lambda retry_state: logger.info(f"[Tenant {tenant_id}] Retrying migrations (attempt {retry_state.attempt_number})")
                )
                def migrate_with_retry():
                    with tenant_context(tenant):
                        logger.info(f"[Tenant {tenant_id}] Running migrations for schema {schema_name}")
                        for app in settings.TENANT_APPS:
                            logger.debug(f"[Tenant {tenant_id}] Migrating app {app}")
                            call_command('migrate', app, interactive=False, schema=tenant.schema_name)
                        logger.info(f"[Tenant {tenant_id}] Migrations completed for schema {schema_name}")

                try:
                    migrate_with_retry()
                except Exception as e:
                    logger.error(f"[Tenant {tenant_id}] Migration failed: {str(e)}", exc_info=True)
                    # Rollback schema creation
                    with connection.cursor() as cursor:
                        cursor.execute(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE")
                        logger.info(f"[Tenant {tenant_id}] Rolled back schema {schema_name}")
                    # Delete tenant record
                    TenantModel.objects.filter(unique_id=tenant_id).delete()
                    # Send to DLQ
                    dlq_producer.send('tenant-dlq', event)
                    dlq_producer.flush()
                    logger.info(f"[Tenant {tenant_id}] Sent failed event to DLQ")
                    consumer.commit()
                    continue

                logger.info(f"[Tenant {tenant_id}] Created tenant {schema_name} with domain {domain_name}")
                consumer.commit()

        except ValidationError as e:
            logger.error(f"[Tenant {tenant_id}] Event validation failed: {str(e)}")
            dlq_producer.send('tenant-dlq', event)
            dlq_producer.flush()
            logger.info(f"[Tenant {tenant_id}] Sent invalid event to DLQ")
            consumer.commit()
        except Exception as e:
            logger.error(f"[Tenant {tenant_id}] Error processing event: {str(e)}", exc_info=True)
            dlq_producer.send('tenant-dlq', event)
            dlq_producer.flush()
            logger.info(f"[Tenant {tenant_id}] Sent failed event to DLQ")
            consumer.commit()

if __name__ == "__main__":
    logger.debug("Starting kafka_consumer.py main function")
    main()