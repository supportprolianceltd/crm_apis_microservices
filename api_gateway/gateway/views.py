import os
import time
import logging
import requests
import re
import uuid
from collections import defaultdict
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django_ratelimit.decorators import ratelimit
from django.utils.encoding import force_str
from urllib.parse import urljoin
import urllib3
import asyncio
import websockets
import json
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

# Disable SSL warnings for internal services
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger('gateway')

# Global session with enhanced connection pooling
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(
    pool_connections=100,
    pool_maxsize=100,
    max_retries=3,
    pool_block=False
)
session.mount('http://', adapter)
session.mount('https://', adapter)


class GatewayCircuitBreaker:
    """
    Enhanced Circuit Breaker for gateway service calls with state management
    """
    def __init__(self, failure_threshold=5, recovery_timeout=60, half_open_timeout=30):
        self.services = defaultdict(lambda: {
            'failure_count': 0,
            'last_failure_time': 0,
            'state': 'CLOSED',  # CLOSED, OPEN, HALF_OPEN
            'half_open_attempts': 0,
            'total_requests': 0,
            'failed_requests': 0
        })
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_timeout = half_open_timeout
        self.half_open_max_attempts = 3
        
    def is_service_available(self, service_name):
        """
        Check if service is available based on circuit breaker state
        """
        service = self.services[service_name]
        service['total_requests'] += 1
        
        if service['state'] == 'OPEN':
            # Check if recovery timeout has passed
            time_since_failure = time.time() - service['last_failure_time']
            if time_since_failure > self.recovery_timeout:
                service['state'] = 'HALF_OPEN'
                service['half_open_attempts'] = 0
                logger.info(f"Circuit breaker for {service_name} moved to HALF_OPEN state")
                return True
            else:
                logger.warning(f"Circuit breaker OPEN for {service_name}, time until retry: {self.recovery_timeout - time_since_failure:.1f}s")
                return False
                
        elif service['state'] == 'HALF_OPEN':
            if service['half_open_attempts'] >= self.half_open_max_attempts:
                service['state'] = 'OPEN'
                service['last_failure_time'] = time.time()
                logger.warning(f"Circuit breaker for {service_name} moved back to OPEN state after {self.half_open_max_attempts} half-open attempts")
                return False
            return True
            
        return True  # CLOSED state
        
    def record_success(self, service_name):
        """
        Record successful service call
        """
        service = self.services[service_name]
        
        if service['state'] == 'HALF_OPEN':
            service['state'] = 'CLOSED'
            service['failure_count'] = 0
            service['half_open_attempts'] = 0
            logger.info(f"Circuit breaker for {service_name} reset to CLOSED state after successful call")
        elif service['state'] == 'CLOSED':
            service['failure_count'] = max(0, service['failure_count'] - 1)  # Gradually recover
            
    def record_failure(self, service_name):
        """
        Record failed service call
        """
        service = self.services[service_name]
        service['failure_count'] += 1
        service['failed_requests'] += 1
        service['last_failure_time'] = time.time()
        
        if service['state'] == 'HALF_OPEN':
            service['half_open_attempts'] += 1
            logger.warning(f"Half-open attempt failed for {service_name} ({service['half_open_attempts']}/{self.half_open_max_attempts})")
            
        if service['failure_count'] >= self.failure_threshold:
            service['state'] = 'OPEN'
            logger.error(f"Circuit breaker OPENED for {service_name} after {service['failure_count']} failures")
            
    def get_service_stats(self, service_name):
        """
        Get statistics for a service
        """
        service = self.services[service_name]
        success_rate = ((service['total_requests'] - service['failed_requests']) / service['total_requests'] * 100) if service['total_requests'] > 0 else 100
        return {
            'state': service['state'],
            'failure_count': service['failure_count'],
            'total_requests': service['total_requests'],
            'failed_requests': service['failed_requests'],
            'success_rate': round(success_rate, 2),
            'last_failure_time': service['last_failure_time'],
            'half_open_attempts': service.get('half_open_attempts', 0)
        }

    def reset_service(self, service_name):
        """
        Manually reset circuit breaker for a service
        """
        if service_name in self.services:
            service = self.services[service_name]
            service.update({
                'failure_count': 0,
                'last_failure_time': 0,
                'state': 'CLOSED',
                'half_open_attempts': 0
            })
            logger.info(f"Circuit breaker manually reset for {service_name}")
            return True
        return False


# Global circuit breaker instance
circuit_breaker = GatewayCircuitBreaker(
    failure_threshold=3,  # Reduced for faster failure detection
    recovery_timeout=120,  # 2 minutes recovery time
    half_open_timeout=30
)


