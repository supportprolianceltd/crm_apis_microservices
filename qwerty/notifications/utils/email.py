import requests
from django.core.mail import EmailMessage

def get_tenant_email_config(tenant_id):
    url = f"http://auth-service:8001/api/public/tenant-config/{tenant_id}/"
    response = requests.get(url)
    return response.json().get("email_config", {})

def render_template_from_key(template_key, context):
    # You can improve this by loading actual templates
    return "\n".join([f"{k}: {v}" for k, v in context.items()])

def send_tenant_email(tenant_id, to_email, subject, template_key, context):
    config = get_tenant_email_config(tenant_id)
    content = render_template_from_key(template_key, context)

    email = EmailMessage(
        subject=subject,
        body=content,
        from_email=config.get("default_from_email"),
        to=[to_email]
    )
    email.send()
