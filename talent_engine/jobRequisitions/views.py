import logging
import jwt
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import JobRequisition
import logging
import requests
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
import logging

from .models import JobRequisition
from .serializers import PublicJobRequisitionSerializer

logger = logging.getLogger(__name__)
logger = logging.getLogger('talent_engine')
import uuid
from django.conf import settings
from django.db import connection, models, transaction
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
 # removed tenant_context import
from drf_spectacular.utils import extend_schema, OpenApiParameter, extend_schema_field
from rest_framework import generics, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter

from rest_framework.response import Response
from rest_framework.views import APIView
from utils.fetch_auth_data import fetch_tenants, fetch_branches
from utils.supabase import upload_file_dynamic
from rest_framework.pagination import PageNumberPagination
from .models import (
    JobRequisition,Request,
    VideoSession,
    Participant,
)
from .serializers import JobRequisitionSerializer,  ComplianceItemSerializer,VideoSessionSerializer, JobRequisitionBulkCreateSerializer, ParticipantSerializer, RequestSerializer, PublicJobRequisitionSerializer
from .permissions import IsMicroserviceAuthenticated


from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from .models import JobRequisition
from .serializers import PublicJobRequisitionSerializer
import logging

logger = logging.getLogger('talent_engine')

def get_tenant_id_from_jwt(request):
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        raise ValidationError('No valid Bearer token provided.')
    token = auth_header.split(' ')[1]
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        return payload.get('tenant_unique_id')
    except Exception:
        raise ValidationError('Invalid JWT token.')


class CustomPagination(PageNumberPagination):
    page_size = 20

class PublicPublishedJobRequisitionsView(APIView):
    permission_classes = []  # No authentication required
    pagination_class = CustomPagination

    def get(self, request):
        today = timezone.now().date()
        queryset = JobRequisition.active_objects.filter(
            publish_status=True,
            is_deleted=False,
            deadline_date=today
        )
        serializer = PublicJobRequisitionSerializer(queryset, many=True)
        logger.info(f"Public requisitions fetched: {queryset.count()}")
        return Response({
            "count": queryset.count(),
            "results": serializer.data
        }, status=status.HTTP_200_OK)  



