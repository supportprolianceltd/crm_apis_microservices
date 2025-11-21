import uuid
from django.db import models, connection
from django.core.exceptions import ValidationError

def gen_id():
    return uuid.uuid4().hex

def generate_task_id(tenant_schema):
    """Generate task ID in format: {TENANT_PREFIX}-TASK-{SEQUENTIAL_NUMBER}"""
    # Get tenant prefix (first 3 letters, uppercase)
    tenant_prefix = tenant_schema[:3].upper()

    # Get the next sequential number for this tenant
    with connection.cursor() as cursor:
        try:
            # Create sequence table if it doesn't exist (works in PostgreSQL)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS task_sequences (
                    tenant_schema VARCHAR(100) PRIMARY KEY,
                    last_number INTEGER DEFAULT 0
                )
            """)

            # Get or create sequence for this tenant
            cursor.execute("""
                INSERT INTO task_sequences (tenant_schema, last_number)
                VALUES (%s, 0)
                ON CONFLICT (tenant_schema) DO NOTHING
            """, [tenant_schema])

            # Increment and get the next number
            cursor.execute("""
                UPDATE task_sequences
                SET last_number = last_number + 1
                WHERE tenant_schema = %s
                RETURNING last_number
            """, [tenant_schema])

            result = cursor.fetchone()
            if result:
                next_number = result[0]
            else:
                # Fallback if RETURNING doesn't work
                cursor.execute("SELECT last_number FROM task_sequences WHERE tenant_schema = %s", [tenant_schema])
                result = cursor.fetchone()
                next_number = (result[0] + 1) if result else 1
                cursor.execute("UPDATE task_sequences SET last_number = %s WHERE tenant_schema = %s", [next_number, tenant_schema])

        except Exception as e:
            # Fallback to a simple counter if table operations fail
            import time
            next_number = int(time.time() * 1000000) % 1000000  # Simple fallback

    # Format as 6-digit number with leading zeros
    sequential_number = f"{next_number:06d}"

    return f"{tenant_prefix}-TASK-{sequential_number}"

class Task(models.Model):
    STATUS_CHOICES = [
        ('not_started', 'Not Started'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('blocked', 'Blocked'),
    ]
    PRIORITY_CHOICES = [('low','Low'),('medium','Medium'),('high','High')]

    id = models.CharField(primary_key=True, max_length=32, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    assigned_to_id = models.CharField(max_length=128, null=True, blank=True)
    assigned_to_first_name = models.CharField(max_length=150, blank=True)
    assigned_to_last_name = models.CharField(max_length=150, blank=True)
    assigned_to_email = models.EmailField(blank=True)
    assigned_by_id = models.CharField(max_length=128)
    assigned_by_first_name = models.CharField(max_length=150, blank=True)
    assigned_by_last_name = models.CharField(max_length=150, blank=True)
    assigned_by_email = models.EmailField(blank=True)

    start_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='not_started')
    progress_percentage = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.id:
            # Generate custom ID on first save
            tenant_schema = connection.get_schema() or 'public'
            self.id = generate_task_id(tenant_schema)
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.id}: {self.title}"

class DailyReport(models.Model):
    id = models.CharField(primary_key=True, max_length=32, default=gen_id, editable=False)
    # Keep UUID for reports since they don't need custom IDs
    task = models.ForeignKey(Task, related_name='daily_reports', on_delete=models.CASCADE)
    date = models.DateField(auto_now_add=True)
    updated_by_id = models.CharField(max_length=128)
    updated_by_first_name = models.CharField(max_length=150)
    updated_by_last_name = models.CharField(max_length=150)
    updated_by_email = models.EmailField()

    completed_description = models.TextField(blank=True)
    remaining_description = models.TextField(blank=True)
    reason_for_incompletion = models.TextField(blank=True)
    next_action_plan = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Task.STATUS_CHOICES, default='in_progress')
    attachments = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']

class Comment(models.Model):
    id = models.CharField(primary_key=True, max_length=32, default=gen_id, editable=False)
    task = models.ForeignKey(Task, related_name='comments', on_delete=models.CASCADE)
    user_id = models.CharField(max_length=128)
    user_first_name = models.CharField(max_length=150)
    user_last_name = models.CharField(max_length=150)
    user_email = models.EmailField()
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']