import uuid
import random
import logging
from django.db import models
from django.db.models import Max
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import AbstractUser, UserManager
from django.core.validators import RegexValidator
from django_tenants.utils import tenant_context
from django.utils.timezone import now

from core.models import Tenant, Module, Branch

logger = logging.getLogger('users')


def generate_kid():
    return uuid.uuid4().hex

def today():
    return timezone.now().date()

import os
from django.core.validators import FileExtensionValidator
from django.core.exceptions import ValidationError

def validate_image_or_pdf(value):
    ext = os.path.splitext(value.name)[1].lower()
    valid_extensions = ['.jpg', '.jpeg', '.png', '.pdf', '.webp', '.gif', '.tiff', '.doc', '.svg',]
    if ext not in valid_extensions:
        raise ValidationError('Only JPG, PNG, and PDF files are allowed.')
    
    # Optional: Add file size validation
    if value.size > 2 * 1024 * 1024:  # 2MB limit
        raise ValidationError('File size cannot exceed 2MB.')

class CustomUserManager(UserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        username = extra_fields.pop('username', None)
        
        # Generate username if not provided
        if not username:
            username = self._generate_username(
                email, 
                extra_fields.get('first_name'), 
                extra_fields.get('last_name'),
                extra_fields.get('tenant')
            )
        
        extra_fields['username'] = username
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def _generate_username(self, email, first_name=None, last_name=None, tenant=None):
        """Generate unique global username (signals enforce global check)."""
        if first_name and last_name:
            initial = first_name[0].lower()
            last = last_name.lower().replace(' ', '')[:12]  # Limit length
            base = f"{initial}{last}"
        else:
            base = email.split('@')[0][:8]
            
        random_digits = ''.join(random.choices('0123456789', k=4))
        candidate = f"{base}{random_digits}"
        
        # Fallback loop (global check happens in signal)
        counter = 0
        while counter < 10:
            # Pre-check in current tenant (for efficiency)
            if tenant and self.filter(tenant=tenant, username=candidate).exists():
                random_digits = ''.join(random.choices('0123456789', k=4))
                candidate = f"{base}{random_digits}"
                counter += 1
                continue
            return candidate
        raise ValueError("Could not generate unique username after 10 attempts")

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractUser):
    ROLES = (

        #APP OWNERS ROLES
        ('super-admin', 'Super Admin'),
        ('admin', 'Admin'),

        #APP USERS ROLES
        ('root-admin', 'Root Admin'),
        ('co-admin', 'Co Admin'),
        ('hr', 'HR'),
        ('staff', 'Staff'), 
        ('investor', 'Investor'),
        ('carer', 'Carer'),
        ('user', 'User'),
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

    STATUS_CHOICES = (
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('suspended', 'Suspended'),
    )

    # Remove the duplicate username field - use the one from AbstractUser
    email = models.EmailField(_('email address'), unique=True)
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    role = models.CharField(max_length=20, choices=ROLES, default='carer')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    permission_levels = models.JSONField(default=list, blank=True)
    job_role = models.CharField(max_length=255, blank=True, null=True, default='user')
    tenant = models.ForeignKey('core.Tenant', on_delete=models.CASCADE, null=True)
    branch = models.ForeignKey('core.Branch', on_delete=models.SET_NULL, null=True, blank=True)
    has_accepted_terms = models.BooleanField(default=False)
    is_locked = models.BooleanField(default=False)
    login_attempts = models.PositiveIntegerField(default=0)
    last_password_reset = models.DateTimeField(null=True, blank=True)

    # Two-Factor Authentication fields
    two_factor_enabled = models.BooleanField(default=False)
    two_factor_secret = models.CharField(max_length=32, blank=True, null=True)
    two_factor_backup_codes = models.JSONField(default=list, blank=True)

    class Meta:
        # REMOVED: unique_together = [('tenant', 'username')]  # Now global via index
        pass

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']  # Add username to required fields

    objects = CustomUserManager()

    def __str__(self):
        return self.email

    def lock_account(self, reason="Manual lock"):
        self.is_locked = True
        self.save()
        logger.info(f"Account locked for user {self.email} in tenant {self.tenant.schema_name}. Reason: {reason}")

    def unlock_account(self):
        self.is_locked = False
        self.login_attempts = 0
        self.save()
        logger.info(f"Account unlocked for user {self.email} in tenant {self.tenant.schema_name}")

    def suspend_account(self):
        self.status = 'suspended'
        self.is_active = False
        self.save()
        logger.info(f"Account suspended for user {self.email} in tenant {self.tenant.schema_name}")

    def activate_account(self):
        self.status = 'active'
        self.is_active = True
        self.save()
        logger.info(f"Account activated for user {self.email} in tenant {self.tenant.schema_name}")

    def increment_login_attempts(self):
        self.login_attempts += 1
        if self.login_attempts >= 5:
            self.lock_account(reason="Too many failed login attempts")
        self.save()
        logger.info(f"Failed login attempt for {self.email}. Attempts: {self.login_attempts}")

    def reset_login_attempts(self):
        self.login_attempts = 0
        self.save()
        logger.info(f"Login attempts reset for user {self.email} in tenant {self.tenant.schema_name}")

    def calculate_completion_percentage(self):
        """
        Calculate the completion percentage of the user profile based on filled fields.
        All fields have equal weight.
        Returns a float between 0 and 100.
        """
        total_fields = 0
        completed_fields = 0

        # CustomUser fields
        user_fields = [
            'email', 'first_name', 'last_name', 'role', 
            'job_role', 'has_accepted_terms'
        ]
        
        for field in user_fields:
            total_fields += 1
            if getattr(self, field):
                completed_fields += 1

        # Check if profile exists
        try:
            profile = self.profile
        except UserProfile.DoesNotExist:
            # If no profile exists, calculate percentage based only on user fields
            return round((completed_fields / total_fields) * 100, 2) if total_fields > 0 else 0

        # UserProfile - Personal Information fields
        personal_fields = [
            'work_phone', 'personal_phone', 'gender', 'dob', 
            'street', 'city', 'state', 'zip_code', 'marital_status'
        ]
        
        for field in personal_fields:
            total_fields += 1
            if getattr(profile, field):
                completed_fields += 1

        # UserProfile - Next of Kin fields
        next_of_kin_fields = [
            'next_of_kin', 'next_of_kin_phone_number', 
            'relationship_to_next_of_kin', 'next_of_kin_email'
        ]
        
        for field in next_of_kin_fields:
            total_fields += 1
            if getattr(profile, field):
                completed_fields += 1

        # UserProfile - Right to Work fields
        right_to_work_fields = [
            'Right_to_Work_document_type', 'Right_to_Work_document_number',
            'Right_to_Work_document_expiry_date', 'Right_to_Work_file'
        ]
        
        for field in right_to_work_fields:
            total_fields += 1
            if getattr(profile, field):
                completed_fields += 1

        # UserProfile - DBS Check fields
        dbs_fields = [
            'dbs_type', 'dbs_certificate_number', 
            'dbs_issue_date', 'dbs_certificate'
        ]
        
        for field in dbs_fields:
            total_fields += 1
            if getattr(profile, field):
                completed_fields += 1

        # UserProfile - Bank Details fields
        bank_fields = [
            'bank_name', 'account_number', 'account_name', 'account_type'
        ]
        
        for field in bank_fields:
            total_fields += 1
            if getattr(profile, field):
                completed_fields += 1

        # Related Models - count each as one field if they have at least one entry
        related_models = [
            'professional_qualifications', 'employment_details',
            'education_details', 'skill_details', 'reference_checks'
        ]
        
        for related_field in related_models:
            total_fields += 1
            if getattr(profile, related_field).exists():
                completed_fields += 1

        # Driver-Specific Fields (only check if user is a driver)
        if profile.is_driver:
            driver_fields = [
                'drivers_licence_image1', 'drivers_licence_date_issue',
                'drivers_licence_expiry_date', 'drivers_license_insurance_provider'
            ]
            
            for field in driver_fields:
                total_fields += 1
                if getattr(profile, field):
                    completed_fields += 1

        # Calculate percentage
        return round((completed_fields / total_fields) * 100, 2) if total_fields > 0 else 0

    # Add this property for easy access
    @property
    def profile_completion_percentage(self):
        """Property to easily access completion percentage."""
        return self.calculate_completion_percentage()


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
    global_correlation_id = models.UUIDField(null=True, blank=True, default=None)

    # Update the ACTION_TYPES in UserActivity model
    ACTION_TYPES = (
        # Authentication & Security
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('login_failed', 'Login Failed'),
        ('password_reset_request', 'Password Reset Request'),
        ('password_reset_confirm', 'Password Reset Confirm'),
        ('account_lock', 'Account Lock'),
        ('account_unlock', 'Account Unlock'),
        ('account_suspend', 'Account Suspend'),
        ('account_activate', 'Account Activate'),
        ('ip_block', 'IP Block'),
        ('ip_unblock', 'IP Unblock'),
        ('impersonation', 'Impersonation'),
        
        # User Management
        ('user_created', 'User Created'),
        ('user_updated', 'User Updated'),
        ('user_deleted', 'User Deleted'),
        ('profile_updated', 'Profile Updated'),
        ('bulk_user_create', 'Bulk User Create'),
        ('user_password_regenerated', 'User Password Regenerated'),
        
        # Document Management
        ('document_uploaded', 'Document Uploaded'),
        ('document_updated', 'Document Updated'),
        ('document_deleted', 'Document Deleted'),
        ('document_acknowledged', 'Document Acknowledged'),
        ('document_permission_granted', 'Document Permission Granted'),
        ('document_permission_revoked', 'Document Permission Revoked'),
        
        # Investment & Financial
        ('investment_created', 'Investment Created'),
        ('investment_updated', 'Investment Updated'),
        ('withdrawal_requested', 'Withdrawal Requested'),
        ('withdrawal_approved', 'Withdrawal Approved'),
        ('withdrawal_rejected', 'Withdrawal Rejected'),
        ('withdrawal_processed', 'Withdrawal Processed'),
        
        # Group Management
        ('group_created', 'Group Created'),
        ('group_updated', 'Group Updated'),
        ('group_deleted', 'Group Deleted'),
        ('group_member_added', 'Group Member Added'),
        ('group_member_removed', 'Group Member Removed'),
        
        # System Operations
        ('rsa_key_created', 'RSA Key Created'),
        ('terms_accepted', 'Terms Accepted'),
        ('session_clock_in', 'Session Clock In'),
        ('session_clock_out', 'Session Clock Out'),
        
        # API & General
        ('api_request', 'API Request'),
        ('export_requested', 'Export Requested'),
        ('bulk_operation', 'Bulk Operation'),


        # New tenant-specific actions        ('tenant_created', 'Tenant Created'),
        ('tenant_user_created', 'Tenant User Created'),
        ('tenant_user_updated', 'Tenant User Updated'),
        ('tenant_user_deleted', 'Tenant User Deleted'),
        ('branch_created', 'Branch Created'),
        ('branch_updated', 'Branch Updated'),
        ('branch_deleted', 'Branch Deleted'),
        ('module_activated', 'Module Activated'),
        ('module_deactivated', 'Module Deactivated'),
        ('tenant_config_updated', 'Tenant Config Updated'),
        ('investment_withdrawn', 'Investment Withdrawn'),
        ('document_shared', 'Document Shared'),
        ('group_member_added', 'Group Member Added'),
        ('session_clocked_in', 'Session Clocked In'),
        ('session_clocked_out', 'Session Clocked Out'),
    )





    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='activities', null=True, blank=True)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    action = models.CharField(max_length=50, choices=ACTION_TYPES)
    performed_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='performed_activities')
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.JSONField(default=dict, blank=True)  # e.g., {"old_balance": 1000, "new_balance": 800}
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    success = models.BooleanField(null=True, help_text="Indicates if the action (e.g., login) was successful.")

    class Meta:
        verbose_name = "User Activity"
        verbose_name_plural = "User Activities"
        indexes = [
            models.Index(fields=['tenant', 'timestamp']),
            models.Index(fields=['tenant', 'action', 'timestamp']),
            models.Index(fields=['tenant', 'user', 'timestamp']),
            models.Index(fields=['tenant', 'performed_by', 'timestamp']),
            models.Index(fields=['tenant', 'success', 'timestamp']),
            models.Index(fields=['ip_address', 'timestamp']),
            models.Index(fields=['action', 'timestamp']),
            models.Index(fields=['timestamp']),  # For time-based queries
        ]
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.action} {'success' if self.success else 'failed' if self.success is False else ''} for {self.user.email if self.user else 'unknown'} at {self.timestamp}"


    def save(self, *args, **kwargs):
        # Optional: Auto-generate correlation ID if not provided (for linking to global events)
        if not self.global_correlation_id:
            self.global_correlation_id = uuid.uuid4()
        super().save(*args, **kwargs)


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
    policy_number = models.CharField(
        max_length=20, 
        blank=True, 
        null=True,
        help_text="Auto-generated policy number for investors (e.g., PRO-000001)"
    )

    # Add the salary rate field
    salary_rate = models.CharField(
        max_length=20, 
        choices=SALARY_RATE_CHOICES, 
        blank=True, 
        null=True,
        help_text="How often the user wants to be paid"
    )

    # New availability field
    availability = models.JSONField(
        default=dict,
        blank=True,
        null=True,
        help_text="Weekly availability schedule as JSON object"
    )

    # ID and Documents
    employee_id = models.CharField(max_length=15, null=True, blank=True)

    # government_id_type = models.CharField(max_length=50, choices=[('Drivers Licence', 'Drivers Licence')], blank=True)
    marital_status = models.CharField(max_length=50, choices=[('Single', 'Single'), ('Married', 'Married'), ('Divorced', 'Divorced'), ('Widowed', 'Widowed'),  ('Others', 'Others')], blank=True)
  
    # Image fields and their corresponding URL fields
    # profile_image = models.ImageField(upload_to='profile_image/', max_length=255, blank=True, null=True)
    profile_image = models.FileField(
        upload_to='profile_image/', 
        max_length=255, 
        blank=True, 
        null=True,
        validators=[validate_image_or_pdf]
    )

    
    profile_image_url = models.CharField(max_length=1024, blank=True, null=True)

    # Driving Risk Assessment (B)
    is_driver = models.BooleanField(default=False)
    type_of_vehicle = models.CharField(max_length=50, blank=True)

    # drivers_licence_image1 = models.ImageField(upload_to='driver_licences/', blank=True, null=True)
    drivers_licence_image1 = models.FileField(
        upload_to='driver_licences/', 
        blank=True, 
        null=True,
        validators=[validate_image_or_pdf]
    )
    drivers_licence_image1_url = models.CharField(max_length=1024, blank=True, null=True)

    # drivers_licence_image2 = models.ImageField(upload_to='driver_licences/',max_length=255, blank=True, null=True)
    drivers_licence_image2 = models.FileField(
        upload_to='driver_licences/', 
        blank=True, 
        null=True,
        validators=[validate_image_or_pdf]
    )
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

    # Right_to_Work_file = models.ImageField(upload_to='right_to_work/', max_length=255, blank=True, null=True)
    Right_to_Work_file = models.FileField(
        upload_to='right_to_work/', 
        max_length=255, 
        blank=True, 
        null=True,
        validators=[validate_image_or_pdf]
    )
    Right_to_Work_file_url = models.CharField(max_length=1024, blank=True, null=True)
    

    
    # Right_to_rent_file = models.ImageField(upload_to='right_to_work/', max_length=255, blank=True, null=True)
    Right_to_rent_file = models.FileField(
        upload_to='right_to_rent/', 
        max_length=255, 
        blank=True, 
        null=True,
        validators=[validate_image_or_pdf]
    )
    Right_to_rent_file_url = models.CharField(max_length=1024, blank=True, null=True)

    Right_to_Work_country_of_issue = models.CharField(max_length=100, blank=True)
    Right_to_Work_restrictions = models.CharField(max_length=255, blank=True)

    #DBS CHECK
    dbs_type = models.CharField(max_length=100,  blank=True)

    # dbs_certificate = models.ImageField(upload_to='dbs_certificates/', max_length=255, blank=True, null=True)
    dbs_certificate = models.FileField(
        upload_to='dbs_certificates/', 
        max_length=255, 
        blank=True, 
        null=True,
        validators=[validate_image_or_pdf]
    )
    dbs_certificate_url = models.CharField(max_length=1024, blank=True, null=True)

    dbs_certificate_number = models.CharField(max_length=100, blank=True)
    dbs_issue_date = models.DateField(null=True, blank=True)

    # dbs_update_file = models.ImageField(upload_to='dbs_update_service/', max_length=255, blank=True, null=True)
    dbs_update_file = models.FileField(
        upload_to='dbs_update_service/', 
        max_length=255, 
        blank=True, 
        null=True,
        validators=[validate_image_or_pdf]
    )
    dbs_update_file_url = models.CharField(max_length=1024, blank=True, null=True)

    dbs_update_certificate_number = models.CharField(max_length=100, blank=True)
    dbs_update_issue_date = models.DateField(null=True, blank=True)

    dbs_status_check = models.BooleanField(default=False)

    # Bank Details
    bank_name = models.CharField(max_length=255, blank=True)
    currency = models.CharField(max_length=5, blank=True)
    account_number = models.CharField(max_length=20, blank=True)
    account_name = models.CharField(max_length=255, blank=True)
    account_type = models.CharField(max_length=50, choices=[('Current', 'Current'), ('Savings', 'Savings'), ('Business', 'Business'),
                                                             ('Individual', 'Individual'),('Checking', 'Checking')], blank=True)

    country_of_bank_account = models.CharField(max_length=10,choices=[('US', 'United States'), ('UK', 'United Kingdom'), ('Others', 'Others')],
        blank=True, help_text="Country where the bank account is held")

    # US-specific
    routing_number = models.CharField(max_length=9,validators=[RegexValidator(r'^\d{9}$')],
        blank=True,null=True, help_text="US Routing Number (9 digits)")
 
    ssn_last4 = models.CharField(max_length=4,
        validators=[RegexValidator(r'^\d{4}$')],
        blank=True,null=True, help_text="Last 4 digits of SSN (Optional)")

    # UK-specific
    sort_code = models.CharField(max_length=8,validators=[RegexValidator(r'^\d{2}-?\d{2}-?\d{2}$')],
        blank=True, null=True,help_text="UK Sort Code (e.g., 12-34-56)"
    )

    iban = models.CharField(max_length=34,blank=True,null=True,
        help_text="IBAN (for international transfers)"
    )
    bic_swift = models.CharField(max_length=11,blank=True,null=True,
        help_text="SWIFT/BIC Code"
    )
    national_insurance_number = models.CharField(
        max_length=20,blank=True,null=True,
        help_text="NI Number (Optional)"
    )

    # Consent and tracking
    consent_given = models.BooleanField(default=False)
    bank_details_submitted_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

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
    last_updated_by_id = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

        indexes = [
            models.Index(fields=['employee_id']),
            models.Index(fields=['user']),
        ]

    # def save(self, *args, **kwargs):
    #     if not self.employee_id and self.user and self.user.tenant:
    #         tenant = self.user.tenant
    #         tenant_code = tenant.name.strip().upper()[:3]  # e.g., "PRO" from "Proliance"

    #         # Get the max employee_id that starts with this tenant code
    #         last_employee = UserProfile.objects.filter(
    #             user__tenant=tenant,
    #             employee_id__startswith=tenant_code
    #         ).aggregate(
    #             max_id=models.Max('employee_id')
    #         )['max_id']

    #         if last_employee:
    #             try:
    #                 last_number = int(last_employee.split('-')[1])
    #             except (IndexError, ValueError):
    #                 last_number = 0
    #         else:
    #             last_number = 0

    #         next_number = last_number + 1
    #         self.employee_id = f"{tenant_code}-{next_number:04d}"

    #     super().save(*args, **kwargs)


    def save(self, *args, **kwargs):
            # Existing employee_id generation logic
            if not self.employee_id and self.user and self.user.tenant:
                tenant = self.user.tenant
                tenant_code = tenant.name.strip().upper()[:3]  # e.g., "PRO" from "Proliance"

                # Get the max employee_id that starts with this tenant code
                last_employee = UserProfile.objects.filter(
                    user__tenant=tenant,
                    employee_id__startswith=tenant_code
                ).aggregate(
                    max_id=models.Max('employee_id')
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

            # New policy_number generation logic for investors
            if (self.user and self.user.role == 'investor' and 
                not self.policy_number and self.user.tenant):
                tenant = self.user.tenant
                tenant_code = tenant.name.strip().upper()[:3]  # e.g., "PRO" from "Proliance"

                # Get the max policy_number that starts with this tenant code for investors
                last_policy = UserProfile.objects.filter(
                    user__tenant=tenant,
                    user__role='investor',
                    policy_number__startswith=tenant_code
                ).aggregate(
                    max_id=models.Max('policy_number')
                )['max_id']

                if last_policy:
                    try:
                        last_number = int(last_policy.split('-')[1])
                    except (IndexError, ValueError):
                        last_number = 0
                else:
                    last_number = 0

                next_number = last_number + 1
                self.policy_number = f"{tenant_code}-{next_number:06d}"

            super().save(*args, **kwargs)



class InvestmentDetail(models.Model):
    ROI_RATE_CHOICES = [
        ('on_demand', 'On Demand (Flexible)'),  # ✅ New option for frontend-defined ROI rate
        ('hourly', 'Hourly'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('bi_weekly', 'Bi-Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('semi_annual', 'Semi-Annual'),
        ('annual', 'Annual'),
        ('one_time', 'One-Time'),
        ('others', 'Others'),
    ]

    roi_rate = models.CharField(
        max_length=20,
        choices=ROI_RATE_CHOICES,
        blank=True,
        null=True,
        help_text="How often the user wants to receive ROI (set to 'On Demand' if flexible)"
    )

    # Optional: If you want to store the actual custom ROI rate from frontend
    custom_roi_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Custom ROI rate value when roi_rate is 'on_demand'"
    )
    user_profile = models.ForeignKey(
        'UserProfile',
        on_delete=models.CASCADE,
        related_name='investment_details'
    )
    investment_amount = models.DecimalField(max_digits=20, decimal_places=2)
    investment_start_date = models.DateTimeField(default=now)
    last_updated_by_id = models.CharField(max_length=100, blank=True, null=True)

    # ✅ OPTIONAL: Add remaining_balance for better withdrawal tracking
    remaining_balance = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0,  # Computed from investment_amount minus total withdrawals
        help_text="Current available balance after withdrawals"
    )

    class Meta:
        verbose_name = "Investment Detail"
        verbose_name_plural = "Investment Details"

    def save(self, *args, **kwargs):
        if self.pk:
            total_withdrawals = self.withdrawals.aggregate(total=models.Sum('withdrawal_amount'))['total'] or 0
            self.remaining_balance = self.investment_amount - total_withdrawals
        else:
            self.remaining_balance = self.investment_amount  # Initial value for new instances
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user_profile} - ${self.investment_amount}"


