from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # WebSocket proxy for microservices
    re_path(r'ws/(?P<path>.*)/$', consumers.WebSocketProxyConsumer.as_asgi()),
]