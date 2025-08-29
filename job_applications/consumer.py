import os
import json
import requests

# Set DJANGO_SETTINGS_MODULE early
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "job_applications.settings")

import django
django.setup()

from kafka import KafkaConsumer
from django.conf import settings

def fetch_tenant_details(tenant_id):
    """
    Fetch tenant details from the auth_service API.
    """
    try:
        # You may need to provide a valid JWT token here if your auth_service requires it
        headers = {}
        if hasattr(settings, "AUTH_SERVICE_INTERNAL_TOKEN"):
            headers["Authorization"] = f"Bearer {settings.AUTH_SERVICE_INTERNAL_TOKEN}"
        response = requests.get(
            f"{settings.AUTH_SERVICE_URL}/api/tenant/tenants/{tenant_id}/",
            headers=headers,
            timeout=10
        )
        if response.status_code == 200:
            return response.json()
        else:
            print(f"[job_applications] Failed to fetch tenant {tenant_id}: {response.status_code}")
    except Exception as e:
        print(f"[job_applications] Exception fetching tenant {tenant_id}: {e}")
    return None

def process_tenant_event(data):
    tenant_id = data.get("id")
    if not tenant_id:
        print("[job_applications] No tenant ID in event data.")
        return
    tenant_details = fetch_tenant_details(tenant_id)
    if tenant_details:
        print(f"[job_applications] Tenant details fetched: {tenant_details}")
        # You can perform any logic here, e.g., cache, update local config, etc.
    else:
        print(f"[job_applications] Could not fetch tenant details for ID {tenant_id}")

def consume_kafka_messages():
    consumer = KafkaConsumer(
        settings.KAFKA_TOPICS["tenant"],
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        auto_offset_reset="latest",
        enable_auto_commit=True,
        group_id="job_applications_tenant_group",
        value_deserializer=lambda x: json.loads(x.decode("utf-8"))
    )

    for message in consumer:
        data = message.value
        if message.topic == settings.KAFKA_TOPICS["tenant"]:
            process_tenant_event(data)
        print(f"[job_applications] Processed message from {message.topic}: {data}")

if __name__ == "__main__":
    consume_kafka_messages()