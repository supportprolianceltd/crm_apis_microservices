# users/management/commands/setup_global_admin.py

import os
import uuid
from django.core.management.base import BaseCommand
from django.db import connection
from django_tenants.utils import get_public_schema_name
from core.models import Tenant, Domain, GlobalUser
from users.models import RSAKeyPair
from auth_service.utils.jwt_rsa import generate_rsa_keypair


class Command(BaseCommand):
    help = 'Setup public tenant, domain, global admin, and RSA keypair'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            default=None,
            help='Admin email (default: from GLOBAL_ADMIN_EMAIL env)'
        )
        parser.add_argument(
            '--password',
            type=str,
            default=None,
            help='Admin password (default: from GLOBAL_ADMIN_PASSWORD env)'
        )

    def handle(self, *args, **options):
        # Set public schema
        connection.set_schema(get_public_schema_name())

        # Get credentials from options or environment
        email = options['email'] or os.getenv('GLOBAL_ADMIN_EMAIL', 'admin@platform.local')
        password = options['password'] or os.getenv('GLOBAL_ADMIN_PASSWORD', 'SuperAdmin2025!')

        self.stdout.write('=' * 60)
        self.stdout.write(self.style.SUCCESS('🚀 Setting up Global Platform Admin'))
        self.stdout.write('=' * 60)

        # 1. Create/Get public tenant
        public_tenant, created = Tenant.objects.get_or_create(
            schema_name='public',
            defaults={
                'name': 'Public Platform',
                'organizational_id': 'TEN-0000',
                'unique_id': uuid.uuid4()
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS('✓ Created public tenant'))
        else:
            self.stdout.write(self.style.WARNING('✓ Public tenant already exists'))

        # 2. Create/Get public domain
        domain, created = Domain.objects.get_or_create(
            domain='localhost',
            tenant=public_tenant,
            defaults={'is_primary': True}
        )
        if created:
            self.stdout.write(self.style.SUCCESS('✓ Created localhost domain'))
        else:
            self.stdout.write(self.style.WARNING('✓ Localhost domain already exists'))

        # 3. Create global super-admin using GlobalUser (NO username field)
        if not GlobalUser.objects.filter(email=email).exists():
            admin_user = GlobalUser.objects.create_superuser(
                email=email,
                password=password,
                first_name='Global',
                last_name='Admin',
                role='super-admin',
                is_staff=True,
                is_superuser=True,
                is_active=True
            )
            self.stdout.write(self.style.SUCCESS(f'✓ Created global super-admin'))
            self.stdout.write(f'  📧 Email: {email}')
            self.stdout.write(f'  🔑 Password: {"*" * len(password)} (set from env)')
        else:
            self.stdout.write(self.style.WARNING(f'✓ Global super-admin already exists: {email}'))

        # 4. Create RSA keypair for JWT signing
        if not RSAKeyPair.objects.filter(tenant=public_tenant, active=True).exists():
            private_pem, public_pem = generate_rsa_keypair()
            keypair = RSAKeyPair.objects.create(
                tenant=public_tenant,
                kid=str(uuid.uuid4().hex[:32]),
                private_key_pem=private_pem,
                public_key_pem=public_pem,
                active=True
            )
            self.stdout.write(self.style.SUCCESS(f'✓ Generated RSA keypair'))
            self.stdout.write(f'  🔐 Key ID: {keypair.kid}')
        else:
            keypair = RSAKeyPair.objects.filter(tenant=public_tenant, active=True).first()
            self.stdout.write(self.style.WARNING(f'✓ RSA keypair already exists'))
            self.stdout.write(f'  🔐 Key ID: {keypair.kid}')

        self.stdout.write('=' * 60)
        self.stdout.write(self.style.SUCCESS('✅ Global admin setup complete!'))
        self.stdout.write('=' * 60)