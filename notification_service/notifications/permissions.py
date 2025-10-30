from rest_framework.permissions import BasePermission
from notifications.utils.context import get_tenant_context

class IsTenantOwner(BasePermission):
    def has_permission(self, request, view):
        context = get_tenant_context(request)
        return context['tenant_id'] is not None