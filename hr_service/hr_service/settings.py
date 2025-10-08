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

SECRET_KEY = env('DJANGO_SECRET_KEY')

DEBUG = env.bool('DEBUG', default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[
    "localhost", "127.0.0.1", "hr-service", "0.0.0.0", "*", "hr-service:8004", "http://localhost:9090"
])

GATEWAY_URL = env("GATEWAY_URL", default="https://server1.prolianceltd.com")

# ======================== Database ========================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env('HR_DB_NAME', default='hr_db'),
        'USER': env('DB_USER', default='postgres'),
        'PASSWORD': env('DB_PASSWORD', default='password'),
        'HOST': env('DB_HOST', default='hr_postgres'),
        'PORT': env('DB_PORT', default='5432'),
        'CONN_MAX_AGE': 0,  # Disable persistent connections to avoid leaks during schema switches
        'OPTIONS': {
            'connect_timeout': 30,
            'keepalives': 1,
            'keepalives_idle': 30,
            'keepalives_interval': 10,
            'keepalives_count': 5,
        },
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
    'hr',  # Your main app
    'django_extensions',
]

# ======================== Middleware ========================
MIDDLEWARE = [
    'hr.middleware.DatabaseConnectionMiddleware',  # Add this FIRST
    'hr.middleware.MicroserviceRS256JWTMiddleware',
    'hr.middleware.CustomTenantSchemaMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

AUTHENTICATION_BACKENDS = ('django.contrib.auth.backends.ModelBackend',)

ROOT_URLCONF = 'hr_service.urls'
WSGI_APPLICATION = 'hr_service.wsgi.application'

# ======================== REST Framework ========================
REST_FRAMEWORK = {
    # Use only custom JWT middleware, not DRF JWTAuthentication
    'DEFAULT_AUTHENTICATION_CLASSES': (),
    'DEFAULT_PERMISSION_CLASSES': ('rest_framework.permissions.AllowAny',),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.MultiPartParser',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
}

# ======================== External Services ========================
AUTH_SERVICE_URL = env('AUTH_SERVICE_URL', default='http://auth-service:8001')
TALENT_ENGINE_URL = env('TALENT_ENGINE_URL', default='http://talent-engine:8002')
NOTIFICATIONS_SERVICE_URL = env('NOTIFICATIONS_SERVICE_URL', default='http://app:3001')

SUPABASE_URL = env('SUPABASE_URL', default='')
SUPABASE_KEY = env('SUPABASE_KEY', default='')
SUPABASE_BUCKET = env('SUPABASE_BUCKET', default='')

STORAGE_TYPE = env('STORAGE_TYPE', default='supabase')

KAFKA_BOOTSTRAP_SERVERS = env('KAFKA_BOOTSTRAP_SERVERS', default='kafka:9092')
KAFKA_TOPICS = {
    'hr_events': 'hr-events',
    'user': 'user-events',
    'tenant': 'tenant-events',
}

CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://hr_redis:6379/0")
CELERY_RESULT_BACKEND = CELERY_BROKER_URL

# ======================== CORS ========================
CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=['http://localhost:3000'])
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = ['DELETE', 'GET', 'OPTIONS', 'PATCH', 'POST', 'PUT']
CORS_ALLOW_HEADERS = ['accept', 'authorization', 'content-type', 'origin', 'x-csrftoken', 'x-requested-with']

# ======================== Static & Media ========================
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

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
LOG_DIR = os.path.join(BASE_DIR, 'logs')
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
            'filename': os.path.join(LOG_DIR, 'hr_service.log'),
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
        'hr': {  # HR-specific
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

# drf-spectacular: Add Bearer token security scheme for Swagger UI
SPECTACULAR_SETTINGS = {
    'TITLE': 'HR Service API',
    'DESCRIPTION': 'API documentation for HR microservice',
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

# Patched split_domain_port for host parsing (from talent_engine)
import django.http.request

def patched_split_domain_port(host):
    # Accept underscores in hostnames
    if host and host.count(':') == 1 and host.rfind(']') < host.find(':'):
        host, port = host.split(':', 1)
    else:
        port = ''
    return host, port

django.http.request.split_domain_port = patched_split_domain_port