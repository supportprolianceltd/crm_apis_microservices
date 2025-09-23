import logging
from django.db import transaction
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.exceptions import ValidationError, NotFound
from rest_framework.decorators import action
from django.db.models import Prefetch
from .models import Role, Group, GroupMembership
from .serializers import RoleSerializer, GroupSerializer, GroupMembershipSerializer, get_tenant_id_from_jwt
from activitylog.models import ActivityLog
import requests
from django.conf import settings

logger = logging.getLogger('group_management')

class TenantBaseView(viewsets.GenericViewSet):
    """Base view to handle tenant validation and default roles/groups setup."""
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        jwt_payload = getattr(request, 'jwt_payload', {})
        tenant_id = jwt_payload.get('tenant_unique_id')
        if not tenant_id:
            logger.error("No tenant_unique_id in JWT payload")
            raise ValidationError("Tenant ID not found in token.")
        logger.debug(f"[Tenant {tenant_id}] Schema set for request")

    def ensure_default_roles_and_groups(self):
        """Ensure 'instructors' and 'learners' roles and groups exist."""
        jwt_payload = self.request.jwt_payload
        tenant_id = jwt_payload.get('tenant_unique_id')
        tenant_name = None
        try:
            tenant_response = requests.get(
                f"{settings.AUTH_SERVICE_URL}/api/tenant/tenants/{tenant_id}/",
                headers={'Authorization': self.request.META.get("HTTP_AUTHORIZATION", "")}
            )
            if tenant_response.status_code == 200:
                tenant_data = tenant_response.json()
                tenant_name = tenant_data.get('name')
        except Exception as e:
            logger.error(f"Error fetching tenant name for {tenant_id}: {str(e)}")

        # Define default roles
        default_roles = [
            {
                'name': 'Instructors',
                'code': 'instructors',
                'permissions': ['create_content', 'edit_content', 'grade_assignments', 'view_content'],
                'is_system': True
            },
            {
                'name': 'Learners',
                'code': 'learners',
                'permissions': ['view_content'],
                'is_system': True,
                'is_default': True
            }
        ]

        # Create or update roles
        for role_data in default_roles:
            role, created = Role.objects.get_or_create(
                tenant_id=tenant_id,
                code=role_data['code'],
                defaults={
                    'tenant_id': tenant_id,
                    'tenant_name': tenant_name,
                    'name': role_data['name'],
                    'permissions': role_data['permissions'],
                    'is_system': True,
                    'is_default': role_data.get('is_default', False)
                }
            )
            if not created and role.is_system:
                role.name = role_data['name']
                role.permissions = role_data['permissions']
                role.is_default = role_data.get('is_default', False)
                role.tenant_name = tenant_name
                role.save()

        # Create default groups
        default_groups = [
            {'name': 'All Instructors', 'role_code': 'instructors', 'is_system': True},
            {'name': 'All Learners', 'role_code': 'learners', 'is_system': True}
        ]

        for group_data in default_groups:
            role = Role.objects.get(tenant_id=tenant_id, code=group_data['role_code'])
            Group.objects.get_or_create(
                tenant_id=tenant_id,
                name=group_data['name'],
                defaults={
                    'tenant_name': tenant_name,
                    'role_id': str(role.id),
                    'description': f'Default group for {group_data["role_code"]}',
                    'is_active': True,
                    'is_system': True
                }
            )

