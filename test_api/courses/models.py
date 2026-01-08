from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.text import slugify
import json
from django.utils import timezone
import uuid
import os
import logging
from django.conf import settings
from activitylog.models import ActivityLog

logger = logging.getLogger('courses')

def course_thumbnail_path(instance, filename):
    return f'courses/{instance.tenant_id}/{instance.slug}/thumbnails/{filename}'

def certificate_logo_path(instance, filename):
    ext = os.path.splitext(filename)[1]
    new_filename = f"{uuid.uuid4().hex}{ext}"
    return os.path.join('courses', instance.tenant_id, str(instance.course.id), 'certificates', 'logos', new_filename)

def certificate_signature_path(instance, filename):
    ext = os.path.splitext(filename)[1]
    new_filename = f"{uuid.uuid4().hex}{ext}"
    return os.path.join('courses', instance.tenant_id, str(instance.course.id), 'certificates', 'signatures', new_filename)

def resource_file_path(instance, filename):
    return f'courses/{instance.course.tenant_id}/{instance.course.slug}/resources/{filename}'

def scorm_package_path(instance, filename):
    return f'courses/{instance.course.tenant_id}/{instance.course.slug}/scorm_packages/{filename}'

def assignment_instructions_path(instance, filename):
    return f'courses/{instance.course.tenant_id}/{instance.course.slug}/assignments/instructions/{filename}'

def assignment_submission_path(instance, filename):
    return f'courses/{instance.assignment.course.tenant_id}/{instance.assignment.course.slug}/assignments/submissions/{filename}'

def get_tenant_name(tenant_id, tenant_name=None):
    """
    Simplified tenant name resolver.
    Prefer passing tenant_name from request JWT payload (via serializer).
    Returns passed tenant_name if available, otherwise None (no network call).
    """
    return tenant_name

class Category(models.Model):
    id = models.AutoField(primary_key=True)
    tenant_id = models.CharField(max_length=36, blank=False, null=False)
    tenant_name = models.CharField(max_length=255, blank=True, null=True, help_text="Tenant name for reference")
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    created_by = models.JSONField(null=True, blank=True)
    last_edited_by = models.JSONField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "Categories"
        unique_together = ['tenant_id', 'name']
        indexes = [
            models.Index(fields=['tenant_id', 'slug'], name='idx_cat_tenant_slug'),
        ]

    def __str__(self):
        return f"{self.name} (Tenant: {self.tenant_id})"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        is_new = self._state.adding
        super().save(*args, **kwargs)
        ActivityLog.objects.create(
            tenant_id=self.tenant_id,
            tenant_name=self.tenant_name,
            user_id=self.created_by.get('id') if self.created_by else None,
            activity_type='category_created' if is_new else 'category_updated',
            details=f"Category {self.name} {'created' if is_new else 'updated'}",
            status='success'
        )
        logger.info(f"[Tenant {self.tenant_id}] Category {self.id} {'created' if is_new else 'updated'}: {self.name}")

    def delete(self, *args, **kwargs):
        ActivityLog.objects.create(
            tenant_id=self.tenant_id,
            tenant_name=self.tenant_name,
            user_id=self.created_by.get('id') if self.created_by else None,
            activity_type='category_deleted',
            details=f"Category {self.name} deleted",
            status='success'
        )
        logger.info(f"[Tenant {self.tenant_id}] Category {self.id} deleted: {self.name}")
        super().delete(*args, **kwargs)



