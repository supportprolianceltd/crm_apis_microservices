
from talent_engine.permissions import IsSubscribedAndAuthorized
from rest_framework import permissions
import logging

logger = logging.getLogger('job_applications')

class IsSubscribedAndAuthorized(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            logger.warning("Unauthenticated user attempted to access view")
            return False

        if request.user.is_superuser:
            return True

        tenant = request.tenant
        if not tenant:
            logger.error("No tenant associated with the request")
            return False

        if not hasattr(request.user, 'tenant') or request.user.tenant != tenant:
            logger.error(f"User {request.user.id} does not belong to tenant {tenant.schema_name}")
            return False

        return True

class BranchRestrictedPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            logger.warning("Unauthenticated user attempted to access view")
            return False

        if request.user.is_superuser or request.user.role == 'team_manager':
            logger.debug(f"User {request.user.id} is superuser or team_manager, granting access")
            return True

        tenant = request.tenant
        if not tenant:
            logger.error("No tenant associated with the request")
            return False

        if not hasattr(request.user, 'tenant') or request.user.tenant != tenant:
            logger.error(f"User {request.user.id} does not belong to tenant {tenant.schema_name}")
            return False

        if request.user.role == 'recruiter' and not request.user.branch:
            logger.error(f"Recruiter {request.user.id} is not assigned to any branch")
            return False

        logger.debug(f"User {request.user.id} granted access with role {request.user.role}")
        return True

    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser or request.user.role == 'team_manager':
            logger.debug(f"User {request.user.id} is superuser or team_manager, granting object access")
            return True

        if request.user.role == 'recruiter' and hasattr(obj, 'branch'):
            if obj.branch == request.user.branch:
                logger.debug(f"Recruiter {request.user.id} granted access to object in branch {obj.branch}")
                return True
            logger.error(f"Recruiter {request.user.id} not authorized for branch {obj.branch}")
            return False

        logger.error(f"User {request.user.id} denied object access due to invalid role or branch")
        return False