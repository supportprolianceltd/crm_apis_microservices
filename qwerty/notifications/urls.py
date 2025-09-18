from django.urls import path
from .views import NotificationListView,  NotificationTestView

urlpatterns = [
    path('test/', NotificationTestView.as_view(), name='notification-test'),
    path('<str:tenant_id>/<str:user_id>/', NotificationListView.as_view()),
]
