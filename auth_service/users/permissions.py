from rest_framework import permissions
from core.models import Branch
from users.models import CustomUser

class BranchRestrictedPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        user = request.user
        if user.is_superuser or user.role in ['admin', 'team_manager']:
            return True
        if user.branch:
            return True
        return False