class Course(models.Model):
    STATUS_CHOICES = [
        ('Draft', 'Draft'),
        ('Published', 'Published'),
        ('Archived', 'Archived'),
    ]
    LEVEL_CHOICES = [
        ('Beginner', 'Beginner'),
        ('Intermediate', 'Intermediate'),
        ('Advanced', 'Advanced'),
    ]
    CURRENCY_CHOICES = [
        ('NGN', 'Naira (₦)'),
        ('USD', 'Dollar ($)'),
        ('EUR', 'Euro (€)'),
        ('GBP', 'Pound (£)'),
        ('JPY', 'Yen (¥)'),
        ('AUD', 'Australian Dollar (A$)'),
        ('CAD', 'Canadian Dollar (C$)'),
        ('CHF', 'Swiss Franc (CHF)'),
        ('CNY', 'Yuan (¥)'),
        ('INR', 'Indian Rupee (₹)'),
    ]
    COURSE_TYPE_CHOICES = [
        ('manual', 'Manual'),
        ('scorm', 'SCORM'),
    ]

    id = models.AutoField(primary_key=True)
    tenant_id = models.CharField(max_length=36, blank=False, null=False)
    tenant_name = models.CharField(max_length=255, blank=True, null=True, help_text="Tenant name for reference")
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, blank=True)
    code = models.CharField(max_length=50)
    description = models.TextField()
    short_description = models.CharField(max_length=300, blank=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='Beginner')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Draft')
    duration = models.CharField(max_length=100, blank=True)
    is_free = models.BooleanField(default=False)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=None)
    discount_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=None)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='NGN')
    thumbnail = models.ImageField(upload_to=course_thumbnail_path, null=True, blank=True, max_length=255)
    thumbnail_url = models.CharField(max_length=1024, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.JSONField(null=True, blank=True)
    last_edited_by = models.JSONField(null=True, blank=True)
    learning_outcomes = models.JSONField(default=list)
    prerequisites = models.JSONField(default=list)
    completion_hours = models.PositiveIntegerField(default=0, help_text="Estimated hours to complete the course")
    course_type = models.CharField(max_length=20, choices=COURSE_TYPE_CHOICES, default='manual')
    scorm_launch_path = models.CharField(max_length=255, blank=True, null=True)
    scorm_metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ['tenant_id', 'code']
        indexes = [
            models.Index(fields=['tenant_id', 'slug'], name='idx_crs_tenant_slug'),
            # models.Index(fields=['created_by_id'], name='idx_crs_created_by'),
        ]

    def __str__(self):
        return f"{self.title} (Tenant: {self.tenant_id})"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        if not self.code:
            tenant_name = self.tenant_name or 'COURSE'
            self.code = f"{tenant_name}-{uuid.uuid4().hex[:8]}"
        if isinstance(self.learning_outcomes, list):
            self.learning_outcomes = [str(item) for item in self.learning_outcomes]
        elif isinstance(self.learning_outcomes, str):
            try:
                parsed = json.loads(self.learning_outcomes)
                self.learning_outcomes = [str(item) for item in parsed] if isinstance(parsed, list) else [self.learning_outcomes]
            except json.JSONDecodeError:
                self.learning_outcomes = [self.learning_outcomes]
        if isinstance(self.prerequisites, list):
            self.prerequisites = [str(item) for item in self.prerequisites]
        elif isinstance(self.prerequisites, str):
            try:
                parsed = json.loads(self.prerequisites)
                self.prerequisites = [str(item) for item in parsed] if isinstance(parsed, list) else [self.prerequisites]
            except json.JSONDecodeError:
                self.prerequisites = [self.prerequisites]
        if self.is_free:
            self.price = None
            self.discount_price = None
        is_new = self._state.adding
        super().save(*args, **kwargs)
        ActivityLog.objects.create(
            tenant_id=self.tenant_id,
            tenant_name=self.tenant_name,
            user_id=self.created_by.get('id') if self.created_by else None,
            activity_type='course_created' if is_new else 'course_updated',
            details=f"Course {self.title} {'created' if is_new else 'updated'}",
            status='success'
        )
        logger.info(f"[Tenant {self.tenant_id}] Course {self.id} {'created' if is_new else 'updated'}: {self.title}")

    def delete(self, *args, **kwargs):
        ActivityLog.objects.create(
            tenant_id=self.tenant_id,
            tenant_name=self.tenant_name,
            user_id=self.created_by.get('id') if self.created_by else None,
            activity_type='course_deleted',
            details=f"Course {self.title} deleted",
            status='success'
        )
        logger.info(f"[Tenant {self.tenant_id}] Course {self.id} deleted: {self.title}")
        super().delete(*args, **kwargs)

    @property
    def current_price(self):
        return self.discount_price if self.discount_price else self.price

class Module(models.Model):
    id = models.AutoField(primary_key=True)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='modules')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=True)
    created_by = models.JSONField(null=True, blank=True)
    last_edited_by = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ['order']
        unique_together = ['course', 'order']
        indexes = [
            models.Index(fields=['course', 'order'], name='idx_mod_crs_order'),
        ]

    def __str__(self):
        return f"{self.course.title} - {self.title} (Tenant: {self.course.tenant_id})"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        ActivityLog.objects.create(
            tenant_id=self.course.tenant_id,
            tenant_name=self.course.tenant_name,
            user_id=None,
            activity_type='module_created' if is_new else 'module_updated',
            details=f"Module {self.title} for course {self.course.title} {'created' if is_new else 'updated'}",
            status='success'
        )
        logger.info(f"[Tenant {self.course.tenant_id}] Module {self.id} {'created' if is_new else 'updated'}: {self.title}")

    def delete(self, *args, **kwargs):
        ActivityLog.objects.create(
            tenant_id=self.course.tenant_id,
            tenant_name=self.course.tenant_name,
            user_id=None,
            activity_type='module_deleted',
            details=f"Module {self.title} for course {self.course.title} deleted",
            status='success'
        )
        logger.info(f"[Tenant {self.course.tenant_id}] Module {self.id} deleted: {self.title}")
        super().delete(*args, **kwargs)

class Lesson(models.Model):
    LESSON_TYPE_CHOICES = [
        ('video', 'Video'),
        ('quiz', 'Quiz'),
        ('assignment', 'Assignment'),
        ('text', 'Text'),
        ('file', 'File'),
        ('link', 'Link'),
    ]

    id = models.AutoField(primary_key=True)
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='lessons')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    lesson_type = models.CharField(max_length=20, choices=LESSON_TYPE_CHOICES, default='video')
    duration = models.CharField(max_length=20, help_text="Duration in minutes", default="1 hour")
    content_url = models.URLField(blank=True)
    content_file = models.FileField(null=True, blank=True, max_length=255)
    content_file_url = models.CharField(max_length=1024, blank=True, null=True)
    content_text = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=True)
    created_by = models.JSONField(null=True, blank=True)
    last_edited_by = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ['order']
        unique_together = ['module', 'order']
        indexes = [
            models.Index(fields=['module', 'order'], name='idx_lsn_mod_order'),
        ]

    def __str__(self):
        return f"{self.module.title} - {self.title} (Tenant: {self.module.course.tenant_id})"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        ActivityLog.objects.create(
            tenant_id=self.module.course.tenant_id,
            tenant_name=self.module.course.tenant_name,
            user_id=None,
            activity_type='lesson_created' if is_new else 'lesson_updated',
            details=f"Lesson {self.title} for module {self.module.title} {'created' if is_new else 'updated'}",
            status='success'
        )
        logger.info(f"[Tenant {self.module.course.tenant_id}] Lesson {self.id} {'created' if is_new else 'updated'}: {self.title}")

    def delete(self, *args, **kwargs):
        ActivityLog.objects.create(
            tenant_id=self.module.course.tenant_id,
            tenant_name=self.module.course.tenant_name,
            user_id=None,
            activity_type='lesson_deleted',
            details=f"Lesson {self.title} for module {self.module.title} deleted",
            status='success'
        )
        logger.info(f"[Tenant {self.module.course.tenant_id}] Lesson {self.id} deleted: {self.title}")
        super().delete(*args, **kwargs)

    @property
    def duration_display(self):
        try:
            duration = int(self.duration)
            hours = duration // 60
            minutes = duration % 60
            if hours > 0:
                return f"{hours}h {minutes}m"
            return f"{minutes}m"
        except (ValueError, TypeError):
            return self.duration

