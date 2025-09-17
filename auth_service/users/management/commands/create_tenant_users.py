# users/management/commands/create_tenant_users.py
from django.core.management.base import BaseCommand
from django_tenants.utils import tenant_context
from core.models import Tenant
from users.models import CustomUser, UserProfile

class Command(BaseCommand):
    help = 'Create users under a specific tenant'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant',
            type=str,
            default='proliance',
            help='Schema name of the tenant (default: proliance)'
        )

    def handle(self, *args, **options):
        tenant_schema = options['tenant']
        
        try:
            tenant = Tenant.objects.get(schema_name=tenant_schema)
            self.stdout.write(self.style.SUCCESS(f'Found tenant: {tenant.name}'))
            
            # Sample users data
            users_data = [
                {
                    'username': 'admin',
                    'email': 'admin@prolianceltd.com',
                    'password': 'admin123',  # In production, use a secure password
                    'first_name': 'Admin',
                    'last_name': 'User',
                    'role': 'admin',
                    'is_active': True
                },
                {
                    'username': 'manager',
                    'email': 'manager@prolianceltd.com',
                    'password': 'manager123',
                    'first_name': 'Manager',
                    'last_name': 'User',
                    'role': 'manager',
                    'is_active': True
                },
                {
                    'username': 'staff',
                    'email': 'staff@prolianceltd.com',
                    'password': 'staff123',
                    'first_name': 'Staff',
                    'last_name': 'User',
                    'role': 'staff',
                    'is_active': True
                }
            ]
            
            with tenant_context(tenant):
                created_count = 0
                for user_data in users_data:
                    username = user_data.pop('username')
                    password = user_data.pop('password')
                    
                    # Create or update user
                    user, created = CustomUser.objects.update_or_create(
                        username=username,
                        defaults=user_data
                    )
                    
                    if created or not user.has_usable_password():
                        user.set_password(password)
                        user.save()
                        created_count += 1
                        self.stdout.write(self.style.SUCCESS(f'Created user: {user.email}'))
                    else:
                        self.stdout.write(self.style.WARNING(f'User already exists: {user.email}'))
                
                self.stdout.write(self.style.SUCCESS(f'\nSuccessfully processed {len(users_data)} users. Created {created_count} new users.'))
                
        except Tenant.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Tenant with schema "{tenant_schema}" does not exist'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'An error occurred: {str(e)}'))