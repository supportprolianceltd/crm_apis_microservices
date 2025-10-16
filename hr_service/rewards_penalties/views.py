




# hr/rewards_penalties/views.py
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
from django.db import close_old_connections
from django.utils import timezone
import logging
from .models import Reward, Penalty, Status
from .serializers import RewardSerializer, PenaltySerializer, get_user_data_from_jwt
from rest_framework.pagination import PageNumberPagination
from django.conf import settings
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode



logger = logging.getLogger('hr_rewards_penalties')


class CustomPagination(PageNumberPagination):
    page_size = 50  # Adjust as needed

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


class RewardListCreateView(generics.ListCreateAPIView):
    serializer_class = RewardSerializer
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['status', 'type', 'is_public']
    search_fields = ['reason', 'description', 'employee_details__first_name', 'employee_details__last_name']

    def get_queryset(self):
        close_old_connections()
        if getattr(self, "swagger_fake_view", False):
            return Reward.objects.none()
        jwt_payload = getattr(self.request, 'jwt_payload', {})
        tenant_id = jwt_payload.get('tenant_unique_id')
        if not tenant_id:
            logger.error("No tenant_id in token")
            return Reward.objects.none()
        return Reward.objects.filter(tenant_id=tenant_id)

    def perform_create(self, serializer):
        close_old_connections()
        serializer.save()

    def perform_update(self, serializer):
        close_old_connections()
        if 'status' in serializer.validated_data and serializer.validated_data['status'] == Status.APPROVED.value:
            user_data = get_user_data_from_jwt(self.request)
            serializer.save(
                approver_id=user_data['id'],
                approver_details=user_data,
                approval_date=timezone.now(),
                updated_by_id=user_data['id'],
                updated_by_details=user_data
            )
        else:
            super().perform_update(serializer)

class PenaltyListCreateView(generics.ListCreateAPIView):
    serializer_class = PenaltySerializer
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['status', 'type', 'severity_level']
    search_fields = ['reason', 'description', 'employee_details__first_name', 'employee_details__last_name', 'legal_compliance_notes']

    def get_queryset(self):
        close_old_connections()
        if getattr(self, "swagger_fake_view", False):
            return Penalty.objects.none()
        jwt_payload = getattr(self.request, 'jwt_payload', {})
        tenant_id = jwt_payload.get('tenant_unique_id')
        if not tenant_id:
            logger.error("No tenant_id in token")
            return Penalty.objects.none()
        return Penalty.objects.filter(tenant_id=tenant_id)

    def perform_create(self, serializer):
        close_old_connections()
        serializer.save()

    def perform_update(self, serializer):
        close_old_connections()
        if 'status' in serializer.validated_data and serializer.validated_data['status'] == Status.ISSUED.value:
            user_data = get_user_data_from_jwt(self.request)
            serializer.save(
                approver_id=user_data['id'],
                approver_details=user_data,
                approval_date=timezone.now(),
                updated_by_id=user_data['id'],
                updated_by_details=user_data
            )
        else:
            super().perform_update(serializer)




class RewardRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = RewardSerializer
    lookup_field = 'id'  # Use the 'id' field (CharField PK) for URL lookup, e.g., /rewards/PRO-R-0001/

    def get_queryset(self):
        # close_old_connections()
        if getattr(self, "swagger_fake_view", False):
            return Reward.objects.none()
        jwt_payload = getattr(self.request, 'jwt_payload', {})
        tenant_id = jwt_payload.get('tenant_unique_id')
        if not tenant_id:
            logger.error("No tenant_id in token")
            return Reward.objects.none()
        return Reward.objects.filter(tenant_id=tenant_id)

    def perform_update(self, serializer):
        # close_old_connections()
        if 'status' in serializer.validated_data and serializer.validated_data['status'] == Status.APPROVED.value:
            user_data = get_user_data_from_jwt(self.request)
            serializer.save(
                approver_id=user_data['id'],
                approver_details=user_data,
                approval_date=timezone.now(),
                updated_by_id=user_data['id'],
                updated_by_details=user_data
            )
        else:
            super().perform_update(serializer)

    def perform_destroy(self, instance):
        # close_old_connections()
        instance.soft_delete()  # Use the model's soft delete instead of hard delete
        return Response(status=status.HTTP_204_NO_CONTENT)
    




class PenaltyRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PenaltySerializer
    lookup_field = 'id'  # Use the 'id' field (CharField PK) for URL lookup, e.g., /penalties/PRO-P-0001/

    def get_queryset(self):
        # close_old_connections()
        if getattr(self, "swagger_fake_view", False):
            return Penalty.objects.none()
        jwt_payload = getattr(self.request, 'jwt_payload', {})
        tenant_id = jwt_payload.get('tenant_unique_id')
        if not tenant_id:
            logger.error("No tenant_id in token")
            return Penalty.objects.none()
        return Penalty.objects.filter(tenant_id=tenant_id)

    def perform_update(self, serializer):
        # close_old_connections()
        if 'status' in serializer.validated_data and serializer.validated_data['status'] == Status.ISSUED.value:
            user_data = get_user_data_from_jwt(self.request)
            serializer.save(
                approver_id=user_data['id'],
                approver_details=user_data,
                approval_date=timezone.now(),
                updated_by_id=user_data['id'],
                updated_by_details=user_data
            )
        else:
            super().perform_update(serializer)

    def perform_destroy(self, instance):
        # close_old_connections()
        instance.soft_delete()  # Use the model's soft delete instead of hard delete
        return Response(status=status.HTTP_204_NO_CONTENT)