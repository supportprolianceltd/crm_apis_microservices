from rest_framework import serializers
from notifications.models import NotificationRecord, TenantCredentials, NotificationTemplate, ChannelType, NotificationStatus
from notifications.utils.encryption import encrypt_data  # For input
from notifications.models import Campaign, CampaignStatus, ChannelType  # Add


class NotificationRecordSerializer(serializers.ModelSerializer):
    channel = serializers.ChoiceField(choices=[(tag.value, tag.name) for tag in ChannelType])
    # In NotificationRecordSerializer
    def validate_recipient(self, value):
        if self.context['channel'] == 'inapp' and value not in ['all', self.context['request'].user.pk]:
            raise serializers.ValidationError("In-app recipient must be 'all' or current user ID.")
        return value


class TenantCredentialsSerializer(serializers.ModelSerializer):
    credentials = serializers.JSONField(write_only=True)  # Encrypt on save

    class Meta:
        model = TenantCredentials
        fields = ['id', 'channel', 'credentials', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def create(self, validated_data):
        creds = validated_data.pop('credentials')
        # Encrypt sensitive fields (e.g., password)
        if 'password' in creds:
            creds['password'] = encrypt_data(creds['password'])
        validated_data['credentials'] = creds
        validated_data['tenant_id'] = self.context['request'].tenant_id
        return super().create(validated_data)
    

class NotificationTemplateSerializer(serializers.ModelSerializer):
    content = serializers.JSONField()

    class Meta:
        model = NotificationTemplate
        fields = ['id', 'name', 'channel', 'content', 'placeholders', 'version', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'version', 'created_at', 'updated_at']

    def create(self, validated_data):
        validated_data['tenant_id'] = self.context['request'].tenant_id
        instance = super().create(validated_data)
        instance.version = 1
        instance.save()
        return instance

class NotificationRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationRecord
        fields = '__all__'
        read_only_fields = ['id', 'status', 'sent_at', 'retry_count', 'created_at', 'updated_at']

    def create(self, validated_data):
        validated_data['tenant_id'] = self.context['request'].tenant_id
        instance = super().create(validated_data)
        # Enqueue immediately
        from notifications.tasks import send_notification_task
        send_notification_task.delay(
            str(instance.id), validated_data['channel'], validated_data['recipient'],
            validated_data.get('content', {}), validated_data.get('context', {})
        )
        return instance
    

    def validate_credentials(self, value):
        channel = self.initial_data.get('channel')

        if channel == 'push':
            required = ['type', 'project_id', 'private_key_id', 'private_key', 'client_email', 'client_id', 'auth_uri', 'token_uri', 'auth_provider_x509_cert_url', 'client_x509_cert_url']
            for key in required:
                if key not in value:
                    raise serializers.ValidationError(f"Push requires '{key}' in credentials (full service account JSON).")
            # Encrypt private_key
            value['private_key'] = encrypt_data(value['private_key'])


        elif channel == 'sms':
            required = ['account_sid', 'auth_token', 'from_phone']
            for key in required:
                if key not in value:
                    raise serializers.ValidationError(f"SMS requires '{key}' in credentials.")
        # Encrypt auth_token for SMS
        if 'auth_token' in value:
            value['auth_token'] = encrypt_data(value['auth_token'])
        return value

    # Add to serializer
    def validate(self, data):
        data['credentials'] = self.validate_credentials(data['credentials'])
        return data
    


class CampaignSerializer(serializers.ModelSerializer):
    class Meta:
        model = Campaign
        fields = '__all__'
        read_only_fields = ['id', 'sent_count', 'status', 'created_at', 'updated_at']

    def create(self, validated_data):
        validated_data['tenant_id'] = self.context['request'].tenant_id
        instance = super().create(validated_data)
        instance.total_recipients = len(validated_data['recipients'])
        instance.save()
        # Enqueue bulk send
        from notifications.tasks import send_bulk_campaign_task
        send_bulk_campaign_task.delay(str(instance.id))
        return instance