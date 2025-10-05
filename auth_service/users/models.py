# users/models.py (full corrected version - remove/avoid serializers import in models)

from django.db import models
from django.contrib.auth.models import AbstractUser, UserManager
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from core.models import Tenant, Module, Branch
from django.db.models import Max
import uuid
import logging
from django_tenants.utils import tenant_context
from django.utils.timezone import now
logger = logging.getLogger('users')

def generate_kid():
    return uuid.uuid4().hex

def today():
    return timezone.now().date()



class CustomUserManager(UserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        username = extra_fields.pop('username', None) or email
        return super().create_user(
            username,
            email=email,
            password=password,
            **extra_fields
        )

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        return self.create_user(email, password, **extra_fields)

    def get_by_email(self, email, tenant):
        """Cached user lookup by email in tenant."""
        from auth_service.utils.cache import get_cache_key, get_from_cache, set_to_cache
        from auth_service.serializers import CustomUserMinimalSerializer  # Lazy import here if needed, but avoid in models
        key = get_cache_key(tenant.schema_name, 'customuser', email)
        user_data = get_from_cache(key)
        if user_data is None:
            with tenant_context(tenant):
                user = self.filter(email=email, tenant=tenant).first()
                if user:
                    user_data = CustomUserMinimalSerializer(user).data
                    set_to_cache(key, user_data, timeout=900)  # 15 min
                    return user
                return None
        # Reconstruct user from cached data if needed (minimal; full query for safety)
        with tenant_context(tenant):
            user = self.filter(email=email, tenant=tenant).first()
            return user

class CustomUser(AbstractUser):
    ROLES = (
        ('admin', 'Admin'),
        ('root-admin', 'Root-Admin'),
        ('co-admin', 'Co-Admin'),
        ('hr', 'HR'),
        ('staff', 'Staff'),
        ('user', 'User'),
        ('carer', 'Carer'),
        ('client', 'Client'),
        ('family', 'Family'),
        ('auditor', 'Auditor'),
        ('tutor', 'Tutor'),
        ('assessor', 'Assessor'),
        ('iqa', 'IQA'),
        ('eqa', 'EQA'),
        ('recruiter', 'Recruiter'),
        ('team_manager', 'Team Manager'),
    )

    DASHBOARD_TYPES = (
        ('admin', 'Admin'),
        ('staff', 'Staff'),
        ('user', 'User'),
    )

    ACCESS_LEVELS = (
        ('full', 'Full Access'),
        ('limited', 'Limited Access'),
    )

    STATUS_CHOICES = (
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('suspended', 'Suspended'),
    )

    TWO_FACTOR_CHOICES = (
        ('enable', 'Enable'),
        ('disable', 'Disable'),
    )

    last_password_reset = models.DateTimeField(null=True, blank=True)
    username = models.CharField(max_length=150, blank=True, null=True, unique=False)
    email = models.EmailField(_('email address'), unique=True)
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    role = models.CharField(max_length=20, choices=ROLES, default='carer')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    permission_levels = models.JSONField(default=list, blank=True)
    job_role = models.CharField(max_length=255, blank=True, null=True, default='user')
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, null=True)
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True)
    has_accepted_terms = models.BooleanField(default=False, help_text="Indicates if the user has accepted the terms and conditions.")
    is_locked = models.BooleanField(default=False, help_text="Indicates if the user account is locked.")
    login_attempts = models.PositiveIntegerField(default=0, help_text="Number of consecutive failed login attempts.")

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    def __str__(self):
        return self.email

    def lock_account(self, reason="Manual lock"):
        """Lock the user account with a reason."""
        self.is_locked = True
        self.save()
        logger.info(f"Account locked for user {self.email} in tenant {self.tenant.schema_name}. Reason: {reason}")

    def unlock_account(self):
        """Unlock the user account and reset login attempts."""
        self.is_locked = False
        self.login_attempts = 0
        self.save()
        logger.info(f"Account unlocked for user {self.email} in tenant {self.tenant.schema_name}")

    def suspend_account(self):
        """Suspend the user account."""
        self.status = 'suspended'
        self.is_active = False
        self.save()
        logger.info(f"Account suspended for user {self.email} in tenant {self.tenant.schema_name}")

    def activate_account(self):
        """Activate the user account."""
        self.status = 'active'
        self.is_active = True
        self.save()
        logger.info(f"Account activated for user {self.email} in tenant {self.tenant.schema_name}")

    def increment_login_attempts(self):
        """Increment failed login attempts and lock if threshold reached."""
        self.login_attempts += 1
        if self.login_attempts >= 5:
            self.lock_account(reason="Too many failed login attempts")
        self.save()
        logger.info(f"Failed login attempt for {self.email}. Attempts: {self.login_attempts}")

    def reset_login_attempts(self):
        """Reset login attempts on successful login."""
        self.login_attempts = 0
        self.save()
        logger.info(f"Login attempts reset for user {self.email} in tenant {self.tenant.schema_name}")

    def calculate_completion_percentage(self):
        """
        Calculate the completion percentage of the user profile based on filled fields.
        Returns a float between 0 and 100.
        """
        total_weight = 0
        completed_weight = 0

        # CustomUser fields (20%)
        user_fields = [
            ('email', 7),
            ('first_name', 7),
            ('last_name', 7),
            ('role', 2),
            ('job_role', 2),
            ('has_accepted_terms', 2),
        ]
        for field, weight in user_fields:
            total_weight += weight
            if getattr(self, field):
                completed_weight += weight

        # Ensure profile exists
        try:
            profile = self.profile
        except UserProfile.DoesNotExist:
            return round(completed_weight / total_weight * 100, 2) if total_weight > 0 else 0

        # UserProfile - Personal Info (20%)
        personal_fields = [
            ('work_phone', 2.5),
            ('personal_phone', 2.5),
            ('gender', 2.5),
            ('dob', 2.5),
            ('street', 2.5),
            ('city', 2.5),
            ('state', 2.5),
            ('zip_code', 2.5),
            ('marital_status', 2.5),
        ]
        for field, weight in personal_fields:
            total_weight += weight
            if getattr(profile, field):
                completed_weight += weight

        # UserProfile - Next of Kin (10%)
        next_of_kin_fields = [
            ('next_of_kin', 2.5),
            ('next_of_kin_phone_number', 2.5),
            ('relationship_to_next_of_kin', 2.5),
            ('next_of_kin_email', 2.5),
        ]
        for field, weight in next_of_kin_fields:
            total_weight += weight
            if getattr(profile, field):
                completed_weight += weight

        # UserProfile - Right to Work (15%)
        right_to_work_fields = [
            ('Right_to_Work_document_type', 3.75),
            ('Right_to_Work_document_number', 3.75),
            ('Right_to_Work_document_expiry_date', 3.75),
            ('Right_to_Work_file', 3.75),
        ]
        for field, weight in right_to_work_fields:
            total_weight += weight
            if getattr(profile, field):
                completed_weight += weight

        # UserProfile - DBS Check (10%)
        dbs_fields = [
            ('dbs_type', 2.5),
            ('dbs_certificate_number', 2.5),
            ('dbs_issue_date', 2.5),
            ('dbs_certificate', 2.5),
        ]
        for field, weight in dbs_fields:
            total_weight += weight
            if getattr(profile, field):
                completed_weight += weight

        # UserProfile - Bank Details (10%)
        bank_fields = [
            ('bank_name', 2.5),
            ('account_number', 2.5),
            ('account_name', 2.5),
            ('account_type', 2.5),
        ]
        for field, weight in bank_fields:
            total_weight += weight
            if getattr(profile, field):
                completed_weight += weight

        # Related Models (15%)
        related_models = [
            ('professional_qualifications', 5),
            ('employment_details', 5),
            ('education_details', 5),
            ('reference_checks', 5),
        ]
        for field, weight in related_models:
            total_weight += weight
            if getattr(profile, field).exists():
                completed_weight += weight

        # Driver-Specific Fields (10%, only if is_driver=True)
        if profile.is_driver:
            driver_fields = [
                ('drivers_licence_image1', 2.5),
                ('drivers_licence_date_issue', 2.5),
                ('drivers_licence_expiry_date', 2.5),
                ('drivers_license_insurance_provider', 2.5),
            ]
            for field, weight in driver_fields:
                total_weight += weight
                if getattr(profile, field):
                    completed_weight += weight

        return round(completed_weight / total_weight * 100, 2) if total_weight > 0 else 0


