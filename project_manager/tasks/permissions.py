from rest_framework import permissions

class IsAuthenticatedWithAuthService(permissions.BasePermission):
    """
    Custom permission that trusts the JWT middleware authentication.
    Since the JWT middleware has already verified the token and set request.user,
    we just need to check if the user is authenticated.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated