from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    LeaveTypeViewSet, LeaveRequestViewSet, ContractViewSet, EquipmentViewSet,
    PolicyViewSet, PolicyAcknowledgmentViewSet, EscalationAlertViewSet,
    DisciplinaryWarningViewSet, ProbationPeriodViewSet, PerformanceReviewViewSet,
    EmployeeRelationCaseViewSet, StarterLeaverViewSet, HRAnalyticsView,
    PublicLeavePoliciesView
)

router = DefaultRouter()
router.register(r"leave-types", LeaveTypeViewSet)
router.register(r"leave-requests", LeaveRequestViewSet)
router.register(r"contracts", ContractViewSet)
router.register(r"equipment", EquipmentViewSet)
router.register(r"policies", PolicyViewSet)
router.register(r"policy-acknowledgments", PolicyAcknowledgmentViewSet)
router.register(r"escalation-alerts", EscalationAlertViewSet)
router.register(r"disciplinary-warnings", DisciplinaryWarningViewSet)
router.register(r"probation-periods", ProbationPeriodViewSet)
router.register(r"performance-reviews", PerformanceReviewViewSet)
router.register(r"employee-relation-cases", EmployeeRelationCaseViewSet)
router.register(r"starters-leavers", StarterLeaverViewSet)

urlpatterns = [
    path("analytics/", HRAnalyticsView.as_view(), name="hr-analytics"),
    path("public/policies/<str:tenant_unique_id>/", PublicLeavePoliciesView.as_view(), name="public-policies"),
] + router.urls