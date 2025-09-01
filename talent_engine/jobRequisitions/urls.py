from django.urls import path, include, re_path
from rest_framework.routers import DefaultRouter
from .views import (
    JobRequisitionListCreateView,MyJobRequisitionListView, JobRequisitionDetailView,
    JobRequisitionBulkDeleteView,SoftDeletedJobRequisitionsView, RecoverSoftDeletedJobRequisitionsView,
    PermanentDeleteJobRequisitionsView,JobRequisitionByLinkView,ComplianceItemView,VideoSessionViewSet,
    RequestListCreateView, RequestDetailView, UserRequestsListView, CustomJobRequisitionByLinkView
)
from . import websocket

app_name = 'talent_engine'

# Define DRF router for REST API endpoints
router = DefaultRouter()
router.register(r'video-sessions', VideoSessionViewSet, basename='video-session')

# REST API URL patterns
urlpatterns = [
    path('', include(router.urls)),  # Include DRF router URLs for video-sessions
    path('requisitions-per-user/', MyJobRequisitionListView.as_view(), name='my-requisition-list'), 
    path('requisitions/', JobRequisitionListCreateView.as_view(), name='requisition-list-create'),
    path('requisitions/<str:id>/', JobRequisitionDetailView.as_view(), name='requisition-detail'),
    path('requisitions/bulk/bulk-delete/', JobRequisitionBulkDeleteView.as_view(), name='requisition-bulk-delete'),
    path('requisitions/deleted/soft_deleted/', SoftDeletedJobRequisitionsView.as_view(), name='soft-deleted-requisitions'),
    path('requisitions/recover/requisition/', RecoverSoftDeletedJobRequisitionsView.as_view(), name='recover-requisitions'),
    path('requisitions/permanent-delete/requisition/', PermanentDeleteJobRequisitionsView.as_view(), name='permanent-delete-requisitions'),
    path('requisitions/by-link/<str:unique_link>/', JobRequisitionByLinkView.as_view(), name='requisition-by-link'),
    path('requisitions/unique_link/<str:unique_link>/', CustomJobRequisitionByLinkView.as_view(), name='custom-requisition-by-link'),
    path('requisitions/<str:job_requisition_id>/compliance-items/', ComplianceItemView.as_view(), name='compliance-item-create'),
    path('requisitions/<str:job_requisition_id>/compliance-items/<str:item_id>/', ComplianceItemView.as_view(), name='compliance-item-detail'),
    # Requests CRUD endpoints
    path('requests/', RequestListCreateView.as_view(), name='request-list-create'),
    path('requests/<uuid:id>/', RequestDetailView.as_view(), name='request-detail'),
    path('requests/user/', UserRequestsListView.as_view(), name='user-requests-list'),
]

# WebSocket URL patterns (to be included in project-level urls.py or handled separately)
websocket_urlpatterns = [
    re_path(r'ws/signaling/(?P<session_id>[^/]+)/$', websocket.SignalingConsumer.as_asgi()),
]