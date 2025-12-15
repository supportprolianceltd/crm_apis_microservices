import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from django.utils import timezone
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from rest_framework.pagination import PageNumberPagination
from .models import Event
from .serializers import EventSerializer
from django.conf import settings
logger = logging.getLogger(__name__)


class CustomPagination(PageNumberPagination):
    page_size = 20  # Adjust as needed

    def get_next_link(self):
        """Override to use gateway base URL."""
        if not self.page.has_next():
            return None
        gateway_url = getattr(settings, 'GATEWAY_URL', None)
        if not gateway_url:
            return super().get_next_link()  # Fallback to default

        request = self.request
        # Build base path from current request (e.g., /api/user/users/)
        path = request.path
        # Get query params, update 'page', preserve others
        query_params = request.query_params.copy()
        query_params['page'] = self.page.next_page_number()
        query_string = urlencode(query_params, doseq=True)

        # Reconstruct full URL with gateway scheme/host
        parsed_gateway = urlparse(gateway_url)
        full_url = f"{parsed_gateway.scheme}://{parsed_gateway.netloc}{path}?{query_string}"
        return full_url

    def get_previous_link(self):
        """Override to use gateway base URL."""
        if not self.page.has_previous():
            return None
        gateway_url = getattr(settings, 'GATEWAY_URL', None)
        if not gateway_url:
            return super().get_previous_link()  # Fallback to default

        request = self.request
        path = request.path
        query_params = request.query_params.copy()
        query_params['page'] = self.page.previous_page_number()
        query_string = urlencode(query_params, doseq=True)

        parsed_gateway = urlparse(gateway_url)
        full_url = f"{parsed_gateway.scheme}://{parsed_gateway.netloc}{path}?{query_string}"
        return full_url

    def get_paginated_response(self, data):
        """Ensure the full response uses overridden links."""
        response = super().get_paginated_response(data)
        gateway_url = getattr(settings, 'GATEWAY_URL', None)
        if gateway_url:
            response['next'] = self.get_next_link()
            response['previous'] = self.get_previous_link()
        return response



