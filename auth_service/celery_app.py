import os
from auth_service.celery_app import Celery
from django.conf import settings
from django.apps import current_app
from django_tenants.utils import tenant_context

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'auth_service.settings')

app = Celery('auth_service')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

@app.task(bind=True)
def log_global_activity(self, action, details, affected_tenant_id, ip_address=None, user_agent=None, success=True, performed_by_id=None, global_user_id=None):
    """Async task for global logging (public schema)."""
    with tenant_context(Tenant.objects.get(id=affected_tenant_id)):
        from users.models import GlobalActivity  # Avoid import cycle
        GlobalActivity.objects.create(
            action=action,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            performed_by_id=performed_by_id,
            global_user_id=global_user_id,
            affected_tenant_id=affected_tenant_id
        )

@app.task(bind=True)
def log_tenant_activity(self, action, details, tenant_id, user_id=None, performed_by_id=None, ip_address=None, user_agent=None, success=True):
    """Async task for tenant logging."""
    from django_tenants.utils import tenant_context
    from core.models import Tenant
    from users.models import UserActivity
    with tenant_context(Tenant.objects.get(id=tenant_id)):
        UserActivity.objects.create(
            action=action,
            details=details,
            user_id=user_id,
            performed_by_id=performed_by_id,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            tenant_id=tenant_id
        )

# In auth_service/__init__.py: default_app_config = 'auth_service.apps.AuthServiceConfig'
# In settings.py: Add CELERY_BROKER_URL = 'redis://redis:6379/0'
# CELERY_RESULT_BACKEND = 'redis://redis:6379/0'
# CELERY_ACCEPT_CONTENT = ['application/json']
# CELERY_TASK_SERIALIZER = 'json'
# CELERY_RESULT_SERIALIZER = 'json'
# CELERY_TIMEZONE = 'UTC'