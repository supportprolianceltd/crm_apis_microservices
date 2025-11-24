import string
from datetime import timedelta
from django.conf import settings
from django_tenants.utils import get_public_schema_name
from rest_framework import status
from core.models import Tenant


class ErrorMessages:
    INVALID_TOKEN_FORMAT = "Invalid token format"
    NO_VALID_BEARER_TOKEN = "No valid Bearer token provided"
    TENANT_NOT_FOUND = "Tenant not found"
    INVALID_TOKEN = "Invalid token"
    ERROR_EXTRACTING_TENANT = "Error extracting tenant: {}"
    USER_NOT_FOUND = "User not found."
    USER_NOT_FOUND_WITH_ID = "User with ID {} not found"
    USER_NOT_FOUND_OR_NOT_IN_TENANT = "User not found or does not belong to this tenant."
    TARGET_USER_NOT_FOUND = "Target user not found."
    DOCUMENT_NOT_FOUND = "Document not found"
    INVALID_LOGIN_TIME_FORMAT = "Invalid login_time format. Use ISO 8601."
    INVALID_LOGOUT_TIME_FORMAT = "Invalid logout_time format. Use ISO 8601."
    INVALID_DATE_FORMAT = "Invalid date format. Use YYYY-MM-DD."
    NO_OPEN_SESSION_FOUND = "No open session found."
    YOU_ALREADY_HAVE_OPEN_SESSION = "You already have an open session. Please clock out first."
    INVALID_EMAIL_FORMAT = "Invalid email format: {}, error: {}"
    NO_USER_FOUND_WITH_EMAIL = "No user found with this email"
    ACCOUNT_LOCKED_OR_SUSPENDED = "Account is locked or suspended"
    THIS_IP_ADDRESS_IS_BLOCKED = "This IP address is blocked"
    INVALID_OR_EXPIRED_TOKEN = "Invalid or expired token."
    THIS_TOKEN_HAS_ALREADY_BEEN_USED = "This token has already been used."
    THIS_TOKEN_HAS_EXPIRED = "This token has expired."
    ACCOUNT_IS_LOCKED_OR_SUSPENDED = "Account is locked or suspended."
    PASSWORD_RESET_FAILED = "Password reset failed."
    USER_ID_IS_REQUIRED = "user_id is required."
    TENANT_ID_AND_SCHEMA_ARE_REQUIRED = "tenant_id and tenant_schema are required for public registration."
    INVALID_TENANT_INFORMATION = "Invalid tenant information."
    THE_PROVIDED_EMAIL_ADDRESS_ALREADY_EXISTS = "The provided email address already exists. Please use a different email."
    NO_TENANT_FOUND_FOR_EMAIL_DOMAIN = "No tenant found for email domain: {}"
    EITHER_TENANT_ID_OR_SCHEMA_NAME_IS_REQUIRED = "Either tenant_id or schema_name is required"
    RSA_KEYPAIR_CREATED_SUCCESSFULLY = "RSAKeyPair created successfully for tenant {}"
    ONLY_ADMINS_OR_SUPERUSERS_CAN_CREATE_USERS = "Only admins or superusers can create users."
    CANNOT_SET_USER_ROLE_TO_ADMIN = "Cannot set user role to 'admin'."
    ONLY_ADMINS_OR_TEAM_MANAGERS_CAN_UPDATE_USER_BRANCH = "Only admins or team managers can update user branch"
    UNAUTHORIZED_BRANCH_UPDATE_ATTEMPT = "Unauthorized branch update attempt by user {} for user {}"
    ONLY_ADMINS_OR_TEAM_MANAGERS_CAN_LIST_ALL_TENANT_USERS = "Only admins or team managers can list all tenant users"
    ONLY_ADMINS_OR_SUPERUSERS_CAN_CREATE_CLIENTS = "Only admins or superusers can create clients."
    YOU_DO_NOT_HAVE_PERMISSION_TO_UPDATE_THIS_CLIENT = "You do not have permission to update this client."
    YOU_DO_NOT_HAVE_PERMISSION_TO_DELETE_CLIENTS = "You do not have permission to delete clients."
    ONLY_ADMINS_OR_SUPERUSERS_CAN_CREATE_GROUPS = "Only admins or superusers can create groups."
    ONLY_ADMINS_OR_SUPERUSERS_CAN_UPDATE_GROUPS = "Only admins or superusers can update groups."
    ONLY_ADMINS_OR_SUPERUSERS_CAN_DELETE_GROUPS = "Only admins or superusers can delete groups."
    ONLY_ADMINS_OR_SUPERUSERS_CAN_ADD_MEMBERS_TO_GROUPS = "Only admins or superusers can add members to groups."
    USER_IS_ALREADY_A_MEMBER_OF_THIS_GROUP = "User is already a member of this group."
    ONLY_ADMINS_OR_SUPERUSERS_CAN_REMOVE_MEMBERS_FROM_GROUPS = "Only admins or superusers can remove members from groups."
    USER_IS_NOT_A_MEMBER_OF_THIS_GROUP = "User is not a member of this group."
    PAYLOAD_MUST_BE_A_LIST_OF_USER_OBJECTS = "Payload must be a list of user objects"
    PAYLOAD_MUST_BE_A_LIST_OF_CLIENT_OBJECTS = "Payload must be a list of client objects"
    CLIENT_USERS_CANNOT_BE_CREATED_VIA_THIS_ENDPOINT = "Client users cannot be created via this endpoint."
    EMAIL_AND_PASSWORD_REQUIRED = "Email and password required"
    INVALID_CREDENTIALS_OR_TENANT = "Invalid credentials or tenant"
    MISSING_TOKEN = "Missing token"
    AUTHENTICATION_REQUIRED = "Authentication required"
    NO_TENANT_ASSOCIATED_WITH_USER = "No tenant associated with user"
    EITHER_USER_ID_OR_EMAIL_QUERY_PARAMETER_IS_REQUIRED = "Either 'user_id' or 'email' query parameter is required."
    NO_ACCESS_FOUND_FOR_THE_SPECIFIED_USER = "No access found for the specified user."
    YOU_HAVE_ALREADY_ACKNOWLEDGED_THIS_DOCUMENT = "You have already acknowledged this document"
    FAILED_TO_GENERATE_IMPERSONATION_TOKENS = "Failed to generate impersonation tokens: {}"
    CANNOT_CREATE_CLIENT_USER_AT_INDEX = "Cannot create client user at index {} via UserViewSet"
    CANNOT_SET_ROLE_TO_ADMIN_AT_INDEX = "Cannot set role to admin at index {} via UserViewSet"
    FAILED_TO_CREATE_USER_AT_INDEX = "Failed to create user at index {}: {}"
    FAILED_TO_CREATE_CLIENT_AT_INDEX = "Failed to create client at index {}: {}"


