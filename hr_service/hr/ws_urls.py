# hr/ws_urls.py
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/performance/(?P<tenant_id>\w+)/$", consumers.PerformanceConsumer.as_asgi()),
]


