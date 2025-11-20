# investments/admin.py
from django.contrib import admin
from .models import InvestmentPolicy, LedgerEntry, WithdrawalRequest, ROIAccrual

@admin.register(InvestmentPolicy)
class InvestmentPolicyAdmin(admin.ModelAdmin):
    list_display = ['policy_number', 'user', 'principal_amount', 'current_balance', 'status', 'start_date']
    list_filter = ['status', 'roi_frequency', 'tenant']
    search_fields = ['policy_number', 'user__email', 'user__first_name', 'user__last_name']
    readonly_fields = ['policy_number', 'unique_policy_id', 'created_at', 'updated_at']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(tenant=request.user.tenant)

@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    list_display = ['policy', 'user', 'amount_requested', 'status', 'request_date']
    list_filter = ['status', 'withdrawal_type', 'tenant']
    actions = ['approve_requests', 'reject_requests']
    
    def approve_requests(self, request, queryset):
        queryset.update(status='approved', approved_by=request.user, approved_date=timezone.now())
    approve_requests.short_description = "Approve selected withdrawals"
    
    def reject_requests(self, request, queryset):
        queryset.update(status='rejected')
    reject_requests.short_description = "Reject selected withdrawals"