class PublicPublishedRequisitionsByTenantView(APIView):
    permission_classes = []  # Public

    def get_tenant_info(self, tenant_unique_id):
        """
        Call the auth-service to fetch tenant info using unique_id.
        """
        try:
            url = f"{settings.AUTH_SERVICE_URL}/api/tenant/public/{tenant_unique_id}/"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Auth-service returned {response.status_code} for tenant ID {tenant_unique_id}")
                return None
        except requests.RequestException as e:
            logger.error(f"Failed to fetch tenant info from auth-service: {e}")
            return None

    def get(self, request, tenant_unique_id):
        try:
            today = timezone.now().date()

            # Fetch job requisitions for this tenant
            queryset = JobRequisition.active_objects.filter(
                tenant_id=tenant_unique_id,
                publish_status=True,
                status='open',
                is_deleted=False,
                # deadline_date__gte=today
            )
            requisitions_data = PublicJobRequisitionSerializer(queryset, many=True).data

            # Fetch tenant metadata from auth-service
            tenant_info = self.get_tenant_info(tenant_unique_id)

            logger.info(f"Fetched {len(requisitions_data)} public requisitions for tenant {tenant_unique_id}")

            return Response({
                "tenant": tenant_info,
                "count": len(requisitions_data),
                "results": requisitions_data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error fetching requisitions for tenant {tenant_unique_id}: {str(e)}")
            return Response({"detail": "An error occurred."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PublicCloseJobRequisitionView(APIView):
    permission_classes = []  # No authentication required

    def post(self, request, job_requisition_id):
        try:
            job_req = JobRequisition.active_objects.get(id=job_requisition_id)
            job_req.status = 'closed'
            job_req.save(update_fields=['status', 'updated_at'])
            logger.info(f"JobRequisition {job_requisition_id} status changed to closed (public endpoint)")
            return Response({
                "detail": f"Job requisition {job_requisition_id} status changed to closed.",
                "id": job_requisition_id,
                "status": job_req.status
            }, status=status.HTTP_200_OK)
        except JobRequisition.DoesNotExist:
            logger.warning(f"JobRequisition {job_requisition_id} not found for public close")
            return Response({"detail": "Job requisition not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error closing job requisition {job_requisition_id}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                         
# views.py
class PublicCloseJobRequisitionBatchView(APIView):
    permission_classes = []  # public endpoint

    def post(self, request):
        job_ids = request.data.get("job_requisition_ids", [])
        if not job_ids:
            return Response({"detail": "No job requisitions provided."}, status=status.HTTP_400_BAD_REQUEST)
        
        closed_jobs = []
        not_found_jobs = []

        for job_id in job_ids:
            try:
                job_req = JobRequisition.active_objects.get(id=job_id)
                job_req.status = 'closed'
                job_req.save(update_fields=['status', 'updated_at'])
                closed_jobs.append(job_id)
            except JobRequisition.DoesNotExist:
                not_found_jobs.append(job_id)
            except Exception as e:
                logger.error(f"Error closing job {job_id}: {str(e)}")

        return Response({
            "closed_jobs": closed_jobs,
            "not_found_jobs": not_found_jobs
        }, status=status.HTTP_200_OK)



class JobRequisitionBulkDeleteView(generics.GenericAPIView):
    serializer_class = JobRequisitionSerializer

    def post(self, request):
        ids = request.data.get('ids', [])
        if not ids:
            logger.warning("No IDs provided for bulk soft delete")
            return Response({"detail": "No IDs provided."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            jwt_payload = getattr(request, 'jwt_payload', {})
            tenant_id = jwt_payload.get('tenant_unique_id')
            role = jwt_payload.get('role')
            branch = jwt_payload.get('branch')
            if not tenant_id:
                return Response({"detail": "No tenant_id in token."}, status=status.HTTP_401_UNAUTHORIZED)
            queryset = JobRequisition.active_objects.filter(tenant_id=tenant_id, id__in=ids)
            if role == 'recruiter' and branch:
                queryset = queryset.filter(branch=branch)
            # Evaluate queryset before transaction block
            requisitions = list(queryset)
            count = len(requisitions)
            if count == 0:
                logger.warning("No active requisitions found for provided IDs")
                return Response({"detail": "No requisitions found."}, status=status.HTTP_404_NOT_FOUND)
            with transaction.atomic():
                for requisition in requisitions:
                    requisition.soft_delete()
            return Response({"detail": f"Soft-deleted {count} requisition(s)."}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Bulk soft delete failed: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MyJobRequisitionListView(generics.ListCreateAPIView):
    serializer_class = JobRequisitionSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    pagination_class = CustomPagination
    filterset_fields = ['status', 'role']
    search_fields = ['title', 'status', 'requested_by__email', 'role', 'interview_location']

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return JobRequisition.objects.none()
        jwt_payload = getattr(self.request, 'jwt_payload', {})
        tenant_id = str(jwt_payload.get('tenant_unique_id')) if jwt_payload.get('tenant_unique_id') is not None else None
        user_id = str(jwt_payload.get('user', {}).get('id')) if jwt_payload.get('user', {}).get('id') is not None else None
        role = jwt_payload.get('role')
        branch = jwt_payload.get('user', {}).get('branch')
        queryset = JobRequisition.active_objects.filter(
            tenant_id=tenant_id,
            requested_by_id=user_id
        )
        if role == 'recruiter' and branch:
            queryset = queryset.filter(branch=branch)
        return queryset
    


class PublishedJobRequisitionListView(generics.ListAPIView):
    serializer_class = JobRequisitionSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['status', 'role']
    search_fields = ['title', 'status', 'requested_by__email', 'role', 'interview_location']

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return JobRequisition.objects.none()
        jwt_payload = getattr(self.request, 'jwt_payload', {})
        tenant_id = jwt_payload.get('tenant_unique_id')
        role = jwt_payload.get('role')
        branch = jwt_payload.get('branch')
        queryset = JobRequisition.active_objects.filter(
            tenant_id=tenant_id,
            publish_status=True
        )
        if role == 'recruiter' and branch:
            queryset = queryset.filter(branch=branch)
        return queryset
    

# class JobRequisitionListCreateView(generics.ListCreateAPIView):
#     serializer_class = JobRequisitionSerializer
#     pagination_class = CustomPagination
#     # permission_classes removed; rely on custom JWT middleware
#     filter_backends = [DjangoFilterBackend, SearchFilter]
#     filterset_fields = ['status', 'role']
#     search_fields = ['title', 'status', 'requested_by__email', 'role', 'interview_location']

#     def get_queryset(self):
#         if getattr(self, "swagger_fake_view", False):
#             return JobRequisition.objects.none()
#         jwt_payload = getattr(self.request, 'jwt_payload', {})
#         tenant_id = jwt_payload.get('tenant_unique_id')
#         role = jwt_payload.get('role')
#         branch = jwt_payload.get('branch')
#         queryset = JobRequisition.active_objects.filter(tenant_id=tenant_id)
#         if role == 'recruiter' and branch:
#             queryset = queryset.filter(branch=branch)
#         return queryset
    
#         #Send notification to admin when job requisition is created
    
#     def perform_create(self, serializer):
#         jwt_payload = getattr(self.request, 'jwt_payload', {})
#         tenant_id = str(jwt_payload.get('tenant_unique_id')) if jwt_payload.get('tenant_unique_id') is not None else None
#         user_id = str(jwt_payload.get('user', {}).get('id')) if jwt_payload.get('user', {}).get('id') is not None else None
#         role = jwt_payload.get('role')
#         branch = jwt_payload.get('user', {}).get('branch')
#         if not tenant_id or not user_id:
#             logger.error("Missing tenant_unique_id or user_id in JWT payload")
#             raise serializers.ValidationError("Missing tenant_unique_id or user_id in token.")
#         serializer.save(
#             tenant_id=tenant_id,
#             requested_by_id=user_id,
#             branch=branch if role == 'recruiter' and branch else None
#         )
#         logger.info(f"Job requisition created: {serializer.validated_data['title']} for tenant {tenant_id} by user {user_id}")

class JobRequisitionListCreateView(generics.ListCreateAPIView):
    serializer_class = JobRequisitionSerializer
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['status', 'role']
    search_fields = ['title', 'status', 'requested_by__email', 'role', 'interview_location']

    def get_serializer_class(self):
        """
        Use different serializer for bulk create operations
        """
        if self.request.method == 'POST' and self.request.path.endswith('/bulk-create/'):
            return JobRequisitionBulkCreateSerializer
        return JobRequisitionSerializer

    def get_serializer(self, *args, **kwargs):
        """
        Override to handle bulk create with many=True
        """
        if self.request.method == 'POST' and self.request.path.endswith('/bulk-create/'):
            kwargs['many'] = True
        return super().get_serializer(*args, **kwargs)

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return JobRequisition.objects.none()
        jwt_payload = getattr(self.request, 'jwt_payload', {})
        tenant_id = jwt_payload.get('tenant_unique_id')
        role = jwt_payload.get('role')
        branch = jwt_payload.get('branch')
        queryset = JobRequisition.active_objects.filter(tenant_id=tenant_id)
        if role == 'recruiter' and branch:
            queryset = queryset.filter(branch=branch)
        return queryset

    def create(self, request, *args, **kwargs):
        """
        Handle both single and bulk create based on the endpoint
        """
        if request.path.endswith('/bulk-create/'):
            return self.bulk_create(request, *args, **kwargs)
        return super().create(request, *args, **kwargs)

    def bulk_create(self, request, *args, **kwargs):
        """
        Custom bulk create method
        """
        # Ensure the data is a list
        if not isinstance(request.data, list):
            return Response(
                {"error": "Request data must be a list of job requisitions"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = self.get_serializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        
        try:
            # Save the data - this will call the create method with many=True
            created_instances = serializer.save()
            
            # Serialize the response using the main serializer
            response_serializer = JobRequisitionSerializer(
                created_instances, 
                many=True, 
                context=self.context
            )
            
            headers = self.get_success_headers(serializer.data)
            return Response(
                response_serializer.data, 
                status=status.HTTP_201_CREATED, 
                headers=headers
            )
        except Exception as e:
            logger.error(f"Bulk create failed: {str(e)}")
            return Response(
                {"error": "Failed to create requisitions in bulk", "details": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    # Remove the perform_bulk_create method since the serializer handles it now

    # Keep your existing perform_create for single creation
    def perform_create(self, serializer):
        jwt_payload = getattr(self.request, 'jwt_payload', {})
        tenant_id = str(jwt_payload.get('tenant_unique_id')) if jwt_payload.get('tenant_unique_id') is not None else None
        user_id = str(jwt_payload.get('user', {}).get('id')) if jwt_payload.get('user', {}).get('id') is not None else None
        role = jwt_payload.get('role')
        branch = jwt_payload.get('user', {}).get('branch')
        if not tenant_id or not user_id:
            logger.error("Missing tenant_unique_id or user_id in JWT payload")
            raise serializers.ValidationError("Missing tenant_unique_id or user_id in token.")
        serializer.save(
            tenant_id=tenant_id,
            requested_by_id=user_id,
            branch=branch if role == 'recruiter' and branch else None
        )
        logger.info(f"Job requisition created: {serializer.validated_data['title']} for tenant {tenant_id} by user {user_id}")






logger = logging.getLogger('talent_engine')

class IncrementJobApplicationsCountView(APIView):
    permission_classes = []  # Public endpoint, no authentication required

    def post(self, request, unique_link):
        """
        Increment the num_of_applications field by 1 for a JobRequisition identified by unique_link.
        No payload is required or accepted.
        """
        try:
            # Extract tenant_id from unique_link (first 5 segments, UUID format)
            parts = unique_link.split('-')
            if len(parts) < 5:
                logger.warning(f"Invalid unique_link format: {unique_link}")
                return Response({"detail": "Invalid unique link format."}, status=status.HTTP_400_BAD_REQUEST)
            tenant_id = '-'.join(parts[:5])

            # Fetch JobRequisition by unique_link
            try:
                job_requisition = JobRequisition.active_objects.get(
                    unique_link=unique_link,
                    tenant_id=tenant_id,
                    publish_status=True,
                    is_deleted=False
                )
            except JobRequisition.DoesNotExist:
                logger.warning(f"JobRequisition with unique_link {unique_link} not found or not published")
                return Response({"detail": "Job requisition not found or not published."}, status=status.HTTP_404_NOT_FOUND)

            # Check for unexpected payload
            if request.data:
                logger.warning(f"Unexpected payload provided for {unique_link}: {request.data}")
                return Response({"detail": "No payload is required for this endpoint."}, status=status.HTTP_400_BAD_REQUEST)

            # Increment num_of_applications
            with transaction.atomic():
                job_requisition.num_of_applications = (job_requisition.num_of_applications or 0) + 1
                job_requisition.save(update_fields=['num_of_applications', 'updated_at'])
                logger.info(f"Incremented num_of_applications to {job_requisition.num_of_applications} for JobRequisition {job_requisition.id} (unique_link: {unique_link})")

            # Serialize response
            serializer = PublicJobRequisitionSerializer(job_requisition)
            return Response({
                "detail": f"Incremented num_of_applications to {job_requisition.num_of_applications}",
                "data": serializer.data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error incrementing num_of_applications for unique_link {unique_link}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class JobRequisitionDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = JobRequisitionSerializer
    # permission_classes removed; rely on custom JWT middleware
    lookup_field = 'id'

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return JobRequisition.objects.none()
        jwt_payload = getattr(self.request, 'jwt_payload', {})
        tenant_id = jwt_payload.get('tenant_unique_id')
        role = jwt_payload.get('role')
        branch = jwt_payload.get('branch')
        queryset = JobRequisition.active_objects.filter(tenant_id=tenant_id)
        if role == 'recruiter' and branch:
            queryset = queryset.filter(branch=branch)
        return queryset

    def perform_update(self, serializer):
        jwt_payload = getattr(self.request, 'jwt_payload', {})
        tenant_id = jwt_payload.get('tenant_unique_id')
        user_id = jwt_payload.get('user_id')
        serializer.save(tenant_id=tenant_id, updated_by_id=user_id)
        logger.info(f"Job requisition updated: {serializer.instance.title} for tenant {tenant_id} by user {user_id}")

    def perform_destroy(self, instance):
        jwt_payload = getattr(self.request, 'jwt_payload', {})
        tenant_id = jwt_payload.get('tenant_unique_id')
        instance.soft_delete()
        logger.info(f"Job requisition soft-deleted: {instance.title} for tenant {tenant_id}")


class JobRequisitionByLinkView(generics.RetrieveAPIView):
    serializer_class = JobRequisitionSerializer
    permission_classes = []
    lookup_field = 'unique_link'

    def get_queryset(self):
        unique_link = self.kwargs.get('unique_link', '')
        
        try:
            # Expecting format: tenant_id-prefix-slug-uuid
            parts = unique_link.split('-')
            if len(parts) < 5:
                logger.warning(f"Invalid unique_link format: {unique_link}")
                return JobRequisition.objects.none()

            tenant_id = '-'.join(parts[:5])  # UUID (has 5 parts)
            return JobRequisition.active_objects.filter(
                tenant_id=tenant_id,
                publish_status=True
            )
        except Exception as e:
            logger.error(f"Error parsing unique_link or fetching queryset: {str(e)}")
            return JobRequisition.objects.none()

    def retrieve(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            logger.info(f"Job requisition accessed via link: {instance.title} for tenant {instance.tenant_id}")
            return Response(serializer.data)
        except JobRequisition.DoesNotExist:
            logger.warning(f"Job with unique_link {kwargs.get('unique_link')} not found or not published")
            return Response({"detail": "Job not found or not published"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error retrieving job requisition: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CustomJobRequisitionByLinkView(generics.RetrieveAPIView):
    serializer_class = JobRequisitionSerializer
    permission_classes = []
    lookup_field = 'unique_link'

    def get_queryset(self):
        unique_link = self.kwargs.get('unique_link', '')
        
        try:
            # Expecting format: tenant_id-prefix-slug-uuid
            parts = unique_link.split('-')
            if len(parts) < 5:
                logger.warning(f"Invalid unique_link format: {unique_link}")
                return JobRequisition.objects.none()

            tenant_id = '-'.join(parts[:5])  # UUID (has 5 parts)
            return JobRequisition.active_objects.filter(
                tenant_id=tenant_id,
                publish_status=True
            )
        except Exception as e:
            logger.error(f"Error parsing unique_link or fetching queryset: {str(e)}")
            return JobRequisition.objects.none()

    def retrieve(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            logger.info(f"Job requisition accessed via link: {instance.title} for tenant {instance.tenant_id}")
            return Response(serializer.data)
        except JobRequisition.DoesNotExist:
            logger.warning(f"Job with unique_link {kwargs.get('unique_link')} not found or not published")
            return Response({"detail": "Job not found or not published"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error retrieving job requisition: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SoftDeletedJobRequisitionsView(generics.ListAPIView):
    serializer_class = JobRequisitionSerializer
    # permission_classes removed; rely on custom JWT middleware

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return JobRequisition.objects.none()
        jwt_payload = getattr(self.request, 'jwt_payload', {})
        tenant_id = jwt_payload.get('tenant_unique_id')
        role = jwt_payload.get('role')
        branch = jwt_payload.get('branch')
        queryset = JobRequisition.objects.filter(tenant_id=tenant_id, is_deleted=True)
        if role == 'recruiter' and branch:
            queryset = queryset.filter(branch=branch)
        return queryset

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.get_queryset()
            serializer = self.get_serializer(queryset, many=True)
            logger.info(f"Retrieved {queryset.count()} soft-deleted job requisitions.")
            return Response({
                "detail": f"Retrieved {queryset.count()} soft-deleted requisition(s).",
                "data": serializer.data
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(f"Error listing soft-deleted job requisitions: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RecoverSoftDeletedJobRequisitionsView(generics.GenericAPIView):
    serializer_class = JobRequisitionSerializer  # Added serializer_class

    def post(self, request, *args, **kwargs):
        try:
            ids = request.data.get('ids', [])
            if not ids:
                logger.warning("No requisition IDs provided for recovery")
                return Response({"detail": "No requisition IDs provided."}, status=status.HTTP_400_BAD_REQUEST)
            jwt_payload = getattr(request, 'jwt_payload', {})
            tenant_id = str(jwt_payload.get('tenant_unique_id')) if jwt_payload.get('tenant_unique_id') is not None else None
            role = jwt_payload.get('role')
            branch = jwt_payload.get('user', {}).get('branch')
            if not tenant_id:
                logger.error("No tenant_unique_id in token")
                return Response({"detail": "No tenant_unique_id in token."}, status=status.HTTP_401_UNAUTHORIZED)
            queryset = JobRequisition.objects.filter(id__in=ids, tenant_id=tenant_id, is_deleted=True)
            if role == 'recruiter' and branch:
                queryset = queryset.filter(branch=branch)
            if not queryset.exists():
                logger.warning(f"No soft-deleted requisitions found for IDs {ids} in tenant {tenant_id}")
                return Response({"detail": "No soft-deleted requisitions found."}, status=status.HTTP_404_NOT_FOUND)
            recovered_count = 0
            with transaction.atomic():
                for requisition in queryset:
                    requisition.restore()
                    recovered_count += 1
            logger.info(f"Successfully recovered {recovered_count} requisitions for tenant {tenant_id}")
            return Response({
                "detail": f"Successfully recovered {recovered_count} requisition(s)."
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(f"Error during recovery of requisitions: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PermanentDeleteJobRequisitionsView(generics.GenericAPIView):
    serializer_class = JobRequisitionSerializer  # Added serializer_class

    def post(self, request, *args, **kwargs):
        try:
            ids = request.data.get('ids', [])
            if not ids:
                logger.warning("No requisition IDs provided for permanent deletion")
                return Response({"detail": "No requisition IDs provided."}, status=status.HTTP_400_BAD_REQUEST)
            jwt_payload = getattr(request, 'jwt_payload', {})
            tenant_id = str(jwt_payload.get('tenant_unique_id')) if jwt_payload.get('tenant_unique_id') is not None else None
            role = jwt_payload.get('role')
            branch = jwt_payload.get('user', {}).get('branch')
            if not tenant_id:
                logger.error("No tenant_unique_id in token")
                return Response({"detail": "No tenant_unique_id in token."}, status=status.HTTP_401_UNAUTHORIZED)
            queryset = JobRequisition.objects.filter(id__in=ids, tenant_id=tenant_id, is_deleted=True)
            if role == 'recruiter' and branch:
                queryset = queryset.filter(branch=branch)
            if not queryset.exists():
                logger.warning(f"No soft-deleted requisitions found for IDs {ids} in tenant {tenant_id}")
                return Response({"detail": "No soft-deleted requisitions found."}, status=status.HTTP_404_NOT_FOUND)
            deleted_count = queryset.delete()[0]
            logger.info(f"Successfully permanently deleted {deleted_count} requisitions for tenant {tenant_id}")
            return Response({
                "detail": f"Successfully permanently deleted {deleted_count} requisition(s)."
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(f"Error during permanent deletion of requisitions: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

 

class ComplianceItemView(APIView):
    serializer_class = ComplianceItemSerializer  # Added serializer_class
    # permission_classes removed; rely on custom JWT middleware

    def post(self, request, job_requisition_id):
        try:
            tenant_id = get_tenant_id_from_jwt(request)
            try:
                job_requisition = JobRequisition.active_objects.get(id=job_requisition_id, tenant_id=tenant_id)
            except JobRequisition.DoesNotExist:
                logger.error(f"JobRequisition {job_requisition_id} not found for tenant {tenant_id}")
                return Response({"detail": "Job requisition not found."}, status=status.HTTP_404_NOT_FOUND)
            if request.user.role == 'recruiter' and request.user.branch and job_requisition.branch != request.user.branch:
                logger.error(f"Unauthorized access to JobRequisition {job_requisition_id} by user {request.user.email}")
                return Response({"detail": "Not authorized to access this requisition."}, status=status.HTTP_403_FORBIDDEN)
            serializer = ComplianceItemSerializer(data=request.data, context={'request': request})
            if serializer.is_valid():
                item_data = serializer.validated_data
                item_data.setdefault('status', 'pending')
                item_data.setdefault('checked_by', None)
                item_data.setdefault('checked_at', None)
                new_item = job_requisition.add_compliance_item(
                    name=item_data['name'],
                    description=item_data.get('description', ''),
                    required=item_data.get('required', True),
                    status=item_data['status'],
                    checked_by=item_data['checked_by'],
                    checked_at=item_data['checked_at']
                )
                logger.info(f"Added compliance item to JobRequisition {job_requisition_id} for tenant {tenant_id}")
                return Response(ComplianceItemSerializer(new_item).data, status=status.HTTP_201_CREATED)
            logger.error(f"Invalid compliance item data for tenant {tenant_id}: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(f"Error adding compliance item to JobRequisition {job_requisition_id}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def put(self, request, job_requisition_id, item_id):
        try:
            tenant_id = get_tenant_id_from_jwt(request)
            try:
                job_requisition = JobRequisition.active_objects.get(id=job_requisition_id, tenant_id=tenant_id)
            except JobRequisition.DoesNotExist:
                logger.error(f"JobRequisition {job_requisition_id} not found for tenant {tenant_id}")
                return Response({"detail": "Job requisition not found."}, status=status.HTTP_404_NOT_FOUND)
            if request.user.role == 'recruiter' and request.user.branch and job_requisition.branch != request.user.branch:
                logger.error(f"Unauthorized access to JobRequisition {job_requisition_id} by user {request.user.email}")
                return Response({"detail": "Not authorized to access this requisition."}, status=status.HTTP_403_FORBIDDEN)
            serializer = ComplianceItemSerializer(data=request.data, context={'request': request})
            if serializer.is_valid():
                item_data = serializer.validated_data
                updated_item = job_requisition.update_compliance_item(
                    item_id=str(item_id),
                    name=item_data['name'],
                    description=item_data.get('description', ''),
                    required=item_data.get('required', True),
                    status=item_data.get('status', 'pending'),
                    checked_by=item_data.get('checked_by'),
                    checked_at=item_data.get('checked_at')
                )
                logger.info(f"Updated compliance item {item_id} for JobRequisition {job_requisition_id} for tenant {tenant_id}")
                return Response(ComplianceItemSerializer(updated_item).data, status=status.HTTP_200_OK)
            logger.error(f"Invalid compliance item data for tenant {tenant_id}: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except ValueError as e:
            logger.error(f"Compliance item {item_id} not found in JobRequisition {job_requisition_id} for tenant {tenant_id}")
            return Response({"detail": str(e)}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception(f"Error updating compliance item {item_id} for JobRequisition {job_requisition_id}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, job_requisition_id, item_id):
        try:
            tenant_id = get_tenant_id_from_jwt(request)
            try:
                job_requisition = JobRequisition.active_objects.get(id=job_requisition_id, tenant_id=tenant_id)
            except JobRequisition.DoesNotExist:
                logger.error(f"JobRequisition {job_requisition_id} not found for tenant {tenant_id}")
                return Response({"detail": "Job requisition not found."}, status=status.HTTP_404_NOT_FOUND)
            if request.user.role == 'recruiter' and request.user.branch and job_requisition.branch != request.user.branch:
                logger.error(f"Unauthorized access to JobRequisition {job_requisition_id} by user {request.user.email}")
                return Response({"detail": "Not authorized to access this requisition."}, status=status.HTTP_403_FORBIDDEN)
            job_requisition.remove_compliance_item(str(item_id))
            logger.info(f"Deleted compliance item {item_id} from JobRequisition {job_requisition_id} for tenant {tenant_id}")
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ValueError as e:
            logger.error(f"Compliance item {item_id} not found in JobRequisition {job_requisition_id} for tenant {tenant_id}")
            return Response({"detail": str(e)}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception(f"Error deleting compliance item {item_id} for JobRequisition {job_requisition_id}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

class VideoSessionViewSet(viewsets.ModelViewSet):
    serializer_class = VideoSessionSerializer
    # permission_classes removed; rely on custom JWT middleware

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return VideoSession.objects.none()
        jwt_payload = getattr(self.request, 'jwt_payload', {})
        tenant_id = jwt_payload.get('tenant_unique_id')
        role = jwt_payload.get('role')
        branch = jwt_payload.get('branch')
        queryset = VideoSession.objects.filter(tenant_id=tenant_id)
        if role == 'recruiter' and branch:
            queryset = queryset.filter(job_application__branch=branch)
        return queryset

    @extend_schema(
        description="Start recording a video session",
        parameters=[
            OpenApiParameter(name='session_id', type=str, required=True)
        ]
    )
    @action(detail=False, methods=['post'])
    def start_recording(self, request):
        jwt_payload = getattr(request, 'jwt_payload', {})
        tenant_id = jwt_payload.get('tenant_unique_id')
        role = jwt_payload.get('role')
        branch = jwt_payload.get('branch')
        session_id = request.data.get('session_id')
        try:
            session = VideoSession.objects.get(id=session_id, is_active=True, tenant_id=tenant_id)
            if role == 'recruiter' and branch and session.job_application.branch != branch:
                logger.error(f"Unauthorized access to session {session_id} by recruiter in branch {branch}")
                return Response({"detail": "Not authorized to access this session."}, status=status.HTTP_403_FORBIDDEN)
            # Placeholder for actual recording logic
            recording_path = f"recordings/{tenant_id}/{session_id}/{uuid.uuid4()}.webm"
            file_data = b"placeholder_recording_data"  # Replace with actual stream data
            recording_url = upload_file_dynamic(
                file=file_data,
                file_path=recording_path,
                content_type="video/webm",
                storage_backend="supabase"
            )
            session.recording_url = recording_url
            session.save()
            logger.info(f"Recording started for session {session_id} in tenant {tenant_id}")
            return Response({'recording_url': session.recording_url}, status=status.HTTP_200_OK)
        except VideoSession.DoesNotExist:
            logger.error(f"Session {session_id} not found or inactive for tenant {tenant_id}")
            return Response({'error': 'Session not found or inactive'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error starting recording for session {session_id}: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @extend_schema(
        description="Join a video session and create a participant entry (by user or candidate email)",
        parameters=[
            OpenApiParameter(name='session_id', type=str, required=True),
            OpenApiParameter(name='email', type=str, required=False)
        ]
    )
    @action(detail=False, methods=['post'])
    def join(self, request):
        jwt_payload = getattr(request, 'jwt_payload', {})
        tenant_id = jwt_payload.get('tenant_unique_id')
        user_id = jwt_payload.get('user_id')
        role = jwt_payload.get('role')
        branch = jwt_payload.get('branch')
        session_id = request.data.get('session_id')
        email = request.data.get('email')
        try:
            session = VideoSession.objects.get(id=session_id, is_active=True, tenant_id=tenant_id)
            # Authenticated user flow (by user_id in JWT)
            if user_id:
                if role == 'recruiter' and branch and session.job_application.branch != branch:
                    logger.error(f"Unauthorized access to session {session_id} by recruiter in branch {branch}")
                    return Response({"detail": "Not authorized to access this session."}, status=status.HTTP_403_FORBIDDEN)
                participant, created = Participant.objects.get_or_create(
                    session=session,
                    user_id=user_id,
                    defaults={'is_muted': False, 'is_camera_on': True}
                )
                logger.info(f"User {user_id} joined session {session_id} in tenant {tenant_id}")
                return Response(ParticipantSerializer(participant).data, status=status.HTTP_200_OK)
            # Candidate email flow
            elif email:
                job_app = session.job_application
                if job_app.email.lower() == email.lower():
                    participant, created = Participant.objects.get_or_create(
                        session=session,
                        candidate_email=email,
                        defaults={'is_muted': False, 'is_camera_on': True}
                    )
                    logger.info(f"Candidate {email} joined session {session_id} in tenant {tenant_id}")
                    return Response(ParticipantSerializer(participant).data, status=status.HTTP_200_OK)
                else:
                    logger.error(f"Email {email} not authorized for session {session_id}")
                    return Response({"detail": "Email not authorized for this session."}, status=status.HTTP_403_FORBIDDEN)
            else:
                logger.error("No authentication or candidate email provided")
                return Response({"detail": "Authentication or candidate email required."}, status=status.HTTP_400_BAD_REQUEST)
        except VideoSession.DoesNotExist:
            logger.error(f"Session {session_id} not found or inactive for tenant {tenant_id}")
            return Response({'error': 'Session not found or inactive'}, status=status.HTTP_404_NOT_FOUND)

    @extend_schema(
        description="Leave a video session",
        parameters=[
            OpenApiParameter(name='session_id', type=str, required=True)
        ]
    )
    @action(detail=False, methods=['post'])
    def leave(self, request):
        jwt_payload = getattr(request, 'jwt_payload', {})
        tenant_id = jwt_payload.get('tenant_unique_id')
        user_id = jwt_payload.get('user_id')
        role = jwt_payload.get('role')
        branch = jwt_payload.get('branch')
        session_id = request.data.get('session_id')
        try:
            participant = Participant.objects.get(
                session__id=session_id,
                session__tenant_id=tenant_id,
                user_id=user_id,
                left_at__isnull=True
            )
            if role == 'recruiter' and branch and participant.session.job_application.branch != branch:
                logger.error(f"Unauthorized access to session {session_id} by recruiter in branch {branch}")
                return Response({"detail": "Not authorized to access this session."}, status=status.HTTP_403_FORBIDDEN)
            participant.left_at = timezone.now()
            participant.save()
            # Check if all participants have left to end the session
            if not Participant.objects.filter(session__id=session_id, left_at__isnull=True).exists():
                session = VideoSession.objects.get(id=session_id)
                session.end_session()
            logger.info(f"User {user_id} left session {session_id} in tenant {tenant_id}")
            return Response({'status': 'Left session'}, status=status.HTTP_200_OK)
        except Participant.DoesNotExist:
            logger.error(f"Participant not found in session {session_id} for tenant {tenant_id}")
            return Response({'error': 'Participant not found'}, status=status.HTTP_404_NOT_FOUND)

    @extend_schema(
        description="Toggle mute status for a participant",
        parameters=[
            OpenApiParameter(name='session_id', type=str, required=True),
            OpenApiParameter(name='mute', type=bool, required=True)
        ]
    )
    @action(detail=False, methods=['post'])
    def toggle_mute(self, request):
        jwt_payload = getattr(request, 'jwt_payload', {})
        tenant_id = jwt_payload.get('tenant_unique_id')
        user_id = jwt_payload.get('user_id')
        role = jwt_payload.get('role')
        branch = jwt_payload.get('branch')
        session_id = request.data.get('session_id')
        mute = request.data.get('mute', False)
        try:
            participant = Participant.objects.get(
                session__id=session_id,
                session__tenant_id=tenant_id,
                user_id=user_id,
                left_at__isnull=True
            )
            if role == 'recruiter' and branch and participant.session.job_application.branch != branch:
                logger.error(f"Unauthorized access to session {session_id} by recruiter in branch {branch}")
                return Response({"detail": "Not authorized to access this session."}, status=status.HTTP_403_FORBIDDEN)
            participant.is_muted = mute
            participant.save()
            logger.info(f"User {user_id} {'muted' if mute else 'unmuted'} in session {session_id} for tenant {tenant_id}")
            return Response(ParticipantSerializer(participant).data, status=status.HTTP_200_OK)
        except Participant.DoesNotExist:
            logger.error(f"Participant not found in session {session_id} for tenant {tenant_id}")
            return Response({'error': 'Participant not found'}, status=status.HTTP_404_NOT_FOUND)

    @extend_schema(
        description="Toggle camera status for a participant",
        parameters=[
            OpenApiParameter(name='session_id', type=str, required=True),
            OpenApiParameter(name='camera_on', type=bool, required=True)
        ]
    )


    @action(detail=False, methods=['post'])
    def toggle_camera(self, request):
        jwt_payload = getattr(request, 'jwt_payload', {})
        tenant_id = jwt_payload.get('tenant_unique_id')
        user_id = jwt_payload.get('user_id')
        session_id = request.data.get('session_id')
        camera_on = request.data.get('camera_on', True)
        email = request.data.get('email')
        try:
            if user_id:
                participant = Participant.objects.get(
                    session__id=session_id,
                    session__tenant_id=tenant_id,
                    user_id=user_id,
                    left_at__isnull=True
                )
            elif email:
                participant = Participant.objects.get(
                    session__id=session_id,
                    session__tenant_id=tenant_id,
                    candidate_email=email,
                    left_at__isnull=True
                )
            else:
                return Response({"detail": "Authentication or candidate email required."}, status=status.HTTP_400_BAD_REQUEST)
            participant.is_camera_on = camera_on
            participant.save()
            return Response(ParticipantSerializer(participant).data, status=status.HTTP_200_OK)
        except Participant.DoesNotExist:
            return Response({'error': 'Participant not found'}, status=status.HTTP_404_NOT_FOUND)


    @extend_schema(
        description="Update interview scores, notes, or tags",
        parameters=[
            OpenApiParameter(name='session_id', type=str, required=True)
        ]
    )
    @action(detail=False, methods=['post'])
    def update_interview_data(self, request):
        jwt_payload = getattr(request, 'jwt_payload', {})
        tenant_id = jwt_payload.get('tenant_unique_id')
        role = jwt_payload.get('role')
        branch = jwt_payload.get('branch')
        session_id = request.data.get('session_id')
        scores = request.data.get('scores')
        notes = request.data.get('notes')
        tags = request.data.get('tags')
        try:
            session = VideoSession.objects.get(id=session_id, is_active=True, tenant_id=tenant_id)
            if role == 'recruiter' and branch and session.job_application.branch != branch:
                logger.error(f"Unauthorized access to session {session_id} by recruiter in branch {branch}")
                return Response({"detail": "Not authorized to access this session."}, status=status.HTTP_403_FORBIDDEN)
            if scores is not None:
                serializer = VideoSessionSerializer(data={'scores': scores}, partial=True)
                serializer.is_valid(raise_exception=True)
                session.scores = serializer.validated_data['scores']
            if notes is not None:
                session.notes = notes
            if tags is not None:
                serializer = VideoSessionSerializer(data={'tags': tags}, partial=True)
                serializer.is_valid(raise_exception=True)
                session.tags = serializer.validated_data['tags']
            session.save()
            logger.info(f"Updated interview data for session {session_id} in tenant {tenant_id}")
            return Response(VideoSessionSerializer(session).data, status=status.HTTP_200_OK)
        except VideoSession.DoesNotExist:
            logger.error(f"Session {session_id} not found or inactive for tenant {tenant_id}")
            return Response({'error': 'Session not found or inactive'}, status=status.HTTP_404_NOT_FOUND)


class RequestListCreateView(generics.ListCreateAPIView):
    serializer_class = RequestSerializer
    # permission_classes removed; rely on custom JWT middleware
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['request_type', 'status']  # Removed 'branch' if not a model field
    search_fields = ['title', 'description', 'requested_by__email']

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Request.objects.none()
        jwt_payload = getattr(self.request, 'jwt_payload', {})
        tenant_id = jwt_payload.get('tenant_unique_id')
        role = jwt_payload.get('role')
        branch = jwt_payload.get('branch')
        queryset = Request.objects.filter(tenant_id=tenant_id, is_deleted=False)
        if role == 'recruiter' and branch:
            queryset = queryset.filter(branch=branch)
        return queryset

    def perform_create(self, serializer):
        jwt_payload = getattr(self.request, 'jwt_payload', {})
        tenant_id = jwt_payload.get('tenant_unique_id')
        user_id = jwt_payload.get('user_id')
        role = jwt_payload.get('role')
        branch = jwt_payload.get('branch')
        serializer.save(
            tenant_id=tenant_id,
            requested_by_id=user_id,
            branch=branch if role == 'recruiter' and branch else None
        )
        logger.info(f"Request created: {serializer.validated_data['title']} for tenant {tenant_id} by user {user_id}")

class RequestDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = RequestSerializer
    # permission_classes removed; rely on custom JWT middleware
    lookup_field = 'id'

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Request.objects.none()
        jwt_payload = getattr(self.request, 'jwt_payload', {})
        tenant_id = jwt_payload.get('tenant_unique_id')
        role = jwt_payload.get('role')
        branch = jwt_payload.get('branch')
        queryset = Request.objects.filter(tenant_id=tenant_id, is_deleted=False)
        if role == 'recruiter' and branch:
            queryset = queryset.filter(branch=branch)
        return queryset

    def perform_destroy(self, instance):
        instance.soft_delete()
        logger.info(f"Request soft-deleted: {instance.title} for tenant {instance.tenant_id}")

class UserRequestsListView(generics.ListAPIView):
    serializer_class = RequestSerializer
    # permission_classes removed; rely on custom JWT middleware
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['request_type', 'status']  # Removed 'branch' if not a model field
    search_fields = ['title', 'description']

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Request.objects.none()
        jwt_payload = getattr(self.request, 'jwt_payload', {})
        tenant_id = jwt_payload.get('tenant_unique_id')
        user_id = jwt_payload.get('user_id')
        role = jwt_payload.get('role')
        branch = jwt_payload.get('branch')
        queryset = Request.objects.filter(tenant_id=tenant_id, is_deleted=False, requested_by_id=user_id)
        if role == 'recruiter' and branch:
            queryset = queryset.filter(branch=branch)
        return queryset