class BlockedIP(models.Model):
    ip_address = models.GenericIPAddressField(unique=True)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    reason = models.CharField(max_length=255, default="Blocked due to excessive failed logins")
    blocked_at = models.DateTimeField(auto_now_add=True)
    blocked_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Blocked IP"
        verbose_name_plural = "Blocked IPs"
        indexes = [
            models.Index(fields=['ip_address']),
            models.Index(fields=['tenant', 'is_active']),
        ]

    def __str__(self):
        return f"Blocked IP {self.ip_address} for tenant {self.tenant.name}"

class UserActivity(models.Model):
    ACTION_TYPES = (
        ('impersonation', 'Impersonation'),
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('password_reset', 'Password Reset'),
        ('account_lock', 'Account Lock'),
        ('account_unlock', 'Account Unlock'),
        ('account_suspend', 'Account Suspend'),
        ('account_activate', 'Account Activate'),
        ('ip_block', 'IP Block'),
        ('ip_unblock', 'IP Unblock'),
    )

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='activities', null=True, blank=True)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    action = models.CharField(max_length=50, choices=ACTION_TYPES)
    performed_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='performed_activities')
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    success = models.BooleanField(null=True, help_text="Indicates if the action (e.g., login) was successful.")

    class Meta:
        verbose_name = "User Activity"
        verbose_name_plural = "User Activities"
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['action', 'timestamp']),
            models.Index(fields=['ip_address']),
        ]

    def __str__(self):
        return f"{self.action} {'success' if self.success else 'failed' if self.success is False else ''} for {self.user.email if self.user else 'unknown'} at {self.timestamp}"


