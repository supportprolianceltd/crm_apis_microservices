#!/bin/bash
set -e

echo "🚀 Starting Rostering Service..."

cd /app

# Check if dist/server.js exists
if [ ! -f "dist/server.js" ]; then
  echo "❌ ERROR: dist/server.js not found!"
  exit 1
fi

echo "✅ Server file found: dist/server.js"

# Generate Prisma client
echo "🔧 Generating Prisma client..."
npx prisma generate

if [ $? -ne 0 ]; then
  echo "❌ Prisma generate failed"
  exit 1
fi

echo "✅ Prisma client generated"

# Wait for database to be ready
echo "⏳ Waiting for database to be ready..."
MAX_RETRIES=30
RETRY_COUNT=0
DB_READY=false

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
  if PGPASSWORD=password psql -h rostering-db -U postgres -d rostering_dev -c "SELECT 1;" 2>/dev/null; then
    echo "✅ Database connection successful!"
    
    # Apply database migrations
    echo "🔧 Applying database schema..."
    if npx prisma db push --skip-generate; then
      echo "✅ Database schema synchronized successfully!"
      DB_READY=true
      break
    else
      echo "❌ Failed to apply database schema"
    fi
  fi

  RETRY_COUNT=$((RETRY_COUNT+1))
  echo "💤 Database not ready, waiting 2 seconds... (attempt $RETRY_COUNT/$MAX_RETRIES)"
  sleep 2
done

if [ "$DB_READY" = false ]; then
  echo "❌ Failed to connect to database after $MAX_RETRIES attempts"
  exit 1
fi

echo "🎉 Setup complete! Starting application..."
exec node dist/server.js