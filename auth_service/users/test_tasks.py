import pytest
from datetime import timedelta
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.utils import timezone
from django_tenants.test.cases import TenantTestCase  # If using django-tenants
from users.tasks import check_expiring_documents, send_expiry_notification
from users.models import UserProfile, OtherUserDocuments
from core.models import Tenant
from django.contrib.auth import get_user_model

User = get_user_model()

@pytest.mark.django_db
class TestExpiringDocuments(TenantTestCase):  # Or TestCase if single-tenant
    def setUp(self):
        super().setUp()
        self.tenant = self.tenant  # django-tenants sets this
        self.user = User.objects.create_user(
            email='test@example.com', first_name='Test', last_name='User',
            is_active=True, tenant=self.tenant
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            Right_to_work_document_expiry_date=timezone.now().date() + timedelta(days=7)
        )

    @patch('requests.post')  # Mock HTTP call
    def test_warning_notification_sent(self, mock_post):
        mock_post.return_value.status_code = 200
        today = timezone.now().date()
        # Adjust expiry to hit threshold
        self.profile.Right_to_work_document_expiry_date = today + timedelta(days=7)
        self.profile.save()

        with patch('logging.Logger.info') as mock_log:
            check_expiring_documents()

        mock_post.assert_called_once()  # Verifies send_expiry_notification was called
        mock_log.assert_any_call('✅ Notification sent for user.document.expiry.warning')

    @patch('requests.post')
    def test_expired_notification(self, mock_post):
        mock_post.return_value.status_code = 200
        today = timezone.now().date()
        self.profile.Right_to_work_document_expiry_date = today - timedelta(days=2)
        self.profile.save()

        check_expiring_documents()
        mock_post.assert_called_once()
        # Add asserts for payload if needed: mock_post.call_args[1]['json']['event_type'] == 'user.document.expired'

    def test_no_notification_if_no_expiry(self):
        self.profile.Right_to_work_document_expiry_date = None
        self.profile.save()

        with patch('requests.post') as mock_post:
            check_expiring_documents()
        mock_post.assert_not_called()

# Standalone test for send_expiry_notification
@pytest.mark.django_db
def test_send_expiry_notification_payload():
    user = User.objects.create_user(email='test@example.com', first_name='Test', last_name='User')
    doc_info = {'type': 'Test Doc', 'name': 'Test', 'expiry_date': timezone.now().date()}
    with patch('requests.post') as mock_post:
        send_expiry_notification(user, doc_info, 7, 'user.document.expiry.warning')
    args, kwargs = mock_post.call_args
    payload = kwargs['json']
    assert payload['data']['event_type'] == 'user.document.expiry.warning'
    assert payload['data']['days_left'] == 7