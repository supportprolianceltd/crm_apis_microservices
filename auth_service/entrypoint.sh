#!/bin/bash
set -e

# Entrypoint script to make migrations and run tenant migrations
cd /app
echo "Starting entrypoint script"
# python manage.py makemigrations users core
# echo "Running makemigrations"
# python manage.py makemigrations --noinput users reviews investments events core
# echo "Makemigrations completed"
# echo "Running migrate_schemas --shared"
# python manage.py migrate_schemas --shared
# echo "migrate_schemas --shared completed"
# echo "Running migrate_schemas"
# python manage.py migrate_schemas
# echo "migrate_schemas completed"
echo "Starting gunicorn"
# exec gunicorn --bind 0.0.0.0:8001 auth_service.wsgi:application
exec gunicorn auth_service.wsgi:application \
  --bind 0.0.0.0:8001 \
  --workers 2 \
  --threads 2 \
  --timeout 120 \
  --worker-class gthread \
  --max-requests 1000 \
  --max-requests-jitter 100
