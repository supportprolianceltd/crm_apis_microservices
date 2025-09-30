import logging
import requests
import re
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django_ratelimit.decorators import ratelimit
from django.shortcuts import render
from django.utils.encoding import force_str
from datetime import datetime
import urllib3
from urllib.parse import urljoin

# Disable SSL warnings for internal services
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger('gateway')

# Global session with connection pooling
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(
    pool_connections=100,
    pool_maxsize=100,
    max_retries=3
)
session.mount('http://', adapter)
session.mount('https://', adapter)

@csrf_exempt
@ratelimit(key='ip', rate='100/m', method='POST', block=True)
@ratelimit(key='ip', rate='200/m', method='GET', block=True)
def api_gateway_view(request, path):
    """
    Main API Gateway view that routes requests to appropriate microservices
    """
    try:
        logger.info(f"Gateway received request: {request.method} /api/{path}")
        
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
            forward_url = f"{base_url}/{sub_path}" if sub_path else base_url
        else:
            # Get base URL for the microservice
            base_url = settings.MICROSERVICE_URLS.get(prefix)
            if not base_url:
                # Check if it's an auth route
                base_url = settings.MICROSERVICE_URLS.get(prefix, None)
                if not base_url:
                    logger.error(f"No route found for prefix: {prefix}")
                    return JsonResponse({"error": f"No route found for /api/{prefix}/"}, status=404)
            
            # Construct forward URL with proper trailing slash handling
            if sub_path:
                # Ensure the URL ends with a slash for POST requests to avoid APPEND_SLASH issues
                if request.method in ['POST', 'PUT', 'PATCH'] and not sub_path.endswith('/'):
                    sub_path = sub_path + '/'
                forward_url = f"{base_url}/api/{prefix}/{sub_path}"
            else:
                forward_url = f"{base_url}/api/{prefix}/"

        # Ensure forward_url has proper format
        forward_url = forward_url.rstrip('/') + '/' if request.method in ['POST', 'PUT', 'PATCH'] else forward_url

        logger.info(f"Forwarding to: {forward_url}")

        # ======================== AUTHENTICATION HANDLING ========================
        is_public = any(public_path in path for public_path in settings.PUBLIC_PATHS)
        
        # Prepare headers for forwarding
        excluded_headers = {
            'host', 'content-length', 'content-encoding', 
            'transfer-encoding', 'connection'
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
            host_without_scheme = base_url.split('//')[-1].split('/')[0]
            headers['Host'] = host_without_scheme

        # ======================== REQUEST BODY HANDLING ========================
        method = request.method.upper()
        
        # Read request body
        try:
            body = request.body
        except Exception as e:
            logger.warning(f"Error reading request body: {str(e)}")
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
                    logger.info(f"Multipart request with files: {file_info}")
            except Exception as e:
                logger.warning(f"Could not parse multipart body: {str(e)}")

        # ======================== TIMEOUT CONFIGURATION ========================
        timeout_config = 300  # Increased default timeout to 5 minutes
        
        # Adjust timeout based on endpoint type
        if 'screen-resumes' in path:
            timeout_config = 600  # 10 minutes for resume screening
        elif 'parse-resume' in path or 'upload' in path:
            timeout_config = 300   # 5 minutes for file processing
        elif prefix == 'notifications':
            timeout_config = 30   # Shorter for notifications

        # ======================== REQUEST FORWARDING ========================
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
            if method in ['POST', 'PUT', 'PATCH', 'DELETE']:
                request_kwargs['data'] = body

            logger.info(f"Forwarding request to: {forward_url} with timeout: {timeout_config}s")
            
            # Use global session for connection pooling
            response = session.request(**request_kwargs)

        except requests.exceptions.Timeout as e:
            logger.error(f"Gateway timeout on /api/{path} after {timeout_config}s")
            return JsonResponse({
                "error": "Request timeout", 
                "details": f"Service took longer than {timeout_config} seconds to respond",
                "service": prefix,
                "suggestion": "Please try again later or contact support if the problem persists"
            }, status=504)
            
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error to {prefix} service: {str(e)}")
            return JsonResponse({
                "error": "Service unavailable",
                "details": f"Cannot connect to {prefix} service",
                "service": prefix,
                "suggestion": "Service may be restarting. Please try again in a few moments."
            }, status=502)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error to {prefix} service: {str(e)}")
            return JsonResponse({
                "error": "Request failed",
                "details": str(e),
                "service": prefix
            }, status=502)

        # ======================== RESPONSE HANDLING ========================
        logger.info(
            f"Gateway forwarded: {method} /api/{path} -> {response.status_code} "
            f"(Service: {prefix}, Time: {timeout_config}s)"
        )

        # Stream the response content to avoid memory issues
        response_content = b''
        for chunk in response.iter_content(chunk_size=8192):
            response_content += chunk

        # Prepare response headers
        response_headers = {}
        for key, value in response.headers.items():
            key_lower = key.lower()
            # Filter out hop-by-hop headers
            if key_lower not in excluded_headers and not key_lower.startswith('content-encoding'):
                response_headers[key] = value

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