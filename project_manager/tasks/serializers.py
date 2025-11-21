from rest_framework import serializers
from .models import Task, DailyReport, Comment

class CommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = '__all__'
        read_only_fields = ('created_at',)

class DailyReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyReport
        fields = '__all__'
        read_only_fields = ('created_at', 'date')

class TaskSerializer(serializers.ModelSerializer):
    comments = CommentSerializer(many=True, read_only=True)
    daily_reports = DailyReportSerializer(many=True, read_only=True)
    
    class Meta:
        model = Task
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')

class TaskCreateSerializer(serializers.ModelSerializer):
    assigned_to_id = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Task
        fields = ('title', 'description', 'assigned_to_id', 'start_date',
                 'due_date', 'priority', 'status')

class BulkTaskCreateSerializer(serializers.Serializer):
    tasks = TaskCreateSerializer(many=True)

    def create(self, validated_data, current_user):
        """Create multiple tasks with proper validation and user assignment"""
        tasks_data = validated_data['tasks']
        created_tasks = []

        for task_data in tasks_data:
            # Handle task assignment
            assigned_to_id = task_data.get('assigned_to_id')

            if not assigned_to_id or assigned_to_id.strip() == '':
                # Task is unassigned
                assigned_user = {
                    'first_name': '',
                    'last_name': '',
                    'email': '',
                }
                task_data['assigned_to_id'] = None
            else:
                # Try to get assigned user details from auth service
                from .auth_utils import get_user_details
                from django.conf import settings
                import requests

                try:
                    assigned_user = get_user_details(assigned_to_id, self.context.get('request').headers.get('Authorization'))
                    if not assigned_user:
                        # Leave task unassigned if user not found
                        assigned_user = {
                            'first_name': '',
                            'last_name': '',
                            'email': '',
                        }
                        task_data['assigned_to_id'] = None
                except:
                    # Leave task unassigned on error
                    assigned_user = {
                        'first_name': '',
                        'last_name': '',
                        'email': '',
                    }
                    task_data['assigned_to_id'] = None

            # Create task data with assignor details
            full_task_data = {
                **task_data,
                'assigned_by_id': current_user['id'],
                'assigned_by_first_name': current_user['first_name'],
                'assigned_by_last_name': current_user['last_name'],
                'assigned_by_email': current_user['email'],
                'assigned_to_first_name': assigned_user['first_name'],
                'assigned_to_last_name': assigned_user['last_name'],
                'assigned_to_email': assigned_user['email'],
            }

            task = Task.objects.create(**full_task_data)
            created_tasks.append(task)

        return created_tasks

class TaskStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ('status', 'progress_percentage')

class CommentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = ('text',)

class DailyReportCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyReport
        fields = ('completed_description', 'remaining_description', 
                 'reason_for_incompletion', 'next_action_plan', 'status')