from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView
from django.views.generic import TemplateView


class CustomSwaggerUIView(TemplateView):
    template_name = 'swagger-ui.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Use absolute URL to schema (adjust for your deployment)
        context['schema_url'] = 'http://hr-service:8004/api/schema/'
        return context
    
urlpatterns = [
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', CustomSwaggerUIView.as_view(), name='swagger-ui'),

    path('api/hr/', include('hr.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)