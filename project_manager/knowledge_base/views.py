from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q
from .models import Category, Tag, Article
from .serializers import (
    CategorySerializer, TagSerializer, ArticleSerializer,
    ArticleCreateSerializer, ArticleListSerializer
)
from rest_framework.pagination import PageNumberPagination
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from django.conf import settings
import logging

logger = logging.getLogger('knowledge_base')

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



class CategoryViewSet(viewsets.ModelViewSet):
    serializer_class = CategorySerializer
    permission_classes = []  # Empty list means no permission checks

    def get_queryset(self):
        jwt_payload = getattr(self.request, 'jwt_payload', None)
        tenant_id = jwt_payload.get('tenant_unique_id') or jwt_payload.get('tenant') or jwt_payload.get('tenant_id') if jwt_payload else None
        # For development/testing, use default tenant if not provided
        if not tenant_id:
            tenant_id = 'default-tenant'
        return Category.objects.filter(tenant_id=tenant_id)

    def get_current_user_info(self):
        """
        Extract user info from JWT payload that was already validated by middleware.
        """
        jwt_payload = getattr(self.request, 'jwt_payload', None)
        if jwt_payload:
            user_info = {
                'id': jwt_payload.get('sub'),
                'first_name': jwt_payload.get('first_name', ''),
                'last_name': jwt_payload.get('last_name', ''),
                'email': jwt_payload.get('email', ''),
                'username': jwt_payload.get('username', ''),
                'role': jwt_payload.get('role', ''),
            }
            return user_info
        return None

    def create(self, request, *args, **kwargs):
        logger.info(f"")
        logger.info(f"={'='*60}")
        logger.info(f"========== CREATE CATEGORY REQUEST START ==========")
        logger.info(f"={'='*60}")
        logger.info(f"Method: {request.method}")
        logger.info(f"Path: {request.path}")
        logger.info(f"Request data: {request.data}")

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

        # Get tenant_id from JWT
        jwt_payload = getattr(self.request, 'jwt_payload', None)
        tenant_id = jwt_payload.get('tenant_unique_id') or jwt_payload.get('tenant') if jwt_payload else None
        if not tenant_id:
            tenant_id = 'default-tenant'
        logger.info(f"Tenant ID extracted: {tenant_id}")

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        logger.info(f"✓ Request data validated")

        serializer.save(tenant_id=tenant_id)
        logger.info(f"✓✓✓ Category created successfully! ✓✓✓")
        logger.info(f"={'='*60}")
        logger.info(f"========== CREATE CATEGORY REQUEST END ==========")
        logger.info(f"={'='*60}")

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        jwt_payload = getattr(self.request, 'jwt_payload', None)
        tenant_id = jwt_payload.get('tenant_unique_id') or jwt_payload.get('tenant') or jwt_payload.get('tenant_id') if jwt_payload else None
        # For development/testing, use default tenant if not provided
        if not tenant_id:
            tenant_id = 'default-tenant'
        serializer.save(tenant_id=tenant_id)

class TagViewSet(viewsets.ModelViewSet):
    serializer_class = TagSerializer
    permission_classes = []  # Empty list means no permission checks

    def get_queryset(self):
        jwt_payload = getattr(self.request, 'jwt_payload', None)
        tenant_id = jwt_payload.get('tenant_unique_id') or jwt_payload.get('tenant') or jwt_payload.get('tenant_id') if jwt_payload else None
        # For development/testing, use default tenant if not provided
        if not tenant_id:
            tenant_id = 'default-tenant'
        return Tag.objects.filter(tenant_id=tenant_id)

    def get_current_user_info(self):
        """
        Extract user info from JWT payload that was already validated by middleware.
        """
        jwt_payload = getattr(self.request, 'jwt_payload', None)
        if jwt_payload:
            user_info = {
                'id': jwt_payload.get('sub'),
                'first_name': jwt_payload.get('first_name', ''),
                'last_name': jwt_payload.get('last_name', ''),
                'email': jwt_payload.get('email', ''),
                'username': jwt_payload.get('username', ''),
                'role': jwt_payload.get('role', ''),
            }
            return user_info
        return None

    def create(self, request, *args, **kwargs):
        logger.info(f"")
        logger.info(f"={'='*60}")
        logger.info(f"========== CREATE TAG REQUEST START ==========")
        logger.info(f"={'='*60}")
        logger.info(f"Method: {request.method}")
        logger.info(f"Path: {request.path}")
        logger.info(f"Request data: {request.data}")

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

        # Get tenant_id from JWT
        jwt_payload = getattr(self.request, 'jwt_payload', None)
        tenant_id = jwt_payload.get('tenant_unique_id') or jwt_payload.get('tenant') if jwt_payload else None
        if not tenant_id:
            tenant_id = 'default-tenant'
        logger.info(f"Tenant ID extracted: {tenant_id}")

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        logger.info(f"✓ Request data validated")

        serializer.save(tenant_id=tenant_id)
        logger.info(f"✓✓✓ Tag created successfully! ✓✓✓")
        logger.info(f"={'='*60}")
        logger.info(f"========== CREATE TAG REQUEST END ==========")
        logger.info(f"={'='*60}")

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        jwt_payload = getattr(self.request, 'jwt_payload', None)
        tenant_id = jwt_payload.get('tenant_unique_id') or jwt_payload.get('tenant') or jwt_payload.get('tenant_id') if jwt_payload else None
        # For development/testing, use default tenant if not provided
        if not tenant_id:
            tenant_id = 'default-tenant'
        serializer.save(tenant_id=tenant_id)