class UserProfile(models.Model):

    SALARY_RATE_CHOICES = [
    ('hourly', 'Hourly'),
    ('daily', 'Daily'),
    ('weekly', 'Weekly'),
    ('bi_weekly', 'Bi-Weekly'),
    ('monthly', 'Monthly'),
    ('annual', 'Annual'),
    ]
        
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='profile')
    work_phone = models.CharField(max_length=20, blank=True, null=True)
    personal_phone = models.CharField(max_length=20, blank=True, null=True)
    gender = models.CharField(max_length=20, blank=True, null=True)
    dob = models.DateField(blank=True, null=True)
    street = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    zip_code = models.CharField(max_length=20, blank=True, null=True)
    department = models.CharField(max_length=100, blank=True, null=True)
    # modules = models.ManyToManyField(Module, blank=True)


    # Add the salary rate field
    salary_rate = models.CharField(
        max_length=20, 
        choices=SALARY_RATE_CHOICES, 
        blank=True, 
        null=True,
        help_text="How often the user wants to be paid"
    )


    # ID and Documents
    employee_id = models.CharField(max_length=15, null=True, blank=True)

    # government_id_type = models.CharField(max_length=50, choices=[('Drivers Licence', 'Drivers Licence')], blank=True)
    marital_status = models.CharField(max_length=50, choices=[('Single', 'Single'), ('Married', 'Married'), ('Divorced', 'Divorced'), ('Widowed', 'Widowed'),  ('Others', 'Others')], blank=True)
    # id_number = models.CharField(max_length=20, blank=True)
    # document_number = models.CharField(max_length=20, blank=True)
    # document_expiry_date = models.DateField(null=True, blank=True)
  
    # Image fields and their corresponding URL fields
    profile_image = models.ImageField(upload_to='profile_image/', max_length=255, blank=True, null=True)
    profile_image_url = models.CharField(max_length=1024, blank=True, null=True)


    # Driving Risk Assessment (B)
    is_driver = models.BooleanField(default=False)
    type_of_vehicle = models.CharField(max_length=50, blank=True)

    drivers_licence_image1 = models.ImageField(upload_to='driver_licences/', blank=True, null=True)
    drivers_licence_image1_url = models.CharField(max_length=1024, blank=True, null=True)

    drivers_licence_image2 = models.ImageField(upload_to='driver_licences/',max_length=255, blank=True, null=True)
    drivers_licence_image2_url = models.CharField(max_length=1024, blank=True, null=True)

    drivers_licence_country_of_issue = models.CharField(max_length=100, blank=True)
    drivers_licence_date_issue = models.DateField(null=True, blank=True)
    drivers_licence_expiry_date = models.DateField(null=True, blank=True)
    drivers_license_insurance_provider = models.CharField(max_length=100, blank=True)
    drivers_licence_insurance_expiry_date = models.DateField(null=True, blank=True)
    drivers_licence_issuing_authority = models.CharField(max_length=100, blank=True)
    drivers_licence_policy_number = models.CharField(max_length=100, blank=True)

    # Care Worker Risk Assessment
    assessor_name = models.CharField(max_length=255, blank=True)
    manual_handling_risk = models.CharField(max_length=50, choices=[('Low', 'Low')], blank=True)
    lone_working_risk = models.CharField(max_length=50, choices=[('Low', 'Low')], blank=True)
    infection_risk = models.CharField(max_length=50, choices=[('Low', 'Low')], blank=True)

    # Personal Information
    next_of_kin = models.CharField(max_length=255, blank=True)
    next_of_kin_address = models.CharField(max_length=255, blank=True)
    next_of_kin_phone_number = models.CharField(max_length=15, blank=True)
    next_of_kin_alternate_phone = models.CharField(max_length=15, blank=True)
    relationship_to_next_of_kin = models.CharField(max_length=100, blank=True)
    next_of_kin_email = models.EmailField(blank=True)
    next_of_kin_town = models.CharField(max_length=255, blank=True)
    next_of_kin_zip_code = models.CharField(max_length=20, blank=True, null=True)

    # Right to Work (Basic fields here, detailed to LegalWorkEligibility)
    Right_to_Work_status = models.CharField(max_length=100, blank=True)
    Right_to_Work_passport_holder = models.CharField(max_length=100, null=True, blank=True)
    Right_to_Work_document_type = models.CharField(max_length=100, choices=[
        ('Biometric Residence Permit', 'Biometric Residence Permit'), 
        ('Passport', 'Passport'), 
        ('National ID', 'National ID'),
        ('Residence Card', 'Residence Card'),
        ('Visa', 'Visa'),
        ('Work Permit', 'Work Permit')
    ], blank=True)
    Right_to_Work_share_code = models.CharField(max_length=255, blank=True)
    Right_to_Work_document_number = models.CharField(max_length=100, blank=True)
    Right_to_Work_document_expiry_date = models.DateField(null=True, blank=True)
    Right_to_Work_country_of_issue = models.CharField(max_length=100, blank=True)

    Right_to_Work_file = models.ImageField(upload_to='right_to_work/', max_length=255, blank=True, null=True)
    Right_to_Work_file_url = models.CharField(max_length=1024, blank=True, null=True)


    Right_to_Work_country_of_issue = models.CharField(max_length=100, blank=True)
    Right_to_Work_restrictions = models.CharField(max_length=255, blank=True)

    #DBS CHECK
    dbs_type = models.CharField(max_length=100,  blank=True)

    dbs_certificate = models.ImageField(upload_to='dbs_certificates/', max_length=255, blank=True, null=True)
    dbs_certificate_url = models.CharField(max_length=1024, blank=True, null=True)


    dbs_certificate_number = models.CharField(max_length=100, blank=True)
    dbs_issue_date = models.DateField(null=True, blank=True)

    dbs_update_file = models.ImageField(upload_to='dbs_update_service/', max_length=255, blank=True, null=True)
    dbs_update_file_url = models.CharField(max_length=1024, blank=True, null=True)


    dbs_update_certificate_number = models.CharField(max_length=100, blank=True)
    dbs_update_issue_date = models.DateField(null=True, blank=True)

    dbs_status_check = models.BooleanField(default=False)

    # Bank Details
    bank_name = models.CharField(max_length=255, blank=True)
    account_number = models.CharField(max_length=20, blank=True)
    account_name = models.CharField(max_length=255, blank=True)
    account_type = models.CharField(max_length=50, choices=[('Current', 'Current'), ('Savings', 'Savings'), ('Business', 'Business')], blank=True)

    # Permissions
    access_duration = models.DateField(default=today, blank=True)
    system_access_rostering = models.BooleanField(default=False)
    system_access_hr = models.BooleanField(default=False)
    system_access_recruitment = models.BooleanField(default=False)
    system_access_training = models.BooleanField(default=False)
    system_access_finance = models.BooleanField(default=False)
    system_access_compliance = models.BooleanField(default=False)
    system_access_co_superadmin = models.BooleanField(default=False)
    system_access_asset_management = models.BooleanField(default=False)
    vehicle_type = models.CharField(max_length=50, choices=[('Personal Vehicle', 'Personal Vehicle'), ('Company Vehicle', 'Company Vehicle'), ('Both', 'Both')], blank=True)

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

        indexes = [
            models.Index(fields=['employee_id']),
            models.Index(fields=['user']),
        ]

    def save(self, *args, **kwargs):
        if not self.employee_id and self.user and self.user.tenant:
            tenant = self.user.tenant
            tenant_code = tenant.name.strip().upper()[:3]  # e.g., "PRO" from "Proliance"

            # Get the max employee_id that starts with this tenant code
            last_employee = UserProfile.objects.filter(
                user__tenant=tenant,
                employee_id__startswith=tenant_code
            ).aggregate(
                max_id=Max('employee_id')
            )['max_id']

            if last_employee:
                try:
                    last_number = int(last_employee.split('-')[1])
                except (IndexError, ValueError):
                    last_number = 0
            else:
                last_number = 0

            next_number = last_number + 1
            self.employee_id = f"{tenant_code}-{next_number:04d}"

        super().save(*args, **kwargs)


