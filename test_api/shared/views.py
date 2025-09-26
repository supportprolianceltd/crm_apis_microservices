from django.shortcuts import render

# Create your views here.
# views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import TenantSerializer
import logging

logger = logging.getLogger(__name__)

class TenantCreateView(APIView):
    """
    POST /api/tenants/
    Creates a new tenant and schema.
    """
    def post(self, request, *args, **kwargs):
        serializer = TenantSerializer(data=request.data, context={"request": request})

        if serializer.is_valid():
            try:
                tenant = serializer.save()
                return Response({
                    "message": "Tenant created successfully.",
                    "tenant": TenantSerializer(tenant).data
                }, status=status.HTTP_201_CREATED)
            except Exception as e:
                logger.exception("Failed to create tenant.")
                return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        logger.error(f"Tenant creation validation failed: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