class RoleViewSet(TenantBaseView, viewsets.ModelViewSet):
    """Manage roles for a tenant with filtering by is_default."""
    serializer_class = RoleSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['is_default']

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Role.objects.none()
        tenant_id = self.request.jwt_payload.get('tenant_unique_id')
        self.ensure_default_roles_and_groups()
        return Role.objects.filter(tenant_id=tenant_id).order_by('name')

    def create(self, request, *args, **kwargs):
        tenant_id = request.jwt_payload.get('tenant_unique_id')
        serializer = self.get_serializer(data=request.data, context={'request': request})
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            logger.error(f"[Tenant {tenant_id}] Role creation validation failed: {str(e)}")
            raise
        with transaction.atomic():
            role = serializer.save()
            logger.info(f"[Tenant {tenant_id}] Role created: {role.name}")
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        tenant_id = request.jwt_payload.get('tenant_unique_id')
        instance = self.get_object()
        if instance.is_system and ('code' in request.data or 'is_system' in request.data):
            logger.error(f"[Tenant {tenant_id}] Attempt to modify system role {instance.name}")
            raise ValidationError("Cannot modify code or system status of system roles")
        serializer = self.get_serializer(instance, data=request.data, partial=kwargs.get('partial', False), context={'request': request})
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            logger.error(f"[Tenant {tenant_id}] Role update validation failed: {str(e)}")
            raise
        with transaction.atomic():
            role = serializer.save()
            logger.info(f"[Tenant {tenant_id}] Role updated: {role.name}")
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        tenant_id = request.jwt_payload.get('tenant_unique_id')
        instance = self.get_object()
        if instance.is_system:
            logger.error(f"[Tenant {tenant_id}] Attempt to delete system role {instance.name}")
            raise ValidationError("System roles cannot be deleted")
        with transaction.atomic():
            instance.delete()
            logger.info(f"[Tenant {tenant_id}] Role deleted: {instance.name}")
        return Response(status=status.HTTP_204_NO_CONTENT)

    def get_permissions(self):
        return [IsAdminUser()] if self.action in ['create', 'update', 'partial_update', 'destroy'] else [IsAuthenticated()]

