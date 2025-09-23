from rest_framework import viewsets, permissions, status, serializers
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import Forum, ForumPost, ModerationQueue
from .serializers import ForumSerializer, ForumPostSerializer, ModerationQueueSerializer, get_tenant_id_from_jwt
from django.db.models import Prefetch, Count
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from activitylog.models import ActivityLog
from activitylog.serializers import ActivityLogSerializer
import logging
from django.utils import timezone

logger = logging.getLogger('forum')

# Assuming TenantBaseView is defined in your project
from messaging.views import TenantBaseView  # Adjust import based on your structure

class ForumViewSet(TenantBaseView):
    queryset = Forum.objects.prefetch_related('posts')
    serializer_class = ForumSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [IsAdminUser()]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Forum.objects.none()
        tenant_id = self.request.jwt_payload.get('tenant_unique_id')
        if not tenant_id:
            logger.error("No tenant_unique_id in JWT payload")
            raise serializers.ValidationError("Tenant ID not found in token.")
        return Forum.objects.filter(tenant_id=tenant_id)

    def perform_create(self, serializer):
        serializer.save()

    def perform_update(self, serializer):
        serializer.save()

    def perform_destroy(self, instance):
        instance.delete()

    @action(detail=False, methods=['get'])
    def stats(self, request):
        tenant_id = request.jwt_payload.get('tenant_unique_id')
        active_forums = Forum.objects.filter(tenant_id=tenant_id, is_active=True).count()
        total_posts = ForumPost.objects.filter(tenant_id=tenant_id).count()
        logger.info(f"[Tenant {tenant_id}] Forum stats: active_forums={active_forums}, total_posts={total_posts}")
        return Response({
            'active_forums': active_forums,
            'total_posts': total_posts
        })

class ForumPostViewSet(TenantBaseView):
    queryset = ForumPost.objects.all()
    serializer_class = ForumPostSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ['update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [IsAdminUser()]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ForumPost.objects.none()
        tenant_id = self.request.jwt_payload.get('tenant_unique_id')
        if not tenant_id:
            logger.error("No tenant_unique_id in JWT payload")
            raise serializers.ValidationError("Tenant ID not found in token.")
        return ForumPost.objects.filter(tenant_id=tenant_id)

    def perform_create(self, serializer):
        serializer.save()

    def perform_update(self, serializer):
        serializer.save(moderated_at=timezone.now())

class ModerationQueueViewSet(TenantBaseView):
    queryset = ModerationQueue.objects.all()
    serializer_class = ModerationQueueSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ['create', 'list', 'retrieve']:
            return [IsAuthenticated()]
        return [IsAdminUser()]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ModerationQueue.objects.none()
        tenant_id = self.request.jwt_payload.get('tenant_unique_id')
        if not tenant_id:
            logger.error("No tenant_unique_id in JWT payload")
            raise serializers.ValidationError("Tenant ID not found in token.")
        return ModerationQueue.objects.filter(tenant_id=tenant_id)

    def perform_create(self, serializer):
        serializer.save()

    def perform_update(self, serializer):
        serializer.save(moderated_at=timezone.now())

    @action(detail=True, methods=['patch'])
    def moderate(self, request, pk=None):
        tenant_id = request.jwt_payload.get('tenant_unique_id')
        item = self.get_object()
        action = request.data.get('action')
        moderation_notes = request.data.get('moderation_notes', '')

        if action not in ['approve', 'reject']:
            logger.error(f"[Tenant {tenant_id}] Invalid moderation action: {action}")
            return Response({'error': 'Invalid action'}, status=status.HTTP_400_BAD_REQUEST)

        item.status = 'approved' if action == 'approve' else 'rejected'
        item.moderation_notes = moderation_notes
        item.moderated_by_id = request.jwt_payload.get('user', {}).get('id')
        item.save()

        # Update related content (e.g., ForumPost)
        if item.content_type == 'forum_post':
            try:
                post = ForumPost.objects.get(id=item.content_id, tenant_id=tenant_id)
                post.is_approved = (action == 'approve')
                post.moderated_by_id = item.moderated_by_id
                post.moderated_at = timezone.now()
                post.save()
                logger.info(f"[Tenant {tenant_id}] ForumPost {post.id} {action}d")
            except ForumPost.DoesNotExist:
                logger.warning(f"[Tenant {tenant_id}] ForumPost {item.content_id} not found for moderation")

        logger.info(f"[Tenant {tenant_id}] ModerationQueue {item.id} {action}d by user {item.moderated_by_id}")
        return Response({'status': f'Content {action}d successfully'})

    @action(detail=False, methods=['get'])
    def pending_count(self, request):
        tenant_id = request.jwt_payload.get('tenant_unique_id')
        count = ModerationQueue.objects.filter(tenant_id=tenant_id, status='pending').count()
        logger.info(f"[Tenant {tenant_id}] Pending moderation items: {count}")
        return Response({'count': count})