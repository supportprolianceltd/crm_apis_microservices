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
    "localhost", "127.0.0.1", "talent-engine", "0.0.0.0", "*", "talent-engine:8001"
])
# ======================== Database ========================

DATABASES = {
    'default': {
        'ENGINE': env('DB_ENGINE', default='django.db.backends.postgresql'),
        'NAME': env('DB_NAME', default=''),
        'USER': env('DB_USER', default=''),
        'PASSWORD': env('DB_PASSWORD', default=''),
        'HOST': env('DB_HOST', default='localhost'),
        'PORT': env('DB_PORT', default='5432'),
        'CONN_MAX_AGE': 60,
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
    'jobRequisitions',
    'django_extensions',
]

# ======================== Middleware ========================
MIDDLEWARE = [
    'talent_engine.middleware.MicroserviceJWTMiddleware',
    'corsheaders.middleware.CorsMiddleware',  # must be first for CORS
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

AUTHENTICATION_BACKENDS = ('django.contrib.auth.backends.ModelBackend',)

ROOT_URLCONF = 'talent_engine.urls'
WSGI_APPLICATION = 'talent_engine.wsgi.application'

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
}

# ======================== Simple JWT ========================
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=120),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': False,
    'BLACKLIST_AFTER_ROTATION': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': env('DJANGO_SECRET_KEY'),
    'VERIFYING_KEY': env('DJANGO_SECRET_KEY'),
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
}


# ======================== External Services ========================
AUTH_SERVICE_URL = env('AUTH_SERVICE_URL', default='http://auth_service:8000')
JOB_APPLICATIONS_URL = env('JOB_APPLICATIONS_URL', default='http://job_applications:8000')

SUPABASE_URL = env('SUPABASE_URL', default='')
SUPABASE_KEY = env('SUPABASE_KEY', default='')
SUPABASE_BUCKET = env('SUPABASE_BUCKET', default='')

STORAGE_TYPE = env('STORAGE_TYPE', default='local')  # or 's3', 'azure', 'local', 'supabase'


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
            'filename': os.path.join(LOG_DIR, 'talent_engine.log'),
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
        'talent_engine': {
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




