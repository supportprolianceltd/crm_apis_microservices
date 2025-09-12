from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.text import slugify
import json
from django.utils import timezone
from django.db import models
import uuid
import os

from users.models import CustomUser

def course_thumbnail_path(instance, filename):
    return f'courses/{instance.slug}/thumbnails/{filename}'

def certificate_logo_path(instance, filename):
    return f'courses/{instance.course.slug}/certificates/logos/{filename}'

def certificate_signature_path(instance, filename):
    return f'courses/{instance.course.slug}/certificates/signatures/{filename}'

# def resource_file_path(instance, filename):
#     return f'courses/{instance.module.course.slug}/resources/{filename}'
def resource_file_path(instance, filename):
    """
    Generate a file path for resource uploads based on the course slug.
    """
    return f'courses/{instance.course.slug}/resources/{filename}'

def scorm_package_path(instance, filename):
    return f'courses/{instance.course.slug}/scorm_packages/{filename}'



class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_categories'
    )

    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


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
    
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField()
    short_description = models.CharField(max_length=300, blank=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='Beginner')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Draft')
    duration = models.CharField(max_length=100, blank=True)
    is_free = models.BooleanField(default=False)  # <-- Add this line
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=None)  # <-- Update
    discount_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=None)  # <-- Update
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='NGN')
    thumbnail = models.ImageField(null=True, blank=True, max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_courses')
    learning_outcomes = models.JSONField(default=list)
    prerequisites = models.JSONField(default=list)
    completion_hours = models.PositiveIntegerField(default=0, help_text="Estimated hours to complete the course")
    COURSE_TYPE_CHOICES = [
        ('manual', 'Manual'),
        ('scorm', 'SCORM'),
    ]
    course_type = models.CharField(max_length=20, choices=COURSE_TYPE_CHOICES, default='manual')
    scorm_launch_path = models.CharField(max_length=255, blank=True, null=True)
    scorm_metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    # def save(self, *args, **kwargs):
    #     if not self.slug:
    #         self.slug = slugify(self.title)
    #     super().save(*args, **kwargs)
    
    def save(self, *args, **kwargs):
        # Ensure learning_outcomes is stored as a flat array
        if isinstance(self.learning_outcomes, list):
            self.learning_outcomes = [str(item) for item in self.learning_outcomes]
        elif isinstance(self.learning_outcomes, str):
            try:
                parsed = json.loads(self.learning_outcomes)
                self.learning_outcomes = [str(item) for item in parsed] if isinstance(parsed, list) else [self.learning_outcomes]
            except json.JSONDecodeError:
                self.learning_outcomes = [self.learning_outcomes]
        
        # Ensure prerequisites is stored as a flat array
        if isinstance(self.prerequisites, list):
            self.prerequisites = [str(item) for item in self.prerequisites]
        elif isinstance(self.prerequisites, str):
            try:
                parsed = json.loads(self.prerequisites)
                self.prerequisites = [str(item) for item in parsed] if isinstance(parsed, list) else [self.prerequisites]
            except json.JSONDecodeError:
                self.prerequisites = [self.prerequisites]
                
        # If course is free, set price and discount_price to None
        if self.is_free:
            self.price = None
            self.discount_price = None

        super().save(*args, **kwargs)
    
    @property
    def current_price(self):
        return self.discount_price if self.discount_price else self.price


class Module(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='modules')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['order']
        unique_together = ['course', 'order']
    
    def __str__(self):
        return f"{self.course.title} - {self.title}"


class Lesson(models.Model):
    LESSON_TYPE_CHOICES = [
        ('video', 'Video'),
        ('quiz', 'Quiz'),
        ('assignment', 'Assignment'),
        ('text', 'Text'),
        ('file', 'File'),
        ('link', 'Link'),  # Add 'link' as a valid choice
    ]
    
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='lessons')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    lesson_type = models.CharField(max_length=20, choices=LESSON_TYPE_CHOICES, default='video')
    duration = models.CharField(max_length=20, help_text="Duration in minutes", default= "1 hour")
    content_url = models.URLField(blank=True)
    content_file = models.FileField(null=True, blank=True, max_length=255)  # Remove upload_to
    content_text = models.TextField(blank=True)  # <-- Add this line
    order = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['order']
        unique_together = ['module', 'order']
    
    def __str__(self):
        return f"{self.module.title} - {self.title}"
    
    @property
    def duration_display(self):
        hours = self.duration // 60
        minutes = self.duration % 60
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"




class Resource(models.Model):
    RESOURCE_TYPE_CHOICES = [
        ('link', 'Web Link'),
        ('pdf', 'PDF Document'),
        ('video', 'Video'),
        ('file', 'File'),
    ]
    
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='resources')
    title = models.CharField(max_length=200)
    resource_type = models.CharField(max_length=20, choices=RESOURCE_TYPE_CHOICES)
    url = models.URLField(blank=True)
    file = models.FileField(upload_to=resource_file_path, blank=True, null=True)
    order = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['order']
    
    def __str__(self):
        return f"{self.course.title} - {self.title}"



class Instructor(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='instructor_profile')
    bio = models.TextField(blank=True)
    expertise = models.ManyToManyField(Category, blank=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.user.get_full_name()

class CourseInstructor(models.Model):
    ASSIGNMENT_CHOICES = [
        ('all', 'Entire Course'),
        ('specific', 'Specific Modules'),
    ]
    
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='course_instructors')
    instructor = models.ForeignKey(Instructor, on_delete=models.CASCADE, related_name='assigned_courses')
    assignment_type = models.CharField(max_length=20, choices=ASSIGNMENT_CHOICES, default='all')
    is_active = models.BooleanField(default=True)
    modules = models.ManyToManyField(Module, blank=True)
    
    class Meta:
        unique_together = ['course', 'instructor']
    
    def __str__(self):
        return f"{self.instructor} - {self.course.title}"