class LogMessages:
    PROCESSING_PASSWORD_RESET_REQUEST = "Processing password reset request with data: {}"
    SERIALIZER_VALIDATION_FAILED = "Serializer validation failed: {}"
    PROCESSING_PASSWORD_RESET_FOR_EMAIL = "Processing password reset for email: {}"
    EMAIL_DOMAIN = "Email domain: {}"
    NO_DOMAIN_FOUND_FOR_EMAIL_DOMAIN = "No domain found for email domain: {}"
    FOUND_TENANT_FOR_EMAIL_DOMAIN = "Found tenant: {} for email domain: {}"
    USER_WITH_EMAIL_NOT_FOUND = "No user found with email {} in tenant {}"
    USER_LOCKED_OR_SUSPENDED = "User {} is locked or suspended in tenant {}"
    IP_BLOCKED = "IP {} is blocked for tenant {}"
    PASSWORD_RESET_TOKEN_CREATED = "Password reset token created for user {} in tenant {}"
    NOTIFICATION_SENT_FOR_PASSWORD_RESET = "Notification sent for password reset: {}, Status: {}"
    FAILED_TO_SEND_PASSWORD_RESET_NOTIFICATION = "Failed to send password reset notification for {}: {}"
    PASSWORD_RESET_TOKEN_GENERATED_SUCCESSFULLY = "Password reset token generated successfully."
    PROCESSING_PASSWORD_RESET_CONFIRMATION = "Processing password reset confirmation with data: {}"
    VALIDATION_FAILED_FOR_PASSWORD_RESET_CONFIRMATION = "Validation failed for password reset confirmation: {}"
    PROCESSING_PASSWORD_RESET_CONFIRMATION_IN_TENANT = "Processing password reset confirmation in tenant: {}"
    INVALID_TOKEN = "Invalid token {} in schema {}"
    TOKEN_ALREADY_USED = "Token {} already used in schema {}"
    TOKEN_EXPIRED = "Token {} expired in schema {}"
    PASSWORD_RESET_SUCCESSFUL = "Password reset successful for user {} in tenant {}"
    NOTIFICATION_SENT_FOR_PASSWORD_RESET_CONFIRMATION = "Notification sent for password reset confirmation: {}, Status: {}"
    FAILED_TO_SEND_PASSWORD_RESET_CONFIRMATION_NOTIFICATION = "Failed to send password reset confirmation notification for {}: {}"
    ERROR_DURING_PASSWORD_RESET_CONFIRMATION = "Error during password reset confirmation in schema {}: {}"
    TENANT_FROM_REQUEST = "Tenant from request: {}"
    TENANT_FROM_USER = "Tenant from user: {}"
    TENANT_EXTRACTED_FROM_TOKEN_BY_ID = "Tenant extracted from token by ID: {}"
    TENANT_EXTRACTED_FROM_TOKEN_BY_SCHEMA = "Tenant extracted from token by schema: {}"
    NO_TENANT_ID_OR_SCHEMA_NAME_IN_TOKEN = "No tenant_id or schema_name in token"
    USER_HAS_ALREADY_ACCEPTED_TERMS = "User {} has already accepted terms and conditions."
    USER_ACCEPTED_TERMS = "User {} accepted terms and conditions for tenant {}."
    RAW_PATCH_REQUEST_DATA = "Raw PATCH request data for tenant {}: {}"
    FILES_IN_REQUEST = "FILES in request: {}"
    VALIDATED_DATA_FOR_USER = "Validated data for user {}: {}"
    SERIALIZER_ERRORS_FOR_USER = "Serializer errors for user {}: {}"
    USER_UPDATED_BY = "User {} updated by {} in tenant {}"
    USER_DELETED_BY = "User {} deleted by {} in tenant {}"
    USER_CREATED = "User created: {} (ID: {}) for tenant {}"
    ADMIN_USER_CREATED = "Admin user created: {} for tenant {}"
    PUBLIC_USER_CREATED = "Public user created: {} (ID: {}) for tenant {}"
    USER_LOCKED_BY = "User {} locked by {} in tenant {}"
    USER_UNLOCKED_BY = "User {} unlocked by {} in tenant {}"
    USER_SUSPENDED_BY = "User {} suspended by {} in tenant {}"
    USER_ACTIVATED_BY = "User {} activated by {} in tenant {}"
    USER_IMPERSONATED_BY = "User {} impersonated by {} in tenant {}"
    USER_BRANCH_ASSIGNED = "User {} assigned to branch {} for tenant {}"
    RETRIEVED_USERS_FOR_TENANT = "Retrieved {} users for tenant {}"
    RETRIEVED_USERS_FOR_BRANCH = "Retrieved {} users for branch {}"
    BULK_CREATE_COMPLETED = "Bulk create completed in tenant {}: {} succeeded, {} failed"
    BULK_CLIENT_CREATE_COMPLETED = "Bulk client create completed in tenant {}: {} succeeded, {} failed"
    CREATED_USER_DURING_BULK = "Created user {} in tenant {} during bulk create"
    CREATED_CLIENT_DURING_BULK = "Created client {} in tenant {} during bulk create"
    PASSWORD_RESET_FOR_USER_BY = "Password reset for user {} by {} in tenant {}"
    USER_WITH_ID_NOT_FOUND = "User with id {} not found in tenant {}"
    USER_WITH_EMAIL_NOT_FOUND = "No user found with email {} in tenant {}"
    USER_LOCKED_OR_SUSPENDED = "User {} is locked or suspended in tenant {}"
    IP_BLOCKED = "IP {} is blocked for tenant {}"
    INVALID_TOKEN = "Invalid token {} in schema {}"
    TOKEN_ALREADY_USED = "Token {} already used in schema {}"
    TOKEN_EXPIRED = "Token {} expired in schema {}"
    PASSWORD_RESET_SUCCESSFUL = "Password reset successful for user {} in tenant {}"
    USING_PROVIDED_EMAIL = "Using provided email: {} for public registration"
    RSA_KEYPAIR_CREATED = "RSAKeyPair created for tenant: {}, kid: {}"
    USER_ATTEMPTED_BULK_CREATE_WITHOUT_PERMISSION = "User {} attempted bulk create without permission in tenant {}"
    USER_ATTEMPTED_BULK_CLIENT_CREATE_WITHOUT_PERMISSION = "User {} attempted bulk client create without permission in tenant {}"
    UNAUTHORIZED_BRANCH_UPDATE = "Unauthorized branch update attempt by user {} for user {}"
    VALIDATION_ERROR_FOR_USER = "Validation error for user {} in tenant {}: {}"
    ERROR_UPDATING_BRANCH = "Error updating branch for user {} in tenant {}: {}"
    RETRIEVED_DOCUMENTS = "Retrieved {} documents for tenant {}"
    DOCUMENT_CREATED = "Document created: {} for tenant {}"
    DOCUMENT_RETRIEVED = "Retrieved document {} for tenant {}"
    DOCUMENT_UPDATED = "Document updated: {} for tenant {}, version {}"
    DOCUMENT_DELETED = "Document deleted: {} for tenant {}"
    RETRIEVED_VERSIONS = "Retrieved {} versions for document {} in tenant {}"
    DOCUMENT_ACKNOWLEDGED = "Document {} acknowledged by {} in tenant {}"
    RETRIEVED_ACKNOWLEDGMENTS = "Retrieved {} acknowledgments for document {} in tenant {}"
    RETRIEVED_DOCUMENTS_FOR_USER = "Retrieved {} documents for user {} in tenant {}"
    ERROR_LISTING_DOCUMENTS = "Error listing documents for tenant {}: {}"
    ERROR_CREATING_DOCUMENT = "Error creating document: {}"
    VALIDATION_ERROR = "Validation error: {}"
    ERROR_RETRIEVING_DOCUMENT = "Error retrieving document for tenant {}: {}"
    ERROR_UPDATING_DOCUMENT = "Error updating document for tenant {}: {}"
    ERROR_DELETING_DOCUMENT = "Error deleting document for tenant {}: {}"
    ERROR_RETRIEVING_VERSIONS = "Error retrieving versions for document {} in tenant {}: {}"
    ERROR_ACKNOWLEDGING_DOCUMENT = "Error acknowledging document for tenant {}: {}"
    ERROR_RETRIEVING_ACKNOWLEDGMENTS = "Error retrieving acknowledgments for document {} in tenant {}: {}"
    ERROR_RETRIEVING_USER_DOCUMENT_ACCESS = "Error retrieving user document access for tenant {}: {}"
    PROCESSING_PASSWORD_RESET_REQUEST = "Processing password reset request with data: {}"
    SERIALIZER_VALIDATION_FAILED = "Serializer validation failed: {}"
    PROCESSING_PASSWORD_RESET_FOR_EMAIL = "Processing password reset for email: {}"
    EMAIL_DOMAIN = "Email domain: {}"
    FOUND_TENANT_FOR_EMAIL_DOMAIN = "Found tenant: {} for email domain: {}"
    NO_DOMAIN_FOUND_FOR_EMAIL_DOMAIN = "No domain found for email domain: {}"
    PASSWORD_RESET_TOKEN_CREATED = "Password reset token created for user {} in tenant {}"
    NOTIFICATION_SENT_FOR_PASSWORD_RESET = "Notification sent for password reset: {}, Status: {}"
    FAILED_TO_SEND_PASSWORD_RESET_NOTIFICATION = "Failed to send password reset notification for {}: {}"
    PROCESSING_PASSWORD_RESET_CONFIRMATION = "Processing password reset confirmation with data: {}"
    VALIDATION_FAILED_FOR_PASSWORD_RESET_CONFIRMATION = "Validation failed for password reset confirmation: {}"
    PROCESSING_PASSWORD_RESET_CONFIRMATION_IN_TENANT = "Processing password reset confirmation in tenant: {}"
    NOTIFICATION_SENT_FOR_PASSWORD_RESET_CONFIRMATION = "Notification sent for password reset confirmation: {}, Status: {}"
    FAILED_TO_SEND_PASSWORD_RESET_CONFIRMATION_NOTIFICATION = "Failed to send password reset confirmation notification for {}: {}"
    ERROR_DURING_PASSWORD_RESET_CONFIRMATION = "Error during password reset confirmation in schema {}: {}"
    REACHED_USER_CREATION_SUCCESS_BLOCK = "🎯 Reached user creation success block. Sending user creation event to notification service."
    REACHED_ADMIN_USER_CREATION_SUCCESS_BLOCK = "🎯 Reached admin user creation success block. Sending user creation event to notification service."
    SENDING_USER_CREATION_EVENT = "🎯 Sending user creation event for {} to notification service."
    POST_TO_NOTIFICATIONS_URL = "➡️ POST to {} with payload: {}"
    NOTIFICATION_SENT_FOR_USER = "✅ Notification sent for {}. Status: {}, Response: {}"
    NOTIFICATION_ERROR = "[❌ Notification Error] Failed to send user creation event for {}: {}"
    NOTIFICATION_EXCEPTION = "[❌ Notification Exception] Unexpected error for {}: {}"
    PUBLIC_REGISTRATION_NOTIFICATION_SENT = "✅ Public registration notification sent for {}. Status: {}"
    PUBLIC_REGISTRATION_NOTIFICATION_ERROR = "[❌ Notification Error] Failed to send public registration event for {}: {}"
    IMPERSONATION_FAILED = "Impersonation failed for {}: {}"
    CLOCKED_IN = "Clocked in."
    CLOCKED_OUT = "Clocked out."
    DAILY_HISTORY = "sessions"
    TOTAL_TIME = "total_time"
    ERROR_PROCESSING_TENANT = "Error processing tenant {}: {}"
    USER_EMAIL_NOT_FOUND = "No user found with email {}"
    USER_ACCOUNT_LOCKED_OR_SUSPENDED = "User {} account is locked or suspended"
    IP_ADDRESS_BLOCKED = "IP {} is blocked"
    INVALID_TOKEN_IN_SCHEMA = "Invalid token {} in schema {}"
    TOKEN_ALREADY_USED_IN_SCHEMA = "Token {} already used in schema {}"
    TOKEN_EXPIRED_IN_SCHEMA = "Token {} expired in schema {}"
    PASSWORD_RESET_SUCCESSFUL_FOR_USER = "Password reset successful for user {} in tenant {}"
    RSA_KEYPAIR_CREATED_FOR_TENANT = "RSAKeyPair created for tenant: {}, kid: {}"
    TENANT_NOT_FOUND_TENANT_ID_SCHEMA = "Tenant not found: tenant_id={}, schema_name={}"
    ERROR_CREATING_RSA_KEYPAIR = "Error creating RSAKeyPair: {}"
    IP_BLOCKED_BY = "IP {} blocked by {} in tenant {}"
    IP_UNBLOCKED_BY = "IP {} unblock by {} in tenant {}"
    IP_UPDATED_BY = "IP {} updated by {} in tenant {}"


