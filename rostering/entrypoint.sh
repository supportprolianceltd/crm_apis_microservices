#!/bin/bash
set -e

echo "🚀 Starting Rostering Service..."

# Change to application directory
cd /app

# Wait for database to be ready
echo "⏳ Waiting for database connection..."
until npx prisma db push --accept-data-loss > /dev/null 2>&1; do
  echo "💤 Database not ready, waiting 2 seconds..."
  sleep 2
done

echo "✅ Database connected!"

# Push schema to database (for development)
echo "🔄 Pushing schema to database..."
npx prisma db push --accept-data-loss

# Generate Prisma client
echo "🔧 Generating Prisma client..."
npx prisma generate

echo "🎉 Setup complete! Starting application..."

# Switch to non-root user and start the application
exec su-exec rostering "$@"