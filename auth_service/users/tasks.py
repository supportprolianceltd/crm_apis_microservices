# users/tasks.py
import logging
from datetime import datetime, timedelta
from celery import shared_task
from django.utils import timezone
from django_tenants.utils import tenant_context
from django.conf import settings
import requests
import uuid

from core.models import Tenant
from users.models import UserProfile, OtherUserDocuments, InsuranceVerification, LegalWorkEligibility, Document
from django.contrib.auth import get_user_model

logger = logging.getLogger('users')

User = get_user_model()

EXPIRY_THRESHOLDS = [30, 14, 7, 3, 1]  # days before expiry

def send_expiry_notification(user, document_info, days_left, event_type, source="users"):
    """
    Send an expiry notification event to the notification microservice.
    """
    try:
        event_payload = {
            "metadata": {
                "tenant_id": str(user.tenant.id),
                "event_type": event_type,
                "event_id": str(uuid.uuid4()),
                "created_at": timezone.now().isoformat(),
                "source": source
            },
            "data": {
                "user_email": user.email,
                "full_name": f"{user.first_name} {user.last_name}".strip() or user.email,
                "document_type": document_info.get("type", "Unknown Document"),
                "document_name": document_info.get("name", ""),
                "expiry_date": document_info.get("expiry_date").isoformat() if document_info.get("expiry_date") else None,
                "days_left": days_left,
                "timestamp": timezone.now().isoformat(),
                "user_agent": "background-task"  # Optional field
            }
        }

        notifications_url = settings.NOTIFICATIONS_SERVICE_URL + "/events/"
        logger.info(f"➡️ POST to {notifications_url} with payload for user {user.email}: {event_payload}")

        response = requests.post(notifications_url, json=event_payload, timeout=5)
        response.raise_for_status()

        logger.info(f"✅ Expiry notification sent for {event_type} to {user.email}. "
                    f"Status: {response.status_code}, Response: {response.text}")

    except requests.exceptions.RequestException as e:
        logger.warning(f"[❌ Notification Error] Failed to send expiry event for {user.email}: {str(e)}")
    except Exception as e:
        logger.error(f"[❌ Notification Exception] Unexpected error for {user.email}: {str(e)}")