class WithdrawalDetail(models.Model):


    # ✅ NEW: ForeignKey to InvestmentDetail for dependency enforcement
    investment = models.ForeignKey(
        InvestmentDetail,
        on_delete=models.CASCADE,
        related_name='withdrawals',
        help_text="The investment this withdrawal is made against"
    )

    # Keep user_profile for backward compatibility/queries, but make it derived/read-only in practice
    user_profile = models.ForeignKey(
        'UserProfile',
        on_delete=models.CASCADE,
        related_name='withdrawal_details',  # Updated related_name to avoid conflict with InvestmentDetail
    )

    last_updated_by_id = models.CharField(max_length=100, blank=True, null=True)
    withdrawal_amount = models.DecimalField(max_digits=20, decimal_places=2)
    withdrawal_request_date = models.DateTimeField(default=now)
    withdrawal_approved_date = models.DateTimeField(default=now)
    withdrawal_approved = models.BooleanField(default=False)
    withdrawal_approved_by = models.JSONField(
        blank=True, null=True,
        help_text="JSON object with approver details: {'id': str, 'email': str, 'first_name': str, 'last_name': str, 'role': str}"
    )
    withdrawn_date = models.DateTimeField(default=now)
    withdrawan = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Withdrawal Detail"
        verbose_name_plural = "Withdrawal Details"

    def save(self, *args, **kwargs):
        # ✅ ENFORCE DEPENDENCY: Ensure user_profile matches the investment's user_profile
        if self.investment:
            self.user_profile = self.investment.user_profile
        super().save(*args, **kwargs)

    # def __str__(self):
    #     return f"{self.user_profile} - {self.roi_rate or 'Not Set'} - {self.investment}"
    def __str__(self):
        return f"{self.user_profile} - {self.investment.roi_rate or 'Not Set'} - {self.investment}"


