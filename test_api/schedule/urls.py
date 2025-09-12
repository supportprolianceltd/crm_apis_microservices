from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ScheduleViewSet

router = DefaultRouter()
router.register(r'schedules', ScheduleViewSet, basename='schedule')

urlpatterns = [
    path('', include(router.urls)),  # Maps to /schedule/api/schedules/
    path('schedules/upcoming/', ScheduleViewSet.as_view({'get': 'upcoming'}), name='schedule-upcoming'),
]

