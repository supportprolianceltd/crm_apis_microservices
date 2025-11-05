from django.http import HttpRequest

def get_tenant_context(request: HttpRequest):
    return {
        'tenant_id': getattr(request, 'tenant_id', None),
        'user_id': getattr(request.user, 'pk', None),
        'schema': getattr(request.user, 'tenant_schema', None),
    }