# hr/rewards_penalties/tests.py
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from unittest.mock import patch, MagicMock
from rest_framework.test import APITestCase, APIClient
from rest_framework.test import APIRequestFactory
from rest_framework import status
from datetime import timedelta, date
import uuid
import json
from unittest.mock import Mock

from .models import Reward, Penalty, RewardType, PenaltyType, Status, validate_details_json, validate_compliance_checklist, validate_approval_workflow
from .serializers import RewardSerializer, PenaltySerializer, get_tenant_id_from_jwt, get_user_data_from_jwt
from .views import RewardListCreateView, PenaltyListCreateView

class ModelsTestCase(TestCase):
    def setUp(self):
        self.tenant_id = uuid.uuid4()
        self.employee_id = uuid.uuid4()
        self.employee_details = {
            'id': str(self.employee_id),
            'email': 'test@example.com',
            'first_name': 'John',
            'last_name': 'Doe',
            'job_role': 'Developer',
            'department': 'IT'
        }
        self.created_by_details = {
            'id': str(uuid.uuid4()),
            'email': 'creator@example.com',
            'first_name': 'Creator',
            'last_name': 'User',
            'job_role': 'HR',
            'department': 'HR'
        }
        self.compliance_checklist = [
            {'name': 'Check policy', 'completed': True},
            {'name': 'Review docs', 'completed': False}
        ]
        self.approval_workflow = {
            'stages': [
                {'role': 'manager'},
                {'role': 'hr'}
            ]
        }

    def test_validate_details_json(self):
        # Valid
        validate_details_json(self.employee_details)
        # Invalid - missing key
        invalid_details = self.employee_details.copy()
        del invalid_details['department']
        with self.assertRaises(ValidationError):
            validate_details_json(invalid_details)
        # Invalid - not dict
        with self.assertRaises(ValidationError):
            validate_details_json("not a dict")

    def test_validate_compliance_checklist(self):
        # Valid
        validate_compliance_checklist(self.compliance_checklist)
        # Invalid - not list
        with self.assertRaises(ValidationError):
            validate_compliance_checklist("not a list")
        # Invalid item
        invalid_list = [{'name': 'item'}]  # missing completed
        with self.assertRaises(ValidationError):
            validate_compliance_checklist(invalid_list)

    def test_validate_approval_workflow(self):
        # Valid
        validate_approval_workflow(self.approval_workflow)
        # Invalid - not dict
        with self.assertRaises(ValidationError):
            validate_approval_workflow("not a dict")
        # Invalid - no stages
        invalid_workflow = {}
        with self.assertRaises(ValidationError):
            validate_approval_workflow(invalid_workflow)
        # Invalid stage
        invalid_stages = [{'no_role': 'item'}]
        invalid = {'stages': invalid_stages}
        with self.assertRaises(ValidationError):
            validate_approval_workflow(invalid)

    def test_reward_generate_code(self):
        tenant_schema = 'HR'
        
        # First reward - save it to the database
        reward = Reward(
            tenant_id=self.tenant_id,
            employee_id=self.employee_id,
            employee_details=self.employee_details,
            created_by_id=self.created_by_details['id'],
            created_by_details=self.created_by_details,
            reason='Test reason',
            tenant_domain='test.com'
        )
        reward.generate_code(tenant_schema)
        reward.save()  # Save the first reward
        
        self.assertEqual(reward.id, 'HR-R-0001')
        self.assertEqual(reward.code, 'HR-REW-0001')

        # Second one - this should now get the next number
        reward2 = Reward(
            tenant_id=self.tenant_id,
            employee_id=self.employee_id,
            employee_details=self.employee_details,
            created_by_id=self.created_by_details['id'],
            created_by_details=self.created_by_details,
            reason='Test reason 2',
            tenant_domain='test.com'
        )
        reward2.generate_code(tenant_schema)
        reward2.save()  # Save the second reward
        self.assertEqual(reward2.id, 'HR-R-0002')
        self.assertEqual(reward2.code, 'HR-REW-0002')

    def test_penalty_generate_code(self):
        tenant_schema = 'HR'
        penalty = Penalty(
            tenant_id=self.tenant_id,
            employee_id=self.employee_id,
            employee_details=self.employee_details,
            created_by_id=self.created_by_details['id'],
            created_by_details=self.created_by_details,
            reason='Test reason',
            tenant_domain='test.com'
        )
        penalty.generate_code(tenant_schema)
        penalty.save()
        self.assertEqual(penalty.id, 'HR-P-0001')
        self.assertEqual(penalty.code, 'HR-PEN-0001')

    def test_penalty_clean_suspension_without_duration(self):
        penalty = Penalty(
            tenant_id=self.tenant_id,
            employee_id=self.employee_id,
            employee_details=self.employee_details,
            created_by_id=self.created_by_details['id'],
            created_by_details=self.created_by_details,
            reason='Test',
            type=PenaltyType.SUSPENSION.value,
            tenant_domain='test.com'
        )
        with self.assertRaises(ValidationError):
            penalty.full_clean()

    def test_penalty_clean_end_date_after_effective(self):
        penalty = Penalty(
            tenant_id=self.tenant_id,
            employee_id=self.employee_id,
            employee_details=self.employee_details,
            created_by_id=self.created_by_details['id'],
            created_by_details=self.created_by_details,
            reason='Test',
            type=PenaltyType.VERBAL_WARNING.value,
            effective_date='2025-10-10',  # String date
            end_date='2025-10-09',  # Earlier date
            tenant_domain='test.com'
        )
        with self.assertRaises(ValidationError):
            penalty.full_clean()

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

    def test_soft_delete(self):
        reward = Reward.objects.create(
            id='test-id',
            tenant_id=self.tenant_id,
            employee_id=self.employee_id,
            employee_details=self.employee_details,
            created_by_id=self.created_by_details['id'],
            created_by_details=self.created_by_details,
            reason='Test',
            code='test-code',
            type=RewardType.BONUS.value,
            value=100.00,
            tenant_domain='test.com',
            date_issued='2025-10-10',  # String date
            effective_date='2025-10-10'  # String date
        )
        reward.soft_delete()
        self.assertTrue(reward.is_deleted)
        self.assertIsNotNone(reward.deleted_at)
        # Query should not include deleted
        self.assertEqual(Reward.objects.count(), 0)
        self.assertEqual(Reward.objects.all_with_deleted().count(), 1)

    def test_restore(self):
        reward = Reward.objects.create(
            id='test-id',
            tenant_id=self.tenant_id,
            employee_id=self.employee_id,
            employee_details=self.employee_details,
            created_by_id=self.created_by_details['id'],
            created_by_details=self.created_by_details,
            reason='Test',
            code='test-code',
            type=RewardType.BONUS.value,
            value=100.00,
            tenant_domain='test.com',
            date_issued='2025-10-10',  # String date
            effective_date='2025-10-10'  # String date
        )
        reward.soft_delete()
        reward.restore()
        self.assertFalse(reward.is_deleted)
        self.assertIsNone(reward.deleted_at)
        self.assertEqual(Reward.objects.count(), 1)

