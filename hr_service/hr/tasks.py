from hr_service.hr_service.celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .models import (
    EscalationAlert, LeaveRequest, ProbationPeriod, PolicyAcknowledgment,
    Equipment, DisciplinaryWarning, Contract
)
import logging

logger = logging.getLogger('hr')

@shared_task
def check_escalations():
    """Step 7: Daily alerts."""
    today = timezone.now().date()
    
    # Get unique tenant_ids from existing records instead of Tenant model
    tenant_ids = set()
    
    # Get tenant IDs from various models
    from_leave = LeaveRequest.objects.values_list('tenant_id', flat=True).distinct()
    from_probation = ProbationPeriod.objects.values_list('tenant_id', flat=True).distinct()
    from_equipment = Equipment.objects.values_list('tenant_id', flat=True).distinct()
    from_warnings = DisciplinaryWarning.objects.values_list('tenant_id', flat=True).distinct()
    
    tenant_ids.update(from_leave)
    tenant_ids.update(from_probation)
    tenant_ids.update(from_equipment)
    tenant_ids.update(from_warnings)

    for tenant_id in tenant_ids:
        # RTW >7 days
        long_absences = LeaveRequest.objects.filter(
            tenant_id=tenant_id, 
            end_date__lt=today - timedelta(days=7), 
            status='approved'
        )
        for req in long_absences:
            if not req.self_cert_form_sent:
                alert = EscalationAlert.objects.create(
                    tenant_id=tenant_id, 
                    user_id=req.user_id,
                    type='rtw_interview', 
                    description='RTW interview overdue',
                    severity='high'
                )
                alert.notify()

        # Probation ends
        ending_probations = ProbationPeriod.objects.filter(
            tenant_id=tenant_id, 
            end_date=today, 
            status='in_progress'
        )
        for prob in ending_probations:
            alert = EscalationAlert.objects.create(
                tenant_id=tenant_id, 
                user_id=prob.user_id,
                type='probation_end', 
                description='Probation review required'
            )
            alert.notify()

        # Active warnings expiring
        expiring_warnings = DisciplinaryWarning.objects.filter(
            tenant_id=tenant_id, 
            expires_date__lte=today + timedelta(days=7), 
            is_active=True
        )
        for warn in expiring_warnings:
            alert = EscalationAlert.objects.create(
                tenant_id=tenant_id, 
                user_id=warn.user_id,
                type='disciplinary_warning', 
                description='Warning expiring soon'
            )
            alert.notify()

        # Unreturned equipment
        overdue_equipment = Equipment.objects.filter(
            tenant_id=tenant_id, 
            issued_date__lt=today - timedelta(days=30), 
            is_returned=False
        )
        for eq in overdue_equipment:
            alert = EscalationAlert.objects.create(
                tenant_id=tenant_id, 
                user_id=eq.user_id,
                type='overdue_document', 
                description=f'Unreturned {eq.item_name}'
            )
            alert.notify()

        # High Bradford
        high_risk = LeaveRequest.objects.filter(
            tenant_id=tenant_id, 
            bradford_factor__gt=100
        )
        for req in high_risk:
            alert = EscalationAlert.objects.create(
                tenant_id=tenant_id, 
                user_id=req.user_id,
                type='high_bradford', 
                description='High absence risk'
            )
            alert.notify()


@shared_task
def send_policy_reminders():
    """Step 6: Remind non-compliant."""
    unacknowledged = PolicyAcknowledgment.objects.filter(acknowledged_at__isnull=True)
    for ack in unacknowledged:
        payload = {
            'tenant_id': str(ack.tenant_id),
            'user_id': str(ack.user_id),
            'message': f'Acknowledge policy: {ack.policy.title}',
            'type': 'policy_reminder'
        }
        logger.info(f"Policy reminder: {payload}")
        # requests.post(NOTIFICATIONS_SERVICE_URL + '/api/notifications/', json=payload)


