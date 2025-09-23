from django.db import transaction
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Q, Count
import logging
import requests
from django.conf import settings
from .models import Schedule, ScheduleParticipant
from .serializers import ScheduleSerializer, ScheduleParticipantSerializer, get_tenant_id_from_jwt
from activitylog.models import ActivityLog

logger = logging.getLogger('schedule')

class TenantBaseView(viewsets.GenericViewSet):
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        jwt_payload = getattr(request, 'jwt_payload', {})
        tenant_id = jwt_payload.get('tenant_unique_id')
        if not tenant_id:
            logger.error("No tenant_unique_id in JWT payload")
            raise ValidationError("Tenant ID not found in token.")
        logger.debug(f"[Tenant {tenant_id}] Schema set for request")

class ScheduleViewSet(TenantBaseView, viewsets.ModelViewSet):
    serializer_class = ScheduleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Schedule.objects.none()
        tenant_id = get_tenant_id_from_jwt(self.request)
        user_id = self.request.jwt_payload.get('user', {}).get('id')
        search = self.request.query_params.get('search')
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        show_past = self.request.query_params.get('show_past', 'false').lower() == 'true'

        queryset = Schedule.objects.filter(
            tenant_id=tenant_id,
        ).distinct().order_by('-start_time')

        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(location__icontains=search)
            )
        if date_from:
            try:
                queryset = queryset.filter(start_time__gte=date_from)
            except ValueError:
                logger.warning(f"[Tenant {tenant_id}] Invalid date_from format: {date_from}")
                raise ValidationError("Invalid date_from format")
        if date_to:
            try:
                queryset = queryset.filter(end_time__lte=date_to)
            except ValueError:
                logger.warning(f"[Tenant {tenant_id}] Invalid date_to format: {date_to}")
                raise ValidationError("Invalid date_to format")
        if not show_past:
            queryset = queryset.filter(end_time__gte=timezone.now())

        logger.debug(f"[Tenant {tenant_id}] Schedule query executed")
        return queryset

    def _get_user_groups(self, user_id, tenant_id):
        try:
            group_response = requests.get(
                f'{settings.AUTH_SERVICE_URL}/api/tenant/users/{user_id}/groups/',
                headers={'Authorization': f'Bearer {self.request.META.get("HTTP_AUTHORIZATION", "").split(" ")[1]}'}
            )
            if group_response.status_code == 200:
                return [g['id'] for g in group_response.json()]
            logger.error(f"[Tenant {tenant_id}] Failed to fetch groups for user {user_id}")
            return []
        except Exception as e:
            logger.error(f"[Tenant {tenant_id}] Error fetching groups for user {user_id}: {str(e)}")
            return []

    def get_serializer_context(self):
        return {'request': self.request}

    def create(self, request, *args, **kwargs):
        tenant_id = get_tenant_id_from_jwt(request)
        serializer = self.get_serializer(data=request.data, context={'request': request})
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            logger.error(f"[Tenant {tenant_id}] Schedule creation validation failed: {str(e)}")
            raise
        with transaction.atomic():
            schedule = serializer.save()
            ActivityLog.objects.create(
                tenant_id=tenant_id,
                tenant_name=schedule.tenant_name,
                user_id=request.jwt_payload.get('user', {}).get('id'),
                activity_type='schedule_created',
                details=f'Schedule "{schedule.title}" created by user {request.jwt_payload.get("user", {}).get("id")}',
                status='success'
            )
            logger.info(f"[Tenant {tenant_id}] Schedule created: {schedule.title} by user {request.jwt_payload.get('user', {}).get('id')}")
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        tenant_id = get_tenant_id_from_jwt(request)
        instance = self.get_object()
        old_data = ScheduleSerializer(instance, context={'request': request}).data
        serializer = self.get_serializer(instance, data=request.data, partial=kwargs.get('partial', False), context={'request': request})
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            logger.error(f"[Tenant {tenant_id}] Schedule update validation failed: {str(e)}")
            raise
        with transaction.atomic():
            serializer.save()
            changes = [
                f"{field}: {old_data[field]} → {serializer.data[field]}"
                for field in serializer.data
                if field in old_data and old_data[field] != serializer.data[field]
                and field not in ['updated_at', 'created_at']
            ]
            ActivityLog.objects.create(
                tenant_id=tenant_id,
                tenant_name=instance.tenant_name,
                user_id=request.jwt_payload.get('user', {}).get('id'),
                activity_type='schedule_updated',
                details=f'Schedule "{instance.title}" updated. Changes: {"; ".join(changes)}',
                status='success'
            )
            logger.info(f"[Tenant {tenant_id}] Schedule updated: {instance.title} by user {request.jwt_payload.get('user', {}).get('id')}")
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        tenant_id = get_tenant_id_from_jwt(request)
        with transaction.atomic():
            instance = self.get_object()
            instance.delete()
            ActivityLog.objects.create(
                tenant_id=tenant_id,
                tenant_name=instance.tenant_name,
                user_id=request.jwt_payload.get('user', {}).get('id'),
                activity_type='schedule_deleted',
                details=f'Schedule "{instance.title}" deleted by user {request.jwt_payload.get("user", {}).get("id")}',
                status='success'
            )
            logger.info(f"[Tenant {tenant_id}] Schedule deleted: {instance.title} by user {request.jwt_payload.get('user', {}).get('id')}")
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'])
    def respond(self, request, pk=None):
        tenant_id = get_tenant_id_from_jwt(request)
        user_id = request.jwt_payload.get('user', {}).get('id')
        response_status = request.data.get('response_status')
        if not response_status:
            logger.warning(f"[Tenant {tenant_id}] Missing response_status for schedule response")
            return Response({"detail": "response_status is required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            with transaction.atomic():
                schedule = self.get_object()
                participant, created = ScheduleParticipant.objects.update_or_create(
                    schedule=schedule,
                    user_id=user_id,
                    defaults={'response_status': response_status}
                )
                action = "created" if created else "updated"
                ActivityLog.objects.create(
                    tenant_id=tenant_id,
                    tenant_name=schedule.tenant_name,
                    user_id=user_id,
                    activity_type='schedule_response',
                    details=f'Responded "{response_status}" to schedule "{schedule.title}"',
                    status='success'
                )
                logger.info(f"[Tenant {tenant_id}] Schedule participant {action}: {schedule.title} by user {user_id}")
                return Response(ScheduleParticipantSerializer(participant, context={'request': request}).data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"[Tenant {tenant_id}] Error processing schedule response: {str(e)}", exc_info=True)
            return Response({"detail": "Error processing response"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        tenant_id = get_tenant_id_from_jwt(request)
        try:
            queryset = self.get_queryset().filter(end_time__gte=timezone.now()).order_by('start_time')[:10]
            serializer = self.get_serializer(queryset, many=True)
            logger.info(f"[Tenant {tenant_id}] Retrieved {len(serializer.data)} upcoming schedules")
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"[Tenant {tenant_id}] Error fetching upcoming schedules: {str(e)}", exc_info=True)
            return Response({"detail": "Error fetching upcoming schedules"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        tenant_id = get_tenant_id_from_jwt(request)
        try:
            total_schedule = Schedule.objects.filter(tenant_id=tenant_id).count()
            logger.info(f"[Tenant {tenant_id}] Retrieved schedule stats: {total_schedule} schedules")
            return Response({"total_schedule": total_schedule})
        except Exception as e:
            logger.error(f"[Tenant {tenant_id}] Error fetching schedule stats: {str(e)}", exc_info=True)
            return Response({"detail": "Error fetching schedule stats"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], url_path='all', permission_classes=[IsAuthenticated])
    def all_schedules(self, request):
        tenant_id = get_tenant_id_from_jwt(request)
        user_id = request.jwt_payload.get('user', {}).get('id')
        try:
            user_response = requests.get(
                f'{settings.AUTH_SERVICE_URL}/api/user/users/{user_id}/',
                headers={'Authorization': f'Bearer {request.META.get("HTTP_AUTHORIZATION", "").split(" ")[1]}'}
            )
            if user_response.status_code == 200 and user_response.json().get('role') != 'admin':
                logger.warning(f"[Tenant {tenant_id}] User {user_id} not authorized for all_schedules")
                return Response({'detail': 'Not authorized.'}, status=status.HTTP_403_FORBIDDEN)
            queryset = Schedule.objects.filter(tenant_id=tenant_id).order_by('-start_time')
            serializer = self.get_serializer(queryset, many=True)
            logger.info(f"[Tenant {tenant_id}] Admin {user_id} retrieved all schedules: {len(serializer.data)} found")
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"[Tenant {tenant_id}] Error fetching all schedules: {str(e)}", exc_info=True)
            return Response({"detail": "Error fetching all schedules"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        tenant_id = get_tenant_id_from_jwt(request)
        user_id = request.jwt_payload.get('user', {}).get('id')
        try:
            with transaction.atomic():
                schedule = self.get_object()
                participant, created = ScheduleParticipant.objects.get_or_create(
                    schedule=schedule,
                    user_id=user_id
                )
                participant.read = True
                participant.save(update_fields=['read'])
                ActivityLog.objects.create(
                    tenant_id=tenant_id,
                    tenant_name=schedule.tenant_name,
                    user_id=user_id,
                    activity_type='schedule_read',
                    details=f'Marked schedule "{schedule.title}" as read',
                    status='success'
                )
                logger.info(f"[Tenant {tenant_id}] Schedule marked as read: {schedule.title} by user {user_id}")
                return Response({'detail': 'Schedule marked as read.'}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"[Tenant {tenant_id}] Error marking schedule as read: {str(e)}", exc_info=True)
            return Response({"detail": "Error marking schedule as read"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'])
    def download_attachment(self, request, pk=None):
        tenant_id = get_tenant_id_from_jwt(request)
        return Response({'detail': 'Attachments not supported in this version.'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['get'])
    def join_meeting(self, request, pk=None):
        tenant_id = get_tenant_id_from_jwt(request)
        try:
            schedule = self.get_object()
            if schedule.location:
                logger.info(f"[Tenant {tenant_id}] Retrieved meeting link for schedule {schedule.id}")
                return Response({'meeting_link': schedule.location}, status=status.HTTP_200_OK)
            logger.warning(f"[Tenant {tenant_id}] No meeting link found for schedule {schedule.id}")
            return Response({'detail': 'No meeting link found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"[Tenant {tenant_id}] Error fetching meeting link: {str(e)}", exc_info=True)
            return Response({"detail": "Error fetching meeting link"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)