class SerializersTestCase(APITestCase):
    def setUp(self):
        self.tenant_id = uuid.uuid4()
        self.employee_id = uuid.uuid4()
        self.employee_details = {
            'id': str(self.employee_id),
            'email': 'test@example.com',
            'first_name': 'John',
            'last_name': 'Doe',
            'job_role': 'Developer',
            'department': 'IT'
        }
        self.created_by_details = {
            'id': str(uuid.uuid4()),
            'email': 'creator@example.com',
            'first_name': 'Creator',
            'last_name': 'User',
            'job_role': 'HR',
            'department': 'HR'
        }
        self.reward_data = {
            'employee_id': str(self.employee_id),
            'employee_details': self.employee_details,
            'date_issued': '2025-10-10',  # String date
            'reason': 'Outstanding performance',
            'description': 'Completed project early',
            'type': RewardType.BONUS.value,
            'value': '1000.00',
            'value_type': 'monetary',
            'compliance_checklist': [
                {'name': 'Policy check', 'completed': True}
            ],
            'approval_workflow': {
                'stages': [{'role': 'manager'}]
            }
        }
        self.penalty_data = {
            'employee_id': str(self.employee_id),
            'employee_details': self.employee_details,
            'date_issued': '2025-10-10',  # String date
            'reason': 'Policy violation',
            'description': 'Late submission',
            'type': PenaltyType.VERBAL_WARNING.value,
            'severity_level': 1,
            'compliance_checklist': [
                {'name': 'Legal review', 'completed': True}
            ],
            'approval_workflow': {
                'stages': [{'role': 'hr'}]
            }
        }
        # Mock request for context
        self.mock_request = Mock()
        self.mock_request.META = {'HTTP_AUTHORIZATION': 'Bearer mock_token'}
        self.mock_request.headers = {'Authorization': 'Bearer mock_token'}
        self.mock_request.jwt_payload = {'tenant_unique_id': self.tenant_id, 'tenant_schema': 'HR', 'tenant_domain': 'test.com'}
        self.reward_data['created_by_id'] = str(self.created_by_details['id'])
        self.reward_data['created_by_details'] = self.created_by_details

    @patch('rewards_penalties.serializers.get_tenant_id_from_jwt')
    @patch('rewards_penalties.serializers.jwt.decode')
    def test_reward_serializer_create(self, mock_decode, mock_tenant):
        mock_tenant.return_value = self.tenant_id
        mock_decode.return_value = {
            'tenant_unique_id': self.tenant_id,
            'tenant_schema': 'HR',
            'tenant_domain': 'test.com'
        }
        serializer = RewardSerializer(data=self.reward_data, context={'request': self.mock_request})
        self.assertTrue(serializer.is_valid())
        instance = serializer.save()
        self.assertEqual(instance.tenant_id, self.tenant_id)
        self.assertEqual(instance.type, RewardType.BONUS.value)
        self.assertEqual(instance.value, 1000.00)
        self.assertEqual(instance.id, 'HR-R-0001')
        self.assertEqual(instance.code, 'HR-REW-0001')

    @patch('rewards_penalties.serializers.get_user_data_from_jwt')
    def test_reward_serializer_update_status(self, mock_user_data):
        mock_user_data.return_value = {
            'id': str(uuid.uuid4()),
            'email': 'updater@example.com',
            'first_name': 'Updater',
            'last_name': 'User',
            'job_role': 'HR',
            'department': 'HR'
        }
        reward = Reward.objects.create(
            id='test-id',
            tenant_id=self.tenant_id,
            employee_id=self.employee_id,
            employee_details=self.employee_details,
            created_by_id=uuid.uuid4(),
            created_by_details=self.employee_details,
            reason='Test',
            code='test-code',
            type=RewardType.BONUS.value,
            value=100.00,
            tenant_domain='test.com',
            date_issued='2025-10-10',  # String date
            effective_date='2025-10-10'  # String date
        )
        update_data = {'status': Status.APPROVED.value}
        serializer = RewardSerializer(reward, data=update_data, partial=True, context={'request': self.mock_request})
        self.assertTrue(serializer.is_valid())
        updated = serializer.save()
        self.assertEqual(updated.status, Status.APPROVED.value)
        self.assertIsNotNone(updated.approver_id)
        self.assertIsNotNone(updated.approval_date)

    @patch('rewards_penalties.serializers.get_tenant_id_from_jwt')
    def test_penalty_serializer_validation_mismatch(self, mock_tenant):
        mock_tenant.return_value = uuid.uuid4()  # Different tenant
        serializer = PenaltySerializer(data=self.penalty_data, context={'request': self.mock_request})
        self.assertFalse(serializer.is_valid())
        self.assertIn('tenant_id', serializer.errors)

    @patch('rewards_penalties.serializers.get_tenant_id_from_jwt')
    @patch('rewards_penalties.serializers.jwt.decode')
    def test_penalty_serializer_create(self, mock_decode, mock_tenant):
        mock_tenant.return_value = self.tenant_id
        mock_decode.return_value = {
            'tenant_unique_id': self.tenant_id,
            'tenant_schema': 'HR',
            'tenant_domain': 'test.com'
        }
        serializer = PenaltySerializer(data=self.penalty_data, context={'request': self.mock_request})
        self.assertTrue(serializer.is_valid())
        instance = serializer.save()
        self.assertEqual(instance.tenant_id, self.tenant_id)
        self.assertEqual(instance.type, PenaltyType.VERBAL_WARNING.value)
        self.assertEqual(instance.severity_level, 1)
        self.assertEqual(instance.id, 'HR-P-0001')
        self.assertEqual(instance.code, 'HR-PEN-0001')

    def test_penalty_serializer_update(self):
        penalty = Penalty.objects.create(
            id='test-id',
            tenant_id=self.tenant_id,
            employee_id=self.employee_id,
            employee_details=self.employee_details,
            created_by_id=uuid.uuid4(),
            created_by_details=self.employee_details,
            reason='Test',
            code='test-code',
            type=PenaltyType.VERBAL_WARNING.value,
            severity_level=1,
            tenant_domain='test.com',
            date_issued='2025-10-10',  # String date
            effective_date='2025-10-10'  # String date
        )
        update_data = {
            'description': 'Updated description',
            'duration_days': 3,
            'effective_date': '2025-10-11'
        }
        serializer = PenaltySerializer(penalty, data=update_data, partial=True, context={'request': self.mock_request})
        self.assertTrue(serializer.is_valid())
        updated = serializer.save()
        self.assertEqual(updated.description, 'Updated description')
        self.assertEqual(updated.duration_days, 3)
        expected_end = '2025-10-14'  # 11 + 3 days
        self.assertEqual(updated.end_date, expected_end)

