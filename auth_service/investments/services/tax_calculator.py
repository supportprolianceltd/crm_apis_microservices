# investments/services/tax_calculator.py
"""
Nigerian Tax Calculator Service
Implements comprehensive tax calculations for investment management system
"""

from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from django.db import transaction
from ..models import TaxRecord, TaxSettings, InvestmentPolicy, LedgerEntry, WithdrawalRequest


class NigerianTaxCalculator:
    """
    Comprehensive Nigerian tax calculator implementing all major tax types
    """

    # Withholding Tax Rates (as per Nigerian tax law)
    WHT_RATES = {
        'wht_dividends': Decimal('0.1000'),      # 10% on dividends
        'wht_interest': Decimal('0.1000'),       # 10% on interest/ROI
        'wht_rent': Decimal('0.1000'),           # 10% on rent
        'wht_commission': Decimal('0.0500'),     # 5% on commission
        'wht_professional': Decimal('0.0500'),   # 5% on professional services
        'wht_contracts': Decimal('0.0250'),      # 2.5% on contracts
    }

    # Personal Income Tax (PIT) brackets for individuals (2024 rates)
    PIT_BRACKETS = [
        {'min': Decimal('0'), 'max': Decimal('300000'), 'rate': Decimal('0.07')},           # 7%
        {'min': Decimal('300001'), 'max': Decimal('600000'), 'rate': Decimal('0.11')},      # 11%
        {'min': Decimal('600001'), 'max': Decimal('1100000'), 'rate': Decimal('0.15')},     # 15%
        {'min': Decimal('1100001'), 'max': Decimal('1600000'), 'rate': Decimal('0.19')},    # 19%
        {'min': Decimal('1600001'), 'max': Decimal('3200000'), 'rate': Decimal('0.21')},    # 21%
        {'min': Decimal('3200001'), 'max': None, 'rate': Decimal('0.24')},                  # 24%
    ]

    # Other Tax Rates
    CGT_RATE = Decimal('0.1000')        # 10% Capital Gains Tax
    VAT_RATE = Decimal('0.0750')        # 7.5% Value Added Tax
    TET_RATE = Decimal('0.0250')        # 2.5% Tertiary Education Tax

    @classmethod
    def get_tenant_tax_settings(cls, tenant):
        """Get tax settings for a tenant, creating defaults if not exist"""
        settings, created = TaxSettings.objects.get_or_create(
            tenant=tenant,
            defaults={
                'wht_dividend_rate': cls.WHT_RATES['wht_dividends'],
                'wht_interest_rate': cls.WHT_RATES['wht_interest'],
                'wht_rent_rate': cls.WHT_RATES['wht_rent'],
                'wht_commission_rate': cls.WHT_RATES['wht_commission'],
                'wht_professional_rate': cls.WHT_RATES['wht_professional'],
                'wht_contract_rate': cls.WHT_RATES['wht_contracts'],
                'cgt_rate': cls.CGT_RATE,
                'vat_rate': cls.VAT_RATE,
                'tet_rate': cls.TET_RATE,
            }
        )
        return settings

    @classmethod
    def calculate_wht(cls, amount, tax_type, tenant=None):
        """
        Calculate Withholding Tax for different types of income

        Args:
            amount (Decimal): Gross amount
            tax_type (str): Type of WHT (e.g., 'wht_interest', 'wht_dividends')
            tenant: Tenant instance for custom rates

        Returns:
            dict: Tax calculation details
        """
        if tenant:
            settings = cls.get_tenant_tax_settings(tenant)
            rate = getattr(settings, f"{tax_type}_rate", cls.WHT_RATES.get(tax_type, Decimal('0')))
        else:
            rate = cls.WHT_RATES.get(tax_type, Decimal('0'))

        tax_amount = (amount * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        net_amount = amount - tax_amount

        return {
            'gross_amount': amount,
            'tax_rate': rate,
            'tax_amount': tax_amount,
            'net_amount': net_amount,
            'tax_type': tax_type
        }

    @classmethod
    def calculate_pit(cls, annual_income):
        """
        Calculate Personal Income Tax using progressive brackets

        Args:
            annual_income (Decimal): Total annual taxable income

        Returns:
            dict: PIT calculation with breakdown
        """
        remaining_income = annual_income
        total_tax = Decimal('0')
        breakdown = []

        for bracket in cls.PIT_BRACKETS:
            if remaining_income <= 0:
                break

            if bracket['max'] is None:
                # Last bracket (no upper limit)
                taxable_amount = remaining_income
            else:
                taxable_amount = min(remaining_income, bracket['max'] - bracket['min'] + 1)

            tax_amount = (taxable_amount * bracket['rate']).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            if tax_amount > 0:
                breakdown.append({
                    'bracket_min': bracket['min'],
                    'bracket_max': bracket['max'],
                    'rate': bracket['rate'],
                    'taxable_amount': taxable_amount,
                    'tax_amount': tax_amount,
                    'bracket_range': cls._format_bracket_range(bracket['min'], bracket['max'])
                })

            total_tax += tax_amount
            remaining_income -= taxable_amount

        effective_rate = (total_tax / annual_income * 100).quantize(Decimal('0.01')) if annual_income > 0 else Decimal('0')

        return {
            'annual_income': annual_income,
            'total_tax': total_tax,
            'effective_rate': effective_rate,
            'breakdown': breakdown
        }

    @classmethod
    def calculate_cgt(cls, capital_gain, tenant=None):
        """
        Calculate Capital Gains Tax

        Args:
            capital_gain (Decimal): Net capital gain
            tenant: Tenant instance for custom rates

        Returns:
            dict: CGT calculation
        """
        if tenant:
            settings = cls.get_tenant_tax_settings(tenant)
            rate = settings.cgt_rate
        else:
            rate = cls.CGT_RATE

        tax_amount = (capital_gain * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        net_amount = capital_gain - tax_amount

        return {
            'capital_gain': capital_gain,
            'tax_rate': rate,
            'tax_amount': tax_amount,
            'net_amount': net_amount
        }

    @classmethod
    def calculate_vat(cls, amount, tenant=None):
        """
        Calculate Value Added Tax

        Args:
            amount (Decimal): Amount before VAT
            tenant: Tenant instance for custom rates

        Returns:
            dict: VAT calculation
        """
        if tenant:
            settings = cls.get_tenant_tax_settings(tenant)
            rate = settings.vat_rate
        else:
            rate = cls.VAT_RATE

        tax_amount = (amount * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        total_amount = amount + tax_amount

        return {
            'amount': amount,
            'tax_rate': rate,
            'tax_amount': tax_amount,
            'total_amount': total_amount
        }

    @classmethod
    def calculate_investment_taxes(cls, amount, annual_income=None, tenant=None):
        """
        Calculate comprehensive taxes for investment income (ROI payments)

        Args:
            amount (Decimal): ROI payment amount
            annual_income (Decimal): Investor's total annual income
            tenant: Tenant instance

        Returns:
            dict: Complete tax breakdown
        """
        # WHT on ROI (treated as interest)
        wht = cls.calculate_wht(amount, 'wht_interest', tenant)

        # PIT calculation if annual income provided
        pit = None
        if annual_income is not None:
            # Add the net ROI to annual income for PIT calculation
            total_annual_income = annual_income + wht['net_amount']
            pit = cls.calculate_pit(total_annual_income)

        # Total tax burden
        total_tax = wht['tax_amount']
        if pit:
            total_tax += pit['total_tax']

        net_after_tax = amount - total_tax
        effective_rate = (total_tax / amount * 100).quantize(Decimal('0.01')) if amount > 0 else Decimal('0')

        return {
            'gross_amount': amount,
            'wht': wht,
            'pit': pit,
            'total_tax': total_tax,
            'net_after_tax': net_after_tax,
            'effective_tax_rate': effective_rate
        }

    @classmethod
    def calculate_company_tax(cls, taxable_profit, turnover, tenant=None):
        """
        Calculate Company Income Tax

        Args:
            taxable_profit (Decimal): Company's taxable profit
            turnover (Decimal): Company turnover
            tenant: Tenant instance

        Returns:
            dict: Company tax calculation
        """
        if tenant:
            settings = cls.get_tenant_tax_settings(tenant)
            threshold = settings.small_company_threshold
            small_rate = settings.small_company_rate
            standard_rate = settings.standard_company_rate
        else:
            threshold = Decimal('25000000')  # ₦25M
            small_rate = Decimal('0.20')     # 20%
            standard_rate = Decimal('0.30')  # 30%

        is_small_company = turnover <= threshold
        rate = small_rate if is_small_company else standard_rate
        tax_amount = (taxable_profit * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        return {
            'taxable_profit': taxable_profit,
            'turnover': turnover,
            'is_small_company': is_small_company,
            'tax_rate': rate,
            'tax_amount': tax_amount,
            'rate_type': 'Small Company (20%)' if is_small_company else 'Standard (30%)'
        }

    @classmethod
    def calculate_tet(cls, assessable_profit, tenant=None):
        """
        Calculate Tertiary Education Tax

        Args:
            assessable_profit (Decimal): Company's assessable profit
            tenant: Tenant instance

        Returns:
            dict: TET calculation
        """
        if tenant:
            settings = cls.get_tenant_tax_settings(tenant)
            rate = settings.tet_rate
        else:
            rate = cls.TET_RATE

        tax_amount = (assessable_profit * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        return {
            'assessable_profit': assessable_profit,
            'tax_rate': rate,
            'tax_amount': tax_amount
        }

    @classmethod
    @transaction.atomic
    def record_tax_calculation(cls, tenant, user, tax_type, calculation_data,
                             transaction=None, withdrawal_request=None, policy=None,
                             calculated_by=None, ip_address=None, user_agent=None):
        """
        Record a tax calculation in the database for audit and compliance

        Args:
            tenant: Tenant instance
            user: User instance
            tax_type (str): Type of tax calculated
            calculation_data (dict): Tax calculation results
            transaction: Related LedgerEntry (optional)
            withdrawal_request: Related WithdrawalRequest (optional)
            policy: Related InvestmentPolicy (optional)
            calculated_by: User who performed calculation
            ip_address: IP address for audit
            user_agent: User agent for audit

        Returns:
            TaxRecord: Created tax record
        """
        # Determine tax period (current year)
        current_year = str(timezone.now().year)

        # Extract bracket info for PIT
        taxable_income_bracket = ''
        annual_income_total = None

        if tax_type == 'pit' and 'breakdown' in calculation_data:
            # Find the highest bracket used
            if calculation_data['breakdown']:
                last_bracket = calculation_data['breakdown'][-1]
                taxable_income_bracket = last_bracket.get('bracket_range', '')
                annual_income_total = calculation_data.get('annual_income')

        tax_record = TaxRecord.objects.create(
            tenant=tenant,
            user=user,
            policy=policy,
            transaction=transaction,
            withdrawal_request=withdrawal_request,
            tax_type=tax_type,
            tax_period=current_year,
            gross_amount=calculation_data.get('gross_amount', calculation_data.get('annual_income', 0)),
            tax_rate=calculation_data.get('tax_rate', calculation_data.get('effective_rate', 0)),
            tax_amount=calculation_data.get('tax_amount', calculation_data.get('total_tax', 0)),
            net_amount=calculation_data.get('net_amount', calculation_data.get('net_after_tax', 0)),
            taxable_income_bracket=taxable_income_bracket,
            annual_income_total=annual_income_total,
            calculated_by=calculated_by,
            ip_address=ip_address,
            user_agent=user_agent or '',
        )

        return tax_record

    @classmethod
    def get_tax_summary(cls, user, tax_year=None):
        """
        Get tax summary for a user for a specific tax year

        Args:
            user: User instance
            tax_year (str): Tax year (defaults to current year)

        Returns:
            dict: Tax summary
        """
        if not tax_year:
            tax_year = str(timezone.now().year)

        tax_records = TaxRecord.objects.filter(
            user=user,
            tax_period=tax_year
        )

        summary = {
            'tax_year': tax_year,
            'total_gross_income': Decimal('0'),
            'total_tax_deducted': Decimal('0'),
            'total_tax_paid': Decimal('0'),
            'tax_breakdown': {},
            'records': []
        }

        for record in tax_records:
            summary['total_gross_income'] += record.gross_amount
            summary['total_tax_deducted'] += record.tax_amount

            if record.tax_type not in summary['tax_breakdown']:
                summary['tax_breakdown'][record.tax_type] = {
                    'count': 0,
                    'total_amount': Decimal('0'),
                    'total_tax': Decimal('0')
                }

            summary['tax_breakdown'][record.tax_type]['count'] += 1
            summary['tax_breakdown'][record.tax_type]['total_amount'] += record.gross_amount
            summary['tax_breakdown'][record.tax_type]['total_tax'] += record.tax_amount

            summary['records'].append({
                'id': record.id,
                'tax_type': record.tax_type,
                'gross_amount': record.gross_amount,
                'tax_amount': record.tax_amount,
                'calculation_date': record.calculation_date,
                'status': record.status
            })

        summary['net_income_after_tax'] = summary['total_gross_income'] - summary['total_tax_deducted']

        return summary

    @classmethod
    def _format_bracket_range(cls, min_val, max_val):
        """Format tax bracket range for display"""
        if max_val is None:
            return f"₦{min_val:,.0f} and above"
        return f"₦{min_val:,.0f} - ₦{max_val:,.0f}"

    @classmethod
    def validate_tax_calculation(cls, expected_result, actual_result, tolerance=Decimal('0.01')):
        """
        Validate tax calculation results for testing

        Args:
            expected_result (dict): Expected calculation
            actual_result (dict): Actual calculation
            tolerance (Decimal): Acceptable difference

        Returns:
            bool: Whether calculation is valid
        """
        if 'tax_amount' in expected_result and 'tax_amount' in actual_result:
            diff = abs(expected_result['tax_amount'] - actual_result['tax_amount'])
            return diff <= tolerance

        return False