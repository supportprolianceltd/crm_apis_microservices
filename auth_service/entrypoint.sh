#!/bin/bash
set -e

# Entrypoint script to make migrations and run tenant migrations
cd /app
# python manage.py makemigrations users core
python manage.py makemigrations --noinput users reviews core
python manage.py migrate_schemas --shared
python manage.py migrate_schemas
exec gunicorn --bind 0.0.0.0:8001 auth_service.wsgi:application