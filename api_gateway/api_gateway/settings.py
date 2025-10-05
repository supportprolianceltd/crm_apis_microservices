
import os
import requests
from pathlib import Path
import environ
import re
from django.http import HttpRequest
from django.core.handlers.wsgi import WSGIRequest

# ======================== MONKEY PATCH FOR HOSTNAMES ========================
# Allow underscores in hostnames (e.g., lms_app)
original_get_host = HttpRequest.get_host

def get_host(self):
    host = original_get_host(self)
    if '_' in host:
        return host
    return host

HttpRequest.get_host = get_host
WSGIRequest.get_host = get_host

def patched_split_domain_port(host):
    # Accept underscores in hostnames
    if host and host.count(':') == 1 and host.rfind(']') < host.find(':'):
        host, port = host.split(':', 1)
    else:
        port = ''
    return host, port

import django.http.request
django.http.request.split_domain_port = patched_split_domain_port
# ======================== END MONKEY PATCH ========================

# ======================== BASE DIRECTORY & ENVIRONMENT ========================
BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env()
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

# ======================== SECURITY ========================
SECRET_KEY = env('DJANGO_SECRET_KEY', default='django-insecure-fallback-key-for-dev-only')
DEBUG = env.bool('DEBUG', default=False)
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost', '127.0.0.1', 'gateway', '0.0.0.0', '*'])

# ======================== APPLICATION DEFINITION ========================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_extensions',
    'gateway',
    'corsheaders',
    'django_ratelimit',
]

# ======================== MIDDLEWARE ========================
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# ======================== URL CONFIGURATION ========================
ROOT_URLCONF = 'api_gateway.urls'

# ======================== TEMPLATES ========================
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

# ======================== WSGI ========================
WSGI_APPLICATION = 'api_gateway.wsgi.application'

# ======================== DATABASE ========================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# ======================== PASSWORD VALIDATION ========================
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# ======================== INTERNATIONALIZATION ========================
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ======================== STATIC FILES ========================
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'


# api_gateway/settings.py
# Increase timeout for resume screening

# Gateway-specific settings
GATEWAY_TIMEOUTS = {
    'default': 300,
    'screen-resumes': 900,
    'upload': 600,
    'health': 30,
    'auth': 60,
    'notifications': 30
}

# Add retry configuration
GATEWAY_RETRIES = {
    'max_retries': 3,
    'backoff_factor': 1,
    'status_forcelist': [500, 502, 503, 504],
}

# Update session configuration with better connection pooling
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(
    pool_connections=50,
    pool_maxsize=50,
    max_retries=3,
    pool_block=True
)
session.mount('http://', adapter)
session.mount('https://', adapter)


# ======================== DEFAULT AUTO FIELD ========================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ======================== FILE UPLOAD LIMITS ========================
FILE_UPLOAD_MAX_MEMORY_SIZE = 2621440  # 2.5 MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 2621440  # 2.5 MB

# ======================== LOGGING ========================
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
            'class': 'logging.FileHandler',
            'filename': 'gateway.log',
            'formatter': 'verbose',
        },
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'gateway': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'django': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

# ======================== CORS CONFIGURATION ========================
CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=[
    "http://localhost:5173",
    "https://crm-frontend-react.vercel.app", 
    "http://localhost:8000",
])


# Add specific headers needed for file uploads
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
    'x-file-size',
    'x-file-name',
]

# Add more permissive CORS settings for development
CORS_ALLOW_ALL_ORIGINS = env.bool('CORS_ALLOW_ALL_ORIGINS', default=False)
CORS_ALLOW_CREDENTIALS = True


# ======================== MICROSERVICE URLS ========================
AUTH_SERVICE_URL = env.str("AUTH_SERVICE_URL", default="http://auth-service:8001")
APPLICATIONS_ENGINE_URL = env.str("JOB_APPLICATIONS_URL", default="http://job-applications:8003")
TALENT_ENGINE_URL = env.str("TALENT_ENGINE_URL", default="http://talent-engine:8002")
MESSAGING_URL = env.str("MESSAGING_URL", default="http://messaging:3000")
LMS_APP_URL = env.str("LMS_APP_URL", default="http://lms-app:8004")
NOTIFICATIONS_SERVICE_URL = env.str("NOTIFICATIONS_SERVICE_URL", default="http://app:3001")

# ======================== ROUTE CONFIGURATION ========================
AUTH_ROUTES = [
    "token", "token/refresh", "token/validate", "login", "logout",
    "verify-2fa", "docs", "doc", "user", "tenant", "public-key", "jitsi"
]

# Microservice routing dictionary
MICROSERVICE_URLS = {
    "auth_service": AUTH_SERVICE_URL,
    "applications-engine": APPLICATIONS_ENGINE_URL,
    "talent-engine": TALENT_ENGINE_URL,
    "messaging": MESSAGING_URL,
    "lms": LMS_APP_URL,
    "notifications": NOTIFICATIONS_SERVICE_URL,
}

# Register all auth routes under auth service
MICROSERVICE_URLS.update({route: AUTH_SERVICE_URL for route in AUTH_ROUTES})

# ======================== PUBLIC PATHS (NO AUTH REQUIRED) ========================


PUBLIC_PATHS = [
    "applications-engine/applications/parse-resume/autofill/",
    "talent-engine/requisitions/by-link/",
    "talent-engine/requisitions/unique_link/",
    "talent-engine/requisitions/public/published/",
    "talent-engine/requisitions/public/close/",
    "talent-engine/requisitions/upcoming/public/jobs",
    "talent-engine/requisitions/public/update-applications/",
    "applications-engine/apply-jobs/",
    "applications-engine/applications/code/",
    "applications-engine/applications/applicant/upload/",
    "talent-engine/requisitions/public/close/batch/",
    "health/",
    "health",
    "metrics/",
    "circuit-breaker/status/",
    "api/user/users/all-tenants/",
]

# ======================== RATE LIMITING ========================
RATELIMIT_ENABLE = True
RATELIMIT_USE_CACHE = 'default'

