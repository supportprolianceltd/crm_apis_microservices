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
import logging

logger = logging.getLogger('knowledge_base')

class CustomPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = []  # Empty list means no permission checks

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
                'tenant': jwt_payload.get('tenant', ''),
            }
            return user_info
        return None

    def create(self, request, *args, **kwargs):
        current_user = self.get_current_user_info()
        if not current_user:
            return Response(
                {'detail': 'Authentication required'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        # This method is now handled in create() method above
        pass

class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = []  # Empty list means no permission checks

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
                'tenant': jwt_payload.get('tenant', ''),
            }
            return user_info
        return None

    def create(self, request, *args, **kwargs):
        current_user = self.get_current_user_info()
        if not current_user:
            return Response(
                {'detail': 'Authentication required'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        # This method is now handled in create() method above
        pass

class ArticleViewSet(viewsets.ModelViewSet):
    permission_classes = []  # Empty list means no permission checks
    pagination_class = CustomPagination

    def get_queryset(self):
        queryset = Article.objects.all().prefetch_related('category', 'tags')

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
        current_user = self.get_current_user_info()
        if not current_user:
            return Response(
                {'detail': 'Authentication required'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        serializer = self.get_serializer(data=request.data, context={'current_user': current_user, 'request': request})
        serializer.is_valid(raise_exception=True)
        article = serializer.save()

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