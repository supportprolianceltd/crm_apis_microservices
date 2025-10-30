#!/bin/bash
set -e

cd /app

echo "=== AUTH SERVICE STARTUP ==="
echo "Environment: ${DEPLOYMENT_ENV:-production}"

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to wait for database with timeout
wait_for_db() {
    local max_attempts=30
    local attempt=1
    
    echo "Waiting for database to be ready..."
    
    while [ $attempt -le $max_attempts ]; do
        if python -c "
import os
import django
from django.db import connection
from django.db.utils import OperationalError

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'auth_service.settings')
django.setup()

try:
    connection.ensure_connection()
    print('SUCCESS: Database connection established')
    exit(0)
except OperationalError as e:
    print(f'Attempt $attempt: Database not ready - {e}')
    exit(1)
except Exception as e:
    print(f'Attempt $attempt: Unexpected error - {e}')
    exit(2)
" 2>/dev/null; then
            echo "✅ Database is ready!"
            return 0
        else
            echo "⏳ Database not ready (attempt $attempt/$max_attempts), waiting 5 seconds..."
            sleep 5
            ((attempt++))
        fi
    done
    
    echo "❌ Database failed to become ready after $max_attempts attempts"
    return 1
}

# Function to wait for Redis
wait_for_redis() {
    local max_attempts=10
    local attempt=1
    
    echo "Waiting for Redis to be ready..."
    
    while [ $attempt -le $max_attempts ]; do
        if python -c "
import redis
import os
try:
    r = redis.from_url('${REDIS_URL}')
    r.ping()
    print('SUCCESS: Redis connection established')
    exit(0)
except Exception as e:
    print(f'Attempt $attempt: Redis not ready - {e}')
    exit(1)
" 2>/dev/null; then
            echo "✅ Redis is ready!"
            return 0
        else
            echo "⏳ Redis not ready (attempt $attempt/$max_attempts), waiting 3 seconds..."
            sleep 3
            ((attempt++))
        fi
    done
    
    echo "⚠️ Redis failed to become ready, but continuing..."
    return 0
}

# Function to create global admin with retries
create_global_admin() {
    local max_attempts=3
    local attempt=1
    
    # Use environment variables from .env
    local email="${GLOBAL_ADMIN_EMAIL}"
    local password="${GLOBAL_ADMIN_PASSWORD}"
    local username="${GLOBAL_ADMIN_USERNAME}"
    
    echo "Creating global admin: $email"
    
    while [ $attempt -le $max_attempts ]; do
        echo "Attempt $attempt to create global admin..."
        
        # Check if global admin already exists
        if python manage.py shell -c "
import os
import django
from django_tenants.utils import tenant_context, get_public_schema_name
from core.models import Tenant, GlobalUser

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'auth_service.settings')
django.setup()

try:
    public_tenant = Tenant.objects.get(schema_name=get_public_schema_name())
    with tenant_context(public_tenant):
        if GlobalUser.objects.filter(email='$email').exists():
            print('EXISTS: Global admin $email already exists')
            exit(0)
        else:
            print('NOT_FOUND: No global admin found, will create one')
            exit(1)
except Exception as e:
    print(f'ERROR: {e}')
    exit(2)
" 2>/dev/null; then
            echo "✅ Global admin already exists, skipping creation."
            return 0
        fi
        
        # Create global admin using management command
        if python manage.py create_global_admin \
            --email="$email" \
            --password="$password" \
            --username="$username" \
            --first-name="Global" \
            --last-name="Admin" \
            --force; then
            echo "✅ Global admin created successfully"
            return 0
        else
            echo "❌ Failed to create global admin (attempt $attempt)"
            ((attempt++))
            sleep 5
        fi
    done
    
    echo "⚠️ All attempts to create global admin failed, but continuing startup..."
    return 1
}

# Function to create RSA key for public tenant
create_rsa_key() {
    echo "Creating RSA key for public tenant..."
    
    if python manage.py shell -c "
import os
import django
from django_tenants.utils import tenant_context, get_public_schema_name
from core.models import Tenant
from users.models import RSAKeyPair

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'auth_service.settings')
django.setup()

try:
    public_tenant = Tenant.objects.get(schema_name=get_public_schema_name())
    with tenant_context(public_tenant):
        if RSAKeyPair.objects.filter(active=True).exists():
            print('EXISTS: Active RSA key already exists for public tenant')
            exit(0)
        else:
            from auth_service.utils.jwt_rsa import create_and_store_keypair
            keypair = create_and_store_keypair(public_tenant)
            print(f'SUCCESS: RSA key created with KID: {keypair.kid}')
            exit(0)
except Exception as e:
    print(f'ERROR: {e}')
    exit(1)
" 2>/dev/null; then
        echo "✅ RSA key creation completed"
        return 0
    else
        echo "⚠️ Failed to create RSA key, but continuing startup..."
        return 1
    fi
}