# class ProfessionalQualification(models.Model):
#     user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='professional_qualifications')
#     name = models.CharField(max_length=255)
#     #image_file = models.ImageField(upload_to='professional_qualifications/', max_length=255, blank=True, null=True)
#     image_file = models.CharField(max_length=1024, blank=True, null=True)
#     uploaded_at = models.DateTimeField(auto_now_add=True)

#     class Meta:
#         verbose_name_plural = "Professional Qualifications"


# class EmploymentDetail(models.Model):
#     user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='employment_details')
#     job_role = models.CharField(max_length=255)
#     hierarchy = models.CharField(max_length=100)
#     department = models.CharField(max_length=100)
#     work_email = models.EmailField()
#     employment_type = models.CharField(max_length=50, choices=[('Full Time', 'Full Time'), ('Part Time', 'Part Time'), ('Contract', 'Contract')])

#     employment_start_date = models.DateTimeField(default=now)
#     employment_end_date = models.DateTimeField(null=True, blank=True)
#     probation_end_date = models.DateTimeField(null=True, blank=True)

#     line_manager = models.CharField(max_length=255, null=True, blank=True)
#     currency = models.CharField(max_length=100, null=True, blank=True)
#     salary = models.DecimalField(max_digits=20, decimal_places=2)
#     working_days = models.CharField(max_length=100, null=True, blank=True)
#     maximum_working_hours = models.PositiveIntegerField(null=True, blank=True)

#     class Meta:
#         verbose_name = "Employment Detail"
#         verbose_name_plural = "Employment Details"



# class EducationDetail(models.Model):
#     user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='education_details')
#     institution = models.CharField(max_length=255)
#     highest_qualification = models.CharField(max_length=255)
#     course_of_study = models.CharField(max_length=255)
#     start_year = models.PositiveIntegerField()
#     end_year = models.PositiveIntegerField()
#     certificate = models.ImageField(upload_to='Educational-certificates/', max_length=255, blank=True, null=True)
#     skills = models.TextField(blank=True)
#     uploaded_at = models.DateTimeField(auto_now_add=True)

#     class Meta:
#         verbose_name = "Education Detail"
#         verbose_name_plural = "Education Details"

# class ReferenceCheck(models.Model):
#     user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='reference_checks')
#     name = models.CharField(max_length=255)
#     phone_number = models.CharField(max_length=15)
#     email = models.EmailField()
#     relationship_to_applicant = models.CharField(max_length=100)

#     class Meta:
#         verbose_name = "Reference Check"
#         verbose_name_plural = "Reference Checks"

# class ProofOfAddress(models.Model):
#     TYPE_CHOICES = [
#         ('utility_bill', 'Utility Bill'),
#         ('bank_statement', 'Bank Statement'),
#         ('tenancy_agreement', 'Tenancy Agreement'),
#     ]
#     user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='proof_of_address')
#     type = models.CharField(max_length=50, choices=TYPE_CHOICES)
#     document = models.CharField(max_length=1024, blank=True, null=True)
#     # document = models.ImageField(upload_to='proof_of_address/', max_length=255, blank=True, null=True)
#     issue_date = models.DateField(null=True, blank=True)
#     nin = models.CharField(max_length=20, blank=True, null=True, verbose_name="National Insurance Number (NIN)")
#     #nin_document = models.ImageField(upload_to='nin_documents/', max_length=255, blank=True, null=True)
#     nin_document = models.CharField(max_length=1024, blank=True, null=True)
#     uploaded_at = models.DateTimeField(auto_now_add=True)

#     def __str__(self):
#         return f"{self.user_profile.user.email} - {self.type}"

# class InsuranceVerification(models.Model):
#     INSURANCE_TYPES = [
#         ('public_liability', 'Public Liability'),
#         ('professional_indemnity', 'Professional Indemnity')
#         # ('employers_liability', 'Employers Liability'),
#     ]
#     user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='insurance_verifications')
#     insurance_type = models.CharField(max_length=50, choices=INSURANCE_TYPES)
#     #document = models.ImageField(upload_to='insurance_documents/', max_length=255, blank=True, null=True)
#     document = models.CharField(max_length=1024, blank=True, null=True)
#     provider_name = models.CharField(max_length=255, blank=True, null=True)
#     coverage_start_date = models.DateField(blank=True, null=True)
#     expiry_date = models.DateField(blank=True, null=True)
#     phone_number = models.CharField(max_length=20, blank=True, null=True)
#     uploaded_at = models.DateTimeField(auto_now_add=True)

