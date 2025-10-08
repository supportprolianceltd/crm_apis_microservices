from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Sum, Avg, Count
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
import uuid
from decimal import Decimal
from datetime import date, timedelta
import logging

logger = logging.getLogger('hr')

class HRBaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant_id = models.CharField(max_length=36, blank=False, null=False)  # Tenant ID from auth_service
    user_id = models.UUIDField(_('User ID from auth_service'), null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_updated_by_id = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        abstract = True
        indexes = [models.Index(fields=['tenant_id', 'user_id'])]

    def save(self, *args, **kwargs):
        # Auto-set tenant_id from JWT if needed (via view/middleware context)
        if not self.tenant_id:
            from django.contrib.auth.models import AnonymousUser
            if not isinstance(self._state.adding, AnonymousUser) and hasattr(self, 'request'):  # Pseudo-code; adapt in views
                self.tenant_id = self.request.jwt_payload.get('tenant_id')
        super().save(*args, **kwargs)


class LeaveType(HRBaseModel):
    name = models.CharField(max_length=50)
    max_days = models.PositiveIntegerField(default=0)
    is_paid = models.BooleanField(default=True)
    requires_approval = models.BooleanField(default=True)
    carry_over_allowed = models.BooleanField(default=False)  # For pro-rata

    class Meta(HRBaseModel.Meta):
        unique_together = ('tenant_id', 'name')
        verbose_name_plural = "Leave Types"

    def __str__(self):
        return f"{self.name} ({self.tenant_id})"

    def calculate_entitlement(self, hire_date, current_date):
        """Pro-rata calc for annual leave (Step 8)."""
        months_worked = (current_date.year - hire_date.year) * 12 + (current_date.month - hire_date.month)
        pro_rata = (self.max_days / 12) * months_worked
        return min(pro_rata, self.max_days)


class LeaveRequest(HRBaseModel):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    )
    leave_type_id = models.CharField(max_length=36, blank=False)  # ID of LeaveType
    start_date = models.DateField()
    end_date = models.DateField()
    days_requested = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    approved_by_id = models.UUIDField(null=True, blank=True)
    notes = models.TextField(blank=True)
    bradford_factor = models.FloatField(null=True, blank=True)
    self_cert_form_sent = models.BooleanField(default=False)  # For >7 days absence

    class Meta(HRBaseModel.Meta):
        verbose_name_plural = "Leave Requests"

    def save(self, *args, **kwargs):
        if self.start_date and self.end_date:
            delta = self.end_date - self.start_date
            self.days_requested = delta.days + 1
        if self.leave_type.name == 'sick':
            self.bradford_factor = self._calculate_bradford()
        if self.days_requested > 7:
            self.self_cert_form_sent = True
            from .tasks import send_self_cert_prompt
            send_self_cert_prompt.delay(self.id)
        super().save(*args, **kwargs)

    def _calculate_bradford(self):
        year_start = timezone.now().date().replace(month=1, day=1)
        spells = self.__class__.objects.filter(
            user_id=self.user_id, leave_type__name='sick',
            start_date__gte=year_start
        ).count()
        total_days = self.__class__.objects.filter(
            user_id=self.user_id, leave_type__name='sick',
            start_date__gte=year_start
        ).aggregate(total=Sum('days_requested'))['total'] or 0
        return spells * spells * total_days if spells else 0

    def get_balance(self):
        """Outstanding balance (Step 8)."""
        hire_date = date.today()  # Fetch from auth API
        entitlement = self.leave_type.calculate_entitlement(hire_date, date.today())
        taken = self.__class__.objects.filter(
            user_id=self.user_id, leave_type=self.leave_type, status='approved'
        ).aggregate(taken=Sum('days_requested'))['taken'] or 0
        return entitlement - taken


class Contract(HRBaseModel):
    CONTRACT_TYPES = (
        ('full_time', 'Full Time'),
        ('part_time', 'Part Time'),
        ('contract', 'Contract'),
    )
    type = models.CharField(max_length=20, choices=CONTRACT_TYPES)
    salary = models.DecimalField(max_digits=10, decimal_places=2)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    probation_days = models.PositiveIntegerField(default=90)
    is_signed = models.BooleanField(default=False)
    signed_at = models.DateTimeField(null=True, blank=True)
    document_id = models.UUIDField(null=True, blank=True)  # Auth Document link
    probation_status = models.CharField(max_length=20, default='in_progress')  # Links to ProbationPeriod

    class Meta(HRBaseModel.Meta):
        verbose_name_plural = "Contracts"

    def generate_and_sign(self):
        """Step 4: Generate PDF, e-sign, auto-file."""
        from .utils import generate_pdf_contract, upload_to_auth, initiate_esign
        pdf_path = generate_pdf_contract(self)
        doc_id = upload_to_auth(pdf_path, self.user_id, title=f"Contract for {self.user_id}")
        self.document_id = doc_id
        esign_url = initiate_esign(doc_id)  # Stub: Return DocuSign URL
        # Webhook callback updates is_signed=True
        from .tasks import notify_contract_ready
        notify_contract_ready.delay(self.id, esign_url)


