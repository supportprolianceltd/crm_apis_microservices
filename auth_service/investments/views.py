# investments/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Sum
from django.db import transaction
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
from rest_framework.views import APIView
# investments/views.py (ensure these imports are present)

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Sum, Count
from django.utils import timezone
from datetime import timedelta
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from .models import InvestmentPolicy, LedgerEntry, WithdrawalRequest, ROIAccrual, TaxRecord, TaxCertificate, TaxSettings
from .serializers import *
from .models import InvestmentPolicy, LedgerEntry, WithdrawalRequest
from .serializers import *
from .services.roi_calculator import ROICalculator
from .services.withdrawal_validator import WithdrawalValidator
from .services.tax_calculator import NigerianTaxCalculator
from django.conf import settings
from django.contrib.auth import get_user_model
# investments/views.py (add this to the existing views)
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, IsAdminUser


class CustomPagination(PageNumberPagination):
    page_size = 20  # Adjust as needed

    def get_next_link(self):
        """Override to use gateway base URL."""
        if not self.page.has_next():
            return None
        gateway_url = getattr(settings, 'GATEWAY_URL', None)
        if not gateway_url:
            return super().get_next_link()  # Fallback to default

        request = self.request
        # Build base path from current request (e.g., /api/user/users/)
        path = request.path
        # Get query params, update 'page', preserve others
        query_params = request.query_params.copy()
        query_params['page'] = self.page.next_page_number()
        query_string = urlencode(query_params, doseq=True)

        # Reconstruct full URL with gateway scheme/host
        parsed_gateway = urlparse(gateway_url)
        full_url = f"{parsed_gateway.scheme}://{parsed_gateway.netloc}{path}?{query_string}"
        return full_url

    def get_previous_link(self):
        """Override to use gateway base URL."""
        if not self.page.has_previous():
            return None
        gateway_url = getattr(settings, 'GATEWAY_URL', None)
        if not gateway_url:
            return super().get_previous_link()  # Fallback to default

        request = self.request
        path = request.path
        query_params = request.query_params.copy()
        query_params['page'] = self.page.previous_page_number()
        query_string = urlencode(query_params, doseq=True)

        parsed_gateway = urlparse(gateway_url)
        full_url = f"{parsed_gateway.scheme}://{parsed_gateway.netloc}{path}?{query_string}"
        return full_url

    def get_paginated_response(self, data):
        """Ensure the full response uses overridden links."""
        response = super().get_paginated_response(data)
        gateway_url = getattr(settings, 'GATEWAY_URL', None)
        if gateway_url:
            response['next'] = self.get_next_link()
            response['previous'] = self.get_previous_link()
        return response



