from django.core.management.base import BaseCommand
from tasks.models import Task, DailyReport, Comment
from django.utils import timezone
from datetime import timedelta

class Command(BaseCommand):
    help = 'Seed the database with sample data'

    def handle(self, *args, **options):
        self.stdout.write('Seeding database...')

        # Clear existing data
        Task.objects.all().delete()
        DailyReport.objects.all().delete()
        Comment.objects.all().delete()

        # Create sample tasks
        tasks = [
            Task(
                title='Develop user authentication',
                description='Implement JWT-based authentication system with refresh tokens',
                assigned_to_id='user-1',
                assigned_to_first_name='John',
                assigned_to_last_name='Developer',
                assigned_to_email='john@company.com',
                assigned_by_id='manager-1',
                assigned_by_first_name='Sarah',
                assigned_by_last_name='Manager',
                assigned_by_email='sarah@company.com',
                start_date=timezone.now().date(),
                due_date=timezone.now().date() + timedelta(days=7),
                priority='high',
                status='in_progress',
                progress_percentage=75
            ),
            Task(
                title='Design dashboard UI',
                description='Create responsive dashboard with task management components',
                assigned_to_id='user-2',
                assigned_to_first_name='Alice',
                assigned_to_last_name='Designer',
                assigned_to_email='alice@company.com',
                assigned_by_id='manager-1',
                assigned_by_first_name='Sarah',
                assigned_by_last_name='Manager',
                assigned_by_email='sarah@company.com',
                start_date=timezone.now().date() - timedelta(days=2),
                due_date=timezone.now().date() + timedelta(days=5),
                priority='medium',
                status='in_progress',
                progress_percentage=50
            ),
            Task(
                title='Setup database schema',
                description='Design and implement PostgreSQL database schema',
                assigned_to_id='user-1',
                assigned_to_first_name='John',
                assigned_to_last_name='Developer',
                assigned_to_email='john@company.com',
                assigned_by_id='manager-1',
                assigned_by_first_name='Sarah',
                assigned_by_last_name='Manager',
                assigned_by_email='sarah@company.com',
                start_date=timezone.now().date() - timedelta(days=5),
                due_date=timezone.now().date() - timedelta(days=1),
                priority='high',
                status='completed',
                progress_percentage=100
            ),
        ]

        for task in tasks:
            task.save()

        # Create sample daily reports
        report1 = DailyReport.objects.create(
            task=tasks[0],
            updated_by_id='user-1',
            updated_by_first_name='John',
            updated_by_last_name='Developer',
            updated_by_email='john@company.com',
            completed_description='Implemented JWT token generation and validation',
            remaining_description='Need to add refresh token functionality',
            reason_for_incompletion='Had to fix critical bugs in authentication flow',
            next_action_plan='Complete refresh token implementation and write tests',
            status='in_progress'
        )

        # Create sample comments
        Comment.objects.create(
            task=tasks[0],
            user_id='manager-1',
            user_first_name='Sarah',
            user_last_name='Manager',
            user_email='sarah@company.com',
            text='Great progress! Please make sure to include proper error handling for token expiration.'
        )

        Comment.objects.create(
            task=tasks[0],
            user_id='user-1',
            user_first_name='John',
            user_last_name='Developer',
            user_email='john@company.com',
            text='Will do. I\'ve added basic error handling, will enhance it further.'
        )

        self.stdout.write(
            self.style.SUCCESS('Successfully seeded database with sample data')
        )