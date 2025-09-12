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

# Run migrations for public schema
echo "Running migrations for public schema..."
python manage.py migrate --noinput

# Execute the command passed via CMD
exec "$@"