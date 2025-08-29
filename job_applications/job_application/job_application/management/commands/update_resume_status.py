from django.core.management.base import BaseCommand
from django_tenants.utils import tenant_context
from job_application.models import JobApplication
from core.models import Tenant
import logging

logger = logging.getLogger('job_applications')

class Command(BaseCommand):
    help = 'Updates resume_status for applications with resume documents'

    def handle(self, *args, **options):
        try:
            tenant = Tenant.objects.get(schema_name="proliance")
        except Tenant.DoesNotExist:
            logger.error("Tenant 'proliance' not found")
            self.stdout.write(self.style.ERROR("Tenant 'proliance' not found"))
            return

        with tenant_context(tenant):
            try:
                applications = JobApplication.active_objects.filter(
                    tenant=tenant,
                    resume_status=False
                )
                if not applications.exists():
                    logger.info("No applications with resume_status=False found")
                    self.stdout.write(self.style.SUCCESS("No applications with resume_status=False found"))
                    return

                for app in applications:
                    try:
                        # Check if documents is a list and iterate directly
                        documents = app.documents if app.documents else []
                        if not isinstance(documents, list):
                            logger.error(f"Documents field for application {app.id} is not a list: {type(documents)}")
                            self.stdout.write(self.style.ERROR(f"Documents field for application {app.id} is not a list"))
                            continue

                        has_resume = any(
                            doc.get('document_type', '').lower() in ["resume", "curriculum vitae (cv)", "cv"]
                            for doc in documents
                        )
                        if has_resume:
                            app.resume_status = True
                            app.save()
                            logger.info(f"Updated resume_status for application {app.id}")
                            self.stdout.write(self.style.SUCCESS(f"Updated resume_status for application {app.id}"))
                        else:
                            logger.info(f"No resume found for application {app.id}")
                            self.stdout.write(self.style.WARNING(f"No resume found for application {app.id}"))
                    except Exception as e:
                        logger.error(f"Error processing application {app.id}: {str(e)}")
                        self.stdout.write(self.style.ERROR(f"Error processing application {app.id}: {str(e)}"))
            except Exception as e:
                logger.error(f"Error querying applications: {str(e)}")
                self.stdout.write(self.style.ERROR(f"Error querying applications: {str(e)}"))