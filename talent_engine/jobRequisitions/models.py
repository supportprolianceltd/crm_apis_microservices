# talent_engine/jobRequisitions/models.py
from django.db import models
from django.utils.text import slugify
from django.utils import timezone
import uuid
import logging
from django.core.exceptions import ValidationError
from django.conf import settings
from kafka import KafkaProducer
import json

logger = logging.getLogger('jobRequisitions')

def validate_compliance_checklist(value):
    if not isinstance(value, list):
        raise ValidationError("Compliance checklist must be a list.")
    for item in value:
        if not isinstance(item, dict) or 'name' not in item:
            raise ValidationError("Each compliance item must be a dictionary with a 'name' field.")

class ActiveRequisitionsManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


# class JobRequisition(models.Model):
 
#     tenant_name = models.CharField(max_length=255, blank=True, null=True, help_text="Tenant name for code generation")


#     STATUS_CHOICES = [
#         ('open', 'Open'),
#         ('pending', 'Pending'),
#         ('closed', 'Closed'),
#         ('rejected', 'Rejected'),
#         ('draft', 'Draft'),
#         ('pending_approval', 'Pending Approval'),
#         ('approved', 'Approved'),
#         ('on_hold', 'On Hold'),
     
#     ]
#     ROLE_CHOICES = [
#         ('staff', 'Staff'),
#         ('admin', 'Admin'),
#     ]
#     JOB_TYPE_CHOICES = [
#         ('full_time', 'Full-time'),
#         ('part_time', 'Part-time'),
#         ('contract', 'Contract'),
#         ('freelance', 'Freelance'),
#         ('internship', 'Internship'),
#         ('temporary', 'Temporary'),
#     ]
#     LOCATION_TYPE_CHOICES = [
#         ('on_site', 'On-site'),
#         ('remote', 'Remote'),
#         ('hybrid', 'Hybrid'),
#     ]
#     POSITION_TYPE_CHOICES = [
#         ('permanent', 'Permanent'),
#         ('contract', 'Contract'),
#         ('internship', 'Internship'),
#     ]
#     URGENCY_LEVEL_CHOICES = [
#         ('critical', 'Critical'),
#         ('high', 'High'),
#         ('medium', 'Medium'),
#         ('low', 'Low'),
#     ]

#     id = models.CharField(primary_key=True, max_length=20, editable=False, unique=True)
#     requisition_number = models.CharField(max_length=50, unique=True, blank=True, null=True)
#     job_requisition_code = models.CharField(max_length=50, unique=True, blank=True, null=True)
#     job_application_code = models.CharField(max_length=50, unique=True, blank=True, null=True)
#     compliance_checklist = models.JSONField(default=list, blank=True, validators=[validate_compliance_checklist])
#     last_compliance_check = models.DateTimeField(null=True, blank=True)
#     checked_by = models.CharField(max_length=255, null=True, blank=True)


#     tenant_id = models.CharField(max_length=255, blank=False, null=False)  # Store Tenant ID
#     branch_id = models.CharField(max_length=36, blank=True, null=True)  # Store Branch ID
#     department_id = models.CharField(max_length=36, blank=True, null=True)  # Store Department ID
#     hiring_manager_id = models.CharField(max_length=36, blank=True, null=True)  # Store Department ID

#     title = models.CharField(max_length=255)
#     unique_link = models.CharField(max_length=255, unique=True, blank=True, editable=False)
#     status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
#     role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='staff')

#     requested_by_id = models.CharField(max_length=36, blank=True, null=True)  # Store CustomUser ID
#     approved_by_id = models.CharField(max_length=36, blank=True, null=True)  # Store CustomUser ID
#     created_by_id = models.CharField(max_length=36, blank=True, null=True)  # Store CustomUser ID
#     updated_by_id = models.CharField(max_length=36, blank=True, null=True)  # Store CustomUser ID

#     company_name = models.CharField(max_length=255, blank=True, null=True)
#     company_address = models.TextField(blank=True, null=True)

#     job_type = models.CharField(max_length=20, choices=JOB_TYPE_CHOICES, default='full_time')
#     position_type = models.CharField(max_length=20, choices=POSITION_TYPE_CHOICES, default='permanent')
#     location_type = models.CharField(max_length=20, choices=LOCATION_TYPE_CHOICES, default='on_site')

