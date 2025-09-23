from django.urls import path, include
from django.contrib import admin
from django.http import JsonResponse
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView



from django.http import HttpResponse

def test_metrics(request):
    return HttpResponse("Test metrics endpoint")


def root_view(request):
    return JsonResponse({
        'status': 'success',
        'message': 'Welcome to LUMINA Care OS API',
        'endpoints': {
            'tenants': '/api/lms/tenant/tenants/',
            'users': '/api/lms//users/',
            'docs': '/api/lms/docs/',
            'token': '/api/lms/token/',
            'schedules': '/api/lms/schedule/',
            'courses': '/api/lms/courses/',
            'messaging': '/api/lms/messaging/',
            'groups': '/api/lms/groups/',
            'adverts': '/api/lms/adverts/',
            'payments': '/api/lms/payments/',
            'forums': '/api/lms/forums/',
            'django_prometheus': '/django_prometheus/',
        }
    })

urlpatterns = [
    path('', root_view, name='root'),
    path('api/lms/activitylog/', include('activitylog.urls')),
    path('api/lms/courses/', include('courses.urls')),
    path('api/lms/schedule/', include('schedule.urls')),
    path('api/lms/messaging/', include('messaging.urls')),
    path('api/lms/carts/', include('carts.urls')),
    path('api/lms/ai_chat/', include('ai_chat.urls')),
    path('api/lms/groups/', include('groups.urls')),
    path('api/lms/adverts/', include('advert.urls')),
    path('api/lms/payments/', include('payments.urls')),
    path('api/lms/forums/', include('forum.urls')),
    path('django_prometheus/', include('django_prometheus.urls')),
]


if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


