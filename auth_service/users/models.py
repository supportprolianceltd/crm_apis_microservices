#users.models

from django.db import models
from django.contrib.auth.models import AbstractUser, UserManager
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from core.models import Tenant, Module, Branch
from django.db.models import Max
from django.db import models
from core.models import Tenant
import uuid

def generate_kid():
    return uuid.uuid4().hex

def today():
    return timezone.now().date()

class CustomUserManager(UserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        username = extra_fields.pop('username', None) or email  # Remove from extra_fields to avoid duplicate
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

class CustomUser(AbstractUser):
    ROLES = (
        ('admin', 'Admin'),
        ('co-admin', 'Co-Admin'),
        ('hr', 'HR'),
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
    permission_levels = models.JSONField(default=list, blank=True)
    job_role = models.CharField(max_length=255, blank=True, null=True, default='staff')
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, null=True)
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True)

  
    has_accepted_terms = models.BooleanField(default=False, help_text="Indicates if the user has accepted the terms and conditions.")


    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    def __str__(self):
        return self.email




class UserProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='profile')
    work_phone = models.CharField(max_length=20, blank=True, null=True)
    personal_phone = models.CharField(max_length=20, blank=True, null=True)
    gender = models.CharField(max_length=20, blank=True, null=True)
    dob = models.DateField(blank=True, null=True)
    street = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    zip_code = models.CharField(max_length=20, blank=True, null=True)
    department = models.CharField(max_length=100, blank=True, null=True)
    # modules = models.ManyToManyField(Module, blank=True)

    # ID and Documents
    employee_id = models.CharField(max_length=15, null=True, blank=True)

    # government_id_type = models.CharField(max_length=50, choices=[('Drivers Licence', 'Drivers Licence')], blank=True)
    marital_status = models.CharField(max_length=50, choices=[('Single', 'Single'), ('Married', 'Married'), ('Divorced', 'Divorced'), ('Widowed', 'Widowed'),  ('Others', 'Others')], blank=True)
    # id_number = models.CharField(max_length=20, blank=True)
    # document_number = models.CharField(max_length=20, blank=True)
    # document_expiry_date = models.DateField(null=True, blank=True)
  
    # Image fields and their corresponding URL fields
    profile_image = models.ImageField(upload_to='profile_image/', blank=True, null=True)
    profile_image_url = models.CharField(max_length=1024, blank=True, null=True)


    # Driving Risk Assessment (B)
    is_driver = models.BooleanField(default=False)
    type_of_vehicle = models.CharField(max_length=50, blank=True)

    drivers_licence_image1 = models.ImageField(upload_to='driver_licences/', blank=True, null=True)
    drivers_licence_image1_url = models.CharField(max_length=1024, blank=True, null=True)

    drivers_licence_image2 = models.ImageField(upload_to='driver_licences/', blank=True, null=True)
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
    next_of_kin_town = models.CharField(max_length=15, blank=True)
    next_of_kin_zip_code = models.CharField(max_length=20, blank=True, null=True)

    # Right to Work (Basic fields here, detailed to LegalWorkEligibility)
    Right_to_Work_status = models.CharField(max_length=100, blank=True)
    Right_to_Work_passport_holder = models.CharField(max_length=100, null=True, blank=True)
    Right_to_Work_document_type = models.CharField(max_length=100, choices=[('Biometric Residence Permit', 'Biometric Residence Permit'), ('Passport', 'Passport'), ("National ID", "National ID")], blank=True)
    Right_to_Work_share_code = models.CharField(max_length=20, blank=True)
    Right_to_Work_document_number = models.CharField(max_length=100, blank=True)
    Right_to_Work_document_expiry_date = models.DateField(null=True, blank=True)
    Right_to_Work_country_of_issue = models.CharField(max_length=100, blank=True)

    Right_to_Work_file = models.ImageField(upload_to='right_to_work/', blank=True, null=True)
    Right_to_Work_file_url = models.CharField(max_length=1024, blank=True, null=True)


    Right_to_Work_country_of_issue = models.CharField(max_length=100, blank=True)
    Right_to_Work_restrictions = models.CharField(max_length=255, blank=True)

    #DBS CHECK
    dbs_type = models.CharField(max_length=100,  blank=True)

    dbs_certificate = models.ImageField(upload_to='dbs_certificates/', blank=True, null=True)
    dbs_certificate_url = models.CharField(max_length=1024, blank=True, null=True)


    dbs_certificate_number = models.CharField(max_length=100, blank=True)
    dbs_issue_date = models.DateField(null=True, blank=True)

    dbs_update_file = models.ImageField(upload_to='dbs_update_service/', blank=True, null=True)
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