#     job_location = models.TextField(blank=True, null=True)
#     interview_location = models.CharField(max_length=255, blank=True)

#     salary_range = models.CharField(max_length=255, blank=True, null=True)

#     salary_range_min = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
#     salary_range_max = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

#     job_description = models.TextField(blank=True, null=True)
#     requirements = models.JSONField(default=list, blank=True)
#     qualification_requirement = models.TextField(blank=True, null=True)
#     experience_requirement = models.TextField(blank=True, null=True)
#     knowledge_requirement = models.TextField(blank=True, null=True)

#     number_of_candidates = models.IntegerField(blank=True, null=True)
   
#     num_of_applications = models.IntegerField(default=0, blank=True, null=True)
   
#     urgency_level = models.CharField(max_length=20, choices=URGENCY_LEVEL_CHOICES, default='medium')

#     reason = models.TextField(blank=True, null=True)
#     deadline_date = models.DateField(blank=True, null=True)
#     start_date = models.DateField(blank=True, null=True)
#     responsibilities = models.JSONField(default=list, blank=True)
#     compliance_checklist = models.JSONField(default=list, blank=True)
#     documents_required = models.JSONField(default=list, blank=True)

#     approval_workflow = models.JSONField(default=dict, blank=True)
#     current_approval_stage = models.IntegerField(default=0)
#     approval_date = models.DateTimeField(null=True, blank=True)
#     time_to_fill_days = models.IntegerField(null=True, blank=True)


#     advert_banner = models.ImageField(upload_to='advert_banners/', blank=True, null=True, max_length=512)
#     advert_banner_url = models.CharField(max_length=1024, blank=True, null=True)

#     requested_date = models.DateField(auto_now_add=True)
#     publish_status = models.BooleanField(default=False)
#     is_deleted = models.BooleanField(default=False)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)
#     comment = models.TextField(blank=True, null=True, help_text="User comment for the Job Requisition")

#     objects = models.Manager()
#     active_objects = ActiveRequisitionsManager()

#     class Meta:
#         db_table = 'talent_engine_job_requisition'
#         indexes = [
#             models.Index(fields=['tenant_id', 'status'], name='idx_req_tenant_status'),
#             models.Index(fields=['department_id', 'job_type'], name='idx_req_department'),
#             models.Index(fields=['requested_by_id', 'approval_date'], name='idx_req_approval'),
#         ]

#     def __str__(self):
#         return f"{self.title} ({self.tenant_id})"

#     def save(self, *args, **kwargs):
#         is_new = self._state.adding
#         # Use tenant_name for prefix if available, else fallback to tenant_id
#         prefix = (self.tenant_name[:3].upper() if self.tenant_name else (self.tenant_id[:3].upper() if self.tenant_id else 'REQ'))
#         if not self.id:
#             latest = JobRequisition.objects.filter(id__startswith=prefix).aggregate(models.Max('id'))['id__max']
#             number = int(latest.split('-')[1]) + 1 if latest else 1
#             self.id = f"{prefix}-{number:04d}"

#         if not self.unique_link:
#             base_slug = slugify(f"{self.title}")
#             short_uuid = str(uuid.uuid4())[:8]
#             # Add tenant_id as the first part of the unique_link
#             slug = f"{self.tenant_id}-{prefix}-{base_slug}-{short_uuid}"
#             counter = 1
#             original_slug = slug
#             while JobRequisition.objects.filter(unique_link=slug).exists():
#                 slug = f"{original_slug}-{counter}"
#                 counter += 1
#             self.unique_link = slug

#         if not self.job_requisition_code:
#             code_prefix = prefix
#             latest_code = JobRequisition.objects.filter(job_requisition_code__startswith=f"{code_prefix}-JR-").order_by('-job_requisition_code').first()
#             new_number = int(latest_code.job_requisition_code.split('-')[-1]) + 1 if latest_code and latest_code.job_requisition_code else 1
#             self.job_requisition_code = f"{code_prefix}-JR-{new_number:04d}"

#         if not self.job_application_code:
#             code_prefix = prefix
#             latest_app_code = JobRequisition.objects.filter(job_application_code__startswith=f"{code_prefix}-JA-").order_by('-job_application_code').first()
#             new_number = int(latest_app_code.job_application_code.split('-')[-1]) + 1 if latest_app_code and latest_app_code.job_application_code else 1
#             self.job_application_code = f"{code_prefix}-JA-{new_number:04d}"

