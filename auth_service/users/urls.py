from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (UserViewSet,TermsAndConditionsView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
    UserPasswordRegenerateView,
    ClientViewSet,
    CurrentUserView,
    TenantUsersListView,
    BranchUsersListView,
    UserSessionViewSet, jwks_view, protected_view,
)
from .views import (UserViewSet, FailedLoginViewSet, BlockedIPViewSet, VulnerabilityAlertViewSet,
    UserActivityViewSet, PasswordResetRequestView, PasswordResetConfirmView, TenantUsersListView)


router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'clients', ClientViewSet, basename='client')
router.register(r'user-sessions', UserSessionViewSet, basename='user-session')
router.register(r'user-activities', UserActivityViewSet, basename='user-activities')
router.register(r'failed-logins', FailedLoginViewSet, basename='failed-logins')
router.register(r'blocked-ips', BlockedIPViewSet, basename='blocked-ips')
router.register(r'vulnerability-alerts', VulnerabilityAlertViewSet, basename='vulnerability-alerts')


urlpatterns = [
    # Dynamic routes from router (should come first)
    path('', include(router.urls)),
    path('protected/', protected_view, name='protected_token'),
    path('api/jwks/<int:tenant_id>/', jwks_view, name='jwks'),
    
    # User management endpoints

    # path('users/admin/create/', AdminUserCreateView.as_view(), name='users_admin_create'),
    path('user/me/', CurrentUserView.as_view(), name='current-user'),
    path('recent-events/', UserActivityViewSet.as_view({'get': 'recent_events'}), name='recent-security-events'),

    path('users/<int:user_id>/regenerate-password/', UserPasswordRegenerateView.as_view(), name='users_regenerate_password'),
    path('tenant-users/', TenantUsersListView.as_view(), name='users_tenant_list'),
    path('branch-users/<int:branch_id>/', BranchUsersListView.as_view(), name='users_branch_list'),

    # Password management endpoints
    path('password/reset/', PasswordResetRequestView.as_view(), name='password_reset_request'),
    path('password/reset/confirm/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('terms-and-conditions/', TermsAndConditionsView.as_view(), name='terms_and_conditions'),



]





