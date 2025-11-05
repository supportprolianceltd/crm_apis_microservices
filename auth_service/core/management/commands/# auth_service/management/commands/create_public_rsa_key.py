# auth_service/management/commands/create_public_rsa_key.py
import logging
from django.core.management.base import BaseCommand
from django_tenants.utils import get_public_schema_name, tenant_context
from django.db import connection

from core.models import Tenant
from users.models import RSAKeyPair
from auth_service.utils.jwt_rsa import generate_rsa_keypair, generate_kid

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Create an active RSA key pair for the public tenant (idempotent)."

    def handle(self, *args, **options):
        public_schema = get_public_schema_name()
        logger.info(f"Ensuring RSA key pair exists for public tenant ({public_schema})")

        try:
            public_tenant = Tenant.objects.get(schema_name=public_schema)
        except Tenant.DoesNotExist:
            logger.error("Public tenant not found – cannot create RSA key.")
            return

        # Switch to public schema
        with tenant_context(public_tenant):
            # Guard: if table does not exist yet, skip silently (migrations will create it)
            with connection.cursor() as cur:
                cur.execute("SELECT to_regclass('users_rsakeypair')")
                if not cur.fetchone()[0]:
                    logger.debug("users_rsakeypair table missing in public – skipping key creation")
                    return

            # Idempotent: create only if none active exists
            if RSAKeyPair.objects.filter(tenant=public_tenant, active=True).exists():
                logger.info("Active RSA key already exists for public tenant – nothing to do.")
                return

            private_pem, public_pem = generate_rsa_keypair()
            kid = generate_kid()  # you already have this helper

            RSAKeyPair.objects.create(
                tenant=public_tenant,
                kid=kid,
                private_key_pem=private_pem,
                public_key_pem=public_pem,
                active=True,
            )
            logger.info(f"RSA key pair created for public tenant (kid={kid})")

        self.stdout.write(self.style.SUCCESS("Public RSA key ready."))