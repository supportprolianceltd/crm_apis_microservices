import logging
import requests

from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django_ratelimit.decorators import ratelimit
from django.shortcuts import render

logger = logging.getLogger('gateway')

AUTH_PREFIXES = {"token", "user", "tenant"}
PUBLIC_PATHS = [
    "applications-engine/applications/parse-resume/autofill/",
    "/api/talent-engine/requisitions/by-link/",
    "/api/talent-engine/requisitions/unique_link/",
    "/api/talent-engine/requisitions/public/published/",
    "/api/talent-engine/requisitions/public/close/",
    "/api/applications-engine/apply-jobs/",
    "/api/applications-engine/applications/code/",
]

import logging
import requests
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django_ratelimit.decorators import ratelimit
from django.utils.encoding import force_str
import re

logger = logging.getLogger('gateway')

AUTH_PREFIXES = {"token", "user", "tenant"}
PUBLIC_PATHS = [
    "applications-engine/applications/parse-resume/autofill/",
    "/api/talent-engine/requisitions/by-link/",
    "/api/talent-engine/requisitions/unique_link/",
    "/api/talent-engine/requisitions/public/published/",
    "/api/talent-engine/requisitions/public/close/",
    "/api/applications-engine/apply-jobs/",
    "/api/applications-engine/applications/code/",
]

@csrf_exempt
@ratelimit(key='ip', rate='10/m', method='POST', block=True)
def api_gateway_view(request, path):
    try:
        segments = path.split('/')
        prefix = segments[0]
        sub_path = '/'.join(segments[1:])
        base_url = settings.MICROSERVICE_URLS.get(prefix)

        if not base_url:
            logger.error(f"No route found for /api/{prefix}/")
            return JsonResponse({"error": f"No route found for /api/{prefix}/"}, status=404)

        forward_url = f"{base_url}/api/{prefix}/{sub_path}"
        is_public = any(path.startswith(public) for public in PUBLIC_PATHS)

        excluded_headers = {"host", "content-length"}
        if is_public:
            excluded_headers.add("authorization")

        headers = {
            k: v for k, v in request.headers.items()
            if k.lower() not in excluded_headers
        }
        headers["Host"] = base_url.split("//")[-1].split(":")[0]

        method = request.method.upper()

        # Read raw body once (safe)
        try:
            body = request.body
        except Exception:
            body = None

        # DEBUG: Log multipart file indicators if present
        content_type = request.META.get("CONTENT_TYPE", "")
        logger.info(f"Incoming request content type: {content_type}")
        logger.info(f"Raw body size: {len(body) if body else 0} bytes")

        if body and content_type.startswith("multipart/form-data"):
            try:
                body_str = force_str(body[:10000])  # Peek into body, limit to first 10KB for safety
                file_fields = re.findall(r'Content-Disposition: form-data; name="([^"]+)"(?:; filename="([^"]+)")?', body_str)
                if file_fields:
                    logger.info(f"Detected file fields in multipart body: {[(f[0], f[1]) for f in file_fields if f[1]]}")
                else:
                    logger.info("No file indicators found in multipart body.")
            except Exception as e:
                logger.warning(f"Could not parse multipart body for file logging: {str(e)}")

        # Forward request
        if method in ['POST', 'PUT', 'PATCH']:
            response = requests.request(
                method=method,
                url=forward_url,
                headers=headers,
                data=body,
                params=request.GET,
                timeout=30
            )
        else:
            response = requests.request(
                method=method,
                url=forward_url,
                headers=headers,
                params=request.GET,
                timeout=30
            )

        logger.info(
            f"METHOD: {method} | PATH: /api/{path} | STATUS: {response.status_code} | "
            f"IP: {request.META.get('REMOTE_ADDR')} | FORWARDED TO: {forward_url}"
        )

        return HttpResponse(
            response.content,
            status=response.status_code,
            content_type=response.headers.get("Content-Type", "application/json")
        )

    except requests.exceptions.Timeout as e:
        logger.error(f"Gateway timeout on /api/{path}: {str(e)}")
        return JsonResponse({"error": "Gateway timeout", "details": str(e)}, status=504)
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error on /api/{path}: {str(e)}")
        return JsonResponse({"error": "Connection error", "details": str(e)}, status=502)
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error on /api/{path}: {str(e)}")
        return JsonResponse({"error": "Request error", "details": str(e)}, status=502)
    except Exception as e:
        logger.error(f"Gateway error on /api/{path}: {str(e)}", exc_info=True)
        return JsonResponse({
            "error": "Internal gateway error",
            "details": str(e),
            "suggestion": "An unexpected error occurred in the gateway. Please contact support."
        }, status=500)


