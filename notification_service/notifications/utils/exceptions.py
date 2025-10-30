from rest_framework.exceptions import APIException

class TenantValidationError(APIException):
    status_code = 403
    default_detail = 'Tenant validation failed.'
    default_code = 'tenant_validation'

class ChannelNotConfiguredError(APIException):
    status_code = 400
    default_detail = 'Channel not configured for tenant.'
    default_code = 'channel_not_configured'

class NotificationFailedError(APIException):
    status_code = 500
    default_detail = 'Notification delivery failed.'
    default_code = 'delivery_failed'