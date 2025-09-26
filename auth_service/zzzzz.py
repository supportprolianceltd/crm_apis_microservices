
# python manage.py makemigrations users core 
# python manage.py migrate_schemas --shared
# python manage.py migrate_schemas

#python manage.py shell
from core.models import Tenant, Domain
if not Tenant.objects.filter(schema_name='public').exists():
    tenant = Tenant.objects.create(
        name='public',
        schema_name='public',
    )
    tenant.auto_create_schema = False
    tenant.save()
    Domain.objects.create(tenant=tenant, domain='127.0.0.1', is_primary=True)
    Domain.objects.create(tenant=tenant, domain='localhost', is_primary=False)

from django_tenants.utils import tenant_context
tenant = Tenant.objects.get(schema_name='proliance')
with tenant_context(tenant):
    CustomUser.objects.create_superuser(
        username='david',
        email='david.dappa@prolianceltd.com',
        password='qwerty',
        role='admin',
        first_name='David',
        last_name='Dappa',
        job_role='Frontend Developer',
        tenant=tenant
    )


from core.models import Tenant, Domain
if not Tenant.objects.filter(schema_name='arts').exists():
    tenant = Tenant.objects.create(
        name='arts',
        schema_name='arts',
    )
    tenant.auto_create_schema = False
    tenant.save()
    Domain.objects.create(tenant=tenant, domain='artstraining.co.uk', is_primary=True)

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
    )
    tenant.auto_create_schema = False
    tenant.save()
    Domain.objects.create(tenant=tenant, domain='netwiver.com', is_primary=True)
    

# python manage.py shell
from core.models import Tenant
from users.models import CustomUser
from django_tenants.utils import tenant_context
tenant = Tenant.objects.get(schema_name='arts')
with tenant_context(tenant):
    CustomUser.objects.create_superuser(
        username='ekeneonwon',
        email='support@artstraining.co.uk',
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
tenant = Tenant.objects.get(schema_name='arts')
with tenant_context(tenant):
    CustomUser.objects.create_superuser(
        username='info',
        email='support@netwiver.com',
        password='qwerty',
        role='admin',
        first_name='Bianka',
        last_name='Jones Admin Officer',
        tenant=tenant
    )

    
from core.models import Tenant
from users.models import CustomUser
from django_tenants.utils import tenant_context
tenant = Tenant.objects.get(schema_name='proliance')
with tenant_context(tenant):
    CustomUser.objects.create_superuser(
        username='dappa',
        email='david.dappa@prolianceltd.com',
        password='qwerty',
        role='admin',
        first_name='David',
        last_name='Dappa',
        job_role=' Frontend developer',
        tenant=tenant
    )


from core.models import Tenant
from users.models import CustomUser
from django_tenants.utils import tenant_context

# Get the tenant
tenant = Tenant.objects.get(schema_name='proliance')

# Enter tenant context
with tenant_context(tenant):
    try:
        user = CustomUser.objects.get(email='support@prolianceltd.com')
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
tenant = Tenant.objects.get(schema_name='arts')
with tenant_context(tenant):
    priv, pub = generate_rsa_keypair()
    RSAKeyPair.objects.create(
        tenant=tenant,
        private_key_pem=priv,
        public_key_pem=pub,
        active=True
    )
    print(f"RSAKeyPair created for tenant: {tenant.schema_name}")




