import os
import django
import requests
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'auth_service.settings')
django.setup()

from users.models import UserActivity
from django.utils import timezone

def test_activity_logging():
    """Test that activity logging is working"""
    print("Testing Activity Logging...")
    
    # Count activities before
    initial_count = UserActivity.objects.count()
    print(f"Initial activity count: {initial_count}")
    
    # Create a test activity
    from core.models import Tenant
    from users.models import CustomUser
    
    try:
        tenant = Tenant.objects.first()
        user = CustomUser.objects.first()
        
        if tenant and user:
            activity = UserActivity.objects.create(
                user=user,
                tenant=tenant,
                action="test_activity",
                performed_by=user,
                details={"test": "data"},
                ip_address="127.0.0.1",
                user_agent="Test Agent",
                success=True
            )
            print(f"✅ Created test activity: {activity.action}")
        else:
            print("⚠️  No tenant or user found for testing")
            
    except Exception as e:
        print(f"❌ Error creating test activity: {e}")
    
    # Count activities after
    final_count = UserActivity.objects.count()
    print(f"Final activity count: {final_count}")
    print(f"Activities created during test: {final_count - initial_count}")

if __name__ == "__main__":
    test_activity_logging()