#!/bin/sh
# Entrypoint script to make migrations and run migrations for project_manager
python manage.py makemigrations
python manage.py migrate
exec gunicorn --bind 0.0.0.0:8005 project_manager.wsgi:application