@csrf_exempt
@ratelimit(key='ip', rate='100/m', method='POST', block=True)
@ratelimit(key='ip', rate='200/m', method='GET', block=True)
def api_gateway_view(request, path):
    """
    Main API Gateway view that routes requests to appropriate microservices
    """
    try:
        # Generate request ID for gateway headers
        request_id = f"gateway_{uuid.uuid4().hex[:8]}"
        logger.info(f"[{request_id}] Gateway received request: {request.method} /api/{path}")
        
        # ======================== REQUEST PARSING ========================
        segments = path.strip('/').split('/')
        if not segments:
            return JsonResponse({"error": "Invalid path"}, status=400)

        # ======================== MICROSERVICE ROUTING ========================
        prefix = segments[0]
        sub_path = '/'.join(segments[1:]) if len(segments) > 1 else ''
        
        # Special handling for notifications service
        if prefix == "notifications":
            base_url = settings.MICROSERVICE_URLS.get("notifications")
            if not base_url:
                logger.error(f"[{request_id}] Notifications service URL not configured")
                return JsonResponse({"error": "Notifications service not available"}, status=500)
                
            forward_url = f"{base_url}/{sub_path}" if sub_path else base_url
            service_name = "notifications"
        else:
            # Get base URL for the microservice - FIXED ROUTING LOGIC
            base_url = settings.MICROSERVICE_URLS.get(prefix)
            
            # If not found, check if it's an auth route
            if not base_url and prefix in getattr(settings, 'AUTH_ROUTES', []):
                base_url = settings.MICROSERVICE_URLS.get("auth_service")
                service_name = "auth_service"
            elif not base_url:
                logger.error(f"[{request_id}] No route found for prefix: {prefix}")
                return JsonResponse({"error": f"No route found for /api/{prefix}/"}, status=404)
            else:
                service_name = prefix

            if not base_url:
                logger.error(f"[{request_id}] Base URL not found for service: {service_name}")
                return JsonResponse({"error": f"Service {service_name} not configured"}, status=500)

            # Construct forward URL with proper trailing slash handling
            if sub_path:
                forward_url = f"{base_url}/api/{prefix}/{sub_path}"
            else:
                forward_url = f"{base_url}/api/{prefix}/"

            # Ensure POST/PUT/PATCH requests have trailing slashes
            if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
                forward_url = forward_url.rstrip('/') + '/'


        logger.info(f"[{request_id}] Forwarding to: {forward_url} (Service: {service_name})")

        # ======================== AUTHENTICATION HANDLING ========================
        is_public = any(public_path in path for public_path in getattr(settings, 'PUBLIC_PATHS', []))
        
        # Prepare headers for forwarding
        excluded_headers = {
            'host', 'content-length', 'content-encoding', 
            'transfer-encoding', 'connection', 'x-forwarded-for',
            'x-real-ip', 'x-forwarded-proto'
        }
        
        headers = {}
        for key, value in request.headers.items():
            key_lower = key.lower()
            if key_lower not in excluded_headers:
                # Remove authorization for public paths
                if is_public and key_lower == 'authorization':
                    continue
                headers[key] = value

        # Set proper Host header
        if base_url:
            try:
                host_without_scheme = base_url.split('//')[-1].split('/')[0]
                headers['Host'] = host_without_scheme
            except Exception as e:
                logger.warning(f"[{request_id}] Failed to parse host from base URL: {str(e)}")

        # ADD CRITICAL GATEWAY HEADERS
        headers['X-Gateway-Request-ID'] = request_id
        headers['X-Gateway-Service'] = service_name
        headers['X-Forwarded-For'] = request.META.get('REMOTE_ADDR', '')
        headers['X-Forwarded-Host'] = request.get_host()
        headers['X-Forwarded-Proto'] = 'https' if request.is_secure() else 'http'

        # ======================== REQUEST BODY HANDLING ========================
        method = request.method.upper()
        
        # Read request body
        try:
            body = request.body
        except Exception as e:
            logger.warning(f"[{request_id}] Error reading request body: {str(e)}")
            body = None

        # Debug logging for multipart requests
        content_type = request.META.get("CONTENT_TYPE", "")
        if content_type.startswith("multipart/form-data") and body:
            try:
                body_str = force_str(body[:10000])  # Peek first 10KB
                file_fields = re.findall(
                    r'Content-Disposition: form-data; name="([^"]+)"(?:; filename="([^"]+)")?', 
                    body_str
                )
                if file_fields:
                    file_info = [(f[0], f[1]) for f in file_fields if f[1]]
                    logger.info(f"[{request_id}] Multipart request with {len(file_info)} files: {file_info}")
            except Exception as e:
                logger.warning(f"[{request_id}] Could not parse multipart body: {str(e)}")

        # ======================== TIMEOUT CONFIGURATION ========================
        timeout_config = 300  # Increased default timeout to 5 minutes
        
        # Adjust timeout based on endpoint type
        if 'screen-resumes' in path or 'screen_resumes' in path:
            timeout_config = 600  # 10 minutes for resume screening
        elif 'parse-resume' in path or 'upload' in path or 'file' in path:
            timeout_config = 300   # 5 minutes for file processing
        elif service_name == 'notifications':
            timeout_config = 30   # Shorter for notifications
        elif service_name == 'auth_service':
            timeout_config = 60   # 1 minute for auth
        # New: Rostering-specific timeout (e.g., for polling/email tasks)
        elif service_name == 'rostering':
            timeout_config = 120  # 2 minutes for rostering operations

        # ======================== REQUEST FORWARDING ========================
        logger.info(f"[{request_id}] Forwarding request to: {forward_url} with timeout: {timeout_config}s")
        
        try:
            request_kwargs = {
                'method': method,
                'url': forward_url,
                'headers': headers,
                'params': request.GET,
                'timeout': timeout_config,
                'verify': False,  # Disable SSL verification for internal services
                'stream': True,   # Stream large responses
            }

            # Add body for methods that require it
            if method in ['POST', 'PUT', 'PATCH', 'DELETE'] and body:
                request_kwargs['data'] = body

            # Use global session for connection pooling
            response = session.request(**request_kwargs)

        except requests.exceptions.Timeout as e:
            logger.error(f"[{request_id}] Gateway timeout on /api/{path} after {timeout_config}s")
            return JsonResponse({
                "error": "Request timeout", 
                "details": f"Service took longer than {timeout_config} seconds to respond",
                "service": service_name,
                "request_id": request_id,
                "suggestion": "Please try again later or contact support if the problem persists"
            }, status=504)
            
        except requests.exceptions.ConnectionError as e:
            logger.error(f"[{request_id}] Connection error to {service_name} service: {str(e)}")
            return JsonResponse({
                "error": "Service unavailable",
                "details": f"Cannot connect to {service_name} service",
                "service": service_name,
                "request_id": request_id,
                "suggestion": "Service may be restarting. Please try again in a few moments."
            }, status=502)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"[{request_id}] Request error to {service_name} service: {str(e)}")
            return JsonResponse({
                "error": "Request failed",
                "details": str(e),
                "service": service_name,
                "request_id": request_id
            }, status=502)

        # ======================== RESPONSE HANDLING ========================
        logger.info(
            f"[{request_id}] Gateway forwarded: {method} /api/{path} -> {response.status_code} "
            f"(Service: {service_name})"
        )

        # Stream the response content to avoid memory issues
        response_content = b''
        for chunk in response.iter_content(chunk_size=8192):
            response_content += chunk

        # Prepare response headers
        excluded_response_headers = {
            'content-encoding', 'transfer-encoding', 'connection',
            'keep-alive', 'proxy-authenticate', 'proxy-authorization'
        }

        response_headers = {}
        for key, value in response.headers.items():
            key_lower = key.lower()
            if key_lower not in excluded_response_headers:
                response_headers[key] = value

        # Add gateway headers to response
        response_headers['X-Gateway-Request-ID'] = request_id
        response_headers['X-Gateway-Service'] = service_name

        # Special handling for Swagger UI static assets
        if service_name == 'rostering' and 'docs' in path:
            # Ensure proper content type for Swagger UI assets
            content_type = response.headers.get('Content-Type', '')
            if not content_type:
                if path.endswith('.css'):
                    response_headers['Content-Type'] = 'text/css'
                elif path.endswith('.js'):
                    response_headers['Content-Type'] = 'application/javascript'
                elif path.endswith('.html') or path.endswith('.htm'):
                    response_headers['Content-Type'] = 'text/html'
                elif path.endswith('.json'):
                    response_headers['Content-Type'] = 'application/json'
                elif path.endswith('.png'):
                    response_headers['Content-Type'] = 'image/png'
                elif path.endswith('.ico'):
                    response_headers['Content-Type'] = 'image/x-icon'

        # Create Django response
        django_response = HttpResponse(
            content=response_content,
            status=response.status_code,
            content_type=response.headers.get('Content-Type', 'application/json')
        )
        
        # Set headers
        for key, value in response_headers.items():
            django_response[key] = value

        return django_response

    except Exception as e:
        logger.exception(f"Unexpected gateway error on /api/{path}: {str(e)}")
        return JsonResponse({
            "error": "Internal gateway error",
            "details": str(e),
            "suggestion": "An unexpected error occurred in the gateway. Please contact support."
        }, status=500)




