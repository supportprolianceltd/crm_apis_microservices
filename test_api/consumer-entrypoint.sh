#!/bin/bash
echo "Starting consumer-entrypoint.sh at $(date)"

# Verify environment variables
echo "DEBUG=$DEBUG"
echo "DATABASE_URL=$DATABASE_URL"
echo "KAFKA_BOOTSTRAP_SERVERS=$KAFKA_BOOTSTRAP_SERVERS"

# Check file permissions and existence
echo "Checking kafka_consumer.py..."
ls -l /app/kafka_consumer.py || { echo "ERROR: kafka_consumer.py not found"; exit 1; }

# Check Python version and dependencies
echo "Python version:"
python --version || { echo "ERROR: Python not installed"; exit 1; }
echo "Checking kafka-python..."
pip show kafka-python || { echo "ERROR: kafka-python not installed"; exit 1; }
echo "Checking jsonschema..."
pip show jsonschema || { echo "ERROR: jsonschema not installed"; exit 1; }
echo "Checking tenacity..."
pip show tenacity || { echo "ERROR: tenacity not installed"; exit 1; }

# Wait for database
echo "Waiting for database..."
while ! nc -z lms-db 5432; do
  echo "Database not ready, retrying..."
  sleep 1
done
echo "lms-db:5432 - accepting connections"

# Wait for Kafka with retries
echo "Waiting for Kafka..."
for i in {1..30}; do
  nc -zv kafka 9092 && break
  echo "Kafka not ready, retrying ($i/30)..."
  sleep 2
done
if ! nc -zv kafka 9092; then
  echo "ERROR: Kafka:9092 - not accessible after 30 attempts"
  exit 1
fi
echo "Kafka:9092 - accessible"

# Create tenant-created and DLQ topics
echo "Creating topic tenant-created..."
docker exec kafka /opt/kafka/bin/kafka-topics.sh --create --topic tenant-created --bootstrap-server kafka:9092 --partitions 1 --replication-factor 1 --if-not-exists || { echo "WARNING: Failed to create tenant-created topic"; }
echo "Creating DLQ topic tenant-dlq..."
docker exec kafka /opt/kafka/bin/kafka-topics.sh --create --topic tenant-dlq --bootstrap-server kafka:9092 --partitions 1 --replication-factor 1 --if-not-exists || { echo "WARNING: Failed to create tenant-dlq topic"; }

# Check Kafka consumer group lag
echo "Checking Kafka consumer group lag..."
docker exec kafka /opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server kafka:9092 --group lms_tenant_consumer --describe || { echo "WARNING: Failed to check consumer group lag"; }

# Run migrations for shared schema
if [ "$DEBUG" = "True" ]; then
    echo "Running makemigrations for shared, activitylog, courses, forum..."
    python manage.py makemigrations shared activitylog courses forum --noinput || { echo "ERROR: makemigrations failed"; exit 1; }
fi

echo "Running migrations for shared schema..."
python manage.py migrate_schemas --shared || { echo "ERROR: migrate_schemas failed"; exit 1; }

# Start Kafka consumer
echo "Starting Kafka consumer..."
exec python /app/kafka_consumer.py || { echo "ERROR: Failed to start kafka_consumer.py"; exit 1; }