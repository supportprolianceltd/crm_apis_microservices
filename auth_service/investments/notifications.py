# investments/notifications.py (CREATE NEW FILE)
from django.core.mail import send_mail
from django.conf import settings

class InvestmentNotifications:
    """Centralized notification system for investment events"""
    
    @staticmethod
    def send_investment_created(policy):
        """Notify investor when investment is created"""
        send_mail(
            subject=f'Investment Policy Created - {policy.policy_number}',
            message=f"""
            Dear {policy.user.first_name},
            
            Your investment policy {policy.policy_number} has been successfully created.
            
            Investment Amount: {policy.principal_amount}
            ROI Rate: {policy.roi_rate}% annually
            Start Date: {policy.start_date}
            
            Thank you for investing with us!
            """,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[policy.user.email],
            fail_silently=True,
        )
    
    @staticmethod
    def send_roi_accrued(policy, roi_amount):
        """Notify investor when ROI is accrued"""
        send_mail(
            subject=f'ROI Accrued - Policy {policy.policy_number}',
            message=f"""
            Dear {policy.user.first_name},
            
            Your monthly ROI of {roi_amount} has been accrued to your policy {policy.policy_number}.
            
            Current Balance: {policy.current_balance}
            ROI Balance: {policy.roi_balance}
            Total Balance: {policy.current_balance + policy.roi_balance}
            
            """,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[policy.user.email],
            fail_silently=True,
        )
    
    @staticmethod
    def send_withdrawal_approved(withdrawal):
        """Notify investor when withdrawal is approved"""
        send_mail(
            subject=f'Withdrawal Approved - {withdrawal.policy.policy_number}',
            message=f"""
            Dear {withdrawal.user.first_name},
            
            Your withdrawal request for {withdrawal.amount_requested} has been approved.
            
            Policy Number: {withdrawal.policy.policy_number}
            Withdrawal Type: {withdrawal.get_withdrawal_type_display()}
            Amount: {withdrawal.amount_requested}
            
            The funds will be disbursed to your registered bank account shortly.
            """,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[withdrawal.user.email],
            fail_silently=True,
        )
    
    @staticmethod
    def send_topup_confirmed(policy, topup_amount):
        """Notify investor when top-up is added"""
        send_mail(
            subject=f'Top-up Confirmed - Policy {policy.policy_number}',
            message=f"""
            Dear {policy.user.first_name},
            
            Your top-up of {topup_amount} has been added to policy {policy.policy_number}.
            
            New Balance: {policy.current_balance}
            
            Thank you for your continued investment!
            """,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[policy.user.email],
            fail_silently=True,
        )