#     def __str__(self):
#         return f"{self.user_profile.user.email} - {self.insurance_type}"

# class DrivingRiskAssessment(models.Model):
#     user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='driving_risk_assessments')
#     assessment_date = models.DateField(blank=True, null=True)
#     fuel_card_usage_compliance = models.BooleanField(default=False)
#     road_traffic_compliance = models.BooleanField(default=False)
#     tracker_usage_compliance = models.BooleanField(default=False)
#     maintenance_schedule_compliance = models.BooleanField(default=False)
#     additional_notes = models.TextField(blank=True, null=True)
#     #supporting_document = models.ImageField(upload_to='driving_risk_docs/', max_length=255, blank=True, null=True)
#     supporting_document = models.CharField(max_length=1024, blank=True, null=True)
#     uploaded_at = models.DateTimeField(auto_now_add=True)

#     def __str__(self):
#         return f"{self.user_profile.user.email} - Driving Risk Assessment"

# class LegalWorkEligibility(models.Model):
#     user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='legal_work_eligibilities')
#     evidence_of_right_to_rent = models.BooleanField(default=False)
#     # document = models.ImageField(upload_to='legal_work_docs/', max_length=255, blank=True, null=True)
#     document = models.CharField(max_length=1024, blank=True, null=True)
#     expiry_date = models.DateField(blank=True, null=True)
#     phone_number = models.CharField(max_length=20, blank=True, null=True)
#     uploaded_at = models.DateTimeField(auto_now_add=True)

#     def __str__(self):
#         return f"{self.user_profile.user.email} - Legal & Work Eligibility"

# class OtherUserDocuments(models.Model):
#     user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='other_user_documents')
#     government_id_type = models.CharField(max_length=100, blank=True)
#     title = models.CharField(max_length=255, blank=True)
#     document_number = models.CharField(max_length=20, blank=True)
#     expiry_date = models.DateField(blank=True, null=True)
#     # file = models.ImageField(upload_to='other_user_documents', max_length=255, blank=True, null=True)
#     file = models.CharField(max_length=1024, blank=True, null=True)
#     uploaded_at = models.DateTimeField(auto_now_add=True)


#     class Meta:
#         verbose_name = "User Document"
#         verbose_name_plural = "User Documents"


class ProfessionalQualification(models.Model):
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='professional_qualifications')
    name = models.CharField(max_length=255)
    image_file = models.ImageField(upload_to='professional_qualifications/', max_length=255, blank=True, null=True)
    image_file_url = models.CharField(max_length=1024, blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Professional Qualifications"

class EducationDetail(models.Model):
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='education_details')
    institution = models.CharField(max_length=255)
    highest_qualification = models.CharField(max_length=255)
    course_of_study = models.CharField(max_length=255)
    start_year = models.PositiveIntegerField()
    end_year = models.PositiveIntegerField()
    certificate = models.ImageField(upload_to='Educational-certificates/', max_length=255, blank=True, null=True)
    certificate_url = models.CharField(max_length=1024, blank=True, null=True)
    skills = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Education Detail"
        verbose_name_plural = "Education Details"

class EmploymentDetail(models.Model):
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='employment_details')
    job_role = models.CharField(max_length=255)
    hierarchy = models.CharField(max_length=100)
    department = models.CharField(max_length=100)
    work_email = models.EmailField()
    employment_type = models.CharField(max_length=50, choices=[('Full Time', 'Full Time'), ('Part Time', 'Part Time'), ('Contract', 'Contract')])

    employment_start_date = models.DateTimeField(default=now)
    employment_end_date = models.DateTimeField(null=True, blank=True)
    probation_end_date = models.DateTimeField(null=True, blank=True)

    line_manager = models.CharField(max_length=255, null=True, blank=True)
    currency = models.CharField(max_length=100, null=True, blank=True)
    salary = models.DecimalField(max_digits=20, decimal_places=2)
    working_days = models.CharField(max_length=100, null=True, blank=True)
    maximum_working_hours = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = "Employment Detail"
        verbose_name_plural = "Employment Details"


class ReferenceCheck(models.Model):
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='reference_checks')
    name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=15)
    email = models.EmailField()
    relationship_to_applicant = models.CharField(max_length=100)

    class Meta:
        verbose_name = "Reference Check"
        verbose_name_plural = "Reference Checks"

class ProofOfAddress(models.Model):
    TYPE_CHOICES = [
        ('utility_bill', 'Utility Bill'),
        ('bank_statement', 'Bank Statement'),
        ('tenancy_agreement', 'Tenancy Agreement'),
    ]
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='proof_of_address')
    type = models.CharField(max_length=50, choices=TYPE_CHOICES)
    document = models.ImageField(upload_to='proof_of_address/', max_length=255, blank=True, null=True)
    document_url = models.CharField(max_length=1024, blank=True, null=True)
    issue_date = models.DateField(null=True, blank=True)
    nin = models.CharField(max_length=20, blank=True, null=True, verbose_name="National Insurance Number (NIN)")
    nin_document = models.ImageField(upload_to='nin_documents/', max_length=255, blank=True, null=True)
    nin_document_url = models.CharField(max_length=1024, blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user_profile.user.email} - {self.type}"

