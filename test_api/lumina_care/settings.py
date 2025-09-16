from pathlib import Path
from datetime import timedelta
import os
import sys
import environ
from logging.handlers import RotatingFileHandler
from django.core.exceptions import ImproperlyConfigured
import django.http.request
# Initialize environment variables
env = environ.Env(
    DEBUG=(bool, False),
    DB_PORT=(str, '5432'),
)
environ.Env.read_env(os.path.join(Path(__file__).resolve().parent.parent, '.env'))

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / 'talent_engine'))

# Core security
SECRET_KEY = env('DJANGO_SECRET_KEY')
DEBUG = env.bool('DEBUG', default=False)
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost', '127.0.0.1', 'lms-app', '0.0.0.0', '*'])

# Frontend URL
FRONTEND_URL = env('FRONTEND_URL', default='http://localhost:5173')

# Installed apps
INSTALLED_APPS = [
    # Third-party
    'django_tenants',
    'corsheaders',
    'django_filters',
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'drf_spectacular',
    'viewflow.fsm',
    'auditlog',
    'django_crontab',
    'channels',
    'daphne',
    'django_prometheus',
    # Django core
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    # Allauth
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.apple',
    'allauth.socialaccount.providers.microsoft',
    # Local apps
    'core.apps.CoreConfig',
    'courses',
    'activitylog',
    'users.apps.UsersConfig',
    'subscriptions',
    'schedule',
    'payments',
    'forum',
    'groups',
    'messaging',
    'advert',
    'ai_chat',
    'carts',
]

SITE_ID = 1

# Middleware
MIDDLEWARE = [
    'django_prometheus.middleware.PrometheusBeforeMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'lumina_care.middleware.MicroserviceRS256JWTMiddleware',  # Updated to match job-applications
    'lumina_care.middleware.CustomTenantSchemaMiddleware',   # Updated to match job-applications
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'lumina_care.middleware.AllowIframeForScormMiddleware',
    'django_prometheus.middleware.PrometheusAfterMiddleware',
]

# Authentication
AUTH_USER_MODEL = 'users.CustomUser'
AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
)

ACCOUNT_EMAIL_VERIFICATION = 'optional'
ACCOUNT_LOGIN_METHOD = 'email'
ACCOUNT_SIGNUP_FIELDS = ['email', 'password1', 'password2']
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_PROVIDERS = {
    'google': {'SCOPE': ['profile', 'email']},
    'apple': {'APP': {'client_id': '', 'secret': '', 'key': '', 'certificate_key': ''}},
    'microsoft': {'APP': {'client_id': '', 'secret': '', 'tenant': 'common'}, 'SCOPE': ['User.Read', 'email']},
}

# Database and tenancy
DATABASES = {
    'default': {
        'ENGINE': 'django_tenants.postgresql_backend',
        **env.db('DATABASE_URL', default='postgres://postgres:qwerty@lms-db:5432/multi_tenant_lms'),
    }
}

DATABASE_ROUTERS = ['django_tenants.routers.TenantSyncRouter']
TENANT_MODEL = 'core.Tenant'
TENANT_DOMAIN_MODEL = 'core.Domain'

SHARED_APPS = [
    'django_tenants',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.sites',
    'rest_framework_simplejwt.token_blacklist',
    'core',
    'users.apps.UsersConfig',
    'subscriptions',
    'django_prometheus',
]

TENANT_APPS = [
    'django.contrib.admin',
    'rest_framework',
    'rest_framework_simplejwt',
    'drf_spectacular',
    'viewflow.fsm',
    'auditlog',
    'courses',
    'activitylog',
    'schedule',
    'payments',
    'forum',
    'groups',
    'messaging',
    'advert',
    'compliance',
    'ai_chat',
    'carts',
]

# CORS and CSRF
CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=[
    'https://complete-lms-sable.vercel.app',
    'http://localhost:5173',
])
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = ['DELETE', 'GET', 'OPTIONS', 'PATCH', 'POST', 'PUT']
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
    'x-tenant-schema',
    'x-tenant-id',
]

CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=[
    'https://complete-lms-sable.vercel.app',
    'http://localhost:5173',
])

# Cookie settings
SESSION_COOKIE_SAMESITE = 'None'
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = 'None'
CSRF_COOKIE_SECURE = True