class Resource(models.Model):
    RESOURCE_TYPE_CHOICES = [
        ('link', 'Web Link'),
        ('pdf', 'PDF Document'),
        ('video', 'Video'),
        ('file', 'File'),
    ]

    id = models.AutoField(primary_key=True)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='resources')
    title = models.CharField(max_length=200)
    resource_type = models.CharField(max_length=20, choices=RESOURCE_TYPE_CHOICES)
    url = models.URLField(blank=True)
    file = models.FileField(upload_to=resource_file_path, blank=True, null=True)
    file_url = models.CharField(max_length=1024, blank=True, null=True)
    order = models.PositiveIntegerField(default=0)
    created_by = models.JSONField(null=True, blank=True)
    last_edited_by = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ['order']
        indexes = [
            models.Index(fields=['course', 'order'], name='idx_res_crs_order'),
        ]

    def __str__(self):
        return f"{self.course.title} - {self.title} (Tenant: {self.course.tenant_id})"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        ActivityLog.objects.create(
            tenant_id=self.course.tenant_id,
            tenant_name=self.course.tenant_name,
            user_id=None,
            activity_type='resource_created' if is_new else 'resource_updated',
            details=f"Resource {self.title} for course {self.course.title} {'created' if is_new else 'updated'}",
            status='success'
        )
        logger.info(f"[Tenant {self.course.tenant_id}] Resource {self.id} {'created' if is_new else 'updated'}: {self.title}")

    def delete(self, *args, **kwargs):
        ActivityLog.objects.create(
            tenant_id=self.course.tenant_id,
            tenant_name=self.course.tenant_name,
            user_id=None,
            activity_type='resource_deleted',
            details=f"Resource {self.title} for course {self.course.title} deleted",
            status='success'
        )
        logger.info(f"[Tenant {self.course.tenant_id}] Resource {self.id} deleted: {self.title}")
        super().delete(*args, **kwargs)

class Instructor(models.Model):
    id = models.AutoField(primary_key=True)
    tenant_id = models.CharField(max_length=36, blank=False, null=False)
    tenant_name = models.CharField(max_length=255, blank=True, null=True, help_text="Tenant name for reference")
    user_id = models.CharField(max_length=36, unique=True)  # From auth-service
    bio = models.TextField(blank=True)
    expertise = models.ManyToManyField(Category, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.JSONField(null=True, blank=True)
    last_edited_by = models.JSONField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['tenant_id', 'user_id'], name='idx_ins_tenant_user'),
        ]

    def __str__(self):
        return f"Instructor {self.user_id} (Tenant: {self.tenant_id})"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        ActivityLog.objects.create(
            tenant_id=self.tenant_id,
            tenant_name=self.tenant_name,
            user_id=self.user_id,
            activity_type='instructor_created' if is_new else 'instructor_updated',
            details=f"Instructor profile for user {self.user_id} {'created' if is_new else 'updated'}",
            status='success'
        )
        logger.info(f"[Tenant {self.tenant_id}] Instructor {self.id} {'created' if is_new else 'updated'}: {self.user_id}")

    def delete(self, *args, **kwargs):
        ActivityLog.objects.create(
            tenant_id=self.tenant_id,
            tenant_name=self.tenant_name,
            user_id=self.user_id,
            activity_type='instructor_deleted',
            details=f"Instructor profile for user {self.user_id} deleted",
            status='success'
        )
        logger.info(f"[Tenant {self.tenant_id}] Instructor {self.id} deleted: {self.user_id}")
        super().delete(*args, **kwargs)

class CourseInstructor(models.Model):
    ASSIGNMENT_CHOICES = [
        ('all', 'Entire Course'),
        ('specific', 'Specific Modules'),
    ]

    id = models.AutoField(primary_key=True)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='course_instructors')
    instructor_id = models.CharField(max_length=36)  # From auth-service
    assignment_type = models.CharField(max_length=20, choices=ASSIGNMENT_CHOICES, default='all')
    is_active = models.BooleanField(default=True)
    modules = models.ManyToManyField(Module, blank=True)
    created_by = models.JSONField(null=True, blank=True)
    last_edited_by = models.JSONField(null=True, blank=True)

    class Meta:
        unique_together = ['course', 'instructor_id']
        indexes = [
            models.Index(fields=['course', 'instructor_id'], name='idx_crs_ins_crs_ins'),
        ]

    def __str__(self):
        return f"Instructor {self.instructor_id} - {self.course.title} (Tenant: {self.course.tenant_id})"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        ActivityLog.objects.create(
            tenant_id=self.course.tenant_id,
            tenant_name=self.course.tenant_name,
            user_id=self.instructor_id,
            activity_type='courseinstructor_created' if is_new else 'courseinstructor_updated',
            details=f"CourseInstructor for {self.course.title} and instructor {self.instructor_id} {'created' if is_new else 'updated'}",
            status='success'
        )
        logger.info(f"[Tenant {self.course.tenant_id}] CourseInstructor {self.id} {'created' if is_new else 'updated'}: {self.instructor_id}")

    def delete(self, *args, **kwargs):
        ActivityLog.objects.create(
            tenant_id=self.course.tenant_id,
            tenant_name=self.course.tenant_name,
            user_id=self.instructor_id,
            activity_type='courseinstructor_deleted',
            details=f"CourseInstructor for {self.course.title} and instructor {self.instructor_id} deleted",
            status='success'
        )
        logger.info(f"[Tenant {self.course.tenant_id}] CourseInstructor {self.id} deleted: {self.instructor_id}")
        super().delete(*args, **kwargs)