# @csrf_exempt
# @ratelimit(key='ip', rate='100/m', method='POST', block=True)
# @ratelimit(key='ip', rate='200/m', method='GET', block=True)
# def api_gateway_view(request, path):
#     """
#     Main API Gateway view that routes requests to appropriate microservices
#     """
#     try:
#         # Generate request ID for gateway headers
#         request_id = f"gateway_{uuid.uuid4().hex[:8]}"
#         logger.info(f"[{request_id}] Gateway received request: {request.method} /api/{path}")
        
#         # ======================== REQUEST PARSING ========================
#         segments = path.strip('/').split('/')
#         if not segments:
#             return JsonResponse({"error": "Invalid path"}, status=400)

#         # ======================== MICROSERVICE ROUTING ========================
#         prefix = segments[0]
#         sub_path = '/'.join(segments[1:]) if len(segments) > 1 else ''
        
#         # Special handling for notifications service
#         if prefix == "notifications":
#             base_url = settings.MICROSERVICE_URLS.get("notifications")
#             if not base_url:
#                 logger.error(f"[{request_id}] Notifications service URL not configured")
#                 return JsonResponse({"error": "Notifications service not available"}, status=500)
                
#             forward_url = f"{base_url}/{sub_path}" if sub_path else base_url
#             service_name = "notifications"
#         else:
#             # Get base URL for the microservice - FIXED ROUTING LOGIC
#             base_url = settings.MICROSERVICE_URLS.get(prefix)
            
#             # If not found, check if it's an auth route
#             if not base_url and prefix in getattr(settings, 'AUTH_ROUTES', []):
#                 base_url = settings.MICROSERVICE_URLS.get("auth_service")
#                 service_name = "auth_service"
#             elif not base_url:
#                 logger.error(f"[{request_id}] No route found for prefix: {prefix}")
#                 return JsonResponse({"error": f"No route found for /api/{prefix}/"}, status=404)
#             else:
#                 service_name = prefix

#             if not base_url:
#                 logger.error(f"[{request_id}] Base URL not found for service: {service_name}")
#                 return JsonResponse({"error": f"Service {service_name} not configured"}, status=500)

#             # Construct forward URL with proper trailing slash handling - ROSTERING-SPECIFIC
#             if prefix == 'rostering':
#                 if sub_path:
#                     forward_url = f"{base_url}/api/rostering/{sub_path}"
#                 else:
#                     forward_url = f"{base_url}/api/rostering/"
#             else:
#                 if sub_path:
#                     forward_url = f"{base_url}/api/{prefix}/{sub_path}"
#                 else:
#                     forward_url = f"{base_url}/api/{prefix}/"

#             # FIXED: Do NOT force trailing slash for POST/etc. - let the service handle it
#             # (Rostering expects exact match without extra trailing slash on the endpoint)

#         logger.info(f"[{request_id}] Forwarding to: {forward_url} (Service: {service_name})")

#         # ======================== AUTHENTICATION HANDLING ========================
#         is_public = any(public_path in path for public_path in getattr(settings, 'PUBLIC_PATHS', []))
        
#         # Prepare headers for forwarding
#         excluded_headers = {
#             'host', 'content-length', 'content-encoding', 
#             'transfer-encoding', 'connection', 'x-forwarded-for',
#             'x-real-ip', 'x-forwarded-proto'
#         }
        
#         headers = {}
#         for key, value in request.headers.items():
#             key_lower = key.lower()
#             if key_lower not in excluded_headers:
#                 # Remove authorization for public paths
#                 if is_public and key_lower == 'authorization':
#                     continue
#                 headers[key] = value

#         # Set proper Host header
#         if base_url:
#             try:
#                 host_without_scheme = base_url.split('//')[-1].split('/')[0]
#                 headers['Host'] = host_without_scheme
#             except Exception as e:
#                 logger.warning(f"[{request_id}] Failed to parse host from base URL: {str(e)}")

#         # ADD CRITICAL GATEWAY HEADERS
#         headers['X-Gateway-Request-ID'] = request_id
#         headers['X-Gateway-Service'] = service_name
#         headers['X-Forwarded-For'] = request.META.get('REMOTE_ADDR', '')
#         headers['X-Forwarded-Host'] = request.get_host()
#         headers['X-Forwarded-Proto'] = 'https' if request.is_secure() else 'http'

#         # ======================== REQUEST BODY HANDLING ========================
#         method = request.method.upper()
        
#         # Read request body
#         try:
#             body = request.body
#         except Exception as e:
#             logger.warning(f"[{request_id}] Error reading request body: {str(e)}")
#             body = None

#         # Debug logging for multipart requests
#         content_type = request.META.get("CONTENT_TYPE", "")
#         if content_type.startswith("multipart/form-data") and body:
#             try:
#                 body_str = force_str(body[:10000])  # Peek first 10KB
#                 file_fields = re.findall(
#                     r'Content-Disposition: form-data; name="([^"]+)"(?:; filename="([^"]+)")?', 
#                     body_str
#                 )
#                 if file_fields:
#                     file_info = [(f[0], f[1]) for f in file_fields if f[1]]
#                     logger.info(f"[{request_id}] Multipart request with {len(file_info)} files: {file_info}")
#             except Exception as e:
#                 logger.warning(f"[{request_id}] Could not parse multipart body: {str(e)}")

