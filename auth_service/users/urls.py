from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserViewSet, TermsAndConditionsView, PasswordResetRequestView, PasswordResetConfirmView,
    DocumentDetailView, DocumentListCreateView, UserPasswordRegenerateView, ClientViewSet,
    AdminUserCreateView, RSAKeyPairCreateView, UserBranchUpdateView, TenantUsersListView,
    BranchUsersListView, UserSessionViewSet, LoginAttemptViewSet, BlockedIPViewSet,
    UserActivityViewSet, jwks_view, protected_view, GroupViewSet, DocumentVersionListView,
    ProfessionalQualificationView, EmploymentDetailView, EducationDetailView,
    ReferenceCheckView, ProofOfAddressView, InsuranceVerificationView,
    DrivingRiskAssessmentView, LegalWorkEligibilityView, OtherUserDocumentsView
)

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'clients', ClientViewSet, basename='client')
router.register(r'user-sessions', UserSessionViewSet, basename='user-session')
router.register(r'login-attempts', LoginAttemptViewSet, basename='login-attempt')
router.register(r'blocked-ips', BlockedIPViewSet, basename='blocked-ip')
router.register(r'user-activities', UserActivityViewSet, basename='user-activity')
router.register(r'groups', GroupViewSet, basename='group')

urlpatterns = [
    path('', include(router.urls)),
    path('protected/', protected_view, name='protected_token'),
    path('api/jwks/<int:tenant_id>/', jwks_view, name='jwks'),
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
    path('documents/<int:document_id>/versions/', DocumentVersionListView.as_view(), name='document-versions'),
    
    # Professional Qualification endpoints
    path('professional-qualifications/', ProfessionalQualificationView.as_view(), name='professional-qualification-create'),
    path('professional-qualifications/<int:obj_id>/', ProfessionalQualificationView.as_view(), name='professional-qualification-update'),
    
    # Employment Detail endpoints
    path('employment-details/', EmploymentDetailView.as_view(), name='employment-detail-create'),
    path('employment-details/<int:obj_id>/', EmploymentDetailView.as_view(), name='employment-detail-update'),
    
    # Education Detail endpoints
    path('education-details/', EducationDetailView.as_view(), name='education-detail-create'),
    path('education-details/<int:obj_id>/', EducationDetailView.as_view(), name='education-detail-update'),
    
    # Reference Check endpoints
    path('reference-checks/', ReferenceCheckView.as_view(), name='reference-check-create'),
    path('reference-checks/<int:obj_id>/', ReferenceCheckView.as_view(), name='reference-check-update'),
    
    # Proof of Address endpoints
    path('proof-of-address/', ProofOfAddressView.as_view(), name='proof-of-address-create'),
    path('proof-of-address/<int:obj_id>/', ProofOfAddressView.as_view(), name='proof-of-address-update'),
    
    # Insurance Verification endpoints
    path('insurance-verifications/', InsuranceVerificationView.as_view(), name='insurance-verification-create'),
    path('insurance-verifications/<int:obj_id>/', InsuranceVerificationView.as_view(), name='insurance-verification-update'),
    
    # Driving Risk Assessment endpoints
    path('driving-risk-assessments/', DrivingRiskAssessmentView.as_view(), name='driving-risk-assessment-create'),
    path('driving-risk-assessments/<int:obj_id>/', DrivingRiskAssessmentView.as_view(), name='driving-risk-assessment-update'),
    
    # Legal Work Eligibility endpoints
    path('legal-work-eligibilities/', LegalWorkEligibilityView.as_view(), name='legal-work-eligibility-create'),
    path('legal-work-eligibilities/<int:obj_id>/', LegalWorkEligibilityView.as_view(), name='legal-work-eligibility-update'),
    
    # Other User Documents endpoints
    path('other-user-documents/', OtherUserDocumentsView.as_view(), name='other-user-document-create'),
    path('other-user-documents/<int:obj_id>/', OtherUserDocumentsView.as_view(), name='other-user-document-update'),
]