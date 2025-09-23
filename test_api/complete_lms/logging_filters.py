import logging
from django_tenants.utils import get_tenant
from django.contrib.auth import get_user

class TenantContextFilter(logging.Filter):
    def filter(self, record):
        # Get the current tenant from django_tenants
        tenant = get_tenant()
        record.tenant_id = tenant.id if tenant else 'unknown'
        return True

class APIContextFilter(logging.Filter):
    def filter(self, record):
        # Expect request object to be passed in extra
        request = getattr(record, 'request', None)
        if request:
            record.user_id = request.user.id if hasattr(request.user, 'id') else 'anonymous'
            record.method = request.method
            record.path = request.path
            record.status = getattr(record, 'status', 'unknown')
        else:
            record.user_id = 'unknown'
            record.method = 'N/A'
            record.path = 'N/A'
            record.status = 'N/A'
        return True