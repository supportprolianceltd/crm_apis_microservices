from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserViewSet, TermsAndConditionsView, PasswordResetRequestView, PasswordResetConfirmView,DocumentDetailView,DocumentListCreateView,
    UserPasswordRegenerateView, ClientViewSet, AdminUserCreateView, UserCreateView,RSAKeyPairCreateView,
    UserBranchUpdateView, TenantUsersListView, BranchUsersListView, UserSessionViewSet,DocumentAcknowledgeView,
    LoginAttemptViewSet, BlockedIPViewSet, UserActivityViewSet, jwks_view, protected_view
)

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'clients', ClientViewSet, basename='client')
router.register(r'user-sessions', UserSessionViewSet, basename='user-session')
router.register(r'login-attempts', LoginAttemptViewSet, basename='login-attempt')
router.register(r'blocked-ips', BlockedIPViewSet, basename='blocked-ip')
router.register(r'user-activities', UserActivityViewSet, basename='user-activity')

urlpatterns = [
    path('', include(router.urls)),
    path('protected/', protected_view, name='protected_token'),
    path('api/jwks/<int:tenant_id>/', jwks_view, name='jwks'),
    path('users/create/', UserCreateView.as_view(), name='users_user_create'),
    path('users/admin/create/', AdminUserCreateView.as_view(), name='users_admin_create'),
    path('users/<int:user_id>/branch/', UserBranchUpdateView.as_view(), name='users_branch_update'),
    path('password/regenerate/', UserPasswordRegenerateView.as_view(), name='users_regenerate_password'),
    path('tenant-users/', TenantUsersListView.as_view(), name='users_tenant_list'),
    path('branch-users/<int:branch_id>/', BranchUsersListView.as_view(), name='users_branch_list'),
    path('password/reset/', PasswordResetRequestView.as_view(), name='password_reset_request'),
    path('password/reset/confirm/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('terms-and-conditions/', TermsAndConditionsView.as_view(), name='terms_and_conditions'),

    path('keys/create/', RSAKeyPairCreateView.as_view(), name='rsa-keypair-create'),

    path('documents/', DocumentListCreateView.as_view(), name='document-list-create'),
    path('documents/<int:id>/', DocumentDetailView.as_view(), name='document-detail'),
    path('documents/<int:document_id>/acknowledge/', DocumentAcknowledgeView.as_view(), name='document-acknowledge'),
]