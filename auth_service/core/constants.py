class ErrorMessages:
    ANOTHER_BRANCH_HEAD_OFFICE = "Another branch ('{}') is already set as head office for this tenant."
    BRANCH_ALREADY_EXISTS = "Branch '{}' already exists for this tenant."
    BRANCH_NAME_INVALID = "Branch name can only contain letters, numbers, spaces, or hyphens."
    DOMAIN_EXISTS = "Domain '{}' already exists."
    DOMAIN_INVALID = "Invalid domain name."
    ERROR_ACCESSING_REQUEST_USER_TENANT = "Error accessing request.user.tenant: {}"
    ERROR_ACTIVATING_TENANT = "Error activating tenant {}: {}"
    ERROR_CREATING_BRANCH = "Error creating branch: {}"
    ERROR_CREATING_MODULE = "Error creating module for tenant {}: {}"
    ERROR_CREATING_TENANT_CONFIG = "Error creating TenantConfig for tenant {}: {}"
    ERROR_CREATING_TENANT_CONFIG_GENERAL = "Error creating tenant config for tenant {}: {}"
    ERROR_DELETING_BRANCH = "Error deleting branch for tenant {}: {}"
    ERROR_EXTRACTING_TENANT = "Error extracting tenant: {}"
    ERROR_FETCHING_USER = "Error fetching {} {}: {}"
    ERROR_LISTING_BRANCHES = "Error listing branches for tenant {}: {}"
    ERROR_LISTING_TENANTS = "Error listing tenants: {}"
    ERROR_SUSPENDING_TENANT = "Error suspending tenant {}: {}"
    ERROR_UPDATING_BRANCH = "Error updating branch for tenant {}: {}"
    FAILED_TO_CREATE_TENANT = "Failed to create tenant: {}"
    FAILED_TO_CREATE_TENANT_CONFIG = "Failed to create tenant configuration"
    FAILED_TO_DECODE_JWT_USER_DATA = "Failed to decode JWT for user data: {}"
    INVALID_JWT_TOKEN_FOR_USER_DATA = "Invalid JWT token for user data."
    INVALID_STATUS = "Invalid status. Must be 'active' or 'suspended'."
    INVALID_TOKEN = "Invalid token"
    INVALID_TOKEN_FORMAT = "Invalid token format"
    KAFKA_PUBLISH_FAILED = "Kafka publish failed: {}"
    KAFKA_PUBLISH_FAILED_ASYNC = "Kafka publish failed (async): {}"
    LOGO_FILE_INVALID = "Only image files are allowed for logo."
    LOGO_FILE_SIZE_EXCEEDS = "Logo file size exceeds 5 MB limit."
    MIN_WITHDRAWAL_MONTHS_INVALID = "Minimum withdrawal months must be at least 1."
    NEXT_POLICY_NUMBER_INVALID = "Next policy number must be positive."
    NO_ACTIVE_KEYPAIR = "No active RSA keypair found for tenant {}"
    NO_VALID_BEARER_TOKEN = "No valid Bearer token provided"
    NOT_AUTHORIZED_DELETE_TENANT = "Not authorized to delete this tenant"
    NOT_AUTHORIZED_UPDATE_TENANT = "Not authorized to update this tenant"
    ONLY_SUPERUSERS_VIEW_GLOBAL_LOGS = "Only platform superusers can view global activity logs."
    POLICY_PREFIX_INVALID = "Policy prefix can only contain letters and numbers."
    PRIMARY_COLOR_INVALID = "Primary color must be a valid hex code (e.g. #1A2B3C)."
    ROI_PERCENT_INVALID = "ROI percentage must be between 0 and 100."
    SCHEMA_NAME_EXISTS = "Schema name already exists."
    SCHEMA_NAME_INVALID = "Schema name can only contain lowercase letters, numbers, or underscores."
    SECONDARY_COLOR_INVALID = "Secondary color must be a valid hex code (e.g. #AABBCC)."
    TENANT_ALREADY_ACTIVE = "Tenant is already active."
    TENANT_ALREADY_SUSPENDED = "Tenant is already suspended."
    TENANT_CONFIG_ALREADY_EXISTS = "Tenant config already exists"
    TENANT_CONFIG_NOT_FOUND = "Tenant config not found"
    TENANT_CREATION_FAILED = "Tenant creation failed: {}"
    TENANT_ID_PARAMETER_REQUIRED = "tenant_id parameter is required"
    TENANT_NOT_FOUND = "Tenant not found"
    TENANT_NOT_FOUND_BY_UNIQUE_ID = "Tenant not found with this unique ID."
    TENANT_NOT_FOUND_GENERAL = "Tenant not found"
    TENANT_NOT_FOUND_IN_REQUEST_CONTEXT = "Tenant not found in request context"
    TENANT_NOT_FOUND_PUBLIC = "Tenant not found."
    TENANT_NOT_SPECIFIED_IN_TOKEN = "Tenant not specified in token"
    USER_NOT_FOUND_LOCAL_DB = "User {} not found in local database"
    VALIDATION_ERROR = "Validation error for tenant {}: {}"