class ViewsTestCase(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant_id = uuid.uuid4()
        self.base_url = '/api/hr/rewards_penalties/rewards/'
        self.penalty_url = '/api/hr/rewards_penalties/penalties/'
        
        # Use string dates
        today_str = '2025-10-10'
        
        self.reward = Reward.objects.create(
            id='test-reward',
            tenant_id=self.tenant_id,
            employee_id=uuid.uuid4(),
            employee_details={'id': 'emp1', 'email': 'emp@example.com', 'first_name': 'Emp', 'last_name': 'One', 'job_role': 'Dev', 'department': 'IT'},
            created_by_id=uuid.uuid4(),
            created_by_details={'id': 'creator1', 'email': 'c@example.com', 'first_name': 'C', 'last_name': 'One', 'job_role': 'HR', 'department': 'HR'},
            reason='Test reward',
            code='TEST-REW-0001',
            type=RewardType.BONUS.value,
            value=500.00,
            tenant_domain='test.com',
            date_issued=today_str,
            effective_date=today_str
        )
        
        self.penalty = Penalty.objects.create(
            id='test-penalty',
            tenant_id=self.tenant_id,
            employee_id=uuid.uuid4(),
            employee_details={'id': 'emp2', 'email': 'emp2@example.com', 'first_name': 'Emp', 'last_name': 'Two', 'job_role': 'Dev', 'department': 'IT'},
            created_by_id=uuid.uuid4(),
            created_by_details={'id': 'creator2', 'email': 'c2@example.com', 'first_name': 'C', 'last_name': 'Two', 'job_role': 'HR', 'department': 'HR'},
            reason='Test penalty',
            code='TEST-PEN-0001',
            type=PenaltyType.VERBAL_WARNING.value,
            severity_level=1,
            tenant_domain='test.com',
            date_issued=today_str,
            effective_date=today_str
        )

    @patch('rewards_penalties.views.getattr')
    @patch('rewards_penalties.views.jwt_payload')
    def test_reward_list_view(self, mock_payload, mock_getattr):
        mock_payload.return_value = {'tenant_unique_id': self.tenant_id}
        mock_getattr.return_value = False
        response = self.client.get(self.base_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], 'test-reward')

    @patch('rewards_penalties.views.close_old_connections')
    @patch('rewards_penalties.serializers.get_user_data_from_jwt')
    @patch('rewards_penalties.serializers.jwt.decode')
    @patch('rewards_penalties.views.jwt_payload')
    def test_reward_create_view(self, mock_payload, mock_decode, mock_user_data, mock_close):
        mock_close.return_value = None
        mock_payload.return_value = {'tenant_unique_id': self.tenant_id, 'tenant_schema': 'TEST', 'tenant_domain': 'test.com'}
        mock_decode.return_value = mock_payload.return_value
        mock_user_data.return_value = {'id': 'user1', 'email': 'u@example.com', 'first_name': 'U', 'last_name': 'One', 'job_role': 'HR', 'department': 'HR'}
        data = {
            'employee_id': str(uuid.uuid4()),
            'employee_details': {'id': 'newemp', 'email': 'new@example.com', 'first_name': 'New', 'last_name': 'Emp', 'job_role': 'Dev', 'department': 'IT'},
            'date_issued': '2025-10-10',
            'reason': 'New reward',
            'type': RewardType.PROMOTION.value,
            'value': '2000.00'
        }
        response = self.client.post(self.base_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['type'], RewardType.PROMOTION.value)
        self.assertIn('TEST-R-', response.data['id'])

    @patch('rewards_penalties.views.close_old_connections')
    @patch('rewards_penalties.serializers.get_user_data_from_jwt')
    @patch('rewards_penalties.views.jwt_payload')
    def test_penalty_update_status(self, mock_payload, mock_user_data, mock_close):
        mock_close.return_value = None
        mock_payload.return_value = {'tenant_unique_id': self.tenant_id}
        mock_user_data.return_value = {'id': 'approver', 'email': 'a@example.com', 'first_name': 'A', 'last_name': 'Prover', 'job_role': 'HR', 'department': 'HR'}
        update_data = {'status': Status.ISSUED.value}
        response = self.client.patch(f'{self.penalty_url}{self.penalty.id}/', update_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        updated_penalty = Penalty.objects.get(id=self.penalty.id)
        self.assertEqual(updated_penalty.status, Status.ISSUED.value)
        self.assertIsNotNone(updated_penalty.approver_id)
        self.assertIsNotNone(updated_penalty.approval_date)

    @patch('rewards_penalties.views.getattr')
    @patch('rewards_penalties.views.jwt_payload')
    def test_penalty_list_view_no_tenant(self, mock_payload, mock_getattr):
        mock_payload.return_value = {'tenant_unique_id': None}
        mock_getattr.return_value = False
        response = self.client.get(self.penalty_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)  # Empty queryset