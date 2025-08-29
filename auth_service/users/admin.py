from django.contrib import admin
from .models import UserSession

@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'login_time', 'logout_time', 'duration', 'ip_address')
    list_filter = ('user', 'date')
    search_fields = ('user__email', 'ip_address', 'user_agent')