#         super().save(*args, **kwargs)
#         logger.info(f"JobRequisition {self.id} {'created' if is_new else 'updated'} for tenant {self.tenant_id}")

#     def soft_delete(self):
#         self.is_deleted = True
#         self.save()
#         logger.info(f"JobRequisition {self.id} soft-deleted for tenant {self.tenant_id}")

#     def restore(self):
#         self.is_deleted = False
#         self.save()
#         logger.info(f"JobRequisition {self.id} restored for tenant {self.tenant_id}")

#     # def add_compliance_item(self, name, description='', required=True, status='pending', checked_by=None, checked_at=None):
#     #     new_item = {
#     #         'id': str(uuid.uuid4()),
#     #         'name': name,
#     #         'description': description,
#     #         'required': required,
#     #         'status': status,
#     #         'checked_by': checked_by,
#     #         'checked_at': checked_at
#     #     }
#     #     self.compliance_checklist.append(new_item)
#     #     self.last_compliance_check = checked_at or self.last_compliance_check
#     #     self.checked_by = checked_by or self.checked_by
#     #     self.save()
#     #     return new_item

#     # def update_compliance_item(self, item_id, **kwargs):
#     #     for item in self.compliance_checklist:
#     #         if item["id"] == item_id:
#     #             item.update(kwargs)
#     #             if 'status' in kwargs and kwargs['status'] in ['completed', 'failed']:
#     #                 item['checked_at'] = kwargs.get('checked_at', timezone.now().isoformat())
#     #                 item['checked_by'] = kwargs.get('checked_by', item.get('checked_by'))
#     #                 self.last_compliance_check = item['checked_at']
#     #                 self.checked_by = item['checked_by']
#     #             self.save()
#     #             logger.info(f"Updated compliance item {item_id} for requisition {self.id}")
#     #             return item
#     #     logger.warning(f"Compliance item {item_id} not found in requisition {self.id}")
#     #     raise ValueError("Compliance item not found")

#     # def remove_compliance_item(self, item_id):
#     #     original_length = len(self.compliance_checklist)
#     #     self.compliance_checklist = [item for item in self.compliance_checklist if item["id"] != item_id]
#     #     if len(self.compliance_checklist) < original_length:
#     #         self.save()
#     #         logger.info(f"Removed compliance item {item_id} from requisition {self.id}")
#     #     else:
#     #         logger.warning(f"Compliance item {item_id} not found in requisition {self.id}")
#     #         raise ValueError("Compliance item not found")



#     def approve(self, approver_id):
#         """
#         Mark this job requisition as approved.
#         Sets status to 'approved', approval_date to now, and approved_by_id to the given user ID.
#         """
#         self.status = 'approved'
#         self.approval_date = timezone.now()
#         self.approved_by_id = approver_id
#         self.save(update_fields=["status", "approval_date", "approved_by_id", "updated_at"])
#         logger.info(f"JobRequisition {self.id} approved by user {approver_id} for tenant {self.tenant_id}")