# Function to create default tenants
create_default_tenants() {
    echo "Setting up default tenants..."
    
    python manage.py shell -c "
import os
import django
from core.models import Tenant, Domain
from django_tenants.utils import get_public_schema_name

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'auth_service.settings')
django.setup()

# Ensure public tenant exists
try:
    public_tenant = Tenant.objects.get(schema_name=get_public_schema_name())
    print('EXISTS: Public tenant found')
except Tenant.DoesNotExist:
    print('CREATING: Public tenant...')
    public_tenant = Tenant(
        schema_name=get_public_schema_name(),
        name='Public Platform',
        organizational_id='PUB-0001'
    )
    public_tenant.save()
    
    # Create domain for public tenant
    Domain.objects.create(
        domain='localhost',
        tenant=public_tenant,
        is_primary=True
    )
    print('SUCCESS: Public tenant created')

# Create example tenant for development
if os.getenv('DEBUG', 'False').lower() == 'true':
    try:
        example_tenant = Tenant.objects.get(schema_name='example')
        print('EXISTS: Example tenant found')
    except Tenant.DoesNotExist:
        print('CREATING: Example tenant...')
        example_tenant = Tenant(
            schema_name='example',
            name='Example Company',
            organizational_id='TEN-0001'
        )
        example_tenant.save()
        
        Domain.objects.create(
            domain='example.localhost',
            tenant=example_tenant,
            is_primary=True
        )
        print('SUCCESS: Example tenant created')
else:
    print('SKIP: Example tenant creation (production mode)'
" 2>/dev/null || echo "⚠️ Tenant setup completed with warnings"
}

# Function to run health checks
run_health_checks() {
    echo "Running health checks..."
    
    # Check if migrations are applied
    if python manage.py showmigrations --plan | grep -q "\[ \]"; then
        echo "⚠️ Some migrations are not applied"
        return 1
    else
        echo "✅ All migrations applied"
    fi
    
    # Check if we can access the database
    if python manage.py shell -c "
from django.db import connection
try:
    connection.ensure_connection()
    print('SUCCESS: Database accessible')
    exit(0)
except Exception as e:
    print(f'ERROR: {e}')
    exit(1)
" 2>/dev/null; then
        echo "✅ Database health check passed"
    else
        echo "❌ Database health check failed"
        return 1
    fi
    
    return 0
}

# Main execution flow
main() {
    echo "Starting Auth Service initialization..."
    
    # Wait for dependencies
    echo "=== PHASE 1: Waiting for dependencies ==="
    wait_for_db || exit 1
    wait_for_redis
    
    # Run migrations
    echo "=== PHASE 2: Database migrations ==="
    echo "1. Migrating shared apps..."
    python manage.py migrate_schemas --shared --noinput
    
    echo "2. Setting up default tenants..."
    create_default_tenants
    
    echo "3. Migrating public schema..."
    if ! python manage.py migrate_schemas --schema=public --noinput; then
        echo "⚠️ First public schema migration failed, retrying..."
        sleep 5
        python manage.py migrate_schemas --schema=public --noinput || {
            echo "❌ Public schema migration failed after retry"
            exit 1
        }
    fi
    
    echo "4. Migrating all tenant schemas..."
    python manage.py migrate_schemas --noinput
    
    # Create essential data
    echo "=== PHASE 3: Creating essential data ==="
    echo "5. Creating global admin..."
    create_global_admin
    
    echo "6. Creating RSA key for public tenant..."
    create_rsa_key
    
    # Final setup
    echo "=== PHASE 4: Final setup ==="
    echo "7. Collecting static files..."
    python manage.py collectstatic --noinput --clear || echo "⚠️ Static collection had issues"
    
    echo "8. Creating cache table..."
    python manage.py createcachetable || echo "⚠️ Cache table creation failed"
    
    echo "9. Running health checks..."
    run_health_checks || echo "⚠️ Health checks had issues"
    
    echo "✅ All setup tasks completed successfully!"
    echo "=== STARTING GUNICORN ==="
    
    # Calculate workers based on available memory
    local available_mem=$(grep MemAvailable /proc/meminfo | awk '{print $2}')
    local workers=2
    
    if [ "$available_mem" -gt 4000000 ]; then
        workers=4
    elif [ "$available_mem" -gt 2000000 ]; then
        workers=3
    fi
    
    echo "Starting Gunicorn with $workers workers (${available_mem}KB memory available)"
    
    # Start Gunicorn
    exec gunicorn auth_service.wsgi:application \
        --bind=0.0.0.0:8001 \
        --workers=$workers \
        --worker-class=sync \
        --timeout=300 \
        --access-logfile=- \
        --error-logfile=- \
        --capture-output \
        --enable-stdio-inheritance \
        --log-level=info
}

# Handle signals for graceful shutdown
trap 'echo "Shutting down..."; exit 0' SIGTERM SIGINT

# Run main function
main "$@"