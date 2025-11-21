# investments/signals.py
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from .models import InvestmentPolicy, LedgerEntry, ROIAccrual

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