# users/tasks.py

import logging
import uuid
from datetime import timedelta
import requests
from celery import shared_task
from django.utils import timezone
from django_tenants.utils import tenant_context
from django.conf import settings
from django.contrib.auth import get_user_model

from core.models import Tenant
from users.models import (
    UserProfile,
    OtherUserDocuments,
    InsuranceVerification,
    LegalWorkEligibility,
    Document,
)

logger = logging.getLogger("users")
User = get_user_model()

# Days before expiry to trigger warning
EXPIRY_THRESHOLDS = [30, 14, 7, 3, 1]


# ---------------------------------------------------------------------------
# Activity Logger (Async)
# ---------------------------------------------------------------------------
@shared_task
def log_activity_async(action, user_id, tenant_id, details, ip=None, user_agent=None, success=True):
    from .models import CustomUser, UserActivity

    user = CustomUser.objects.get(id=user_id) if user_id else None
    tenant = Tenant.objects.get(id=tenant_id)

    UserActivity.objects.create(
        user=user,
        tenant=tenant,
        action=action,
        details=details,
        ip_address=ip,
        user_agent=user_agent,
        success=success,
    )


# ---------------------------------------------------------------------------
# Notification Sender
# ---------------------------------------------------------------------------
def send_expiry_notification(user, document_info, days_value, event_type, source="application-system"):
    """
    Send a document expiry or expired notification to the Notification microservice.
    event_type can be:
      - user.document.expiry.warning
      - user.document.expired
    """
    try:
        now = timezone.now()
        tenant_id = str(user.tenant.id) if hasattr(user, "tenant") else "unknown-tenant"

        event_payload = {
            "metadata": {
                "event_id": str(uuid.uuid4()),
                "event_type": event_type,
                "event_version": "1.0",
                "created_at": now.isoformat(),
                "source": source,
                "tenant_id": tenant_id,
                "timestamp": now.isoformat(),
            },
            "data": {
                "full_name": f"{user.first_name} {user.last_name}".strip() or user.email,
                "user_email": user.email,
                "document_type": document_info.get("type", "Unknown Document"),
                "document_name": document_info.get("name", ""),
                "expiry_date": (
                    document_info.get("expiry_date").isoformat()
                    if document_info.get("expiry_date")
                    else None
                ),
                "days_left": days_value if event_type == "user.document.expiry.warning" else None,
                "days_expired": days_value if event_type == "user.document.expired" else None,
                "message": (
                    f"Your {document_info.get('type')} is expiring soon. "
                    "Please renew immediately to avoid employment disruption."
                    if event_type == "user.document.expiry.warning"
                    else f"Your {document_info.get('type')} has expired. Please renew immediately."
                ),
                "timezone": str(now.tzinfo) or "Africa/Lagos",
            },
        }

        notifications_url = settings.NOTIFICATIONS_SERVICE_URL + "/events/"
        logger.info(f"➡️ Sending {event_type} for {user.email} to {notifications_url}")
        response = requests.post(notifications_url, json=event_payload, timeout=5)
        response.raise_for_status()
        logger.info(f"✅ Notification sent for {event_type} ({response.status_code})")

    except requests.exceptions.RequestException as e:
        logger.warning(f"[❌ Notification Error] Failed to send event for {user.email}: {str(e)}")
    except Exception as e:
        logger.error(f"[❌ Notification Exception] Unexpected error for {user.email}: {str(e)}")


