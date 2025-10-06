# auth_service/settings.py
import os
from datetime import timedelta
from pathlib import Path

import environ
from django.utils.translation import gettext_lazy as _

# Initialize environment variables
env = environ.Env(
    DEBUG=(bool, True),
    DJANGO_SECRET_KEY=(str, "django-insecure-va=ok0r=3)*b@ekd_c^+zkz&d)@*sd3sm$t(1o-n$yj)zwfked"),
)
BASE_DIR = Path(__file__).resolve().parent.parent
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

# Core Settings
SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env.list(
    "ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "auth_service", "http://localhost:9090", "*"]
)
NOTIFICATIONS_SERVICE_URL = env("NOTIFICATIONS_SERVICE_URL", default="http://app:3001")

MIDDLEWARE = [
    "auth_service.middleware.CustomTenantMiddleware",  # Tenant resolution
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# Database Configuration for Multi-Tenancy
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

# Shared and Tenant Apps
SHARED_APPS = [
    "django_tenants",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "rest_framework",
    "drf_spectacular",
    "core",  # Tenant, Domain
]

TENANT_APPS = [
    "django.contrib.auth",
    "django.contrib.admin",  # Moved to TENANT_APPS to avoid CustomUser dependency in public schema
    "rest_framework_simplejwt",
    "users",  # CustomUser, PasswordResetToken, etc.
]

# INSTALLED_APPS = SHARED_APPS + TENANT_APPS
INSTALLED_APPS = SHARED_APPS + TENANT_APPS + ["django_extensions"]


# Authentication
AUTH_USER_MODEL = "users.CustomUser"

# Update AUTHENTICATION_BACKENDS in settings.py
AUTHENTICATION_BACKENDS = (
    'auth_service.authentication.UsernameModelBackend',  # New
    'django.contrib.auth.backends.ModelBackend',  # Existing for email
)

# REST Framework
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ("auth_service.authentication.RS256TenantJWTAuthentication",),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.MultiPartParser",
    ],
}

# Simple JWT
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=120),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "AUTH_HEADER_TYPES": ("Bearer",),
    "TOKEN_OBTAIN_SERIALIZER": "users.serializers.CustomTokenSerializer",
    "BLACKLIST_AFTER_ROTATION": True,
}

# Social Authentication Providers
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
    },
    "apple": {
        "APP": {
            "client_id": env("APPLE_CLIENT_ID", default=""),
            "secret": env("APPLE_KEY_ID", default=""),
            "key": env("APPLE_TEAM_ID", default=""),
            "certificate_key": env("APPLE_CERTIFICATE_KEY", default=""),
        }
    },
    "microsoft": {
        "APP": {
            "client_id": env("MICROSOFT_CLIENT_ID", default=""),
            "secret": env("MICROSOFT_CLIENT_SECRET", default=""),
            "tenant": "common",
        },
        "SCOPE": ["User.Read", "email"],
    },
}

# Kafka Configuration
KAFKA_BOOTSTRAP_SERVERS = env.list("KAFKA_BOOTSTRAP_SERVERS", default=["kafka:9092"])
KAFKA_TOPIC_USER_EVENTS = "user-events"
KAFKA_TOPIC_TENANT_EVENTS = "tenant-created"

# CORS Configuration
CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=[
        "http://localhost:5173",
        "https://crm-frontend-react.vercel.app",
    ],
)
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = ["DELETE", "GET", "OPTIONS", "PATCH", "POST", "PUT"]
CORS_ALLOW_HEADERS = [
    "accept",
    "authorization",
    "content-type",
    "origin",
    "x-csrftoken",
    "x-requested-with",
]

# URL Configuration
ROOT_URLCONF = "auth_service.urls"
WSGI_APPLICATION = "auth_service.wsgi.application"
ASGI_APPLICATION = "auth_service.asgi.application"

# Templates
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

# Static and Media Files
STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

# Logging Configuration
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
            "maxBytes": 5 * 1024 * 1024,  # 5MB
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
        "utils.supabase": {
            "handlers": ["file", "console"],
            "level": "DEBUG",
            "propagate": False,
        },
        "auth_service": {  # Add this logger configuration
            "handlers": ["file", "console"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}
# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Environment-Specific Settings
WEB_PAGE_URL = env("WEB_PAGE_URL", default="https://crm-frontend-react.vercel.app")

AUTH_SERVICE_URL = env("AUTH_SERVICE_URL", default="http://auth-service:8001")
NOTIFICATIONS_EVENT_URL = env("NOTIFICATIONS_EVENT_URL", default="http://app:3000/events/")
GATEWAY_URL = env("GATEWAY_URL", default="https://server1.prolianceltd.com")


SUPABASE_URL = env("SUPABASE_URL", default="")
SUPABASE_KEY = env("SUPABASE_KEY", default="")
SUPABASE_BUCKET = env("SUPABASE_BUCKET", default="")

STORAGE_TYPE = env("STORAGE_TYPE", default="supabase")  # or 's3', 'azure', 'local', 'supabase'

SPECTACULAR_SETTINGS = {
    "TITLE": "LUMINA Care OS API",
    "DESCRIPTION": "API documentation for LUMINA Care OS",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SECURITY": [{"BearerAuth": []}],  # Important: tells Swagger to use JWT Auth
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


# Caching Configuration
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


# Cache-enabled flag for feature toggle
CACHE_ENABLED = env.bool("CACHE_ENABLED", default=True)

# Multi-tenant cache prefix helper (use in code)
TENANT_CACHE_PREFIX = "tenant:{}:"  # e.g., "tenant:example_user:"



# sudo nano /etc/nginx/nginx.conf
# sudo nano /etc/nginx/conf.d/crm_api.conf

# sudo hostnamectl set-hostname server1.prolianceltd.com

# docker exec -it auth-service  python manage.py shell

#  ssh -i "$env:USERPROFILE\.ssh\my_vps_key" -p 2222 root@162.254.32.158
# ssh -i "$env:USERPROFILE\.ssh\my_vps_key" -p 2222 root@162.254.32.158


