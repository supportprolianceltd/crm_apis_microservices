import logging
from django.db import transaction
from rest_framework import viewsets, status, serializers
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.http import Http404
from .models import ChatSession, ChatMessage
from .serializers import ChatSessionSerializer, ChatMessageSerializer, get_tenant_id_from_jwt

logger = logging.getLogger('ai_chat')

class ChatSessionViewSet(viewsets.ModelViewSet):
    serializer_class = ChatSessionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ChatSession.objects.none()
        jwt_payload = getattr(self.request, 'jwt_payload', {})
        tenant_id = jwt_payload.get('tenant_unique_id')
        user_id = jwt_payload.get('user', {}).get('id')
        if not tenant_id or not user_id:
            logger.error("No tenant_unique_id or user_id in JWT payload")
            raise serializers.ValidationError("Tenant ID or user ID not found in token.")
        # Schema is set by CustomTenantSchemaMiddleware
        return ChatSession.objects.filter(
            tenant_id=tenant_id,
            user_id=user_id
        ).order_by("-created_at")

    def list(self, request, *args, **kwargs):
        tenant_id = request.jwt_payload.get('tenant_unique_id')
        try:
            queryset = self.get_queryset()
            serializer = self.get_serializer(queryset, many=True)
            logger.info(f"[Tenant {tenant_id}] Listed chat sessions, count: {len(serializer.data)}")
            return Response({"sessions": serializer.data})
        except Exception as e:
            logger.error(f"[Tenant {tenant_id}] Error listing chat sessions: {str(e)}", exc_info=True)
            return Response({"detail": "Error fetching chat sessions"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def create(self, request, *args, **kwargs):
        tenant_id = request.jwt_payload.get('tenant_unique_id')
        serializer = self.get_serializer(data=request.data, context={'request': request})
        try:
            serializer.is_valid(raise_exception=True)
        except serializers.ValidationError as e:
            logger.error(f"[Tenant {tenant_id}] ChatSession creation validation failed: {str(e)}")
            raise
        with transaction.atomic():
            session = serializer.save()
            logger.info(f"[Tenant {tenant_id}] ChatSession created: {session.title} for user {session.user_id}")
        return Response({"session": serializer.data}, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        tenant_id = request.jwt_payload.get('tenant_unique_id')
        try:
            session = get_object_or_404(self.get_queryset(), pk=pk)
            serializer = self.get_serializer(session)
            logger.info(f"[Tenant {tenant_id}] Retrieved chat session: {session.title} for user {session.user_id}")
            return Response(serializer.data)
        except Http404:
            logger.warning(f"[Tenant {tenant_id}] ChatSession not found for id: {pk}")
            return Response({"detail": "Chat session not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"[Tenant {tenant_id}] Error retrieving chat session: {str(e)}", exc_info=True)
            return Response({"detail": "Error retrieving chat session"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def destroy(self, request, pk=None):
        tenant_id = request.jwt_payload.get('tenant_unique_id')
        try:
            with transaction.atomic():
                session = get_object_or_404(self.get_queryset(), pk=pk)
                session.delete()
                logger.info(f"[Tenant {tenant_id}] ChatSession deleted: {session.title} for user {session.user_id}")
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Http404:
            logger.warning(f"[Tenant {tenant_id}] ChatSession not found for id: {pk}")
            return Response({"detail": "Chat session not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"[Tenant {tenant_id}] Error deleting chat session: {str(e)}", exc_info=True)
            return Response({"detail": "Error deleting chat session"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ChatMessageViewSet(viewsets.ModelViewSet):
    serializer_class = ChatMessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ChatMessage.objects.none()
        jwt_payload = getattr(self.request, 'jwt_payload', {})
        tenant_id = jwt_payload.get('tenant_unique_id')
        user_id = jwt_payload.get('user', {}).get('id')
        session_id = self.kwargs.get("session_pk")
        if not tenant_id or not user_id or not session_id:
            logger.error("Missing tenant_unique_id, user_id, or session_pk in request")
            raise serializers.ValidationError("Tenant ID, user ID, or session ID not found.")
        return ChatMessage.objects.filter(
            tenant_id=tenant_id,
            session__id=session_id,
            session__user_id=user_id
        ).order_by("timestamp")

    def list(self, request, session_pk=None):
        tenant_id = request.jwt_payload.get('tenant_unique_id')
        try:
            queryset = self.get_queryset()
            serializer = self.get_serializer(queryset, many=True)
            logger.info(f"[Tenant {tenant_id}] Listed chat messages for session {session_pk}, count: {len(serializer.data)}")
            return Response({"messages": serializer.data})
        except Exception as e:
            logger.error(f"[Tenant {tenant_id}] Error listing chat messages for session {session_pk}: {str(e)}", exc_info=True)
            return Response({"detail": "Error fetching chat messages"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def create(self, request, session_pk=None):
        tenant_id = request.jwt_payload.get('tenant_unique_id')
        try:
            with transaction.atomic():
                session = get_object_or_404(
                    ChatSession.objects.filter(
                        tenant_id=tenant_id,
                        user_id=request.jwt_payload.get('user', {}).get('id')
                    ),
                    pk=session_pk
                )
                serializer = self.get_serializer(data=request.data, context={'request': request})
                serializer.is_valid(raise_exception=True)
                serializer.validated_data['tenant_id'] = tenant_id
                serializer.validated_data['tenant_name'] = session.tenant_name
                message = serializer.save(session=session)
                logger.info(f"[Tenant {tenant_id}] ChatMessage created in session {session_pk} by {message.sender}")
                return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Http404:
            logger.warning(f"[Tenant {tenant_id}] ChatSession not found for id: {session_pk}")
            return Response({"detail": "Chat session not found"}, status=status.HTTP_404_NOT_FOUND)
        except serializers.ValidationError as e:
            logger.error(f"[Tenant {tenant_id}] ChatMessage creation validation failed: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"[Tenant {tenant_id}] Error creating chat message: {str(e)}", exc_info=True)
            return Response({"detail": "Error creating chat message"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)