# ---------------------------------------------------------------------------
# Daily Document Expiry Checker
# ---------------------------------------------------------------------------
@shared_task
def check_expiring_documents():
    """
    Daily task to check for expiring or expired documents across all tenants
    and send notifications to the Notification Service.
    """
    logger.info("🔄 Starting daily check for expiring and expired documents")
    today = timezone.now().date()
    tenants = Tenant.objects.all()

    for tenant in tenants:
        with tenant_context(tenant):
            logger.info(f"🏢 Processing tenant: {tenant.schema_name}")

            # -------------------------------------------------------------------
            # USER PROFILE DOCUMENTS
            # -------------------------------------------------------------------
            user_profiles = UserProfile.objects.select_related("user").all()
            for profile in user_profiles:
                user = profile.user
                if not user or not user.is_active:
                    continue

                # Define documents to check
                docs_to_check = [
                    {
                        "field": "Right_to_work_document_expiry_date",
                        "type": "Right to Work Document",
                        "name": profile.Right_to_work_document_type or "Right to Work",
                    },
                    {
                        "field": "drivers_licence_expiry_date",
                        "type": "Driver's Licence",
                        "name": "Driver's Licence",
                    },
                    {
                        "field": "drivers_licence_insurance_expiry_date",
                        "type": "Driver's Licence Insurance",
                        "name": profile.drivers_license_insurance_provider or "Insurance",
                    },
                ]

                for doc in docs_to_check:
                    expiry_date = getattr(profile, doc["field"], None)
                    if not expiry_date:
                        continue

                    # Warn before expiry
                    if expiry_date >= today:
                        for threshold in EXPIRY_THRESHOLDS:
                            if expiry_date == today + timedelta(days=threshold):
                                send_expiry_notification(
                                    user,
                                    doc,
                                    threshold,
                                    "user.document.expiry.warning",
                                )
                                break

                    # Notify if already expired
                    elif expiry_date < today:
                        days_expired = (today - expiry_date).days
                        send_expiry_notification(
                            user,
                            doc,
                            days_expired,
                            "user.document.expired",
                        )

            # -------------------------------------------------------------------
            # OTHER USER DOCUMENTS
            # -------------------------------------------------------------------
            other_docs = OtherUserDocuments.objects.select_related("user_profile__user").all()
            for doc in other_docs:
                user = doc.user_profile.user
                if not user or not user.is_active:
                    continue
                expiry_date = doc.expiry_date

                if not expiry_date:
                    continue

                if expiry_date >= today:
                    for threshold in EXPIRY_THRESHOLDS:
                        if expiry_date == today + timedelta(days=threshold):
                            send_expiry_notification(
                                user,
                                {
                                    "type": "Other User Document",
                                    "name": doc.title or doc.government_id_type or "Generic Document",
                                    "expiry_date": expiry_date,
                                },
                                threshold,
                                "user.document.expiry.warning",
                            )
                            break
                elif expiry_date < today:
                    days_expired = (today - expiry_date).days
                    send_expiry_notification(
                        user,
                        {
                            "type": "Other User Document",
                            "name": doc.title or doc.government_id_type or "Generic Document",
                            "expiry_date": expiry_date,
                        },
                        days_expired,
                        "user.document.expired",
                    )

            # -------------------------------------------------------------------
            # INSURANCE VERIFICATION
            # -------------------------------------------------------------------
            insurances = InsuranceVerification.objects.select_related("user_profile__user").all()
            for ins in insurances:
                user = ins.user_profile.user
                if not user or not user.is_active:
                    continue
                expiry_date = ins.expiry_date
                if not expiry_date:
                    continue

                doc_info = {
                    "type": "Insurance Verification",
                    "name": ins.insurance_type.replace("_", " ").title(),
                    "expiry_date": expiry_date,
                }

                if expiry_date >= today:
                    for threshold in EXPIRY_THRESHOLDS:
                        if expiry_date == today + timedelta(days=threshold):
                            send_expiry_notification(user, doc_info, threshold, "user.document.expiry.warning")
                            break
                elif expiry_date < today:
                    days_expired = (today - expiry_date).days
                    send_expiry_notification(user, doc_info, days_expired, "user.document.expired")

            # -------------------------------------------------------------------
            # LEGAL WORK ELIGIBILITY
            # -------------------------------------------------------------------
            legal_docs = LegalWorkEligibility.objects.select_related("user_profile__user").all()
            for legal in legal_docs:
                user = legal.user_profile.user
                if not user or not user.is_active:
                    continue
                expiry_date = legal.expiry_date
                if not expiry_date:
                    continue

                doc_info = {
                    "type": "Legal Work Eligibility",
                    "name": "Legal Work Document",
                    "expiry_date": expiry_date,
                }

                if expiry_date >= today:
                    for threshold in EXPIRY_THRESHOLDS:
                        if expiry_date == today + timedelta(days=threshold):
                            send_expiry_notification(user, doc_info, threshold, "user.document.expiry.warning")
                            break
                elif expiry_date < today:
                    days_expired = (today - expiry_date).days
                    send_expiry_notification(user, doc_info, days_expired, "user.document.expired")

            # -------------------------------------------------------------------
            # GENERAL DOCUMENTS
            # -------------------------------------------------------------------
            general_docs = Document.objects.filter(tenant_id=tenant.id)
            for doc in general_docs:
                try:
                    user = User.objects.get(id=doc.uploaded_by_id) if doc.uploaded_by_id else None
                except User.DoesNotExist:
                    logger.warning(f"No user found for document {doc.id} in tenant {tenant.schema_name}")
                    continue

                if not user or not user.is_active:
                    continue

                expiry_date = doc.expiring_date.date() if doc.expiring_date else None
                if not expiry_date:
                    continue

                doc_info = {
                    "type": "General Document",
                    "name": doc.title or "Untitled Document",
                    "expiry_date": expiry_date,
                }

                if expiry_date >= today:
                    for threshold in EXPIRY_THRESHOLDS:
                        if expiry_date == today + timedelta(days=threshold):
                            send_expiry_notification(user, doc_info, threshold, "user.document.expiry.warning")
                            break
                elif expiry_date < today:
                    days_expired = (today - expiry_date).days
                    send_expiry_notification(user, doc_info, days_expired, "user.document.expired")

    logger.info("✅ Daily check for expiring and expired documents completed")
