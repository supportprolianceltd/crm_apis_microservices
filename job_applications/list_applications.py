import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "job_applications.settings")
django.setup()

from job_application.models import JobApplication

requisition_id = "PRO-0002"
applications = JobApplication.active_objects.filter(job_requisition_id=requisition_id)

print("Found", applications.count(), "applications for requisition", requisition_id)
for app in applications:
    print(app.id, app.email, app.tenant_id, app.resume_status)