class JobRequisition(models.Model):
    # New JSONFields for user details (populated from JWT at create/update)
    requested_by_details = models.JSONField(default=dict, blank=True, help_text="Details of requester from JWT")
    created_by_details = models.JSONField(default=dict, blank=True, help_text="Details of creator from JWT")
    updated_by_details = models.JSONField(default=dict, blank=True, help_text="Details of last updater from JWT")
    approved_by_details = models.JSONField(default=dict, blank=True, help_text="Details of approver from JWT")

    # New CharField for domain (populated from JWT)
    tenant_domain = models.CharField(max_length=255, blank=True, null=True, help_text="Tenant domain from JWT")

    # New CharField for schema (populated from JWT for ID prefix)
    tenant_schema = models.CharField(max_length=255, blank=True, null=True, help_text="Tenant schema from JWT for code prefix")

    tenant_name = models.CharField(max_length=255, blank=True, null=True, help_text="Tenant name for code generation")

    STATUS_CHOICES = [
        ('open', 'Open'),
        ('pending', 'Pending'),
        ('closed', 'Closed'),
        ('rejected', 'Rejected'),
        ('draft', 'Draft'),
        ('pending_approval', 'Pending Approval'),
        ('approved', 'Approved'),
        ('on_hold', 'On Hold'),
    ]
    ROLE_CHOICES = [
        ('staff', 'Staff'),
        ('admin', 'Admin'),
    ]
    JOB_TYPE_CHOICES = [
        ('full_time', 'Full-time'),
        ('part_time', 'Part-time'),
        ('contract', 'Contract'),
        ('freelance', 'Freelance'),
        ('internship', 'Internship'),
        ('temporary', 'Temporary'),
    ]
    LOCATION_TYPE_CHOICES = [
        ('on_site', 'On-site'),
        ('remote', 'Remote'),
        ('hybrid', 'Hybrid'),
    ]
    POSITION_TYPE_CHOICES = [
        ('permanent', 'Permanent'),
        ('contract', 'Contract'),
        ('internship', 'Internship'),
    ]
    URGENCY_LEVEL_CHOICES = [
        ('critical', 'Critical'),
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
    ]

    id = models.CharField(primary_key=True, max_length=20, editable=False, unique=True)
    requisition_number = models.CharField(max_length=50, unique=True, blank=True, null=True)
    job_requisition_code = models.CharField(max_length=50, unique=True, blank=True, null=True)
    job_application_code = models.CharField(max_length=50, unique=True, blank=True, null=True)
    compliance_checklist = models.JSONField(default=list, blank=True, validators=[validate_compliance_checklist])
    last_compliance_check = models.DateTimeField(null=True, blank=True)
    checked_by = models.CharField(max_length=255, null=True, blank=True)

    tenant_id = models.CharField(max_length=255, blank=False, null=False)  # Store Tenant ID
    department_id = models.CharField(max_length=36, blank=True, null=True)  # Store Department ID
    hiring_manager_id = models.CharField(max_length=36, blank=True, null=True)  # Store Hiring Manager ID

    title = models.CharField(max_length=255)
    unique_link = models.CharField(max_length=255, unique=True, blank=True, editable=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='staff')

    requested_by_id = models.CharField(max_length=36, blank=True, null=True)  # Store CustomUser ID
    approved_by_id = models.CharField(max_length=36, blank=True, null=True)  # Store CustomUser ID
    created_by_id = models.CharField(max_length=36, blank=True, null=True)  # Store CustomUser ID
    updated_by_id = models.CharField(max_length=36, blank=True, null=True)  # Store CustomUser ID

    company_name = models.CharField(max_length=255, blank=True, null=True)
    company_address = models.TextField(blank=True, null=True)

    job_type = models.CharField(max_length=20, choices=JOB_TYPE_CHOICES, default='full_time')
    position_type = models.CharField(max_length=20, choices=POSITION_TYPE_CHOICES, default='permanent')
    location_type = models.CharField(max_length=20, choices=LOCATION_TYPE_CHOICES, default='on_site')

    job_location = models.TextField(blank=True, null=True)
    interview_location = models.CharField(max_length=255, blank=True)

    salary_range = models.CharField(max_length=255, blank=True, null=True)

    salary_range_min = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    salary_range_max = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    job_description = models.TextField(blank=True, null=True)
    requirements = models.JSONField(default=list, blank=True)
    qualification_requirement = models.TextField(blank=True, null=True)
    experience_requirement = models.TextField(blank=True, null=True)
    knowledge_requirement = models.TextField(blank=True, null=True)

    number_of_candidates = models.IntegerField(blank=True, null=True)
   
    num_of_applications = models.IntegerField(default=0, blank=True, null=True)
   
    urgency_level = models.CharField(max_length=20, choices=URGENCY_LEVEL_CHOICES, default='medium')

    reason = models.TextField(blank=True, null=True)
    deadline_date = models.DateField(blank=True, null=True)
    start_date = models.DateField(blank=True, null=True)
    responsibilities = models.JSONField(default=list, blank=True)
    documents_required = models.JSONField(default=list, blank=True)

    approval_workflow = models.JSONField(default=dict, blank=True)
    current_approval_stage = models.IntegerField(default=0)
    approval_date = models.DateTimeField(null=True, blank=True)
    time_to_fill_days = models.IntegerField(null=True, blank=True)

    advert_banner = models.ImageField(upload_to='advert_banners/', blank=True, null=True, max_length=512)
    advert_banner_url = models.CharField(max_length=1024, blank=True, null=True)

    requested_date = models.DateField(auto_now_add=True)
    publish_status = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    comment = models.TextField(blank=True, null=True, help_text="User comment for the Job Requisition")

    objects = models.Manager()
    active_objects = ActiveRequisitionsManager()

    class Meta:
        db_table = 'talent_engine_job_requisition'
        indexes = [
            models.Index(fields=['tenant_id', 'status'], name='idx_req_tenant_status'),
            models.Index(fields=['department_id', 'job_type'], name='idx_req_department'),
            models.Index(fields=['requested_by_id', 'approval_date'], name='idx_req_approval'),
        ]

    def __str__(self):
        return f"{self.title} ({self.tenant_id})"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        # Use tenant_schema for prefix if available, else fallback to 'REQ'
        prefix = (self.tenant_schema[:3].upper() if self.tenant_schema else 'REQ')
        if not self.id:
            latest = JobRequisition.objects.filter(id__startswith=prefix).aggregate(models.Max('id'))['id__max']
            number = int(latest.split('-')[1]) + 1 if latest else 1
            self.id = f"{prefix}-{number:04d}"

        if not self.unique_link:
            base_slug = slugify(f"{self.title}")
            short_uuid = str(uuid.uuid4())[:8]
            # Add tenant_id as the first part of the unique_link
            slug = f"{self.tenant_id}-{prefix}-{base_slug}-{short_uuid}"
            counter = 1
            original_slug = slug
            while JobRequisition.objects.filter(unique_link=slug).exists():
                slug = f"{original_slug}-{counter}"
                counter += 1
            self.unique_link = slug

        if not self.job_requisition_code:
            code_prefix = prefix
            latest_code = JobRequisition.objects.filter(job_requisition_code__startswith=f"{code_prefix}-JR-").order_by('-job_requisition_code').first()
            new_number = int(latest_code.job_requisition_code.split('-')[-1]) + 1 if latest_code and latest_code.job_requisition_code else 1
            self.job_requisition_code = f"{code_prefix}-JR-{new_number:04d}"

        if not self.job_application_code:
            code_prefix = prefix
            latest_app_code = JobRequisition.objects.filter(job_application_code__startswith=f"{code_prefix}-JA-").order_by('-job_application_code').first()
            new_number = int(latest_app_code.job_application_code.split('-')[-1]) + 1 if latest_app_code and latest_app_code.job_application_code else 1
            self.job_application_code = f"{code_prefix}-JA-{new_number:04d}"

        super().save(*args, **kwargs)
        logger.info(f"JobRequisition {self.id} {'created' if is_new else 'updated'} for tenant {self.tenant_id}")

    def soft_delete(self):
        self.is_deleted = True
        self.save()
        logger.info(f"JobRequisition {self.id} soft-deleted for tenant {self.tenant_id}")

    def restore(self):
        self.is_deleted = False
        self.save()
        logger.info(f"JobRequisition {self.id} restored for tenant {self.tenant_id}")

    def approve(self, approver_id, approver_details=None):
        """
        Mark this job requisition as approved.
        Sets status to 'approved', approval_date to now, and approved_by_id to the given user ID.
        """
        self.status = 'approved'
        self.approval_date = timezone.now()
        self.approved_by_id = approver_id
        if approver_details:
            self.approved_by_details = approver_details
        self.save(update_fields=["status", "approval_date", "approved_by_id", "approved_by_details", "updated_at"])
        logger.info(f"JobRequisition {self.id} approved by user {approver_id} for tenant {self.tenant_id}")





class VideoSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job_application_id = models.CharField(max_length=20, blank=False, null=False)  # Reference JobApplication ID from job_applications
    tenant_id = models.CharField(max_length=36, blank=False, null=False)  # Reference Tenant ID from auth_service
    created_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    recording_url = models.URLField(null=True, blank=True)
    meeting_id = models.CharField(max_length=50, unique=True, default=uuid.uuid4)  # Unique meeting ID for WebRTC
    scores = models.JSONField(default=dict, blank=True)  # Store scores {technical: 0, communication: 0, problemSolving: 0}
    notes = models.TextField(blank=True, null=True)  # Store interviewer notes
    tags = models.JSONField(default=list, blank=True)  # Store tags like ["Frontend", "Leadership"]

    class Meta:
        db_table = 'video_session'

    def __str__(self):
        return f"Video Session {self.id} for Job Application {self.job_application_id} ({self.tenant_id})"

    def end_session(self):
        self.is_active = False
        self.ended_at = timezone.now()
        self.save()
        logger.info(f"Video session {self.id} ended for tenant {self.tenant_id}")

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        if is_new:
            producer = KafkaProducer(bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS, value_serializer=lambda v: json.dumps(v).encode('utf-8'))
            producer.send('video-session-events', {
                'id': str(self.id),
                'job_application_id': self.job_application_id,
                'tenant_id': self.tenant_id,
                'action': 'created'
            })
            producer.flush()
            logger.info(f"Video session {self.id} created for tenant {self.tenant_id}")



