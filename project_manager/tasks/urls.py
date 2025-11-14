from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TaskViewSet, CommentViewSet, DailyReportViewSet, user_tasks

router = DefaultRouter()
router.register(r'tasks', TaskViewSet, basename='task')
router.register(r'comments', CommentViewSet)
router.register(r'reports', DailyReportViewSet)

urlpatterns = [
    path('', include(router.urls)),
    # Custom endpoint for user-specific tasks: /api/users/{user_id}/tasks/
    path('users/<str:user_id>/tasks/', user_tasks, name='user-tasks'),
]