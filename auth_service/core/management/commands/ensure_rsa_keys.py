# management/commands/ensure_rsa_keys.py

from django.core.management.base import BaseCommand
from core.models import Tenant
from users.models import RSAKeyPair
from django_tenants.utils import tenant_context
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

class Command(BaseCommand):
    help = 'Ensure all tenants have active RSA key pairs'

    def handle(self, *args, **options):
        def generate_rsa_keypair():
            private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
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

        tenants = Tenant.objects.all()
        
        for tenant in tenants:
            self.stdout.write(f"Checking {tenant.name}...")
            with tenant_context(tenant):
                if not RSAKeyPair.objects.filter(active=True).exists():
                    self.stdout.write(f"  Creating RSA key pair for {tenant.name}")
                    priv, pub = generate_rsa_keypair()
                    RSAKeyPair.objects.create(
                        tenant=tenant,
                        private_key_pem=priv,
                        public_key_pem=pub,
                        active=True
                    )
                else:
                    self.stdout.write(f"  ✅ {tenant.name} already has active RSA keys")