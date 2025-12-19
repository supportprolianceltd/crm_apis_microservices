#!/bin/sh

# Entrypoint script to make migrations and run migrations for talent_engine

python manage.py makemigrations

python manage.py migrate

exec gunicorn --bind 0.0.0.0:8002 talent_engine.wsgi:application
