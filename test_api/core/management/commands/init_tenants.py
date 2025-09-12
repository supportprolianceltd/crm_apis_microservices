from django.core.management.base import BaseCommand
from django.db import connection
from core.models import Tenant, Domain
import logging
from django.core.management import call_command
from django_tenants.utils import schema_context

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Initialize public schema and default tenants'

    def handle(self, *args, **options):
        # Ensure public schema exists
        if not Tenant.objects.filter(schema_name='public').exists():
            tenant = Tenant.objects.create(
                name='public',
                schema_name='public',
                auto_create_schema=False
            )
            Domain.objects.create(tenant=tenant, domain='localhost', is_primary=True)
            logger.info("Created public tenant")
        
        # Create default tenant (e.g., proliance)
        if not Tenant.objects.filter(schema_name='proliance').exists():
            tenant = Tenant.objects.create(
                name='proliance',
                schema_name='proliance',
                auto_create_schema=True
            )
            Domain.objects.create(tenant=tenant, domain='prolianceltd.com', is_primary=True)
            logger.info("Created proliance tenant")
        
        # Apply migrations to public schema
        connection.set_schema_to_public()
        self.stdout.write("Applying migrations to public schema...")
       
        call_command('migrate', interactive=False)
        
        # Apply migrations to all tenant schemas
        for tenant in Tenant.objects.exclude(schema_name='public'):
            with connection.cursor() as cursor:
                cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {tenant.schema_name};")
            
            with schema_context(tenant.schema_name):
                self.stdout.write(f"Applying migrations to tenant {tenant.schema_name}...")
                call_command('migrate', interactive=False)
        
        self.stdout.write(self.style.SUCCESS("Tenant initialization and migrations completed."))