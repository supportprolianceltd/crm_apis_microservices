import requests
import logging
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django_ratelimit.decorators import ratelimit
from django_ratelimit.core import is_ratelimited

logger = logging.getLogger('gateway')

AUTH_PREFIXES = {"token", "user", "tenant"}
PUBLIC_PATHS = [
    "applications-engine/applications/parse-resume/autofill/",
    "applications-engine/apply-jobs/",
    # Add other public paths as needed
]

@ratelimit(key='ip', rate='10/m', method='POST', block=True)
@csrf_exempt
def api_gateway_view(request, path):
    try:
        # Support multi-segment prefixes (e.g., talent-engine, applications-engine)
        segments = path.split('/')
        if len(segments) >= 2 and segments[0] in {"talent-engine", "applications-engine"}:
            prefix = segments[0]
            sub_path = '/'.join(segments[1:])
        else:
            prefix = segments[0]
            sub_path = '/'.join(segments[1:])

        base_url = settings.MICROSERVICE_URLS.get(prefix)

        if not base_url:
            logger.warning(f"No route found for /api/{prefix}/ from IP {request.META.get('REMOTE_ADDR')}")
            return JsonResponse({"error": f"No route found for /api/{prefix}/"}, status=404)

        forward_url = f"{base_url}/api/{prefix}/{sub_path}"

        is_public = any(path.startswith(public) for public in PUBLIC_PATHS)

        # Check if request has files to handle multipart/form-data
        if request.FILES:
            headers = {
                key: value for key, value in request.headers.items()
                if key.lower() not in ["host", "content-length", "content-type"] + (["authorization"] if is_public else [])
            }
            # Dynamically set Host header to match the service name (without port)
            service_host = base_url.split("//")[-1].split(":")[0]
            headers["Host"] = service_host

            files = {k: (f.name, f.file, f.content_type) for k, f in request.FILES.items()}
            data = request.POST.dict()
            response = requests.request(
                method=request.method,
                url=forward_url,
                headers=headers,
                files=files,
                data=data,
                params=request.GET,
                timeout=30
            )
        else:
            headers = {
                key: value for key, value in request.headers.items()
                if key.lower() not in ["host", "content-length"] + (["authorization"] if is_public else [])
            }
            service_host = base_url.split("//")[-1].split(":")[0]
            headers["Host"] = service_host

            raw_body = request.body
            response = requests.request(
                method=request.method,
                url=forward_url,
                headers=headers,
                data=raw_body,
                params=request.GET,
                timeout=30
            )

        # Logging
        logger.info(
            f"METHOD: {request.method} | PATH: /api/{path} | STATUS: {response.status_code} | "
            f"IP: {request.META.get('REMOTE_ADDR')} | FORWARDED TO: {forward_url}"
        )

        return HttpResponse(
            response.content,
            status=response.status_code,
            content_type=response.headers.get("Content-Type", "application/json")
        )

    except Exception as e:
        logger.error(f"Error forwarding request to /api/{path} from {request.META.get('REMOTE_ADDR')}: {str(e)}")
        return JsonResponse({"error": "Internal gateway error", "details": str(e)}, status=500)




# @ratelimit(key='ip', rate='5/m', method='POST', block=True)
# @csrf_exempt
# def api_gateway_view(request, path):
#     try:
#         # Support multi-segment prefixes (e.g., talent-engine, applications-engine)
#         segments = path.split('/')
#         if len(segments) >= 2 and segments[0] in {"talent-engine", "applications-engine"}:
#             prefix = segments[0]
#             sub_path = '/'.join(segments[1:])
#         else:
#             prefix = segments[0]
#             sub_path = '/'.join(segments[1:])

#         base_url = settings.MICROSERVICE_URLS.get(prefix)

#         if not base_url:
#             logger.warning(f"No route found for /api/{prefix}/ from IP {request.META.get('REMOTE_ADDR')}")
#             return JsonResponse({"error": f"No route found for /api/{prefix}/"}, status=404)

#         forward_url = f"{base_url}/api/{prefix}/{sub_path}"

#         # Check if request has files to handle multipart/form-data
#         if request.FILES:
#             # Remove content-type header to let requests set it with boundary
#             headers = {
#                 key: value for key, value in request.headers.items()
#                 if key.lower() not in ["host", "content-length", "content-type"]
#             }
#             # Dynamically set Host header to match the service name (without port)
#             service_host = base_url.split("//")[-1].split(":")[0]
#             headers["Host"] = service_host

#             files = {k: (f.name, f.file, f.content_type) for k, f in request.FILES.items()}
#             data = request.POST.dict()
#             response = requests.request(
#                 method=request.method,
#                 url=forward_url,
#                 headers=headers,
#                 files=files,
#                 data=data,
#                 params=request.GET,
#                 timeout=30
#             )
#         else:
#             # For non-multipart requests, include content-type header
#             headers = {
#                 key: value for key, value in request.headers.items()
#                 if key.lower() not in ["host", "content-length"]
#             }
#             service_host = base_url.split("//")[-1].split(":")[0]
#             headers["Host"] = service_host

#             response = requests.request(
#                 method=request.method,
#                 url=forward_url,
#                 headers=headers,
#                 data=request.body,
#                 params=request.GET,
#                 timeout=30
#             )

#         # Logging
#         logger.info(
#             f"METHOD: {request.method} | PATH: /api/{path} | STATUS: {response.status_code} | "
#             f"IP: {request.META.get('REMOTE_ADDR')} | FORWARDED TO: {forward_url}"
#         )

#         return HttpResponse(
#             response.content,
#             status=response.status_code,
#             content_type=response.headers.get("Content-Type", "application/json")
#         )

#     except Exception as e:
#         logger.error(f"Error forwarding request to /api/{path} from {request.META.get('REMOTE_ADDR')}: {str(e)}")
#         return JsonResponse({"error": "Internal gateway error", "details": str(e)}, status=500)
