import os
from celery import Celery
from django.db import connection
from celery.signals import task_postrun, worker_process_init, worker_process_shutdown
import django.http.request
from celery.schedules import crontab
# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'job_applications.settings')

app = Celery('job_applications')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Properly closes the DB connection after each task to prevent "cursor already closed"
@task_postrun.connect
def close_db_connection(**kwargs):
    connection.close()

# Initialize database connection for each worker process
@worker_process_init.connect
def init_worker(**kwargs):
    connection.connect()

# Close database connection when worker shuts down
@worker_process_shutdown.connect
def shutdown_worker(**kwargs):
    connection.close()

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



def patched_split_domain_port(host):
    # Accept underscores in hostnames
    if host and host.count(':') == 1 and host.rfind(']') < host.find(':'):
        host, port = host.split(':', 1)
    else:
        port = ''
    return host, port

django.http.request.split_domain_port = patched_split_domain_port


