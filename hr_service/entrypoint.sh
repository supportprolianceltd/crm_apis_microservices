#!/usr/bin/env bash
set -e

echo "⏳ Waiting for database..."
/app/wait-for-it.sh hr_postgres:5432 -t 60 -- echo "✅ Database is up"

# Run Django setup only in hr-service
if [ "$RUN_MAIN_SERVICE" = "true" ]; then
  echo "🔧 Running migrations..."
  python manage.py makemigrations --noinput
  python manage.py migrate --noinput

  echo "📦 Collecting static files..."
  python manage.py collectstatic --noinput --clear

  echo "✅ HR service is ready."
fi

# Run the main container command (e.g. gunicorn, celery, etc.)
exec "$@"
