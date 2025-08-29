Authentication Service Setup Guide
This guide provides step-by-step instructions to set up, run, and test the Authentication Service (auth-service) for a multi-tenant Django CRM application. The service handles user authentication, JWT issuance, and tenant resolution using django-tenants, with PostgreSQL for schema-based multi-tenancy and Kafka for event-driven architecture. The service exposes endpoints like /api/token/, /api/token/validate/, and /api/docs/ for Swagger UI.
Prerequisites

Docker: Install Docker (docker --version) and Docker Compose (docker-compose --version). Install Docker.
Python: Python 3.11 is used in the Docker image. Local Python is optional for development.
Git: For cloning or managing the repository.
Hardware: At least 4GB RAM and 2 CPU cores for Docker.
Network: Ensure ports 8000 (auth service), 5432 (PostgreSQL), 9092 (Kafka), and 2181 (Zookeeper) are free.

Project Structure
The auth-service directory should have the following structure:
auth-service/
├── auth_service/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── middleware.py
│   ├── wsgi.py
│   ├── asgi.py
├── core/
│   ├── migrations/
│   ├── __init__.py
│   ├── models.py
├── users/
│   ├── migrations/
│   ├── __init__.py
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
├── logs/
├── templates/
├── staticfiles/
├── media/
├── manage.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env

Setup Instructions
1. Clone or Create the Repository
Clone the repository or create the project directory:
git clone <your-repo-url> auth-service
cd auth-service

If starting fresh, create the directory and files as described below.
2. Create Configuration Files
2.1. Dockerfile
Create auth-service/Dockerfile:
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "auth_service.wsgi:application"]

2.2. docker-compose.yml
Create auth-service/docker-compose.yml:
version: '3.8'
services:
  db:
    image: postgres:15
    container_name: auth_postgres
    environment:
      POSTGRES_DB: auth_db
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5
  auth:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: auth_service
    ports:
      - "8000:8000"
    environment:
      - AUTH_DB_URL=postgres://postgres:password@db:5432/auth_db
      - DJANGO_SECRET_KEY=${DJANGO_SECRET_KEY}
      - DEBUG=True
      - KAFKA_BOOTSTRAP_SERVERS=kafka:9092
      - CORS_ALLOWED_ORIGINS=http://localhost:5173,https://crm-frontend-react.vercel.app
    depends_on:
      db:
        condition: service_healthy
    volumes:
      - .:/app
  kafka:
    image: confluentinc/cp-kafka:7.0.1
    container_name: kafka
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
    depends_on:
      - zookeeper
    ports:
      - "9092:9092"
  zookeeper:
    image: confluentinc/cp-zookeeper:7.0.1
    container_name: zookeeper
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
      ZOOKEEPER_TICK_TIME: 2000
    ports:
      - "2181:2181"
volumes:
  postgres_data:

2.3. requirements.txt
Create auth-service/requirements.txt:
django==4.2
django-tenants==3.7
djangorestframework==3.15
djangorestframework-simplejwt==5.3
drf-spectacular==0.27
psycopg2-binary==2.9
python-environ==0.11
kafka-python==2.0
gunicorn==22.0

2.4. .env
Create auth-service/.env:
DJANGO_SECRET_KEY=your-secret-key-here
DEBUG=True
DB_NAME=auth_db
DB_USER=postgres
DB_PASSWORD=password
DB_HOST=db
DB_PORT=5432
KAFKA_BOOTSTRAP_SERVERS=kafka:9092
CORS_ALLOWED_ORIGINS=http://localhost:5173,https://crm-frontend-react.vercel.app,http://localhost:8000


Note: Replace your-secret-key-here with a secure key (e.g., generate using python -c "import secrets; print(secrets.token_hex(32))").

2.5. settings.py
Create auth_service/settings.py:
import os
from pathlib import Path
from datetime import timedelta
import environ
from django.utils.translation import gettext_lazy as _

env = environ.Env(
    DEBUG=(bool, True),
    DJANGO_SECRET_KEY=(str, 'your-default-secret-key'),
)
BASE_DIR = Path(__file__).resolve().parent.parent
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

SECRET_KEY = env('DJANGO_SECRET_KEY')
DEBUG = env('DEBUG')
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost', '127.0.0.1', '*'])

INSTALLED_APPS = [
    'django_tenants',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'drf_spectacular',
    'core',
    'users',
]