class CertificateTemplate(models.Model):
    id = models.AutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    course = models.ForeignKey('courses.Course', on_delete=models.CASCADE, related_name='certificate_templates')
    is_active = models.BooleanField(default=True)
    template = models.CharField(max_length=50, default='default')
    custom_text = models.TextField(default='Congratulations on completing the course!')
    logo = models.FileField(upload_to=certificate_logo_path, null=True, blank=True, max_length=255)
    logo_url = models.CharField(max_length=1024, blank=True, null=True)
    signature = models.FileField(upload_to=certificate_signature_path, null=True, blank=True, max_length=255)
    signature_url = models.CharField(max_length=1024, blank=True, null=True)
    signature_name = models.CharField(max_length=100, default='Course Instructor')
    show_date = models.BooleanField(default=True)
    show_course_name = models.BooleanField(default=True)
    show_completion_hours = models.BooleanField(default=True)
    min_score = models.PositiveIntegerField(default=80)
    require_all_modules = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.JSONField(null=True, blank=True)
    last_edited_by = models.JSONField(null=True, blank=True)

    class Meta:
        unique_together = ('course',)
        indexes = [
            models.Index(fields=['course'], name='idx_cert_temp_course'),
        ]

    def __str__(self):
        return f"Certificate Template for {self.course.title} (Tenant: {self.course.tenant_id})"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        ActivityLog.objects.create(
            tenant_id=self.course.tenant_id,
            tenant_name=self.course.tenant_name,
            user_id=None,
            activity_type='certificatetemplate_created' if is_new else 'certificatetemplate_updated',
            details=f"CertificateTemplate for course {self.course.title} {'created' if is_new else 'updated'}",
            status='success'
        )
        logger.info(f"[Tenant {self.course.tenant_id}] CertificateTemplate {self.id} {'created' if is_new else 'updated'}: {self.course.title}")

    def delete(self, *args, **kwargs):
        ActivityLog.objects.create(
            tenant_id=self.course.tenant_id,
            tenant_name=self.course.tenant_name,
            user_id=None,
            activity_type='certificatetemplate_deleted',
            details=f"CertificateTemplate for course {self.course.title} deleted",
            status='success'
        )
        logger.info(f"[Tenant {self.course.tenant_id}] CertificateTemplate {self.id} deleted: {self.course.title}")
        super().delete(*args, **kwargs)

class SCORMxAPISettings(models.Model):
    STANDARD_CHOICES = [
        ('scorm12', 'SCORM 1.2'),
        ('scorm2004', 'SCORM 2004'),
        ('xapi', 'xAPI (Tin Can)'),
    ]

    id = models.AutoField(primary_key=True)
    course = models.OneToOneField(Course, on_delete=models.CASCADE, related_name='scorm_settings')
    is_active = models.BooleanField(default=False)
    standard = models.CharField(max_length=20, choices=STANDARD_CHOICES, default='scorm12')
    version = models.CharField(max_length=20, default='1.2')
    completion_threshold = models.PositiveIntegerField(
        default=80,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    score_threshold = models.PositiveIntegerField(
        default=70,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    track_completion = models.BooleanField(default=True)
    track_score = models.BooleanField(default=True)
    track_time = models.BooleanField(default=True)
    track_progress = models.BooleanField(default=True)
    package = models.FileField(upload_to=scorm_package_path, null=True, blank=True, max_length=255)
    package_url = models.CharField(max_length=1024, blank=True, null=True)
    created_by = models.JSONField(null=True, blank=True)
    last_edited_by = models.JSONField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['course'], name='idx_scorm_set_course'),
        ]

    def __str__(self):
        return f"SCORM/xAPI Settings for {self.course.title} (Tenant: {self.course.tenant_id})"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        ActivityLog.objects.create(
            tenant_id=self.course.tenant_id,
            tenant_name=self.course.tenant_name,
            user_id=None,
            activity_type='scormsettings_created' if is_new else 'scormsettings_updated',
            details=f"SCORMxAPISettings for course {self.course.title} {'created' if is_new else 'updated'}",
            status='success'
        )
        logger.info(f"[Tenant {self.course.tenant_id}] SCORMxAPISettings {self.id} {'created' if is_new else 'updated'}: {self.course.title}")

    def delete(self, *args, **kwargs):
        ActivityLog.objects.create(
            tenant_id=self.course.tenant_id,
            tenant_name=self.course.tenant_name,
            user_id=None,
            activity_type='scormsettings_deleted',
            details=f"SCORMxAPISettings for course {self.course.title} deleted",
            status='success'
        )
        logger.info(f"[Tenant {self.course.tenant_id}] SCORMxAPISettings {self.id} deleted: {self.course.title}")
        super().delete(*args, **kwargs)