class ProfessionalQualification(models.Model):
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='professional_qualifications')
    name = models.CharField(max_length=255)
    # image_file = models.ImageField(upload_to='professional_qualifications/', max_length=255, blank=True, null=True)
    image_file = models.FileField(
        upload_to='professional_qualifications/', 
        max_length=255, 
        blank=True, 
        null=True,
        validators=[validate_image_or_pdf]
    )
    image_file_url = models.CharField(max_length=1024, blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    last_updated_by_id = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        verbose_name_plural = "Professional Qualifications"



class EducationDetail(models.Model):
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='education_details')
    institution = models.CharField(max_length=255)
    highest_qualification = models.CharField(max_length=255)
    course_of_study = models.CharField(max_length=255)
    start_year = models.PositiveIntegerField(blank=True, null=True)  # Keep as integer for now
    end_year = models.PositiveIntegerField(blank=True, null=True)    # Keep as integer for now


    start_year_new = models.DateField(blank=True, null=True)
    end_year_new = models.DateField(blank=True, null=True)

    certificate = models.FileField(
        upload_to='Educational-certificates/',
        max_length=255,
        blank=True,
        null=True,
        validators=[validate_image_or_pdf]
    )
    certificate_url = models.CharField(max_length=1024, blank=True, null=True)
    skills = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    last_updated_by_id = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        verbose_name = "Education Detail"
        verbose_name_plural = "Education Details"


