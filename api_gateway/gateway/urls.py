# gateway/urls.py
from django.urls import re_path, path
from .views import api_gateway_view, multi_docs_view

urlpatterns = [
    path('api/docs/', multi_docs_view, name='multi-docs'),
    re_path(r'^api/(?P<path>.*)$', api_gateway_view),
]
