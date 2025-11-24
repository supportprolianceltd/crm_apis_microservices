from django.core.management.base import BaseCommand
from django_tenants.utils import tenant_context
from core.models import Tenant
from users.models import RSAKeyPair
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

class Command(BaseCommand):
    help = 'Create RSA key pair for JWT validation'

    def add_arguments(self, parser):
        parser.add_argument('--kid', type=str, default='8eae781f90f648ebb9ef024b4fbab9d6',
                          help='Key ID for the RSA key pair')
        parser.add_argument('--tenant-schema', type=str, default='appbrew',
                          help='Tenant schema name')

    def handle(self, *args, **options):
        kid = options['kid']
        tenant_schema = options['tenant_schema']

        try:
            tenant = Tenant.objects.get(schema_name=tenant_schema)
            self.stdout.write(f'Found tenant: {tenant.schema_name}')

            with tenant_context(tenant):
                # Check if key already exists
                existing_key = RSAKeyPair.objects.filter(kid=kid).first()
                if existing_key:
                    self.stdout.write(self.style.WARNING(f'Key with KID {kid} already exists'))
                    return

                self.stdout.write(f'Creating RSA key pair with KID: {kid}')

                # Generate private key
                private_key = rsa.generate_private_key(
                    public_exponent=65537,
                    key_size=2048,
                )

                # Serialize private key
                private_pem = private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                )

                # Serialize public key
                public_pem = private_key.public_key().public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo
                )

                # Create the key pair
                key_pair = RSAKeyPair.objects.create(
                    tenant=tenant,
                    kid=kid,
                    private_key_pem=private_pem.decode(),
                    public_key_pem=public_pem.decode(),
                    active=True
                )

                self.stdout.write(self.style.SUCCESS(f'Successfully created RSA key pair with KID: {kid}'))

        except Tenant.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Tenant {tenant_schema} not found'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error creating key: {str(e)}'))
            import traceback
            traceback.print_exc()