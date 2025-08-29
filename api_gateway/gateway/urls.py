from django.urls import re_path
from .views import api_gateway_view

urlpatterns = [
    re_path(r'^api/(?P<path>.*)$', api_gateway_view),
]