class ResponseKeys:
    STATUS = "status"
    MESSAGE = "message"
    DETAIL = "detail"
    ERROR = "error"
    DATA = "data"
    USER_ID = "user_id"
    EMAIL = "email"
    NEW_PASSWORD = "new_password"
    USERNAME = "username"
    JOB_ROLE = "job_role"
    TENANT_ID = "tenant_id"
    TENANT_SCHEMA = "tenant_schema"
    BRANCH = "branch"
    REFRESH = "refresh"
    ACCESS = "access"
    SESSION_ID = "session_id"
    DURATION = "duration"
    SESSIONS = "sessions"
    TOTAL_TIME = "total_time"
    TENANTS = "tenants"
    TOTAL_COUNT = "total_count"
    TOTAL_TENANTS = "total_tenants"
    CREATED = "created"
    ERRORS = "errors"
    UNIQUE_ID = "unique_id"
    NAME = "name"
    PRIMARY_DOMAIN = "primary_domain"
    ALL_DOMAINS = "all_domains"
    STATUS_KEY = "status"
    ROOT_ADMIN = "root_admin"
    COUNT = "count"
    CREATED_AT = "created_at"
    USERS = "users"
    SCHEMA_NAME = "schema_name"
    TEMP_PASSWORD = "temp_password"
    LOGIN_LINK = "login_link"
    TIMESTAMP = "timestamp"
    USER_AGENT = "user_agent"
    USER_ID_STR = "user_id"
    COMPANY_NAME = "company_name"
    KID = "kid"
    PUBLIC_KEY = "public_key"
    TENANT_DOMAIN = "tenant_domain"
    EXPORT_INFO = "export_info"
    EXPORTED_AT = "exported_at"
    TOTAL_RECORDS = "total_records"
    FORMAT = "format"
    PERIOD = "period"
    ACTIVITIES = "activities"
    USER_INFO = "user_info"
    FIRST_NAME = "first_name"
    LAST_NAME = "last_name"
    ROLE = "role"
    SUMMARY = "summary"
    TOTAL_ACTIVITIES_AS_SUBJECT = "total_activities_as_subject"
    TOTAL_ACTIVITIES_AS_PERFORMER = "total_activities_as_performer"
    AVERAGE_DAILY_ACTIVITIES = "average_daily_activities"
    ACTIVITY_BREAKDOWN = "activity_breakdown"
    DAILY_ACTIVITY_PATTERN = "daily_activity_pattern"
    TOP_ACTIONS = "top_actions"
    RECENT_ACTIVITIES = "recent_activities"
    METRICS = "metrics"
    THRESHOLDS = "thresholds"
    SUMMARY_METRICS = "summary_metrics"
    ACTIVITIES_BY_TYPE = "activities_by_type"
    TOP_ACTIVE_USERS = "top_active_users"
    DAILY_ACTIVITY_TREND = "daily_activity_trend"
    HOURLY_ACTIVITY_PATTERN = "hourly_activity_pattern"


