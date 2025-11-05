#!/bin/bash
set -e

echo "🌱 Starting database seeding process..."
echo "📝 Working directory: $(pwd)"
echo "📝 Node version: $(node --version)"
echo "📝 NPM version: $(npm --version)"

cd /app

# Check if dist directory exists (built app)
if [ ! -d "dist" ]; then
  echo "❌ ERROR: dist/ directory not found! Application needs to be built."
  exit 1
fi

# Generate Prisma client if needed
echo "🔧 Ensuring Prisma client is generated..."
npx prisma generate

if [ $? -ne 0 ]; then
  echo "❌ Prisma generate failed"
  exit 1
fi

echo "✅ Prisma client ready"

# Wait for database to be ready
echo "⏳ Waiting for database..."
MAX_RETRIES=30
RETRY_COUNT=0
DB_READY=false

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
  # Reset database by dropping all tables and recreating schema
  if PGPASSWORD=rostering_password psql -h rostering-db -U rostering_user -d rostering_dev -c "
    DROP SCHEMA public CASCADE;
    CREATE SCHEMA public;
    GRANT ALL ON SCHEMA public TO rostering_user;
    GRANT ALL ON SCHEMA public TO public;
  " 2>/dev/null && npx prisma db push --skip-generate 2>/dev/null; then
    echo "✅ Database is ready!"
    DB_READY=true
    break
  fi

  RETRY_COUNT=$((RETRY_COUNT+1))
  echo "💤 Database not ready, waiting 2 seconds... (attempt $RETRY_COUNT/$MAX_RETRIES)"
  sleep 2
done

if [ "$DB_READY" = false ]; then
  echo "❌ Failed to connect to database after $MAX_RETRIES attempts"
  exit 1
fi

# Run the seed script
echo "🚀 Running seed script..."
npx tsx prisma/seed.ts

if [ $? -eq 0 ]; then
  echo "✅ Database seeding completed successfully!"
else
  echo "❌ Database seeding failed!"
  exit 1
fi