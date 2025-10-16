from __future__ import absolute_import, unicode_literals
import os
from hr_service.hr_service.celery import Celery

# Set default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hr_service.settings')

app = Celery('hr_service')

# Load settings from Django’s settings.py
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks across all apps
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
