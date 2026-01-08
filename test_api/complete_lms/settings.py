# lms-service/complete_lms/settings.py
import django.http.request
from django.db.backends.signals import connection_created
import os
from datetime import timedelta
from pathlib import Path
import environ
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy as _

# Base Dir & Env
BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env()
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

DATABASE_ROUTERS = []

INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'corsheaders',
    'django.contrib.auth',
    'django.contrib.staticfiles',
    'rest_framework',
    'drf_spectacular',
    'drf_yasg',
    'django_filters',
    'courses',
    'activitylog',
    'schedule',
    'payments',
    'forum',
    'groups',
    'messaging',
    'advert',
    'ai_chat',
    'carts',
    'auditlog',
    'django_extensions',
]

# drf-spectacular
SPECTACULAR_SETTINGS = {
    'TITLE': 'LMS API',
    'DESCRIPTION': 'API documentation for LMS microservice',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'SWAGGER_UI_SETTINGS': {
        'persistAuthorization': True,
    },
    'COMPONENT_SPLIT_REQUEST': True,
    'SECURITY': [{"BearerAuth": []}],
    'SECURITY_SCHEMES': {
        'BearerAuth': {
            'type': 'http',
            'scheme': 'bearer',
            'bearerFormat': 'JWT',
        },
    },
}

# Patch split_domain_port
def patched_split_domain_port(host):
    if host and host.count(':') == 1 and host.rfind(']') < host.find(':'):
        host, port = host.split(':', 1)
    else:
        port = ''
    return host, port

django.http.request.split_domain_port = patched_split_domain_port

SECRET_KEY = env('DJANGO_SECRET_KEY')
DEBUG = env.bool('DEBUG', default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[
    "localhost", "127.0.0.1", "lms-app", "0.0.0.0", "*", "lms-app:8004", "http://localhost:9090"
])

# Database
DATABASES = {
    'default': {
        'ENGINE': env('DB_ENGINE', default='django_tenants.postgresql_backend'),
        'NAME': env('DB_NAME', default='multi_tenant_lms'),
        'USER': env('DB_USER', default='postgres'),
        'PASSWORD': env('DB_PASSWORD'),
        'HOST': env('DB_HOST', default='lms-db'),
        'PORT': env('DB_PORT', default='5432'),
        'CONN_MAX_AGE': 60,
    }
}

if not DATABASES['default']['ENGINE']:
    raise ImproperlyConfigured("DATABASES['default']['ENGINE'] must be set.")

MIDDLEWARE = [
    'complete_lms.middleware.DatabaseConnectionMiddleware',
    'complete_lms.middleware.MicroserviceRS256JWTMiddleware',
    'complete_lms.middleware.CustomTenantSchemaMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

AUTHENTICATION_BACKENDS = ('django.contrib.auth.backends.ModelBackend',)

ROOT_URLCONF = 'complete_lms.urls'
WSGI_APPLICATION = 'complete_lms.wsgi.application'

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (),
    'DEFAULT_PERMISSION_CLASSES': ('rest_framework.permissions.AllowAny',),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.MultiPartParser',
    ],
}

# SIMPLE_JWT = {
#     "ACCESS_TOKEN_LIFETIME": timedelta(minutes=120),
#     "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
#     "AUTH_HEADER_TYPES": ("Bearer",),
#     "BLACKLIST_AFTER_ROTATION": True,
# }

# External Services
AUTH_SERVICE_URL = env('AUTH_SERVICE_URL', default='http://auth-service:8001')
JOB_APPLICATIONS_URL = env('JOB_APPLICATIONS_URL', default='http://job-applications:8003')
NOTIFICATIONS_SERVICE_URL = env('NOTIFICATIONS_SERVICE_URL', default='http://app:3001')

SUPABASE_URL = env('SUPABASE_URL')
SUPABASE_KEY = env('SUPABASE_KEY')
SUPABASE_BUCKET = env('SUPABASE_BUCKET')

STORAGE_TYPE = env('STORAGE_TYPE', default='supabase')

KAFKA_BOOTSTRAP_SERVERS = env('KAFKA_BOOTSTRAP_SERVERS', default='kafka:9092')
KAFKA_TOPICS = {
    'requisition': 'requisition-events',
    'video_session': 'video-session-events',
    'participant': 'participant-events',
    'request': 'request-events',
    'tenant': 'tenant-created',  # Match auth-service
    'branch': 'branch-events',
}

# CORS
CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=['http://localhost:3000'])
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = ['DELETE', 'GET', 'OPTIONS', 'PATCH', 'POST', 'PUT']
CORS_ALLOW_HEADERS = ['accept', 'authorization', 'content-type', 'origin', 'x-csrftoken', 'x-requested-with', 'x-tenant-id']

# Static & Media
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Templates
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
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

# Logging
LOG_DIR = os.path.join(BASE_DIR, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{asctime} [{levelname}] {name} {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
        'simple': {
            'format': '[{levelname}] {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOG_DIR, 'complete_lms.log'),
            'maxBytes': 5 * 1024 * 1024,
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'complete_lms': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
        'courses': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
        'forum': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
        'activitylog': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
        'lms_consumer': {
            'handlers': ['file', 'console'],
            'level': 'DEBUG',  # Increased to DEBUG for detailed consumer logs
            'propagate': False,
        },
    },
}

# Defaults
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Handle schema for connections
def set_schema_to_public(sender, connection, **kwargs):
    if connection.schema_name is None:
        connection.set_schema(PUBLIC_SCHEMA_NAME)
connection_created.connect(set_schema_to_public)