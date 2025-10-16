try:
    from hr_service.hr_service.celery import app as celery_app
except ImportError:
    celery_app = None
__all__ = ('celery_app',)