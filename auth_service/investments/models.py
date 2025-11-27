# investments/models.py
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator
from decimal import Decimal

class InvestmentPolicy(models.Model):
    """Core investment policy model"""
    POLICY_STATUS = [
        ('active', 'Active'),
        ('matured', 'Matured'),
        ('closed', 'Closed'),
        ('suspended', 'Suspended'),
    ]
    
    ROLLOVER_OPTIONS = [
        ('principal_only', 'Principal Only'),
        ('principal_plus_roi', 'Principal + ROI'),
        ('custom', 'Custom Amount'),
    ]
    
    tenant = models.ForeignKey('core.Tenant', on_delete=models.CASCADE)
    user = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE, related_name='investment_policies')
    profile = models.ForeignKey('users.UserProfile', on_delete=models.CASCADE, related_name='policies')
    
    # Policy Identification
    policy_number = models.CharField(max_length=20, unique=True, db_index=True)
    unique_policy_id = models.CharField(max_length=50, unique=True)  # 6-digit logical sequence
    
    # Investment Details
    principal_amount = models.DecimalField(max_digits=20, decimal_places=2, validators=[MinValueValidator(0)])
    current_balance = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    total_withdrawn = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    
    # ROI Configuration
    roi_rate = models.DecimalField(max_digits=5, decimal_places=2, default=40.00)  # Annual rate
    roi_frequency = models.CharField(max_length=20, choices=[('monthly', 'Monthly'), ('on_demand', 'On Demand')], default='monthly')
    roi_balance = models.DecimalField(max_digits=20, decimal_places=2, default=0)  # Accumulated ROI
    
    # Dates & Terms
    start_date = models.DateTimeField(default=timezone.now)
    maturity_date = models.DateTimeField(null=True, blank=True)
    last_roi_calculation = models.DateTimeField(null=True, blank=True)
    next_roi_date = models.DateTimeField(null=True, blank=True)
    
    # Policy Rules
    min_withdrawal_months = models.PositiveIntegerField(default=4)
    allow_partial_withdrawals = models.BooleanField(default=True)
    auto_rollover = models.BooleanField(default=False)
    rollover_option = models.CharField(max_length=20, choices=ROLLOVER_OPTIONS, default='principal_only')
    
    # Status & Metadata
    status = models.CharField(max_length=20, choices=POLICY_STATUS, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_updated_by = models.ForeignKey('users.CustomUser', on_delete=models.SET_NULL, null=True, related_name='updated_policies')

    class Meta:
        db_table = 'investments_policy'
        indexes = [
            models.Index(fields=['tenant', 'policy_number']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'next_roi_date']),
        ]

    def __str__(self):
        return f"{self.policy_number} - {self.user.email}"

class LedgerEntry(models.Model):
    """Comprehensive ledger for all financial transactions"""
    ENTRY_TYPES = [
        ('deposit', 'Deposit'),
        ('top_up', 'Top Up'),
        ('withdrawal_principal', 'Withdrawal - Principal'),
        ('withdrawal_roi', 'Withdrawal - ROI'),
        ('roi_accrual', 'ROI Accrual'),
        ('fee', 'Fee'),
        ('adjustment', 'Adjustment'),
    ]
    
    tenant = models.ForeignKey('core.Tenant', on_delete=models.CASCADE)
    policy = models.ForeignKey(InvestmentPolicy, on_delete=models.CASCADE, related_name='ledger_entries')
    
    # Entry Identification
    entry_date = models.DateTimeField(default=timezone.now)
    unique_reference = models.CharField(max_length=50, unique=True)
    description = models.TextField()
    entry_type = models.CharField(max_length=25, choices=ENTRY_TYPES)
    
    # Financial Amounts
    inflow = models.DecimalField(max_digits=20, decimal_places=2, default=0)  # Deposits, top-ups
    outflow = models.DecimalField(max_digits=20, decimal_places=2, default=0)  # Withdrawals, fees
    
    # Running Balances
    principal_balance = models.DecimalField(max_digits=20, decimal_places=2)
    roi_balance = models.DecimalField(max_digits=20, decimal_places=2)
    total_balance = models.DecimalField(max_digits=20, decimal_places=2)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey('users.CustomUser', on_delete=models.SET_NULL, null=True)
    
    class Meta:
        db_table = 'investments_ledger'
        indexes = [
            models.Index(fields=['policy', 'entry_date']),
            models.Index(fields=['tenant', 'entry_date']),
            models.Index(fields=['entry_type', 'entry_date']),
        ]
        ordering = ['-entry_date']

    @property
    def entry_type_display(self):
        return self.get_entry_type_display()

