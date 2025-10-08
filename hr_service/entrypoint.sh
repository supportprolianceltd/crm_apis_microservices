#!/bin/bash
set -e

# Wait for DB
echo "⏳ Waiting for database..."
./wait-for-it.sh $DB_HOST:5432 -t 60 -- echo "✅ Database is up"

# Run migrations (standard, no schemas)
echo "🔧 Running migrations..."
python manage.py migrate --noinput

# Collect static files
echo "📦 Collecting static files..."
python manage.py collectstatic --noinput

# Execute the command
exec "$@"