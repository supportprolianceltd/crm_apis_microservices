from django.db import transaction
from rest_framework import viewsets, generics, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Q
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import logging
import requests
from django.conf import settings
from .models import Message, MessageRecipient, MessageAttachment, MessageType
from .serializers import MessageSerializer, MessageAttachmentSerializer, MessageTypeSerializer, get_tenant_id_from_jwt
from activitylog.models import ActivityLog
from utils.storage import get_storage_service
logger = logging.getLogger('messaging')
channel_layer = get_channel_layer()

class TenantBaseView(viewsets.ViewSetMixin, generics.GenericAPIView):
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        jwt_payload = getattr(request, 'jwt_payload', {})
        tenant_id = jwt_payload.get('tenant_unique_id')
        if not tenant_id:
            logger.error("No tenant_unique_id in JWT payload")
            raise serializers.ValidationError("Tenant ID not found in token.")
        logger.debug(f"[Tenant {tenant_id}] Schema set for request")

class MessageTypeViewSet(TenantBaseView):
    serializer_class = MessageTypeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return MessageType.objects.none()
        tenant_id = get_tenant_id_from_jwt(self.request)
        return MessageType.objects.filter(tenant_id=tenant_id)

    def list(self, request, *args, **kwargs):
        tenant_id = get_tenant_id_from_jwt(request)
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        logger.info(f"[Tenant {tenant_id}] Listed message types, count: {len(serializer.data)}")
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        tenant_id = get_tenant_id_from_jwt(request)
        serializer = self.get_serializer(data=request.data, context={'request': request})
        try:
            if serializer.is_valid():
                serializer.save()
                logger.info(f"[Tenant {tenant_id}] MessageType created")
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            logger.error(f"[Tenant {tenant_id}] Validation failed for MessageType creation: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except serializers.ValidationError as e:
            logger.error(f"[Tenant {tenant_id}] Validation error for MessageType creation: {e.detail}")
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, *args, **kwargs):
        tenant_id = get_tenant_id_from_jwt(request)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        logger.info(f"[Tenant {tenant_id}] MessageType {instance.id} updated")
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        tenant_id = get_tenant_id_from_jwt(request)
        instance = self.get_object()
        self.perform_destroy(instance)
        logger.info(f"[Tenant {tenant_id}] MessageType {instance.id} deleted")
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def set_default(self, request, pk=None):
        tenant_id = get_tenant_id_from_jwt(request)
        instance = self.get_object()
        logger.info(f"[Tenant {tenant_id}] MessageType {instance.pk} set as default")
        return Response({"status": "default set"})

