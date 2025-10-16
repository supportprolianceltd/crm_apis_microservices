#!/bin/bash
set -e

echo "⏳ Waiting for database..."
/app/wait-for-it.sh hr_postgres:5432 -t 60 -- echo "✅ Database is up"

echo "🔧 Running public schema migrations..."
python manage.py migrate_schemas --schema=public --noinput

echo "🏗️ Creating default tenant if not exists..."
python create_default_tenant.py

echo "✅ Worker service is ready."
exec "$@"




