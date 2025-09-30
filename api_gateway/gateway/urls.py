# # gateway/urls.py
# from django.urls import re_path, path
# from .views import api_gateway_view, health_check

# urlpatterns = [
#     #path('api/docs/', multi_docs_view, name='multi-docs'),
#     re_path(r'^api/(?P<path>.*)$', api_gateway_view),
#     path('health/', health_check, name='health_check'),
# ]




from django.urls import path, re_path
from . import views

urlpatterns = [
    path('health/', views.health_check, name='health_check'),
    path('metrics/', views.gateway_metrics, name='gateway_metrics'),
    path('circuit-breaker/status/', views.circuit_breaker_status, name='circuit_breaker_status'),
    path('circuit-breaker/reset/<str:service_name>/', views.reset_circuit_breaker, name='reset_circuit_breaker'),
    re_path(r'^api/(?P<path>.*)$', views.api_gateway_view, name='api_gateway'),
]

handler404 = views.handle_404
handler500 = views.handle_500
handler403 = views.handle_403
handler400 = views.handle_400