class ResponseStatuses:
    SUCCESS = "success"
    ERROR = "error"
    PARTIAL_SUCCESS = "partial_success"


class FieldNames:
    STATUS = 'status'
    USERNAME = 'username'
    TENANT = 'tenant'
    USER_ID = 'user_id'
    EMAIL = 'email'
    FIRST_NAME = 'first_name'
    LAST_NAME = 'last_name'
    ROLE = 'role'
    JOB_ROLE = 'job_role'
    TENANT_ID = 'tenant_id'
    TENANT_SCHEMA = 'tenant_schema'
    BRANCH = 'branch'
    HAS_ACCEPTED_TERMS = 'has_accepted_terms'
    IS_LOCKED = 'is_locked'
    IS_ACTIVE = 'is_active'
    PROFILE = 'profile'
    PROFESSIONAL_QUALIFICATIONS = 'professional_qualifications'
    EMPLOYMENT_DETAILS = 'employment_details'
    EDUCATION_DETAILS = 'education_details'
    REFERENCE_CHECKS = 'reference_checks'
    PROOF_OF_ADDRESS = 'proof_of_address'
    INSURANCE_VERIFICATIONS = 'insurance_verifications'
    DRIVING_RISK_ASSESSMENTS = 'driving_risk_assessments'
    LEGAL_WORK_ELIGIBILITIES = 'legal_work_eligibilities'
    OTHER_USER_DOCUMENTS = 'other_user_documents'
    SKILL_DETAILS = 'skill_details'
    ACTION = 'action'
    PERFORMED_BY = 'performed_by'
    DETAILS = 'details'
    IP_ADDRESS = 'ip_address'
    USER_AGENT = 'user_agent'
    SUCCESS = 'success'
    TIMESTAMP = 'timestamp'
    LOGIN_TIME = 'login_time'
    LOGOUT_TIME = 'logout_time'
    DATE = 'date'
    TITLE = 'title'
    VERSION = 'version'
    USER_ID_FIELD = 'user_id'
    DOCUMENT = 'document'
    ACKNOWLEDGED_AT = 'acknowledged_at'
    TENANT_ID_FIELD = 'tenant_id'
    GROUP = 'group'
    USER = 'user'


class StatusValues:
    SUSPENDED = "suspended"
    ACTIVE = "active"
    LOCKED = "locked"
    ROOT_ADMIN = "root-admin"
    ADMIN = "admin"
    TEAM_MANAGER = "team_manager"
    RECRUITER = "recruiter"
    USER = "user"
    CLIENT = "client"
    CO_ADMIN = "co-admin"


class ActionNames:
    PASSWORD_RESET_REQUEST = "password_reset_request"
    PASSWORD_RESET_CONFIRM = "password_reset_confirm"
    ACCOUNT_LOCK = "account_lock"
    ACCOUNT_UNLOCK = "account_unlock"
    ACCOUNT_SUSPEND = "account_suspend"
    ACCOUNT_ACTIVATE = "account_activate"
    IMPERSONATION = "impersonation"
    IP_BLOCK = "ip_block"
    IP_UNBLOCK = "ip_unblock"
    LOGIN = "login"
    LOGIN_FAILED = "login_failed"


class URLPaths:
    CLOCK_IN = "clock-in"
    CLOCK_OUT = "clock-out"
    DAILY_HISTORY = "daily-history"
    EDIT = "edit"
    LOCK = "lock"
    UNLOCK = "unlock"
    SUSPEND = "suspend"
    ACTIVATE = "activate"
    IMPERSONATE = "impersonate"
    BULK_CREATE = "bulk-create"
    MEMBERS = "members"
    ADD_MEMBER = "add-member"
    REMOVE_MEMBER = "remove-member"
    DASHBOARD_STATS = "dashboard-stats"
    SECURITY_EVENTS = "security-events"
    USER_ACTIVITY_REPORT = "user-activity-report"
    SYSTEM_HEALTH = "system-health"
    EXPORT = "export"
    UNBLOCK = "unblock"


class QueryParams:
    USER_ID = "user_id"
    EMAIL = "email"
    IP_ADDRESS = "ip_address"
    DATE_FROM = "date_from"
    DATE_TO = "date_to"
    SUCCESS = "success"
    ACTION = "action"
    PERFORMED_BY = "performed_by"
    USER = "user"
    IP_ADDRESS_PARAM = "ip_address"
    SEARCH = "search"
    DAYS = "days"
    SECURITY_ACTION = "security_action"
    LIMIT = "limit"
    FORMAT = "format"
    DATE = "date"


class EventTypes:
    USER_ACCOUNT_CREATED = "user.account.created"
    USER_PASSWORD_RESET_REQUESTED = "user.password.reset.requested"
    AUTH_PASSWORD_RESET_CONFIRMED = "auth.password_reset.confirmed"