class ROIAccrual(models.Model):
    """Track ROI calculations and accruals"""
    tenant = models.ForeignKey('core.Tenant', on_delete=models.CASCADE)
    policy = models.ForeignKey(InvestmentPolicy, on_delete=models.CASCADE, related_name='roi_accruals')
    
    accrual_date = models.DateTimeField()
    calculation_period = models.CharField(max_length=50)  # e.g., "2024-01"
    principal_for_calculation = models.DecimalField(max_digits=20, decimal_places=2)
    roi_rate_applied = models.DecimalField(max_digits=5, decimal_places=2)
    roi_amount = models.DecimalField(max_digits=20, decimal_places=2)
    
    # Status
    is_accrued = models.BooleanField(default=True)
    is_paid = models.BooleanField(default=False)
    paid_date = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'investments_roi_accrual'
        unique_together = ['policy', 'calculation_period']
        indexes = [
            models.Index(fields=['policy', 'accrual_date']),
            models.Index(fields=['is_paid', 'accrual_date']),
        ]

class WithdrawalRequest(models.Model):
    """Withdrawal request and approval workflow"""
    REQUEST_STATUS = [
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('processed', 'Processed'),
        ('cancelled', 'Cancelled'),
    ]
    
    WITHDRAWAL_TYPES = [
        ('roi_only', 'ROI Only'),
        ('principal_only', 'Principal Only'),
        ('composite', 'Composite (Principal + ROI)'),
    ]
    
    tenant = models.ForeignKey('core.Tenant', on_delete=models.CASCADE)
    policy = models.ForeignKey(InvestmentPolicy, on_delete=models.CASCADE, related_name='withdrawal_requests')
    user = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE)
    
    # Request Details
    request_date = models.DateTimeField(default=timezone.now)
    withdrawal_type = models.CharField(max_length=20, choices=WITHDRAWAL_TYPES)
    amount_requested = models.DecimalField(max_digits=20, decimal_places=2)
    
    # Approval Workflow
    status = models.CharField(max_length=20, choices=REQUEST_STATUS, default='pending')
    approved_by = models.ForeignKey('users.CustomUser', on_delete=models.SET_NULL, null=True, related_name='approved_withdrawals')
    approved_date = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    
    # Processing
    processed_date = models.DateTimeField(null=True, blank=True)
    actual_amount = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    
    # Bank Details for Disbursement
    disbursement_bank = models.CharField(max_length=255, blank=True)
    account_name = models.CharField(max_length=255, blank=True)
    account_number = models.CharField(max_length=50, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'investments_withdrawal_request'
        indexes = [
            models.Index(fields=['policy', 'status']),
            models.Index(fields=['user', 'request_date']),
            models.Index(fields=['status', 'request_date']),
        ]


class TaxRecord(models.Model):
    """Comprehensive tax calculation and compliance records"""
    TAX_TYPES = [
        ('wht_dividends', 'WHT - Dividends'),
        ('wht_interest', 'WHT - Interest/ROI'),
        ('wht_rent', 'WHT - Rent'),
        ('wht_commission', 'WHT - Commission'),
        ('wht_professional', 'WHT - Professional Services'),
        ('wht_contracts', 'WHT - Contracts'),
        ('pit', 'Personal Income Tax'),
        ('cgt', 'Capital Gains Tax'),
        ('vat', 'Value Added Tax'),
        ('tet', 'Tertiary Education Tax'),
        ('company_tax', 'Company Income Tax'),
    ]

    STATUS_CHOICES = [
        ('calculated', 'Calculated'),
        ('paid', 'Paid'),
        ('adjusted', 'Adjusted'),
        ('disputed', 'Disputed'),
    ]

    tenant = models.ForeignKey('core.Tenant', on_delete=models.CASCADE)
    user = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE, related_name='tax_records')
    policy = models.ForeignKey(InvestmentPolicy, on_delete=models.CASCADE, null=True, blank=True, related_name='tax_records')

    # Transaction Reference
    transaction = models.ForeignKey(LedgerEntry, on_delete=models.CASCADE, null=True, blank=True, related_name='tax_records')
    withdrawal_request = models.ForeignKey(WithdrawalRequest, on_delete=models.CASCADE, null=True, blank=True, related_name='tax_records')

    # Tax Calculation Details
    tax_type = models.CharField(max_length=30, choices=TAX_TYPES)
    tax_period = models.CharField(max_length=20, help_text="Tax year/period (e.g., 2024, Q1-2024)")  # Tax year or period
    calculation_date = models.DateTimeField(default=timezone.now)

    # Financial Amounts
    gross_amount = models.DecimalField(max_digits=20, decimal_places=2, help_text="Amount before tax")
    tax_rate = models.DecimalField(max_digits=5, decimal_places=4, help_text="Tax rate applied (e.g., 0.1000 for 10%)")
    tax_amount = models.DecimalField(max_digits=20, decimal_places=2, help_text="Calculated tax amount")
    net_amount = models.DecimalField(max_digits=20, decimal_places=2, help_text="Amount after tax")

    # Additional Tax Information
    taxable_income_bracket = models.CharField(max_length=50, blank=True, help_text="PIT bracket (e.g., '₦300,001 - ₦600,000')")
    annual_income_total = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True, help_text="Total annual income for PIT calculations")

    # Status & Compliance
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='calculated')
    payment_date = models.DateTimeField(null=True, blank=True)
    payment_reference = models.CharField(max_length=100, blank=True, help_text="Bank/payment reference for tax payment")

    # Audit Trail
    calculated_by = models.ForeignKey('users.CustomUser', on_delete=models.SET_NULL, null=True, related_name='calculated_taxes')
    approved_by = models.ForeignKey('users.CustomUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_taxes')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    # FIRS Compliance
    firs_reference = models.CharField(max_length=50, blank=True, help_text="FIRS reference number")
    tax_certificate_issued = models.BooleanField(default=False)
    certificate_number = models.CharField(max_length=50, blank=True)

    # Metadata
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'investments_tax_record'
        indexes = [
            models.Index(fields=['tenant', 'tax_type', 'tax_period']),
            models.Index(fields=['user', 'tax_period']),
            models.Index(fields=['policy', 'calculation_date']),
            models.Index(fields=['status', 'calculation_date']),
            models.Index(fields=['tax_type', 'status']),
        ]
        ordering = ['-calculation_date']

    def __str__(self):
        return f"{self.tax_type} - {self.user.email} - ₦{self.tax_amount} ({self.tax_period})"


