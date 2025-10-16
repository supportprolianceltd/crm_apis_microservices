# hr/rewards_penalties/tests_integration.py
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.urls import reverse
from django.utils import timezone
from unittest.mock import patch, MagicMock
import uuid
import json
from datetime import timedelta, date

from .models import Reward, Penalty, RewardType, PenaltyType, Status
from .serializers import get_user_data_from_jwt

class RewardsPenaltiesIntegrationTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant_id = uuid.uuid4()
        self.employee_id = uuid.uuid4()
        self.user_id = uuid.uuid4()
        self.base_url = reverse('rewards_penalties:reward-list-create')
        self.penalty_url = reverse('rewards_penalties:penalty-list-create')
        
        # Mock JWT payload
        self.jwt_payload = {
            'tenant_unique_id': self.tenant_id,
            'tenant_schema': 'HR',
            'tenant_domain': 'test.com'
        }
        self.user_data = {
            'id': str(self.user_id),
            'email': 'hr@example.com',
            'first_name': 'HR',
            'last_name': 'Admin',
            'job_role': 'HR Manager',
            'department': 'HR'
        }
        
        # Create initial data
        self.reward_data = {
            'employee_id': str(self.employee_id),
            'employee_details': {
                'id': str(self.employee_id),
                'email': 'employee@example.com',
                'first_name': 'John',
                'last_name': 'Doe',
                'job_role': 'Developer',
                'department': 'Engineering'
            },
            'date_issued': '2025-10-10',
            'effective_date': '2025-10-15',
            'reason': 'Outstanding performance',
            'description': 'Completed project ahead of schedule',
            'status': Status.PENDING.value,
            'type': RewardType.BONUS.value,
            'value': '1500.00',
            'value_type': 'monetary',
            'compliance_checklist': [
                {'name': 'Policy compliance', 'completed': True},
                {'name': 'Budget approval', 'completed': False}
            ],
            'approval_workflow': {
                'stages': [
                    {'role': 'manager', 'approved': False},
                    {'role': 'hr', 'approved': False}
                ]
            },
            'notes': 'Discuss with team lead',
            'is_public': True,
            'impact_assessment': {'morale': 'positive', 'productivity': 'increased'}
        }
        
        self.penalty_data = {
            'employee_id': str(self.employee_id),
            'employee_details': {
                'id': str(self.employee_id),
                'email': 'employee@example.com',
                'first_name': 'John',
                'last_name': 'Doe',
                'job_role': 'Developer',
                'department': 'Engineering'
            },
            'date_issued': '2025-10-10',
            'effective_date': '2025-10-15',
            'reason': 'Policy violation',
            'description': 'Missed deadline without notice',
            'status': Status.PENDING.value,
            'type': PenaltyType.WRITTEN_WARNING.value,
            'severity_level': 2,
            'duration_days': 30,
            'probation_period_months': 3,
            'compliance_checklist': [
                {'name': 'Legal review', 'completed': True},
                {'name': 'Union notification', 'completed': False}
            ],
            'approval_workflow': {
                'stages': [
                    {'role': 'manager', 'approved': False},
                    {'role': 'hr', 'approved': False}
                ]
            },
            'corrective_action_plan': {
                'steps': ['Attend training', 'Submit weekly reports'],
                'timeline': 'Next 30 days'
            },
            'legal_compliance_notes': 'In line with company policy section 4.2',
            'notes': 'First offense, offer support'
        }
        self.reward_data['created_by_id'] = str(self.created_by_details['id'])
        self.reward_data['created_by_details'] = self.created_by_details
        self.penalty_data['created_by_id'] = str(self.created_by_details['id'])
        self.penalty_data['created_by_details'] = self.created_by_details

    @patch('rewards_penalties.serializers.jwt.decode')
    def test_create_reward_integration(self, mock_decode):
        """Test full integration for creating a reward: POST request, serialization, model save, code generation."""
        mock_decode.return_value = self.jwt_payload
        
        # Mock user data for created_by
        with patch('rewards_penalties.serializers.get_user_data_from_jwt') as mock_user:
            mock_user.return_value = self.user_data
            response = self.client.post(self.base_url, self.reward_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['tenant_id'], str(self.tenant_id))
        self.assertEqual(response.data['type'], RewardType.BONUS.value)
        self.assertEqual(response.data['value'], '1500.00')
        self.assertIn('HR-R-', response.data['id'])
        self.assertIn('HR-REW-', response.data['code'])
        self.assertEqual(response.data['created_by_details'], self.user_data)
        self.assertEqual(response.data['status'], Status.PENDING.value)
        
        # Verify model instance
        reward = Reward.objects.get(id=response.data['id'])
        self.assertEqual(reward.reason, 'Outstanding performance')
        self.assertEqual(reward.is_public, True)

    @patch('rewards_penalties.serializers.jwt.decode')
    def test_create_penalty_integration(self, mock_decode):
        """Test full integration for creating a penalty: POST request, validation, model save, end_date calculation."""
        mock_decode.return_value = self.jwt_payload
        
        # Mock user data for created_by
        with patch('rewards_penalties.serializers.get_user_data_from_jwt') as mock_user:
            mock_user.return_value = self.user_data
            response = self.client.post(self.penalty_url, self.penalty_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['tenant_id'], str(self.tenant_id))
        self.assertEqual(response.data['type'], PenaltyType.WRITTEN_WARNING.value)
        self.assertEqual(response.data['severity_level'], 2)
        self.assertEqual(response.data['duration_days'], 30)
        self.assertIn('HR-P-', response.data['id'])
        self.assertIn('HR-PEN-', response.data['code'])
        
        # Verify end_date calculation
        effective_date = timezone.datetime(2025, 10, 15).date()
        expected_end_date = effective_date + timedelta(days=30)
        self.assertEqual(response.data['end_date'], expected_end_date.strftime('%Y-%m-%d'))
        
        # Verify model instance
        penalty = Penalty.objects.get(id=response.data['id'])
        self.assertEqual(penalty.severity_level, 2)
        self.assertEqual(penalty.legal_compliance_notes, 'In line with company policy section 4.2')
        
        # Verify end_date directly
        expected_end = date(2025, 10, 15)
        self.assertEqual(penalty.end_date, expected_end)

    def test_list_rewards_integration(self):
        """Test listing rewards: Create multiple, GET list, filter by status and type."""
        
        # Create two rewards
        with patch('rewards_penalties.serializers.get_user_data_from_jwt') as mock_user:
            mock_user.return_value = self.user_data
            self.client.post(self.base_url, self.reward_data, format='json')
            updated_data = self.reward_data.copy()
            updated_data['type'] = RewardType.PROMOTION.value
            self.client.post(self.base_url, updated_data, format='json')
        
        # GET list
        response = self.client.get(self.base_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        
        # Filter by status
        response = self.client.get(f"{self.base_url}?status=pending")
        self.assertEqual(len(response.data), 2)
        
        # Filter by type
        response = self.client.get(f"{self.base_url}?type=promotion")
        self.assertEqual(len(response.data), 1)

    def test_list_penalties_integration(self):
        """Test listing penalties: Create multiple, GET list, filter by severity."""
        
        # Create two penalties
        with patch('rewards_penalties.serializers.get_user_data_from_jwt') as mock_user:
            mock_user.return_value = self.user_data
            self.client.post(self.penalty_url, self.penalty_data, format='json')
            updated_data = self.penalty_data.copy()
            updated_data['severity_level'] = 3
            self.client.post(self.penalty_url, updated_data, format='json')
        
        # GET list
        response = self.client.get(self.penalty_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        
        # Filter by severity_level
        response = self.client.get(f"{self.penalty_url}?severity_level=3")
        self.assertEqual(len(response.data), 1)

    @patch('rewards_penalties.serializers.jwt.decode')
    def test_update_reward_approval_integration(self, mock_decode):
        """Test updating reward status to approved: Sets approver, approval_date."""
        mock_decode.return_value = self.jwt_payload
        
        # Create reward
        with patch('rewards_penalties.serializers.get_user_data_from_jwt') as mock_user_create:
            mock_user_create.return_value = self.user_data
            create_response = self.client.post(self.base_url, self.reward_data, format='json')
            reward_id = create_response.data['id']
        
        # Update to approved
        update_data = {'status': Status.APPROVED.value}
        with patch('rewards_penalties.serializers.get_user_data_from_jwt') as mock_user_update:
            mock_user_update.return_value = self.user_data
            response = self.client.patch(f"{self.base_url}{reward_id}/", update_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], Status.APPROVED.value)
        self.assertEqual(response.data['approver_details'], self.user_data)
        self.assertIsNotNone(response.data['approval_date'])
        
        # Verify model
        reward = Reward.objects.get(id=reward_id)
        self.assertEqual(reward.status, Status.APPROVED.value)
        self.assertEqual(reward.approver_id, self.user_id)
        self.assertIsNotNone(reward.approval_date)

    @patch('rewards_penalties.serializers.jwt.decode')
    def test_update_penalty_issued_integration(self, mock_decode):
        """Test updating penalty status to issued: Sets approver, approval_date."""
        mock_decode.return_value = self.jwt_payload
        
        # Create penalty
        with patch('rewards_penalties.serializers.get_user_data_from_jwt') as mock_user_create:
            mock_user_create.return_value = self.user_data
            create_response = self.client.post(self.penalty_url, self.penalty_data, format='json')
            penalty_id = create_response.data['id']
        
        # Update to issued
        update_data = {'status': Status.ISSUED.value}
        with patch('rewards_penalties.serializers.get_user_data_from_jwt') as mock_user_update:
            mock_user_update.return_value = self.user_data
            response = self.client.patch(f"{self.penalty_url}{penalty_id}/", update_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], Status.ISSUED.value)
        self.assertEqual(response.data['approver_details'], self.user_data)
        self.assertIsNotNone(response.data['approval_date'])
        
        # Verify model
        penalty = Penalty.objects.get(id=penalty_id)
        self.assertEqual(penalty.status, Status.ISSUED.value)
        self.assertEqual(penalty.approver_id, self.user_id)

    @patch('rewards_penalties.serializers.jwt.decode')
    def test_search_and_filter_integration(self, mock_decode):
        """Test search and filter on list views."""
        mock_decode.return_value = self.jwt_payload
        
        # Create rewards with searchable content
        reward1_data = self.reward_data.copy()
        reward1_data['reason'] = 'Outstanding performance in Q3'
        reward2_data = self.reward_data.copy()
        reward2_data['employee_details']['first_name'] = 'Jane'
        reward2_data['reason'] = 'Team collaboration award'
        
        with patch('rewards_penalties.serializers.get_user_data_from_jwt'):
            self.client.post(self.base_url, reward1_data, format='json')
            self.client.post(self.base_url, reward2_data, format='json')
        
        # Search by reason
        response = self.client.get(f"{self.base_url}?search=performance")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertIn('Q3', response.data[0]['reason'])
        
        # Search by name
        response = self.client.get(f"{self.base_url}?search=Jane")
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['employee_details']['first_name'], 'Jane')
        
        # Filter by is_public
        response = self.client.get(f"{self.base_url}?is_public=true")
        self.assertEqual(len(response.data), 2)  # Both are public in data

    def test_unauthorized_tenant_access(self):
        """Test tenant isolation: Wrong tenant_id should return empty list."""
        # Mock payload with different tenant
        wrong_payload = {'tenant_unique_id': uuid.uuid4()}
        with patch('rewards_penalties.views.jwt_payload', return_value=wrong_payload):
            # Create data with original tenant
            with patch('rewards_penalties.serializers.get_user_data_from_jwt'):
                self.client.post(self.base_url, self.reward_data, format='json')
            
            # List with wrong tenant
            response = self.client.get(self.base_url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(len(response.data), 0)

    @patch('rewards_penalties.serializers.get_tenant_id_from_jwt')
    def test_tenant_mismatch_validation(self, mock_tenant):
        """Test validation error on tenant mismatch in serializer."""
        mock_tenant.return_value = uuid.uuid4()  # Different from data
        response = self.client.post(self.base_url, {**self.reward_data, 'tenant_id': str(self.tenant_id)}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('tenant_id', response.data['non_field_errors'][0])

    def test_penalty_clean_auto_end_date(self):
        effective_date_str = '2025-10-10'
        duration_days = 5
        penalty = Penalty(
            tenant_id=self.tenant_id,
            employee_id=self.employee_id,
            employee_details=self.employee_details,
            created_by_id=self.created_by_details['id'],
            created_by_details=self.created_by_details,
            reason='Test',
            type=PenaltyType.SUSPENSION.value,
            effective_date=effective_date_str,
            duration_days=duration_days,
            tenant_domain='test.com'
        )
        penalty.full_clean()
        from datetime import date
        expected_end = date(2025, 10, 15)  # 10 + 5 days
        self.assertEqual(penalty.end_date, expected_end)