def certificate_logo_path(instance, filename):
    ext = os.path.splitext(filename)[1]
    new_filename = f"{uuid.uuid4().hex}{ext}"
    return os.path.join('courses', str(instance.course.id), 'certificates', 'logos', new_filename)

def certificate_signature_path(instance, filename):
    ext = os.path.splitext(filename)[1]
    new_filename = f"{uuid.uuid4().hex}{ext}"
    return os.path.join('courses', str(instance.course.id), 'certificates', 'signatures', new_filename)

class CertificateTemplate(models.Model):
    id = models.AutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    course = models.ForeignKey('courses.Course', on_delete=models.CASCADE, related_name='certificate_templates')
    is_active = models.BooleanField(default=True)
    template = models.CharField(max_length=50, default='default')
    custom_text = models.TextField(default='Congratulations on completing the course!')
    logo = models.FileField(null=True, blank=True, max_length=255)  # Already updated
    signature = models.FileField(null=True, blank=True, max_length=255)  # Already updated
    signature_name = models.CharField(max_length=100, default='Course Instructor')
    show_date = models.BooleanField(default=True)
    show_course_name = models.BooleanField(default=True)
    show_completion_hours = models.BooleanField(default=True)
    min_score = models.PositiveIntegerField(default=80)
    require_all_modules = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('course',)
        

class SCORMxAPISettings(models.Model):
    STANDARD_CHOICES = [
        ('scorm12', 'SCORM 1.2'),
        ('scorm2004', 'SCORM 2004'),
        ('xapi', 'xAPI (Tin Can)'),
    ]
    
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
    package = models.FileField(null=True, blank=True, max_length=255)  # Remove upload_to
    
    def __str__(self):
        return f"SCORM/xAPI Settings for {self.course.title}"



class SCORMTracking(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    progress = models.PositiveIntegerField(default=0)
    score = models.PositiveIntegerField(default=0)
    completed = models.BooleanField(default=False)
    raw_data = models.JSONField(default=dict, blank=True)
    last_updated = models.DateTimeField(auto_now=True)


class LearningPath(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    courses = models.ManyToManyField(Course, related_name='learning_paths')
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_learning_paths'
    )
    
    class Meta:
        ordering = ['order']
    
    def __str__(self):
        return self.title

class LessonProgress(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='lesson_progress')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='progress')
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['user', 'lesson']

    def __str__(self):
        return f"{self.user} - {self.lesson} - {'Completed' if self.is_completed else 'In Progress'}"
    

class Enrollment(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    enrolled_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ['user', 'course']

    def __str__(self):
        return f"{self.user} - {self.course}"

    def get_progress(self):
        total_lessons = Lesson.objects.filter(module__course=self.course).count()
        completed_lessons = LessonProgress.objects.filter(
            user=self.user, lesson__module__course=self.course, is_completed=True
        ).count()
        if total_lessons == 0:
            return 0
        return int((completed_lessons / total_lessons) * 100)



class Certificate(models.Model):
    enrollment = models.OneToOneField(Enrollment, on_delete=models.CASCADE, related_name='certificate')
    issued_at = models.DateTimeField(auto_now_add=True)
    certificate_id = models.CharField(max_length=50, unique=True)
    pdf_file = models.FileField(null=True, blank=True, max_length=255)  # Remove upload_to
    
    def __str__(self):
        return f"Certificate {self.certificate_id} for {self.enrollment.user}"





class CourseRating(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='course_ratings')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='ratings')
    rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    review = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'course']
    
    def __str__(self):
        return f"{self.user} rated {self.course} {self.rating} stars"

class Badge(models.Model):
    title = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    image = models.ImageField(null=True, blank=True, max_length=255)  # Remove upload_to
    criteria = models.JSONField(default=dict, help_text="Criteria for earning the badge, e.g., {'courses_completed': 5}")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

class UserPoints(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='points')
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

    class Meta:
        unique_together = ['user', 'course', 'activity_type']

    def __str__(self):
        return f"{self.user} - {self.points} points"

class UserBadge(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='badges')
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE)
    awarded_at = models.DateTimeField(auto_now_add=True)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        unique_together = ['user', 'badge', 'course']

    def __str__(self):
        return f"{self.user} - {self.badge.title}"

class FAQ(models.Model):
    course = models.ForeignKey(
        Course, 
        on_delete=models.CASCADE, 
        related_name='faqs'
    )
    question = models.CharField(max_length=255)
    answer = models.TextField()
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'created_at']
        verbose_name = 'FAQ'
        verbose_name_plural = 'FAQs'

    def __str__(self):
        return f"{self.course.title} - {self.question[:50]}..."


class Assignment(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    module = models.ForeignKey(Module, on_delete=models.CASCADE, null=True, blank=True)  # <-- Add this linements')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    instructions_file = models.FileField(upload_to='assignments/instructions/', blank=True, null=True)
    due_date = models.DateTimeField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


    def __str__(self):
        return f"{self.title} ({self.course.title})"

class AssignmentSubmission(models.Model):
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    submitted_at = models.DateTimeField(auto_now_add=True)
    submission_file = models.FileField(upload_to='assignments/submissions/', blank=True, null=True)
    response_text = models.TextField(blank=True)
    grade = models.PositiveIntegerField(null=True, blank=True)
    feedback = models.TextField(blank=True)
    is_graded = models.BooleanField(default=False)

    class Meta:
        unique_together = ['assignment', 'student']

    def __str__(self):
        return f"{self.student} - {self.assignment.title}"