class DefaultValues:
    MANUAL_LOCK = "Manual lock"
    MANUAL_SUSPENSION = "Manual suspension"
    MANUAL_ACTIVATION = "Manual activation"
    UNKNOWN = "Unknown"
    UNKNOWN_COMPANY = "Unknown Company"
    SOURCE_AUTH_SERVICE = "auth-service"
    N_A = "N/A"
    PUBLIC_SYSTEM = "public-system"
    PUBLIC_SYSTEM_EMAIL = "public@system.com"
    PUBLIC_SYSTEM_FIRST_NAME = "Public"
    PUBLIC_SYSTEM_LAST_NAME = "Registration"
    USER_ROLE = "user"
    TEMP_EMAIL_SUFFIX = "@temp.com"
    TEMP_EMAIL_SUFFIX_WITH_SCHEMA = "@{}.temp.com"
    TEMP_EMAIL_DOMAIN = ".temp.com"
    DEFAULT_ROLE = "user"
    ACCOUNT_CREATED_SUCCESSFULLY = "Account created successfully!"
    REDACTED = "[REDACTED]"
    EVT_PREFIX = "evt-"
    UUID_LENGTH = 8
    PASSWORD_LENGTH = 12
    ASCII_LETTERS_DIGITS_PUNCTUATION = string.ascii_letters + string.digits + string.punctuation
    CACHE_TIMEOUT_5_MIN = 60 * 5
    CACHE_TIMEOUT_30_DAYS = 60 * 60 * 24 * 30
    CACHE_KEY_PREFIX = "public_all_tenants_users"
    CACHE_KEY_PREFIX_PAGINATED = "public_all_tenants_users_paginated"
    CACHE_KEY_PREFIX_USERS = "users_"
    CACHE_KEY_PREFIX_USER = "customuser"
    CACHE_KEY_PREFIX_USERS_LIST = "users_list"
    NOTIFICATIONS_SERVICE_URL = settings.NOTIFICATIONS_SERVICE_URL
    NOTIFICATIONS_EVENT_URL = settings.NOTIFICATIONS_EVENT_URL
    WEB_PAGE_URL = settings.WEB_PAGE_URL
    KAFKA_TOPIC_TENANT_EVENTS = settings.KAFKA_TOPIC_TENANT_EVENTS
    CACHE_ENABLED = settings.CACHE_ENABLED
    GATEWAY_URL = getattr(settings, 'GATEWAY_URL', None)
    REMOTE_ADDR = "REMOTE_ADDR"
    HTTP_USER_AGENT = "HTTP_USER_AGENT"
    AUTHORIZATION = "Authorization"
    BEARER = "Bearer "
    SUB = "sub"
    ROLE = "role"
    TENANT_ID_JWT = "tenant_id"
    TENANT_SCHEMA_JWT = "tenant_schema"
    HAS_ACCEPTED_TERMS_JWT = "has_accepted_terms"
    USER_JWT = "user"
    EMAIL_JWT = "email"
    TYPE = "type"
    ACCESS = "access"
    REFRESH = "refresh"
    EXP = "exp"
    JTI = "jti"
    IMPERSONATED_BY = "impersonated_by"
    EXCLUDED_SCHEMAS = {get_public_schema_name(), 'auth-service'}
    DEFAULT_TENANT = Tenant.objects.first()
    PUBLIC_TENANT = Tenant.objects.get(schema_name=get_public_schema_name())
    HOURS_1 = timedelta(hours=1)
    MINUTES_15 = timedelta(minutes=15)
    MINUTES_30 = timedelta(minutes=30)
    HOURS_24 = timedelta(hours=24)
    DAYS_7 = 7
    DAYS_30 = 30
    DAYS_60 = 60
    PAGE_SIZE = 20
    TIMEOUT_5 = 5
    TIMEOUT_300 = 300
    TIMEOUT_600 = 600
    LIMIT_10000 = 10000
    LIMIT_1000 = 1000
    PERCENT_100 = 100
    PERCENT_10 = 10
    PERCENT_25 = 25
    PERCENT_30 = 30
    PERCENT_50 = 50
    PERCENT_20 = 20
    PERCENT_NEG_20 = -20
    COUNT_10 = 10
    COUNT_5 = 5
    COUNT_1 = 1
    COUNT_0 = 0
    INDEX_0 = 0
    INDEX_1 = 1
    INDEX_100 = 100
    INDEX_999 = 999
    INDEX_3 = 3
    INDEX_4 = 4
    INDEX_500 = 500
    INDEX_8 = 8
    INDEX_12 = 12
    INDEX_201 = 201
    INDEX_204 = 204
    INDEX_400 = 400
    INDEX_401 = 401
    INDEX_403 = 403
    INDEX_404 = 404
    INDEX_500_ERROR = 500
    INDEX_405 = 405
    INDEX_201_CREATED = status.HTTP_201_CREATED
    INDEX_200_OK = status.HTTP_200_OK
    INDEX_204_NO_CONTENT = status.HTTP_204_NO_CONTENT
    INDEX_400_BAD_REQUEST = status.HTTP_400_BAD_REQUEST
    INDEX_401_UNAUTHORIZED = status.HTTP_401_UNAUTHORIZED
    INDEX_403_FORBIDDEN = status.HTTP_403_FORBIDDEN
    INDEX_404_NOT_FOUND = status.HTTP_404_NOT_FOUND
    INDEX_500_INTERNAL_SERVER_ERROR = status.HTTP_500_INTERNAL_SERVER_ERROR
    INDEX_405_METHOD_NOT_ALLOWED = status.HTTP_405_METHOD_NOT_ALLOWED


class SerializerFields:
    ID = 'id'
    EMAIL = 'email'
    FIRST_NAME = 'first_name'
    LAST_NAME = 'last_name'
    ROLE = 'role'
    JOB_ROLE = 'job_role'
    TENANT_ID = 'tenant_id'
    TENANT_SCHEMA = 'tenant_schema'
    BRANCH = 'branch'
    USERNAME = 'username'
    PASSWORD = 'password'
    IS_ACTIVE = 'is_active'
    IS_LOCKED = 'is_locked'
    STATUS = 'status'
    HAS_ACCEPTED_TERMS = 'has_accepted_terms'
    PROFILE = 'profile'
    PROFESSIONAL_QUALIFICATIONS = 'professional_qualifications'
    EMPLOYMENT_DETAILS = 'employment_details'
    EDUCATION_DETAILS = 'education_details'
    REFERENCE_CHECKS = 'reference_checks'
    PROOF_OF_ADDRESS = 'proof_of_address'
    INSURANCE_VERIFICATIONS = 'insurance_verifications'
    DRIVING_RISK_ASSESSMENTS = 'driving_risk_assessments'
    LEGAL_WORK_ELIGIBILITIES = 'legal_work_eligibilities'
    OTHER_USER_DOCUMENTS = 'other_user_documents'
    SKILL_DETAILS = 'skill_details'
    ACTION = 'action'
    PERFORMED_BY = 'performed_by'
    DETAILS = 'details'
    IP_ADDRESS = 'ip_address'
    USER_AGENT = 'user_agent'
    SUCCESS = 'success'
    TIMESTAMP = 'timestamp'
    LOGIN_TIME = 'login_time'
    LOGOUT_TIME = 'logout_time'
    DATE = 'date'
    TITLE = 'title'
    VERSION = 'version'
    USER_ID_FIELD = 'user_id'
    DOCUMENT = 'document'
    ACKNOWLEDGED_AT = 'acknowledged_at'
    TENANT_ID_FIELD = 'tenant_id'
    GROUP = 'group'
    USER = 'user'
    FILES = 'files'
    DATA = 'data'
    REQUEST = 'request'
    USER_OBJ = 'user'
    TARGET_USER = 'user'
    CONTEXT = 'context'


class ModelNames:
    USER_SESSION = "UserSession"
    DOCUMENT = "Document"
    USER_PROFILE = "UserProfile"
    CUSTOM_USER = "CustomUser"
    GROUP_MEMBERSHIP = "GroupMembership"


class PermissionMessages:
    ONLY_ADMINS_CAN_EXPORT_ACTIVITY_LOGS = "Only admins can export activity logs."
    ONLY_ADMINS_OR_TEAM_MANAGERS_CAN_VIEW_ACTIVITY_LOGS = "Only admins or team managers can view activity logs."
    ONLY_ADMINS_OR_SUPERUSERS_CAN_MANAGE_BLOCKED_IPS = "Only admins or superusers can manage blocked IPs."
    ONLY_ADMINS_OR_SUPERUSERS_CAN_VIEW_LOGIN_ATTEMPTS = "Only admins or superusers can view login attempts."


