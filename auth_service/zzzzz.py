
# python manage.py makemigrations users core 
# python manage.py migrate_schemas --shared
# python manage.py migrate_schemas



from django_tenants.utils import tenant_context
tenant = Tenant.objects.get(schema_name='appBrew')
with tenant_context(tenant):
    CustomUser.objects.create_superuser(
        email='support@appBrew.com',
        password='qwerty',
        role='admin',
        first_name='Tonna',
        last_name='Ezugwu',
        job_role='Project Manager',
        tenant=tenant
    )

from django_tenants.utils import tenant_context
tenant = Tenant.objects.get(schema_name='proliance')
with tenant_context(tenant):
    CustomUser.objects.create_superuser(
        email='tonna.ezugwu@prolianceltd.com',
        password='qwerty',
        role='admin',
        first_name='Tonna',
        last_name='Ezugwu',
        job_role='Project Manager',
        tenant=tenant
    )


from django_tenants.utils import tenant_context
tenant = Tenant.objects.get(schema_name='proliance')
with tenant_context(tenant):
    CustomUser.objects.create_superuser(
   
        email='prince.godson@prolianceltd.com',
        password='qwerty',
        role='admin',
        first_name='Prince',
        last_name='Godson',
        job_role='Frontend Developer',
        tenant=tenant
    )


from django_tenants.utils import tenant_context
tenant = Tenant.objects.get(schema_name='appbrew')
with tenant_context(tenant):
    CustomUser.objects.create_superuser(
        email='supporta@appbrew.com',
        password='qwerty',
        role='root-admin',
        first_name='Ekene',
        last_name='Hanson',
        job_role='Frontend Developer',
        tenant=tenant
    )

from django_tenants.utils import tenant_context
tenant = Tenant.objects.get(schema_name='proliance')
with tenant_context(tenant):
    CustomUser.objects.create_superuser(
        email='apps@prolianceltd.com',
        password='qwerty',
        role='admin',
        first_name='David',
        last_name='Dappa',
        job_role='Frontend Developer',
        tenant=tenant
    )

from core.models import Tenant, Domain
if not Tenant.objects.filter(schema_name='public').exists():
    tenant = Tenant.objects.create(
        name='public',
        schema_name='public',
    )
    tenant.auto_create_schema = False
    tenant.save()
    Domain.objects.create(tenant=tenant, domain='public.com', is_primary=True)

from core.models import Tenant, Domain
if not Tenant.objects.filter(schema_name='auth-service').exists():
    tenant = Tenant.objects.create(
        name='auth-service',
        schema_name='auth-service',
    )
    tenant.auto_create_schema = False
    tenant.save()
    Domain.objects.create(tenant=tenant, domain='auth-service', is_primary=True)


from core.models import Tenant, Domain
if not Tenant.objects.filter(schema_name='proliance').exists():
    tenant = Tenant.objects.create(
        name='proliance',
        schema_name='proliance',
    )
    tenant.auto_create_schema = False
    tenant.save()
    Domain.objects.create(tenant=tenant, domain='prolianceltd.com', is_primary=True)

from core.models import Tenant, Domain
if not Tenant.objects.filter(schema_name='netwiver').exists():
    tenant = Tenant.objects.create(
        name='netwiver',
        schema_name='netwiver',
        status="suspended"
    )
    tenant.auto_create_schema = False
    tenant.save()
    Domain.objects.create(tenant=tenant, domain='netwiver.com', is_primary=True)


from core.models import Tenant, Domain
if not Tenant.objects.filter(schema_name='rodrimine').exists():
    tenant = Tenant.objects.create(
        name='rodrimine',
        schema_name='rodrimine',
        status="active"
    )
    tenant.auto_create_schema = False
    tenant.save()
    Domain.objects.create(tenant=tenant, domain='rodrimine.com', is_primary=True)

from core.models import Tenant, Domain
if not Tenant.objects.filter(schema_name='appbrew').exists():
    tenant = Tenant.objects.create(
        name='appbrew',
        schema_name='appbrew',
        status="active"
    )
    tenant.auto_create_schema = False
    tenant.save()
    Domain.objects.create(tenant=tenant, domain='appbrew.com', is_primary=True)
    

# python manage.py shell
from core.models import Tenant
from users.models import CustomUser
from django_tenants.utils import tenant_context
tenant = Tenant.objects.get(schema_name='rodrimine')
with tenant_context(tenant):
    CustomUser.objects.create_superuser(
        email='support@rodrimine.com',
        password='qwerty',
        role='admin',
        first_name='Ikenga',
        last_name='Odili',
        job_role='Admin Desk',
        tenant=tenant
    )

    

from core.models import Tenant
from users.models import CustomUser
from django_tenants.utils import tenant_context
tenant = Tenant.objects.get(schema_name='rodrimine')
with tenant_context(tenant):
    CustomUser.objects.create_superuser(
        email='admin@rodrimine.com',
        password='qwerty',
        role='root-admin',
        first_name='Gideon',
        last_name='Jones Admin Officer',
        tenant=tenant
    )

    