class InsuranceVerification(models.Model):
    INSURANCE_TYPES = [
        ('public_liability', 'Public Liability'),
        ('professional_indemnity', 'Professional Indemnity')
    ]
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='insurance_verifications')
    insurance_type = models.CharField(max_length=50, choices=INSURANCE_TYPES)
    document = models.ImageField(upload_to='insurance_documents/', max_length=255, blank=True, null=True)
    document_url = models.CharField(max_length=1024, blank=True, null=True)
    provider_name = models.CharField(max_length=255, blank=True, null=True)
    coverage_start_date = models.DateField(blank=True, null=True)
    expiry_date = models.DateField(blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user_profile.user.email} - {self.insurance_type}"

class DrivingRiskAssessment(models.Model):
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='driving_risk_assessments')
    assessment_date = models.DateField(blank=True, null=True)
    fuel_card_usage_compliance = models.BooleanField(default=False)
    road_traffic_compliance = models.BooleanField(default=False)
    tracker_usage_compliance = models.BooleanField(default=False)
    maintenance_schedule_compliance = models.BooleanField(default=False)
    additional_notes = models.TextField(blank=True, null=True)
    supporting_document = models.ImageField(upload_to='driving_risk_docs/', max_length=255, blank=True, null=True)
    supporting_document_url = models.CharField(max_length=1024, blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user_profile.user.email} - Driving Risk Assessment"

class LegalWorkEligibility(models.Model):
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='legal_work_eligibilities')
    evidence_of_right_to_rent = models.BooleanField(default=False)
    document = models.ImageField(upload_to='legal_work_docs/', max_length=255, blank=True, null=True)
    document_url = models.CharField(max_length=1024, blank=True, null=True)
    expiry_date = models.DateField(blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user_profile.user.email} - Legal & Work Eligibility"