@shared_task
def check_expiring_documents():
    """
    Daily task to check for expiring documents across all tenants and send notifications.
    """
    logger.info("Starting daily check for expiring documents")
    today = timezone.now().date()
    
    # Get all tenants
    tenants = Tenant.objects.all()
    
    for tenant in tenants:
        with tenant_context(tenant):
            logger.info(f"Processing tenant: {tenant.schema_name}")
            
            # UserProfile documents
            user_profiles = UserProfile.objects.select_related('user').all()
            for profile in user_profiles:
                user = profile.user
                if not user.is_active:
                    continue
                
                # Right to Work
                if profile.Right_to_work_document_expiry_date:
                    expiry_date = profile.Right_to_work_document_expiry_date
                    if expiry_date >= today:
                        for threshold in EXPIRY_THRESHOLDS:
                            target_date = today + timedelta(days=threshold)
                            if expiry_date == target_date:
                                document_info = {
                                    "type": "Right to Work Document",
                                    "name": profile.Right_to_work_document_type or "Right to Work",
                                    "expiry_date": expiry_date
                                }
                                event_type = f"user.document.right_to_work.expiry.warning.{threshold}d"
                                send_expiry_notification(user, document_info, threshold, event_type)
                                break
                
                # Driver's Licence
                if profile.drivers_licence_expiry_date:
                    expiry_date = profile.drivers_licence_expiry_date
                    if expiry_date >= today:
                        for threshold in EXPIRY_THRESHOLDS:
                            target_date = today + timedelta(days=threshold)
                            if expiry_date == target_date:
                                document_info = {
                                    "type": "Driver's Licence",
                                    "name": "Driver's Licence",
                                    "expiry_date": expiry_date
                                }
                                event_type = f"user.document.drivers_licence.expiry.warning.{threshold}d"
                                send_expiry_notification(user, document_info, threshold, event_type)
                                break
                
                # Driver's Licence Insurance
                if profile.drivers_licence_insurance_expiry_date:
                    expiry_date = profile.drivers_licence_insurance_expiry_date
                    if expiry_date >= today:
                        for threshold in EXPIRY_THRESHOLDS:
                            target_date = today + timedelta(days=threshold)
                            if expiry_date == target_date:
                                document_info = {
                                    "type": "Driver's Licence Insurance",
                                    "name": profile.drivers_license_insurance_provider or "Insurance",
                                    "expiry_date": expiry_date
                                }
                                event_type = f"user.document.drivers_insurance.expiry.warning.{threshold}d"
                                send_expiry_notification(user, document_info, threshold, event_type)
                                break
            
            # OtherUserDocuments
            other_docs = OtherUserDocuments.objects.select_related('user_profile__user').filter(expiry_date__gte=today)
            for doc in other_docs:
                user = doc.user_profile.user
                if not user.is_active:
                    continue
                expiry_date = doc.expiry_date
                for threshold in EXPIRY_THRESHOLDS:
                    target_date = today + timedelta(days=threshold)
                    if expiry_date == target_date:
                        document_info = {
                            "type": "Other User Document",
                            "name": doc.title or doc.government_id_type or "Generic Document",
                            "expiry_date": expiry_date
                        }
                        event_type = f"user.document.other.expiry.warning.{threshold}d"
                        send_expiry_notification(user, document_info, threshold, event_type)
                        break
            
            # InsuranceVerification
            insurances = InsuranceVerification.objects.select_related('user_profile__user').filter(expiry_date__gte=today)
            for ins in insurances:
                user = ins.user_profile.user
                if not user.is_active:
                    continue
                expiry_date = ins.expiry_date
                for threshold in EXPIRY_THRESHOLDS:
                    target_date = today + timedelta(days=threshold)
                    if expiry_date == target_date:
                        document_info = {
                            "type": "Insurance Verification",
                            "name": ins.insurance_type.replace('_', ' ').title(),
                            "expiry_date": expiry_date
                        }
                        event_type = f"user.document.insurance.expiry.warning.{threshold}d"
                        send_expiry_notification(user, document_info, threshold, event_type)
                        break
            
            # LegalWorkEligibility
            legal_docs = LegalWorkEligibility.objects.select_related('user_profile__user').filter(expiry_date__gte=today)
            for legal in legal_docs:
                user = legal.user_profile.user
                if not user.is_active:
                    continue
                expiry_date = legal.expiry_date
                for threshold in EXPIRY_THRESHOLDS:
                    target_date = today + timedelta(days=threshold)
                    if expiry_date == target_date:
                        document_info = {
                            "type": "Legal Work Eligibility",
                            "name": "Legal Work Document",
                            "expiry_date": expiry_date
                        }
                        event_type = f"user.document.legal_work.expiry.warning.{threshold}d"
                        send_expiry_notification(user, document_info, threshold, event_type)
                        break
            
            # Document (General) - assuming tenant_id links to tenant
            general_docs = Document.objects.filter(tenant_id=tenant.id, expiring_date__gte=timezone.now())
            for doc in general_docs:
                # Find associated user if possible, e.g., via uploaded_by_id or other logic
                # For simplicity, assume we can find user; adjust as needed
                try:
                    user = User.objects.get(id=doc.uploaded_by_id) if doc.uploaded_by_id else None
                    if user and not user.is_active:
                        continue
                    expiry_date = doc.expiring_date.date()
                    if expiry_date >= today:
                        for threshold in EXPIRY_THRESHOLDS:
                            target_date = today + timedelta(days=threshold)
                            if expiry_date == target_date:
                                document_info = {
                                    "type": "General Document",
                                    "name": doc.title,
                                    "expiry_date": expiry_date
                                }
                                event_type = f"user.document.general.expiry.warning.{threshold}d"
                                if user:
                                    send_expiry_notification(user, document_info, threshold, event_type)
                                break
                except User.DoesNotExist:
                    logger.warning(f"No user found for document {doc.id} in tenant {tenant.schema_name}")
                    continue
    
    logger.info("Daily check for expiring documents completed")