class SCORMTracking(models.Model):
    id = models.AutoField(primary_key=True)
    tenant_id = models.CharField(max_length=36, blank=False, null=False)
    tenant_name = models.CharField(max_length=255, blank=True, null=True, help_text="Tenant name for reference")
    user_id = models.CharField(max_length=36)  # From auth-service
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    progress = models.PositiveIntegerField(default=0)
    score = models.PositiveIntegerField(default=0)
    completed = models.BooleanField(default=False)
    raw_data = models.JSONField(default=dict, blank=True)
    last_updated = models.DateTimeField(auto_now=True)
    created_by = models.JSONField(null=True, blank=True)
    last_edited_by = models.JSONField(null=True, blank=True)

    class Meta:
        unique_together = ['tenant_id', 'user_id', 'course']
        indexes = [
            models.Index(fields=['tenant_id', 'user_id'], name='idx_scorm_trk_tnt_usr'),
        ]

    def __str__(self):
        return f"SCORM Tracking for user {self.user_id} - {self.course.title} (Tenant: {self.tenant_id})"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        ActivityLog.objects.create(
            tenant_id=self.tenant_id,
            tenant_name=self.tenant_name,
            user_id=self.user_id,
            activity_type='scormtracking_created' if is_new else 'scormtracking_updated',
            details=f"SCORMTracking for course {self.course.title} {'created' if is_new else 'updated'}",
            status='success'
        )
        logger.info(f"[Tenant {self.tenant_id}] SCORMTracking {self.id} {'created' if is_new else 'updated'}: {self.course.title}")

    def delete(self, *args, **kwargs):
        ActivityLog.objects.create(
            tenant_id=self.tenant_id,
            tenant_name=self.tenant_name,
            user_id=self.user_id,
            activity_type='scormtracking_deleted',
            details=f"SCORMTracking for course {self.course.title} deleted",
            status='success'
        )
        logger.info(f"[Tenant {self.tenant_id}] SCORMTracking {self.id} deleted: {self.course.title}")
        super().delete(*args, **kwargs)

class LearningPath(models.Model):
    id = models.AutoField(primary_key=True)
    tenant_id = models.CharField(max_length=36, blank=False, null=False)
    tenant_name = models.CharField(max_length=255, blank=True, null=True, help_text="Tenant name for reference")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    courses = models.ManyToManyField(Course, related_name='learning_paths')
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.JSONField(null=True, blank=True)
    last_edited_by = models.JSONField(null=True, blank=True)
    updated_by_id = models.CharField(max_length=36, blank=True, null=True)  # From auth-service

    class Meta:
        ordering = ['order']
        indexes = [
            models.Index(fields=['tenant_id', 'order'], name='idx_lrn_path_tnt_ord'),
        ]

    def __str__(self):
        return f"{self.title} (Tenant: {self.tenant_id})"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        ActivityLog.objects.create(
            tenant_id=self.tenant_id,
            tenant_name=self.tenant_name,
            user_id=self.created_by.get('id') if self.created_by else None,
            activity_type='learningpath_created' if is_new else 'learningpath_updated',
            details=f"LearningPath {self.title} {'created' if is_new else 'updated'}",
            status='success'
        )
        logger.info(f"[Tenant {self.tenant_id}] LearningPath {self.id} {'created' if is_new else 'updated'}: {self.title}")

    def delete(self, *args, **kwargs):
        ActivityLog.objects.create(
            tenant_id=self.tenant_id,
            tenant_name=self.tenant_name,
            user_id=self.created_by.get('id') if self.created_by else None,
            activity_type='learningpath_deleted',
            details=f"LearningPath {self.title} deleted",
            status='success'
        )
        logger.info(f"[Tenant {self.tenant_id}] LearningPath {self.id} deleted: {self.title}")
        super().delete(*args, **kwargs)

class LessonProgress(models.Model):
    id = models.AutoField(primary_key=True)
    tenant_id = models.CharField(max_length=36, blank=False, null=False)
    tenant_name = models.CharField(max_length=255, blank=True, null=True, help_text="Tenant name for reference")
    user_id = models.CharField(max_length=36)  # From auth-service
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='progress')
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    created_by = models.JSONField(null=True, blank=True)
    last_edited_by = models.JSONField(null=True, blank=True)

    class Meta:
        unique_together = ['tenant_id', 'user_id', 'lesson']
        indexes = [
            models.Index(fields=['tenant_id', 'user_id'], name='idx_lsn_prg_tnt_usr'),
        ]

    def __str__(self):
        return f"User {self.user_id} - {self.lesson.title} - {'Completed' if self.is_completed else 'In Progress'} (Tenant: {self.tenant_id})"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        ActivityLog.objects.create(
            tenant_id=self.tenant_id,
            tenant_name=self.tenant_name,
            user_id=self.user_id,
            activity_type='lessonprogress_created' if is_new else 'lessonprogress_updated',
            details=f"LessonProgress for lesson {self.lesson.title} {'created' if is_new else 'updated'}",
            status='success'
        )
        logger.info(f"[Tenant {self.tenant_id}] LessonProgress {self.id} {'created' if is_new else 'updated'}: {self.lesson.title}")

    def delete(self, *args, **kwargs):
        ActivityLog.objects.create(
            tenant_id=self.tenant_id,
            tenant_name=self.tenant_name,
            user_id=self.user_id,
            activity_type='lessonprogress_deleted',
            details=f"LessonProgress for lesson {self.lesson.title} deleted",
            status='success'
        )
        logger.info(f"[Tenant {self.tenant_id}] LessonProgress {self.id} deleted: {self.lesson.title}")
        super().delete(*args, **kwargs)

