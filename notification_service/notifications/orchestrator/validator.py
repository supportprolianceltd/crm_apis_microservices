from notifications.utils.exceptions import TenantValidationError, ChannelNotConfiguredError
from notifications.models import TenantCredentials
from notifications.utils.context import get_tenant_context

def validate_tenant_and_channel(tenant_id: str, channel: str):
    context = get_tenant_context(None)  # In view, pass request
    if context['tenant_id'] != tenant_id:
        raise TenantValidationError("Tenant mismatch.")
    
    creds = TenantCredentials.objects.filter(tenant_id=tenant_id, channel=channel, is_active=True).first()
    if not creds:
        raise ChannelNotConfiguredError(f"Channel {channel} not configured for tenant {tenant_id}.")
    
    return creds.credentials