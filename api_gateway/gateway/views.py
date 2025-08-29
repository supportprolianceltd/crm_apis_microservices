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
    # Add other public paths as needed
]

@ratelimit(key='ip', rate='5/m', method='POST', block=True)
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

        # Check if the path is public
        if any(path.startswith(public) for public in PUBLIC_PATHS):
            # Optionally, remove Authorization header if present
            headers = {
                key: value for key, value in request.headers.items()
                if key.lower() not in ["host", "content-length", "authorization"]
            }
        else:
            # Normal header logic
            headers = {
                key: value for key, value in request.headers.items()
                if key.lower() not in ["host", "content-length"]
            }
        # Dynamically set Host header to match the service name (without port)
        service_host = base_url.split("//")[-1].split(":")[0]
        headers["Host"] = service_host

        # Apply rate limiting to login
        if path.startswith("token/") and request.method == "POST":
            was_limited = is_ratelimited(
                request=request,
                fn=api_gateway_view,
                key='ip',
                rate='5/m',
                method='POST',
                increment=True
            )
            if was_limited:
                logger.warning(f"Rate limit exceeded for /api/{path} from IP {request.META.get('REMOTE_ADDR')}")
                return JsonResponse({"error": "Rate limit exceeded. Max 5 login attempts per minute."}, status=429)

        # Handle file upload vs JSON
        if request.content_type and request.content_type.startswith('multipart/form-data'):
            # Forward as multipart with correct file structure
            files = {
                name: (file.name, file.file, file.content_type)
                for name, file in request.FILES.items()
            }
            data = request.POST.dict()
            response = requests.request(
                method=request.method,
                url=forward_url,
                headers=headers,
                files=files if files else None,
                data=data,
                params=request.GET,
                timeout=30
            )
        else:
            # Handle JSON and other content types
            response = requests.request(
                method=request.method,
                url=forward_url,
                headers=headers,
                data=request.body,
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