class TaxCertificate(models.Model):
    """Official tax certificates issued to investors"""
    CERTIFICATE_TYPES = [
        ('wht', 'Withholding Tax Certificate'),
        ('pit', 'Personal Income Tax Certificate'),
        ('annual_summary', 'Annual Tax Summary'),
        ('cgt', 'Capital Gains Tax Certificate'),
    ]

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('issued', 'Issued'),
        ('revoked', 'Revoked'),
        ('reissued', 'Reissued'),
    ]

    tenant = models.ForeignKey('core.Tenant', on_delete=models.CASCADE)
    user = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE, related_name='tax_certificates')

    # Certificate Details
    certificate_number = models.CharField(max_length=50, unique=True)
    certificate_type = models.CharField(max_length=20, choices=CERTIFICATE_TYPES)
    tax_year = models.CharField(max_length=10, help_text="Tax year (e.g., 2024)")
    issue_date = models.DateTimeField(default=timezone.now)
    validity_period_start = models.DateField()
    validity_period_end = models.DateField()

    # Financial Summary
    total_gross_income = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    total_tax_deducted = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    total_tax_paid = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    net_income_after_tax = models.DecimalField(max_digits=20, decimal_places=2, default=0)

    # Tax Breakdown (JSON field for flexible storage)
    tax_breakdown = models.JSONField(default=dict, help_text="Detailed tax breakdown by type")

    # Certificate Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    issued_by = models.ForeignKey('users.CustomUser', on_delete=models.SET_NULL, null=True, related_name='issued_certificates')
    approved_by = models.ForeignKey('users.CustomUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_certificates')

    # Digital Signature & Security
    digital_signature = models.TextField(blank=True, help_text="Digital signature for authenticity")
    qr_code_data = models.TextField(blank=True, help_text="QR code data for verification")

    # FIRS Integration
    firs_submission_date = models.DateTimeField(null=True, blank=True)
    firs_reference = models.CharField(max_length=50, blank=True)

    # Audit Trail
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Related Records
    related_tax_records = models.ManyToManyField(TaxRecord, related_name='certificates', blank=True)

    class Meta:
        db_table = 'investments_tax_certificate'
        indexes = [
            models.Index(fields=['tenant', 'certificate_number']),
            models.Index(fields=['user', 'tax_year']),
            models.Index(fields=['certificate_type', 'status']),
            models.Index(fields=['issue_date']),
        ]
        ordering = ['-issue_date']

    def __str__(self):
        return f"{self.certificate_type} - {self.certificate_number} - {self.user.email}"

    def generate_certificate_number(self):
        """Generate unique certificate number"""
        import uuid
        from datetime import datetime

        year = datetime.now().year
        unique_id = str(uuid.uuid4())[:8].upper()
        self.certificate_number = f"TAX-{year}-{unique_id}"
        return self.certificate_number