class OtherUserDocuments(models.Model):
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='other_user_documents')
    government_id_type = models.CharField(max_length=100, blank=True)
    title = models.CharField(max_length=255, blank=True)
    document_number = models.CharField(max_length=20, blank=True)
    expiry_date = models.DateField(blank=True, null=True)
    file = models.ImageField(upload_to='other_user_documents', max_length=255, blank=True, null=True)
    file_url = models.CharField(max_length=1024, blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "User Document"
        verbose_name_plural = "User Documents"


class PasswordResetToken(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    token = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateField()
    used = models.BooleanField(default=False)

    class Meta:
        unique_together = ('user', 'tenant', 'token')
        verbose_name = "Password Reset Token"
        verbose_name_plural = "Password Reset Tokens"

    def __str__(self):
        return f"Password reset token for {self.user.email} in tenant {self.tenant.schema_name}"
    
class UserSession(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='sessions')
    login_time = models.DateTimeField()
    logout_time = models.DateTimeField(null=True, blank=True)
    duration = models.DurationField(null=True, blank=True)
    date = models.DateField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.login_time and self.logout_time:
            self.duration = self.logout_time - self.login_time
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.email} | {self.date} | {self.login_time} - {self.logout_time}"

class ClientProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='client_profile')
    client_id = models.CharField(max_length=15, null=True, blank=True)
    
    # Personal Information (beyond what's in CustomUser)
    title = models.CharField(max_length=20, choices=[('Mr', 'Mr'), ('Mrs', 'Mrs'), ('Miss', 'Miss'), ('Dr', 'Dr')], blank=True, null=True)
    contact_number = models.CharField(max_length=20, blank=True, null=True)
    gender_identity = models.CharField(
        max_length=20,
        choices=[
            ('Male', 'Male'),
            ('Female', 'Female'),
            ('Non-Binary', 'Non-Binary'),
            ('Other', 'Other'),
            ('Prefer not to say', 'Prefer not to say'),
        ],
        blank=True,
        null=True
    )
  
    preferred_pronouns = models.CharField(max_length=20, blank=True, null=True)
    preferred_name = models.CharField(max_length=100, blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)

    nhis_number = models.CharField(max_length=50, blank=True, null=True)
    nationality = models.CharField(max_length=100, blank=True, null=True)
    #state_of_origin = models.CharField(max_length=100, blank=True, null=True)
    # address = models.CharField(max_length=255, blank=True, null=True)

    # Address
    address_line = models.CharField(max_length=255, blank=True, null=True)
    town = models.CharField(max_length=100, blank=True, null=True)
    county = models.CharField(max_length=100,blank=True, null=True)
    postcode = models.CharField(max_length=20, blank=True, null=True)
    type_of_residence = models.CharField(
        max_length=50,
        choices=[
            ('private_home', 'Private Home'),
            ('care_home', 'Care Home'),
            ('assisted_living', 'Assisted Living'),
            ('sheltered', 'Sheltered Housing'),
        ],
        default='private_home'
    )



    town = models.CharField(max_length=100, blank=True, null=True)
    zip_code = models.CharField(max_length=20, blank=True, null=True)
    marital_status = models.CharField(
        max_length=20,
        choices=[
            ('Single', 'Single'),
            ('Married', 'Married'),
            ('Divorced', 'Divorced'),
            ('Widowed', 'Widowed'),
            ('Other', 'Other'),
        ],
        blank=True,
        null=True
    )
 
    photo = models.ImageField(upload_to='client_photos/', max_length=255, blank=True, null=True)
    photo_url = models.CharField(max_length=1024, blank=True, null=True)
    
    contact_number = models.CharField(max_length=20, blank=True, null=True)
    alt_contact_number = models.CharField(max_length=20, blank=True, null=True)

    # Primary Contact
    primary_contact_name = models.CharField(max_length=100, blank=True, null=True)
    primary_contact_phone = models.CharField(max_length=100, blank=True, null=True)
    primary_contact_email = models.CharField(max_length=100, blank=True, null=True)
   

    # Secondary Contact
    secondary_contact_name = models.CharField(max_length=100, blank=True, null=True)
    secondary_contact_phone = models.CharField(max_length=100, blank=True, null=True)
    secondary_contact_email = models.CharField(max_length=100, blank=True, null=True)


    # Preferred Communication Method
    communication_preference = models.CharField(
        max_length=20,
        choices=[
            ('phone_call', 'Phone Call'),
            ('sms', 'SMS'),
            ('email', 'Email')
        ],
        default='phone_call'
    )


    # Living Situation
    lives_alone = models.BooleanField(default=True)
    co_residents = models.TextField(blank=True, null=True)  # Optional description if not living alone
    key_safe_instructions = models.TextField(blank=True, null=True)


    # Next of Kin
    next_of_kin_full_name = models.CharField(max_length=255, blank=True, null=True)
    next_of_kin_relationship = models.CharField(max_length=100, blank=True, null=True)
    next_of_kin_address = models.CharField(max_length=255, blank=True, null=True)
    next_of_kin_contact_number = models.CharField(max_length=20, blank=True, null=True)
    next_of_kin_alt_contact_number = models.CharField(max_length=20, blank=True, null=True)
    next_of_kin_town = models.CharField(max_length=100, blank=True, null=True)
    next_of_kin_phone = models.CharField(max_length=20, blank=True, null=True)
    next_of_kin_email = models.EmailField(blank=True, null=True)

     
    # Care Requirements
    care_plan = models.CharField(max_length=100, blank=True, null=True)  # e.g., 'Single Handed Call'
    care_tasks = models.TextField(blank=True, null=True)  # Comma-separated or free text, e.g., 'Meal Preparation'
    care_type = models.CharField(max_length=100, blank=True, null=True)  # e.g., 'Medical Support'
    special_needs = models.TextField(blank=True, null=True)  # e.g., 'Dementia'
    preferred_carer_gender = models.CharField(
        max_length=20,
        choices=[
            ('Male', 'Male'),
            ('Female', 'Female'),
            ('No Preference', 'No Preference'),
        ],
        blank=True,
        null=True
    )
    language_preference = models.CharField(max_length=100, blank=True, null=True)
    preferred_care_times = models.JSONField(default=dict, blank=True)  # e.g., {'Sun': ['AM', 'PM'], 'Mon': ['Night']}
    frequency_of_care = models.CharField(
        max_length=50,
        choices=[
            ('Daily', 'Daily'),
            ('Weekly', 'Weekly'),
            ('Weekend', 'Weekend'),
            ('Other', 'Other'),
        ],
        blank=True,
        null=True
    )
    flexibility = models.BooleanField(default=True)
    
    # Administrative & Compliance
    funding_type = models.CharField(
        max_length=50,
        choices=[
            ('Private', 'Private'),
            ('Government', 'Government'),
            ('Insurance', 'Insurance'),
            ('Other', 'Other'),
        ],
        blank=True,
        null=True
    )
    care_package_start_date = models.DateField(blank=True, null=True)
    care_package_review_date = models.DateField(blank=True, null=True)
    
    # Preferred Carers (link to carers, assuming CustomUser with role='carer')
    preferred_carers = models.ManyToManyField(
        CustomUser,
        related_name='preferred_for_clients',
        blank=True,
        limit_choices_to={'role': 'carer'}
    )
    
    # Status and Compliance (from list view)
    status = models.CharField(
        max_length=20,
        choices=[
            ('Active', 'Active'),
            ('Inactive', 'Inactive'),
        ],
        default='Active'
    )
    compliance = models.CharField(max_length=50, default='Passed', blank=True, null=True)  # e.g., 'Passed'
    last_visit = models.DateField(blank=True, null=True)
    

    # Company Info
    company_name = models.CharField(max_length=255, null=True, blank=True, help_text="Official name of the client company")
    contact_person_name = models.CharField(max_length=255, null=True, blank=True, help_text="Primary contact person's full name")
    contact_person_title = models.CharField(max_length=100, null=True, blank=True, help_text="Contact person's job title")
    contact_person_department = models.CharField(max_length=100, null=True, blank=True, help_text="Contact person's department")
    contact_email = models.EmailField(null=True, blank=True, help_text="Contact person's email address")
    contact_phone = models.CharField(max_length=20, null=True, blank=True, help_text="Contact person's phone number")
    company_address = models.TextField(null=True, blank=True, help_text="Client company's physical address")

    # Client Profile
    industry = models.CharField(max_length=100, null=True, blank=True, help_text="Client's industry or sector")
    business_type = models.CharField(max_length=100, null=True, blank=True, help_text="Client's business type (e.g., supplier, customer, partner)")
    client_type = models.CharField(max_length=100, null=True, blank=True, help_text="Client's relationship with the company (e.g., direct customer)")

    # Order and Payment Information
    order_history = models.JSONField(null=True, blank=True, help_text="Record of past orders including dates, quantities, and values")
    payment_terms = models.TextField(null=True, blank=True, help_text="Client's payment terms, methods, and schedules")
    credit_limit = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Client's credit limit")
    credit_utilization = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Client's current credit usage")
    payment_history = models.JSONField(null=True, blank=True, help_text="Record of past payments including dates and amounts")

    # Communication and Feedback
    communication_preferences = models.CharField(max_length=255, null=True, blank=True, help_text="Client's preferred communication channels (e.g., email, phone)")
    feedback = models.JSONField(null=True, blank=True, help_text="Client feedback and satisfaction ratings")
    complaints = models.JSONField(null=True, blank=True, help_text="Record of client complaints and resolutions")

    # Additional Information
    special_requirements = models.TextField(null=True, blank=True, help_text="Client's special requirements or requests (e.g., custom packaging)")
    notes = models.TextField(null=True, blank=True, help_text="Additional notes or comments about the client")

    class Meta:
        verbose_name = "Client Profile"
        verbose_name_plural = "Client Profiles"
        indexes = [
            models.Index(fields=['client_id']),
            models.Index(fields=['user']),
        ]

    def save(self, *args, **kwargs):
        if not self.client_id and self.user and self.user.tenant:
            tenant = self.user.tenant
            tenant_code = tenant.name.strip().upper()[:3]  # e.g., "PRO" from "Proliance"
            client_prefix = f"{tenant_code}CLIENT-"         # Use "CLIENT" as the prefix

            # Get the max client_id that starts with this tenant code + 'CLIENT-'
            last_client = ClientProfile.objects.filter(
                user__tenant=tenant,
                client_id__startswith=client_prefix
            ).aggregate(
                max_id=Max('client_id')
            )['max_id']

            if last_client:
                try:
                    last_number = int(last_client.split('-')[1])
                except (IndexError, ValueError):
                    last_number = 0
            else:
                last_number = 0

            next_number = last_number + 1
            self.client_id = f"{client_prefix}{next_number:04d}"

        super().save(*args, **kwargs)


    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True,  null=True)

    # def __str__(self):
    #     return f"{self.first_name} {self.last_name}"


