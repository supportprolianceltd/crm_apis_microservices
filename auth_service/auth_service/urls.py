# lumina_care/urls.py
from django.urls import path, include
from django.http import JsonResponse
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from .views import (
    CustomTokenObtainPairView, CustomTokenRefreshView, JWKSView, JitsiTokenView, TokenValidateView,
    LoginWith2FAView, Verify2FAView, LogoutView, PublicKeyView
)
from django.conf import settings
from django.conf.urls.static import static

def root_view(request):
    return JsonResponse({
        'status': 'success',
        'message': 'Welcome to LUMINA Care OS API',
        'endpoints': {
            'tenants': '/api/tenant/tenants',
            'users': '/api/user/users',
            'docs': '/api/docs/',
            'token': '/api/token/'
        }
    })

urlpatterns = [
    path('', root_view, name='root'),

    path('api/tenant/', include('core.urls')),
    path('api/user/', include('users.urls')),

    # 2FA endpoints
    path('api/login/', LoginWith2FAView.as_view(), name='login_with_2fa'),
    path('api/logout/', LogoutView.as_view(), name='token_logout'),
    path('api/verify-2fa/', Verify2FAView.as_view(), name='verify_2fa'),

    path('api/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),
    path('api/token/validate/', TokenValidateView.as_view(), name='token_validate'),

    path('api/public-key/<str:kid>/', PublicKeyView.as_view(), name='public-key'),

    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),


    path('api/jitsi/well-known/jwks.json/', JWKSView.as_view(), name='jwks'),
    path('api/jitsi/token/', JitsiTokenView.as_view(), name='jitsi_token'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


