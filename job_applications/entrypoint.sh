#!/bin/bash
python manage.py migrate
python manage.py collectstatic --noinput
gunicorn job_applications.wsgi:application --bind 0.0.0.0:8002