# class RSAKeyPair(models.Model):
#     tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='rsa_keys')
#     kid = models.CharField(max_length=64, unique=True, default=generate_kid)
#     private_key_pem = models.TextField()  # PEM encoded private key
#     public_key_pem = models.TextField()   # PEM encoded public key
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)  # <-- Add this
#     active = models.BooleanField(default=True)


#     @classmethod
#     def get_active_by_kid(cls, kid, tenant):
#         """Cached active keypair lookup."""
#         from auth_service.utils.cache import get_cache_key, get_from_cache, set_to_cache
#         key = get_cache_key(tenant.schema_name, 'rsakey', kid)
#         keypair = get_from_cache(key)
#         if keypair is None:
#             with tenant_context(tenant):
#                 keypair = cls.objects.filter(kid=kid, active=True, tenant=tenant).first()
#                 if keypair:
#                     # Cache public_key_pem only for security
#                     set_to_cache(key, keypair.public_key_pem, timeout=3600)  # 1 hour
#         return keypair

#     def __str__(self):
#         return f"RSAKeyPair(kid={self.kid}, tenant={self.tenant_id}, active={self.active})"


class RSAKeyPair(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='rsa_keys')
    kid = models.CharField(max_length=64, unique=True, default=generate_kid)
    private_key_pem = models.TextField()  # PEM encoded private key
    public_key_pem = models.TextField()   # PEM encoded public key
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    active = models.BooleanField(default=True)

    @classmethod
    def get_active_by_kid(cls, kid, tenant):
        """Cached active keypair lookup."""
        from auth_service.utils.cache import get_cache_key, get_from_cache, set_to_cache
        key = get_cache_key(tenant.schema_name, 'rsakey', kid)
        keypair_data = get_from_cache(key)
        if keypair_data is None:
            with tenant_context(tenant):
                keypair = cls.objects.filter(kid=kid, active=True, tenant=tenant).first()
                if keypair:
                    # Cache public_key_pem only for security
                    set_to_cache(key, keypair.public_key_pem, timeout=3600)  # 1 hour
                    return keypair
                return None
        # If cached, reconstruct minimal (but for key, just return the PEM string)
        with tenant_context(tenant):
            keypair = cls.objects.filter(kid=kid, active=True, tenant=tenant).first()
            return keypair  # Full query for safety

    def __str__(self):
        return f"RSAKeyPair(kid={self.kid}, tenant={self.tenant_id}, active={self.active})"


class BlacklistedToken(models.Model):
    jti = models.CharField(max_length=255, unique=True)  # JWT ID
    blacklisted_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()


class Document(models.Model):
    tenant_id = models.CharField(max_length=255, blank=True, null=True)
    title = models.CharField(max_length=255)
    file_url = models.URLField(max_length=500, blank=True, null=True)
    file_path = models.CharField(max_length=500, blank=True, null=True)
    file_type = models.CharField(max_length=100, blank=True, null=True)
    file_size = models.BigIntegerField(blank=True, null=True)
    version = models.IntegerField(default=1)
    uploaded_by_id = models.CharField(max_length=255, blank=True, null=True)
    updated_by_id = models.CharField(max_length=255, blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expiring_date = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=50, default="active")
    document_number = models.CharField(max_length=100, unique=True, blank=True, null=True)

    class Meta:
        unique_together = ('tenant_id', 'document_number')

class DocumentVersion(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='versions')
    version = models.IntegerField()
    file_url = models.URLField(max_length=500)
    file_path = models.CharField(max_length=500)
    file_type = models.CharField(max_length=100)
    file_size = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by_id = models.CharField(max_length=255)

    class Meta:
        unique_together = ('document', 'version')

# class DocumentAcknowledgment(models.Model):
#     document = models.ForeignKey(Document, on_delete=models.CASCADE)
#     user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
#     # tenant = models.ForeignKey('core.Tenant', on_delete=models.CASCADE)
#     acknowledged_at = models.DateTimeField(auto_now_add=True)


class Group(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='groups')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('tenant', 'name')
        indexes = [
            models.Index(fields=['tenant', 'name']),
        ]

    def __str__(self):
        return f"{self.name} ({self.tenant.name})"

class GroupMembership(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='group_memberships')
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('group', 'user')
        indexes = [
            models.Index(fields=['group', 'user']),
            models.Index(fields=['tenant', 'user']),
        ]

    def __str__(self):
        return f"{self.user.email} in {self.group.name}"