MIDDLEWARE = [
    'auth_service.middleware.CustomTenantMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

DATABASES = {
    'default': {
        'ENGINE': 'django_tenants.postgresql_backend',
        'NAME': env('DB_NAME', default='auth_db'),
        'USER': env('DB_USER', default='postgres'),
        'PASSWORD': env('DB_PASSWORD', default='password'),
        'HOST': env('DB_HOST', default='db'),
        'PORT': env('DB_PORT', default='5432'),
        'CONN_MAX_AGE': 60,
    }
}

DATABASE_ROUTERS = ['django_tenants.routers.TenantSyncRouter']
TENANT_MODEL = 'core.Tenant'
TENANT_DOMAIN_MODEL = 'core.Domain'
PUBLIC_SCHEMA_NAME = 'public'

SHARED_APPS = [
    'django_tenants',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'core',
]

TENANT_APPS = [
    'django.contrib.auth',
    'django.contrib.admin',
    'rest_framework',
    'rest_framework_simplejwt',
    'drf_spectacular',
    'users',
]

INSTALLED_APPS = SHARED_APPS + TENANT_APPS

AUTH_USER_MODEL = 'users.CustomUser'
AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
)

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.MultiPartParser',
    ],
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=120),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'AUTH_HEADER_TYPES': ('Bearer',),
    'TOKEN_OBTAIN_SERIALIZER': 'users.serializers.CustomTokenSerializer',
    'BLACKLIST_AFTER_ROTATION': True,
}

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
    },
    'apple': {
        'APP': {
            'client_id': env('APPLE_CLIENT_ID', default=''),
            'secret': env('APPLE_KEY_ID', default=''),
            'key': env('APPLE_TEAM_ID', default=''),
            'certificate_key': env('APPLE_CERTIFICATE_KEY', default=''),
        }
    },
    'microsoft': {
        'APP': {
            'client_id': env('MICROSOFT_CLIENT_ID', default=''),
            'secret': env('MICROSOFT_CLIENT_SECRET', default=''),
            'tenant': 'common',
        },
        'SCOPE': ['User.Read', 'email'],
    }
}

KAFKA_BOOTSTRAP_SERVERS = env.list('KAFKA_BOOTSTRAP_SERVERS', default=['kafka:9092'])
KAFKA_TOPIC_USER_EVENTS = 'user-events'

CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=[
    'http://localhost:5173',
    'https://crm-frontend-react.vercel.app',
    'http://localhost:8000',
])
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = ['DELETE', 'GET', 'OPTIONS', 'PATCH', 'POST', 'PUT']
CORS_ALLOW_HEADERS = [
    'accept',
    'authorization',
    'content-type',
    'origin',
    'x-csrftoken',
    'x-requested-with',
]

ROOT_URLCONF = 'auth_service.urls'
WSGI_APPLICATION = 'auth_service.wsgi.application'
ASGI_APPLICATION = 'auth_service.asgi.application'

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

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

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
            'filename': os.path.join(LOG_DIR, 'auth_service.log'),
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
        'core': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': False,
        },
        'users': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

WEB_PAGE_URL = env('WEB_PAGE_URL', default='https://crm-frontend-react.vercel.app')

2.6. urls.py
Create auth_service/urls.py:
from django.urls import path
from users.views import CustomTokenObtainPairView, TokenValidateView, CustomTokenRefreshView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path('api/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),
    path('api/token/validate/', TokenValidateView.as_view(), name='token_validate'),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]

2.7. Models, Serializers, Views, and Middleware
Ensure the following files exist (based on your provided code):

core/models.py: Contains Tenant and Domain models.
users/models.py: Contains CustomUser and PasswordResetToken models.
users/serializers.py: Contains CustomTokenSerializer, CustomTokenRefreshSerializer.
users/views.py: Contains CustomTokenObtainPairView, CustomTokenRefreshView, TokenValidateView.
auth_service/middleware.py: Contains CustomTenantMiddleware.

If these are missing, copy them from your monolith or request specific implementations.
3. Set Up the Database

Start Docker Containers:cd auth-service
docker-compose up -d --build


Builds the auth_service image and starts PostgreSQL, Kafka, and Zookeeper.


Verify Containers:docker ps


Ensure auth_service, auth_postgres, kafka, and zookeeper are running and auth_postgres is healthy.


Apply Migrations:docker exec -it auth_service bash
python manage.py makemigrations
python manage.py migrate_schemas --shared


#python manage.py shell
from core.models import Tenant, Domain
if not Tenant.objects.filter(schema_name='public').exists():
    tenant = Tenant.objects.create(
        name='public',
        schema_name='public',
    )
    tenant.auto_create_schema = False
    tenant.save()
    Domain.objects.create(tenant=tenant, domain='127.0.0.1', is_primary=True)
    Domain.objects.create(tenant=tenant, domain='localhost', is_primary=False)