#         # ======================== TIMEOUT CONFIGURATION ========================
#         timeout_config = 300  # Increased default timeout to 5 minutes
        
#         # Adjust timeout based on endpoint type
#         if 'screen-resumes' in path or 'screen_resumes' in path:
#             timeout_config = 600  # 10 minutes for resume screening
#         elif 'parse-resume' in path or 'upload' in path or 'file' in path:
#             timeout_config = 300   # 5 minutes for file processing
#         elif service_name == 'notifications':
#             timeout_config = 30   # Shorter for notifications
#         elif service_name == 'auth_service':
#             timeout_config = 60   # 1 minute for auth
#         # New: Rostering-specific timeout (e.g., for polling/email tasks)
#         elif service_name == 'rostering':
#             timeout_config = 120  # 2 minutes for rostering operations

#         # ======================== REQUEST FORWARDING ========================
#         logger.info(f"[{request_id}] Forwarding request to: {forward_url} with timeout: {timeout_config}s")
        
#         try:
#             request_kwargs = {
#                 'method': method,
#                 'url': forward_url,
#                 'headers': headers,
#                 'params': request.GET,
#                 'timeout': timeout_config,
#                 'verify': False,  # Disable SSL verification for internal services
#                 'stream': True,   # Stream large responses
#             }

#             # Add body for methods that require it
#             if method in ['POST', 'PUT', 'PATCH', 'DELETE'] and body:
#                 request_kwargs['data'] = body

#             # Use global session for connection pooling
#             response = session.request(**request_kwargs)

#         except requests.exceptions.Timeout as e:
#             logger.error(f"[{request_id}] Gateway timeout on /api/{path} after {timeout_config}s")
#             return JsonResponse({
#                 "error": "Request timeout", 
#                 "details": f"Service took longer than {timeout_config} seconds to respond",
#                 "service": service_name,
#                 "request_id": request_id,
#                 "suggestion": "Please try again later or contact support if the problem persists"
#             }, status=504)
            
#         except requests.exceptions.ConnectionError as e:
#             logger.error(f"[{request_id}] Connection error to {service_name} service: {str(e)}")
#             return JsonResponse({
#                 "error": "Service unavailable",
#                 "details": f"Cannot connect to {service_name} service",
#                 "service": service_name,
#                 "request_id": request_id,
#                 "suggestion": "Service may be restarting. Please try again in a few moments."
#             }, status=502)
            
#         except requests.exceptions.RequestException as e:
#             logger.error(f"[{request_id}] Request error to {service_name} service: {str(e)}")
#             return JsonResponse({
#                 "error": "Request failed",
#                 "details": str(e),
#                 "service": service_name,
#                 "request_id": request_id
#             }, status=502)

#         # ======================== RESPONSE HANDLING ========================
#         logger.info(
#             f"[{request_id}] Gateway forwarded: {method} /api/{path} -> {response.status_code} "
#             f"(Service: {service_name})"
#         )

#         # Stream the response content to avoid memory issues
#         response_content = b''
#         for chunk in response.iter_content(chunk_size=8192):
#             response_content += chunk

#         # Prepare response headers
#         excluded_response_headers = {
#             'content-encoding', 'transfer-encoding', 'connection',
#             'keep-alive', 'proxy-authenticate', 'proxy-authorization'
#         }
        
#         response_headers = {}
#         for key, value in response.headers.items():
#             key_lower = key.lower()
#             if key_lower not in excluded_response_headers:
#                 response_headers[key] = value

#         # Add gateway headers to response
#         response_headers['X-Gateway-Request-ID'] = request_id
#         response_headers['X-Gateway-Service'] = service_name

#         # Create Django response
#         django_response = HttpResponse(
#             content=response_content,
#             status=response.status_code,
#             content_type=response.headers.get('Content-Type', 'application/json')
#         )
        
#         # Set headers
#         for key, value in response_headers.items():
#             django_response[key] = value

#         return django_response

#     except Exception as e:
#         logger.exception(f"Unexpected gateway error on /api/{path}: {str(e)}")
#         return JsonResponse({
#             "error": "Internal gateway error",
#             "details": str(e),
#             "suggestion": "An unexpected error occurred in the gateway. Please contact support."
#         }, status=500)



# @csrf_exempt
# @ratelimit(key='ip', rate='100/m', method='POST', block=True)
# @ratelimit(key='ip', rate='200/m', method='GET', block=True)
# def api_gateway_view(request, path):
#     """
#     Main API Gateway view that routes requests to appropriate microservices
#     """
#     try:
#         # Generate request ID for gateway headers
#         request_id = f"gateway_{uuid.uuid4().hex[:8]}"
#         logger.info(f"[{request_id}] Gateway received request: {request.method} /api/{path}")
        
#         # ======================== REQUEST PARSING ========================
#         segments = path.strip('/').split('/')
#         if not segments:
#             return JsonResponse({"error": "Invalid path"}, status=400)

#         # ======================== MICROSERVICE ROUTING ========================
#         prefix = segments[0]
#         sub_path = '/'.join(segments[1:]) if len(segments) > 1 else ''
        
#         # Special handling for notifications service
#         if prefix == "notifications":
#             base_url = settings.MICROSERVICE_URLS.get("notifications")
#             if not base_url:
#                 logger.error(f"[{request_id}] Notifications service URL not configured")
#                 return JsonResponse({"error": "Notifications service not available"}, status=500)
                
#             forward_url = f"{base_url}/{sub_path}" if sub_path else base_url
#             service_name = "notifications"
#         else:
#             # Get base URL for the microservice - FIXED ROUTING LOGIC
#             base_url = settings.MICROSERVICE_URLS.get(prefix)
            
#             # If not found, check if it's an auth route
#             if not base_url and prefix in getattr(settings, 'AUTH_ROUTES', []):
#                 base_url = settings.MICROSERVICE_URLS.get("auth_service")
#                 service_name = "auth_service"
#             elif not base_url:
#                 logger.error(f"[{request_id}] No route found for prefix: {prefix}")
#                 return JsonResponse({"error": f"No route found for /api/{prefix}/"}, status=404)
#             else:
#                 service_name = prefix

#             if not base_url:
#                 logger.error(f"[{request_id}] Base URL not found for service: {service_name}")
#                 return JsonResponse({"error": f"Service {service_name} not configured"}, status=500)

