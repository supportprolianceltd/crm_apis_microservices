#!/bin/bash
set -e

echo "🌱 Starting database seeding for Rostering Service..."
echo "📝 Current directory: $(pwd)"

# Check if docker-compose.seed.yml exists
if [ ! -f "docker-compose.seed.yml" ]; then
  echo "❌ ERROR: docker-compose.seed.yml not found!"
  exit 1
fi

# Check if main docker-compose is running
if ! docker-compose ps | grep -q "Up"; then
  echo "⚠️  Warning: No docker-compose services appear to be running"
  echo "   Make sure your database and other services are running first"
  read -p "Continue anyway? (y/N): " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
  fi
fi

# Run the seeding service
echo "🚀 Running seeding service..."
docker-compose -f docker-compose.seed.yml up rostering-seed

echo "✅ Seeding completed!"
echo ""
echo "💡 Tip: You can now test the rostering API with the seeded data"