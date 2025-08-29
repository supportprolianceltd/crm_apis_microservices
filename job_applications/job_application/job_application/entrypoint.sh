#!/bin/bash
python manage.py migrate
python manage.py collectstatic --noinput
gunicorn job_application.wsgi:application --bind 0.0.0.0:8002db32a3a0d0e4