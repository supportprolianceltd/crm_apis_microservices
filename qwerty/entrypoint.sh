#!/bin/bash

echo "Applying migrations..."
python manage.py migrate

echo "Starting Celery worker..."
celery -A notifications_service worker -l info &

echo "Starting Django server..."
daphne -b 0.0.0.0 -p 8005 notifications_service.asgi:application
