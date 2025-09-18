from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
# Create your views here.
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Notification

class NotificationListView(APIView):
    def get(self, request, tenant_id, user_id):
        notifications = Notification.objects.filter(tenant_id=tenant_id, user_id=user_id)
        data = [{"title": n.title, "message": n.message, "is_read": n.is_read} for n in notifications]
        return Response(data)


class NotificationTestView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"message": "Hello from notifications API!"})
