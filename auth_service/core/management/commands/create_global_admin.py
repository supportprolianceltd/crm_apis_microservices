# core/management/commands/create_global_admin.py
from django.core.management.base import BaseCommand
from django_tenants.utils import tenant_context, get_public_schema_name
from core.models import Tenant, GlobalUser, UsernameIndex
import os

class Command(BaseCommand):
    help = 'Create global admin users'

    def add_arguments(self, parser):
        parser.add_argument('--email', type=str, help='Admin email')
        parser.add_argument('--password', type=str, help='Admin password')
        parser.add_argument('--first-name', type=str, default='Global', help='First name')
        parser.add_argument('--last-name', type=str, default='Admin', help='Last name')
        parser.add_argument('--username', type=str, help='Username (optional)')
        parser.add_argument('--force', action='store_true', help='Force creation even if exists')

    def handle(self, *args, **options):
        try:
            public_tenant = Tenant.objects.get(schema_name=get_public_schema_name())
        except Tenant.DoesNotExist:
            self.stdout.write(
                self.style.ERROR('Public tenant does not exist. Run migrations first.')
            )
            return

        with tenant_context(public_tenant):
            # Get values from arguments or environment
            email = options['email'] or os.getenv('GLOBAL_ADMIN_EMAIL')
            password = options['password'] or os.getenv('GLOBAL_ADMIN_PASSWORD')
            first_name = options['first_name']
            last_name = options['last_name']
            username = options['username'] or os.getenv('GLOBAL_ADMIN_USERNAME')
            force = options['force']

            if not email or not password:
                self.stdout.write(
                    self.style.ERROR('Email and password are required. Set via arguments or environment variables.')
                )
                return

            # Default username to email prefix if not provided
            if not username:
                username = email.split('@')[0]

            # Check if user exists
            existing_user = GlobalUser.objects.filter(email=email).first()
            if existing_user:
                if force:
                    self.stdout.write(self.style.WARNING(f'Updating existing global admin: {email}'))
                    existing_user.set_password(password)
                    existing_user.first_name = first_name
                    existing_user.last_name = last_name
                    existing_user.username = username
                    existing_user.is_active = True
                    existing_user.is_superuser = True
                    existing_user.is_staff = True
                    existing_user.save()
                    admin = existing_user
                else:
                    self.stdout.write(self.style.WARNING(f'Global admin {email} already exists'))
                    admin = existing_user
            else:
                # Create global admin
                admin = GlobalUser.objects.create_superuser(
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    username=username
                )
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully created global admin: {email}')
                )

            # Ensure username is indexed
            UsernameIndex.objects.update_or_create(
                username=username,
                defaults={'tenant': public_tenant, 'user_id': admin.id}
            )
            self.stdout.write(
                self.style.SUCCESS(f'Username index updated for: {username}')
            )

            # Also index by email for fallback lookup
            UsernameIndex.objects.update_or_create(
                username=email,
                defaults={'tenant': public_tenant, 'user_id': admin.id}
            )
            self.stdout.write(
                self.style.SUCCESS(f'Email index updated for: {email}')
            )