from celery import shared_task
from .utils.email import send_tenant_email

@shared_task
def send_notification_email(tenant_id, to_email, subject, template_key, context):
    send_tenant_email(tenant_id, to_email, subject, template_key, context)
