from django.db import models
from django.utils import timezone
import logging

logger = logging.getLogger('job_applications')

class ActiveApplicationsManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

class JobApplication(models.Model):
    STATUS_CHOICES = [
        ('new', 'New'),
        ('in_review', 'In Review'),
        ('shortlisted', 'Shortlisted'),
        ('interviewing', 'Interviewing'),
        ('offer_pending', 'Offer Pending'),
        ('hired', 'Hired'),
        ('rejected', 'Rejected'),
        ('withdrawn', 'Withdrawn'),
    ]
    STAGE_CHOICES = [
        ('application', 'Application'),
        ('screening', 'Screening'),
        ('interview', 'Interview'),
        ('offer', 'Offer'),
        ('hired', 'Hired'),
        ('rejected', 'Rejected'),
    ]
    SOURCE_CHOICES = [
        ('career_site', 'Career Site'),
        ('linkedin', 'LinkedIn'),
        ('indeed', 'Indeed'),
        ('referral', 'Referral'),
        ('agency', 'Agency'),
        ('other', 'Other'),
    ]
    SCREENING_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processed', 'Processed'),
        ('failed', 'Failed'),
    ]

    id = models.CharField(primary_key=True, max_length=36, editable=False, unique=True)
    tenant_id = models.CharField(max_length=36, blank=False, null=False)
    job_requisition_id = models.CharField(max_length=36, blank=False, null=False)
    branch_id = models.CharField(max_length=36, null=True, blank=True)

    # Candidate info
    first_name = models.CharField(max_length=100, blank=False, null=False)
    last_name = models.CharField(max_length=100, blank=False, null=False)
    full_name = models.CharField(max_length=255, blank=True, null=True)  # Optional, can be auto-filled
    email = models.EmailField(max_length=255, blank=False, null=False)
    phone = models.CharField(max_length=50, blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)

    # Documents
    resume_url = models.TextField(blank=False, null=False)
    cover_letter_url = models.TextField(blank=True, null=True)
    resume_status = models.BooleanField(default=True)

    # Application meta
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='career_site')
    referred_by = models.CharField(max_length=36, blank=True, null=True)  # Employee UUID

    application_date = models.DateTimeField(default=timezone.now)
    current_stage = models.CharField(max_length=20, choices=STAGE_CHOICES, default='application')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')

    # AI vetting
    ai_vetting_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    ai_vetting_notes = models.JSONField(default=dict, blank=True)

    # Screening & tags
    screening_status = models.CharField(max_length=20, choices=SCREENING_STATUS_CHOICES, default='pending')
    screening_score = models.FloatField(null=True, blank=True)
    screening_questions = models.JSONField(default=list, blank=True)
    tags = models.JSONField(default=list, blank=True)

    # Candidate details
    qualification = models.TextField(max_length=255, blank=True, null=True)
    experience = models.TextField(max_length=255, blank=True, null=True)
    knowledge_skill = models.TextField(blank=True, null=True)
    cover_letter = models.TextField(blank=True, null=True)
    employment_gaps = models.JSONField(default=list, blank=True)
    documents = models.JSONField(default=list, blank=True)
    compliance_status = models.JSONField(default=list, blank=True)
    interview_location = models.CharField(max_length=255, blank=True, null=True)

    # Disposition
    disposition_reason = models.CharField(max_length=255, blank=True, null=True)

    # Soft delete & timestamps
    is_deleted = models.BooleanField(default=False)
    applied_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()
    active_objects = ActiveApplicationsManager()

    class Meta:
        db_table = 'job_applications_job_application'
        unique_together = ('tenant_id', 'job_requisition_id', 'email', 'branch_id')
        indexes = [
            models.Index(fields=['tenant_id', 'job_requisition_id'], name='idx_candidates_tenant'),
            models.Index(fields=['status', 'current_stage'], name='idx_candidates_status'),
            models.Index(fields=['email', 'tenant_id'], name='idx_candidates_email'),
            models.Index(fields=['-ai_vetting_score'], name='idx_candidates_vetting'),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.job_requisition_id} ({self.tenant_id})"

    def save(self, *args, **kwargs):
        is_new = not self.pk
        if not self.id:
            import uuid
            self.id = str(uuid.uuid4())
        if not self.full_name:
            self.full_name = f"{self.first_name} {self.last_name}"
        super().save(*args, **kwargs)

    def soft_delete(self):
        if not self.is_deleted:
            self.is_deleted = True
            self.save()
            logger.info(f"JobApplication {self.id} soft-deleted for tenant {self.tenant_id}")

    def restore(self):
        if self.is_deleted:
            self.is_deleted = False
            self.save()
            logger.info(f"JobApplication {self.id} restored for tenant {self.tenant_id}")




class Schedule(models.Model):
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    TIMEZONE_CHOICES = [
        ('UTC', 'UTC'),
        ('America/New_York', 'Eastern Time (US)'),
        ('America/Chicago', 'Central Time (US)'),
        ('America/Los_Angeles', 'Pacific Time (US)'),
        ('Europe/London', 'London'),
        ('Asia/Tokyo', 'Tokyo'),
    ]

    id = models.CharField(primary_key=True, max_length=20, editable=False, unique=True)
    tenant_id = models.CharField(max_length=36, blank=False, null=False)  # Store Tenant ID
    branch_id = models.CharField(max_length=36, null=True, blank=True)    # Store Branch ID
    job_application_id = models.CharField(max_length=20, blank=False, null=False)  # Store JobApplication ID

    interview_start_date_time = models.DateTimeField()
    interview_end_date_time = models.DateTimeField(null=True, blank=True)
    meeting_mode = models.CharField(max_length=20, choices=[('Virtual', 'Virtual'), ('Physical', 'Physical')])
    meeting_link = models.URLField(max_length=255, blank=True, null=True)
    interview_address = models.TextField(max_length=255, blank=True, null=True)
    message = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    cancellation_reason = models.TextField(blank=True, null=True)
    timezone = models.CharField(max_length=100, choices=TIMEZONE_CHOICES, default='UTC')
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()

    class ActiveManager(models.Manager):
        def get_queryset(self):
            return super().get_queryset().filter(is_deleted=False)

    active_objects = ActiveManager()

    class Meta:
        db_table = 'job_applications_schedule'
        unique_together = ('tenant_id', 'job_application_id', 'interview_start_date_time', 'branch_id')
        constraints = [
            models.UniqueConstraint(
                fields=['job_application_id'],
                condition=models.Q(is_deleted=False, status='scheduled'),
                name='unique_active_schedule_per_application'
            )
        ]

    def __str__(self):
        return f"Schedule for {self.job_application_id} ({self.interview_start_date_time})"

    def save(self, *args, **kwargs):
        if not self.id:
            prefix = (self.tenant_id[:3].upper() if self.tenant_id else 'SCH')
            latest = Schedule.objects.filter(id__startswith=prefix).aggregate(models.Max('id'))['id__max']
            number = int(latest.split('-')[1]) + 1 if latest else 1
            self.id = f"{prefix}-{number:04d}"
        super().save(*args, **kwargs)

    def soft_delete(self):
        self.is_deleted = True
        self.save()
        logger.info(f"Schedule {self.id} soft-deleted for tenant {self.tenant_id}")

    def restore(self):
        self.is_deleted = False
        self.save()
        logger.info(f"Schedule {self.id} restored for tenant {self.tenant_id}")







