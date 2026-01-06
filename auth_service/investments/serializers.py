# investments/serializers.py
from rest_framework import serializers
from .models import InvestmentPolicy, LedgerEntry, WithdrawalRequest, ROIAccrual, TaxRecord, TaxCertificate, TaxSettings
from users.models import CustomUser, UserProfile
from users.serializers import InvestmentDetailSerializer, WithdrawalDetailSerializer

class InvestmentUserSerializer(serializers.ModelSerializer):
    """Minimal user serializer for investment policies"""
    bank_name = serializers.CharField(source='profile.bank_name', read_only=True)
    account_number = serializers.CharField(source='profile.account_number', read_only=True)
    account_name = serializers.CharField(source='profile.account_name', read_only=True)
    account_type = serializers.CharField(source='profile.account_type', read_only=True)
    country_of_bank_account = serializers.CharField(source='profile.country_of_bank_account', read_only=True)
    investment_details = InvestmentDetailSerializer(source='profile.investment_details', many=True, read_only=True)
    withdrawal_details = WithdrawalDetailSerializer(source='profile.withdrawal_details', many=True, read_only=True)

    class Meta:
        model = CustomUser
        fields = ['id', 'email', 'first_name', 'last_name', 'role', 'bank_name', 'account_number', 'account_name', 'account_type', 'country_of_bank_account', 'investment_details', 'withdrawal_details']

# investments/serializers.py
class InvestmentPolicySerializer(serializers.ModelSerializer):
    user_details = InvestmentUserSerializer(source='user', read_only=True)

    def validate(self, data):
        """Ensure data belongs to current tenant"""
        request = self.context.get('request')
        if request and hasattr(request, 'tenant'):
            # ✅ Ensure created objects belong to current tenant
            data['tenant'] = request.tenant
        
        return super().validate(data)
    
    def create(self, validated_data):
        """Auto-assign tenant, user, and profile on creation if not provided. Set current_balance = principal_amount if not provided."""
        request = self.context.get('request')

        # Auto-assign tenant
        if request and hasattr(request, 'tenant'):
            validated_data['tenant'] = request.tenant

        # Assign user: use provided user or default to request user
        if 'user' not in validated_data:
            if request and hasattr(request, 'user'):
                validated_data['user'] = request.user

        # Assign profile based on the assigned user
        if 'profile' not in validated_data:
            assigned_user = validated_data.get('user')
            if assigned_user and hasattr(assigned_user, 'profile'):
                validated_data['profile'] = assigned_user.profile

        # Set current_balance = principal_amount if not provided
        if 'current_balance' not in validated_data or validated_data.get('current_balance') in (None, ''):
            principal = validated_data.get('principal_amount')
            if principal is not None:
                validated_data['current_balance'] = principal

        # Generate policy_number if not provided
        tenant = validated_data.get('tenant')
        if 'policy_number' not in validated_data and tenant:
            # Generate policy number: PREFIX-XXXXXX where PREFIX is first 3 letters of tenant name (upper), XXXXXX is 6-digit sequential per tenant
            prefix = tenant.name[:3].upper()
            count = InvestmentPolicy.objects.filter(tenant=tenant).count() + 1  # +1 for the new one
            validated_data['policy_number'] = f"{prefix}-{count:06d}"

        # Generate unique_policy_id if not provided
        if 'unique_policy_id' not in validated_data and tenant:
            # Generate unique policy id (6-digit logical sequence per tenant)
            from django.db.models import Max
            max_unique = InvestmentPolicy.objects.filter(tenant=tenant).aggregate(Max('unique_policy_id'))['unique_policy_id__max'] or 0
            validated_data['unique_policy_id'] = str(int(max_unique) + 1).zfill(6) if max_unique else '000001'

        return super().create(validated_data)

    class Meta:
        model = InvestmentPolicy
        fields = [
            'id', 'user', 'user_details', 'policy_number', 'unique_policy_id', 'principal_amount', 'roi_rate',
            'roi_frequency', 'min_withdrawal_months', 'allow_partial_withdrawals','current_balance', 'roi_balance',
                'next_roi_date', 'auto_rollover', 'rollover_option', 'status', 'maturity_date', 'start_date', 'roi_due'
        ]
        read_only_fields = ['id', 'policy_number', 'unique_policy_id', 'status', 'user_details']
        extra_kwargs = {
            'user': {'required': False},
            'profile': {'required': False},
        }


class LedgerEntrySerializer(serializers.ModelSerializer):
    investor_name = serializers.CharField(source='policy.user.get_full_name', read_only=True)
    policy_number = serializers.CharField(source='policy.policy_number', read_only=True)
    
    class Meta:
        model = LedgerEntry
        fields = [
            'id', 'entry_date', 'unique_reference', 'policy_number', 'investor_name',
            'description', 'entry_type', 'inflow', 'outflow', 
            'principal_balance', 'roi_balance', 'total_balance'
        ]
        read_only_fields = fields