class CacheKeys:
    PUBLIC_ALL_TENANTS_USERS = "public_all_tenants_users"
    PUBLIC_ALL_TENANTS_USERS_PAGINATED = "public_all_tenants_users_paginated"
    USERS_LIST = "users_list"


class FilePaths:
    ACTIVITIES_CSV = "activities_{}.csv"


class ContentTypes:
    TEXT_CSV = 'text/csv'
    APPLICATION_JSON = 'application/json'


class HTTPMethods:
    POST = "POST"
    GET = "GET"
    PATCH = "PATCH"
    PUT = "PUT"
    DELETE = "DELETE"


class Algorithms:
    HS256 = "HS256"
    RS256 = "RS256"


class JWTKeys:
    SECRET_KEY = settings.SECRET_KEY


class Headers:
    AUTHORIZATION = "Authorization"
    BEARER = "Bearer "


class StatusValues:
    SUSPENDED = "suspended"
    ACTIVE = "active"
    LOCKED = "locked"
    ROOT_ADMIN = "root-admin"
    ADMIN = "admin"
    TEAM_MANAGER = "team_manager"
    RECRUITER = "recruiter"
    USER = "user"
    CLIENT = "client"
    CO_ADMIN = "co-admin"


class OrderingFields:
    EMAIL = "email"
    TIMESTAMP = "-timestamp"
    BLOCKED_AT = "-blocked_at"
    ACKNOWLEDGED_AT = "-acknowledged_at"


class LookupFields:
    ID = 'id'
    UNIQUE_ID = 'unique_id'
    EMAIL = 'email'
    USERNAME = 'username'
    TENANT_ID = 'tenant_id'
    SCHEMA_NAME = 'schema_name'
    DOMAIN = 'domain'
    IS_PRIMARY = 'is_primary'
    USER_ID = 'user_id'
    TOKEN = 'token'
    ACTION = 'action'
    SUCCESS = 'success'
    DATE = 'date'
    LOGOUT_TIME = 'logout_time'
    TITLE = 'title'
    DOCUMENT = 'document'
    GROUP = 'group'


class ContextKeys:
    REQUEST = 'request'
    USER = 'user'
    TARGET_USER = 'target_user'
    USER_OBJ = 'user'


class DetailsKeys:
    REASON = 'reason'
    TOKEN = 'token'
    ACCESS_JTI = 'access_jti'
    REFRESH_JTI = 'refresh_jti'
    IP_ADDRESS = 'ip_address'


class URLParams:
    USER_ID = 'user_id'
    EMAIL = 'email'
    IP_ADDRESS = 'ip_address'
    DATE_FROM = 'date_from'
    DATE_TO = 'date_to'
    SUCCESS = 'success'
    ACTION = 'action'
    PERFORMED_BY = 'performed_by'
    USER = 'user'
    SEARCH = 'search'
    DAYS = 'days'
    SECURITY_ACTION = 'security_action'
    LIMIT = 'limit'
    FORMAT = 'format'
    DATE = 'date'


class MetaAttributes:
    REMOTE_ADDR = "REMOTE_ADDR"
    HTTP_USER_AGENT = "HTTP_USER_AGENT"
    HTTP_AUTHORIZATION = "HTTP_AUTHORIZATION"


class JWKSKeys:
    KTY = "kty"
    USE = "use"
    KID = "kid"
    ALG = "alg"
    N = "n"
    E = "e"
    RSA = "RSA"
    SIG = "sig"
    RS256 = "RS256"


class ExportFormats:
    JSON = 'json'
    CSV = 'csv'


class DateFormats:
    YYYY_MM_DD = "%Y-%m-%d"
    ISO_8601 = "ISO 8601"


class SecurityActions:
    LOGIN = 'login'
    LOGIN_FAILED = 'login_failed'
    ACCOUNT_LOCK = 'account_lock'
    ACCOUNT_UNLOCK = 'account_unlock'
    IP_BLOCK = 'ip_block'
    IP_UNBLOCK = 'ip_unblock'
    PASSWORD_RESET_REQUEST = 'password_reset_request'
    PASSWORD_RESET_CONFIRM = 'password_reset_confirm'
    IMPERSONATION = 'impersonation'


class ActivityActions:
    PASSWORD_RESET_REQUEST = "password_reset_request"
    PASSWORD_RESET_CONFIRM = "password_reset_confirm"
    ACCOUNT_LOCK = "account_lock"
    ACCOUNT_UNLOCK = "account_unlock"
    ACCOUNT_SUSPEND = "account_suspend"
    ACCOUNT_ACTIVATE = "account_activate"
    IMPERSONATION = "impersonation"
    IP_BLOCK = "ip_block"
    IP_UNBLOCK = "ip_unblock"
    LOGIN = "login"
    LOGIN_FAILED = "login_failed"


class SystemHealthMetrics:
    RECENT_ERROR_RATE = 'recent_error_rate'
    LOGIN_FAILURE_RATE = 'login_failure_rate'
    CURRENT_HOUR_ACTIVITIES = 'current_hour_activities'
    PREVIOUS_HOUR_ACTIVITIES = 'previous_hour_activities'
    ACTIVITY_TREND = 'activity_trend'
    FAILED_LOGINS_LAST_HOUR = 'failed_logins_last_hour'
    ERROR_RATE_WARNING = 10
    ERROR_RATE_CRITICAL = 25
    LOGIN_FAILURE_WARNING = 30
    LOGIN_FAILURE_CRITICAL = 50


class TrendValues:
    STABLE = "stable"
    INCREASING = "increasing"
    DECREASING = "decreasing"


class SystemStatus:
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ProfileFields:
    PROFESSIONAL_QUALIFICATIONS = 'professional_qualifications'
    EMPLOYMENT_DETAILS = 'employment_details'
    EDUCATION_DETAILS = 'education_details'
    REFERENCE_CHECKS = 'reference_checks'
    PROOF_OF_ADDRESS = 'proof_of_address'
    INSURANCE_VERIFICATIONS = 'insurance_verifications'
    DRIVING_RISK_ASSESSMENTS = 'driving_risk_assessments'
    LEGAL_WORK_ELIGIBILITIES = 'legal_work_eligibilities'
    OTHER_USER_DOCUMENTS = 'other_user_documents'
    SKILL_DETAILS = 'skill_details'
    WORK_PHONE = 'work_phone'
    PERSONAL_PHONE = 'personal_phone'
    NEXT_OF_KIN = 'next_of_kin'
    NEXT_OF_KIN_PHONE_NUMBER = 'next_of_kin_phone_number'
    RELATIONSHIP_TO_NEXT_OF_KIN = 'relationship_to_next_of_kin'
    DOB = 'dob'
    GENDER = 'gender'
    RELATIONSHIP_TO_NEXT_OF_KIN_DEFAULT = 'N/A'
    GENDER = 'gender'


