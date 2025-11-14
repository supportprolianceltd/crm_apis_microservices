# Generated manually to fix the max_length issue

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0002_alter_task_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='task',
            name='id',
            field=models.CharField(editable=False, max_length=32, primary_key=True, serialize=False),
        ),
    ]