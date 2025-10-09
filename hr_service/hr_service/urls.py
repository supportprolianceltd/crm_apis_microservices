# from django.urls import path, include
# from django.conf import settings
# from django.conf.urls.static import static
# from drf_spectacular.views import SpectacularAPIView
# from django.views.generic import TemplateView


# class CustomSwaggerUIView(TemplateView):
#     template_name = 'swagger-ui.html'

#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         # Use absolute URL to schema (adjust for your deployment)
#         context['schema_url'] = 'http://hr-service:8004/api/schema/'
#         return context
    
# urlpatterns = [
#     path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
#     path('api/docs/', CustomSwaggerUIView.as_view(), name='swagger-ui'),

#     path('api/hr/', include('hr.urls')),
# ] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework import permissions
from django.http import JsonResponse


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/hr/', include('hr.urls')),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/hr/health/', lambda request: JsonResponse({"status": "ok"}), name='health-check'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)