class PrefetchFields:
    PROFILE = "profile"
    TENANT = "tenant"
    BRANCH = "branch"
    PROFILE__PROFESSIONAL_QUALIFICATIONS = "profile__professional_qualifications"
    PROFILE__EMPLOYMENT_DETAILS = "profile__employment_details"
    PROFILE__EDUCATION_DETAILS = "profile__education_details"
    PROFILE__REFERENCE_CHECKS = "profile__reference_checks"
    PROFILE__PROOF_OF_ADDRESS = "profile__proof_of_address"
    PROFILE__INSURANCE_VERIFICATIONS = "profile__insurance_verifications"
    PROFILE__DRIVING_RISK_ASSESSMENTS = "profile__driving_risk_assessments"
    PROFILE__LEGAL_WORK_ELIGIBILITIES = "profile__legal_work_eligibilities"
    PROFILE__OTHER_USER_DOCUMENTS = "profile__other_user_documents"
    PROFILE__SKILL_DETAILS = "profile__skill_details"
    USER = 'user'
    PERFORMED_BY = 'performed_by'
    DOCUMENT = 'document'
    DOMAINS = 'domains'
    PROFILE__SKILL_DETAILS_SHORT = "profile__skill_details"


class SelectFields:
    ID_EMAIL_FIRST_NAME_LAST_NAME_ROLE = 'id', 'email', 'first_name', 'last_name', 'role'


class ValuesFields:
    USER__ID_USER__EMAIL_USER__FIRST_NAME_USER__LAST_NAME_USER__ROLE = 'user__id', 'user__email', 'user__first_name', 'user__last_name', 'user__role'
    ACTION = 'action'
    DATE = 'date'
    HOUR = 'hour'


class AnnotateFields:
    ACTIVITY_COUNT = 'activity_count'
    LAST_ACTIVITY = 'last_activity'
    COUNT = 'count'
    SUCCESS_COUNT = 'success_count'
    FAILURE_COUNT = 'failure_count'
    SUCCESS_RATE = 'success_rate'


class OrderByFields:
    EMAIL = "email"
    TIMESTAMP_DESC = "-timestamp"
    BLOCKED_AT_DESC = "-blocked_at"
    ACKNOWLEDGED_AT_DESC = "-acknowledged_at"
    COUNT_DESC = '-count'
    DATE = 'date'
    HOUR = 'hour'


class FilterFields:
    TENANT = 'tenant'
    ROLE = 'role'
    BRANCH = 'branch'
    ID = 'id'
    EMAIL = 'email'
    USERNAME = 'username'
    TENANT_ID = 'tenant_id'
    ACTION = 'action'
    SUCCESS = 'success'
    TIMESTAMP__GTE = 'timestamp__gte'
    TIMESTAMP__LTE = 'timestamp__lte'
    USER__EMAIL__ICONTAINS = 'user__email__icontains'
    USER__ID__ICONTAINS = 'user__id__icontains'
    PERFORMED_BY__EMAIL__ICONTAINS = 'performed_by__email__icontains'
    PERFORMED_BY__ID__ICONTAINS = 'performed_by__id__icontains'
    IP_ADDRESS = 'ip_address'
    TIMESTAMP__GTE_DATE_FROM = 'timestamp__gte'
    TIMESTAMP__LTE_DATE_TO = 'timestamp__lte'
    ACTION__IN = 'action__in'
    USER__EMAIL__ICONTAINS_SEARCH = 'user__email__icontains'
    PERFORMED_BY__EMAIL__ICONTAINS_SEARCH = 'performed_by__email__icontains'
    IP_ADDRESS__ICONTAINS = 'ip_address__icontains'
    DETAILS__ICONTAINS = 'details__icontains'
    USER__ID = 'user__id'
    USER__EMAIL = 'user__email'
    USER__FIRST_NAME = 'user__first_name'
    USER__LAST_NAME = 'user__last_name'
    USER__ROLE = 'user__role'
    TIMESTAMP__GTE_START_DATE = 'timestamp__gte'
    TIMESTAMP__LTE_END_DATE = 'timestamp__lte'
    ACTION__IN_SECURITY_ACTIONS = 'action__in'
    TIMESTAMP__GTE_TWENTY_FOUR_HOURS_AGO = 'timestamp__gte'
    TIMESTAMP__GTE_ONE_HOUR_AGO = 'timestamp__gte'
    SUCCESS_FALSE = 'success'
    ACTION_LOGIN_FAILED = 'action'
    ACTION_LOGIN = 'action'
    TIMESTAMP__GTE_CURRENT_HOUR = 'timestamp__gte'
    TIMESTAMP__GTE_PREVIOUS_HOUR = 'timestamp__gte'
    TIMESTAMP__LT_CURRENT_HOUR = 'timestamp__lt'
    USER__NULL_FALSE = 'user__isnull'
    TIMESTAMP__GTE_THIRTY_DAYS_AGO = 'timestamp__gte'
    USER__NULL = 'user__isnull'
    PERFORMED_BY = 'performed_by'
    LOGOUT_TIME__NULL = 'logout_time__isnull'
    LOGOUT_TIME__NULL_TRUE = 'logout_time__isnull'
    DATE = 'date'
    USER_ID = 'user_id'
    TOKEN = 'token'
    EXPIRES_AT__LT = 'expires_at__lt'
    USED = 'used'
    LAST_PASSWORD_RESET = 'last_password_reset'
    IS_ACTIVE = 'is_active'
    STATUS = 'status'
    IS_LOCKED = 'is_locked'
    IP_ADDRESS_ACTIVE_TRUE = 'ip_address'
    TENANT_ACTIVE_TRUE = 'tenant'
    IS_ACTIVE_TRUE = 'is_active'
    UNIQUE_ID = 'unique_id'
    SCHEMA_NAME = 'schema_name'
    DOMAIN = 'domain'
    IS_PRIMARY = 'is_primary'
    TITLE = 'title'
    VERSION = 'version'
    DOCUMENT_ID = 'document_id'
    ACKNOWLEDGED_AT = 'acknowledged_at'
    GROUP_ID = 'group_id'
    USER_ID_FIELD = 'user_id'


class ExcludeFields:
    SCHEMA_NAME__IN = 'schema_name__in'


class UpdateFields:
    STATUS = ['status']
    HAS_ACCEPTED_TERMS = ['has_accepted_terms']
    PASSWORD_LAST_PASSWORD_RESET = ['password', 'last_password_reset']
    USED = ['used']
    LOGIN_TIME_LOGOUT_TIME = ['login_time', 'logout_time']
    IS_ACTIVE = ['is_active']


class CreateFields:
    USER_LOGIN_TIME_DATE_IP_ADDRESS_USER_AGENT = ['user', 'login_time', 'date', 'ip_address', 'user_agent']


class EventPayloadKeys:
    METADATA = "metadata"
    EVENT_ID = "event_id"
    EVENT_TYPE = "event_type"
    EVENT_VERSION = "event_version"
    CREATED_AT = "created_at"
    SOURCE = "source"
    TENANT_ID = "tenant_id"
    DATA = "data"
    USER_EMAIL = "user_email"
    USER_NAME = "user_name"
    RESET_LINK = "reset_link"
    EXPIRES_AT = "expires_at"
    USER_ID = "user_id"
    TIMESTAMP = "timestamp"
    USER_AGENT = "user_agent"
    COMPANY_NAME = "company_name"
    TEMP_PASSWORD = "temp_password"
    LOGIN_LINK = "login_link"


