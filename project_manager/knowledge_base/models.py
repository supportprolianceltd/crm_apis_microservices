import uuid
from django.db import models
from django.core.exceptions import ValidationError

def gen_id():
    return uuid.uuid4().hex

class Category(models.Model):
    id = models.CharField(primary_key=True, max_length=32, default=gen_id, editable=False)
    tenant_id = models.CharField(max_length=255, blank=False, null=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.tenant_id})"

class Tag(models.Model):
    id = models.CharField(primary_key=True, max_length=32, default=gen_id, editable=False)
    tenant_id = models.CharField(max_length=255, blank=False, null=False, default='default-tenant')
    name = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.tenant_id})"

class Article(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    ]

    id = models.CharField(primary_key=True, max_length=32, default=gen_id, editable=False)
    tenant_id = models.CharField(max_length=255, blank=False, null=False, default='default-tenant')
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True)
    content = models.TextField()
    excerpt = models.TextField(blank=True, help_text="Short summary of the article")
    author_id = models.CharField(max_length=128)
    author_first_name = models.CharField(max_length=150)
    author_last_name = models.CharField(max_length=150)
    author_email = models.EmailField()
    category = models.ForeignKey(Category, related_name='articles', on_delete=models.SET_NULL, null=True, blank=True)
    tags = models.ManyToManyField(Tag, related_name='articles', blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    featured_image = models.URLField(blank=True, help_text="URL to featured image")
    reading_time = models.PositiveIntegerField(default=0, help_text="Estimated reading time in minutes")
    view_count = models.PositiveIntegerField(default=0)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-published_at', '-created_at']

    def __str__(self):
        return f"{self.title} ({self.tenant_id})"

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.title)
            # Ensure uniqueness
            original_slug = self.slug
            counter = 1
            while Article.objects.filter(slug=self.slug).exclude(id=self.id).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)