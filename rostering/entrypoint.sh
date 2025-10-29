#!/bin/bash
set -e

echo "🚀 Starting Rostering Service..."
cd /app

# Generate Prisma client (safe to rerun)
echo "🔧 Generating Prisma client..."
npx prisma generate

# Wait for database and apply migrations with retry logic
echo "⏳ Waiting for database and applying migrations..."
MAX_RETRIES=30
RETRY_COUNT=0
MIGRATION_SUCCESS=false

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
  if npx prisma migrate deploy; then
    echo "✅ Database connected and migrations applied successfully!"
    MIGRATION_SUCCESS=true
    break
  fi
  
  RETRY_COUNT=$((RETRY_COUNT+1))
  echo "💤 Database not ready or migrations pending, waiting 2 seconds... (attempt $RETRY_COUNT/$MAX_RETRIES)"
  sleep 2
done

if [ "$MIGRATION_SUCCESS" = false ]; then
  echo "❌ Failed to apply migrations after $MAX_RETRIES attempts"
  echo "🔍 Checking database connection..."
  
  # Try to get more detailed error info
  if npx prisma db execute --stdin --url="$DATABASE_URL" <<< "SELECT 1" > /dev/null 2>&1; then
    echo "✅ Database is accessible, but migrations failed"
    echo "📋 Checking migration status..."
    npx prisma migrate status
  else
    echo "❌ Cannot connect to database at all"
  fi
  
  exit 1
fi

echo "🎉 Setup complete! Starting application..."

# Switch to non-root user and start the application
exec su-exec rostering "$@"