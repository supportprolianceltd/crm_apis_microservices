
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
if not Tenant.objects.filter(schema_name='arts').exists():
    tenant = Tenant.objects.create(
        name='arts',
        schema_name='arts',
    )
    tenant.auto_create_schema = False
    tenant.save()
    Domain.objects.create(tenant=tenant, domain='artstraining.co.uk', is_primary=True)
    

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
        first_name='Ekene-onwon',
        last_name='Abrahamn',
        job_role='Backend Developer',
        tenant=tenant
    )

    

from core.models import Tenant
from users.models import CustomUser
from django_tenants.utils import tenant_context
tenant = Tenant.objects.get(schema_name='proliance')
with tenant_context(tenant):
    CustomUser.objects.create_superuser(
        username='info',
        email='admin@prolianceltd.com',
        password='qwerty',
        role='admin',
        first_name='Gauis',
        last_name='Immanuel',
        job_role='Care Cordinator',
        tenant=tenant
    )

    
from core.models import Tenant
from users.models import CustomUser
from django_tenants.utils import tenant_context
tenant = Tenant.objects.get(schema_name='proliance')
with tenant_context(tenant):
    CustomUser.objects.create_superuser(
        username='david_dappa',
        email='david.dappa@prolianceltd.com',
        password='qwerty',
        role='admin',
        first_name='David',
        last_name='Dappa',
        job_role='Frontend Engineer',
        tenant=tenant
    )


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