#!/bin/bash
# reset_database.sh - Clean database reset for multi-tenancy

echo "==========================================="
echo "🔴 WARNING: This will DELETE ALL DATA!"
echo "==========================================="
echo ""
echo "This script will:"
echo "  1. Stop all containers"
echo "  2. Remove Docker volumes (database data)"
echo "  3. Remove migration files"
echo "  4. Rebuild and start fresh"
echo ""
read -p "Are you sure? (type 'yes' to continue): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Aborted."
    exit 1
fi

echo ""
echo "Step 1: Stopping containers..."
docker-compose down -v

echo ""
echo "Step 2: Removing migration files..."
# Remove all migrations except __init__.py
find ./core/migrations -type f -name "*.py" ! -name "__init__.py" -delete
find ./users/migrations -type f -name "*.py" ! -name "__init__.py" -delete

# Ensure __init__.py exists
touch ./core/migrations/__init__.py
touch ./users/migrations/__init__.py

echo ""
echo "Step 3: Removing Python cache..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete

echo ""
echo "Step 4: Rebuilding containers..."
docker-compose build --no-cache auth-service

echo ""
echo "✅ Database reset complete!"
echo ""
echo "Now run: docker-compose up"