from core.models import Tenant, Domain
if not Tenant.objects.filter(schema_name='proliance').exists():
    tenant = Tenant.objects.create(
        name='proliance',
        schema_name='proliance',
    )
    tenant.auto_create_schema = False
    tenant.save()
    Domain.objects.create(tenant=tenant, domain='prolianceltd.com', is_primary=True)
    


Apply Tenant Migrations:python manage.py migrate_schemas


# python manage.py shell
from core.models import Tenant
from users.models import CustomUser
from django_tenants.utils import tenant_context
tenant = Tenant.objects.get(schema_name='proliance')
with tenant_context(tenant):
    CustomUser.objects.create_superuser(
        username='daniel',
        email='info@prolianceltd.com',
        password='qwerty',
        role='admin',
        first_name='Daniel',
        last_name='Quinn',
        job_role='Tester 2',
        tenant=tenant
    )


4. Run the Application

Ensure Containers are Running:If not already running:docker-compose up -d


Check Logs:docker logs auth_service


Look for Gunicorn startup (e.g., [INFO] Starting gunicorn 22.0).


Verify Service:curl http://localhost:8000/api/docs/


Should return HTML for the Swagger UI.



5. Test Endpoints in a Browser

Access Swagger UI:
Open a browser (e.g., Chrome, Firefox) and navigate to:http://localhost:8000/api/docs/


You should see the Swagger UI listing endpoints like /api/token/, /api/token/refresh/, and /api/token/validate/.


Test /api/token/:
In Swagger UI:
Click /api/token/.
Click “Try it out”.
Enter:{
  "email": "test@example.localhost",
  "password": "password"
}


Click “Execute”.
Expect a response like:{
  "refresh": "...",
  "access": "...",
  "tenant_id": "...",
  "tenant_schema": "example",
  "user": {...}
}




Copy the access token for further testing.


Test /api/token/validate/:
In Swagger UI:
Click /api/token/validate/.
Add the Authorization header: Bearer <access_token>.
Click “Execute”.
Expect:{
  "status": "success",
  "user": {...},
  "tenant_id": "...",
  "tenant_schema": "example"
}






Alternative Testing with Postman:
POST to http://localhost:8000/api/token/:{
  "email": "test@example.localhost",
  "password": "password"
}


GET to http://localhost:8000/api/token/validate/ with header Authorization: Bearer <access_token>.



6. Troubleshooting

Service Not Accessible:
Check port 8000: lsof -i :8000. Kill conflicting processes or change the port in docker-compose.yml.
Verify logs: docker logs auth_service.


Database Issues:
Ensure PostgreSQL is healthy: docker inspect auth_postgres --format='{{.State.Health.Status}}'.
Test connection: docker exec -it auth_service psql -h db -U postgres -d auth_db.
Reset DB: docker-compose down -v && docker-compose up -d.


CORS Errors:
Ensure http://localhost:8000 is in CORS_ALLOWED_ORIGINS in .env.
Restart: docker-compose down && docker-compose up -d.


Migration Errors:
Delete migrations: rm -rf core/migrations/* users/migrations/*.
Recreate: python manage.py makemigrations.
Reapply: python manage.py migrate_schemas --shared && python manage.py migrate_schemas.



7. Data Migration from Monolith
To migrate data from your existing monolith:

Export public schema:pg_dump -h localhost -U postgres -n public -t core_tenant -t core_domain lumina_care_db > public_tables.sql


Export tenant schema:pg_dump -h localhost -U postgres -n abraham_ekene_onwon lumina_care_db > tenant_data.sql


Import into auth_db:docker cp public_tables.sql auth_postgres:/public_tables.sql
docker exec -i auth_postgres psql -U postgres -d auth_db -f /public_tables.sql
docker cp tenant_data.sql auth_postgres:/tenant_data.sql
docker exec -i auth_postgres psql -U postgres -d auth_db -c "CREATE SCHEMA example;"
docker exec -i auth_postgres psql -U postgres -d auth_db -n example -f /tenant_data.sql



8. Next Steps

Integrate with Monolith: Proxy /api/token/ to http://localhost:8000 in your monolith’s API Gateway or urls.py.
Secure Production: Use HTTPS, tighten ALLOWED_HOSTS, and secure DB credentials.
Monitor: Add Prometheus/Grafana for metrics.
Extract Notification Service: Subscribe to user-events topic in Kafka.

For issues, check logs (docker logs auth_service) or contact the developer with specific error details.