class ArticleViewSet(viewsets.ModelViewSet):
    permission_classes = []  # Empty list means no permission checks
    pagination_class = CustomPagination

    def get_queryset(self):
        jwt_payload = getattr(self.request, 'jwt_payload', None)
        tenant_id = jwt_payload.get('tenant_unique_id') or jwt_payload.get('tenant') or jwt_payload.get('tenant_id') if jwt_payload else None
        # For development/testing, use default tenant if not provided
        if not tenant_id:
            tenant_id = 'default-tenant'
        logger.info(f"ArticleViewSet.get_queryset: tenant_id={tenant_id}, jwt_payload={jwt_payload}")
        queryset = Article.objects.filter(tenant_id=tenant_id).prefetch_related('category', 'tags')
        logger.info(f"ArticleViewSet.get_queryset: found {queryset.count()} articles")

        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Filter by category
        category_filter = self.request.query_params.get('category')
        if category_filter:
            queryset = queryset.filter(category_id=category_filter)

        # Filter by author
        author_filter = self.request.query_params.get('author')
        if author_filter:
            queryset = queryset.filter(author_id=author_filter)

        # Search functionality
        search_query = self.request.query_params.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) |
                Q(content__icontains=search_query) |
                Q(excerpt__icontains=search_query) |
                Q(tags__name__icontains=search_query)
            ).distinct()

        # Filter by tags
        tags_filter = self.request.query_params.getlist('tags')
        if tags_filter:
            queryset = queryset.filter(tags__name__in=tags_filter).distinct()

        return queryset

    def get_serializer_class(self):
        if self.action == 'create':
            return ArticleCreateSerializer
        elif self.action == 'update':
            return ArticleCreateSerializer
        elif self.action == 'list':
            return ArticleListSerializer
        return ArticleSerializer

    def get_current_user_info(self):
        """
        Extract user info from JWT payload that was already validated by middleware.
        """
        jwt_payload = getattr(self.request, 'jwt_payload', None)
        if jwt_payload:
            user_info = {
                'id': jwt_payload.get('sub'),
                'first_name': jwt_payload.get('first_name', ''),
                'last_name': jwt_payload.get('last_name', ''),
                'email': jwt_payload.get('email', ''),
                'username': jwt_payload.get('username', ''),
                'role': jwt_payload.get('role', ''),
            }
            return user_info
        return None

    def create(self, request, *args, **kwargs):
        logger.info(f"")
        logger.info(f"={'='*60}")
        logger.info(f"========== CREATE ARTICLE REQUEST START ==========")
        logger.info(f"={'='*60}")
        logger.info(f"Method: {request.method}")
        logger.info(f"Path: {request.path}")
        logger.info(f"Request data: {request.data}")

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

        jwt_payload = getattr(self.request, 'jwt_payload', None)
        tenant_id = jwt_payload.get('tenant_unique_id') or jwt_payload.get('tenant') or jwt_payload.get('tenant_id') if jwt_payload else None
        # For development/testing, use default tenant if not provided
        if not tenant_id:
            tenant_id = 'default-tenant'

        serializer = self.get_serializer(data=request.data, context={'current_user': current_user, 'request': request})
        serializer.is_valid(raise_exception=True)
        logger.info(f"✓ Request data validated")

        article = serializer.save(tenant_id=tenant_id)
        logger.info(f"✓✓✓ Article created successfully! ID: {article.id} ✓✓✓")
        logger.info(f"={'='*60}")
        logger.info(f"========== CREATE ARTICLE REQUEST END ==========")
        logger.info(f"={'='*60}")

        return Response(
            ArticleSerializer(article).data,
            status=status.HTTP_201_CREATED
        )

    def update(self, request, *args, **kwargs):
        current_user = self.get_current_user_info()
        if not current_user:
            return Response(
                {'detail': 'Authentication required'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, context={'current_user': current_user})
        serializer.is_valid(raise_exception=True)
        article = serializer.save()

        return Response(ArticleSerializer(article).data)

    @action(detail=True, methods=['post'])
    def increment_view(self, request, pk=None):
        """Increment view count for an article"""
        article = self.get_object()
        article.view_count += 1
        article.save()
        return Response({'view_count': article.view_count})

    @action(detail=False, methods=['get'])
    def published(self, request):
        """Get only published articles"""
        queryset = self.get_queryset().filter(status='published')
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = ArticleListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = ArticleListSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def my_articles(self, request):
        """Get articles by current user"""
        current_user = self.get_current_user_info()
        if not current_user:
            return Response(
                {'detail': 'Authentication required'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        queryset = self.get_queryset().filter(author_id=current_user['id'])
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = ArticleListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = ArticleListSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def featured(self, request):
        """Get featured articles (published, with featured image)"""
        queryset = self.get_queryset().filter(
            status='published',
            featured_image__isnull=False
        ).exclude(featured_image='')[:5]  # Limit to 5 featured articles

        serializer = ArticleListSerializer(queryset, many=True)
        return Response(serializer.data)