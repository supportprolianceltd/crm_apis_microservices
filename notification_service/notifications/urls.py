from django.urls import path
from .views import (
    AnalyticsView, CampaignListCreateView, NotificationListCreateView, TenantCredentialsListCreateView, NotificationTemplateListCreateView
)

app_name = 'notifications'

urlpatterns = [
    path('records/', NotificationListCreateView.as_view(), name='notification-list-create'),
    path('credentials/', TenantCredentialsListCreateView.as_view(), name='credentials-list-create'),
    path('templates/', NotificationTemplateListCreateView.as_view(), name='template-list-create'),
    path('analytics/', AnalyticsView.as_view(), name='analytics'),
    path('campaigns/', CampaignListCreateView.as_view(), name='campaign-list-create'),
]
