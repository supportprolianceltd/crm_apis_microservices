from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'leave-types', views.LeaveTypeViewSet, basename='leavetype')
router.register(r'leave-requests', views.LeaveRequestViewSet, basename='leaverequest')
router.register(r'contracts', views.ContractViewSet, basename='contract')
router.register(r'equipment', views.EquipmentViewSet, basename='equipment')
router.register(r'policies', views.PolicyViewSet, basename='policy')
router.register(r'policy-acknowledgments', views.PolicyAcknowledgmentViewSet, basename='policyacknowledgment')
router.register(r'alerts', views.EscalationAlertViewSet, basename='alert')
router.register(r'warnings', views.DisciplinaryWarningViewSet, basename='warning')
router.register(r'probation-periods', views.ProbationPeriodViewSet, basename='probationperiod')
router.register(r'performance-reviews', views.PerformanceReviewViewSet, basename='performancereview')
router.register(r'er-cases', views.EmployeeRelationCaseViewSet, basename='ercase')
router.register(r'starters-leavers', views.StarterLeaverViewSet, basename='starterleaver')

urlpatterns = [
    path('', include(router.urls)),
    path('analytics/dashboard/', views.HRAnalyticsView.as_view(), name='hr-analytics'),
    path('public/policies/<str:tenant_unique_id>/', views.PublicLeavePoliciesView.as_view(), name='public-policies'),
]