#             # Construct forward URL with proper trailing slash handling - ROSTERING-SPECIFIC
#             if prefix == 'rostering':
#                 if sub_path:
#                     forward_url = f"{base_url}/api/rostering/{sub_path}"
#                 else:
#                     forward_url = f"{base_url}/api/rostering/"
#             else:
#                 if sub_path:
#                     forward_url = f"{base_url}/api/{prefix}/{sub_path}"
#                 else:
#                     forward_url = f"{base_url}/api/{prefix}/"

#             # FIXED: Do NOT force trailing slash for POST/etc. - let the service handle it
#             # (Rostering expects exact match without extra trailing slash on the endpoint)

#         logger.info(f"[{request_id}] Forwarding to: {forward_url} (Service: {service_name})")

#         # ======================== AUTHENTICATION HANDLING ========================
#         is_public = any(public_path in path for public_path in getattr(settings, 'PUBLIC_PATHS', []))
        
#         # Prepare headers for forwarding
#         excluded_headers = {
#             'host', 'content-length', 'content-encoding', 
#             'transfer-encoding', 'connection', 'x-forwarded-for',
#             'x-real-ip', 'x-forwarded-proto'
#         }
        
#         headers = {}
#         for key, value in request.headers.items():
#             key_lower = key.lower()
#             if key_lower not in excluded_headers:
#                 # Remove authorization for public paths
#                 if is_public and key_lower == 'authorization':
#                     continue
#                 headers[key] = value

#         # Set proper Host header
#         if base_url:
#             try:
#                 host_without_scheme = base_url.split('//')[-1].split('/')[0]
#                 headers['Host'] = host_without_scheme
#             except Exception as e:
#                 logger.warning(f"[{request_id}] Failed to parse host from base URL: {str(e)}")

#         # ADD CRITICAL GATEWAY HEADERS
#         headers['X-Gateway-Request-ID'] = request_id
#         headers['X-Gateway-Service'] = service_name
#         headers['X-Forwarded-For'] = request.META.get('REMOTE_ADDR', '')
#         headers['X-Forwarded-Host'] = request.get_host()
#         headers['X-Forwarded-Proto'] = 'https' if request.is_secure() else 'http'

#         # ======================== REQUEST BODY HANDLING ========================
#         method = request.method.upper()
        
#         # Read request body
#         try:
#             body = request.body
#         except Exception as e:
#             logger.warning(f"[{request_id}] Error reading request body: {str(e)}")
#             body = None

#         # Debug logging for multipart requests
#         content_type = request.META.get("CONTENT_TYPE", "")
#         if content_type.startswith("multipart/form-data") and body:
#             try:
#                 body_str = force_str(body[:10000])  # Peek first 10KB
#                 file_fields = re.findall(
#                     r'Content-Disposition: form-data; name="([^"]+)"(?:; filename="([^"]+)")?', 
#                     body_str
#                 )
#                 if file_fields:
#                     file_info = [(f[0], f[1]) for f in file_fields if f[1]]
#                     logger.info(f"[{request_id}] Multipart request with {len(file_info)} files: {file_info}")
#             except Exception as e:
#                 logger.warning(f"[{request_id}] Could not parse multipart body: {str(e)}")

#         # ======================== TIMEOUT CONFIGURATION ========================
#         timeout_config = 300  # Increased default timeout to 5 minutes
        
#         # Adjust timeout based on endpoint type
#         if 'screen-resumes' in path or 'screen_resumes' in path:
#             timeout_config = 600  # 10 minutes for resume screening
#         elif 'parse-resume' in path or 'upload' in path or 'file' in path:
#             timeout_config = 300   # 5 minutes for file processing
#         elif service_name == 'notifications':
#             timeout_config = 30   # Shorter for notifications
#         elif service_name == 'auth_service':
#             timeout_config = 60   # 1 minute for auth
#         # New: Rostering-specific timeout (e.g., for polling/email tasks)
#         elif service_name == 'rostering':
#             timeout_config = 120  # 2 minutes for rostering operations

#         # ======================== REQUEST FORWARDING ========================
#         logger.info(f"[{request_id}] Forwarding request to: {forward_url} with timeout: {timeout_config}s")
        
#         try:
#             request_kwargs = {
#                 'method': method,
#                 'url': forward_url,
#                 'headers': headers,
#                 'params': request.GET,
#                 'timeout': timeout_config,
#                 'verify': False,  # Disable SSL verification for internal services
#                 'stream': True,   # Stream large responses
#             }

#             # Add body for methods that require it
#             if method in ['POST', 'PUT', 'PATCH', 'DELETE'] and body:
#                 request_kwargs['data'] = body

#             # Use global session for connection pooling
#             response = session.request(**request_kwargs)

#         except requests.exceptions.Timeout as e:
#             logger.error(f"[{request_id}] Gateway timeout on /api/{path} after {timeout_config}s")
#             return JsonResponse({
#                 "error": "Request timeout", 
#                 "details": f"Service took longer than {timeout_config} seconds to respond",
#                 "service": service_name,
#                 "request_id": request_id,
#                 "suggestion": "Please try again later or contact support if the problem persists"
#             }, status=504)
            
#         except requests.exceptions.ConnectionError as e:
#             logger.error(f"[{request_id}] Connection error to {service_name} service: {str(e)}")
#             return JsonResponse({
#                 "error": "Service unavailable",
#                 "details": f"Cannot connect to {service_name} service",
#                 "service": service_name,
#                 "request_id": request_id,
#                 "suggestion": "Service may be restarting. Please try again in a few moments."
#             }, status=502)
            
#         except requests.exceptions.RequestException as e:
#             logger.error(f"[{request_id}] Request error to {service_name} service: {str(e)}")
#             return JsonResponse({
#                 "error": "Request failed",
#                 "details": str(e),
#                 "service": service_name,
#                 "request_id": request_id
#             }, status=502)

#         # ======================== RESPONSE HANDLING ========================
#         logger.info(
#             f"[{request_id}] Gateway forwarded: {method} /api/{path} -> {response.status_code} "
#             f"(Service: {service_name})"
#         )

#         # FIXED: Handle decompression for compressed responses
#         content_encoding = response.headers.get('content-encoding', '').lower()
#         response_content = b''
#         for chunk in response.iter_content(chunk_size=8192):
#             response_content += chunk

