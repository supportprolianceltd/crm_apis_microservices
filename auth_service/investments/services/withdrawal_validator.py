# investments/services/withdrawal_validator.py
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from django.core.exceptions import ValidationError

class WithdrawalValidator:
    """Validate withdrawal requests against business rules"""
    
    @staticmethod
    def validate_principal_withdrawal(policy, amount):
        """Validate principal withdrawal against 4-month rule"""
        if policy.status != 'active':
            raise ValidationError("Policy must be active for withdrawals")
        
        # Check 4-month restriction
        months_invested = (timezone.now() - policy.start_date).days // 30
        if months_invested < policy.min_withdrawal_months:
            raise ValidationError(
                f"Principal withdrawals allowed only after {policy.min_withdrawal_months} months. "
                f"Current: {months_invested} months"
            )
        
        # Check sufficient balance
        if amount > policy.current_balance:
            raise ValidationError(
                f"Insufficient principal balance. Available: {policy.current_balance}"
            )
        
        return True
    
    @staticmethod
    def validate_roi_withdrawal(policy, amount):
        """Validate ROI withdrawal"""
        if amount > policy.roi_balance:
            raise ValidationError(
                f"Insufficient ROI balance. Available: {policy.roi_balance}"
            )
        return True
    
    @staticmethod
    def validate_composite_withdrawal(policy, principal_amount, roi_amount):
        """Validate composite withdrawal (principal + ROI)"""
        # Validate principal portion
        if principal_amount > 0:
            WithdrawalValidator.validate_principal_withdrawal(policy, principal_amount)
        
        # Validate ROI portion
        if roi_amount > 0:
            WithdrawalValidator.validate_roi_withdrawal(policy, roi_amount)
        
        return True
    
    @classmethod
    def get_available_balances(cls, policy):
        """Get available balances for withdrawal"""
        months_invested = (timezone.now() - policy.start_date).days // 30
        
        return {
            'principal_available': policy.current_balance if months_invested >= policy.min_withdrawal_months else Decimal('0.00'),
            'roi_available': policy.roi_balance,
            'total_available': policy.total_balance,
            'principal_locked_until': policy.start_date + timedelta(days=policy.min_withdrawal_months * 30),
        }