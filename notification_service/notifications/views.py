from rest_framework import generics
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated  # Or custom
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
from notifications.models import NotificationRecord, TenantCredentials, NotificationTemplate
from notifications.serializers import NotificationRecordSerializer, TenantCredentialsSerializer, NotificationTemplateSerializer
from notifications.orchestrator.validator import validate_tenant_and_channel
from notifications.utils.context import get_tenant_context
from rest_framework.pagination import PageNumberPagination
import logging

logger = logging.getLogger('notifications.api')

from rest_framework.views import APIView
from django.db.models import Count, Q
from notifications.models import NotificationRecord, ChannelType
from django.utils import timezone
from datetime import timedelta
import logging

class AnalyticsView(APIView):
    def get(self, request):
        tenant_id = request.tenant_id
        period_days = int(request.query_params.get('days', 30))
        cutoff = timezone.now() - timedelta(days=period_days)
        
        records = NotificationRecord.objects.filter(tenant_id=tenant_id, created_at__gte=cutoff)
        
        data = {
            'total_sent': records.filter(status=NotificationStatus.SUCCESS.value).count(),
            'total_failed': records.filter(status=NotificationStatus.FAILED.value).count(),
            'success_rate': round(
                (records.filter(status=NotificationStatus.SUCCESS.value).count() / records.count() * 100)
                if records.count() > 0 else 0, 2
            ),
            'channel_usage': dict(
                records.values('channel').annotate(count=Count('channel'))
            ),
            'failure_patterns': dict(
                records.filter(status=NotificationStatus.FAILED.value)
                       .values('failure_reason').annotate(count=Count('failure_reason'))
            ),
        }
        
        return Response(data)

        
class StandardResultsSetPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 100

class NotificationListCreateView(generics.ListCreateAPIView):
    serializer_class = NotificationRecordSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['status', 'channel']
    search_fields = ['recipient', 'provider_response']

    def get_queryset(self):
        tenant_id = self.request.tenant_id
        return NotificationRecord.objects.filter(tenant_id=tenant_id)

    def perform_create(self, serializer):
        serializer.save()

class TenantCredentialsListCreateView(generics.ListCreateAPIView):
    serializer_class = TenantCredentialsSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        tenant_id = self.request.tenant_id
        return TenantCredentials.objects.filter(tenant_id=tenant_id)

class NotificationTemplateListCreateView(generics.ListCreateAPIView):
    serializer_class = NotificationTemplateSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        tenant_id = self.request.tenant_id
        return NotificationTemplate.objects.filter(tenant_id=tenant_id)

# Add Retrieve/Update/Destroy as needed, similar to your HR views

from notifications.models import Campaign  # Add
from .serializers import CampaignSerializer  # Add

class CampaignListCreateView(generics.ListCreateAPIView):
    serializer_class = CampaignSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        tenant_id = self.request.tenant_id
        return Campaign.objects.filter(tenant_id=tenant_id)

# Add to urlpatterns in api/urls.py
