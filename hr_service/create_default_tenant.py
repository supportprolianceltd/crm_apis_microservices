# create_default_tenant.py
import os
import django
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hr_service.settings")
django.setup()

from core.models import Tenant

def create_default_tenant():
    TENANT_SCHEMA = "default"  # Changed from "public" to "default"
    TENANT_NAME = "Default Tenant"
    TENANT_DOMAIN = "localhost"

    try:
        # Only create if it doesn't exist
        if not Tenant.objects.filter(schema_name=TENANT_SCHEMA).exists():
            tenant = Tenant(
                schema_name=TENANT_SCHEMA,
                name=TENANT_NAME,
                paid_until="2030-01-01",
                on_trial=False,
            )
            tenant.save()

        else:
            print("✅ Tenant already exists.")
            
        return True
    except Exception as e:
        print(f"❌ Error creating tenant: {e}")
        return False

if __name__ == "__main__":
    success = create_default_tenant()
    sys.exit(0 if success else 1)