# # #  ssh -i "$env:USERPROFILE\.ssh\my_vps_key" -p 2222 root@162.254.32.158
# # # ssh -i "$env:USERPROFILE\.ssh\my_vps_key" -p 2222 root@162.254.32.158

import os
from datetime import timedelta
from pathlib import Path
from celery.schedules import crontab
import environ
import logging
from django.utils.translation import gettext_lazy as _
from urllib.parse import urlparse
from cryptography.fernet import Fernet
import base64


env = environ.Env(
    DEBUG=(bool, True),
    DJANGO_SECRET_KEY=(str, "django-insecure-va=ok0r=3)*b@ekd_c^+zkz&d)@*sd3sm$t(1o-n$yj)zwfked"),
    DEPLOYMENT_ENV=(str, "development"),
)
BASE_DIR = Path(__file__).resolve().parent.parent
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env("DEBUG")
DEPLOYMENT_ENV = env("DEPLOYMENT_ENV")
# Generate a key once (run in shell: from cryptography.fernet import Fernet; print(Fernet.generate_key().decode()))
QR_ENCRYPTION_KEY = env("QR_ENCRYPTION_KEY", default="e9SQU1V0RmKKxz1w6nLKnBX9sFMEy7SXBnsuK900xDM=")  # Replace with real key

# ============================================================================
# ENVIRONMENT-AWARE CONFIGURATION
# ============================================================================

IS_DEVELOPMENT = DEPLOYMENT_ENV == "development"
IS_PRODUCTION = DEPLOYMENT_ENV == "production"
IS_STAGING = DEPLOYMENT_ENV == "staging"

# Frontend URLs
if IS_PRODUCTION:
    FRONTEND_URLS = [
        "https://e3os.co.uk",
        "https://crm-frontend-react.vercel.app",
        "https://loan-management-rho.vercel.app",
        "https://task-manager-two-plum.vercel.app",
        "https://technicalglobaladministrator.e3os.co.uk",
        "https://dev.e3os.co.uk",
        "https://e3os.co.uk"
    ]
    DEFAULT_FRONTEND_URL = "https://e3os.co.uk"
elif IS_STAGING:
    FRONTEND_URLS = [
        "https://e3os.co.uk",
        "https://crm-frontend-react.vercel.app",
       "https://loan-management-rho.vercel.app",
       "https://task-manager-two-plum.vercel.app",
        "https://technicalglobaladministrator.e3os.co.uk",
        "https://dev.e3os.co.uk",
        "https://e3os.co.uk"
    ]
    DEFAULT_FRONTEND_URL = "https://crm-frontend-react.vercel.app"
else:  # development
    FRONTEND_URLS = [
        "https://dev.e3os.co.uk",
        "http://localhost:5173",
        "http://localhost:4000",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://localhost:4000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
         "https://dev.e3os.co.uk",
    ]
    DEFAULT_FRONTEND_URL = "http://localhost:5173"
    REVIEWS_QR_BASE_URL = "http://localhost:5173"

# ============================================================================
# SECURITY & CORS SETTINGS - FIXED
# ============================================================================

ALLOWED_HOSTS = env.list(
    "ALLOWED_HOSTS", 
    default=["localhost", "127.0.0.1", "auth_service", "0.0.0.0", "backend", "127.0.0.1:9090", "localhost:9090"]
)



# CORS Configuration - FIXED: Remove CORS_ALLOW_ALL_ORIGINS to avoid conflicts
CORS_ALLOW_ALL_ORIGINS = False  # Don't use this in production
CORS_ALLOWED_ORIGINS = FRONTEND_URLS

# For development, allow all localhost ports with regex
if IS_DEVELOPMENT:
    CORS_ALLOWED_ORIGIN_REGEXES = [
        r"^http://localhost:\d+$",
        r"^http://127.0.0.1:\d+$",
        r"^http://0.0.0.0:\d+$",
    ]

CORS_ALLOW_CREDENTIALS = True

# CORS headers and methods
CORS_ALLOW_METHODS = [
    "DELETE",
    "GET", 
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
]

CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding", 
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    "x-requested-by",
]

# CSRF Trusted Origins
CSRF_TRUSTED_ORIGINS = FRONTEND_URLS.copy()
if IS_DEVELOPMENT:
    CSRF_TRUSTED_ORIGINS.extend([
        "http://localhost:5173",
        "http://127.0.0.1:5173", 
        "http://localhost:3000",
        "http://localhost:4000",
        "http://127.0.0.1:3000",
        "https://dev.e3os.co.uk",
    ])