class TaxSettings(models.Model):
    """Tenant-specific tax configuration settings"""
    tenant = models.OneToOneField('core.Tenant', on_delete=models.CASCADE, related_name='tax_settings')

    # Tax Rates (can be customized per tenant)
    wht_dividend_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0.1000, help_text="10% default")
    wht_interest_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0.1000, help_text="10% default")
    wht_rent_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0.1000, help_text="10% default")
    wht_commission_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0.0500, help_text="5% default")
    wht_professional_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0.0500, help_text="5% default")
    wht_contract_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0.0250, help_text="2.5% default")

    cgt_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0.1000, help_text="10% default")
    vat_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0.0750, help_text="7.5% default")
    tet_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0.0250, help_text="2.5% default")

    # Company Tax Settings
    small_company_threshold = models.DecimalField(max_digits=20, decimal_places=2, default=25000000.00, help_text="₦25M threshold")
    small_company_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0.2000, help_text="20% rate")
    standard_company_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0.3000, help_text="30% rate")

    # Compliance Settings
    auto_calculate_taxes = models.BooleanField(default=True)
    require_tax_certificates = models.BooleanField(default=True)
    firs_integration_enabled = models.BooleanField(default=False)
    tax_year_start_month = models.PositiveIntegerField(default=1, help_text="1=January, 4=April, etc.")

    # Notification Settings
    notify_tax_calculations = models.BooleanField(default=True)
    notify_certificate_issuance = models.BooleanField(default=True)
    tax_reminder_days = models.PositiveIntegerField(default=30, help_text="Days before tax deadline to send reminders")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'investments_tax_settings'

    def __str__(self):
        return f"Tax Settings - {self.tenant.name}"