#!/bin/bash

# Wait for the database to be ready with a timeout
MAX_RETRIES=30
RETRY_COUNT=0
until pg_isready -h lms-db -p 5432 -U postgres; do
  echo "Waiting for database..."
  sleep 2
  RETRY_COUNT=$((RETRY_COUNT + 1))
  if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
    echo "Error: Database connection timed out after $MAX_RETRIES attempts"
    exit 1
  fi
done

# Run makemigrations for all apps (conditional for development or initial setup)
if [ "$DEBUG" = "True" ]; then
  echo "Running makemigrations for all apps..."
  python manage.py makemigrations --noinput
fi

# Run migrations for public schema (shared apps)
echo "Running migrations for public schema..."
python manage.py migrate --run-syncdb --noinput
python manage.py migrate --noinput

# Run migrations for all schemas if migrate_schemas is available
echo "Running migrations for all schemas..."
python manage.py migrate_schemas --noinput 2>/dev/null || echo "migrate_schemas command not available, skipping tenant migrations"

# Execute the command passed via CMD
exec "$@"