def multi_docs_view(request):
    return render(request, 'docs.html', {
        'auth_docs_url': f"{settings.MICROSERVICE_URLS['auth_service']}/api/docs/",
        'applications_docs_url': f"{settings.MICROSERVICE_URLS['applications-engine']}/api/docs/",
        'talent_docs_url': f"{settings.MICROSERVICE_URLS['talent-engine']}/api/docs/",
    })
        
# @csrf_exempt
# @ratelimit(key='ip', rate='10/m', method='POST', block=True)
# def api_gateway_view(request, path):
#     try:
#         segments = path.split('/')
#         prefix = segments[0]
#         sub_path = '/'.join(segments[1:])
#         base_url = settings.MICROSERVICE_URLS.get(prefix)

#         if not base_url:
#             return JsonResponse({"error": f"No route found for /api/{prefix}/"}, status=404)

#         forward_url = f"{base_url}/api/{prefix}/{sub_path}"
#         is_public = any(path.startswith(public) for public in PUBLIC_PATHS)

#         excluded_headers = ["host", "content-length"]
#         if is_public:
#             excluded_headers.append("authorization")

#         if request.content_type and request.content_type.startswith("multipart/form-data"):
#             excluded_headers.append("content-type")  # Let requests auto-set it

#         headers = {
#             k: v for k, v in request.headers.items()
#             if k.lower() not in excluded_headers
#         }
#         headers["Host"] = base_url.split("//")[-1].split(":")[0]

#         method = request.method.upper()

#         # Forward the request based on method and content type
#         if method in ['POST', 'PUT', 'PATCH']:
#             if request.content_type and request.content_type.startswith("multipart/form-data"):
#                 # For file upload forms
#                 data = request.POST.copy()
#                 files = {
#                     key: (file.name, file.file, file.content_type)
#                     for key, file in request.FILES.items()
#                 }
#                 response = requests.request(
#                     method=method,
#                     url=forward_url,
#                     headers=headers,
#                     data=data,
#                     files=files,
#                     params=request.GET,
#                     timeout=30
#                 )
#             else:
#                 # For JSON or raw payloads
#                 try:
#                     body = request.body  # Safe to read once
#                 except Exception:
#                     body = None

#                 if not request.content_type:
#                     headers["Content-Type"] = "application/json"

#                 response = requests.request(
#                     method=method,
#                     url=forward_url,
#                     headers=headers,
#                     data=body,
#                     params=request.GET,
#                     timeout=30
#                 )
#         else:
#             # For GET, DELETE, etc.
#             response = requests.request(
#                 method=method,
#                 url=forward_url,
#                 headers=headers,
#                 params=request.GET,
#                 timeout=30
#             )

#         logger.info(
#             f"METHOD: {method} | PATH: /api/{path} | STATUS: {response.status_code} | "
#             f"IP: {request.META.get('REMOTE_ADDR')} | FORWARDED TO: {forward_url}"
#         )

#         return HttpResponse(
#             response.content,
#             status=response.status_code,
#             content_type=response.headers.get("Content-Type", "application/json")
#         )

#     except requests.exceptions.Timeout as e:
#         return JsonResponse({"error": "Gateway timeout", "details": str(e)}, status=504)
#     except requests.exceptions.ConnectionError as e:
#         return JsonResponse({"error": "Connection error", "details": str(e)}, status=502)
#     except requests.exceptions.RequestException as e:
#         return JsonResponse({"error": "Request error", "details": str(e)}, status=502)
#     except Exception as e:
#         logger.error(f"Gateway error on /api/{path}: {str(e)}")
#         return JsonResponse({
#             "error": "Internal gateway error",
#             "details": str(e),
#             "suggestion": "An unexpected error occurred in the gateway. Please contact support."
#         }, status=500)

