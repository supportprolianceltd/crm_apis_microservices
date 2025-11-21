# investments/tasks.py
from celery import shared_task
from django.utils import timezone
from .services.roi_calculator import ROICalculator
from .models import InvestmentPolicy

# investments/tasks.py
@shared_task
def accrue_monthly_roi_for_tenant(tenant_id=None):
    """Scheduled task with explicit tenant support"""
    from django_tenants.utils import tenant_context
    from core.models import Tenant
    
    if tenant_id:
        # Process for specific tenant
        tenant = Tenant.objects.get(id=tenant_id)
        with tenant_context(tenant):
            results = ROICalculator.process_monthly_roi_accruals()
    else:
        # Process for all tenants (system-wide task)
        tenants = Tenant.objects.filter(status='active')
        all_results = {}
        
        for tenant in tenants:
            with tenant_context(tenant):
                results = ROICalculator.process_monthly_roi_accruals()
                all_results[tenant.schema_name] = results
    
    return all_results


@shared_task
def send_roi_due_notifications():
    """Send notifications for upcoming ROI payments"""
    from django.core.mail import send_mail
    
    due_policies = InvestmentPolicy.objects.filter(
        status='active',
        next_roi_date__lte=timezone.now() + timedelta(days=3)
    ).select_related('user')
    
    for policy in due_policies:
        send_mail(
            subject=f'ROI Payment Due - Policy {policy.policy_number}',
            message=f'Your ROI payment for policy {policy.policy_number} is due soon.',
            from_email='noreply@yourcompany.com',
            recipient_list=[policy.user.email],
            fail_silently=True,
        )
    
    return f"Notifications sent for {due_policies.count()} policies"