class WithdrawalRequestSerializer(serializers.ModelSerializer):
    investor_name = serializers.CharField(source='user.get_full_name', read_only=True)
    policy_number = serializers.CharField(source='policy.policy_number', read_only=True)
    available_balances = serializers.SerializerMethodField()
    
    class Meta:
        model = WithdrawalRequest
        fields = [
            'id', 'policy', 'policy_number', 'investor_name', 'request_date',
            'withdrawal_type', 'amount_requested', 'status', 'approved_by',
            'approved_date', 'processed_date', 'actual_amount', 'available_balances',
            'disbursement_bank', 'account_name', 'account_number', 'rejection_reason'
        ]
        read_only_fields = ['status', 'approved_by', 'approved_date', 'processed_date']
    
    def get_available_balances(self, obj):
        if obj.policy:
            from .services.withdrawal_validator import WithdrawalValidator
            return WithdrawalValidator.get_available_balances(obj.policy)
        return {}
    
    def validate(self, data):
        from .services.withdrawal_validator import WithdrawalValidator
        
        policy = data.get('policy') or self.instance.policy if self.instance else None
        withdrawal_type = data.get('withdrawal_type')
        amount_requested = data.get('amount_requested')
        
        if policy and withdrawal_type and amount_requested:
            if withdrawal_type == 'roi_only':
                WithdrawalValidator.validate_roi_withdrawal(policy, amount_requested)
            elif withdrawal_type == 'principal_only':
                WithdrawalValidator.validate_principal_withdrawal(policy, amount_requested)
        
        return data

    def create(self, validated_data):
        """Auto-fill bank details from user profile if not provided"""
        user = validated_data.get('user') or self.context['request'].user
        policy = validated_data.get('policy')
        
        # Auto-fill bank details from profile if not provided
        if not validated_data.get('disbursement_bank') and hasattr(user, 'profile'):
            profile = user.profile
            validated_data['disbursement_bank'] = profile.bank_name or ''
            validated_data['account_name'] = profile.account_name or ''
            validated_data['account_number'] = profile.account_number or ''
        
        return super().create(validated_data)
    


class LedgerFilterSerializer(serializers.Serializer):
    """
    Serializer for ledger filtering parameters
    """
    policy_number = serializers.CharField(required=False, help_text="Filter by policy number")
    investor_name = serializers.CharField(required=False, help_text="Filter by investor name")
    entry_type = serializers.ChoiceField(
        choices=LedgerEntry.ENTRY_TYPES, 
        required=False, 
        help_text="Filter by entry type"
    )
    date_from = serializers.DateTimeField(required=False, help_text="Start date for filtering")
    date_to = serializers.DateTimeField(required=False, help_text="End date for filtering")
    policy_id = serializers.IntegerField(required=False, help_text="Filter by specific policy ID")


class TaxRecordSerializer(serializers.ModelSerializer):
    """Serializer for tax records"""
    calculated_by_name = serializers.CharField(source='calculated_by.get_full_name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True)
    policy_number = serializers.CharField(source='policy.policy_number', read_only=True)
    transaction_reference = serializers.CharField(source='transaction.unique_reference', read_only=True)

    class Meta:
        model = TaxRecord
        fields = [
            'id', 'tax_type', 'tax_period', 'calculation_date', 'gross_amount',
            'tax_rate', 'tax_amount', 'net_amount', 'taxable_income_bracket',
            'annual_income_total', 'status', 'payment_date', 'payment_reference',
            'firs_reference', 'tax_certificate_issued', 'certificate_number',
            'notes', 'calculated_by_name', 'approved_by_name', 'policy_number',
            'transaction_reference', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class TaxCertificateSerializer(serializers.ModelSerializer):
    """Serializer for tax certificates"""
    issued_by_name = serializers.CharField(source='issued_by.get_full_name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True)

    class Meta:
        model = TaxCertificate
        fields = [
            'id', 'certificate_number', 'certificate_type', 'tax_year',
            'issue_date', 'validity_period_start', 'validity_period_end',
            'total_gross_income', 'total_tax_deducted', 'total_tax_paid',
            'net_income_after_tax', 'tax_breakdown', 'status',
            'issued_by_name', 'approved_by_name', 'firs_submission_date',
            'firs_reference', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'certificate_number', 'created_at', 'updated_at']


class TaxSettingsSerializer(serializers.ModelSerializer):
    """Serializer for tax settings"""

    class Meta:
        model = TaxSettings
        fields = [
            'id', 'wht_dividend_rate', 'wht_interest_rate', 'wht_rent_rate',
            'wht_commission_rate', 'wht_professional_rate', 'wht_contract_rate',
            'cgt_rate', 'vat_rate', 'tet_rate', 'small_company_threshold',
            'small_company_rate', 'standard_company_rate', 'auto_calculate_taxes',
            'require_tax_certificates', 'firs_integration_enabled',
            'tax_year_start_month', 'notify_tax_calculations',
            'notify_certificate_issuance', 'tax_reminder_days',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class TaxCalculationSerializer(serializers.Serializer):
    """Serializer for tax calculation requests"""
    amount = serializers.DecimalField(max_digits=20, decimal_places=2, help_text="Amount to calculate tax on")
    tax_type = serializers.ChoiceField(
        choices=TaxRecord.TAX_TYPES,
        help_text="Type of tax to calculate"
    )
    annual_income = serializers.DecimalField(
        max_digits=20,
        decimal_places=2,
        required=False,
        help_text="Annual income for PIT calculations"
    )
    include_breakdown = serializers.BooleanField(
        default=True,
        help_text="Include detailed tax breakdown"
    )


class TaxSummarySerializer(serializers.Serializer):
    """Serializer for tax summary responses"""
    tax_year = serializers.CharField()
    total_gross_income = serializers.DecimalField(max_digits=20, decimal_places=2)
    total_tax_deducted = serializers.DecimalField(max_digits=20, decimal_places=2)
    total_tax_paid = serializers.DecimalField(max_digits=20, decimal_places=2)
    net_income_after_tax = serializers.DecimalField(max_digits=20, decimal_places=2)
    tax_breakdown = serializers.DictField()
    records = serializers.ListField()


class TaxCertificateRequestSerializer(serializers.Serializer):
    """Serializer for tax certificate generation requests"""
    certificate_type = serializers.ChoiceField(choices=TaxCertificate.CERTIFICATE_TYPES)
    tax_year = serializers.CharField(help_text="Tax year (e.g., 2024)")
    include_related_records = serializers.BooleanField(default=True)
    
