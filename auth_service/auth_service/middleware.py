# auth_service/middleware.py
from django_tenants.middleware import TenantMainMiddleware
from django_tenants.utils import get_public_schema_name
from core.models import Domain, Tenant
from users.models import PasswordResetToken
from django.http import JsonResponse
from django.db import connection
import logging
import json
from rest_framework_simplejwt.authentication import JWTAuthentication

logger = logging.getLogger(__name__)

class CustomTenantMiddleware(TenantMainMiddleware):
    def process_request(self, request):
        try:
            host = request.get_host()
        except Exception as e:
            host = f"Invalid host: {e}"
        logger.info(f"Processing request: {request.method} {request.path}, Host: {host}")

        # Public paths (excluding /api/token/)
        public_paths = [
            '/api/docs/', '/api/schema/', '/api/token/refresh/',
            '/api/social/callback/', '/api/admin/create/',
            '/api/user/password/reset/', '/api/user/password/reset/confirm/',
            '/api/applications-engine/applications/parse-resume/application/autofil/',  # <-- Make this endpoint public
        ]

        if any(request.path.startswith(path) for path in public_paths):
            try:
                public_tenant = Tenant.objects.get(schema_name=get_public_schema_name())
                request.tenant = public_tenant
                connection.set_schema(public_tenant.schema_name)
                logger.info(f"Set public schema for path: {public_tenant.schema_name}")
                return
            except Tenant.DoesNotExist:
                logger.error("Public tenant does not exist")
                return JsonResponse({'error': 'Public tenant not configured'}, status=404)

        # Handle /api/token/ and /api/login/ for email-based tenant resolution
        if (request.path.startswith('/api/token/') or request.path.startswith('/api/login/') or request.path.startswith('/api/verify-2fa/')) and request.method == 'POST' :
            try:
                body = request.body.decode('utf-8') if request.body else '{}'
                logger.debug(f"Request body: {body}")
                data = json.loads(body)
                email = data.get('email')
                if not email:
                    logger.error("No email provided in login/token request")
                    return JsonResponse({'error': 'Email is required'}, status=400)

                email_domain = email.split('@')[1]
                logger.debug(f"Email domain: {email_domain}")
                domain = Domain.objects.filter(domain=email_domain).first()
                if not domain:
                    logger.error(f"No domain found for email domain: {email_domain}")
                    return JsonResponse({'error': f'No tenant found for email domain: {email_domain}'}, status=404)

                request.tenant = domain.tenant
                connection.set_schema(domain.tenant.schema_name)
                logger.info(f"Set tenant schema for email domain {email_domain}: {domain.tenant.schema_name}")
                with connection.cursor() as cursor:
                    cursor.execute("SHOW search_path;")
                    logger.debug(f"Current search_path: {cursor.fetchone()[0]}")
                return
            except (ValueError, KeyError, json.JSONDecodeError) as e:
                logger.error(f"Error processing login/token request: {str(e)}")
                return JsonResponse({'error': 'Invalid request format'}, status=400)

        # Handle password reset confirmation
        if request.path.startswith('/api/user/password/reset/confirm/') and request.method == 'POST':
            try:
                body = request.body.decode('utf-8') if request.body else '{}'
                data = json.loads(body)
                token = data.get('token')
                if not token:
                    logger.error("No token provided in password reset confirm request")
                    return JsonResponse({'error': 'Token is required'}, status=400)

                reset_token = PasswordResetToken.objects.filter(token=token).first()
                if not reset_token:
                    logger.error(f"Invalid or missing reset token: {token}")
                    return JsonResponse({'error': 'Invalid or missing token'}, status=400)

                request.tenant = reset_token.tenant
                connection.set_schema(reset_token.tenant.schema_name)
                logger.info(f"Set tenant schema for reset token: {reset_token.tenant.schema_name}")
                return
            except (ValueError, KeyError, json.JSONDecodeError) as e:
                logger.error(f"Error processing reset token request: {str(e)}")
                return JsonResponse({'error': 'Invalid request format'}, status=400)

        # Try JWT authentication
        try:
            auth = JWTAuthentication().authenticate(request)
            if auth:
                user, token = auth
                tenant_id = token.get('tenant_id')
                if tenant_id:
                    tenant = Tenant.objects.get(id=tenant_id)
                    request.tenant = tenant
                    connection.set_schema(tenant.schema_name)
                    logger.info(f"Set tenant schema from JWT: {tenant.schema_name}")
                    return
        except Exception as e:
            logger.debug(f"JWT authentication failed: {str(e)}")

        # Fallback to hostname with error handling for DisallowedHost
        try:
            hostname = request.get_host().split(':')[0]
            # Handle special cases like 0.0.0.0
            if hostname == '0.0.0.0':
                hostname = 'localhost'  # or your preferred default
        except Exception as e:
            logger.error(f"Error getting host: {str(e)}")
            hostname = 'localhost'  # fallback to default

        # Allow hostnames with hyphens (Django already allows this, but ensure domain lookup is robust)
        domain = Domain.objects.filter(domain=hostname).first()
        if domain:
            request.tenant = domain.tenant
            connection.set_schema(domain.tenant.schema_name)
            logger.info(f"Set tenant schema from hostname: {domain.tenant.schema_name}")
            return

        # Development fallback
        if hostname in ['127.0.0.1', 'localhost']:
            try:
                tenant = Tenant.objects.get(schema_name='example')
                request.tenant = tenant
                connection.set_schema(tenant.schema_name)
                logger.info(f"Set tenant schema for local development: {tenant.schema_name}")
                return
            except Tenant.DoesNotExist:
                logger.error("Development tenant 'example' does not exist")
                return JsonResponse({'error': 'Development tenant not configured'}, status=404)

        logger.error(f"No tenant found for hostname: {hostname}")
        return JsonResponse({'error': f'No tenant found for hostname: {hostname}'}, status=404)