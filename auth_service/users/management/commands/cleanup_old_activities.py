from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from users.models import UserActivity
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Clean up old user activities based on retention policy'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=365,
            help='Delete activities older than this many days (default: 365)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        activities_to_delete = UserActivity.objects.filter(timestamp__lt=cutoff_date)
        count = activities_to_delete.count()
        
        self.stdout.write(
            self.style.WARNING(
                f"Found {count} activities older than {days} days (before {cutoff_date})"
            )
        )
        
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS("Dry run completed - no activities were deleted")
            )
            return
        
        # Actually delete the activities
        deleted_count, _ = activities_to_delete.delete()
        
        self.stdout.write(
            self.style.SUCCESS(f"Successfully deleted {deleted_count} old activities")
        )
        
        logger.info(f"Cleaned up {deleted_count} user activities older than {days} days")