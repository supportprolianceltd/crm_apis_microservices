from django.urls import re_path, path
from .views import api_gateway_view

urlpatterns = [
    path('api/schema/', api_gateway_view, {'path': 'auth_service/schema/'}, name='gateway-schema'),
    re_path(r'^api/(?P<path>.*)$', api_gateway_view),
]
