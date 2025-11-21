# investments/services/roi_calculator.py
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
from django.db import transaction
from ..models import InvestmentPolicy, ROIAccrual, LedgerEntry

class ROICalculator:
    """Handle all ROI calculation logic"""
    
    @staticmethod
    def calculate_monthly_roi(principal, annual_rate=Decimal('40.00')):
        """Calculate monthly ROI (40% annual / 12 months)"""
        monthly_rate = annual_rate / Decimal('12.00') / Decimal('100.00')
        return principal * monthly_rate
    
    @staticmethod
    def should_accrue_roi(investment_date):
        """Determine if investment qualifies for current month ROI based on 1st-12th rule"""
        today = timezone.now().date()
        
        # Investments from 1st-12th get ROI for same month
        if 1 <= investment_date.day <= 12:
            return True
        
        # Investments from 13th+ get ROI from next month
        # Check if we're in a subsequent month
        return today > investment_date.replace(day=28) + timedelta(days=4)
    
    @classmethod
    def accrue_monthly_roi_for_policy(cls, policy):
        """Accrue monthly ROI for a specific policy"""
        if not cls.should_accrue_roi(policy.start_date.date()):
            return None
        
        # Calculate ROI
        roi_amount = cls.calculate_monthly_roi(policy.current_balance, policy.roi_rate)
        
        with transaction.atomic():
            # Update policy balances
            policy.roi_balance += roi_amount
            policy.total_balance += roi_amount
            policy.last_roi_calculation = timezone.now()
            policy.next_roi_date = timezone.now() + timedelta(days=30)
            policy.save()
            
            # Create ROI accrual record
            accrual = ROIAccrual.objects.create(
                tenant=policy.tenant,
                policy=policy,
                accrual_date=timezone.now(),
                calculation_period=timezone.now().strftime('%Y-%m'),
                principal_for_calculation=policy.current_balance,
                roi_rate_applied=policy.roi_rate,
                roi_amount=roi_amount
            )
            
            # Create ledger entry
            LedgerEntry.objects.create(
                tenant=policy.tenant,
                policy=policy,
                entry_date=timezone.now(),
                unique_reference=f"ROI-{policy.policy_number}-{timezone.now().strftime('%Y%m')}",
                description=f"ROI Accrual - {timezone.now().strftime('%B %Y')}",
                entry_type='roi_accrual',
                inflow=roi_amount,
                outflow=0,
                principal_balance=policy.current_balance,
                roi_balance=policy.roi_balance,
                total_balance=policy.total_balance,
                created_by=policy.last_updated_by
            )
            
            return accrual
    
    @classmethod
    def process_monthly_roi_accruals(cls):
        """Batch process ROI accruals for all eligible policies"""
        eligible_policies = InvestmentPolicy.objects.filter(
            status='active',
            next_roi_date__lte=timezone.now()
        )
        
        results = {
            'processed': 0,
            'errors': 0,
            'accruals': []
        }
        
        for policy in eligible_policies:
            try:
                accrual = cls.accrue_monthly_roi_for_policy(policy)
                if accrual:
                    results['accruals'].append(accrual)
                    results['processed'] += 1
            except Exception as e:
                results['errors'] += 1
                # Log error
                print(f"Error processing ROI for policy {policy.policy_number}: {e}")
        
        return results