#         if content_encoding == 'gzip':
#             try:
#                 buffer = io.BytesIO(response_content)
#                 with gzip.GzipFile(fileobj=buffer) as gz:
#                     response_content = gz.read()
#                 logger.info(f"[{request_id}] Decompressed gzip response")
#             except Exception as decomp_err:
#                 logger.warning(f"[{request_id}] Failed to decompress gzip: {str(decomp_err)}")
#         elif content_encoding == 'deflate':
#             # Simple deflate (without zlib header)
#             try:
#                 response_content = gzip.decompress(response_content)
#                 logger.info(f"[{request_id}] Decompressed deflate response")
#             except Exception as decomp_err:
#                 logger.warning(f"[{request_id}] Failed to decompress deflate: {str(decomp_err)}")

#         # Prepare response headers
#         excluded_response_headers = {
#             'content-encoding', 'transfer-encoding', 'connection',
#             'keep-alive', 'proxy-authenticate', 'proxy-authorization'
#         }
        
#         response_headers = {}
#         for key, value in response.headers.items():
#             key_lower = key.lower()
#             if key_lower not in excluded_response_headers:
#                 response_headers[key] = value

#         # Add gateway headers to response
#         response_headers['X-Gateway-Request-ID'] = request_id
#         response_headers['X-Gateway-Service'] = service_name

#         # Create Django response
#         django_response = HttpResponse(
#             content=response_content,
#             status=response.status_code,
#             content_type=response.headers.get('Content-Type', 'application/json')
#         )
        
#         # Set headers
#         for key, value in response_headers.items():
#             django_response[key] = value

#         return django_response

#     except Exception as e:
#         logger.exception(f"Unexpected gateway error on /api/{path}: {str(e)}")
#         return JsonResponse({
#             "error": "Internal gateway error",
#             "details": str(e),
#             "suggestion": "An unexpected error occurred in the gateway. Please contact support."
#         }, status=500)


@csrf_exempt
def health_check(request):
    """
    Comprehensive health check endpoint for the API Gateway
    """
    health_data = {
        "status": "healthy",
        "service": "api-gateway",
        "timestamp": time.time(),
        "version": "1.0.0",
        "dependencies": {}
    }
    
    status_code = 200
    
    try:
        # Check circuit breaker status for all services
        circuit_breaker_status = {}
        for service_name in getattr(settings, 'MICROSERVICE_URLS', {}).keys():
            circuit_breaker_status[service_name] = circuit_breaker.get_service_stats(service_name)
            if circuit_breaker_status[service_name]['state'] == 'OPEN':
                health_data["status"] = "degraded"
        
        health_data["circuit_breaker"] = circuit_breaker_status
        
        # Check database connection (if using database)
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            health_data["dependencies"]["database"] = "connected"
        except Exception as e:
            health_data["dependencies"]["database"] = f"error: {str(e)}"
            health_data["status"] = "unhealthy"
            status_code = 503
            
        # Check if we can resolve internal services
        for service_name, service_url in getattr(settings, 'MICROSERVICE_URLS', {}).items():
            try:
                test_response = session.head(service_url, timeout=5, verify=False)
                health_data["dependencies"][service_name] = "reachable"
            except Exception as e:
                health_data["dependencies"][service_name] = f"unreachable: {str(e)}"
                health_data["status"] = "degraded"
                
    except Exception as e:
        health_data["status"] = "unhealthy"
        health_data["error"] = str(e)
        status_code = 503
        
    return JsonResponse(health_data, status=status_code)


@csrf_exempt
def circuit_breaker_status(request):
    """
    Endpoint to check circuit breaker status for all services
    """
    try:
        status_data = {
            "timestamp": time.time(),
            "services": {}
        }
        
        for service_name in getattr(settings, 'MICROSERVICE_URLS', {}).keys():
            status_data["services"][service_name] = circuit_breaker.get_service_stats(service_name)
            
        return JsonResponse(status_data)
        
    except Exception as e:
        logger.error(f"Error getting circuit breaker status: {str(e)}")
        return JsonResponse({
            "error": "Failed to get circuit breaker status",
            "details": str(e)
        }, status=500)


@csrf_exempt
def reset_circuit_breaker(request, service_name):
    """
    Endpoint to manually reset circuit breaker for a service (for admin use)
    """
    try:
        if service_name not in getattr(settings, 'MICROSERVICE_URLS', {}):
            return JsonResponse({
                "error": "Service not found",
                "details": f"Service {service_name} not configured"
            }, status=404)
            
        # Reset the circuit breaker for the specified service
        success = circuit_breaker.reset_service(service_name)
        
        if success:
            return JsonResponse({
                "message": f"Circuit breaker reset for {service_name}",
                "service": service_name,
                "status": "reset"
            })
        else:
            return JsonResponse({
                "error": f"Failed to reset circuit breaker for {service_name}",
                "details": "Service not found in circuit breaker"
            }, status=404)
        
    except Exception as e:
        logger.error(f"Error resetting circuit breaker for {service_name}: {str(e)}")
        return JsonResponse({
            "error": f"Failed to reset circuit breaker for {service_name}",
            "details": str(e)
        }, status=500)


@csrf_exempt
def gateway_metrics(request):
    """
    Endpoint to expose gateway metrics for monitoring
    """
    try:
        metrics_data = {
            "timestamp": time.time(),
            "requests_processed": 0,
            "services": {}
        }
        
        total_requests = 0
        total_failures = 0
        
        for service_name in getattr(settings, 'MICROSERVICE_URLS', {}).keys():
            stats = circuit_breaker.get_service_stats(service_name)
            metrics_data["services"][service_name] = stats
            total_requests += stats['total_requests']
            total_failures += stats['failed_requests']
            
        metrics_data["requests_processed"] = total_requests
        metrics_data["error_rate"] = round((total_failures / total_requests * 100) if total_requests > 0 else 0, 2)
        
        return JsonResponse(metrics_data)
        
    except Exception as e:
        logger.error(f"Error generating gateway metrics: {str(e)}")
        return JsonResponse({
            "error": "Failed to generate metrics",
            "details": str(e)
        }, status=500)


@csrf_exempt
def gateway_info(request):
    """
    Endpoint to get gateway information and configuration
    """
    try:
        info_data = {
            "service": "api-gateway",
            "version": "1.0.0",
            "timestamp": time.time(),
            "features": {
                "circuit_breaker": True,
                "rate_limiting": True,
                "connection_pooling": True,
                "request_tracking": True
            },
            "configuration": {
                "microservices": list(getattr(settings, 'MICROSERVICE_URLS', {}).keys()),
                "public_paths": getattr(settings, 'PUBLIC_PATHS', []),
                "timeouts": getattr(settings, 'GATEWAY_TIMEOUTS', {})
            }
        }
        return JsonResponse(info_data)
    except Exception as e:
        logger.error(f"Error getting gateway info: {str(e)}")
        return JsonResponse({
            "error": "Failed to get gateway information",
            "details": str(e)
        }, status=500)


