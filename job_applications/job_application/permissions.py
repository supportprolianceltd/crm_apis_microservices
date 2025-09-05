from rest_framework.permissions import BasePermission
import logging

logger = logging.getLogger('job_applications')

class IsMicroserviceAuthenticated(BasePermission):
    def has_permission(self, request, view):
        has_user = hasattr(request, 'user') and request.user and request.user.is_authenticated
        logger.info(f"Permission check: user={request.user}, has_user={has_user}, is_authenticated={request.user.is_authenticated if has_user else False}")
        if not has_user:
            logger.warning("No authenticated user found in request")
            return False
        # Optional: Add role-based checks if needed
        if hasattr(request.user, 'role') and request.user.role not in ['admin', 'recruiter']:
            logger.warning(f"User role {request.user.role} not authorized")
            return False
        return True