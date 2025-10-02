# users/management/commands/create_tenant_users.py
import uuid
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django_tenants.utils import tenant_context
from core.models import Tenant
from users.models import CustomUser
from users.serializers import CustomUserMinimalSerializer
from auth_service.utils.jwt_rsa import issue_rsa_jwt


class Command(BaseCommand):
    help = "Create users under a specific tenant"

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant", type=str, default="proliance", help="Schema name of the tenant (default: proliance)"
        )

    def handle(self, *args, **options):
        tenant_schema = options["tenant"]

        try:
            tenant = Tenant.objects.get(schema_name=tenant_schema)
            self.stdout.write(self.style.SUCCESS(f"Found tenant: {tenant.name}"))

            # Sample users data
            users_data = [
                {
                    "username": "addie",
                    "email": "addie@prolianceltd.com",
                    "password": "password123",  # In production, use a secure password
                    "first_name": "Addie",
                    "last_name": "User",
                    "role": "admin",
                    "is_active": True,
                },
                {
                    "username": "methus",
                    "email": "methus@prolianceltd.com",
                    "password": "password123",
                    "first_name": "Metheus",
                    "last_name": "User",
                    "role": "manager",
                    "is_active": True,
                },
                {
                    "username": "seth",
                    "email": "seth@prolianceltd.com",
                    "password": "password123",
                    "first_name": "Seth",
                    "last_name": "User",
                    "role": "staff",
                    "is_active": True,
                },
            ]

            with tenant_context(tenant):
                created_count = 0
                for user_data in users_data:
                    username = user_data.pop("username")
                    password = user_data.pop("password")

                    # Create or update user
                    user, created = CustomUser.objects.update_or_create(
                        username=username,
                        defaults={
                            **user_data,
                            'tenant': tenant  # Ensure tenant is set
                        }
                    )

                    if created or not user.has_usable_password():
                        user.set_password(password)
                        user.save()
                        created_count += 1
                        self.stdout.write(self.style.SUCCESS(f"Created user: {user.email}"))

                    else:
                        self.stdout.write(self.style.WARNING(f"User already exists: {user.email}"))

                    # Ensure user has proper tenant relationship for token generation
                    if not user.tenant:
                        user.tenant = tenant
                        user.save()
                        self.stdout.write(self.style.WARNING(f"Fixed tenant relationship for user: {user.email}"))

                    # Generate RSA JWT tokens (similar to CustomTokenSerializer logic)
                    try:
                        # Debug: Check user and tenant before token generation
                        self.stdout.write(
                            self.style.WARNING(f"Generating tokens for user: {user.email}, tenant: {user.tenant}")
                        )

                        # Fetch the primary domain
                        primary_domain = tenant.domain_set.filter(is_primary=True).first()
                        tenant_domain = primary_domain.domain if primary_domain else None

                        # Create access token payload
                        access_payload = {
                            "jti": str(uuid.uuid4()),
                            "sub": user.email,
                            "role": user.role,
                            "status": user.status,
                            "tenant_id": user.tenant.id,
                            "tenant_organizational_id": str(tenant.organizational_id),
                            "tenant_unique_id": str(tenant.unique_id),
                            "tenant_schema": user.tenant.schema_name,
                            "tenant_domain": tenant_domain,
                            "has_accepted_terms": user.has_accepted_terms,
                            "user": CustomUserMinimalSerializer(user).data,
                            "email": user.email,
                            "type": "access",
                            "exp": int((timezone.now() + timedelta(minutes=180)).timestamp()),
                        }
                        access_token = issue_rsa_jwt(access_payload, user.tenant)

                        # Create refresh token payload
                        refresh_jti = str(uuid.uuid4())
                        refresh_payload = {
                            "jti": refresh_jti,
                            "sub": user.email,
                            "tenant_id": user.tenant.id,
                            "tenant_organizational_id": str(tenant.organizational_id),
                            "tenant_unique_id": str(tenant.unique_id),
                            "tenant_domain": tenant_domain,
                            "type": "refresh",
                            "exp": int((timezone.now() + timedelta(days=7)).timestamp()),
                        }
                        refresh_token = issue_rsa_jwt(refresh_payload, user.tenant)

                        # Output token information
                        self.stdout.write(
                            self.style.SUCCESS(f"Generated RSA JWT access_token: {access_token}")
                        )
                        self.stdout.write(
                            self.style.SUCCESS(f"Generated RSA JWT refresh_token: {refresh_token}")
                        )

                        # Display token details for verification
                        token_data = {
                            "access_token": access_token,
                            "refresh_token": refresh_token,
                            "tenant_id": user.tenant.id,
                            "tenant_organizational_id": str(tenant.organizational_id),
                            "tenant_unique_id": str(tenant.unique_id),
                            "tenant_schema": user.tenant.schema_name,
                            "tenant_domain": tenant_domain,
                            "user": CustomUserMinimalSerializer(user).data,
                            "has_accepted_terms": user.has_accepted_terms,
                        }
                        self.stdout.write(
                            self.style.SUCCESS(f"Token data: {token_data}")
                        )

                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f"Failed to generate RSA JWT tokens for user {user.email}: {str(e)}")
                        )
                self.stdout.write(
                    self.style.SUCCESS(
                        f"\nSuccessfully processed {len(users_data)} users. Created {created_count} new users."
                    )
                )

        except Tenant.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Tenant with schema "{tenant_schema}" does not exist'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"An error occurred: {str(e)}"))