# Cookie settings - FIXED for development
# Cookie settings - FIXED for development
if IS_DEVELOPMENT:
    COOKIE_SAMESITE = 'Lax' 
    COOKIE_SECURE = False    
    CSRF_COOKIE_SECURE = False
    SESSION_COOKIE_SECURE = False
    COOKIE_HTTPONLY = True
    COOKIE_DOMAIN = None  
else:
    COOKIE_SAMESITE = 'None'
    COOKIE_SECURE = True

COOKIE_HTTPONLY = True
COOKIE_PATH = '/'

# Session settings
SESSION_COOKIE_SAMESITE = COOKIE_SAMESITE
SESSION_COOKIE_SECURE = COOKIE_SECURE
SESSION_COOKIE_HTTPONLY = True

CSRF_COOKIE_SAMESITE = COOKIE_SAMESITE
CSRF_COOKIE_SECURE = COOKIE_SECURE
CSRF_COOKIE_HTTPONLY = False

# ============================================================================
# APPLICATION CONFIGURATION
# ============================================================================

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",  # Should be at the top
    "auth_service.middleware.CustomTenantMiddleware",
    "auth_service.middleware.EnhancedActivityLoggingMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# Database Configuration
DATABASES = {
    "default": {
        "ENGINE": "django_tenants.postgresql_backend",
        "NAME": env("DB_NAME", default="auth_db"),
        "USER": env("DB_USER", default="postgres"),
        "PASSWORD": env("DB_PASSWORD", default="password"),
        "HOST": env("DB_HOST", default="db"),
        "PORT": env("DB_PORT", default="5432"),
        "CONN_MAX_AGE": 60,
    }
}

DATABASE_ROUTERS = ["django_tenants.routers.TenantSyncRouter"]
TENANT_MODEL = "core.Tenant"
TENANT_DOMAIN_MODEL = "core.Domain"
PUBLIC_SCHEMA_NAME = "public"

SHARED_APPS = [
    "django_tenants",
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "rest_framework",
    "drf_spectacular",
    "corsheaders",
    "core",
]

TENANT_APPS = [
    "django.contrib.admin",
    "rest_framework_simplejwt",
    "users",
    "reviews",
    "investments",
    "events",
]

INSTALLED_APPS = list(SHARED_APPS) + [
    app for app in TENANT_APPS if app not in SHARED_APPS
] + ["django_extensions"]

# ============================================================================
# AUTHENTICATION CONFIGURATION
# ============================================================================

AUTH_USER_MODEL = "users.CustomUser"

AUTHENTICATION_BACKENDS = (
    'auth_service.authentication.GlobalUserBackend',
    'auth_service.authentication.UsernameModelBackend',
    'django.contrib.auth.backends.ModelBackend',
)

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "auth_service.authentication.RS256TenantJWTAuthentication",
        "auth_service.authentication.RS256CookieJWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.MultiPartParser",
    ],
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=120),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "AUTH_HEADER_TYPES": ("Bearer",),
    "TOKEN_OBTAIN_SERIALIZER": "users.serializers.CustomTokenSerializer",
    "BLACKLIST_AFTER_ROTATION": True,
}

# ============================================================================
# EXTERNAL SERVICES
# ============================================================================

NOTIFICATIONS_SERVICE_URL = env("NOTIFICATIONS_SERVICE_URL", default="http://app:3001")
GLOBAL_ADMIN_PASSWORD = env("GLOBAL_ADMIN_PASSWORD", default="SuperAdmin2025!")
GLOBAL_ADMIN_EMAIL = env("GLOBAL_ADMIN_EMAIL", default="admin@platform.local")

# ============================================================================
# URL & TEMPLATE CONFIGURATION
# ============================================================================

ROOT_URLCONF = "auth_service.urls"
WSGI_APPLICATION = "auth_service.wsgi.application"
ASGI_APPLICATION = "auth_service.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ============================================================================
# FILE & MEDIA CONFIGURATION
# ============================================================================

STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{asctime} [{levelname}] {name}: {message}",
            "style": "{",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "simple": {"format": "[{levelname}] {message}", "style": "{", "datefmt": "%Y-%m-%d %H:%M:%S"},
    },
    "handlers": {
        "file": {
            "level": "DEBUG",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(LOG_DIR, "auth_service.log"),
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "verbose",
        },
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["file", "console"],
            "level": "INFO",
            "propagate": True,
        },
        "core": {
            "handlers": ["file", "console"],
            "level": "DEBUG",
            "propagate": False,
        },
        "users": {
            "handlers": ["file", "console"],
            "level": "DEBUG",
            "propagate": False,
        },
        'cache': {
            'handlers': ['file', 'console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        "auth_service": {
            "handlers": ["file", "console"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}

# ============================================================================
# INTERNATIONALIZATION
# ============================================================================

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ============================================================================
# ENVIRONMENT-SPECIFIC SETTINGS
# ============================================================================

WEB_PAGE_URL = env("WEB_PAGE_URL", default=DEFAULT_FRONTEND_URL)
AUTH_SERVICE_URL = env("AUTH_SERVICE_URL", default="http://auth-service:8001")
NOTIFICATIONS_EVENT_URL = env("NOTIFICATIONS_EVENT_URL", default="http://app:3000/events/")
GATEWAY_URL = env("GATEWAY_URL", default="https://server1.prolianceltd.com")

SPECTACULAR_SETTINGS = {
    "TITLE": "LUMINA Care OS API",
    "DESCRIPTION": "API documentation for LUMINA Care OS",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SECURITY": [{"BearerAuth": []}],
    "COMPONENTS": {
        "securitySchemes": {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
            }
        }
    },
}

# ============================================================================
# CACHING CONFIGURATION
# ============================================================================

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": env("REDIS_URL", default="redis://redis:6379/0"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "CONNECTION_POOL_KWARGS": {"max_connections": 20},
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT": 5,
            "COMPRESSOR": "django_redis.compressors.zlib.ZlibCompressor",
            "SOCKET_KEEPALIVE": True,
            "SOCKET_KEEPALIVE_OPTIONS": {
                "tcp_keepalive": True,
                "tcp_keepalive_idle": 60,
                "tcp_keepalive_intvl": 10,
                "tcp_keepalive_probes": 3,
            },
        },
        "KEY_PREFIX": "authservice:v1:",
        "DEFAULT_TIMEOUT": 300,
    }
}

CACHE_ENABLED = env.bool("CACHE_ENABLED", default=True)

# Kafka Configuration
KAFKA_BOOTSTRAP_SERVERS = env.list("KAFKA_BOOTSTRAP_SERVERS", default=["kafka:9092"])
KAFKA_TOPIC_USER_EVENTS = "user-events"
KAFKA_TOPIC_TENANT_EVENTS = "tenant-created"

CACHE_ENABLED = env.bool("CACHE_ENABLED", default=True)
TENANT_CACHE_PREFIX = "tenant:{}:"

# Environment info logging
logger = logging.getLogger(__name__)
logger.info(f"🚀 Starting auth-service in {DEPLOYMENT_ENV} mode")
logger.info(f"🌍 Frontend URLs: {FRONTEND_URLS}")
logger.info(f"🔧 Cookie settings - SameSite: {COOKIE_SAMESITE}, Secure: {COOKIE_SECURE}")
logger.info(f"🔧 CORS Allowed Origins: {CORS_ALLOWED_ORIGINS}")
logger.info(f"🔧 CSRF Trusted Origins: {CSRF_TRUSTED_ORIGINS}")

SUPABASE_URL = env("SUPABASE_URL", default="")
SUPABASE_KEY = env("SUPABASE_KEY", default="")
SUPABASE_BUCKET = env("SUPABASE_BUCKET", default="")
STORAGE_TYPE = env("STORAGE_TYPE", default="supabase")

# Add to settings.py
CELERY_BEAT_SCHEDULE = {
    'accrue-monthly-roi': {
        'task': 'investments.tasks.accrue_monthly_roi',
        'schedule': crontab(0, 0, day_of_month='1'),  # 1st of every month
    },
    'send-roi-notifications': {
        'task': 'investments.tasks.send_roi_due_notifications', 
        'schedule': crontab(0, 0, day_of_month='25'),  # 25th of every month
    },
}

# #  ssh -i "$env:USERPROFILE\.ssh\my_vps_key" -p 2222 root@162.254.32.158
# # ssh -i "$env:USERPROFILE\.ssh\my_vps_key" -p 2222 root@162.254.32.158

# corgi spaceship banana notebook

# PASSWORD: Kd8k{tq|5?mQeB Health Care, Professional Services

# Email: ekeabr815
# Password: M'7Sf$DI}B?C
