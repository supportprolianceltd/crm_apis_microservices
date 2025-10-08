# hr/routing.py

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/performance/(?P<tenant_id>\w+)/$", consumers.PerformanceConsumer.as_asgi()),
]

application = ProtocolTypeRouter({
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    )
})