class Equipment(HRBaseModel):
    item_name = models.CharField(max_length=100)
    serial_number = models.CharField(max_length=50, unique=True)
    issued_date = models.DateField()
    return_date = models.DateField(null=True, blank=True)
    is_returned = models.BooleanField(default=False)
    acceptance_signed = models.BooleanField(default=False)
    rfid_tag = models.CharField(max_length=50, blank=True)  # For tracking

    class Meta(HRBaseModel.Meta):
        unique_together = ('tenant_id', 'serial_number')
        verbose_name_plural = "Equipment"

    def issue(self):
        """Step 5: Issue + e-sign acceptance."""
        self.issued_date = date.today()
        from .utils import generate_acceptance_form, initiate_esign
        form_path = generate_acceptance_form(self)
        esign_url = initiate_esign(form_path, self.user_id)
        from .tasks import notify_equipment_issued
        notify_equipment_issued.delay(self.id, esign_url)


class Policy(HRBaseModel):
    title = models.CharField(max_length=200)
    content = models.TextField()
    requires_acknowledgment = models.BooleanField(default=True)
    quiz_required = models.BooleanField(default=False)
    quiz_questions = models.JSONField(default=list, blank=True)  # e.g., [{'q': '...', 'ans': '...'}]

    class Meta(HRBaseModel.Meta):
        verbose_name_plural = "Policies"


class PolicyAcknowledgment(HRBaseModel):
    policy_id = models.CharField(max_length=36, blank=False)  # ID of Policy
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    quiz_score = models.FloatField(null=True, blank=True)
    is_compliant = models.BooleanField(default=False)  # Score > 80%

    class Meta(HRBaseModel.Meta):
        unique_together = ('user_id', 'policy_id', 'tenant_id')
        verbose_name_plural = "Policy Acknowledgments"

    def save(self, *args, **kwargs):
        if self.quiz_score and self.quiz_score >= 80:
            self.is_compliant = True
            self.acknowledged_at = timezone.now()
        super().save(*args, **kwargs)


class EscalationAlert(HRBaseModel):
    ALERT_TYPES = (
        ('overdue_document', 'Overdue Document'),
        ('probation_end', 'Probation End'),
        ('rtw_interview', 'RTW Interview'),
        ('high_bradford', 'High Bradford Factor'),
        ('disciplinary_warning', 'Disciplinary Warning'),
        ('unsubmitted_leave', 'Unsubmitted Leave'),
        ('self_cert_overdue', 'Self-Cert Overdue'),
    )
    type = models.CharField(max_length=50, choices=ALERT_TYPES)
    description = models.TextField()
    severity = models.CharField(max_length=20, default='medium', choices=(('low', 'Low'), ('medium', 'Medium'), ('high', 'High')))
    resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta(HRBaseModel.Meta):
        verbose_name_plural = "Escalation Alerts"

    def notify(self):
        """Step 7: Send to notifications."""
        payload = {
            'tenant_id': str(self.tenant_id),
            'user_id': str(self.user_id),
            'type': self.type,
            'message': self.description,
            'severity': self.severity
        }
        # requests.post(NOTIFICATIONS_SERVICE_URL + '/api/notifications/', json=payload)
        logger.info(f"Alert notified: {payload}")


class DisciplinaryWarning(HRBaseModel):
    reason = models.TextField()
    issued_date = models.DateField()
    expires_date = models.DateField()
    is_active = models.BooleanField(default=True)

    class Meta(HRBaseModel.Meta):
        verbose_name_plural = "Disciplinary Warnings"


class ProbationPeriod(HRBaseModel):
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, default='in_progress', choices=(('in_progress', 'In Progress'), ('passed', 'Passed'), ('failed', 'Failed')))
    review_notes = models.TextField(blank=True)

    class Meta(HRBaseModel.Meta):
        verbose_name_plural = "Probation Periods"


class PerformanceReview(HRBaseModel):
    review_date = models.DateField()
    score = models.FloatField()  # 1-10
    feedback = models.TextField()
    supervisor_id = models.UUIDField(null=True, blank=True)
    training_completed = models.BooleanField(default=False)

    class Meta(HRBaseModel.Meta):
        verbose_name_plural = "Performance Reviews"


class EmployeeRelationCase(HRBaseModel):
    """ER cases (Step 2/3 monitoring)."""
    title = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(max_length=20, default='open', choices=(('open', 'Open'), ('in_progress', 'In Progress'), ('closed', 'Closed')))
    assigned_to_id = models.UUIDField(null=True, blank=True)

    class Meta(HRBaseModel.Meta):
        verbose_name_plural = "ER Cases"


class StarterLeaver(HRBaseModel):
    """Track starters/leavers for analytics (Step 8)."""
    TYPE_CHOICES = (('starter', 'Starter'), ('leaver', 'Leaver'))
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    reason = models.TextField(blank=True)

    class Meta(HRBaseModel.Meta):
        verbose_name_plural = "Starters/Leavers"

