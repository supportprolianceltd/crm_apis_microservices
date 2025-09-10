from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from django.utils import timezone
from .models import UserSession
from django.db.models.signals import post_save
from django.dispatch import receiver
from core.models import Tenant
from users.models import RSAKeyPair
from django_tenants.utils import tenant_context
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from django.db import connection
from django.contrib.auth.signals import user_login_failed
from django.dispatch import receiver
from django_tenants.utils import tenant_context
from .models import FailedLogin
import logging
from django.db.models.signals import m2m_changed
from django.contrib.auth.models import Group

logger = logging.getLogger('auth_service')


@receiver(user_logged_in)
def create_user_session(sender, request, user, **kwargs):
    ip = request.META.get('REMOTE_ADDR')
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    UserSession.objects.create(
        user=user,
        login_time=timezone.now(),
        date=timezone.now().date(),
        ip_address=ip,
        user_agent=user_agent
    )

@receiver(user_logged_out)
def close_user_session(sender, request, user, **kwargs):
    try:
        session = UserSession.objects.filter(user=user, logout_time__isnull=True).latest('login_time')
        session.logout_time = timezone.now()
        session.save()
    except UserSession.DoesNotExist:
        pass



def generate_rsa_keypair(key_size: int = 2048):
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size
    )
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

@receiver(post_save, sender=Tenant)
def create_rsa_keypair_for_tenant(sender, instance, created, **kwargs):
    if created:
        # Only create keypair for new tenants

        try:
            with tenant_context(instance):
                # Check if the table exists before creating the keypair
                if 'users_rsakeypair' in connection.introspection.table_names():
                    priv, pub = generate_rsa_keypair()
                    RSAKeyPair.objects.create(
                        tenant=instance,
                        private_key_pem=priv,
                        public_key_pem=pub,
                        active=True
                    )
                else:
                    import logging
                    logger = logging.getLogger('users')
                    logger.warning(f"users_rsakeypair table does not exist in schema {instance.schema_name}. Skipping RSA keypair creation.")
        except Exception as e:
            import logging
            logger = logging.getLogger('users')
            logger.error(f"Failed to create RSAKeyPair for tenant {instance.schema_name}: {str(e)}")




@receiver(user_login_failed)
def log_failed_login(sender, credentials, request, **kwargs):
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        logger.error("No tenant associated with failed login attempt")
        return
    try:
        with tenant_context(tenant):
            ip_address = request.META.get('REMOTE_ADDR', 'unknown')
            username = credentials.get('username', 'unknown')
            FailedLogin.objects.create(
                tenant=tenant,
                ip_address=ip_address,
                username=username,
                attempts=1,  # Increment if tracking multiple attempts per IP/username
                status='failed'
            )
            logger.info(f"[{tenant.schema_name}] Recorded failed login for username {username} from IP {ip_address}")
    except Exception as e:
        logger.error(f"[{tenant.schema_name}] Error recording failed login: {str(e)}", exc_info=True)
