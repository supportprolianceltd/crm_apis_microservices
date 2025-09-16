import logging
import requests
from django.conf import settings
import jwt
logger = logging.getLogger('tenant_utils')


def get_tenant_from_request(request):
    """
    Extracts tenant_id and tenant_schema from the JWT payload attached by middleware.
    """
    payload = getattr(request, 'jwt_payload', None)
    if not payload:
        # Fallback: try to decode from Authorization header if present
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith('Bearer '):
            return None, None
      
        try:
            token = auth_header.split(' ')[1]
            payload = jwt.decode(token, settings.SIMPLE_JWT['SIGNING_KEY'], algorithms=[settings.SIMPLE_JWT['ALGORITHM']])
        except Exception as e:
            logger.warning(f"Could not decode JWT: {e}")
            return None, None
    tenant_id = payload.get('tenant_id')
    tenant_schema = payload.get('tenant_schema')
    return tenant_id, tenant_schema


def resolve_tenant_from_unique_link(unique_link: str, request=None):
    """
    Resolves and returns the tenant and job requisition dicts based on the unique link,
    using JWT payload for tenant info if available.
    """
    if not unique_link or '-' not in unique_link:
        logger.warning("Missing or invalid unique_link format")
        return None, None

    # Use JWT payload if available
    tenant_id, tenant_schema = (None, None)
    if request:
        tenant_id, tenant_schema = get_tenant_from_request(request)
    if not tenant_schema:
        tenant_schema = unique_link.split('-')[0]

    # Fetch tenant details if needed (only if you need more than id/schema)
    tenant = None
    if tenant_id:
        tenant_resp = requests.get(
            f"{settings.AUTH_SERVICE_URL}/api/tenant/tenants/{tenant_id}/"
        )
        if tenant_resp.status_code == 200:
            tenant = tenant_resp.json()
    else:
        # fallback to schema_name query if no token
        tenant_resp = requests.get(
            f"{settings.AUTH_SERVICE_URL}/api/tenant/tenants/",
            params={"schema_name": tenant_schema}
        )
        if tenant_resp.status_code == 200:
            tenants = tenant_resp.json()
            if isinstance(tenants, list) and tenants:
                tenant = tenants[0]
            elif isinstance(tenants, dict) and tenants.get('results'):
                tenant = tenants['results'][0]

    if not tenant:
        logger.warning("Tenant not found")
        return None, None

    # Fetch job requisition by unique_link and tenant via API
    job_req_resp = requests.get(
        f"{settings.TALENT_ENGINE_URL}/api/talent-engine/requisitions/by-link/{unique_link}/",
        params={"tenant_id": tenant['id'], "publish_status": True}
    )
    if job_req_resp.status_code != 200:
        logger.warning(f"No published JobRequisition found for link: {unique_link}")
        return tenant, None
    job_requisition = job_req_resp.json()

    return tenant, job_requisition