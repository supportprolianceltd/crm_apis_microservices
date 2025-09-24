import re
from pathlib import Path
import environ
from django.http import HttpRequest
from django.core.handlers.wsgi import WSGIRequest

# Monkey patch to allow underscores in hostnames (e.g., lms_app)
original_get_host = HttpRequest.get_host

def get_host(self):
    host = original_get_host(self)
    if '_' in host:
        return host
    return host

HttpRequest.get_host = get_host
WSGIRequest.get_host = get_host

# Environment setup
BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env(ALLOWED_HOSTS=(list, []))
environ.Env.read_env(BASE_DIR / '.env')

# Security
SECRET_KEY = 'django-insecure-$jqc+rt9j)0$1g)&ogr7ssxm27z0qdhp%h#&*nq$z$g)57cbb-'
DEBUG = True
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "talent_engine"])

# Installed apps
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
    'django_ratelimit',  # Used to be 'ratelimit'
]

# Middleware
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

# URL config
ROOT_URLCONF = 'api_gateway.urls'

# Templates
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# WSGI
WSGI_APPLICATION = 'api_gateway.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# File upload limits
FILE_UPLOAD_MAX_MEMORY_SIZE = 2621440  # 2.5 MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 2621440  # 2.5 MB

# Static files
STATIC_URL = 'static/'

# Default auto field
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{asctime} {levelname} {name} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'gateway.log',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'gateway': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

# CORS
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "https://crm-frontend-react.vercel.app",
    "http://localhost:8000",
]

# Microservice URLs from .env
AUTH_SERVICE_URL = env.str("AUTH_SERVICE_URL", default="http://auth-service:8001")
APPLICATIONS_ENGINE_URL = env.str("JOB_APPLICATIONS_URL", default="http://job-applications:8003")
TALENT_ENGINE_URL = env.str("TALENT_ENGINE_URL", default="http://talent-engine:8002")
MESSAGING_URL = env.str("MESSAGING_URL", default="http://messaging:3500")
LMS_APP_URL = env.str("LMS_APP_URL", default="http://lms-app:8004")
NOTIFICATIONS_SERVICE_URL = env.str("NOTIFICATIONS_SERVICE_URL", default="http://app:3001")

# Routes that all map to auth service
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
