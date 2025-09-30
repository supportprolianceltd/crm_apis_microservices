from django.contrib import admin
from django.urls import path, include
from django.contrib import admin
from django.urls import path




urlpatterns = [
    path('admin/', admin.site.urls),
    
    path('', include('gateway.urls')),

    path('admin/', admin.site.urls),
    #path('api/docs/', multi_docs_view, name='multi-docs'),
]
