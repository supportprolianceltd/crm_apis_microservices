# hr/rewards_penalties/models.py
from django.db import models
from django.utils.text import slugify
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.conf import settings
import uuid
import logging
import json
from django.db.models import JSONField
from enum import Enum
from datetime import date, timedelta

logger = logging.getLogger('hr_rewards_penalties')



def current_date():
    return timezone.now().date()  # Call the method to get the actual date

class RewardType(Enum):
    BONUS = 'bonus'
    PROMOTION = 'promotion'
    RECOGNITION = 'recognition'
    EXTRA_PTO = 'extra_pto'
    GIFT_CARD = 'gift_card'
    PUBLIC_PRAISE = 'public_praise'
    TRAINING_OPPORTUNITY = 'training_opportunity'
    OTHER = 'other'

class PenaltyType(Enum):
    VERBAL_WARNING = 'verbal_warning'
    WRITTEN_WARNING = 'written_warning'
    PERFORMANCE_IMPROVEMENT_PLAN = 'performance_improvement_plan'
    SUSPENSION = 'suspension'
    DEMOTION = 'demotion'
    TERMINATION = 'termination'
    OTHER = 'other'

class Status(Enum):
    PENDING = 'pending'
    UNDER_REVIEW = 'under_review'
    APPROVED = 'approved'
    ISSUED = 'issued'
    REJECTED = 'rejected'
    RESOLVED = 'resolved'
    CANCELLED = 'cancelled'

def validate_details_json(value):
    if not isinstance(value, dict):
        raise ValidationError("Details must be a dictionary.")
    required_keys = ['id', 'email', 'first_name', 'last_name', 'job_role', 'department']
    for key in required_keys:
        if key not in value:
            raise ValidationError(f"Details must include '{key}'.")
    return value

def validate_compliance_checklist(value):
    if not isinstance(value, list):
        raise ValidationError("Compliance checklist must be a list.")
    for item in value:
        if not isinstance(item, dict) or 'name' not in item or 'completed' not in item:
            raise ValidationError("Each compliance item must be a dictionary with 'name' and 'completed' fields.")
    return value

def validate_approval_workflow(value):
    if not isinstance(value, dict):
        raise ValidationError("Approval workflow must be a dictionary.")
    if 'stages' not in value or not isinstance(value['stages'], list):
        raise ValidationError("Approval workflow must have a 'stages' list.")
    for stage in value['stages']:
        if not isinstance(stage, dict) or 'role' not in stage:
            raise ValidationError("Each stage must have a 'role' field.")
    return value

class ActiveRewardsPenaltiesManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

class SoftDeleteQuerySet(models.query.QuerySet):
    def delete(self):
        self.update(is_deleted=True, deleted_at=timezone.now())

class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).filter(is_deleted=False)

    def all_with_deleted(self):
        return super().get_queryset()

    def deleted_set(self):
        return super().get_queryset().filter(is_deleted=True)

class BaseRewardsPenaltyModel(models.Model):
    id = models.CharField(max_length=50, primary_key=True, editable=False)
    tenant_id = models.UUIDField(db_index=True)
    tenant_domain = models.CharField(max_length=255, blank=True, null=True)
    employee_id = models.UUIDField(db_index=True)
    employee_details = JSONField(validators=[validate_details_json])
    date_issued = models.DateField(default=current_date)
    effective_date = models.DateField(null=True, blank=True)
    reason = models.TextField(max_length=1000)
    description = models.TextField(max_length=2000, blank=True)
    status = models.CharField(max_length=20, choices=[(tag.value, tag.name) for tag in Status], default=Status.PENDING.value)
    approver_id = models.UUIDField(null=True, blank=True)
    approver_details = JSONField(validators=[validate_details_json], null=True, blank=True)
    created_by_id = models.UUIDField()
    created_by_details = JSONField(validators=[validate_details_json])
    updated_by_id = models.UUIDField(null=True, blank=True)
    updated_by_details = JSONField(validators=[validate_details_json], null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    compliance_checklist = JSONField(default=list, blank=True, null=True, validators=[validate_compliance_checklist])
    last_compliance_check = models.DateTimeField(null=True, blank=True)
    checked_by_id = models.UUIDField(null=True, blank=True)
    checked_by_details = JSONField(default=dict, blank=True, null=True, validators=[validate_details_json])
    approval_workflow = JSONField(default=dict, blank=True, null=True, validators=[validate_approval_workflow])
    current_approval_stage = models.IntegerField(default=0)
    approval_date = models.DateTimeField(null=True, blank=True)
    evidence_file = models.FileField(upload_to='evidence/%Y/%m/%d/', null=True, blank=True)
    evidence_file_url = models.URLField(max_length=500, blank=True, null=True)
    notes = models.TextField(max_length=500, blank=True)
    is_public = models.BooleanField(default=False)  # For announcements
    impact_assessment = JSONField(default=dict, blank=True)  # e.g., {'team_morale': 'positive', 'productivity': 'high'}

    objects = SoftDeleteManager()
    active_objects = ActiveRewardsPenaltiesManager()

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['tenant_id', 'status']),
            models.Index(fields=['tenant_id', 'date_issued']),
            models.Index(fields=['employee_id', 'tenant_id']),
        ]

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=['is_deleted', 'deleted_at'])

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=['is_deleted', 'deleted_at'])

