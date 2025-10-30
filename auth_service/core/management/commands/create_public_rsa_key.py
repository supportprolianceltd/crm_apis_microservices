# core/management/commands/create_public_rsa_key.py
from django.core.management.base import BaseCommand
from django_tenants.utils import tenant_context, get_public_schema_name
from core.models import Tenant
from users.models import RSAKeyPair
from auth_service.utils.jwt_rsa import create_and_store_keypair

class Command(BaseCommand):
    help = 'Create RSA keypair for public tenant'

    def handle(self, *args, **options):
        try:
            public_tenant = Tenant.objects.get(schema_name=get_public_schema_name())
        except Tenant.DoesNotExist:
            self.stdout.write(
                self.style.ERROR('Public tenant does not exist. Run migrations first.')
            )
            return

        with tenant_context(public_tenant):
            # Check if active key already exists
            if RSAKeyPair.objects.filter(active=True).exists():
                self.stdout.write(
                    self.style.WARNING('Active RSA key already exists for public tenant')
                )
                return

            # Create new keypair
            try:
                keypair = create_and_store_keypair(public_tenant)
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully created RSA keypair with kid: {keypair.kid}')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Failed to create RSA keypair: {str(e)}')
                )