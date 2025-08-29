from django.core.management.base import BaseCommand
from users.models import UserProfile
from core.models import Tenant
from django.db.models import Max
from django.db import transaction


class Command(BaseCommand):
    help = 'Regenerates missing employee IDs for all tenants'

    def handle(self, *args, **kwargs):
        tenants = Tenant.objects.all()
        updated_count = 0

        for tenant in tenants:
            tenant_code = tenant.name.strip().upper()[:3]

            existing_ids = (
                UserProfile.objects.filter(user__tenant=tenant, employee_id__startswith=tenant_code)
                .values_list('employee_id', flat=True)
            )

            # Get the next number to start from
            if existing_ids:
                numbers = []
                for eid in existing_ids:
                    try:
                        numbers.append(int(eid.split('-')[1]))
                    except:
                        continue
                next_number = max(numbers) + 1 if numbers else 1
            else:
                next_number = 1

            # Get all profiles without an employee_id for this tenant
            profiles = UserProfile.objects.filter(user__tenant=tenant, employee_id__isnull=True)

            for profile in profiles:
                # Generate new ID
                new_id = f"{tenant_code}-{next_number:04d}"

                # Assign and save
                profile.employee_id = new_id
                profile.save()

                self.stdout.write(self.style.SUCCESS(
                    f"Assigned ID {new_id} to {profile.user.get_full_name()} ({profile.user.email})"
                ))
                updated_count += 1
                next_number += 1

        self.stdout.write(self.style.SUCCESS(
            f"\nSuccessfully updated {updated_count} user profiles with employee IDs."
        ))