class LogMessages:
    BRANCH_CREATED = "Branch created: {} for tenant {}"
    BRANCH_DELETED = "Branch deleted: {} for tenant {}"
    BRANCH_UPDATED = "Branch updated: {} for tenant {}"
    BRANCHES_RETRIEVED = "Retrieved {} branches for tenant {}"
    CREATED_MODULES_FOR_TENANT = "Created modules for tenant {}"
    CREATING_TENANT = "Creating tenant: {} | Schema: {} | Domain: {}"
    DATABASE_SEARCH_PATH = "Database search_path: {}"
    FILTERING_QUERYSET_FOR_TENANT = "Filtering queryset for tenant: {}"
    LISTING_ALL_TENANTS = "Listing all tenants: {}"
    LISTING_PAGINATED_TENANTS = "Listing paginated tenants: {}"
    MODULE_CREATED = "Module created: {} for tenant {}"
    MODULES_RETRIEVED = "Retrieved {} modules for tenant {}"
    NO_TENANT_IN_TOKEN = "No tenant_id or schema_name in token"
    RETRIEVING_TENANT = "Retrieving tenant: {} for tenant {}"
    RETURNING_ALL_TENANTS = "Returning all tenants for list action"
    SENT_TENANT_CREATED_EVENT = "Sent tenant_created event for tenant {}"
    TENANT_ACTIVATED = "Tenant activated: {} (ID: {}) by {}"
    TENANT_CONFIG_ALREADY_EXISTS_LOG = "Tenant config already exists for tenant {}"
    TENANT_CONFIG_CREATED_DEFAULT = "Created TenantConfig for tenant {} with default email templates"
    TENANT_CONFIG_CREATED_LOG = "Tenant config created for tenant {}"
    TENANT_CONFIG_FETCHED = "Fetched TenantConfig for tenant {}"
    TENANT_CONFIG_NOT_FOUND_LOG = "Tenant config not found for tenant {}"
    TENANT_CONFIG_UPDATED = "Tenant config updated for tenant {}"
    TENANT_CREATED = "Tenant created: {} (schema: {})"
    TENANT_DELETED = "Tenant deleted: {} for tenant {}"
    TENANT_EXTRACTED_BY_ID = "Tenant extracted from token by ID: {}"
    TENANT_EXTRACTED_BY_SCHEMA = "Tenant extracted from token by schema: {}"
    TENANT_EXTRACTED_FROM_TOKEN = "Tenant extracted from token: {}"
    TENANT_FROM_USER = "Tenant from user: {}"
    TENANT_SUSPENDED = "Tenant suspended: {} (ID: {}) by {}"
    TENANT_UPDATED = "Tenant updated: {} for tenant {}"
    UNAUTHORIZED_DELETE_ATTEMPT = "Unauthorized delete attempt on tenant {} by tenant {}"
    UPLOADED_LOGO_FOR_TENANT = "Uploaded logo for tenant {}"


class EventTypes:
    TENANT_ACTIVATED = "tenant_activated"
    TENANT_CREATED = "tenant_created"
    TENANT_DELETED = "tenant_deleted"
    TENANT_SUSPENDED = "tenant_suspended"
    TENANT_UPDATED = "tenant_updated"


