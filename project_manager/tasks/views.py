from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from django.db import transaction
from .models import Task, DailyReport, Comment
from .serializers import *
from .permissions import IsAuthenticatedWithAuthService
from .auth_utils import get_user_details
from rest_framework.exceptions import PermissionDenied
import logging
from rest_framework.pagination import PageNumberPagination
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
logger = logging.getLogger('project_manager')
from django.conf import settings


@api_view(['GET'])
def user_tasks(request, user_id):
    """Get tasks assigned to a specific user"""
    try:
        # Get tenant_id from JWT
        jwt_payload = getattr(request, 'jwt_payload', None)
        tenant_id = jwt_payload.get('tenant_unique_id') or jwt_payload.get('tenant') if jwt_payload else None
        # For development/testing, use default tenant if not provided
        if not tenant_id:
            tenant_id = 'default-tenant'

        # Get tasks assigned to the specified user
        tasks = Task.objects.filter(assigned_to_id=user_id, tenant_id=tenant_id).prefetch_related('comments', 'daily_reports')

        # Apply any query parameters (like status filtering)
        status_filter = request.query_params.get('status')
        if status_filter:
            tasks = tasks.filter(status=status_filter)

        # Paginate if needed
        page = request.query_params.get('page')
        if page:
            paginator = CustomPagination()
            paginated_tasks = paginator.paginate_queryset(tasks, request)
            serializer = TaskSerializer(paginated_tasks, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = TaskSerializer(tasks, many=True)
        return Response(serializer.data)

    except Exception as e:
        logger.error(f"Error fetching tasks for user {user_id}: {str(e)}")
        return Response(
            {'detail': f'Error fetching tasks: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )



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



class TaskViewSet(viewsets.ModelViewSet):
    # Temporarily use AllowAny to debug
    permission_classes = []  # Empty list means no permission checks
    pagination_class = CustomPagination
    
    def get_queryset(self):
        jwt_payload = getattr(self.request, 'jwt_payload', None)
        tenant_id = jwt_payload.get('tenant_unique_id') or jwt_payload.get('tenant') if jwt_payload else None
        # For development/testing, use default tenant if not provided
        if not tenant_id:
            tenant_id = 'default-tenant'
        queryset = Task.objects.filter(tenant_id=tenant_id).prefetch_related('comments', 'daily_reports')

        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        assigned_to_filter = self.request.query_params.get('assigned_to')
        if assigned_to_filter:
            queryset = queryset.filter(assigned_to_id=assigned_to_filter)

        return queryset

    def get_serializer_class(self):
        if self.action == 'create':
            return TaskCreateSerializer
        elif self.action == 'update_status':
            return TaskStatusUpdateSerializer
        return TaskSerializer

    def get_current_user_info(self):
        """
        Extract user info from JWT payload that was already validated by middleware.
        This avoids re-validation and auth service calls.
        """
        logger.info(f"========== GET_CURRENT_USER_INFO START ==========")

        # Use the JWT payload that was already validated by middleware
        jwt_payload = getattr(self.request, 'jwt_payload', None)
        if jwt_payload:
            user_info = {
                'id': jwt_payload.get('sub'),  # User identifier from JWT
                'first_name': jwt_payload.get('first_name', ''),
                'last_name': jwt_payload.get('last_name', ''),
                'email': jwt_payload.get('email', ''),
                'username': jwt_payload.get('username', ''),
                'role': jwt_payload.get('role', ''),
            }

            logger.info(f"✓✓✓ Successfully extracted user from validated JWT payload: {user_info} ✓✓✓")
            logger.info(f"========== GET_CURRENT_USER_INFO END ==========")
            return user_info

        # Fallback: try to decode token directly (for debugging)
        logger.warning("⚠ JWT payload not found, trying direct token extraction...")
        token = self.request.headers.get('Authorization', '').split('Bearer ')[-1]
        if not token:
            logger.error("✗ No token found in Authorization header")
            return None

        try:
            import jwt
            # Try unverified decode to at least get the payload
            payload = jwt.decode(token, options={"verify_signature": False})

            user_info = {
                'id': payload.get('sub'),
                'first_name': payload.get('first_name', ''),
                'last_name': payload.get('last_name', ''),
                'email': payload.get('email', ''),
                'username': payload.get('username', ''),
                'role': payload.get('role', ''),
            }

            logger.info(f"✓ Extracted user from unverified token (fallback): {user_info}")
            logger.info(f"========== GET_CURRENT_USER_INFO END ==========")
            return user_info

        except Exception as e:
            logger.error(f"✗ Error extracting user from token: {str(e)}")
            logger.info(f"========== GET_CURRENT_USER_INFO END ==========")
            return None

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        logger.info(f"")
        logger.info(f"={'='*60}")
        logger.info(f"========== CREATE TASK REQUEST START ==========")
        logger.info(f"={'='*60}")
        logger.info(f"Method: {request.method}")
        logger.info(f"Path: {request.path}")
        logger.info(f"Request data: {request.data}")
        
        # Get current user info from request.user (already set by middleware)
        current_user = self.get_current_user_info()
        
        if not current_user:
            logger.error(f"")
            logger.error(f"{'='*60}")
            logger.error("✗✗✗ AUTHENTICATION FAILED ✗✗✗")
            logger.error(f"{'='*60}")
            return Response(
                {'detail': 'Authentication required'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        logger.info(f"✓ Current user authenticated: {current_user}")

        # Validate request data
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        logger.info(f"✓ Request data validated")

        # Get assigned user details from auth service
        assigned_to_id = serializer.validated_data.get('assigned_to_id')

        # Handle task assignment
        if not assigned_to_id or assigned_to_id.strip() == '':
            # Task is unassigned - leave it blank
            logger.info("Task created without assignment")
            assigned_user = {
                'first_name': '',
                'last_name': '',
                'email': '',
            }
            serializer.validated_data['assigned_to_id'] = None
        else:
            # Try to get assigned user details from auth service
            token = request.headers.get('Authorization', '').split('Bearer ')[-1]

            logger.info(f"Fetching details for assigned user: {assigned_to_id}")
            assigned_user = get_user_details(assigned_to_id, token)

            if not assigned_user:
                logger.warning(f"⚠ Assigned user not found: {assigned_to_id}, leaving task unassigned")
                # Leave task unassigned if user not found
                assigned_user = {
                    'first_name': '',
                    'last_name': '',
                    'email': '',
                }
                serializer.validated_data['assigned_to_id'] = None
                logger.info(f"✓ Task left unassigned due to user not found")

        logger.info(f"✓ Assigned user details: {assigned_user}")

        # Get tenant_id
        jwt_payload = getattr(self.request, 'jwt_payload', None)
        tenant_id = jwt_payload.get('tenant_unique_id') or jwt_payload.get('tenant') if jwt_payload else None
        # For development/testing, use default tenant if not provided
        if not tenant_id:
            tenant_id = 'default-tenant'
        # For development/testing, use default tenant if not provided
        if not tenant_id:
            tenant_id = 'default-tenant'
        # For development/testing, use default tenant if not provided
        if not tenant_id:
            tenant_id = 'default-tenant'

        # Create task with both assignor and assignee details
        task_data = {
            **serializer.validated_data,
            'tenant_id': tenant_id,
            'assigned_by_id': current_user['id'],
            'assigned_by_first_name': current_user['first_name'],
            'assigned_by_last_name': current_user['last_name'],
            'assigned_by_email': current_user['email'],
            'assigned_to_first_name': assigned_user['first_name'],
            'assigned_to_last_name': assigned_user['last_name'],
            'assigned_to_email': assigned_user['email'],
        }

        logger.info(f"Creating task with data: {task_data}")
        task = Task.objects.create(**task_data)
        logger.info(f"✓✓✓ Task created successfully! ID: {task.id} ✓✓✓")
        logger.info(f"={'='*60}")
        logger.info(f"========== CREATE TASK REQUEST END ==========")
        logger.info(f"={'='*60}")
        
        return Response(
            TaskSerializer(task).data, 
            status=status.HTTP_201_CREATED
        )

    @action(detail=False, methods=['get'])
    def my_tasks(self, request):
        """Get tasks assigned to current user"""
        current_user = self.get_current_user_info()
        if not current_user:
            return Response(
                {'detail': 'Authentication required'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        tasks = self.get_queryset().filter(assigned_to_id=current_user['id'])
        page = self.paginate_queryset(tasks)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(tasks, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """Create multiple tasks in a single request"""
        logger.info(f"")
        logger.info(f"={'='*60}")
        logger.info(f"========== BULK CREATE TASKS REQUEST START ==========")
        logger.info(f"={'='*60}")
        logger.info(f"Method: {request.method}")
        logger.info(f"Request data: {request.data}")

        # Get current user info
        current_user = self.get_current_user_info()

        if not current_user:
            logger.error(f"")
            logger.error(f"{'='*60}")
            logger.error("✗✗✗ AUTHENTICATION FAILED ✗✗✗")
            logger.error(f"{'='*60}")
            return Response(
                {'detail': 'Authentication required'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        logger.info(f"✓ Current user authenticated: {current_user}")

        # Validate request data
        serializer = BulkTaskCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        logger.info(f"✓ Request data validated")

        # Create tasks
        try:
            created_tasks = serializer.create(serializer.validated_data, current_user)
            logger.info(f"✓✓✓ Bulk creation successful! Created {len(created_tasks)} tasks ✓✓✓")

            # Return created tasks data
            response_serializer = TaskSerializer(created_tasks, many=True)
            response_data = {
                'message': f'Successfully created {len(created_tasks)} tasks',
                'created_count': len(created_tasks),
                'tasks': response_serializer.data
            }

            logger.info(f"={'='*60}")
            logger.info(f"========== BULK CREATE TASKS REQUEST END ==========")
            logger.info(f"={'='*60}")

            return Response(response_data, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"✗✗✗ Bulk creation failed: {str(e)} ✗✗✗")
            logger.info(f"========== BULK CREATE TASKS REQUEST END ==========")
            return Response(
                {'detail': f'Bulk creation failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['patch'])
    def update_status(self, request, pk=None):
        """Update task status and create daily report"""
        task = self.get_object()
        current_user = self.get_current_user_info()
        if not current_user:
            return Response(
                {'detail': 'Authentication required'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        serializer = TaskStatusUpdateSerializer(task, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        task = serializer.save()
        
        # Get tenant_id
        jwt_payload = getattr(self.request, 'jwt_payload', None)
        tenant_id = jwt_payload.get('tenant_unique_id') or jwt_payload.get('tenant') if jwt_payload else None

        # Auto-create daily report for status changes
        if request.data.get('status') in ['completed', 'blocked']:
            DailyReport.objects.create(
                tenant_id=tenant_id,
                task=task,
                updated_by_id=current_user['id'],
                updated_by_first_name=current_user['first_name'],
                updated_by_last_name=current_user['last_name'],
                updated_by_email=current_user['email'],
                completed_description=f"Status changed to {request.data.get('status')}",
                status=request.data.get('status')
            )
        
        return Response(TaskSerializer(task).data)

    @action(detail=True, methods=['post'])
    def comment(self, request, pk=None):
        """Add comment to task"""
        task = self.get_object()
        current_user = self.get_current_user_info()
        if not current_user:
            return Response(
                {'detail': 'Authentication required'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        serializer = CommentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Get tenant_id
        jwt_payload = getattr(self.request, 'jwt_payload', None)
        tenant_id = jwt_payload.get('tenant_unique_id') or jwt_payload.get('tenant') if jwt_payload else None

        comment = Comment.objects.create(
            tenant_id=tenant_id,
            task=task,
            user_id=current_user['id'],
            user_first_name=current_user['first_name'],
            user_last_name=current_user['last_name'],
            user_email=current_user['email'],
            text=serializer.validated_data['text']
        )
        
        return Response(
            CommentSerializer(comment).data, 
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['post'])
    def report(self, request, pk=None):
        """Create daily report for task"""
        task = self.get_object()
        current_user = self.get_current_user_info()
        if not current_user:
            return Response(
                {'detail': 'Authentication required'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        serializer = DailyReportCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Get tenant_id
        jwt_payload = getattr(self.request, 'jwt_payload', None)
        tenant_id = jwt_payload.get('tenant_unique_id') or jwt_payload.get('tenant') if jwt_payload else None

        report = DailyReport.objects.create(
            tenant_id=tenant_id,
            task=task,
            updated_by_id=current_user['id'],
            updated_by_first_name=current_user['first_name'],
            updated_by_last_name=current_user['last_name'],
            updated_by_email=current_user['email'],
            **serializer.validated_data
        )
        
        # Update task status if changed
        new_status = serializer.validated_data.get('status')
        if new_status and new_status != task.status:
            task.status = new_status
            task.save()
        
        return Response(
            DailyReportSerializer(report).data, 
            status=status.HTTP_201_CREATED
        )


class CommentViewSet(viewsets.ModelViewSet):
    permission_classes = []  # Empty list means no permission checks

    def get_queryset(self):
        jwt_payload = getattr(self.request, 'jwt_payload', None)
        tenant_id = jwt_payload.get('tenant_unique_id') or jwt_payload.get('tenant') if jwt_payload else None
        # For development/testing, use default tenant if not provided
        if not tenant_id:
            tenant_id = 'default-tenant'
        return Comment.objects.filter(tenant_id=tenant_id)

    def get_serializer_class(self):
        if self.action == 'create':
            return CommentCreateSerializer
        return CommentSerializer

    def perform_create(self, serializer):
        jwt_payload = getattr(self.request, 'jwt_payload', None)
        tenant_id = jwt_payload.get('tenant_unique_id') or jwt_payload.get('tenant') if jwt_payload else None
        # For development/testing, use default tenant if not provided
        if not tenant_id:
            tenant_id = 'default-tenant'
        user = self.request.user
        serializer.save(
            tenant_id=tenant_id,
            user_id=str(user.pk),
            user_first_name=user.first_name,
            user_last_name=user.last_name,
            user_email=user.email,
        )


class DailyReportViewSet(viewsets.ModelViewSet):
    permission_classes = []  # Empty list means no permission checks

    def get_queryset(self):
        jwt_payload = getattr(self.request, 'jwt_payload', None)
        tenant_id = jwt_payload.get('tenant_unique_id') or jwt_payload.get('tenant') if jwt_payload else None
        # For development/testing, use default tenant if not provided
        if not tenant_id:
            tenant_id = 'default-tenant'
        return DailyReport.objects.filter(tenant_id=tenant_id)

    def get_serializer_class(self):
        if self.action == 'create':
            return DailyReportCreateSerializer
        return DailyReportSerializer

    def perform_create(self, serializer):
        jwt_payload = getattr(self.request, 'jwt_payload', None)
        tenant_id = jwt_payload.get('tenant_unique_id') or jwt_payload.get('tenant') if jwt_payload else None
        # For development/testing, use default tenant if not provided
        if not tenant_id:
            tenant_id = 'default-tenant'
        user = self.request.user
        task = serializer.validated_data['task']
        new_status = serializer.validated_data.get('status')

        # Update task status if changed
        if new_status and new_status != task.status:
            task.status = new_status
            task.save()

        serializer.save(
            tenant_id=tenant_id,
            updated_by_id=str(user.pk),
            updated_by_first_name=user.first_name,
            updated_by_last_name=user.last_name,
            updated_by_email=user.email,
        )