class Participant(models.Model):
    session = models.ForeignKey(
        VideoSession,
        on_delete=models.CASCADE,
        related_name='participants'
    )
    user_id = models.CharField(max_length=36, null=True, blank=True)  # Reference CustomUser ID from auth_service
    candidate_email = models.EmailField(max_length=255, null=True, blank=True)
    is_muted = models.BooleanField(default=False)
    is_camera_on = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'video_participant'

    def __str__(self):
        if self.user_id:
            return f"User {self.user_id} in {self.session}"
        elif self.candidate_email:
            return f"{self.candidate_email} in {self.session}"
        return f"Participant in {self.session}"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        if is_new:
            producer = KafkaProducer(bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS, value_serializer=lambda v: json.dumps(v).encode('utf-8'))
            producer.send('participant-events', {
                'id': str(self.id),
                'session_id': str(self.session.id),
                'user_id': self.user_id,
                'candidate_email': self.candidate_email,
                'tenant_id': self.session.tenant_id,
                'action': 'created'
            })
            producer.flush()
            logger.info(f"Participant created for session {self.session.id}")



# class Request(models.Model):
#     REQUEST_TYPE_CHOICES = [
#         ('material', 'Material Request'),
#         ('leave', 'Leave Request'),
#     ]
#     STATUS_CHOICES = [
#         ('pending', 'Pending'),
#         ('approved', 'Approved'),
#         ('rejected', 'Rejected'),
#         ('cancelled', 'Cancelled'),
#         ('completed', 'Completed'),
#     ]

#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     tenant_id = models.CharField(max_length=36, blank=False, null=False)  # Reference Tenant ID
#     branch_id = models.CharField(max_length=36, null=True, blank=True)  # Reference Branch ID
#     requested_by_id = models.CharField(max_length=36, null=True, blank=True)  # Reference CustomUser ID
#     approved_by_id = models.CharField(max_length=36, null=True, blank=True)  # Reference CustomUser ID for approver
#     approved_by_details = models.JSONField(default=dict, blank=True, null=True, help_text="Details of the user who approved the request")
#     request_type = models.CharField(max_length=20, choices=REQUEST_TYPE_CHOICES)
#     title = models.CharField(max_length=255)
#     description = models.TextField(blank=True, null=True)
#     status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
#     details = models.JSONField(default=dict, blank=True, help_text="Extra details specific to the request type")
#     comment = models.TextField(blank=True, null=True)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)
#     is_deleted = models.BooleanField(default=False)

#     class Meta:
#         db_table = 'crm_request'
#         ordering = ['-created_at']

#     def __str__(self):
#         return f"{self.get_request_type_display()} by {self.requested_by_id or 'Unknown'} ({self.status})"

#     def soft_delete(self):
#         self.is_deleted = True
#         self.save()
#         logger.info(f"Request {self.id} soft-deleted for tenant {self.tenant_id}")

#     def restore(self):
#         self.is_deleted = False
#         self.save()
#         logger.info(f"Request {self.id} restored for tenant {self.tenant_id}")