# Simple JWT
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=120),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'AUTH_COOKIE': 'access_token',
    'AUTH_COOKIE_REFRESH': 'refresh_token',
    'AUTH_COOKIE_SECURE': env.bool('DEBUG', default=False),  # False for local dev
    'AUTH_COOKIE_HTTP_ONLY': True,
    'AUTH_COOKIE_SAMESITE': 'None',
    'SIGNING_KEY': SECRET_KEY,
    'TOKEN_OBTAIN_SERIALIZER': 'lumina_care.views.CustomTokenSerializer',
}

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (),  # Handled by MicroserviceRS256JWTMiddleware
    'DEFAULT_PERMISSION_CLASSES': ('rest_framework.permissions.IsAuthenticated',),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.MultiPartParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.JSONParser',
    ],
}

# Channels
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [('redis', 6379)],
        },
    },
}
ASGI_APPLICATION = 'lumina_care.asgi.application'

# Templates
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# Static and media
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Logging
LOG_DIR = os.path.join(BASE_DIR, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {'format': '{asctime} [{levelname}] {name}: {message}', 'style': '{'},
        'simple': {'format': '[{levelname}] {message}', 'style': '{'},
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOG_DIR, 'lumina_care.log'),
            'maxBytes': 5 * 1024 * 1024,
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'django': {'handlers': ['file', 'console'], 'level': 'INFO', 'propagate': True},
        'core': {'handlers': ['file'], 'level': 'INFO', 'propagate': False},
        'users': {'handlers': ['file'], 'level': 'INFO', 'propagate': False},
        'talent_engine': {'handlers': ['file'], 'level': 'INFO', 'propagate': False},
        'subscriptions': {'handlers': ['file'], 'level': 'INFO', 'propagate': False},
        '': {'handlers': ['file', 'console'], 'level': 'INFO'},  # Catch-all logger
    },
}

# Cron jobs
CRONTAB_COMMAND_PREFIX = ''
CRONTAB_DJANGO_PROJECT_NAME = 'lumina_care'
CRONJOBS = [
    ('0 11 * * *', 'talent_engine.cron.close_expired_requisitions', f'>> {os.path.join(LOG_DIR, "lumina_care.log")} 2>&1'),
    ('0 0 * * *', 'courses.management.commands.index_courses', f'>> {os.path.join(LOG_DIR, "lumina_care.log")} 2>&1'),
]

# Email (commented out for now, enable as needed)
# EMAIL_BACKEND = env('EMAIL_BACKEND', default='django.core.mail.backends.smtp.EmailBackend')
# EMAIL_HOST = env('EMAIL_HOST', default='smtp.gmail.com')
# EMAIL_PORT = env('EMAIL_PORT', default=587, cast=int)
# EMAIL_USE_SSL = env('EMAIL_USE_SSL', default=False, cast=bool)
# EMAIL_HOST_USER = env('EMAIL_HOST_USER')
# EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD')
# DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL')

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Storage configuration
STORAGE_TYPE = env('STORAGE_TYPE', default='supabase')
SUPABASE_URL = env('SUPABASE_URL', default='')
SUPABASE_KEY = env('SUPABASE_KEY', default='')
SUPABASE_BUCKET = env('SUPABASE_BUCKET', default='luminaaremedia')

# External services
AUTH_SERVICE_URL = env('AUTH_SERVICE_URL', default='http://auth-service:8001')
KAFKA_BOOTSTRAP_SERVERS = env('KAFKA_BOOTSTRAP_SERVERS', default='kafka:9092')
KAFKA_TOPICS = {
    'tenant': 'tenant-events',
    # Add other topics as needed
}

# OpenAI and other APIs
OPENAI_API_KEY = env('OPENAI_API_KEY', default='')
GROK_API_KEY = env('GROK_API_KEY', default='')
PINECONE_API_KEY = env('PINECONE_API_KEY', default='')

# DRF Spectacular
SPECTACULAR_SETTINGS = {
    'TITLE': 'Lumina Care LMS API',
    'DESCRIPTION': 'API documentation for Lumina Care LMS',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'SWAGGER_UI_SETTINGS': {'persistAuthorization': True},
    'COMPONENT_SPLIT_REQUEST': True,
    'SECURITY': [{'BearerAuth': []}],
    'SECURITY_SCHEMES': {
        'BearerAuth': {
            'type': 'http',
            'scheme': 'bearer',
            'bearerFormat': 'JWT',
        },
    },
}

# Patch for underscores in hostnames

def patched_split_domain_port(host):
    if host and host.count(':') == 1 and host.rfind(']') < host.find(':'):
        host, port = host.split(':', 1)
    else:
        port = ''
    return host, port
django.http.request.split_domain_port = patched_split_domain_port