class GroupViewSet(TenantBaseView, viewsets.ModelViewSet):
    """Manage groups for a tenant with role and membership prefetching."""
    serializer_class = GroupSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Group.objects.none()
        tenant_id = self.request.jwt_payload.get('tenant_unique_id')
        self.ensure_default_roles_and_groups()
        return Group.objects.filter(tenant_id=tenant_id).prefetch_related(
            Prefetch('memberships', queryset=GroupMembership.objects.filter(tenant_id=tenant_id))
        ).order_by('name')

    def create(self, request, *args, **kwargs):
        tenant_id = request.jwt_payload.get('tenant_unique_id')
        serializer = self.get_serializer(data=request.data, context={'request': request})
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            logger.error(f"[Tenant {tenant_id}] Group creation validation failed: {str(e)}")
            raise
        with transaction.atomic():
            group = serializer.save()
            logger.info(f"[Tenant {tenant_id}] Group created: {group.name}")
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        tenant_id = request.jwt_payload.get('tenant_unique_id')
        instance = self.get_object()
        if instance.is_system and ('name' in request.data or 'role_id' in request.data or 'is_system' in request.data):
            logger.error(f"[Tenant {tenant_id}] Attempt to modify restricted fields of system group {instance.name}")
            raise ValidationError("Cannot modify name, role, or system status of system groups")
        serializer = self.get_serializer(instance, data=request.data, partial=kwargs.get('partial', False), context={'request': request})
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            logger.error(f"[Tenant {tenant_id}] Group update validation failed: {str(e)}")
            raise
        with transaction.atomic():
            group = serializer.save()
            logger.info(f"[Tenant {tenant_id}] Group updated: {group.name}")
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        tenant_id = request.jwt_payload.get('tenant_unique_id')
        instance = self.get_object()
        if instance.is_system:
            logger.error(f"[Tenant {tenant_id}] Attempt to delete system group {instance.name}")
            raise ValidationError("System groups cannot be deleted")
        with transaction.atomic():
            instance.delete()
            logger.info(f"[Tenant {tenant_id}] Group deleted: {instance.name}")
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def add_member(self, request, pk=None):
        tenant_id = request.jwt_payload.get('tenant_unique_id')
        try:
            with transaction.atomic():
                group = self.get_object()
                user_id = request.data.get('user_id')
                if not user_id:
                    logger.warning(f"[Tenant {tenant_id}] Missing user_id for add_member to group {group.name}")
                    return Response({"detail": "user_id is required"}, status=status.HTTP_400_BAD_REQUEST)
                
                # Validate user_id via auth-service
                try:
                    user_response = requests.get(
                        f'{settings.AUTH_SERVICE_URL}/api/user/users/{user_id}/',
                        headers={'Authorization': f'Bearer {request.META.get("HTTP_AUTHORIZATION", "").split(" ")[1]}'}
                    )
                    if user_response.status_code != 200:
                        logger.warning(f"[Tenant {tenant_id}] User {user_id} not found in auth_service")
                        return Response({"detail": f"User with ID {user_id} not found"}, status=status.HTTP_400_BAD_REQUEST)
                    user_data = user_response.json()
                    user_email = user_data.get('email', '')
                except Exception as e:
                    logger.error(f"[Tenant {tenant_id}] Error validating user {user_id}: {str(e)}")
                    return Response({"detail": "Error validating user_id"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

                if GroupMembership.objects.filter(tenant_id=tenant_id, group_id=group.id, user_id=user_id).exists():
                    logger.warning(f"[Tenant {tenant_id}] User {user_id} already a member of group {group.name}")
                    return Response({"detail": f"User {user_id} is already a member of group {group.name}"}, status=status.HTTP_400_BAD_REQUEST)

                membership = GroupMembership.objects.create(
                    tenant_id=tenant_id,
                    tenant_name=group.tenant_name,
                    user_id=user_id,
                    group_id=str(group.id),
                    role_id=group.role_id,
                    is_active=True
                )
                serializer = GroupMembershipSerializer(membership, context={'request': request})
                logger.info(f"[Tenant {tenant_id}] Added user {user_id} to group {group.name}")
                return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"[Tenant {tenant_id}] Error adding member to group {pk}: {str(e)}", exc_info=True)
            return Response({"detail": "Error adding group member"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['delete'], url_path='members/(?P<user_id>[^/.]+)')
    def remove_member(self, request, pk=None, user_id=None):
        tenant_id = request.jwt_payload.get('tenant_unique_id')
        try:
            with transaction.atomic():
                group = self.get_object()
                try:
                    membership = GroupMembership.objects.get(tenant_id=tenant_id, group_id=group.id, user_id=user_id)
                except GroupMembership.DoesNotExist:
                    logger.warning(f"[Tenant {tenant_id}] Membership for user {user_id} in group {group.name} not found")
                    return Response({"detail": f"User {user_id} is not a member of group {group.name}"}, status=status.HTTP_404_NOT_FOUND)

                # Fetch user email for logging
                user_email = 'unknown'
                try:
                    user_response = requests.get(
                        f'{settings.AUTH_SERVICE_URL}/api/user/users/{user_id}/',
                        headers={'Authorization': f'Bearer {request.META.get("HTTP_AUTHORIZATION", "").split(" ")[1]}'}
                    )
                    if user_response.status_code == 200:
                        user_email = user_response.json().get('email', 'unknown')
                except Exception as e:
                    logger.error(f"[Tenant {tenant_id}] Error fetching user {user_id} for logging: {str(e)}")

                membership.delete()
                logger.info(f"[Tenant {tenant_id}] Removed user {user_id} from group {group.name}")
                return Response({"detail": f"User {user_id} removed from group {group.name}"}, status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            logger.error(f"[Tenant {tenant_id}] Error removing member {user_id} from group {pk}: {str(e)}", exc_info=True)
            return Response({"detail": "Error removing group member"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def update_members(self, request, pk=None):
        tenant_id = request.jwt_payload.get('tenant_unique_id')
        try:
            with transaction.atomic():
                group = self.get_object()
                member_ids = request.data.get('members', [])
                if not isinstance(member_ids, list):
                    logger.warning(f"[Tenant {tenant_id}] Invalid input for update_members: members must be a list")
                    return Response({"detail": "members must be a list"}, status=status.HTTP_400_BAD_REQUEST)

                # Validate user IDs
                existing_users = set()
                for user_id in member_ids:
                    try:
                        user_response = requests.get(
                            f'{settings.AUTH_SERVICE_URL}/api/user/users/{user_id}/',
                            headers={'Authorization': f'Bearer {request.META.get("HTTP_AUTHORIZATION", "").split(" ")[1]}'}
                        )
                        if user_response.status_code == 200:
                            existing_users.add(user_id)
                        else:
                            logger.warning(f"[Tenant {tenant_id}] User {user_id} not found in auth_service")
                    except Exception as e:
                        logger.error(f"[Tenant {tenant_id}] Error validating user {user_id}: {str(e)}")

                invalid_ids = set(member_ids) - existing_users
                if invalid_ids:
                    logger.warning(f"[Tenant {tenant_id}] Invalid user IDs for group {group.name}: {invalid_ids}")
                    return Response({"detail": f"Invalid user IDs: {invalid_ids}"}, status=status.HTTP_400_BAD_REQUEST)

                current_members = set(GroupMembership.objects.filter(tenant_id=tenant_id, group_id=group.id).values_list('user_id', flat=True))
                new_member_ids = set(member_ids) - current_members
                removed_member_ids = current_members - set(member_ids)

                for user_id in new_member_ids:
                    GroupMembership.objects.create(
                        tenant_id=tenant_id,
                        tenant_name=group.tenant_name,
                        user_id=user_id,
                        group_id=str(group.id),
                        role_id=group.role_id
                    )
                GroupMembership.objects.filter(tenant_id=tenant_id, group_id=group.id, user_id__in=removed_member_ids).delete()

                logger.info(f"[Tenant {tenant_id}] Updated members for group {group.name}: {len(new_member_ids)} added, {len(removed_member_ids)} removed")
                return Response({
                    "detail": "Group members updated",
                    "added": list(new_member_ids),
                    "removed": list(removed_member_ids),
                    "total_members": GroupMembership.objects.filter(tenant_id=tenant_id, group_id=group.id).count()
                }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"[Tenant {tenant_id}] Error updating members for group {pk}: {str(e)}", exc_info=True)
            return Response({"detail": "Error updating group members"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'])
    def members(self, request, pk=None):
        tenant_id = request.jwt_payload.get('tenant_unique_id')
        try:
            group = self.get_object()
            memberships = GroupMembership.objects.filter(tenant_id=tenant_id, group_id=group.id)
            serializer = GroupMembershipSerializer(memberships, many=True, context={'request': request})
            logger.info(f"[Tenant {tenant_id}] Retrieved members for group {group.name}")
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"[Tenant {tenant_id}] Error retrieving members for group {pk}: {str(e)}", exc_info=True)
            return Response({"detail": "Error retrieving group members"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], url_path='by-name/(?P<name>[^/.]+)/members')
    def members_by_name(self, request, name=None):
        tenant_id = request.jwt_payload.get('tenant_unique_id')
        try:
            group = Group.objects.get(tenant_id=tenant_id, name__iexact=name)
            memberships = GroupMembership.objects.filter(tenant_id=tenant_id, group_id=group.id)
            serializer = GroupMembershipSerializer(memberships, many=True, context={'request': request})
            logger.info(f"[Tenant {tenant_id}] Retrieved members for group {name}")
            return Response(serializer.data)
        except Group.DoesNotExist:
            logger.warning(f"[Tenant {tenant_id}] Group {name} not found")
            raise NotFound(f"Group with name '{name}' not found")
        except Exception as e:
            logger.error(f"[Tenant {tenant_id}] Error retrieving members for group {name}: {str(e)}", exc_info=True)
            return Response({"detail": "Error retrieving group members"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get_permissions(self):
        return [IsAdminUser()] if self.action in ['create', 'update', 'partial_update', 'destroy', 'update_members', 'add_member', 'remove_member'] else [IsAuthenticated()]