class Enrollment(models.Model):
    id = models.AutoField(primary_key=True)
    tenant_id = models.CharField(max_length=36, blank=False, null=False)
    tenant_name = models.CharField(max_length=255, blank=True, null=True, help_text="Tenant name for reference")
    user_id = models.CharField(max_length=36)  # From auth-service
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    enrolled_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.JSONField(null=True, blank=True)
    last_edited_by = models.JSONField(null=True, blank=True)

    class Meta:
        unique_together = ['tenant_id', 'user_id', 'course']
        indexes = [
            models.Index(fields=['tenant_id', 'user_id'], name='idx_enroll_tnt_usr'),
        ]

    def __str__(self):
        return f"User {self.user_id} - {self.course.title} (Tenant: {self.tenant_id})"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        ActivityLog.objects.create(
            tenant_id=self.tenant_id,
            tenant_name=self.tenant_name,
            user_id=self.user_id,
            activity_type='enrollment_created' if is_new else 'enrollment_updated',
            details=f"Enrollment for course {self.course.title} {'created' if is_new else 'updated'}",
            status='success'
        )
        logger.info(f"[Tenant {self.tenant_id}] Enrollment {self.id} {'created' if is_new else 'updated'}: {self.course.title}")

    def delete(self, *args, **kwargs):
        ActivityLog.objects.create(
            tenant_id=self.tenant_id,
            tenant_name=self.tenant_name,
            user_id=self.user_id,
            activity_type='enrollment_deleted',
            details=f"Enrollment for course {self.course.title} deleted",
            status='success'
        )
        logger.info(f"[Tenant {self.tenant_id}] Enrollment {self.id} deleted: {self.course.title}")
        super().delete(*args, **kwargs)

    def get_progress(self):
        total_lessons = Lesson.objects.filter(module__course=self.course).count()
        completed_lessons = LessonProgress.objects.filter(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            lesson__module__course=self.course,
            is_completed=True
        ).count()
        if total_lessons == 0:
            return 0
        return int((completed_lessons / total_lessons) * 100)

class Certificate(models.Model):
    id = models.AutoField(primary_key=True)
    enrollment = models.OneToOneField(Enrollment, on_delete=models.CASCADE, related_name='certificate')
    issued_at = models.DateTimeField(auto_now_add=True)
    certificate_id = models.CharField(max_length=50)
    pdf_file = models.FileField(null=True, blank=True, max_length=255)
    pdf_file_url = models.CharField(max_length=1024, blank=True, null=True)
    created_by = models.JSONField(null=True, blank=True)
    last_edited_by = models.JSONField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['enrollment'], name='idx_cert_enrollment'),
        ]

    def __str__(self):
        return f"Certificate {self.certificate_id} for user {self.enrollment.user_id} (Tenant: {self.enrollment.tenant_id})"

    def save(self, *args, **kwargs):
        if not self.certificate_id:
            self.certificate_id = f"CERT-{self.enrollment.tenant_id}-{uuid.uuid4().hex[:8]}"
        is_new = self._state.adding
        super().save(*args, **kwargs)
        ActivityLog.objects.create(
            tenant_id=self.enrollment.tenant_id,
            tenant_name=self.enrollment.tenant_name,
            user_id=self.enrollment.user_id,
            activity_type='certificate_created' if is_new else 'certificate_updated',
            details=f"Certificate {self.certificate_id} for course {self.enrollment.course.title} {'created' if is_new else 'updated'}",
            status='success'
        )
        logger.info(f"[Tenant {self.enrollment.tenant_id}] Certificate {self.id} {'created' if is_new else 'updated'}: {self.certificate_id}")

    def delete(self, *args, **kwargs):
        ActivityLog.objects.create(
            tenant_id=self.enrollment.tenant_id,
            tenant_name=self.enrollment.tenant_name,
            user_id=self.enrollment.user_id,
            activity_type='certificate_deleted',
            details=f"Certificate {self.certificate_id} for course {self.enrollment.course.title} deleted",
            status='success'
        )
        logger.info(f"[Tenant {self.enrollment.tenant_id}] Certificate {self.id} deleted: {self.certificate_id}")
        super().delete(*args, **kwargs)

class CourseRating(models.Model):
    id = models.AutoField(primary_key=True)
    tenant_id = models.CharField(max_length=36, blank=False, null=False)
    tenant_name = models.CharField(max_length=255, blank=True, null=True, help_text="Tenant name for reference")
    user_id = models.CharField(max_length=36)  # From auth-service
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='ratings')
    rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    review = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.JSONField(null=True, blank=True)
    last_edited_by = models.JSONField(null=True, blank=True)

    class Meta:
        unique_together = ['tenant_id', 'user_id', 'course']
        indexes = [
            models.Index(fields=['tenant_id', 'user_id'], name='idx_crs_rat_tnt_usr'),
        ]

    def __str__(self):
        return f"User {self.user_id} rated {self.course.title} {self.rating} stars (Tenant: {self.tenant_id})"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        ActivityLog.objects.create(
            tenant_id=self.tenant_id,
            tenant_name=self.tenant_name,
            user_id=self.user_id,
            activity_type='courserating_created' if is_new else 'courserating_updated',
            details=f"CourseRating for course {self.course.title} {'created' if is_new else 'updated'}",
            status='success'
        )
        logger.info(f"[Tenant {self.tenant_id}] CourseRating {self.id} {'created' if is_new else 'updated'}: {self.course.title}")

    def delete(self, *args, **kwargs):
        ActivityLog.objects.create(
            tenant_id=self.tenant_id,
            tenant_name=self.tenant_name,
            user_id=self.user_id,
            activity_type='courserating_deleted',
            details=f"CourseRating for course {self.course.title} deleted",
            status='success'
        )
        logger.info(f"[Tenant {self.tenant_id}] CourseRating {self.id} deleted: {self.course.title}")
        super().delete(*args, **kwargs)