class SkillDetail(models.Model):
    PROFICIENCY_LEVELS = [
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
        ('expert', 'Expert'),
    ]

    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='skill_details')
    skill_name = models.CharField(max_length=255, help_text="Name of the skill")
    proficiency_level = models.CharField(
        max_length=20,
        choices=PROFICIENCY_LEVELS,
        blank=True,
        null=True,
        help_text="Level of proficiency in this skill"
    )
    description = models.TextField(blank=True, help_text="Description of the skill and experience")
    acquired_date = models.DateField(blank=True, null=True, help_text="When the skill was acquired")
    years_of_experience = models.PositiveIntegerField(blank=True, null=True, help_text="Years of experience with this skill")

    # Optional document/file for the skill
    certificate = models.FileField(
        upload_to='skill-certificates/',
        max_length=255,
        blank=True,
        null=True,
        validators=[validate_image_or_pdf],
        help_text="Certificate or document proving this skill"
    )
    certificate_url = models.CharField(max_length=1024, blank=True, null=True)

    uploaded_at = models.DateTimeField(auto_now_add=True)
    last_updated_by_id = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        verbose_name = "Skill Detail"
        verbose_name_plural = "Skill Details"
        unique_together = ('user_profile', 'skill_name')  # Prevent duplicate skills per user

    def __str__(self):
        return f"{self.skill_name} - {self.user_profile.user.email}"


