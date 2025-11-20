# investments/urls.py (complete corrected version)

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'policies', views.InvestmentPolicyViewSet, basename='investment-policy')
router.register(r'withdrawals', views.WithdrawalRequestViewSet, basename='withdrawal-request')
router.register(r'ledger', views.LedgerEntryViewSet, basename='ledger-entry')
router.register(r'taxes/records', views.TaxRecordViewSet, basename='tax-record')
router.register(r'taxes/certificates', views.TaxCertificateViewSet, basename='tax-certificate')

urlpatterns = [
    path('', include(router.urls)),
    path('dashboard/', views.InvestmentDashboardView.as_view(), name='investment-dashboard'),
    path('statements/generate/', views.StatementGenerationView.as_view(), name='generate-statement'),
    path('roi/accrue/', views.ROIAccrualView.as_view(), name='roi-accrual'),  # ✅ Fixed
    path('search/', views.InvestmentSearchView.as_view(), name='investment-search'),  # ✅ Fixed
    
    path('reports/performance/', views.InvestmentPerformanceReportView.as_view(), name='investment-performance'),
    path('reports/roi-due/', views.ROIDueReportView.as_view(), name='roi-due-report'),

    # Tax Management URLs
    path('taxes/calculate/', views.TaxCalculationView.as_view(), name='tax-calculate'),
    path('taxes/summary/', views.TaxSummaryView.as_view(), name='tax-summary'),
    path('taxes/settings/', views.TaxSettingsView.as_view(), name='tax-settings'),
    path('taxes/reports/', views.TaxReportView.as_view(), name='tax-reports'),
]