@csrf_exempt
def service_discovery(request):
    """
    Endpoint to discover available microservices and their status
    """
    try:
        discovery_data = {
            "timestamp": time.time(),
            "services": {}
        }
        
        for service_name, service_url in getattr(settings, 'MICROSERVICE_URLS', {}).items():
            service_info = {
                "url": service_url,
                "circuit_breaker": circuit_breaker.get_service_stats(service_name)
            }
            
            # Try to ping the service
            try:
                ping_start = time.time()
                response = session.head(service_url, timeout=5, verify=False)
                service_info["reachable"] = True
                service_info["response_time"] = round((time.time() - ping_start) * 1000, 2)  # ms
            except Exception as e:
                service_info["reachable"] = False
                service_info["error"] = str(e)
                
            discovery_data["services"][service_name] = service_info
            
        return JsonResponse(discovery_data)
        
    except Exception as e:
        logger.error(f"Error in service discovery: {str(e)}")
        return JsonResponse({
            "error": "Failed to perform service discovery",
            "details": str(e)
        }, status=500)


@csrf_exempt
def request_logs(request):
    """
    Endpoint to get recent gateway request logs (for debugging)
    Note: This is a simplified version - in production, we will use proper log aggregation
    """
    try:
        # This would typically connect to your log storage system
        # For now, return basic statistics
        log_data = {
            "timestamp": time.time(),
            "recent_activity": {
                "total_services": len(getattr(settings, 'MICROSERVICE_URLS', {})),
                "circuit_breaker_stats": {}
            }
        }
        
        for service_name in getattr(settings, 'MICROSERVICE_URLS', {}).keys():
            stats = circuit_breaker.get_service_stats(service_name)
            log_data["recent_activity"]["circuit_breaker_stats"][service_name] = {
                "state": stats['state'],
                "success_rate": stats['success_rate'],
                "total_requests": stats['total_requests']
            }
            
        return JsonResponse(log_data)
        
    except Exception as e:
        logger.error(f"Error getting request logs: {str(e)}")
        return JsonResponse({
            "error": "Failed to get request logs",
            "details": str(e)
        }, status=500)


@csrf_exempt
@ratelimit(key='ip', rate='10/m', method='POST', block=True)
def emergency_shutdown(request):
    """
    Emergency endpoint to temporarily disable gateway or specific services
    (Admin use only - should be protected with additional authentication)
    """
    if request.method != 'POST':
        return JsonResponse({
            "error": "Method not allowed",
            "details": "Only POST method is supported"
        }, status=405)
        
    try:
        service_name = request.POST.get('service')
        action = request.POST.get('action')  # 'disable' or 'enable'
        
        if not service_name or not action:
            return JsonResponse({
                "error": "Missing parameters",
                "details": "Both 'service' and 'action' parameters are required"
            }, status=400)
            
        if service_name not in getattr(settings, 'MICROSERVICE_URLS', {}):
            return JsonResponse({
                "error": "Service not found",
                "details": f"Service {service_name} not configured"
            }, status=404)
            
        if action == 'disable':
            # Force circuit breaker to open
            circuit_breaker.record_failure(service_name)
            # Manually set to OPEN state
            service_data = circuit_breaker.services[service_name]
            service_data['state'] = 'OPEN'
            service_data['failure_count'] = circuit_breaker.failure_threshold
            
            logger.critical(f"Emergency shutdown: Service {service_name} manually disabled")
            
            return JsonResponse({
                "message": f"Service {service_name} manually disabled",
                "action": "disabled",
                "service": service_name
            })
            
        elif action == 'enable':
            # Reset circuit breaker
            circuit_breaker.reset_service(service_name)
            
            logger.critical(f"Emergency shutdown: Service {service_name} manually enabled")
            
            return JsonResponse({
                "message": f"Service {service_name} manually enabled",
                "action": "enabled",
                "service": service_name
            })
        else:
            return JsonResponse({
                "error": "Invalid action",
                "details": "Action must be either 'disable' or 'enable'"
            }, status=400)
            
    except Exception as e:
        logger.error(f"Error in emergency shutdown: {str(e)}")
        return JsonResponse({
            "error": "Emergency shutdown failed",
            "details": str(e)
        }, status=500)


# Error handlers
def handle_404(request, exception=None):
    """
    Custom 404 handler for the gateway
    """
    return JsonResponse({
        "error": "Endpoint not found",
        "path": request.path,
        "method": request.method,
        "details": "The requested API endpoint does not exist",
        "suggestion": "Check the API documentation for available endpoints"
    }, status=404)


def handle_500(request):
    """
    Custom 500 handler for the gateway
    """
    return JsonResponse({
        "error": "Internal server error",
        "details": "An unexpected error occurred in the API gateway",
        "suggestion": "Please try again later or contact support"
    }, status=500)


def handle_403(request, exception=None):
    """
    Custom 403 handler for the gateway
    """
    return JsonResponse({
        "error": "Access forbidden",
        "details": "You don't have permission to access this resource",
        "suggestion": "Check your authentication credentials or contact administrator"
    }, status=403)


def handle_400(request, exception=None):
    """
    Custom 400 handler for the gateway
    """
    return JsonResponse({
        "error": "Bad request",
        "details": "The request could not be processed",
        "suggestion": "Check your request parameters and try again"
    }, status=400)


# Middleware-style functions for additional request processing
def add_security_headers(response):
    """
    Add security headers to all gateway responses
    """
    response['X-Content-Type-Options'] = 'nosniff'
    response['X-Frame-Options'] = 'DENY'
    response['X-XSS-Protection'] = '1; mode=block'
    response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response['Content-Security-Policy'] = "default-src 'self'"
    return response


def gateway_middleware(get_response):
    """
    Custom middleware for additional gateway functionality
    """
    def middleware(request):
        # Pre-process request
        start_time = time.time()
        
        # Add gateway timestamp header
        request.META['HTTP_X_GATEWAY_START_TIME'] = str(start_time)
        
        # Get response
        response = get_response(request)
        
        # Post-process response
        if hasattr(response, 'status_code') and response.status_code < 400:
            response = add_security_headers(response)
            
        # Add response time header
        response_time = time.time() - start_time
        response['X-Gateway-Processing-Time'] = f'{response_time:.3f}s'
        
        return response
    
    return middleware