class ResponseKeys:
    ACTIVITIES_BY_TENANT = 'activities_by_tenant'
    ACTIVITIES_BY_TYPE = 'activities_by_type'
    ACTIVE_ADMINS = 'active_admins'
    DETAIL = 'detail'
    ERROR = 'error'
    PERIOD = 'period'
    STATUS = 'status'
    SUMMARY = 'summary'


class ResponseStatuses:
    ERROR = "error"


class ResponseMessages:
    TENANT_ACTIVATED_SUCCESS = 'Tenant "{}" activated successfully.'
    TENANT_ALREADY_ACTIVE_DETAIL = "Tenant is already active."
    TENANT_ALREADY_SUSPENDED_DETAIL = "Tenant is already suspended."
    TENANT_NOT_FOUND_DETAIL = "Tenant not found."
    TENANT_SUSPENDED_SUCCESS = 'Tenant "{}" suspended successfully.'


class EmailTemplates:
    INTERVIEW_ACCEPTANCE = (
        'Hello [Candidate Name],\n\n'
        'Congratulations! We are moving you to the next stage. We\'ll follow up with next steps.\n\n'
        'Looking forward,\n[Your Name]'
    )
    INTERVIEW_REJECTION = (
        'Hello [Candidate Name],\n\n'
        'Thank you for taking the time to interview. After careful consideration, '
        'we have decided not to move forward.\n\n'
        'Best wishes,\n[Your Name]'
    )
    INTERVIEW_RESCHEDULING = (
        'Hello [Candidate Name],\n\n'
        'Due to unforeseen circumstances, we need to reschedule your interview originally set for [Old Date/Time]. '
        'Kindly share a few alternative slots that work for you.\n\n'
        'Thanks for your understanding,\n[Your Name]'
    )
    INTERVIEW_SCHEDULING = (
        'Hello [Candidate Name],\n\n'
        'We\'re pleased to invite you to an interview for the [Position] role at [Company].\n'
        'Please let us know your availability so we can confirm a convenient time.\n\n'
        'Best regards,\n[Your Name]'
    )
    JOB_ACCEPTANCE = (
        'Hello [Candidate Name],\n\n'
        'We\'re excited to offer you the [Position] role at [Company]! '
        'Please find the offer letter attached.\n\n'
        'Welcome aboard!\n[Your Name]'
    )
    JOB_REJECTION = (
        'Hello [Candidate Name],\n\n'
        'Thank you for applying. Unfortunately, we\'ve chosen another candidate at this time.\n\n'
        'Kind regards,\n[Your Name]'
    )


class DefaultTemplateKeys:
    INTERVIEW_ACCEPTANCE = 'interviewAcceptance'
    INTERVIEW_REJECTION = 'interviewRejection'
    INTERVIEW_RESCHEDULING = 'interviewRescheduling'
    INTERVIEW_SCHEDULING = 'interviewScheduling'
    JOB_ACCEPTANCE = 'jobAcceptance'
    JOB_REJECTION = 'jobRejection'


class JWTKeys:
    EMAIL = 'email'
    FIRST_NAME = 'first_name'
    ID = 'id'
    JOB_ROLE = 'job_role'
    LAST_NAME = 'last_name'
    TENANT_ID = 'tenant_id'
    TENANT_SCHEMA = 'tenant_schema'
    TENANT_UNIQUE_ID = 'tenant_unique_id'
    USER = 'user'


class Headers:
    AUTHORIZATION = 'Authorization'
    BEARER_PREFIX = 'Bearer '


class Algorithms:
    HS256 = 'HS256'
    RS256 = 'RS256'


class QueryParams:
    ACTION = 'action'
    ACTION_ALT = 'action[]'
    DATE_FROM = 'date_from'
    DATE_TO = 'date_to'
    DAYS = 'days'
    PAGE = 'page'
    PAGE_ALT = 'page[]'
    SEARCH = 'search'
    TENANT_ID = 'tenant_id'


class RequestDataKeys:
    EMAIL_TEMPLATES = 'email_templates'
    REASON = 'reason'