from core.models import Tenant
from users.models import CustomUser
from django_tenants.utils import tenant_context
tenant = Tenant.objects.get(schema_name='proliance')
with tenant_context(tenant):
    CustomUser.objects.create_superuser(
        email='prince.godson@prolianceltd.com',
        password='qwerty',
        role='admin',
        first_name='Prince',
        last_name='Godson',
        job_role=' Frontend Developer',
        tenant=tenant
    )
    
from core.models import Tenant
from users.models import CustomUser
from django_tenants.utils import tenant_context
tenant = Tenant.objects.get(schema_name='appbrew')
with tenant_context(tenant):
    CustomUser.objects.create_superuser(
        email='support@appbrew.com',
        password='qwerty',
        role='staff',
        first_name='Abib',
        last_name='Achmed',
        job_role=' Frontend Developer',
        tenant=tenant
    )


from core.models import Tenant
from users.models import CustomUser
from django_tenants.utils import tenant_context

# Get the tenant
tenant = Tenant.objects.get(schema_name='rodimine')

# Enter tenant context
with tenant_context(tenant):
    try:
        user = CustomUser.objects.get(email='support@rodimine.com')
        user.delete()
        print("User deleted successfully.")
    except CustomUser.DoesNotExist:
        print("User not found.")

from core.models import Tenant
from subscriptions.models import Subscription
tenant = Tenant.objects.get(schema_name='proliance')
Subscription.objects.create(tenant=tenant, module='talent_engine', is_active=True)


from core.models import Tenant

# List all tenants
for t in Tenant.objects.all():
    print(f"Name: {t.name}, Schema: {t.schema_name}")

# One-liner alternative (Linux shell)

# python manage.py shell -c "from core.models import Tenant; print(list(Tenant.objects.values_list('schema_name', flat=True)))"

from core.models import Tenant
tenant = Tenant.objects.all()
for t in tenant:
    print(f"Name: {t.name}, Schema: {t.schema_name}")
#python manage.py migrate_schemas --schema=proliance
#sudo systemctl restart gunicorn


#docker exec auth_service python manage.py shell


# https://server1.prolianceltd.com/



#DELETE A TENANT
from core.models import Tenant, Domain
from django_tenants.utils import schema_context

# Change this to the tenant schema name you want to delete
schema_to_delete = 'proliance'  # example

try:
    tenant = Tenant.objects.get(schema_name=schema_to_delete)
except Tenant.DoesNotExist:
    print(f"❌ Tenant with schema '{schema_to_delete}' does not exist.")
else:
    confirm = input(f"⚠️ Are you sure you want to delete tenant '{tenant.name}' (schema: {tenant.schema_name})? Type 'yes' to confirm: ")
    if confirm.lower() == 'yes':
        # Delete associated domains first (optional but cleaner)
        Domain.objects.filter(tenant=tenant).delete()

        # Drop the tenant schema (this removes all tenant data)
        tenant.delete(force_drop=True)
        print(f"✅ Tenant '{tenant.name}' (schema: {tenant.schema_name}) deleted successfully along with its schema.")
    else:
        print("🚫 Tenant deletion aborted.")



from core.models import Tenant
from users.models import RSAKeyPair
from django_tenants.utils import tenant_context

# Your keypair generation function
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

def generate_rsa_keypair(key_size=2048):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=key_size)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode('utf-8')
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode('utf-8')
    return private_pem, public_pem

# Trigger for a specific tenant (e.g., 'auth-service')
tenant = Tenant.objects.get(schema_name='appbrew')
with tenant_context(tenant):
    priv, pub = generate_rsa_keypair()
    RSAKeyPair.objects.create(
        tenant=tenant,
        private_key_pem=priv,
        public_key_pem=pub,
        active=True
    )
    print(f"RSAKeyPair created for tenant: {tenant.schema_name}")




from core.models import Tenant, GlobalUser
from django_tenants.utils import get_public_schema_name, tenant_context

public_tenant = Tenant.objects.get(schema_name=get_public_schema_name())
with tenant_context(public_tenant):
    admin = GlobalUser.objects.get(email='admin@platform.local')
    print(f"Admin: {admin.email} | Active: {admin.is_active} | Superuser: {admin.is_superuser} | Staff: {admin.is_staff}")
    print(f"Public tenant domains: {[d.domain for d in public_tenant.domains.all()]}")


from django.contrib.auth import authenticate
from core.models import Tenant
from django_tenants.utils import get_public_schema_name, tenant_context

public_tenant = Tenant.objects.get(schema_name=get_public_schema_name())
with tenant_context(public_tenant):
    user = authenticate(email='admin@platform.local', password='SuperAdmin2025!')
    print(f"Authenticated: {user is not None} | User: {user.email if user else 'None'}")


from core.models import Tenant, Domain
from django_tenants.utils import get_public_schema_name

# Get public tenant
public_tenant = Tenant.objects.get(schema_name=get_public_schema_name())

# Add global admin domain (for email @platform.local)
Domain.objects.get_or_create(
    domain='platform.local',
    tenant=public_tenant,
    defaults={'is_primary': False}  # Not primary; localhost stays primary
)

# Add internal service domain (for auth-service:8001 requests)
Domain.objects.get_or_create(
    domain='auth-service',
    tenant=public_tenant,
    defaults={'is_primary': False}
)

# Verify
print("Public tenant domains:", [d.domain for d in public_tenant.domains.all()])