class ROIAccrualView(APIView):
    """
    API endpoint for manual ROI accrual (admin only)
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def post(self, request):
        """
        Manually trigger ROI accrual for all eligible policies
        """
        from .services.roi_calculator import ROICalculator
        
        try:
            results = ROICalculator.process_monthly_roi_accruals()
            
            return Response({
                'message': 'ROI accrual processed successfully',
                'results': results,
                'timestamp': timezone.now().isoformat()
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'error': f'ROI accrual failed: {str(e)}',
                'timestamp': timezone.now().isoformat()
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def get(self, request):
        """
        Get ROI accrual status and upcoming calculations
        """
        from .models import InvestmentPolicy
        
        tenant = request.user.tenant
        
        # Get policies due for ROI accrual
        due_policies = InvestmentPolicy.objects.filter(
            tenant=tenant,
            status='active',
            next_roi_date__lte=timezone.now() + timedelta(days=7)
        ).select_related('user')
        
        due_summary = due_policies.aggregate(
            total_policies=Count('id'),
            total_principal=Sum('current_balance'),
            estimated_roi=Sum('current_balance') * 0.40 / 12  # 40% annual / 12 months
        )
        
        # Recent ROI accruals
        recent_accruals = ROIAccrual.objects.filter(
            tenant=tenant,
            accrual_date__gte=timezone.now() - timedelta(days=30)
        ).select_related('policy', 'policy__user').order_by('-accrual_date')[:10]
        
        recent_data = [
            {
                'policy_number': accrual.policy.policy_number,
                'investor_name': accrual.policy.user.get_full_name(),
                'accrual_date': accrual.accrual_date,
                'roi_amount': accrual.roi_amount,
                'principal': accrual.principal_for_calculation
            }
            for accrual in recent_accruals
        ]
        
        return Response({
            'upcoming_accruals': {
                'due_count': due_policies.count(),
                'total_principal': due_summary['total_principal'] or 0,
                'estimated_monthly_roi': due_summary['estimated_roi'] or 0,
                'policies': [
                    {
                        'policy_number': policy.policy_number,
                        'investor_name': policy.user.get_full_name(),
                        'current_balance': policy.current_balance,
                        'next_roi_date': policy.next_roi_date,
                        'estimated_roi': policy.current_balance * 0.40 / 12
                    }
                    for policy in due_policies
                ]
            },
            'recent_accruals': recent_data
        })
        
        
class InvestmentPolicyViewSet(viewsets.ModelViewSet):
    serializer_class = InvestmentPolicySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination
    
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'roi_frequency']
    
    def get_queryset(self):
        tenant = self.request.user.tenant
        user = self.request.user

        # Admins see all policies, investors see only their own
        if user.role in ['root-admin', 'co-admin', 'admin', 'staff']:
            return InvestmentPolicy.objects.filter(tenant=tenant).select_related('user', 'profile')
        else:
            return InvestmentPolicy.objects.filter(tenant=tenant, user=user).select_related('user', 'profile')
    
    @action(detail=True, methods=['post'])
    def change_roi_frequency(self, request, pk=None):
        """Change ROI frequency between monthly and on-demand"""
        policy = self.get_object()
        new_frequency = request.data.get('roi_frequency')
        
        if new_frequency not in ['monthly', 'on_demand']:
            return Response(
                {'error': 'Invalid ROI frequency'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        policy.roi_frequency = new_frequency
        policy.save()
        
        return Response({'message': f'ROI frequency updated to {new_frequency}'})
    
    @action(detail=False, methods=['get'])
    def search(self, request):
        """Search policies by name or policy number"""
        query = request.query_params.get('q', '')

        if not query:
            return Response({'error': 'Search query required'}, status=400)

        policies = self.get_queryset().filter(
            Q(policy_number__icontains=query) |
            Q(unique_policy_id__icontains=query) |
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(user__email__icontains=query)
        )

        serializer = self.get_serializer(policies, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def add_topup(self, request, pk=None):
        """Add top-up to an investment policy"""
        policy = self.get_object()
        amount = Decimal(request.data.get('amount', 0))
        top_up_date = timezone.now()

        if amount <= 0:
            return Response({'error': 'Invalid amount'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            # Update policy balance
            policy.current_balance += amount
            policy.principal_amount += amount
            policy.save()

            # Apply date-based ROI rules
            if top_up_date.day >= 13:
                # ROI starts next month
                description = f"Top-up (ROI from next month) - {amount}"
            else:
                # ROI includes current month
                description = f"Top-up (ROI from current month) - {amount}"

            # Create ledger entry
            LedgerEntry.objects.create(
                tenant=policy.tenant,
                policy=policy,
                entry_date=top_up_date,
                unique_reference=f"TOPUP-{policy.policy_number}-{top_up_date.strftime('%Y%m%d%H%M%S')}",
                description=description,
                entry_type='top_up',
                inflow=amount,
                outflow=0,
                principal_balance=policy.current_balance,
                roi_balance=policy.roi_balance,
                total_balance=policy.current_balance + policy.roi_balance,
                created_by=request.user
            )

        return Response({
            'message': 'Top-up added successfully',
            'new_balance': policy.current_balance
        })

    @action(detail=False, methods=['get'])
    def by_investor(self, request):
        """Get all investment policies for a specific investor by ID or email"""
        investor_id = request.query_params.get('investor_id')
        investor_email = request.query_params.get('investor_email')

        if not investor_id and not investor_email:
            return Response(
                {'error': 'Either investor_id or investor_email parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Build query to find the investor
        investor_query = Q()
        if investor_id:
            try:
                investor_query &= Q(id=investor_id)
            except ValueError:
                return Response(
                    {'error': 'Invalid investor_id format'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        if investor_email:
            investor_query &= Q(email=investor_email)

        # Get the investor
        User = get_user_model()
        try:
            investor = User.objects.get(investor_query)
        except User.DoesNotExist:
            return Response(
                {'error': 'Investor not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except User.MultipleObjectsReturned:
            return Response(
                {'error': 'Multiple investors found with the given criteria'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get all policies for this investor
        policies = self.get_queryset().filter(user=investor)

        # Add investor info to response
        serializer = self.get_serializer(policies, many=True)

        return Response({
            'investor': {
                'id': investor.id,
                'name': investor.get_full_name(),
                'email': investor.email,
                'phone_number': getattr(investor, 'phone_number', None)
            },
            'policies_count': policies.count(),
            'policies': serializer.data
        })


class WithdrawalRequestViewSet(viewsets.ModelViewSet):
    serializer_class = WithdrawalRequestSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'withdrawal_type']
    
    def get_queryset(self):
        tenant = self.request.user.tenant
        user = self.request.user
        
        if user.role in ['admin', 'staff']:
            return WithdrawalRequest.objects.filter(tenant=tenant).select_related('policy', 'user')
        else:
            return WithdrawalRequest.objects.filter(tenant=tenant, user=user).select_related('policy', 'user')
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve withdrawal request (admin only)"""
        if request.user.role not in ['admin', 'staff']:
            return Response(
                {'error': 'Only admins can approve withdrawals'},
                status=status.HTTP_403_FORBIDDEN
            )

        withdrawal = self.get_object()
        withdrawal.status = 'approved'
        withdrawal.approved_by = request.user
        withdrawal.approved_date = timezone.now()
        withdrawal.save()

        return Response({'message': 'Withdrawal approved'})
    
    @action(detail=True, methods=['post'])
    def process(self, request, pk=None):
        from .services.tax_calculator import NigerianTaxCalculator

        withdrawal = self.get_object()

        if withdrawal.status != 'approved':
            return Response({'error': 'Only approved withdrawals can be processed'},
                         status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            policy = withdrawal.policy
            tenant = policy.tenant

            # Calculate tax for ROI withdrawals (10% WHT)
            tax_amount = Decimal('0')
            if withdrawal.withdrawal_type in ['roi_only', 'composite']:
                # For ROI withdrawals, calculate 10% WHT
                roi_amount = withdrawal.amount_requested
                if withdrawal.withdrawal_type == 'composite':
                    # For composite, assume the ROI portion is specified or calculate proportionally
                    roi_portion = getattr(withdrawal, 'roi_amount', withdrawal.amount_requested * Decimal('0.5'))
                    roi_amount = roi_portion

                tax_calculation = NigerianTaxCalculator.calculate_wht(roi_amount, 'wht_interest', tenant)
                tax_amount = tax_calculation['tax_amount']

                # Record tax calculation
                NigerianTaxCalculator.record_tax_calculation(
                    tenant=tenant,
                    user=withdrawal.user,
                    tax_type='wht_interest',
                    calculation_data=tax_calculation,
                    withdrawal_request=withdrawal,
                    policy=policy,
                    calculated_by=request.user,
                    ip_address=request.META.get('REMOTE_ADDR'),
                    user_agent=request.META.get('HTTP_USER_AGENT')
                )

            # Update balances based on withdrawal type
            if withdrawal.withdrawal_type == 'roi_only':
                policy.roi_balance -= withdrawal.amount_requested
            elif withdrawal.withdrawal_type == 'principal_only':
                policy.current_balance -= withdrawal.amount_requested
            elif withdrawal.withdrawal_type == 'composite':
                # Use the amounts specified in the withdrawal request
                principal_amount = getattr(withdrawal, 'principal_amount', withdrawal.amount_requested * Decimal('0.5'))
                roi_amount = getattr(withdrawal, 'roi_amount', withdrawal.amount_requested * Decimal('0.5'))
                policy.current_balance -= principal_amount
                policy.roi_balance -= roi_amount

            policy.total_withdrawn += withdrawal.amount_requested
            policy.save()

            # Create ledger entry
            LedgerEntry.objects.create(
                tenant=policy.tenant,
                policy=policy,
                entry_date=timezone.now(),
                unique_reference=f"WD-{policy.policy_number}-{timezone.now().strftime('%Y%m%d%H%M%S')}",
                description=f"Withdrawal - {withdrawal.get_withdrawal_type_display()}",
                entry_type=f'withdrawal_{withdrawal.withdrawal_type.split("_")[0]}',
                inflow=0,
                outflow=withdrawal.amount_requested,
                principal_balance=policy.current_balance,
                roi_balance=policy.roi_balance,
                total_balance=policy.current_balance + policy.roi_balance,
                created_by=request.user
            )

            withdrawal.status = 'processed'
            withdrawal.processed_date = timezone.now()
            withdrawal.actual_amount = withdrawal.amount_requested
            withdrawal.save()

        return Response({
            'message': 'Withdrawal processed successfully',
            'tax_deducted': str(tax_amount),
            'net_amount': str(withdrawal.amount_requested - tax_amount)
        })


class InvestmentDashboardView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        tenant = request.user.tenant
        user = request.user
        
        # Base queryset
        if user.role in ['admin', 'staff']:
            policies = InvestmentPolicy.objects.filter(tenant=tenant)
        else:
            policies = InvestmentPolicy.objects.filter(tenant=tenant, user=user)
        
        # Dashboard metrics
        total_policies = policies.count()
        total_investment = policies.aggregate(total=Sum('current_balance'))['total'] or 0
        total_roi = policies.aggregate(total=Sum('roi_balance'))['total'] or 0
        active_policies = policies.filter(status='active').count()
        
        # ROI due this month (for admin)
        roi_due = []
        if user.role in ['admin', 'staff']:
            roi_due = policies.filter(
                status='active',
                next_roi_date__lte=timezone.now() + timedelta(days=7)
            ).values('policy_number', 'user__email', 'roi_balance')
        
        return Response({
            'metrics': {
                'total_policies': total_policies,
                'total_investment': total_investment,
                'total_roi': total_roi,
                'active_policies': active_policies,
                'total_policy_amount': total_investment + total_roi,
            },
            'roi_due': roi_due,
        })

class StatementGenerationView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        policy_id = request.data.get('policy_id')
        duration = request.data.get('duration', '3_months')  # 1_month, 3_months, 6_months, 1_year, custom
        
        # Calculate date range
        end_date = timezone.now()
        if duration == '1_month':
            start_date = end_date - timedelta(days=30)
        elif duration == '3_months':
            start_date = end_date - timedelta(days=90)
        elif duration == '6_months':
            start_date = end_date - timedelta(days=180)
        elif duration == '1_year':
            start_date = end_date - timedelta(days=365)
        else:
            # Custom date range
            start_date = request.data.get('start_date')
            end_date = request.data.get('end_date')
        
        # Get ledger entries
        entries = LedgerEntry.objects.filter(
            policy_id=policy_id,
            entry_date__range=[start_date, end_date]
        ).order_by('entry_date')
        
        serializer = LedgerEntrySerializer(entries, many=True)
        
        return Response({
            'statement_period': f"{start_date} to {end_date}",
            'entries': serializer.data,
            'summary': {
                'total_inflow': entries.aggregate(total=Sum('inflow'))['total'] or 0,
                'total_outflow': entries.aggregate(total=Sum('outflow'))['total'] or 0,
                'entry_count': entries.count()
            }
        })
        
# investments/views.py (add this to the existing views)

class LedgerEntryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only viewset for ledger entries with comprehensive filtering and reporting
    """
    serializer_class = LedgerEntrySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['entry_type', 'policy']
    
    def get_queryset(self):
        tenant = self.request.user.tenant
        user = self.request.user
        
        queryset = LedgerEntry.objects.filter(tenant=tenant).select_related(
            'policy', 
            'policy__user'
        ).order_by('-entry_date')
        
        # Apply additional filters from query parameters
        policy_number = self.request.query_params.get('policy_number')
        investor_name = self.request.query_params.get('investor_name')
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        
        if policy_number:
            queryset = queryset.filter(policy__policy_number__icontains=policy_number)
        
        if investor_name:
            queryset = queryset.filter(
                Q(policy__user__first_name__icontains=investor_name) |
                Q(policy__user__last_name__icontains=investor_name) |
                Q(policy__user__email__icontains=investor_name)
            )
        
        if date_from:
            queryset = queryset.filter(entry_date__gte=date_from)
        
        if date_to:
            queryset = queryset.filter(entry_date__lte=date_to)
        
        # Non-admin users can only see their own ledger entries
        if user.role not in ['admin', 'staff']:
            queryset = queryset.filter(policy__user=user)
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """
        Get ledger summary with totals and breakdown
        """
        queryset = self.get_queryset()
        
        # Date range filtering for summary
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        
        if date_from:
            queryset = queryset.filter(entry_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(entry_date__lte=date_to)
        
        # Calculate summary statistics
        summary = queryset.aggregate(
            total_inflow=Sum('inflow'),
            total_outflow=Sum('outflow'),
            net_flow=Sum('inflow') - Sum('outflow'),
            entry_count=Count('id')
        )
        
        # Breakdown by entry type
        type_breakdown = queryset.values('entry_type').annotate(
            count=Count('id'),
            total_inflow=Sum('inflow'),
            total_outflow=Sum('outflow')
        ).order_by('entry_type')
        
        # Latest balance
        latest_entry = queryset.first()
        current_balances = {
            'principal_balance': latest_entry.principal_balance if latest_entry else 0,
            'roi_balance': latest_entry.roi_balance if latest_entry else 0,
            'total_balance': latest_entry.total_balance if latest_entry else 0,
        } if latest_entry else {}
        
        return Response({
            'summary': summary,
            'type_breakdown': type_breakdown,
            'current_balances': current_balances,
            'date_range': {
                'from': date_from,
                'to': date_to
            }
        })
    
    @action(detail=False, methods=['get'])
    def export(self, request):
        """
        Export ledger entries to CSV format
        """
        import csv
        from django.http import HttpResponse
        from django.utils import timezone
        
        queryset = self.get_queryset()
        
        # Create HttpResponse object with CSV header
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="ledger_export_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
        
        writer = csv.writer(response)
        
        # Write CSV headers
        writer.writerow([
            'Date', 'Policy Number', 'Investor Name', 'Description', 
            'Entry Type', 'Inflow', 'Outflow', 
            'Principal Balance', 'ROI Balance', 'Total Balance', 'Reference'
        ])
        
        # Write data rows
        for entry in queryset:
            writer.writerow([
                entry.entry_date.strftime('%Y-%m-%d %H:%M:%S'),
                entry.policy.policy_number,
                entry.policy.user.get_full_name(),
                entry.description,
                entry.get_entry_type_display(),
                float(entry.inflow),
                float(entry.outflow),
                float(entry.principal_balance),
                float(entry.roi_balance),
                float(entry.total_balance),
                entry.unique_reference
            ])
        
        return response
    
    @action(detail=False, methods=['get'])
    def by_policy(self, request):
        """
        Get ledger entries grouped by policy with policy summary
        """
        tenant = request.user.tenant
        user = request.user
        
        # Base queryset
        policies = InvestmentPolicy.objects.filter(tenant=tenant)
        
        # Non-admin users can only see their own policies
        if user.role not in ['admin', 'staff']:
            policies = policies.filter(user=user)
        
        policy_ledgers = []
        
        for policy in policies:
            ledger_entries = LedgerEntry.objects.filter(
                policy=policy
            ).order_by('-entry_date')[:50]  # Last 50 entries
            
            policy_summary = {
                'policy_number': policy.policy_number,
                'investor_name': policy.user.get_full_name(),
                'current_principal': policy.current_balance,
                'current_roi': policy.roi_balance,
                'total_balance': policy.total_balance,
                'total_withdrawn': policy.total_withdrawn,
                'ledger_entries': LedgerEntrySerializer(ledger_entries, many=True).data
            }
            
            policy_ledgers.append(policy_summary)
        
        return Response(policy_ledgers)
    
    @action(detail=False, methods=['get'])
    def monthly_report(self, request):
        """
        Generate monthly ledger report with summaries
        """
        from django.db.models.functions import TruncMonth
        
        queryset = self.get_queryset()
        
        # Group by month
        monthly_data = queryset.annotate(
            month=TruncMonth('entry_date')
        ).values('month').annotate(
            total_inflow=Sum('inflow'),
            total_outflow=Sum('outflow'),
            net_flow=Sum('inflow') - Sum('outflow'),
            entry_count=Count('id'),
            deposit_count=Count('id', filter=Q(entry_type='deposit')),
            withdrawal_count=Count('id', filter=Q(entry_type__in=['withdrawal_principal', 'withdrawal_roi'])),
            roi_accrual_count=Count('id', filter=Q(entry_type='roi_accrual'))
        ).order_by('-month')
        
        return Response({
            'monthly_reports': list(monthly_data),
            'report_generated_at': timezone.now()
        })
        
# investments/views.py (add this as well)

class InvestmentSearchView(APIView):
    """
    Comprehensive search across investments
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """
        Search investments by various criteria
        """
        query = request.query_params.get('q', '')
        search_type = request.query_params.get('type', 'all')  # all, policy, investor
        
        if not query:
            return Response(
                {'error': 'Search query parameter "q" is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        tenant = request.user.tenant
        user = request.user
        
        # Base queryset with tenant filtering
        policies = InvestmentPolicy.objects.filter(tenant=tenant)
        
        # Non-admin users can only search their own investments
        if user.role not in ['admin', 'staff']:
            policies = policies.filter(user=user)
        
        # Build search query based on type
        search_filters = Q()
        
        if search_type in ['all', 'policy']:
            search_filters |= Q(policy_number__icontains=query)
            search_filters |= Q(unique_policy_id__icontains=query)
        
        if search_type in ['all', 'investor']:
            search_filters |= Q(user__first_name__icontains=query)
            search_filters |= Q(user__last_name__icontains=query)
            search_filters |= Q(user__email__icontains=query)
        
        # Apply search filters
        results = policies.filter(search_filters).select_related('user')
        
        # Serialize results
        serializer = InvestmentPolicySerializer(results, many=True)
        
        return Response({
            'query': query,
            'search_type': search_type,
            'results_count': results.count(),
            'results': serializer.data
        })
        
        
# investments/views.py (ADD THIS)
# class InvestmentPerformanceReportView(APIView):
#     """
#     Generate investment performance analytics
#     GET /api/investments/reports/performance/
#     Query params: ?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD
#     """
#     permission_classes = [IsAuthenticated, IsAdminUser]
    
#     def get(self, request):
#         tenant = request.user.tenant
#         date_from = request.query_params.get('date_from')
#         date_to = request.query_params.get('date_to', timezone.now())
        
#         policies = InvestmentPolicy.objects.filter(tenant=tenant)
        
#         if date_from:
#             policies = policies.filter(start_date__gte=date_from)
        
#         # Aggregate metrics
#         metrics = policies.aggregate(
#             total_policies=Count('id'),
#             active_policies=Count('id', filter=Q(status='active')),
#             total_principal=Sum('principal_amount'),
#             total_current_balance=Sum('current_balance'),
#             total_roi_accrued=Sum('roi_balance'),
#             total_withdrawn=Sum('total_withdrawn')
#         )
        
#         # Top-up statistics
#         topup_entries = LedgerEntry.objects.filter(
#             tenant=tenant,
#             entry_type='top_up'
#         )
#         if date_from:
#             topup_entries = topup_entries.filter(entry_date__gte=date_from)
        
#         topup_stats = topup_entries.aggregate(
#             total_topups=Sum('inflow'),
#             topup_count=Count('id')
#         )
        
#         # Withdrawal statistics
#         withdrawal_entries = LedgerEntry.objects.filter(
#             tenant=tenant,
#             entry_type__in=['withdrawal_principal', 'withdrawal_roi']
#         )
#         if date_from:
#             withdrawal_entries = withdrawal_entries.filter(entry_date__gte=date_from)
        
#         withdrawal_stats = withdrawal_entries.aggregate(
#             total_withdrawals=Sum('outflow'),
#             withdrawal_count=Count('id')
#         )
        
#         return Response({
#             'period': {
#                 'from': date_from,
#                 'to': date_to
#             },
#             'overview': metrics,
#             'topups': topup_stats,
#             'withdrawals': withdrawal_stats,
#             'growth': {
#                 'principal_growth': (metrics['total_current_balance'] or 0) - (metrics['total_principal'] or 0),
#                 'roi_generated': metrics['total_roi_accrued'] or 0
#             }
#         })
 
 
# investments/views.py (ADD THIS)
class InvestmentPerformanceReportView(APIView):
    """
    Generate investment performance analytics
    GET /api/investments/reports/performance/
    Query params: ?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def get(self, request):
        tenant = request.user.tenant
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to', timezone.now())
        
        policies = InvestmentPolicy.objects.filter(tenant=tenant)
        
        if date_from:
            policies = policies.filter(start_date__gte=date_from)
        
        # Aggregate metrics
        metrics = policies.aggregate(
            total_policies=Count('id'),
            active_policies=Count('id', filter=Q(status='active')),
            total_principal=Sum('principal_amount'),
            total_current_balance=Sum('current_balance'),
            total_roi_accrued=Sum('roi_balance'),
            total_withdrawn=Sum('total_withdrawn')
        )
        
        # Top-up statistics
        topup_entries = LedgerEntry.objects.filter(
            tenant=tenant,
            entry_type='top_up'
        )
        if date_from:
            topup_entries = topup_entries.filter(entry_date__gte=date_from)
        
        topup_stats = topup_entries.aggregate(
            total_topups=Sum('inflow'),
            topup_count=Count('id')
        )
        
        # Withdrawal statistics
        withdrawal_entries = LedgerEntry.objects.filter(
            tenant=tenant,
            entry_type__in=['withdrawal_principal', 'withdrawal_roi']
        )
        if date_from:
            withdrawal_entries = withdrawal_entries.filter(entry_date__gte=date_from)
        
        withdrawal_stats = withdrawal_entries.aggregate(
            total_withdrawals=Sum('outflow'),
            withdrawal_count=Count('id')
        )
        
        return Response({
            'period': {
                'from': date_from,
                'to': date_to
            },
            'overview': metrics,
            'topups': topup_stats,
            'withdrawals': withdrawal_stats,
            'growth': {
                'principal_growth': (metrics['total_current_balance'] or 0) - (metrics['total_principal'] or 0),
                'roi_generated': metrics['total_roi_accrued'] or 0
            }
        })
        
               
# investments/views.py (ADD THIS)
class ROIDueReportView(APIView):
    """
    Generate printable ROI due report
    GET /api/investments/reports/roi-due/
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def get(self, request):
        tenant = request.user.tenant
        
        # Get policies due for ROI in next 7 days
        due_policies = InvestmentPolicy.objects.filter(
            tenant=tenant,
            status='active',
            roi_frequency='monthly',
            next_roi_date__lte=timezone.now() + timedelta(days=7)
        ).select_related('user', 'profile')
        
        report_data = []
        total_roi_due = Decimal('0.00')
        
        for policy in due_policies:
            monthly_roi = (policy.current_balance * policy.roi_rate / 100) / 12
            total_roi_due += monthly_roi
            
            report_data.append({
                'name': policy.user.get_full_name(),
                'email': policy.user.email,
                'phone': policy.user.phone_number,
                'policy_number': policy.policy_number,
                'roi_amount': monthly_roi,
                'next_roi_date': policy.next_roi_date,
                'bank_name': policy.profile.bank_name if policy.profile else '',
                'account_number': policy.profile.account_number if policy.profile else '',
                'account_name': policy.profile.account_name if policy.profile else ''
            })
        
        return Response({
            'report_date': timezone.now(),
            'total_customers': len(report_data),
            'total_roi_due': total_roi_due,
            'customers': report_data
        })


# ===============================
# TAX MANAGEMENT VIEWS
# ===============================

class TaxCalculationView(APIView):
    """
    Calculate taxes for investment transactions
    POST /api/investments/taxes/calculate/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = TaxCalculationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        amount = serializer.validated_data['amount']
        tax_type = serializer.validated_data['tax_type']
        annual_income = serializer.validated_data.get('annual_income')
        include_breakdown = serializer.validated_data.get('include_breakdown', True)

        tenant = request.user.tenant

        try:
            if tax_type == 'pit':
                # Personal Income Tax calculation
                if not annual_income:
                    return Response(
                        {'error': 'annual_income is required for PIT calculations'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                calculation = NigerianTaxCalculator.calculate_pit(annual_income)
            elif tax_type.startswith('wht'):
                # Withholding Tax calculation
                calculation = NigerianTaxCalculator.calculate_wht(amount, tax_type, tenant)
            elif tax_type == 'cgt':
                # Capital Gains Tax calculation
                calculation = NigerianTaxCalculator.calculate_cgt(amount, tenant)
            elif tax_type == 'vat':
                # Value Added Tax calculation
                calculation = NigerianTaxCalculator.calculate_vat(amount, tenant)
            else:
                return Response(
                    {'error': f'Unsupported tax type: {tax_type}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Record the tax calculation for audit
            tax_record = NigerianTaxCalculator.record_tax_calculation(
                tenant=tenant,
                user=request.user,
                tax_type=tax_type,
                calculation_data=calculation,
                calculated_by=request.user,
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )

            response_data = {
                'tax_type': tax_type,
                'calculation': calculation,
                'tax_record_id': tax_record.id,
                'calculated_at': tax_record.calculation_date
            }

            if not include_breakdown and 'breakdown' in calculation:
                del calculation['breakdown']

            return Response(response_data)

        except Exception as e:
            return Response(
                {'error': f'Tax calculation failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class TaxRecordViewSet(viewsets.ReadOnlyModelViewSet):
    """
    View tax records for audit and compliance
    """
    serializer_class = TaxRecordSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['tax_type', 'status', 'tax_period']

    def get_queryset(self):
        tenant = self.request.user.tenant
        user = self.request.user

        queryset = TaxRecord.objects.filter(tenant=tenant)

        # Non-admin users can only see their own tax records
        if user.role not in ['admin', 'staff']:
            queryset = queryset.filter(user=user)

        return queryset.order_by('-calculation_date')


class TaxSummaryView(APIView):
    """
    Get tax summary for a user or tenant
    GET /api/investments/taxes/summary/
    Query params: ?user_id=123&tax_year=2024
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_id = request.query_params.get('user_id')
        tax_year = request.query_params.get('tax_year')

        tenant = request.user.tenant
        current_user = request.user

        # Determine which user's tax summary to get
        if user_id:
            # Admin requesting specific user's summary
            if current_user.role not in ['admin', 'staff']:
                return Response(
                    {'error': 'Only admins can view other users\' tax summaries'},
                    status=status.HTTP_403_FORBIDDEN
                )
            try:
                target_user = get_user_model().objects.get(id=user_id, tenant=tenant)
            except get_user_model().DoesNotExist:
                return Response(
                    {'error': 'User not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            # User requesting their own summary
            target_user = current_user

        # Get tax summary
        summary = NigerianTaxCalculator.get_tax_summary(target_user, tax_year)

        return Response({
            'user': {
                'id': target_user.id,
                'name': target_user.get_full_name(),
                'email': target_user.email
            },
            'summary': summary
        })


class TaxCertificateViewSet(viewsets.ModelViewSet):
    """
    Manage tax certificates
    """
    serializer_class = TaxCertificateSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['certificate_type', 'status', 'tax_year']

    def get_queryset(self):
        tenant = self.request.user.tenant
        user = self.request.user

        queryset = TaxCertificate.objects.filter(tenant=tenant)

        # Non-admin users can only see their own certificates
        if user.role not in ['admin', 'staff']:
            queryset = queryset.filter(user=user)

        return queryset.order_by('-issue_date')

    def perform_create(self, serializer):
        """Auto-generate certificate number and set issuer"""
        tenant = self.request.user.tenant
        certificate = serializer.save(
            tenant=tenant,
            issued_by=self.request.user
        )
        certificate.generate_certificate_number()
        certificate.save()

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve a tax certificate (admin only)"""
        if request.user.role not in ['admin', 'staff']:
            return Response(
                {'error': 'Only admins can approve tax certificates'},
                status=status.HTTP_403_FORBIDDEN
            )

        certificate = self.get_object()
        certificate.status = 'issued'
        certificate.approved_by = request.user
        certificate.save()

        return Response({'message': 'Tax certificate approved and issued'})

    @action(detail=False, methods=['post'])
    def generate(self, request):
        """Generate a tax certificate for a user"""
        serializer = TaxCertificateRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        certificate_type = serializer.validated_data['certificate_type']
        tax_year = serializer.validated_data['tax_year']
        include_related_records = serializer.validated_data.get('include_related_records', True)

        tenant = request.user.tenant
        current_user = request.user

        # Determine target user (admin can generate for others)
        target_user_id = request.data.get('user_id')
        if target_user_id and current_user.role in ['admin', 'staff']:
            try:
                target_user = get_user_model().objects.get(id=target_user_id, tenant=tenant)
            except get_user_model().DoesNotExist:
                return Response(
                    {'error': 'Target user not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            target_user = current_user

        # Get tax summary for the year
        tax_summary = NigerianTaxCalculator.get_tax_summary(target_user, tax_year)

        # Create certificate
        certificate = TaxCertificate.objects.create(
            tenant=tenant,
            user=target_user,
            certificate_type=certificate_type,
            tax_year=tax_year,
            validity_period_start=f"{tax_year}-01-01",
            validity_period_end=f"{tax_year}-12-31",
            total_gross_income=tax_summary['total_gross_income'],
            total_tax_deducted=tax_summary['total_tax_deducted'],
            total_tax_paid=tax_summary['total_tax_paid'],
            net_income_after_tax=tax_summary['net_income_after_tax'],
            tax_breakdown=tax_summary['tax_breakdown'],
            issued_by=current_user
        )

        certificate.generate_certificate_number()
        certificate.save()

        # Link related tax records if requested
        if include_related_records:
            related_records = TaxRecord.objects.filter(
                tenant=tenant,
                user=target_user,
                tax_period=tax_year
            )
            certificate.related_tax_records.set(related_records)

        serializer = self.get_serializer(certificate)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class TaxSettingsView(APIView):
    """
    Manage tenant tax settings
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        """Get current tax settings"""
        tenant = request.user.tenant
        settings = NigerianTaxCalculator.get_tenant_tax_settings(tenant)
        serializer = TaxSettingsSerializer(settings)
        return Response(serializer.data)

    def put(self, request):
        """Update tax settings"""
        tenant = request.user.tenant
        settings = NigerianTaxCalculator.get_tenant_tax_settings(tenant)

        serializer = TaxSettingsSerializer(settings, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TaxReportView(APIView):
    """
    Generate comprehensive tax reports
    GET /api/investments/taxes/reports/
    Query params: ?report_type=annual_summary&tax_year=2024
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        report_type = request.query_params.get('report_type', 'annual_summary')
        tax_year = request.query_params.get('tax_year', str(timezone.now().year))

        tenant = request.user.tenant

        if report_type == 'annual_summary':
            return self._generate_annual_summary_report(tenant, tax_year)
        elif report_type == 'wht_summary':
            return self._generate_wht_summary_report(tenant, tax_year)
        elif report_type == 'compliance':
            return self._generate_compliance_report(tenant, tax_year)
        else:
            return Response(
                {'error': f'Unsupported report type: {report_type}'},
                status=status.HTTP_400_BAD_REQUEST
            )

    def _generate_annual_summary_report(self, tenant, tax_year):
        """Generate annual tax summary for all users"""
        tax_records = TaxRecord.objects.filter(
            tenant=tenant,
            tax_period=tax_year
        ).select_related('user')

        # Group by user
        user_summaries = {}
        for record in tax_records:
            user_id = record.user.id
            if user_id not in user_summaries:
                user_summaries[user_id] = {
                    'user': {
                        'id': record.user.id,
                        'name': record.user.get_full_name(),
                        'email': record.user.email
                    },
                    'tax_breakdown': {},
                    'total_gross': Decimal('0'),
                    'total_tax': Decimal('0'),
                    'net_after_tax': Decimal('0')
                }

            user_summary = user_summaries[user_id]
            user_summary['total_gross'] += record.gross_amount
            user_summary['total_tax'] += record.tax_amount

            if record.tax_type not in user_summary['tax_breakdown']:
                user_summary['tax_breakdown'][record.tax_type] = {
                    'count': 0,
                    'total_amount': Decimal('0'),
                    'total_tax': Decimal('0')
                }

            user_summary['tax_breakdown'][record.tax_type]['count'] += 1
            user_summary['tax_breakdown'][record.tax_type]['total_amount'] += record.gross_amount
            user_summary['tax_breakdown'][record.tax_type]['total_tax'] += record.tax_amount

        # Calculate net amounts
        for user_summary in user_summaries.values():
            user_summary['net_after_tax'] = user_summary['total_gross'] - user_summary['total_tax']

        return Response({
            'report_type': 'annual_summary',
            'tax_year': tax_year,
            'generated_at': timezone.now(),
            'total_users': len(user_summaries),
            'user_summaries': list(user_summaries.values())
        })

    def _generate_wht_summary_report(self, tenant, tax_year):
        """Generate WHT summary report"""
        wht_records = TaxRecord.objects.filter(
            tenant=tenant,
            tax_period=tax_year,
            tax_type__startswith='wht'
        ).select_related('user')

        summary = wht_records.aggregate(
            total_gross=Sum('gross_amount'),
            total_wht=Sum('tax_amount'),
            record_count=Count('id')
        )

        # Breakdown by WHT type
        type_breakdown = wht_records.values('tax_type').annotate(
            count=Count('id'),
            total_gross=Sum('gross_amount'),
            total_tax=Sum('tax_amount')
        ).order_by('tax_type')

        return Response({
            'report_type': 'wht_summary',
            'tax_year': tax_year,
            'generated_at': timezone.now(),
            'summary': summary,
            'type_breakdown': list(type_breakdown)
        })

    def _generate_compliance_report(self, tenant, tax_year):
        """Generate tax compliance report"""
        total_users = get_user_model().objects.filter(tenant=tenant).count()
        users_with_tax_records = TaxRecord.objects.filter(
            tenant=tenant,
            tax_period=tax_year
        ).values('user').distinct().count()

        certificates_issued = TaxCertificate.objects.filter(
            tenant=tenant,
            tax_year=tax_year,
            status='issued'
        ).count()

        pending_certificates = TaxCertificate.objects.filter(
            tenant=tenant,
            tax_year=tax_year,
            status='draft'
        ).count()

        return Response({
            'report_type': 'compliance',
            'tax_year': tax_year,
            'generated_at': timezone.now(),
            'compliance_metrics': {
                'total_users': total_users,
                'users_with_tax_records': users_with_tax_records,
                'certificates_issued': certificates_issued,
                'pending_certificates': pending_certificates,
                'compliance_rate': (users_with_tax_records / total_users * 100) if total_users > 0 else 0
            }
        })