@csrf_exempt
def socketio_gateway_view(request, path):
    """
    Socket.IO gateway view that proxies Socket.IO polling requests to messaging service
    """
    try:
        # Generate request ID for gateway headers
        request_id = f"gateway_socketio_{uuid.uuid4().hex[:8]}"
        logger.info(f"[{request_id}] Socket.IO Gateway received request: /socket.io/{path}")

        # Get messaging service URL
        messaging_url = settings.MICROSERVICE_URLS.get("messaging")
        if not messaging_url:
            logger.error(f"[{request_id}] Messaging service URL not configured")
            return JsonResponse({"error": "Messaging service not available"}, status=500)

        # Construct forward URL for Socket.IO polling
        if path:
            forward_url = f"{messaging_url}/socket.io/{path}"
        else:
            forward_url = f"{messaging_url}/socket.io/"

        logger.info(f"[{request_id}] Forwarding Socket.IO request to: {forward_url}")

        # Prepare headers for forwarding
        excluded_headers = {
            'host', 'content-length', 'content-encoding',
            'transfer-encoding', 'connection', 'x-forwarded-for',
            'x-real-ip', 'x-forwarded-proto'
        }

        headers = {}
        for key, value in request.headers.items():
            key_lower = key.lower()
            if key_lower not in excluded_headers:
                headers[key] = value

        # Set proper Host header
        try:
            host_without_scheme = messaging_url.split('//')[-1].split('/')[0]
            headers['Host'] = host_without_scheme
        except Exception as e:
            logger.warning(f"[{request_id}] Failed to parse host from messaging URL: {str(e)}")

        # Add gateway headers
        headers['X-Gateway-Request-ID'] = request_id
        headers['X-Gateway-Service'] = 'messaging'

        # Read request body
        try:
            body = request.body
        except Exception as e:
            logger.warning(f"[{request_id}] Error reading request body: {str(e)}")
            body = None

        # Forward the request to messaging service
        try:
            request_kwargs = {
                'method': request.method,
                'url': forward_url,
                'headers': headers,
                'params': request.GET,
                'timeout': 30,  # Shorter timeout for real-time requests
                'verify': False,
                'stream': True,
            }

            if request.method in ['POST', 'PUT', 'PATCH'] and body:
                request_kwargs['data'] = body

            response = session.request(**request_kwargs)

        except requests.exceptions.Timeout as e:
            logger.error(f"[{request_id}] Socket.IO gateway timeout: {str(e)}")
            return JsonResponse({"error": "Request timeout"}, status=504)

        except requests.exceptions.RequestException as e:
            logger.error(f"[{request_id}] Socket.IO gateway error: {str(e)}")
            return JsonResponse({"error": "Service unavailable"}, status=502)

        # Stream response content
        response_content = b''
        for chunk in response.iter_content(chunk_size=8192):
            response_content += chunk

        # Prepare response headers
        excluded_response_headers = {
            'content-encoding', 'transfer-encoding', 'connection',
            'keep-alive', 'proxy-authenticate', 'proxy-authorization'
        }

        response_headers = {}
        for key, value in response.headers.items():
            key_lower = key.lower()
            if key_lower not in excluded_response_headers:
                response_headers[key] = value

        # Add gateway headers
        response_headers['X-Gateway-Request-ID'] = request_id
        response_headers['X-Gateway-Service'] = 'messaging'

        # Create Django response
        django_response = HttpResponse(
            content=response_content,
            status=response.status_code,
            content_type=response.headers.get('Content-Type', 'application/json')
        )

        # Set headers
        for key, value in response_headers.items():
            django_response[key] = value

        logger.info(f"[{request_id}] Socket.IO gateway forwarded: {request.method} /socket.io/{path} -> {response.status_code}")
        return django_response

    except Exception as e:
        logger.exception(f"Unexpected Socket.IO gateway error on /socket.io/{path}: {str(e)}")
        return JsonResponse({
            "error": "Internal Socket.IO gateway error",
            "details": str(e),
        }, status=500)


@csrf_exempt
def websocket_gateway_view(request, path):
    """
    WebSocket gateway view that routes WebSocket connections to appropriate microservices
    """
    try:
        # Generate request ID for gateway headers
        request_id = f"gateway_ws_{uuid.uuid4().hex[:8]}"
        logger.info(f"[{request_id}] WebSocket Gateway received connection request: /ws/{path}")

        # Parse WebSocket path
        segments = path.strip('/').split('/')
        if not segments:
            return JsonResponse({"error": "Invalid WebSocket path"}, status=400)

        # Route WebSocket connections based on service
        prefix = segments[0]

        # For messaging service WebSocket connections
        if prefix == "messaging":
            messaging_url = settings.MICROSERVICE_URLS.get("messaging")
            if not messaging_url:
                logger.error(f"[{request_id}] Messaging service URL not configured")
                return JsonResponse({"error": "Messaging service not available"}, status=500)

            # Convert HTTP URL to WebSocket URL
            ws_url = messaging_url.replace('http://', 'ws://').replace('https://', 'wss://')

            # Construct WebSocket URL with remaining path
            sub_path = '/'.join(segments[1:]) if len(segments) > 1 else ''
            if sub_path:
                target_ws_url = f"{ws_url}/{sub_path}"
            else:
                target_ws_url = f"{ws_url}/"

            logger.info(f"[{request_id}] Routing WebSocket to: {target_ws_url}")

            # Return WebSocket routing information
            # In a real implementation, this would upgrade the connection
            # For now, return the routing info that frontend can use
            return JsonResponse({
                "websocket_url": target_ws_url,
                "service": "messaging",
                "request_id": request_id,
                "status": "routed"
            })

        else:
            logger.error(f"[{request_id}] No WebSocket route found for prefix: {prefix}")
            return JsonResponse({"error": f"No WebSocket route found for /{prefix}/"}, status=404)

    except Exception as e:
        logger.exception(f"Unexpected WebSocket gateway error on /ws/{path}: {str(e)}")
        return JsonResponse({
            "error": "Internal WebSocket gateway error",
            "details": str(e),
            "suggestion": "An unexpected error occurred in the WebSocket gateway."
        }, status=500)