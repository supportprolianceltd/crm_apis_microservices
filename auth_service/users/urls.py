from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    UserViewSet,TermsAndConditionsView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
    UserPasswordRegenerateView,
    ClientViewSet,
    AdminUserCreateView,
    UserCreateView,
    UserBranchUpdateView,
    TenantUsersListView,
    BranchUsersListView,
    UserSessionViewSet,
)

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'clients', ClientViewSet, basename='client')
router.register(r'user-sessions', UserSessionViewSet, basename='user-session')

urlpatterns = [
    # Dynamic routes from router (should come first)
    path('', include(router.urls)),

    # User management endpoints
    path('users/create/', UserCreateView.as_view(), name='users_user_create'),
    path('users/admin/create/', AdminUserCreateView.as_view(), name='users_admin_create'),
    path('users/<int:user_id>/branch/', UserBranchUpdateView.as_view(), name='users_branch_update'),
    path('users/<int:user_id>/regenerate-password/', UserPasswordRegenerateView.as_view(), name='users_regenerate_password'),
    path('tenant-users/', TenantUsersListView.as_view(), name='users_tenant_list'),
    path('branch-users/<int:branch_id>/', BranchUsersListView.as_view(), name='users_branch_list'),

    # Password management endpoints
    path('password/reset/', PasswordResetRequestView.as_view(), name='password_reset_request'),
    path('password/reset/confirm/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('terms-and-conditions/', TermsAndConditionsView.as_view(), name='terms_and_conditions'),
]