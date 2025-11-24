from django.urls import path, include
from django.http import JsonResponse
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from .views import (
    CookieDebugView, CustomTokenObtainPairView, CustomTokenRefreshView, JWKSView, 
    JitsiTokenView, SimpleCookieTestView, TokenValidateView, TestCookieSetView,
    LoginWith2FAView, Verify2FAView, LogoutView, PublicKeyView, EnvironmentInfoView, 
    SilentTokenRenewView
)
from django.conf import settings
from django.views.generic import TemplateView
from django.conf.urls.static import static

def root_view(request):
    return JsonResponse({
        'status': 'success',
        'message': 'Welcome to LUMINA Care OS API',
        'endpoints': {
            'tenants': '/api/tenant/tenants',
            'users': '/api/user/users',
            'reviews': '/api/reviews/',
            'investments': '/api/investments/',
            'events': '/api/events/events/',
            'docs': '/api/docs/',
            'token': '/api/token/',
            'environment_info': '/api/environment-info/'
        }
    })

urlpatterns = [
    path('', root_view, name='root'),

    path('api/tenant/', include('core.urls')),
    path('api/user/', include('users.urls')),
    path('api/reviews/', include('reviews.urls')),  # This should point to your reviews/urls.py
    path('api/investments/', include('investments.urls')),
    path('api/events/', include('events.urls')),

    # 2FA endpoints
    path('api/login/', LoginWith2FAView.as_view(), name='login_with_2fa'),
    path('api/logout/', LogoutView.as_view(), name='token_logout'),
    path('api/verify-2fa/', Verify2FAView.as_view(), name='verify_2fa'),
    path('api/test-cookies/', TestCookieSetView.as_view(), name='test_cookies'),

    # Authentication endpoints
    path('api/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),
    path('api/token/renew/', SilentTokenRenewView.as_view(), name='silent_renew'),
    path('api/token/validate/', TokenValidateView.as_view(), name='token_validate'),

    # Environment and debugging
    path('api/tenant/environment-info/', EnvironmentInfoView.as_view(), name='environment_info'),
    path('api/debug-cookies/', CookieDebugView.as_view(), name='debug_cookies'),
    path('api/simple-cookie-test/', SimpleCookieTestView.as_view(), name='simple_cookie_test'),

    # Security endpoints
    path('api/public-key/<str:kid>/', PublicKeyView.as_view(), name='public-key'),

    # Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),

    # Jitsi endpoints
    path('api/jitsi/well-known/jwks.json/', JWKSView.as_view(), name='jwks'),
    path('api/jitsi/token/', JitsiTokenView.as_view(), name='jitsi_token'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)