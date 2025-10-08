import requests
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from io import BytesIO
import json
from django.conf import settings
import logging

logger = logging.getLogger('hr')

def fetch_user_details(user_id, tenant_id):
    """Fetch from auth API (Step 1/2)."""
    try:
        response = requests.get(
            f"{settings.AUTH_SERVICE_URL}/api/user/users/{user_id}/",
            headers={'X-Tenant-ID': tenant_id},
            timeout=5
        )
        if response.status_code == 200:
            return response.json()
        return {}
    except requests.RequestException as e:
        logger.error(f"Failed to fetch user {user_id}: {str(e)}")
        return {}

def fetch_users_from_auth(tenant_id, include_profile=False):
    """Batch fetch employees."""
    try:
        params = {'tenant_id': tenant_id}
        if include_profile:
            params['include_profile'] = 'true'
            
        response = requests.get(
            f"{settings.AUTH_SERVICE_URL}/api/user/users/", 
            params=params,
            timeout=10
        )
        if response.status_code == 200:
            return response.json().get('results', [])
        return []
    except requests.RequestException as e:
        logger.error(f"Failed to fetch users for tenant {tenant_id}: {str(e)}")
        return []

def generate_pdf_contract(contract):
    """Step 4: Simple PDF gen."""
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    
    # Add content to PDF
    p.drawString(100, 750, f"Employment Contract")
    p.drawString(100, 730, f"Employee ID: {contract.user_id}")
    p.drawString(100, 710, f"Type: {contract.get_type_display()}")
    p.drawString(100, 690, f"Salary: {contract.salary}")
    p.drawString(100, 670, f"Start Date: {contract.start_date}")
    if contract.end_date:
        p.drawString(100, 650, f"End Date: {contract.end_date}")
    p.drawString(100, 630, f"Probation Period: {contract.probation_days} days")
    
    p.save()
    buffer.seek(0)
    return buffer

def upload_to_auth(pdf_buffer, user_id, title):
    """Upload to auth Document model."""
    try:
        files = {'file': ('contract.pdf', pdf_buffer, 'application/pdf')}
        data = {
            'title': title, 
            'uploaded_by_id': user_id,
            'document_type': 'contract'
        }
        response = requests.post(
            f"{settings.AUTH_SERVICE_URL}/api/user/documents/", 
            files=files, 
            data=data,
            timeout=10
        )
        if response.status_code == 201:
            return response.json().get('id')
        logger.error(f"Upload failed: {response.status_code} - {response.text}")
        raise ValueError("Upload failed")
    except requests.RequestException as e:
        logger.error(f"Upload request failed: {str(e)}")
        raise ValueError(f"Upload failed: {str(e)}")

def initiate_esign(doc_id, user_id=None):
    """Stub: E-sign integration."""
    # This would integrate with DocuSign, HelloSign, etc.
    # For now, return a stub URL
    logger.info(f"Initiating e-sign for document {doc_id}")
    return f"https://esign-demo.com/sign/{doc_id}"

# Kafka Consumer (commented out as it would run in separate process)
"""
from kafka import KafkaConsumer
import json

def start_kafka_consumer():
    consumer = KafkaConsumer(
        getattr(settings, 'KAFKA_USER_EVENTS_TOPIC', 'user-events'),
        bootstrap_servers=getattr(settings, 'KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092'),
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        group_id='hr-service'
    )
    
    for message in consumer:
        event = message.value
        if event.get('action') == 'user_created':
            # Auto-create probation/contract
            from .tasks import create_onboarding
            create_onboarding.delay(event['user_id'], event['tenant_id'])
            
        logger.info(f"Processed Kafka event: {event.get('action')}")
"""