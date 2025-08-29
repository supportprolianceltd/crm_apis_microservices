#RUN THIS COMMAND WITH python manage.py update_email_templates

from django.core.management.base import BaseCommand
from core.models import TenantConfig

SHORTLISTED_TEMPLATE = {
    'content': (
        'Hello [Candidate Name],\n\n'
        'Congratulations! You have been shortlisted for the [Position] role at [Company]. '
        'We will contact you soon with further details.\n\n'
        'Best regards,\n[Your Name]'
    ),
    'is_auto_sent': True
}

class Command(BaseCommand):
    help = 'Add shortlistedNotification template to all TenantConfig email_templates if missing.'

    def handle(self, *args, **options):
        updated = 0
        for config in TenantConfig.objects.all():
            templates = config.email_templates or {}
            if 'shortlistedNotification' not in templates:
                templates['shortlistedNotification'] = SHORTLISTED_TEMPLATE
                config.email_templates = templates
                config.save()
                updated += 1
                self.stdout.write(self.style.SUCCESS(
                    f'Updated TenantConfig for tenant {getattr(config.tenant, "schema_name", config.tenant)}'
                ))
        if updated == 0:
            self.stdout.write(self.style.WARNING('No TenantConfig needed updating.'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Updated {updated} TenantConfig(s).'))