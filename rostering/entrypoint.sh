#!/bin/bash
set -e

echo "🚀 Starting Rostering Service..."

# Change to application directory
cd /app


# Wait for database to be ready and apply migrations
echo "⏳ Waiting for database connection and running migrations..."
until npx prisma migrate deploy > /dev/null 2>&1; do
  echo "💤 Database not ready or migrations failed, waiting 2 seconds..."
  sleep 2
done

echo "✅ Database connected and migrations applied!"

# Generate Prisma client
echo "🔧 Generating Prisma client..."
npx prisma generate

echo "🎉 Setup complete! Starting application..."

# Switch to non-root user and start the application
exec su-exec rostering "$@"