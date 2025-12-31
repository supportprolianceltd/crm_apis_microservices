# investments/signals.py
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from .models import InvestmentPolicy, LedgerEntry, ROIAccrual
from datetime import datetime, timedelta


# investments/signals.py
@receiver(pre_save, sender=InvestmentPolicy)
def generate_policy_numbers(sender, instance, **kwargs):
    """Auto-generate policy numbers with tenant isolation"""
    if not instance.policy_number:
        # ✅ Ensure tenant context for policy number generation
        instance.policy_number = instance.tenant.get_next_policy_number()

    if not instance.unique_policy_id:
        # ✅ Tenant-isolated sequence generation
        last_policy = InvestmentPolicy.objects.filter(
            tenant=instance.tenant  # ✅ Critical: Filter by tenant
        ).order_by('-unique_policy_id').first()

        if last_policy and last_policy.unique_policy_id:
            last_number = int(last_policy.unique_policy_id)
            instance.unique_policy_id = str(last_number + 1).zfill(6)
        else:
            instance.unique_policy_id = "200000"

    # Set next_roi_date for new policies based on eligibility
    if not instance.next_roi_date:
        from .services.roi_calculator import ROICalculator
        if ROICalculator.should_accrue_roi(instance.start_date.date()):
            # Policy is eligible for ROI now, set next_roi_date to past so it gets picked up
            instance.next_roi_date = timezone.now() - timedelta(days=1)
        else:
            # Policy not eligible yet, set to next month
            instance.next_roi_date = timezone.now() + timedelta(days=30)
            
            
@receiver(post_save, sender=InvestmentPolicy)
def create_initial_ledger_entry(sender, instance, created, **kwargs):
    """Create initial ledger entry for new investment"""
    if created:
        LedgerEntry.objects.create(
            tenant=instance.tenant,
            policy=instance,
            entry_date=timezone.now(),
            unique_reference=f"DEP-{instance.policy_number}-INIT",
            description=f"Initial deposit - Policy {instance.policy_number}",
            entry_type='deposit',
            inflow=instance.principal_amount,
            outflow=0,
            principal_balance=instance.principal_amount,
            roi_balance=0,
            total_balance=instance.principal_amount,
            created_by=instance.last_updated_by
        )

        # Update user's profile investment_details
        if hasattr(instance.user, 'profile'):
            profile = instance.user.profile
            # Check if investment detail already exists
            existing_detail = None
            for detail in profile.investment_details.all():
                if str(detail.investment_amount) == str(instance.principal_amount):
                    existing_detail = detail
                    break

            if not existing_detail:
                # Add new investment detail as related model instance
                from decimal import Decimal
                profile.investment_details.create(
                    roi_rate=instance.roi_frequency,
                    custom_roi_rate=None,
                    investment_amount=instance.principal_amount,
                    investment_start_date=instance.start_date,
                    remaining_balance=instance.principal_amount,
                    last_updated_by_id=getattr(instance.last_updated_by, 'id', 'system') if instance.last_updated_by else 'system',
                )