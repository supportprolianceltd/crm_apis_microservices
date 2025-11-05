# #!/bin/bash
# set -e
# cd /app

# echo "=============================================="
# echo "[STARTUP] Waiting for database to be ready..."
# echo "=============================================="
# sleep 10

# echo ""
# echo "=============================================="
# echo "[STARTUP] Fixing migration sync for public schema..."
# echo "=============================================="
# # Check if tables exist and handle migration state properly
# python -c "
# import os
# import sys
# import django
# os.environ['DJANGO_SETTINGS_MODULE'] = 'auth_service.settings'
# django.setup()
# from django.db import connection
# try:
#     with connection.cursor() as cursor:
#         # Check if django_migrations table exists
#         cursor.execute(\"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'django_migrations');\")
#         migrations_table_exists = cursor.fetchone()[0]
        
#         # Check if core_globaluser exists
#         cursor.execute(\"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'core_globaluser');\")
#         core_globaluser_exists = cursor.fetchone()[0]
        
#         cursor.execute(\"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'users_rsakeypair');\")
#         users_rsakeypair_exists = cursor.fetchone()[0]
    
#     if not migrations_table_exists:
#         print('django_migrations table missing - database is fresh.')
#     elif core_globaluser_exists and users_rsakeypair_exists:
#         print('All required tables exist - no fix needed.')
#     else:
#         print('Tables exist but migration state is inconsistent.')
#         print('Some tenant tables may be missing in public schema.')
        
# except Exception as e:
#     print(f'Error checking tables: {e}')
#     sys.exit(1)
# "

# echo ""
# echo "=============================================="
# echo "[STARTUP] Step 1: Making migrations..."
# echo "=============================================="
# python manage.py makemigrations --noinput

# echo ""
# echo "=============================================="
# echo "[STARTUP] Step 2: Applying migrations with --fake-initial..."
# echo "=============================================="
# # Use --fake-initial to handle existing tables
# python manage.py migrate --fake-initial --noinput

# echo ""
# echo "=============================================="
# echo "[STARTUP] Step 2.5: Applying tenant apps to PUBLIC schema explicitly..."
# echo "=============================================="
# # Force tenant apps to create tables in public schema
# python manage.py migrate users --database=default --noinput
# python manage.py migrate admin --database=default --noinput

# echo ""
# echo "=============================================="
# echo "[STARTUP] Step 3: Setting up global admin (with error handling)..."
# echo "=============================================="
# # Check if users_rsakeypair exists before running setup_global_admin
# python -c "
# import os
# import sys
# import django
# os.environ['DJANGO_SETTINGS_MODULE'] = 'auth_service.settings'
# django.setup()
# from django.db import connection

# with connection.cursor() as cursor:
#     cursor.execute(\"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'users_rsakeypair');\")
#     rsa_table_exists = cursor.fetchone()[0]

# if rsa_table_exists:
#     print('✓ users_rsakeypair table exists - running setup_global_admin')
#     os.system('python manage.py setup_global_admin')
# else:
#     print('⚠️ users_rsakeypair table missing - skipping setup_global_admin')
#     print('⚠️ Manual intervention required: RSA key generation will fail')
# "

# echo ""
# echo "=============================================="
# echo "[STARTUP] Step 4: Generating RSA keys for public tenant..."
# echo "=============================================="
# python manage.py shell -c "
# import os
# os.environ['DJANGO_SETTINGS_MODULE'] = 'auth_service.settings'
# import django
# django.setup()
# import uuid
# from core.models import Tenant
# from users.models import RSAKeyPair
# from django_tenants.utils import tenant_context
# from cryptography.hazmat.primitives.asymmetric import rsa
# from cryptography.hazmat.primitives import serialization
# from django.db import connection

# # Check if the table exists first
# with connection.cursor() as cursor:
#     cursor.execute(\"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'users_rsakeypair');\")
#     table_exists = cursor.fetchone()[0]

# if not table_exists:
#     print('❌ users_rsakeypair table does not exist - cannot generate RSA keys')
#     print('❌ Please run migrations manually: python manage.py migrate users --database=default')
# else:
#     try:
#         public_tenant = Tenant.objects.get(schema_name='public')
#         with tenant_context(public_tenant):
#             if not RSAKeyPair.objects.filter(tenant=public_tenant, active=True).exists():
#                 private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
#                 private_pem = private_key.private_bytes(
#                     encoding=serialization.Encoding.PEM,
#                     format=serialization.PrivateFormat.PKCS8,
#                     encryption_algorithm=serialization.NoEncryption()
#                 )
#                 public_key = private_key.public_key()
#                 public_pem = public_key.public_bytes(
#                     encoding=serialization.Encoding.PEM,
#                     format=serialization.PublicFormat.SubjectPublicKeyInfo
#                 )
#                 kid = uuid.uuid4().hex[:32]
#                 keypair = RSAKeyPair(
#                     tenant=public_tenant,
#                     kid=kid,
#                     private_key_pem=private_pem.decode(),
#                     public_key_pem=public_pem.decode(),
#                     active=True
#                 )
#                 keypair.save()
#                 print('✅ RSA keypair generated for public tenant.')
#             else:
#                 print('✅ Active RSA keypair already exists.')
#     except Exception as e:
#         print(f'❌ Error generating RSA key: {e}')
# "

# echo ""
# echo "=============================================="
# echo "[STARTUP] Step 5: Collecting static files..."
# echo "=============================================="
# python manage.py collectstatic --noinput || echo "⚠️ Static collection failed (non-fatal)"

# echo ""
# echo "=============================================="
# echo "[STARTUP] ✅ All setup complete!"
# echo "[STARTUP] Starting Gunicorn on 0.0.0.0:8001..."
# echo "=============================================="
# exec gunicorn \
#     --bind 0.0.0.0:8001 \
#     --workers ${GUNICORN_WORKERS:-4} \
#     --timeout ${GUNICORN_TIMEOUT:-120} \
#     --access-logfile - \
#     --error-logfile - \
#     --log-level info \
#     auth_service.wsgi:application