from django.db import models
from django.utils import timezone
from core.models import Tenant, Branch
from talent_engine.models import JobRequisition
import logging

logger = logging.getLogger('job_applications')

class ActiveApplicationsManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

class JobApplication(models.Model):
    STATUS_CHOICES = [
        ('new', 'New'),
        ('shortlisted', 'Shortlisted'),
        ('rejected', 'Rejected'),
        ('hired', 'Hired'),
    ]
    SCREENING_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processed', 'Processed'),
        ('failed', 'Failed'),
    ]

    id = models.CharField(primary_key=True, max_length=20, editable=False, unique=True)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='job_applications')
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True, related_name='job_applications')
    job_requisition = models.ForeignKey(JobRequisition, on_delete=models.CASCADE, related_name='applications')
    full_name = models.CharField(max_length=255)
    email = models.EmailField(max_length=255)
    phone = models.CharField(max_length=20)
    qualification = models.TextField(max_length=255)
    experience = models.TextField(max_length=255)
    knowledge_skill = models.TextField(blank=True, null=True)
    cover_letter = models.TextField(blank=True, null=True)
    resume_status = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    screening_status = models.CharField(max_length=20, choices=SCREENING_STATUS_CHOICES, default='pending')
    screening_score = models.FloatField(null=True, blank=True)
    employment_gaps = models.JSONField(default=list, blank=True)
    source = models.CharField(max_length=50, blank=True, null=True, default='Website')
    documents = models.JSONField(default=list, blank=True)
    compliance_status = models.JSONField(default=list, blank=True)
    interview_location = models.CharField(max_length=255, blank=True, null=True)
    is_deleted = models.BooleanField(default=False)
    applied_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    date_of_birth = models.DateField(blank=True, null=True)

    objects = models.Manager()
    active_objects = ActiveApplicationsManager()

    class Meta:
        db_table = 'job_applications_job_application'
        unique_together = ('tenant', 'job_requisition', 'email', 'branch')

    def __str__(self):
        return f"{self.full_name} - {self.job_requisition.title} ({self.tenant.name})"

    def save(self, *args, **kwargs):
        is_new = not self.pk
        if not self.id:
            prefix = self.tenant.name[:3].upper()
            latest = JobApplication.objects.filter(id__startswith=prefix).aggregate(models.Max('id'))['id__max']
            number = int(latest.split('-')[1]) + 1 if latest else 1
            self.id = f"{prefix}-{number:04d}"
        super().save(*args, **kwargs)
        if is_new:
            self.job_requisition.num_of_applications += 1
            self.job_requisition.save()

    # def soft_delete(self):
    #     self.is_deleted = True
    #     self.save()
    #     logger.info(f"JobApplication {self.id} soft-deleted for tenant {self.tenant.schema_name}")
    def soft_delete(self):
        if not self.is_deleted:
            self.is_deleted = True
            self.save()
            if self.job_requisition.num_of_applications > 0:
                self.job_requisition.num_of_applications -= 1
            # self.job_requisition.num_of_applications -= 1
            self.job_requisition.save()
            logger.info(f"JobApplication {self.id} soft-deleted for tenant {self.tenant.schema_name}")




    # def restore(self):
    #     self.is_deleted = False
    #     self.save()
    #     logger.info(f"JobApplication {self.id} restored for tenant {self.tenant.schema_name}")
    def restore(self):
        if self.is_deleted:
            self.is_deleted = False
            self.save()
            self.job_requisition.num_of_applications += 1
            self.job_requisition.save()
            logger.info(f"JobApplication {self.id} restored for tenant {self.tenant.schema_name}")


    def initialize_compliance_status(self, job_requisition):
        if not self.compliance_status:
            self.compliance_status = [
                {
                    "id": str(item["id"]),
                    "name": item["name"],
                    "description": item["description"],
                    "required": item["required"],
                    "status": "pending",
                    "checked_by": None,
                    "checked_at": None,
                    "notes": ""
                } for item in job_requisition.compliance_checklist
            ]
            self.save()
            logger.info(f"Initialized compliance status for application {self.id}")

    def update_compliance_status(self, item_id, status, checked_by=None, notes=""):
        for item in self.compliance_status:
            if str(item["id"]) == str(item_id):
                item["status"] = status
                item["checked_by"] = checked_by.id if checked_by else None
                item["checked_at"] = timezone.now().isoformat() if status != "pending" else None
                item["notes"] = notes
                self.save()
                logger.info(f"Updated compliance status for item {item_id} in application {self.id}")
                return item
        logger.warning(f"Compliance item {item_id} not found in application {self.id}")
        raise ValueError("Compliance item not found")




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
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='schedules')
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True, related_name='schedules')
    job_application = models.ForeignKey(JobApplication, on_delete=models.CASCADE, related_name='schedules')
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
    active_objects = models.Manager()

    class ActiveManager(models.Manager):
        def get_queryset(self):
            return super().get_queryset().filter(is_deleted=False)

    active_objects = ActiveManager()

    class Meta:
        db_table = 'job_applications_schedule'
        unique_together = ('tenant', 'job_application', 'interview_start_date_time', 'branch')
        constraints = [
            models.UniqueConstraint(
                fields=['job_application'],
                condition=models.Q(is_deleted=False, status='scheduled'),
                name='unique_active_schedule_per_application'
            )
        ]

    def __str__(self):
        return f"Schedule for {self.job_application.full_name} - {self.job_application.job_requisition.title} ({self.interview_start_date_time})"

    def save(self, *args, **kwargs):
        if not self.id:
            prefix = self.tenant.name[:3].upper()
            latest = Schedule.objects.filter(id__startswith=prefix).aggregate(models.Max('id'))['id__max']
            number = int(latest.split('-')[1]) + 1 if latest else 1
            self.id = f"{prefix}-{number:04d}"
        super().save(*args, **kwargs)

    def soft_delete(self):
        self.is_deleted = True
        self.save()
        logger.info(f"Schedule {self.id} soft-deleted for tenant {self.tenant.schema_name}")

    def restore(self):
        self.is_deleted = False
        self.save()
        logger.info(f"Schedule {self.id} restored for tenant {self.tenant.schema_name}")