class Badge(models.Model):
    id = models.AutoField(primary_key=True)
    tenant_id = models.CharField(max_length=36, blank=False, null=False)
    tenant_name = models.CharField(max_length=255, blank=True, null=True, help_text="Tenant name for reference")
    title = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    image = models.ImageField(null=True, blank=True, max_length=255)
    image_url = models.CharField(max_length=1024, blank=True, null=True)
    criteria = models.JSONField(default=dict, help_text="Criteria for earning the badge, e.g., {'courses_completed': 5}")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.JSONField(null=True, blank=True)
    last_edited_by = models.JSONField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['tenant_id'], name='idx_badge_tenant'),
        ]

    def __str__(self):
        return f"{self.title} (Tenant: {self.tenant_id})"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        ActivityLog.objects.create(
            tenant_id=self.tenant_id,
            tenant_name=self.tenant_name,
            user_id=None,
            activity_type='badge_created' if is_new else 'badge_updated',
            details=f"Badge {self.title} {'created' if is_new else 'updated'}",
            status='success'
        )
        logger.info(f"[Tenant {self.tenant_id}] Badge {self.id} {'created' if is_new else 'updated'}: {self.title}")

    def delete(self, *args, **kwargs):
        ActivityLog.objects.create(
            tenant_id=self.tenant_id,
            tenant_name=self.tenant_name,
            user_id=None,
            activity_type='badge_deleted',
            details=f"Badge {self.title} deleted",
            status='success'
        )
        logger.info(f"[Tenant {self.tenant_id}] Badge {self.id} deleted: {self.title}")
        super().delete(*args, **kwargs)

class UserPoints(models.Model):
    id = models.AutoField(primary_key=True)
    tenant_id = models.CharField(max_length=36, blank=False, null=False)
    tenant_name = models.CharField(max_length=255, blank=True, null=True, help_text="Tenant name for reference")
    user_id = models.CharField(max_length=36)  # From auth-service
    course = models.ForeignKey(Course, on_delete=models.CASCADE, null=True, blank=True)
    points = models.PositiveIntegerField(default=0)
    activity_type = models.CharField(max_length=50, choices=[
        ('course_completion', 'Course Completion'),
        ('module_completion', 'Module Completion'),
        ('lesson_completion', 'Lesson Completion'),
        ('quiz_score', 'Quiz Score'),
        ('discussion', 'Discussion Participation'),
    ])
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.JSONField(null=True, blank=True)
    last_edited_by = models.JSONField(null=True, blank=True)

    class Meta:
        unique_together = ['tenant_id', 'user_id', 'course', 'activity_type']
        indexes = [
            models.Index(fields=['tenant_id', 'user_id'], name='idx_usr_pts_tnt_usr'),
        ]

    def __str__(self):
        return f"User {self.user_id} - {self.points} points (Tenant: {self.tenant_id})"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        ActivityLog.objects.create(
            tenant_id=self.tenant_id,
            tenant_name=self.tenant_name,
            user_id=self.user_id,
            activity_type='userpoints_created' if is_new else 'userpoints_updated',
            details=f"UserPoints for activity {self.activity_type} {'created' if is_new else 'updated'}",
            status='success'
        )
        logger.info(f"[Tenant {self.tenant_id}] UserPoints {self.id} {'created' if is_new else 'updated'}: {self.activity_type}")

    def delete(self, *args, **kwargs):
        ActivityLog.objects.create(
            tenant_id=self.tenant_id,
            tenant_name=self.tenant_name,
            user_id=self.user_id,
            activity_type='userpoints_deleted',
            details=f"UserPoints for activity {self.activity_type} deleted",
            status='success'
        )
        logger.info(f"[Tenant {self.tenant_id}] UserPoints {self.id} deleted: {self.activity_type}")
        super().delete(*args, **kwargs)

class UserBadge(models.Model):
    id = models.AutoField(primary_key=True)
    tenant_id = models.CharField(max_length=36, blank=False, null=False)
    tenant_name = models.CharField(max_length=255, blank=True, null=True, help_text="Tenant name for reference")
    user_id = models.CharField(max_length=36)  # From auth-service
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE)
    awarded_at = models.DateTimeField(auto_now_add=True)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, null=True, blank=True)
    created_by = models.JSONField(null=True, blank=True)
    last_edited_by = models.JSONField(null=True, blank=True)

    class Meta:
        unique_together = ['tenant_id', 'user_id', 'badge', 'course']
        indexes = [
            models.Index(fields=['tenant_id', 'user_id'], name='idx_usr_bdg_tnt_usr'),
        ]

    def __str__(self):
        return f"User {self.user_id} - {self.badge.title} (Tenant: {self.tenant_id})"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        ActivityLog.objects.create(
            tenant_id=self.tenant_id,
            tenant_name=self.tenant_name,
            user_id=self.user_id,
            activity_type='userbadge_created' if is_new else 'userbadge_updated',
            details=f"UserBadge {self.badge.title} for course {self.course.title if self.course else 'N/A'} {'created' if is_new else 'updated'}",
            status='success'
        )
        logger.info(f"[Tenant {self.tenant_id}] UserBadge {self.id} {'created' if is_new else 'updated'}: {self.badge.title}")

    def delete(self, *args, **kwargs):
        ActivityLog.objects.create(
            tenant_id=self.tenant_id,
            tenant_name=self.tenant_name,
            user_id=self.user_id,
            activity_type='userbadge_deleted',
            details=f"UserBadge {self.badge.title} for course {self.course.title if self.course else 'N/A'} deleted",
            status='success'
        )
        logger.info(f"[Tenant {self.tenant_id}] UserBadge {self.id} deleted: {self.badge.title}")
        super().delete(*args, **kwargs)

