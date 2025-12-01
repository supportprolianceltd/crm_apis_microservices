import logging
from rest_framework import serializers
from .models import Event
from users.models import CustomUser

logger = logging.getLogger(__name__)

def get_user_data_from_jwt(request):
    """Extract user data from the authenticated request user."""
    if not request.user or not request.user.is_authenticated:
        logger.warning("No authenticated user available in request")
        raise serializers.ValidationError("Authentication required. No user found in request.")

    user = request.user
    logger.info(f"Extracting user data from request user: {user.email}, ID: {user.id}")

    return {
        'email': user.email,
        'first_name': user.first_name or '',
        'last_name': user.last_name or '',
        'job_role': getattr(user, 'job_role', ''),
        'id': user.id
    }

class EventSerializer(serializers.ModelSerializer):
    participants_details = serializers.SerializerMethodField(read_only=True)
    creator_details = serializers.SerializerMethodField(read_only=True)
    tenant_details = serializers.SerializerMethodField(read_only=True)
    last_updated_by = serializers.SerializerMethodField(read_only=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter participants by tenant
        if self.context.get('request'):
            request = self.context['request']
            tenant = getattr(request, 'tenant', getattr(request.user, 'tenant', None) if request.user else None)
            if tenant:
                self.fields['participants'] = serializers.PrimaryKeyRelatedField(
                    many=True,
                    queryset=CustomUser.objects.filter(tenant=tenant),
                    required=False
                )
            else:
                self.fields['participants'] = serializers.PrimaryKeyRelatedField(
                    many=True,
                    queryset=CustomUser.objects.none(),
                    required=False
                )
        else:
            self.fields['participants'] = serializers.PrimaryKeyRelatedField(
                many=True,
                queryset=CustomUser.objects.none(),
                required=False
            )

    class Meta:
        model = Event
        fields = [
            'id', 'title', 'description', 'start_datetime', 'end_datetime',
            'location', 'meeting_link', 'creator', 'tenant', 'visibility', 'include_all_tenant_users', 'participants',
            'participants_details', 'creator_details', 'tenant_details', 'created_at',
            'updated_at', 'last_updated_by_id', 'last_updated_by'
        ]
        read_only_fields = ['id', 'creator', 'tenant', 'created_at', 'updated_at', 'last_updated_by', 'last_updated_by_id']

    def get_participants_details(self, obj):
        return [
            {
                'id': participant.id,
                'email': participant.email,
                'first_name': participant.first_name,
                'last_name': participant.last_name,
                'role': participant.role
            }
            for participant in obj.participants.all()
        ]

    def get_creator_details(self, obj):
        return {
            'id': obj.creator.id,
            'email': obj.creator.email,
            'first_name': obj.creator.first_name,
            'last_name': obj.creator.last_name,
            'role': obj.creator.role
        }

    def get_tenant_details(self, obj):
        return {
            'id': obj.tenant.id,
            'name': obj.tenant.name,
            'schema_name': obj.tenant.schema_name
        }

    def get_last_updated_by(self, obj):
        if obj.last_updated_by_id:
            try:
                user = CustomUser.objects.get(id=obj.last_updated_by_id)
                return {
                    'id': user.id,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name
                }
            except CustomUser.DoesNotExist:
                return None
        return None

    def validate(self, data):
        """Ensure data belongs to current tenant"""
        request = self.context.get('request')
        if request and hasattr(request, 'user') and hasattr(request.user, 'tenant'):
            # ✅ Ensure created objects belong to current tenant
            data['tenant'] = request.user.tenant

        start_datetime = data.get('start_datetime')
        end_datetime = data.get('end_datetime')
        visibility = data.get('visibility')
        include_all_tenant_users = data.get('include_all_tenant_users', False)
        participants = data.get('participants', [])

        if start_datetime and end_datetime and start_datetime >= end_datetime:
            raise serializers.ValidationError("End datetime must be after start datetime.")

        if visibility == 'specific_users' and not participants:
            raise serializers.ValidationError("Participants are required when visibility is 'specific_users'.")

        if include_all_tenant_users and participants:
            raise serializers.ValidationError("Participants should not be specified when include_all_tenant_users is true.")

        return data

    def create(self, validated_data):
        """Auto-assign tenant, creator, and last_updated_by on creation"""
        request = self.context.get('request')

        # Auto-assign tenant
        if request and hasattr(request, 'user') and hasattr(request.user, 'tenant'):
            validated_data['tenant'] = request.user.tenant

        # Auto-assign creator
        if 'creator' not in validated_data:
            if request and hasattr(request, 'user'):
                validated_data['creator'] = request.user

        # Set last_updated_by
        user_data = get_user_data_from_jwt(request)
        user_id = user_data.get('id')
        if user_id:
            validated_data['last_updated_by_id'] = str(user_id)
        else:
            logger.warning("No user_id found in JWT payload for creation")
            raise serializers.ValidationError({"last_updated_by_id": "User ID required for creation."})

        instance = super().create(validated_data)

        if instance.include_all_tenant_users:
            tenant_users = CustomUser.objects.filter(tenant=instance.tenant)
            instance.participants.set(tenant_users)

        return instance

    def update(self, instance, validated_data):
        user_data = get_user_data_from_jwt(self.context['request'])
        user_id = user_data.get('id')
        if user_id:
            instance.last_updated_by_id = str(user_id)
        else:
            logger.warning("No user_id found in JWT payload for update")

        instance = super().update(instance, validated_data)

        if instance.include_all_tenant_users:
            tenant_users = CustomUser.objects.filter(tenant=instance.tenant)
            instance.participants.set(tenant_users)

        return instance