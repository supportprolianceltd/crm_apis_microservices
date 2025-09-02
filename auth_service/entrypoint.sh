#!/bin/sh
# Entrypoint script to make migrations and run tenant migrations
python manage.py makemigrations users core
python manage.py migrate_schemas --shared
python manage.py migrate_schemas
gunicorn --bind 0.0.0.0:8001 auth_service.wsgi:application
