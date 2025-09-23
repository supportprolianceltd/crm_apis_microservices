from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.db.models import Q
from .models import Advert
from .serializers import AdvertSerializer, get_tenant_id_from_jwt
from activitylog.models import ActivityLog
from activitylog.serializers import ActivityLogSerializer
import logging
from rest_framework.pagination import PageNumberPagination

logger = logging.getLogger('advert')

class StandardResultsPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class AdvertViewSet(viewsets.ModelViewSet):
    serializer_class = AdvertSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Advert.objects.none()
        jwt_payload = getattr(self.request, 'jwt_payload', {})
        tenant_id = jwt_payload.get('tenant_unique_id')
        if not tenant_id:
            logger.error("No tenant_unique_id in JWT payload")
            raise serializers.ValidationError("Tenant ID not found in token.")
        queryset = Advert.objects.filter(tenant_id=tenant_id).order_by('-priority', '-created_at')
        
        # Apply filters
        search = self.request.query_params.get('search', None)
        status = self.request.query_params.get('status', None)
        target = self.request.query_params.get('target', None)
        date_from = self.request.query_params.get('date_from', None)
        date_to = self.request.query_params.get('date_to', None)
        
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(content__icontains=search)
            )
        if status and status != 'all':
            queryset = queryset.filter(status=status)
        if target and target != 'all':
            queryset = queryset.filter(target=target)
        if date_from:
            queryset = queryset.filter(start_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(end_date__lte=date_to)
            
        return queryset

    def create(self, request, *args, **kwargs):
        tenant_id = request.jwt_payload.get('tenant_unique_id')
        logger.debug(f"Request data type: {type(request.data)}")
        logger.debug(f"Request data content: {request.data}")
        logger.debug(f"Request headers: {request.headers}")
        logger.debug(f"Request content type: {request.content_type}")
        
        serializer = self.get_serializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            logger.info(f"[Tenant {tenant_id}] Advert created: {serializer.data['title']}")
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
        
        logger.error(f"[Tenant {tenant_id}] Create advert failed. Errors: {serializer.errors}")
        logger.error(f"[Tenant {tenant_id}] Data that failed validation: {serializer.initial_data}")
        return Response({
            'error': 'Validation failed',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, *args, **kwargs):
        tenant_id = request.jwt_payload.get('tenant_unique_id')
        logger.debug(f"Request data: {request.data}")
        logger.debug(f"Request headers: {request.headers}")
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial, context={'request': request})
        if serializer.is_valid():
            self.perform_update(serializer)
            logger.info(f"[Tenant {tenant_id}] Advert updated: {instance.title}")
            return Response(serializer.data)
        logger.error(f"[Tenant {tenant_id}] Update advert failed: {serializer.errors}")
        return Response({
            'error': 'Validation failed',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    def perform_create(self, serializer):
        serializer.save()

    def perform_update(self, serializer):
        serializer.save()

    @action(detail=True, methods=['get'])
    def activity(self, request, pk=None):
        tenant_id = request.jwt_payload.get('tenant_unique_id')
        advert = self.get_object()
        activities = ActivityLog.objects.filter(
            tenant_id=tenant_id,
            activity_type__in=['advert_created', 'advert_updated', 'advert_deleted'],
            details__contains=advert.title
        ).order_by('-timestamp')
        
        page = self.paginate_queryset(activities)
        if page is not None:
            serializer = ActivityLogSerializer(page, many=True)
            logger.info(f"[Tenant {tenant_id}] Listed activities for advert {advert.title}, count: {len(serializer.data)}")
            return self.get_paginated_response(serializer.data)
        
        serializer = ActivityLogSerializer(activities, many=True)
        logger.info(f"[Tenant {tenant_id}] Listed activities for advert {advert.title}, count: {len(serializer.data)}")
        return Response(serializer.data)