@shared_task
def calculate_bradford_factors():
    """Monthly Bradford recalc (Step 3)."""
    sick_leave_requests = LeaveRequest.objects.filter(
        leave_type__name='sick', 
        bradford_factor__isnull=True
    )
    for req in sick_leave_requests:
        req.save()  # Triggers recalc in save method


@shared_task
def notify_leave_approved(leave_id):
    try:
        leave = LeaveRequest.objects.get(id=leave_id)
        payload = {
            'tenant_id': str(leave.tenant_id),
            'user_id': str(leave.user_id),
            'message': f'Leave approved: {leave.start_date} to {leave.end_date}',
            'type': 'leave_approved'
        }
        logger.info(f"Leave approved notification: {payload}")
        # requests.post(NOTIFICATIONS_SERVICE_URL + '/api/notifications/', json=payload)
    except LeaveRequest.DoesNotExist:
        logger.error(f"LeaveRequest {leave_id} not found for notification")


@shared_task
def send_self_cert_prompt(leave_id):
    try:
        leave = LeaveRequest.objects.get(id=leave_id)
        leave.self_cert_form_sent = True
        leave.save()
        payload = {
            'tenant_id': str(leave.tenant_id),
            'user_id': str(leave.user_id),
            'message': 'Complete self-cert form for absence >7 days',
            'type': 'self_cert_prompt',
            'attachment': 'self_cert.pdf'
        }
        logger.info(f"Self-cert prompt: {payload}")
        # requests.post(NOTIFICATIONS_SERVICE_URL + '/api/notifications/', json=payload)
    except LeaveRequest.DoesNotExist:
        logger.error(f"LeaveRequest {leave_id} not found for self-cert prompt")


@shared_task
def notify_contract_ready(contract_id, esign_url):
    try:
        contract = Contract.objects.get(id=contract_id)
        payload = {
            'tenant_id': str(contract.tenant_id),
            'user_id': str(contract.user_id),
            'message': 'Review and sign contract',
            'type': 'contract_ready',
            'url': esign_url
        }
        logger.info(f"Contract ready notification: {payload}")
        # requests.post(NOTIFICATIONS_SERVICE_URL + '/api/notifications/', json=payload)
    except Contract.DoesNotExist:
        logger.error(f"Contract {contract_id} not found for notification")


@shared_task
def notify_equipment_issued(equipment_id, esign_url):
    try:
        equipment = Equipment.objects.get(id=equipment_id)
        payload = {
            'tenant_id': str(equipment.tenant_id),
            'user_id': str(equipment.user_id),
            'message': f'Accept {equipment.item_name}',
            'type': 'equipment_accept',
            'url': esign_url
        }
        logger.info(f"Equipment issued notification: {payload}")
        # requests.post(NOTIFICATIONS_SERVICE_URL + '/api/notifications/', json=payload)
    except Equipment.DoesNotExist:
        logger.error(f"Equipment {equipment_id} not found for notification")


@shared_task
def generate_contract_task(contract_id):
    """Step 4: Async PDF gen."""
    try:
        contract = Contract.objects.get(id=contract_id)
        contract.generate_and_sign()
    except Contract.DoesNotExist:
        logger.error(f"Contract {contract_id} not found for generation")
    except Exception as e:
        logger.error(f"Contract generation failed for {contract_id}: {str(e)}")


@shared_task
def create_onboarding(user_id, tenant_id):
    """Create initial HR records for new user."""
    try:
        # Create initial probation period (90 days from start)
        start_date = timezone.now().date()
        end_date = start_date + timedelta(days=90)
        
        ProbationPeriod.objects.create(
            tenant_id=tenant_id,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            status='in_progress'
        )
        
        logger.info(f"Created onboarding for user {user_id} in tenant {tenant_id}")
    except Exception as e:
        logger.error(f"Failed to create onboarding for user {user_id}: {str(e)}")