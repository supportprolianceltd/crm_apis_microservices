# job_application/migrations/0004_alter_jobapplication_screening_status.py

from django.db import migrations, models
import json
from django.utils import timezone


def transform_to_json_string(apps, schema_editor):
    """
    Transform existing screening_status strings to JSON string format in TextField.
    e.g., "processed" -> '[{"status": "processed", "updated_at": "timestamp"}]'
    """
    JobApplication = apps.get_model('job_application', 'JobApplication')
    now = timezone.now().isoformat()
    
    for application in JobApplication.objects.all():
        data = application.screening_status
        if data:  # Assuming it's a string
            status = data
            json_str = json.dumps([{'status': status, 'updated_at': now}])
            application.screening_status = json_str
        else:
            json_str = json.dumps([{'status': 'pending', 'updated_at': now}])
            application.screening_status = json_str
        application.save(update_fields=['screening_status'])


def reverse_transform_from_json_string(apps, schema_editor):
    """
    Reverse: extract status from JSON string back to plain string.
    """
    JobApplication = apps.get_model('job_application', 'JobApplication')
    
    for application in JobApplication.objects.all():
        try:
            json_str = application.screening_status
            if isinstance(json_str, str):
                data = json.loads(json_str)
                if isinstance(data, list) and len(data) > 0:
                    status = data[0].get('status', 'pending')
                    application.screening_status = status
                else:
                    application.screening_status = 'pending'
            else:
                application.screening_status = 'pending'
        except (json.JSONDecodeError, KeyError, TypeError):
            application.screening_status = 'pending'
        application.save(update_fields=['screening_status'])


class Migration(migrations.Migration):

    dependencies = [
        ('job_application', '0003_jobapplication_status_history'),
    ]

    operations = [
        # First, change to TextField to allow longer JSON strings
        migrations.AlterField(
            model_name='jobapplication',
            name='screening_status',
            field=models.TextField(
                default='[]',
                blank=True,
                help_text="Temporary TextField for JSON data"
            ),
        ),
        # Then, transform data to JSON strings
        migrations.RunPython(
            transform_to_json_string,
            reverse_transform_from_json_string,
        ),
        # Finally, change to JSONField
        migrations.AlterField(
            model_name='jobapplication',
            name='screening_status',
            field=models.JSONField(
                default=list,
                blank=True,
                help_text="Single array containing the latest screening status dictionary. Updates override previous entries."
            ),
        ),
    ]