class NotificationURLs:
    EVENTS = "/events/"


class RandomChoices:
    ASCII_LETTERS_DIGITS = string.ascii_letters + string.digits


class StringFormats:
    EVT_FORMAT = "evt-{}"
    TEMP_EMAIL_FORMAT = "{}.{}@{}.temp.com"
    TEMP_EMAIL_FORMAT_COUNTER = "{}_{}@{}.temp.com"
    LOGIN_LINK_FORMAT = "https://learn.prolianceltd.com/home/login"
    NOTIFICATIONS_URL_FORMAT = "{}" + "/events/"
    CACHE_KEY_FORMAT = "{}_{}"
    CACHE_KEY_USER_FORMAT = "{}_{}_{}"


class LambdaDefaults:
    DEFAULT_DICT = lambda: {
        "users": [], "unique_id": None, "name": None,
        "primary_domain": None, "all_domains": [], "status": None,
        "root_admin": None, "created_at": None,
    }


class SortedKeys:
    EMAIL = lambda u: u.email


class GroupedKeys:
    SCHEMA_NAME = 'schema_name'
    UNIQUE_ID = 'unique_id'
    NAME = 'name'
    PRIMARY_DOMAIN = 'primary_domain'
    ALL_DOMAINS = 'all_domains'
    STATUS = 'status'
    ROOT_ADMIN = 'root_admin'
    COUNT = 'count'
    CREATED_AT = 'created_at'
    USERS = 'users'


class ResponseDataKeys:
    TENANTS = 'tenants'
    TOTAL_COUNT = 'total_count'
    TOTAL_TENANTS = 'total_tenants'
    STATUS = 'status'
    MESSAGE = 'message'
    DATA = 'data'
    USER_ID = 'user_id'
    EMAIL = 'email'
    NEW_PASSWORD = 'new_password'
    USERNAME = 'username'
    JOB_ROLE = 'job_role'
    TENANT_ID = 'tenant_id'
    TENANT_SCHEMA = 'tenant_schema'
    BRANCH = 'branch'
    REFRESH = 'refresh'
    ACCESS = 'access'
    SESSION_ID = 'session_id'
    DURATION = 'duration'
    SESSIONS = 'sessions'
    TOTAL_TIME = 'total_time'
    CREATED = 'created'
    ERRORS = 'errors'
    UNIQUE_ID = 'unique_id'
    SCHEMA_NAME = 'schema_name'
    TEMP_PASSWORD = 'temp_password'
    LOGIN_LINK = 'login_link'
    TIMESTAMP = 'timestamp'
    USER_AGENT = 'user_agent'
    USER_ID_STR = 'user_id'
    COMPANY_NAME = 'company_name'
    KID = 'kid'
    PUBLIC_KEY = 'public_key'
    TENANT_DOMAIN = 'tenant_domain'
    EXPORT_INFO = 'export_info'
    EXPORTED_AT = 'exported_at'
    TOTAL_RECORDS = 'total_records'
    FORMAT = 'format'
    PERIOD = 'period'
    ACTIVITIES = 'activities'
    USER_INFO = 'user_info'
    FIRST_NAME = 'first_name'
    LAST_NAME = 'last_name'
    ROLE = 'role'
    SUMMARY = 'summary'
    TOTAL_ACTIVITIES_AS_SUBJECT = 'total_activities_as_subject'
    TOTAL_ACTIVITIES_AS_PERFORMER = 'total_activities_as_performer'
    AVERAGE_DAILY_ACTIVITIES = 'average_daily_activities'
    ACTIVITY_BREAKDOWN = 'activity_breakdown'
    DAILY_ACTIVITY_PATTERN = 'daily_activity_pattern'
    TOP_ACTIONS = 'top_actions'
    RECENT_ACTIVITIES = 'recent_activities'
    METRICS = 'metrics'
    THRESHOLDS = 'thresholds'
    SUMMARY_METRICS = 'summary_metrics'
    ACTIVITIES_BY_TYPE = 'activities_by_type'
    TOP_ACTIVE_USERS = 'top_active_users'
    DAILY_ACTIVITY_TREND = 'daily_activity_trend'
    HOURLY_ACTIVITY_PATTERN = 'hourly_activity_pattern'
    NAME = 'name'
    PRIMARY_DOMAIN = 'primary_domain'
    ALL_DOMAINS = 'all_domains'
    ROOT_ADMIN = 'root_admin'
    COUNT = 'count'
    CREATED_AT = 'created_at'
    USERS = 'users'


class SerializerContextKeys:
    REQUEST = 'request'
    USER = 'user'
    TARGET_USER = 'target_user'
    USER_OBJ = 'user'


class SerializerDataKeys:
    FILES = 'FILES'
    DATA = 'data'
    REQUEST = 'request'
    META = 'META'
    HEADERS = 'headers'


class RequestMetaKeys:
    REMOTE_ADDR = "REMOTE_ADDR"
    HTTP_USER_AGENT = "HTTP_USER_AGENT"
    HTTP_AUTHORIZATION = "HTTP_AUTHORIZATION"


class RequestDataKeys:
    USER_ID = 'user_id'
    EMAIL = 'email'
    PASSWORD = 'password'
    FIRST_NAME = 'first_name'
    LAST_NAME = 'last_name'
    USERNAME = 'username'
    PHONE_NUMBER = 'phoneNumber'
    NEXT_OF_KIN_NAME = 'nextOfKinName'
    NEXT_OF_KIN_PHONE = 'nextOfKinPhone'
    DOB = 'dob'
    SEX = 'sex'
    FIRST_NAME_DATA = 'firstName'
    SURNAME = 'surname'
    TENANT_ID = 'tenant_id'
    TENANT_SCHEMA = 'tenant_schema'
    REASON = 'reason'
    TOKEN = 'token'
    NEW_PASSWORD = 'new_password'
    LOGIN_TIME = 'login_time'
    LOGOUT_TIME = 'logout_time'
    DATE = 'date'
    DOCUMENT_ID = 'document_id'
    USER_IDENTIFIER = 'user_id'
    SECURITY_ACTION = 'security_action'
    SUCCESS_FILTER = 'success'
    USER_ID_PARAM = 'user_id'
    FORMAT_PARAM = 'format'
    LIMIT_PARAM = 'limit'


class RequestQueryParams:
    USER_ID = 'user_id'
    EMAIL = 'email'
    IP_ADDRESS = 'ip_address'
    DATE_FROM = 'date_from'
    DATE_TO = 'date_to'
    SUCCESS = 'success'
    ACTION = 'action'
    PERFORMED_BY = 'performed_by'
    USER = 'user'
    SEARCH = 'search'
    DAYS = 'days'
    SECURITY_ACTION = 'security_action'
    LIMIT = 'limit'
    FORMAT = 'format'
    DATE = 'date'


class RequestFiles:
    FILES = 'FILES'


class RequestHeaders:
    AUTHORIZATION = 'Authorization'


class PublicUserDefaults:
    ID = 'public-system'
    EMAIL = 'public@system.com'
    FIRST_NAME = 'Public'
    LAST_NAME = 'Registration'
    ROLE = 'user'