class MessageViewSet(TenantBaseView):
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Message.objects.none()
        user_id = self.request.jwt_payload.get('user', {}).get('id')
        tenant_id = get_tenant_id_from_jwt(self.request)
        return Message.objects.filter(
            tenant_id=tenant_id,
            recipients__in=MessageRecipient.objects.filter(
                Q(recipient_id=user_id) | Q(group_member_id=user_id),
                deleted=False
            )
        ).distinct().order_by("-sent_at")

    def list(self, request, *args, **kwargs):
        tenant_id = get_tenant_id_from_jwt(request)
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            logger.info(f"[Tenant {tenant_id}] Listed messages, count: {len(serializer.data)}")
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        logger.info(f"[Tenant {tenant_id}] Listed messages, count: {len(serializer.data)}")
        return Response(serializer.data)

    def get_serializer_context(self):
        return {"request": self.request}

    def create(self, request, *args, **kwargs):
        tenant_id = get_tenant_id_from_jwt(request)
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            message = serializer.save()
            ActivityLog.objects.create(
                tenant_id=tenant_id,
                tenant_name=message.tenant_name,
                user_id=request.jwt_payload.get('user', {}).get('id'),
                activity_type="message_sent",
                details=f"Sent '{message.subject}'",
                status="success"
            )
            transaction.on_commit(lambda: self._notify_recipients(message))
        logger.info(f"[Tenant {tenant_id}] Message created: {message.subject}")
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def _notify_recipients(self, message):
        recipients = set()
        for mr in message.recipients.all():
            if mr.recipient_id:
                recipients.add(mr.recipient_id)
            if mr.recipient_group_id and mr.group_member_id:
                recipients.add(mr.group_member_id)
        message_data = MessageSerializer(message, context=self.get_serializer_context()).data
        tenant_id = get_tenant_id_from_jwt(self.request)
        for user_id in recipients:
            async_to_sync(channel_layer.group_send)(
                f"{tenant_id}_user_{user_id}",
                {
                    "type": "new_message",
                    "message": message_data
                }
            )

    @action(detail=False, methods=['get'], url_path='unread_count')
    def unread_count(self, request):
        tenant_id = get_tenant_id_from_jwt(request)
        user_id = request.jwt_payload.get('user', {}).get('id')
        count = Message.objects.filter(
            tenant_id=tenant_id,
            recipients__recipient_id=user_id,
            recipients__read=False
        ).count()
        logger.info(f"[Tenant {tenant_id}] Unread message count for user {user_id}: {count}")
        return Response({'count': count})

    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        tenant_id = get_tenant_id_from_jwt(request)
        user_id = request.jwt_payload.get('user', {}).get('id')
        total = Message.objects.filter(tenant_id=tenant_id, recipients__recipient_id=user_id).count()
        unread = Message.objects.filter(
            tenant_id=tenant_id,
            recipients__recipient_id=user_id,
            recipients__read=False
        ).count()
        sent = Message.objects.filter(tenant_id=tenant_id, sender_id=user_id).count()
        logger.info(f"[Tenant {tenant_id}] Message stats for user {user_id}: total={total}, unread={unread}, sent={sent}")
        return Response({
            'total': total,
            'unread': unread,
            'sent': sent
        })

    @action(detail=False, methods=['post'], url_path='send_to_group')
    def send_to_group(self, request):
        tenant_id = get_tenant_id_from_jwt(request)
        group_id = request.data.get('group_id')
        subject = request.data.get('subject')
        content = request.data.get('content')
        message_type_id = request.data.get('message_type')
        try:
            group_response = requests.get(
                f'{settings.AUTH_SERVICE_URL}/api/tenant/groups/{group_id}/',
                headers={'Authorization': f'Bearer {request.META.get("HTTP_AUTHORIZATION", "").split(" ")[1]}'}
            )
            if group_response.status_code != 200:
                raise serializers.ValidationError({"group_id": f"Invalid group ID: {group_id}"})
            group_data = group_response.json()
            if group_data.get('tenant_unique_id') != tenant_id:
                raise serializers.ValidationError({"group_id": f"Group {group_id} does not belong to tenant {tenant_id}"})
            message_type = MessageType.objects.get(id=message_type_id, tenant_id=tenant_id)
            user_id = request.jwt_payload.get('user', {}).get('id')
            message = Message.objects.create(
                tenant_id=tenant_id,
                sender_id=user_id,
                subject=subject,
                content=content,
                message_type=message_type,
                status='sent'
            )
            user_ids = group_data.get('members', [])
            recipients = [
                MessageRecipient(message=message, recipient_group_id=group_id, group_member_id=user_id)
                for user_id in user_ids
            ]
            MessageRecipient.objects.bulk_create(recipients)
            ActivityLog.objects.create(
                tenant_id=tenant_id,
                user_id=user_id,
                activity_type="message_sent_to_group",
                details=f"Sent '{subject}' to group {group_id}",
                status="success"
            )
            logger.info(f"[Tenant {tenant_id}] Message sent to group {group_id}")
            return Response({'message': 'Message sent to group.'}, status=status.HTTP_201_CREATED)
        except MessageType.DoesNotExist:
            logger.error(f"[Tenant {tenant_id}] MessageType {message_type_id} not found")
            return Response({'error': 'MessageType not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"[Tenant {tenant_id}] Error sending message to group: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['patch'], url_path='mark_as_read')
    def mark_as_read(self, request, pk=None):
        tenant_id = get_tenant_id_from_jwt(request)
        user_id = request.jwt_payload.get('user', {}).get('id')
        try:
            message = self.get_object()
            MessageRecipient.objects.filter(
                message=message, recipient_id=user_id
            ).update(read=True, read_at=timezone.now())
            logger.info(f"[Tenant {tenant_id}] Message {pk} marked as read by user {user_id}")
            return Response({'status': 'marked as read'})
        except Message.DoesNotExist:
            logger.error(f"[Tenant {tenant_id}] Message {pk} not found")
            return Response({'error': 'Message not found'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['patch'], url_path='delete_for_user')
    def delete_for_user(self, request, pk=None):
        tenant_id = get_tenant_id_from_jwt(request)
        user_id = request.jwt_payload.get('user', {}).get('id')
        try:
            message = self.get_object()
            MessageRecipient.objects.filter(message=message, recipient_id=user_id).update(deleted=True)
            logger.info(f"[Tenant {tenant_id}] Message {pk} deleted for user {user_id}")
            return Response({'status': 'deleted for user'})
        except Message.DoesNotExist:
            logger.error(f"[Tenant {tenant_id}] Message {pk} not found")
            return Response({'error': 'Message not found'}, status=status.HTTP_404_NOT_FOUND)

class MessageAttachmentViewSet(TenantBaseView):
    serializer_class = MessageAttachmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return MessageAttachment.objects.none()
        tenant_id = get_tenant_id_from_jwt(self.request)
        return MessageAttachment.objects.filter(message__tenant_id=tenant_id)

    def get_serializer_context(self):
        return {"request": self.request}

    def create(self, request, *args, **kwargs):
        tenant_id = get_tenant_id_from_jwt(request)
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        logger.info(f"[Tenant {tenant_id}] MessageAttachment created")
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        tenant_id = get_tenant_id_from_jwt(request)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        logger.info(f"[Tenant {tenant_id}] MessageAttachment {instance.id} updated")
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        tenant_id = get_tenant_id_from_jwt(request)
        instance = self.get_object()
        storage_service = get_storage_service()
        if instance.file_url:
            storage_service.delete_file(instance.file_url)
        self.perform_destroy(instance)
        logger.info(f"[Tenant {tenant_id}] MessageAttachment {instance.id} deleted")
        return Response(status=status.HTTP_204_NO_CONTENT)