class Reward(BaseRewardsPenaltyModel):
    code = models.CharField(max_length=50, editable=False)
    type = models.CharField(max_length=50, choices=[(tag.value, tag.name) for tag in RewardType], default=RewardType.BONUS.value)
    value = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)  # Monetary or points
    value_type = models.CharField(max_length=20, choices=[('monetary', 'Monetary'), ('points', 'Points')], default='monetary')
    duration_days = models.PositiveIntegerField(null=True, blank=True)  # e.g., for extra PTO
    announcement_channel = models.CharField(max_length=100, blank=True)  # e.g., 'company-wide', 'department'
    follow_up_required = models.BooleanField(default=False)
    follow_up_date = models.DateField(null=True, blank=True)
    custom_fields = JSONField(default=dict, blank=True)  # Extensible for tenant-specific fields

    class Meta:
        verbose_name_plural = "Rewards"
        unique_together = [('tenant_id', 'code')]

    def generate_code(self, tenant_schema):
        # Use the model's default manager to ensure we're querying the same database
        model_class = self.__class__
        
        # Get the latest instance for this tenant
        latest_instance = model_class.objects.filter(
            tenant_id=self.tenant_id,
            id__startswith=f"{tenant_schema}-{self._get_code_prefix()}-"
        ).order_by('-created_at').first()
        
        last_number = 0
        if latest_instance and latest_instance.id:
            try:
                last_number = int(latest_instance.id.split('-')[-1])
            except (ValueError, IndexError):
                last_number = 0
        
        next_number = str(last_number + 1).zfill(4)
        code_suffix = self._get_code_suffix()
        
        self.id = f"{tenant_schema}-{self._get_code_prefix()}-{next_number}"
        self.code = f"{tenant_schema}-{code_suffix}-{next_number}"

    def _get_code_prefix(self):
        """Get the prefix for ID (R for Reward, P for Penalty)"""
        return 'R' if isinstance(self, Reward) else 'P'

    def _get_code_suffix(self):
        """Get the suffix for code (REW for Reward, PEN for Penalty)"""
        return 'REW' if isinstance(self, Reward) else 'PEN'

class Penalty(BaseRewardsPenaltyModel):
    code = models.CharField(max_length=50, editable=False)
    type = models.CharField(max_length=50, choices=[(tag.value, tag.name) for tag in PenaltyType], default=PenaltyType.VERBAL_WARNING.value)
    severity_level = models.PositiveSmallIntegerField(choices=[(1, 'Low'), (2, 'Medium'), (3, 'High')], default=1)
    duration_days = models.PositiveIntegerField(null=True, blank=True)  # e.g., for suspension
    end_date = models.DateField(null=True, blank=True)
    probation_period_months = models.PositiveSmallIntegerField(null=True, blank=True)
    corrective_action_plan = JSONField(default=dict, blank=True)  # e.g., {'steps': [...], 'timeline': '...' }
    escalation_history = JSONField(default=list, blank=True)  # Track previous penalties
    legal_compliance_notes = models.TextField(max_length=1000, blank=True)
    custom_fields = JSONField(default=dict, blank=True)  # Extensible

    class Meta:
        verbose_name_plural = "Penalties"
        unique_together = [('tenant_id', 'code')]

    def generate_code(self, tenant_schema):
        # Use the model's default manager to ensure we're querying the same database
        model_class = self.__class__
        
        # Get the latest instance for this tenant
        latest_instance = model_class.objects.filter(
            tenant_id=self.tenant_id,
            id__startswith=f"{tenant_schema}-{self._get_code_prefix()}-"
        ).order_by('-created_at').first()
        
        last_number = 0
        if latest_instance and latest_instance.id:
            try:
                last_number = int(latest_instance.id.split('-')[-1])
            except (ValueError, IndexError):
                last_number = 0
        
        next_number = str(last_number + 1).zfill(4)
        code_suffix = self._get_code_suffix()
        
        self.id = f"{tenant_schema}-{self._get_code_prefix()}-{next_number}"
        self.code = f"{tenant_schema}-{code_suffix}-{next_number}"

    def _get_code_prefix(self):
        """Get the prefix for ID (R for Reward, P for Penalty)"""
        return 'R' if isinstance(self, Reward) else 'P'

    def _get_code_suffix(self):
        """Get the suffix for code (REW for Reward, PEN for Penalty)"""
        return 'REW' if isinstance(self, Reward) else 'PEN'

    def clean(self):
        super().clean()
        if self.type == PenaltyType.SUSPENSION.value and not self.duration_days:
            raise ValidationError("Suspension requires duration_days.")
        if self.end_date and self.effective_date and self.end_date <= self.effective_date:
            raise ValidationError("End date must be after effective date.")
        if self.duration_days:
            # Ensure effective_date is a date object
            effective = self.effective_date
            if hasattr(effective, 'date'):
                effective = effective.date()
            self.end_date = effective + timedelta(days=self.duration_days)