class FAQ(models.Model):
    id = models.AutoField(primary_key=True)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='faqs')
    question = models.CharField(max_length=255)
    answer = models.TextField()
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.JSONField(null=True, blank=True)
    last_edited_by = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ['order', 'created_at']
        verbose_name = 'FAQ'
        verbose_name_plural = 'FAQs'
        indexes = [
            models.Index(fields=['course', 'order'], name='idx_faq_crs_order'),
        ]

    def __str__(self):
        return f"{self.course.title} - {self.question[:50]}... (Tenant: {self.course.tenant_id})"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        ActivityLog.objects.create(
            tenant_id=self.course.tenant_id,
            tenant_name=self.course.tenant_name,
            user_id=None,
            activity_type='faq_created' if is_new else 'faq_updated',
            details=f"FAQ for course {self.course.title} {'created' if is_new else 'updated'}",
            status='success'
        )
        logger.info(f"[Tenant {self.course.tenant_id}] FAQ {self.id} {'created' if is_new else 'updated'}: {self.question[:50]}")

    def delete(self, *args, **kwargs):
        ActivityLog.objects.create(
            tenant_id=self.course.tenant_id,
            tenant_name=self.course.tenant_name,
            user_id=None,
            activity_type='faq_deleted',
            details=f"FAQ for course {self.course.title} deleted",
            status='success'
        )
        logger.info(f"[Tenant {self.course.tenant_id}] FAQ {self.id} deleted: {self.question[:50]}")
        super().delete(*args, **kwargs)

class Assignment(models.Model):
    id = models.AutoField(primary_key=True)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    module = models.ForeignKey(Module, on_delete=models.CASCADE, null=True, blank=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    instructions_file = models.FileField(upload_to=assignment_instructions_path, blank=True, null=True)
    instructions_file_url = models.CharField(max_length=1024, blank=True, null=True)
    due_date = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.JSONField(null=True, blank=True)
    last_edited_by = models.JSONField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['course', 'created_at'], name='idx_asgn_crs_crt'),
        ]

    def __str__(self):
        return f"{self.title} ({self.course.title}) (Tenant: {self.course.tenant_id})"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        ActivityLog.objects.create(
            tenant_id=self.course.tenant_id,
            tenant_name=self.course.tenant_name,
            user_id=self.created_by.get('id') if self.created_by else None,
            activity_type='assignment_created' if is_new else 'assignment_updated',
            details=f"Assignment {self.title} for course {self.course.title} {'created' if is_new else 'updated'}",
            status='success'
        )
        logger.info(f"[Tenant {self.course.tenant_id}] Assignment {self.id} {'created' if is_new else 'updated'}: {self.title}")

    def delete(self, *args, **kwargs):
        ActivityLog.objects.create(
            tenant_id=self.course.tenant_id,
            tenant_name=self.course.tenant_name,
            user_id=self.created_by.get('id') if self.created_by else None,
            activity_type='assignment_deleted',
            details=f"Assignment {self.title} for course {self.course.title} deleted",
            status='success'
        )
        logger.info(f"[Tenant {self.course.tenant_id}] Assignment {self.id} deleted: {self.title}")
        super().delete(*args, **kwargs)

class AssignmentSubmission(models.Model):
    id = models.AutoField(primary_key=True)
    tenant_id = models.CharField(max_length=36, blank=False, null=False)
    tenant_name = models.CharField(max_length=255, blank=True, null=True, help_text="Tenant name for reference")
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='submissions')
    student_id = models.CharField(max_length=36)  # From auth-service
    submitted_at = models.DateTimeField(auto_now_add=True)
    submission_file = models.FileField(upload_to=assignment_submission_path, blank=True, null=True)
    submission_file_url = models.CharField(max_length=1024, blank=True, null=True)
    response_text = models.TextField(blank=True)
    grade = models.PositiveIntegerField(null=True, blank=True)
    feedback = models.TextField(blank=True)
    is_graded = models.BooleanField(default=False)
    created_by = models.JSONField(null=True, blank=True)
    last_edited_by = models.JSONField(null=True, blank=True)

    class Meta:
        unique_together = ['tenant_id', 'student_id', 'assignment']
        indexes = [
            models.Index(fields=['tenant_id', 'student_id'], name='idx_asgn_sub_tnt_stu'),
        ]

    def __str__(self):
        return f"User {self.student_id} - {self.assignment.title} (Tenant: {self.tenant_id})"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        ActivityLog.objects.create(
            tenant_id=self.tenant_id,
            tenant_name=self.tenant_name,
            user_id=self.student_id,
            activity_type='assignmentsubmission_created' if is_new else 'assignmentsubmission_updated',
            details=f"AssignmentSubmission for assignment {self.assignment.title} {'created' if is_new else 'updated'}",
            status='success'
        )
        logger.info(f"[Tenant {self.tenant_id}] AssignmentSubmission {self.id} {'created' if is_new else 'updated'}: {self.assignment.title}")

    def delete(self, *args, **kwargs):
        ActivityLog.objects.create(
            tenant_id=self.tenant_id,
            tenant_name=self.tenant_name,
            user_id=self.student_id,
            activity_type='assignmentsubmission_deleted',
            details=f"AssignmentSubmission for assignment {self.assignment.title} deleted",
            status='success'
        )
        logger.info(f"[Tenant {self.tenant_id}] AssignmentSubmission {self.id} deleted: {self.assignment.title}")
        super().delete(*args, **kwargs)