class EventViewSet(viewsets.ModelViewSet):
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    def get_queryset(self):
        tenant = self.request.user.tenant
        user = self.request.user

        # Admins see all events, regular users see only their own events or public events
        if user.role in ['root-admin', 'co-admin', 'admin', 'staff']:
            return Event.objects.filter(tenant=tenant).select_related('creator')
        else:
            return Event.objects.filter(
                Q(tenant=tenant) & (
                    Q(creator=user) |
                    Q(participants=user) |
                    Q(visibility='public')
                )
            ).distinct().select_related('creator')


    @action(detail=False, methods=['get'], url_path='my_events')
    def my_events(self, request):
        """Get events created by the current user."""
        user = request.user
        tenant = user.tenant
        events = Event.objects.filter(creator=user, tenant=tenant)
        serializer = self.get_serializer(events, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='my_invitations')
    def my_invitations(self, request):
        """Get events where the user is invited (participant)."""
        user = request.user
        tenant = user.tenant
        events = Event.objects.filter(
            participants=user,
            tenant=tenant
        ).exclude(creator=user).distinct()
        serializer = self.get_serializer(events, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='public_events')
    def public_events(self, request):
        """Get all public events in the tenant."""
        user = request.user
        tenant = user.tenant
        events = Event.objects.filter(
            visibility='public',
            tenant=tenant
        )
        serializer = self.get_serializer(events, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='dashboard')
    def dashboard(self, request):
        """Get event dashboard metrics."""
        user = request.user
        tenant = user.tenant

        # Get metrics
        total_events = Event.objects.filter(tenant=tenant).count()
        upcoming_events = Event.objects.filter(
            tenant=tenant,
            start_datetime__gte=timezone.now()
        ).count()
        past_events = total_events - upcoming_events

        public_events = Event.objects.filter(
            tenant=tenant,
            visibility='public'
        ).count()

        private_events = Event.objects.filter(
            tenant=tenant,
            visibility='private'
        ).count()

        specific_user_events = Event.objects.filter(
            tenant=tenant,
            visibility='specific_users'
        ).count()

        # Count total participants across all events
        total_participants = 0
        events_with_participants = Event.objects.filter(tenant=tenant)
        for event in events_with_participants:
            total_participants += event.participants.count()

        avg_participants = round(total_participants / total_events, 2) if total_events > 0 else 0

        # Get upcoming events list
        upcoming_events_list = Event.objects.filter(
            tenant=tenant,
            start_datetime__gte=timezone.now()
        ).order_by('start_datetime')[:5]

        upcoming_events_data = []
        for event in upcoming_events_list:
            upcoming_events_data.append({
                'id': str(event.id),
                'title': event.title,
                'start_datetime': event.start_datetime.isoformat(),
                'participant_count': event.participants.count(),
                'creator_name': f"{event.creator.first_name} {event.creator.last_name}"
            })

        # Event types breakdown
        event_types = {
            'public': public_events,
            'private': private_events,
            'specific_users': specific_user_events
        }

        # Monthly creation stats (simplified)
        monthly_stats = Event.objects.filter(
            tenant=tenant,
            created_at__year=timezone.now().year,
            created_at__month=timezone.now().month
        ).count()

        response_data = {
            'metrics': {
                'total_events': total_events,
                'upcoming_events': upcoming_events,
                'past_events': past_events,
                'public_events': public_events,
                'private_events': private_events,
                'specific_user_events': specific_user_events,
                'total_participants': total_participants,
                'average_participants_per_event': avg_participants,
                'events_this_month': monthly_stats
            },
            'upcoming_events': upcoming_events_data,
            'event_types_breakdown': event_types,
            'monthly_event_creation': [{
                'month': timezone.now().strftime('%Y-%m'),
                'count': monthly_stats
            }]
        }

        return Response(response_data)

    @action(detail=False, methods=['get'], url_path='calendar')
    def calendar(self, request):
        """Get events formatted for calendar display."""
        queryset = self.get_queryset()
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        if start_date:
            queryset = queryset.filter(start_datetime__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(end_datetime__date__lte=end_date)

        events_data = []
        for event in queryset:
            events_data.append({
                'id': str(event.id),
                'title': event.title,
                'start': event.start_datetime.isoformat(),
                'end': event.end_datetime.isoformat(),
                'location': event.location,
                'description': event.description,
                'visibility': event.visibility,
                'creator': {
                    'id': event.creator.id,
                    'name': f"{event.creator.first_name} {event.creator.last_name}",
                    'email': event.creator.email
                },
                'participants': [
                    {
                        'id': p.id,
                        'name': f"{p.first_name} {p.last_name}",
                        'email': p.email
                    } for p in event.participants.all()
                ],
                'is_creator': event.creator == request.user,
                'is_participant': request.user in event.participants.all(),
                'can_edit': event.creator == request.user,
                'backgroundColor': '#3788d8' if event.visibility == 'public' else '#28a745' if event.creator == request.user else '#6c757d',
                'borderColor': '#3788d8' if event.visibility == 'public' else '#28a745' if event.creator == request.user else '#6c757d',
                'textColor': '#ffffff'
            })

        return Response({'events': events_data})

    @action(detail=True, methods=['post'], url_path='add-participants')
    def add_participants(self, request, pk=None):
        """Add participants to an event."""
        event = self.get_object()
        if event.creator != request.user:
            return Response(
                {"detail": "Only the event creator can add participants."},
                status=status.HTTP_403_FORBIDDEN
            )

        user_ids = request.data.get('user_ids', [])
        if not user_ids:
            return Response(
                {"detail": "user_ids list is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        from users.models import CustomUser
        tenant = request.user.tenant
        users_to_add = CustomUser.objects.filter(id__in=user_ids, tenant=tenant)
        event.participants.add(*users_to_add)

        serializer = self.get_serializer(event)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        """Delete an event - only the creator can delete."""
        event = self.get_object()
        logger.info(f"User {request.user.id} ({request.user.email}) attempting to delete event {event.id} created by {event.creator.id} ({event.creator.email})")
        if event.creator != request.user:
            logger.warning(f"Unauthorized delete attempt: User {request.user.id} tried to delete event {event.id} created by {event.creator.id}")
            return Response(
                {"detail": "Only the event creator can delete this event."},
                status=status.HTTP_403_FORBIDDEN
            )
        logger.info(f"Authorized delete: User {request.user.id} deleting their event {event.id}")
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'], url_path='remove-participants')
    def remove_participants(self, request, pk=None):
        """Remove participants from an event."""
        event = self.get_object()
        if event.creator != request.user:
            return Response(
                {"detail": "Only the event creator can remove participants."},
                status=status.HTTP_403_FORBIDDEN
            )

        user_ids = request.data.get('user_ids', [])
        if not user_ids:
            return Response(
                {"detail": "user_ids list is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        from users.models import CustomUser
        tenant = request.user.tenant
        users_to_remove = CustomUser.objects.filter(id__in=user_ids, tenant=tenant)
        event.participants.remove(*users_to_remove)

        serializer = self.get_serializer(event)
        return Response(serializer.data)