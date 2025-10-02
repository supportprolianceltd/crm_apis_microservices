import os
from pathlib import Path
import environ
import logging
import stat
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy as _
from celery.schedules import crontab
import django.http.request

# Set up a basic logger before the full configuration is applied
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ======================== Base Dir & Env ========================
BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env()
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

# Patch Django's split_domain_port to accept underscores in hostnames
def patched_split_domain_port(host):
    if host and host.count(':') == 1 and host.rfind(']') < host.find(':'):
        host, port = host.split(':', 1)
    else:
        port = ''
    return host, port

django.http.request.split_domain_port = patched_split_domain_port

# ======================== Security & Hosts ========================
SECRET_KEY = env('DJANGO_SECRET_KEY')
DEBUG = env.bool('DEBUG', default=True)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[
    "localhost", "127.0.0.1", "job-applications", "0.0.0.0", "job-applications:8003", "*"
])

# ======================== Installed Apps ========================
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
# MIDDLEWARE = [
#     'django.middleware.security.SecurityMiddleware',
#     'corsheaders.middleware.CorsMiddleware',
#     'django.contrib.sessions.middleware.SessionMiddleware',
#     'django.middleware.common.CommonMiddleware',
#     'django.middleware.csrf.CsrfViewMiddleware',
#     'django.contrib.auth.middleware.AuthenticationMiddleware',
#     'django.contrib.messages.middleware.MessageMiddleware',
#     'django.middleware.clickjacking.XFrameOptionsMiddleware',
#     'job_applications.middleware.MicroserviceRS256JWTMiddleware',
#     'job_applications.middleware.CustomTenantSchemaMiddleware',
# ]
# Add connection health check middleware
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'job_applications.middleware.DatabaseConnectionMiddleware',  # Add this
    'job_applications.middleware.MicroserviceRS256JWTMiddleware',
    'job_applications.middleware.CustomTenantSchemaMiddleware',
]

# ======================== Authentication ========================
AUTHENTICATION_BACKENDS = ('django.contrib.auth.backends.ModelBackend',)

# ======================== Database ========================
# In your settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django_tenants.postgresql_backend',
        'NAME': env('DB_NAME', default=''),
        'USER': env('DB_USER', default=''),
        'PASSWORD': env('DB_PASSWORD', default=''),
        'HOST': env('DB_HOST', default='localhost'),
        'PORT': env('DB_PORT', default='5432'),
        'CONN_MAX_AGE': 0,  # Set to 0 to disable persistent connections
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

DATABASE_ROUTERS = []

# ======================== REST Framework ========================
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

# ======================== drf-spectacular ========================
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

# ======================== External Services ========================
AUTH_SERVICE_URL = env('AUTH_SERVICE_URL', default='http://auth-service:8001')
TALENT_ENGINE_URL = env('TALENT_ENGINE_URL', default='http://talent-engine:8002')
JOB_APPLICATIONS_URL = env('JOB_APPLICATIONS_URL', default='http://job-applications:8003')
NOTIFICATIONS_SERVICE_URL = env('NOTIFICATIONS_EVENT_URL', default='http://app:3000/events/')
SUPABASE_URL = env('SUPABASE_URL', default='')
SUPABASE_KEY = env('SUPABASE_KEY', default='')
SUPABASE_BUCKET = env('SUPABASE_BUCKET', default='luminacaremedia')
STORAGE_TYPE = env('STORAGE_TYPE', default='supabase')

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
CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=[
    'http://localhost:5173',
    'https://crm-frontend-react.vercel.app',
    'http://localhost:8000'
])
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = ['DELETE', 'GET', 'OPTIONS', 'PATCH', 'POST', 'PUT']
CORS_ALLOW_HEADERS = ['accept', 'authorization', 'content-type', 'origin', 'x-csrftoken', 'x-requested-with']

# ======================== Static & Media ========================
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
ENABLE_FILE_COMPRESSION = True

# ======================== Templates ========================
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

# ======================== Logging ========================
LOG_DIR = env('DJANGO_LOG_DIR', default=os.path.join(BASE_DIR, 'logs'))
try:
    os.makedirs(LOG_DIR, exist_ok=True)
    os.chmod(LOG_DIR, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
    logger.info(f"Log directory created or verified: {LOG_DIR}")
except Exception as e:
    logger.error(f"Failed to create log directory {LOG_DIR}: {str(e)}")
    raise

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
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOG_DIR, 'job_applications.log'),
            'maxBytes': 5 * 1024 * 1024,
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        '': {
            'handlers': ['file', 'console'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'django': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'job_applications': {
            'handlers': ['file', 'console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

try:
    import logging.config
    logging.config.dictConfig(LOGGING)
    logger.info("Logging configuration applied successfully")
except Exception as e:
    logger.error(f"Failed to apply logging configuration: {str(e)}")
    raise

# ======================== Celery Configuration ========================
CELERY_BROKER_URL = env('CELERY_BROKER_URL', default='redis://job_app_redis:6379/0')
CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND', default='redis://job_app_redis:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'

# CELERY_BEAT_SCHEDULE = {
#     'auto-screen-all-applications-at-midnight': {
#         'task': 'job_application.tasks.auto_screen_all_applications',
#         'schedule': crontab(hour=10, minute=45),
#     },
# }

# job_applications/settings.py
# Update the CELERY_BEAT_SCHEDULE to add the new task. Replace the existing one.

CELERY_BEAT_SCHEDULE = {
    'daily-background-cv-vetting-at-midnight': {
        'task': 'job_application.tasks.daily_background_cv_vetting',
        'schedule': crontab(hour=0, minute=0),  # Midnight UTC
    },
    # Keep existing if needed, but update the auto-screen one if conflicting
    # 'auto-screen-all-applications-at-midnight': { ... }  # Comment out or remove if replacing
}

# ======================== Defaults ========================
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
ROOT_URLCONF = 'job_applications.urls'
WSGI_APPLICATION = 'job_applications.wsgi.application'