class KafkaEventKeys:
    DATA = 'data'
    EVENT_TYPE = 'event_type'
    TENANT_ID = 'tenant_id'


class NotificationKeys:
    EXTERNAL_ID = 'externalId'
    ID = 'id'
    NAME = 'name'


class StatusValues:
    ACTIVE = 'active'
    SUSPENDED = 'suspended'


class SchemaNames:
    PUBLIC = 'public'


class KafkaTopics:
    TENANT_EVENTS = 'tenant-events'


class JWTDecodeOptions:
    VERIFY_SIGNATURE = 'verify_signature'


class DefaultReasons:
    MANUAL_ACTIVATION = 'Manual activation'
    MANUAL_SUSPENSION = 'Manual suspension'


class OrderingFields:
    TIMESTAMP_DESC = '-timestamp'


class FieldNames:
    ACTION = 'action'
    ACTIVE_ADMINS_COUNT = 'active_admins_count'
    AFFECTED_TENANT = 'affected_tenant'
    AFFECTED_TENANTS_COUNT = 'affected_tenants_count'
    AFFECTED_TENANT_NAME = 'affected_tenant__name'
    AFFECTED_TENANT_SCHEMA_NAME = 'affected_tenant__schema_name'
    AFFECTED_TENANT_UNIQUE_ID = 'affected_tenant__unique_id'
    DAYS = 'days'
    END_DATE = 'end_date'
    START_DATE = 'start_date'
    STATUS = 'status'
    TENANT = 'tenant'
    TOTAL_ACTIVITIES = 'total_activities'
    USER_ID = 'user_id'
    USERNAME = 'username'


class SQLQueries:
    SHOW_SEARCH_PATH = "SHOW search_path;"


class AttributeNames:
    TENANT = 'tenant'


class ActionNames:
    LIST = 'list'


class URLParams:
    PK = 'pk'


class LookupFields:
    ID = 'id'


class ContextKeys:
    REQUEST = 'request'


class DetailsKeys:
    ORGANIZATIONAL_ID = 'organizational_id'
    REASON = 'reason'
    SCHEMA_NAME = 'schema_name'
    TENANT_NAME = 'tenant_name'


class URLPaths:
    ACTIVATE = 'activate'


class SerializerFields:
    # BranchSerializer
    BRANCH_FIELDS = ['id', 'name', 'location', 'is_head_office', 'created_at']
    BRANCH_READ_ONLY = ['id', 'created_at']

    # ModuleSerializer
    MODULE_FIELDS = ['id', 'name', 'is_active']
    MODULE_READ_ONLY = ['id']

    # TenantConfigSerializer
    TENANT_CONFIG_FIELDS = ['logo', 'custom_fields', 'email_templates']

    # TenantSerializer
    TENANT_FIELDS = [
        'id', 'unique_id', 'organizational_id', 'name', 'title', 'schema_name', 'created_at',
        'status', 'logo', 'logo_file', 'email_host', 'email_port', 'email_use_ssl',
        'email_host_user', 'email_host_password', 'default_from_email', 'about_us',
        'domain', 'domains', 'primary_color', 'secondary_color', 'account_name',
        'bank_name', 'account_number', 'roi_percent', 'roi_frequency',
        'min_withdrawal_months', 'unique_policy_prefix', 'next_policy_number',
        'kyc_method', 'kyc_custom'
    ]
    TENANT_READ_ONLY = ['id', 'unique_id', 'organizational_id', 'created_at', 'schema_name', 'logo']

    # PublicTenantSerializer
    PUBLIC_TENANT_FIELDS = ['name', 'title', 'logo', 'status']

    # GlobalActivitySerializer
    GLOBAL_ACTIVITY_FIELDS = [
        'id', 'global_user', 'affected_tenant', 'action', 'performed_by',
        'timestamp', 'details', 'ip_address', 'user_agent', 'success', 'global_correlation_id'
    ]


class FilePaths:
    TENANT_LOGOS_BASE = 'tenant_logos'


class DefaultModules:
    MODULES = [
        'Talent Engine', 'Compliance', 'Training', 'Care Coordination',
        'Workforce', 'Analytics', 'Integrations', 'Assets Management', 'Payroll'
    ]