class ProfessionalQualification(models.Model):
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='professional_qualifications')
    name = models.CharField(max_length=255)
    image_file = models.ImageField(upload_to='professional_qualifications/', blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Professional Qualifications"

class EmploymentDetail(models.Model):
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='employment_details')
    job_role = models.CharField(max_length=255)
    hierarchy = models.CharField(max_length=100)
    department = models.CharField(max_length=100)
    work_email = models.EmailField()
    employment_type = models.CharField(max_length=50, choices=[('Full Time', 'Full Time'), ('Part Time', 'Part Time'), ('Contract', 'Contract')])
    employment_start_date = models.DateField(default=today)
    employment_end_date = models.DateField(null=True, blank=True)
    probation_end_date = models.DateField(null=True, blank=True)
    line_manager = models.CharField(max_length=255, null=True, blank=True)
    currency = models.CharField(max_length=100, null=True, blank=True)
    salary = models.DecimalField(max_digits=10, decimal_places=2)
    working_days = models.CharField(max_length=100, null=True, blank=True)
    maximum_working_hours = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = "Employment Detail"
        verbose_name_plural = "Employment Details"

class EducationDetail(models.Model):
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='education_details')
    institution = models.CharField(max_length=255)
    highest_qualification = models.CharField(max_length=255)
    course_of_study = models.CharField(max_length=255)
    start_year = models.PositiveIntegerField()
    end_year = models.PositiveIntegerField()
    certificate = models.ImageField(upload_to='Educational-certificates/', blank=True, null=True)
    skills = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Education Detail"
        verbose_name_plural = "Education Details"

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
    document = models.ImageField(upload_to='proof_of_address/', blank=True, null=True)
    issue_date = models.DateField(null=True, blank=True)   
    nin = models.CharField(max_length=20, blank=True, null=True, verbose_name="National Insurance Number (NIN)")
    nin_document = models.ImageField(upload_to='nin_documents/', blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user_profile.user.email} - {self.type}"

class InsuranceVerification(models.Model):
    INSURANCE_TYPES = [
        ('public_liability', 'Public Liability'),
        ('professional_indemnity', 'Professional Indemnity')
        # ('employers_liability', 'Employers Liability'),
    ]
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='insurance_verifications')
    insurance_type = models.CharField(max_length=50, choices=INSURANCE_TYPES)
    document = models.ImageField(upload_to='insurance_documents/', blank=True, null=True)
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
    supporting_document = models.ImageField(upload_to='driving_risk_docs/', blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user_profile.user.email} - Driving Risk Assessment"

class LegalWorkEligibility(models.Model):
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='legal_work_eligibilities')
    evidence_of_right_to_rent = models.BooleanField(default=False)
    document = models.ImageField(upload_to='legal_work_docs/', blank=True, null=True)
    expiry_date = models.DateField(blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user_profile.user.email} - Legal & Work Eligibility"

class OtherUserDocuments(models.Model):
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='other_user_documents')
    government_id_type = models.CharField(max_length=100, blank=True)
    document_number = models.CharField(max_length=20, blank=True)
    expiry_date = models.DateField(blank=True, null=True)
    file = models.ImageField(upload_to='other_user_documents', blank=True, null=True)
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
    contact_number = models.CharField(max_length=20, blank=True, null=True)
    gender = models.CharField(
        max_length=20,
        choices=[
            ('Male', 'Male'),
            ('Female', 'Female'),
            ('Non-Binary', 'Non-Binary'),
            ('Prefer not to say', 'Prefer not to say'),
        ],
        blank=True,
        null=True
    )
    dob = models.DateField(blank=True, null=True)
    nationality = models.CharField(max_length=100, blank=True, null=True)
    #state_of_origin = models.CharField(max_length=100, blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)
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
    photo = models.ImageField(upload_to='client_photos/', blank=True, null=True)
    
    # Next of Kin
    next_of_kin_name = models.CharField(max_length=255, blank=True, null=True)
    next_of_kin_relationship = models.CharField(max_length=100, blank=True, null=True)
    next_of_kin_address = models.CharField(max_length=255, blank=True, null=True)
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






class RSAKeyPair(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='rsa_keys')
    kid = models.CharField(max_length=64, unique=True, default=generate_kid)
    private_key_pem = models.TextField()  # PEM encoded private key
    public_key_pem = models.TextField()   # PEM encoded public key
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)  # <-- Add this
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"RSAKeyPair(kid={self.kid}, tenant={self.tenant_id}, active={self.active})"



class BlacklistedToken(models.Model):
    jti = models.CharField(max_length=255, unique=True)  # JWT ID
    blacklisted_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()


# docker compose exec auth-service python manage.py makemigrations users
# docker compose exec auth-service python manage.py migrate