class EmploymentDetail(models.Model):

    SALARY_RATE_CHOICES = [
        ('hourly', 'Hourly'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('bi_weekly', 'Bi-Weekly'),
        ('monthly', 'Monthly'),
        ('annual', 'Annual'),
        ]

        # Add the salary rate field
    salary_rate = models.CharField(
        max_length=20, 
        choices=SALARY_RATE_CHOICES, 
        blank=True, 
        null=True,
        help_text="How often the user wants to be paid"
    )

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
    last_updated_by_id = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        verbose_name = "Employment Detail"
        verbose_name_plural = "Employment Details"


class ReferenceCheck(models.Model):
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='reference_checks')
    name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=15)
    email = models.EmailField()
    relationship_to_applicant = models.CharField(max_length=100)
    last_updated_by_id = models.CharField(max_length=100, blank=True, null=True)

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
    # document = models.ImageField(upload_to='proof_of_address/', max_length=255, blank=True, null=True)
    document = models.FileField(
        upload_to='proof_of_address/', 
        max_length=255, 
        blank=True, 
        null=True,
        validators=[validate_image_or_pdf]
    )
    document_url = models.CharField(max_length=1024, blank=True, null=True)
    issue_date = models.DateField(null=True, blank=True)
    # nin = models.CharField(max_length=20, blank=True, null=True, verbose_name="National Insurance Number (NIN)")
    nin_document = models.FileField(
        upload_to='nin_documents/', 
        max_length=255, 
        blank=True, 
        null=True,
        validators=[validate_image_or_pdf]
    )
    nin_document = models.ImageField(upload_to='nin_documents/', max_length=255, blank=True, null=True)
    nin_document_url = models.CharField(max_length=1024, blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    last_updated_by_id = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"{self.user_profile.user.email} - {self.type}"

class InsuranceVerification(models.Model):
    INSURANCE_TYPES = [
        ('public_liability', 'Public Liability'),
        ('professional_indemnity', 'Professional Indemnity')
    ]
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='insurance_verifications')
    insurance_type = models.CharField(max_length=50, choices=INSURANCE_TYPES)
    # document = models.ImageField(upload_to='insurance_documents/', max_length=255, blank=True, null=True)
    document = models.FileField(
        upload_to='insurance_documents/', 
        max_length=255, 
        blank=True, 
        null=True,
        validators=[validate_image_or_pdf]
    )
    document_url = models.CharField(max_length=1024, blank=True, null=True)
    provider_name = models.CharField(max_length=255, blank=True, null=True)
    coverage_start_date = models.DateField(blank=True, null=True)
    expiry_date = models.DateField(blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    last_updated_by_id = models.CharField(max_length=100, blank=True, null=True)

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
    # supporting_document = models.ImageField(upload_to='driving_risk_docs/', max_length=255, blank=True, null=True)
    supporting_document = models.FileField(
        upload_to='driving_risk_docs/', 
        max_length=255, 
        blank=True, 
        null=True,
        validators=[validate_image_or_pdf]
    )
    supporting_document_url = models.CharField(max_length=1024, blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    last_updated_by_id = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"{self.user_profile.user.email} - Driving Risk Assessment"

class LegalWorkEligibility(models.Model):
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='legal_work_eligibilities')
    evidence_of_right_to_rent = models.BooleanField(default=False)
    # document = models.ImageField(upload_to='legal_work_docs/', max_length=255, blank=True, null=True)
    document = models.FileField(
        upload_to='legal_work_docs/', 
        max_length=255, 
        blank=True, 
        null=True,
        validators=[validate_image_or_pdf]
    )
    document_url = models.CharField(max_length=1024, blank=True, null=True)
    expiry_date = models.DateField(blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    last_updated_by_id = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"{self.user_profile.user.email} - Legal & Work Eligibility"

class OtherUserDocuments(models.Model):
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='other_user_documents')
    government_id_type = models.CharField(max_length=100, blank=True)
    title = models.CharField(max_length=255, blank=True)
    document_number = models.CharField(max_length=20, blank=True)
    expiry_date = models.DateField(blank=True, null=True)
    # file = models.ImageField(upload_to='other_user_documents', max_length=255, blank=True, null=True)
    file = models.FileField(
        upload_to='other_user_documents',
        max_length=255, 
        blank=True, 
        null=True,
        validators=[validate_image_or_pdf]
    )
    file_url = models.CharField(max_length=1024, blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    last_updated_by_id = models.CharField(max_length=100, blank=True, null=True)

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
 
    # photo = models.ImageField(upload_to='client_photos/', max_length=255, blank=True, null=True)
    photo = models.FileField(
        upload_to='client_photos/', 
        max_length=255, 
        blank=True, 
        null=True,
        validators=[validate_image_or_pdf]
    )
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
    last_updated_by_id = models.CharField(max_length=100, blank=True, null=True)

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


class RSAKeyPair(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='rsa_keys')
    kid = models.CharField(max_length=64, unique=True, default=generate_kid)
    private_key_pem = models.TextField()  # PEM encoded private key
    public_key_pem = models.TextField()   # PEM encoded public key
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    active = models.BooleanField(default=True)
    last_updated_by_id = models.CharField(max_length=100, blank=True, null=True)

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
    description = models.TextField(blank=True)
    file_url = models.URLField(max_length=500, blank=True, null=True)
    file_path = models.CharField(max_length=500, blank=True, null=True)
    file_type = models.CharField(max_length=100, blank=True, null=True)
    file_size = models.BigIntegerField(blank=True, null=True)
    version = models.IntegerField(default=1)
    uploaded_by_id = models.CharField(max_length=255, blank=True, null=True)
    updated_by_id = models.CharField(max_length=255, blank=True, null=True)
    last_updated_by_id = models.CharField(max_length=255, blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expiring_date = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=50, default="active")
    document_number = models.CharField(max_length=100, unique=True, blank=True, null=True)
    tags = models.CharField(max_length=500, blank=True, default='', help_text='Comma-separated tags (e.g., "tag1, tag2, tag3")')

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

class DocumentPermission(models.Model):
    PERMISSION_CHOICES = [
        ('view', 'View Only'),
        ('view_download', 'View and Download'),
    ]
    
    document = models.ForeignKey('Document', on_delete=models.CASCADE, related_name='permissions')
    user_id = models.CharField(max_length=255)
    email = models.EmailField(max_length=255)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    role = models.CharField(max_length=100)
    permission_level = models.CharField(max_length=20, choices=PERMISSION_CHOICES)
    tenant_id = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('document', 'user_id', 'tenant_id')
        indexes = [
            models.Index(fields=['document', 'tenant_id']),
            models.Index(fields=['user_id', 'tenant_id']),
        ]

class DocumentAcknowledgment(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='acknowledgments')
    user_id = models.CharField(max_length=255)
    email = models.EmailField(max_length=255)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    role = models.CharField(max_length=100)
    acknowledged_at = models.DateTimeField(auto_now_add=True)
    tenant_id = models.CharField(max_length=255)

    class Meta:
        unique_together = ('document', 'user_id', 'tenant_id')
        indexes = [
            models.Index(fields=['document', 'tenant_id']),
            models.Index(fields=['user_id', 'tenant_id']),
        ]


class Group(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='groups')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_updated_by_id = models.CharField(max_length=100, blank=True, null=True)

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

