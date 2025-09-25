# drf-spectacular: Add Bearer token security scheme for Swagger UI
SPECTACULAR_SETTINGS = {
    'TITLE': 'Talent Engine API',
    'DESCRIPTION': 'API documentation for Talent Engine microservice',
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

import django.http.request
from celery.schedules import crontab
import logging
logger = logging.getLogger(__name__)

def patched_split_domain_port(host):
    # Accept underscores in hostnames
    if host and host.count(':') == 1 and host.rfind(']') < host.find(':'):
        host, port = host.split(':', 1)
    else:
        port = ''
    return host, port

django.http.request.split_domain_port = patched_split_domain_port

import os
from pathlib import Path
import environ
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy as _
from datetime import timedelta
import logging

# ======================== Base Dir & Env ========================
BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env()
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

DATABASE_ROUTERS = []

SECRET_KEY = env('DJANGO_SECRET_KEY')

DEBUG = env.bool('DEBUG', default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[
    "localhost", "127.0.0.1", "job_applications", "0.0.0.0", "http://localhost:9090","*", "job_applications:8001"
])
# ======================== Database ========================

DATABASES = {
    'default': {
        'ENGINE': 'django_tenants.postgresql_backend',
        'NAME': env('DB_NAME', default=''),
        'USER': env('DB_USER', default=''),
        'PASSWORD': env('DB_PASSWORD', default=''),
        'HOST': env('DB_HOST', default='localhost'),
        'PORT': env('DB_PORT', default='5432'),
        'CONN_MAX_AGE': 300,  # Reduce to 5 minutes
        'CONN_HEALTH_CHECKS': True,  # Enable health checks
    }
}



if not DATABASES['default']['ENGINE']:
    raise ImproperlyConfigured("DATABASES['default']['ENGINE'] must be set.")


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
    'job_application',
    'django_extensions',
]

# ======================== Middleware ========================

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'job_applications.middleware.MicroserviceRS256JWTMiddleware',
    'job_applications.middleware.CustomTenantSchemaMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


AUTHENTICATION_BACKENDS = ('django.contrib.auth.backends.ModelBackend',)

ROOT_URLCONF = 'job_applications.urls'
WSGI_APPLICATION = 'job_applications.wsgi.application'

# ======================== REST Framework ========================
# REST_FRAMEWORK = {
#     # Use only custom JWT middleware, not DRF JWTAuthentication
#     'DEFAULT_AUTHENTICATION_CLASSES': (),
#     'DEFAULT_PERMISSION_CLASSES': ('rest_framework.permissions.AllowAny',),
#     'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
#     'DEFAULT_PARSER_CLASSES': [
#         'rest_framework.parsers.JSONParser',
#         'rest_framework.parsers.FormParser',
#         'rest_framework.parsers.MultiPartParser',
#     ],
# }

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (),  # Empty tuple - handled by middleware
    'DEFAULT_PERMISSION_CLASSES': ('rest_framework.permissions.AllowAny',),
        'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.MultiPartParser',
    ],
    # ... other settings
}


# ======================== External Services ========================
AUTH_SERVICE_URL = env('AUTH_SERVICE_URL', default='http://auth-service:8001')
TALENT_ENGINE_URL = env('TALENT_ENGINE_URL', default='http://talent-engine:8002')
JOB_APPLICATIONS_URL = env('JOB_APPLICATIONS_URL', default='http://job-applications:8003')
NOTIFICATIONS_SERVICE_URL = env('NOTIFICATIONS_SERVICE_URL', default='http://app:3001')
SUPABASE_URL = env('SUPABASE_URL', default='')
SUPABASE_KEY = env('SUPABASE_KEY', default='')
SUPABASE_BUCKET = env('SUPABASE_BUCKET', default='')

STORAGE_TYPE = env('STORAGE_TYPE', default='supabase')  # or 's3', 'azure', 'local', 'supabase'

# print("LOADED BUCKET:", SUPABASE_BUCKET)

#logger.info(f"[DEBUG] SUPABASE_BUCKET = {SUPABASE_BUCKET}")
KAFKA_BOOTSTRAP_SERVERS = env('KAFKA_BOOTSTRAP_SERVERS', default='localhost:9092')
KAFKA_TOPICS = {
    'requisition': 'requisition-events',
    'video_session': 'video-session-events',
    'participant': 'participant-events',
    'request': 'request-events',
    'tenant': 'tenant-events',
    'branch': 'branch-events',
    'user': 'user-events',
}

# ======================== CORS ========================
CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=['http://localhost:3000'])
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = ['DELETE', 'GET', 'OPTIONS', 'PATCH', 'POST', 'PUT']
CORS_ALLOW_HEADERS = ['accept', 'authorization', 'content-type', 'origin', 'x-csrftoken', 'x-requested-with']

# ======================== Static & Media ========================
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
# STATICFILES_DIRS = [BASE_DIR / 'static']  # For dev, uncomment if needed

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# ======================== Templates ========================
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

# ======================== Logging ========================
LOG_DIR = os.path.join('/tmp', 'job_applications_logs')
os.makedirs(LOG_DIR, exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{asctime} [{levelname}] {name}: {message}',
            'style': '{'
        },
        'simple': {
            'format': '[{levelname}] {message}',
            'style': '{'
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOG_DIR, 'job_applications.log'),
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
        'django': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'job_applications': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}



# ======================== Defaults ========================
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Celery Configuration
CELERY_BROKER_URL = 'redis://job_app_redis:6379/0'
CELERY_RESULT_BACKEND = 'redis://job_app_redis:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC' #GMT = Lagos/Africa Time - 1
CELERY_ENABLE_UTC = True

# Celery Beat Schedule
CELERY_BEAT_SCHEDULE = {
    'auto-screen-all-applications-at-midnight': {
        'task': 'job_application.tasks.auto_screen_all_applications',
        'schedule': crontab(hour=10, minute=45),  # Runs daily at 23:00 UTC
    },
}