#     def save(self, *args, **kwargs):
#         is_new = self._state.adding
#         super().save(*args, **kwargs)
#         if is_new:
#             producer = KafkaProducer(bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS, value_serializer=lambda v: json.dumps(v).encode('utf-8'))
#             producer.send('request-events', {
#                 'id': str(self.id),
#                 'tenant_id': self.tenant_id,
#                 'branch_id': self.branch_id,
#                 'requested_by_id': self.requested_by_id,
#                 'approved_by_id': self.approved_by_id,
#                 'request_type': self.request_type,
#                 'title': self.title,
#                 'action': 'created'
#             })
#             producer.flush()
#             logger.info(f"Request {self.id} created for tenant {self.tenant_id}")




class Request(models.Model):
    REQUEST_TYPE_CHOICES = [
        ('material', 'Material Request'),
        ('leave', 'Leave Request'),
        ('service', 'Service Request'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
    ]

    # Material Request Choices
    MATERIAL_TYPE_CHOICES = [
        ('ppe', 'PPE'),
        ('consumables', 'Consumables'),
        ('equipment', 'Equipment'),
        ('others', 'Others'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ]

    # Leave Request Choices
    LEAVE_CATEGORY_CHOICES = [
        ('annual', 'Annual'),
        ('casual', 'Casual'),
        ('sick', 'Sick'),
        ('study', 'Study'),
        ('others', 'Others'),
    ]
    
    REGION_CHOICES = [
        ('abroad', 'Abroad'),
        ('local', 'Local'),
    ]

    # Service Request Choices
    SERVICE_TYPE_CHOICES = [
        ('logistics', 'Logistics (e.g., transportation, storage)'),
        ('training', 'Training (e.g., workshops, courses)'),
        ('maintenance', 'Maintenance (e.g., equipment, facilities)'),
        ('it_support', 'IT Support (e.g., hardware, software)'),
        ('administrative_support', 'Administrative Support (e.g., documentation, supplies)'),
        ('other', 'Other (please specify)'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant_id = models.CharField(max_length=36, blank=False, null=False)
    branch_id = models.CharField(max_length=36, null=True, blank=True)
    requested_by_id = models.CharField(max_length=36, null=True, blank=True)
    approved_by_id = models.CharField(max_length=36, null=True, blank=True)
    cancelled_by_id = models.CharField(max_length=36, null=True, blank=True)
    rejected_by_id = models.CharField(max_length=36, null=True, blank=True)
    requested_by_details = models.JSONField(default=dict, blank=True, null=True, help_text="Details of the user who requested the request")
    approved_by_details = models.JSONField(default=dict, blank=True, null=True, help_text="Details of the user who approved the request")
    cancelled_by_details = models.JSONField(default=dict, blank=True, null=True, help_text="Details of the user who cancelled the request")
    rejected_by_details = models.JSONField(default=dict, blank=True, null=True, help_text="Details of the user who rejected the request")
    
    # Basic request info
    request_type = models.CharField(max_length=20, choices=REQUEST_TYPE_CHOICES)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    comment = models.TextField(blank=True, null=True)
    
    # File attachments
    supporting_document = models.FileField(upload_to='request_documents/', blank=True, null=True)
    supporting_document_url = models.CharField(max_length=1024, blank=True, null=True)
    additional_attachment = models.FileField(upload_to='request_attachments/', blank=True, null=True)
    additional_attachment_url = models.CharField(max_length=1024, blank=True, null=True)
    
    # Material Request Fields
    item_name = models.CharField(max_length=255, blank=True, null=True)
    material_type = models.CharField(max_length=20, choices=MATERIAL_TYPE_CHOICES, blank=True, null=True)
    request_id = models.CharField(max_length=50, blank=True, null=True, unique=True)
    item_specification = models.TextField(blank=True, null=True)
    quantity_needed = models.IntegerField(blank=True, null=True)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, blank=True, null=True)
    reason_for_request = models.TextField(blank=True, null=True)
    needed_date = models.DateField(blank=True, null=True)
    
    # Leave Request Fields
    leave_category = models.CharField(max_length=20, choices=LEAVE_CATEGORY_CHOICES, blank=True, null=True)
    number_of_days = models.IntegerField(blank=True, null=True)
    start_date = models.DateField(blank=True, null=True)
    resumption_date = models.DateField(blank=True, null=True)
    region_of_stay = models.CharField(max_length=20, choices=REGION_CHOICES, blank=True, null=True)
    address_during_leave = models.TextField(blank=True, null=True)
    contact_phone_number = models.CharField(max_length=20, blank=True, null=True)
    additional_information = models.TextField(blank=True, null=True)
    
    # Service Request Fields
    service_type = models.CharField(max_length=30, choices=SERVICE_TYPE_CHOICES, blank=True, null=True)
    service_description = models.TextField(blank=True, null=True)
    priority_level = models.CharField(max_length=20, choices=PRIORITY_CHOICES, blank=True, null=True)
    desired_completion_date = models.DateField(blank=True, null=True)
    requester_name = models.CharField(max_length=255, blank=True, null=True)
    requester_department = models.CharField(max_length=255, blank=True, null=True)
    requester_contact_info = models.TextField(blank=True, null=True)
    special_instructions = models.TextField(blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        db_table = 'crm_request'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['request_type', 'status']),
            models.Index(fields=['tenant_id', 'created_at']),
            models.Index(fields=['request_id']),
        ]

    def __str__(self):
        return f"{self.get_request_type_display()} - {self.title} ({self.status})"

    def save(self, *args, **kwargs):
        # Generate request ID if not provided for ALL request types
        if not self.request_id:
            # Use a while loop to handle potential race conditions
            max_attempts = 5
            for attempt in range(max_attempts):
                try:
                    self.request_id = self._generate_request_id()
                    # Test if this ID already exists (race condition protection)
                    if not Request.objects.filter(request_id=self.request_id).exists():
                        break
                    if attempt == max_attempts - 1:
                        # Last attempt, use a UUID fallback
                        import uuid
                        self.request_id = f"{self._get_prefix()}-{uuid.uuid4().hex[:8].upper()}"
                except Exception as e:
                    logger.error(f"Error generating request ID on attempt {attempt + 1}: {str(e)}")
                    if attempt == max_attempts - 1:
                        import uuid
                        self.request_id = f"{self._get_prefix()}-{uuid.uuid4().hex[:8].upper()}"
        
        is_new = self._state.adding
        try:
            super().save(*args, **kwargs)
            
            if is_new:
                self._send_kafka_event('created')
        except Exception as e:
            logger.error(f"Error saving request: {str(e)}")
            raise

    def _get_prefix(self):
        """Get prefix for request type"""
        prefix_map = {
            'material': 'MAT',
            'leave': 'LEV', 
            'service': 'SER',
        }
        return prefix_map.get(self.request_type, 'REQ')

    def _generate_request_id(self):
        """Generate unique request ID for all request types"""
        prefix = self._get_prefix()
        timestamp = timezone.now().strftime('%Y%m%d')
        
        # Use database aggregation to avoid race conditions
        try:
            last_request = Request.objects.filter(
                request_type=self.request_type,
                request_id__startswith=f"{prefix}-{timestamp}"
            ).order_by('-created_at').first()
            
            if last_request and last_request.request_id:
                try:
                    last_number = int(last_request.request_id.split('-')[-1])
                    next_number = last_number + 1
                except (ValueError, IndexError):
                    next_number = 1
            else:
                next_number = 1
                
            return f"{prefix}-{timestamp}-{next_number:04d}"
        except Exception as e:
            logger.error(f"Error in _generate_request_id: {str(e)}")
            # Fallback: use timestamp with random component
            import random
            random_suffix = random.randint(1000, 9999)
            return f"{prefix}-{timestamp}-{random_suffix:04d}"
        
        
    def _send_kafka_event(self, action):
        """Send Kafka event for request creation"""
        try:
            producer = KafkaProducer(
                bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS, 
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            producer.send('request-events', {
                'id': str(self.id),
                'tenant_id': self.tenant_id,
                'branch_id': self.branch_id,
                'requested_by_id': self.requested_by_id,
                'request_type': self.request_type,
                'title': self.title,
                'action': action
            })
            producer.flush()
            logger.info(f"Request {self.id} {action} for tenant {self.tenant_id}")
        except Exception as e:
            logger.error(f"Failed to send Kafka event for request {self.id}: {str(e)}")

    def soft_delete(self):
        self.is_deleted = True
        self.save()
        self._send_kafka_event('deleted')
        logger.info(f"Request {self.id} soft-deleted for tenant {self.tenant_id}")



    def restore(self):
        self.is_deleted = False
        self.save()
        logger.info(f"Request {self.id} restored for tenant {self.tenant_id}")

