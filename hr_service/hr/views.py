# from rest_framework import viewsets, permissions, status
# from rest_framework.decorators import action
# from rest_framework.response import Response
# from django.db.models import Q
# from .models import (
#     LeaveRequest, Contract, Equipment, Policy, PolicyAcknowledgment,
#     EscalationAlert, DisciplinaryWarning, ProbationPeriod, PerformanceReview,
#     EmployeeRelationCase, StarterLeaver, LeaveType
# )
# from .serializers import (
#     LeaveRequestSerializer, ContractSerializer, EquipmentSerializer,
#     PolicySerializer, PolicyAcknowledgmentSerializer, AlertSerializer,
#     DisciplinaryWarningSerializer, ProbationPeriodSerializer,
#     PerformanceReviewSerializer, EmployeeRelationCaseSerializer,
#     StarterLeaverSerializer
# )
# from .utils import fetch_users_from_auth  # Batch fetch
# from .tasks import generate_contract_task  # Celery

# class IsHRUser(permissions.BasePermission):
#     """Access control: Only HR roles (from JWT)."""
#     def has_permission(self, request, view):
#         return request.user.role in ['hr', 'admin', 'root-admin']

# class HRDashboardViewSet(viewsets.ViewSet):
#     permission_classes = [permissions.IsAuthenticated, IsHRUser]

#     @action(detail=False, methods=['get'])
#     def dashboard(self, request):
#         """Step 2: Centralized dashboard (profiles, leave, alerts, monitoring tables)."""
#         tenant = request.user.tenant
#         # Fetch employee profiles from auth
#         users = fetch_users_from_auth(tenant.id, include_profile=True)
#         # Leave balances
#         leave_data = LeaveRequest.objects.filter(tenant=tenant).values('user_id').annotate(
#             taken=Sum('days_requested'),
#             pending=Count('id', filter=Q(status='pending'))
#         )
#         # Monitoring tables
#         probation_active = ProbationPeriod.objects.filter(tenant=tenant, status='in_progress').count()
#         warnings_active = DisciplinaryWarning.objects.filter(tenant=tenant, is_active=True).count()
#         er_open = EmployeeRelationCase.objects.filter(tenant=tenant, status='open').count()
#         starters_this_month = StarterLeaver.objects.filter(
#             tenant=tenant, type='starter',
#             start_date__month=timezone.now().month
#         ).count()
#         leavers_this_month = StarterLeaver.objects.filter(
#             tenant=tenant, type='leaver',
#             end_date__month=timezone.now().month
#         ).count()
#         alerts_count = EscalationAlert.objects.filter(tenant=tenant, resolved=False).count()
#         return Response({
#             'users': users,
#             'leave_summary': list(leave_data),
#             'monitoring': {
#                 'probation_active': probation_active,
#                 'warnings_active': warnings_active,
#                 'er_open': er_open,
#                 'starters': starters_this_month,
#                 'leavers': leavers_this_month,
#             },
#             'alerts_count': alerts_count
#         })


# class LeaveViewSet(viewsets.ModelViewSet):
#     queryset = LeaveRequest.objects.all()
#     serializer_class = LeaveRequestSerializer
#     permission_classes = [permissions.IsAuthenticated, IsHRUser]

#     def get_queryset(self):
#         return self.queryset.filter(tenant=self.request.user.tenant)

#     def perform_create(self, serializer):
#         instance = serializer.save(tenant=self.request.user.tenant, user_id=self.request.user.id)
#         if instance.status == 'approved':
#             from .tasks import notify_leave_approved
#             notify_leave_approved.delay(instance.id)

#     @action(detail=True, methods=['post'])
#     def approve(self, request, pk=None):
#         leave = self.get_object()
#         leave.status = 'approved'
#         leave.approved_by_id = request.user.id
#         leave.save()
#         return Response(LeaveRequestSerializer(leave).data)


# class ContractViewSet(viewsets.ModelViewSet):
#     queryset = Contract.objects.all()
#     serializer_class = ContractSerializer
#     permission_classes = [permissions.IsAuthenticated, IsHRUser]

#     def get_queryset(self):
#         return self.queryset.filter(tenant=self.request.user.tenant)

#     @action(detail=True, methods=['post'])
#     def generate(self, request, pk=None):
#         contract = self.get_object()
#         generate_contract_task.delay(contract.id)
#         return Response({'status': 'Generation started'})


# class EquipmentViewSet(viewsets.ModelViewSet):
#     queryset = Equipment.objects.all()
#     serializer_class = EquipmentSerializer
#     permission_classes = [permissions.IsAuthenticated, IsHRUser]

#     def get_queryset(self):
#         return self.queryset.filter(tenant=self.request.user.tenant)

#     @action(detail=True, methods=['post'])
#     def issue(self, request, pk=None):
#         equipment = self.get_object()
#         equipment.issue()
#         return Response({'status': 'Issued, e-sign sent'})


# class PolicyViewSet(viewsets.ModelViewSet):
#     queryset = Policy.objects.all()
#     serializer_class = PolicySerializer
#     permission_classes = [permissions.IsAuthenticated, IsHRUser]

#     def get_queryset(self):
#         return self.queryset.filter(tenant=self.request.user.tenant)


# class PolicyAcknowledgmentViewSet(viewsets.ModelViewSet):
#     queryset = PolicyAcknowledgment.objects.all()
#     serializer_class = PolicyAcknowledgmentSerializer
#     permission_classes = [permissions.IsAuthenticated]

#     def get_queryset(self):
#         return self.queryset.filter(tenant=self.request.user.tenant, user_id=self.request.user.id)

#     def perform_create(self, serializer):
#         ack = serializer.save(tenant=self.request.user.tenant, user_id=self.request.user.id)
#         if not ack.is_compliant:
#             from .tasks import send_policy_reminder
#             send_policy_reminder.delay(ack.id)


# class AlertViewSet(viewsets.ModelViewSet):
#     queryset = EscalationAlert.objects.all()
#     serializer_class = AlertSerializer
#     permission_classes = [permissions.IsAuthenticated, IsHRUser]

#     def get_queryset(self):
#         return self.queryset.filter(tenant=self.request.user.tenant)


# class MonitoringViewSet(viewsets.ViewSet):
#     permission_classes = [permissions.IsAuthenticated, IsHRUser]

#     @action(detail=False, methods=['get'])
#     def probation(self, request):
#         """HR Monitoring: Probation table."""
#         tenant = request.user.tenant
#         probs = ProbationPeriod.objects.filter(tenant=tenant).select_related('user_id')
#         return Response(ProbationPeriodSerializer(probs, many=True).data)

#     @action(detail=False, methods=['get'])
#     def warnings(self, request):
#         """Active warnings table."""
#         tenant = request.user.tenant
#         warnings = DisciplinaryWarning.objects.filter(tenant=tenant, is_active=True)
#         return Response(DisciplinaryWarningSerializer(warnings, many=True).data)

#     @action(detail=False, methods=['get'])
#     def er_cases(self, request):
#         """Ongoing ER cases table."""
#         tenant = request.user.tenant
#         cases = EmployeeRelationCase.objects.filter(tenant=tenant, status='open')
#         return Response(EmployeeRelationCaseSerializer(cases, many=True).data)

#     @action(detail=False, methods=['get'])
#     def starters_leavers(self, request):
#         """Starters/leavers table."""
#         tenant = request.user.tenant
#         starters_leavers = StarterLeaver.objects.filter(tenant=tenant).order_by('-created_at')
#         return Response(StarterLeaverSerializer(starters_leavers, many=True).data)


# class AnalyticsViewSet(viewsets.ViewSet):
#     permission_classes = [permissions.IsAuthenticated, IsHRUser]

#     @action(detail=False, methods=['get'])
#     def reports(self, request):
#         """Step 8: Custom reports."""
#         tenant = request.user.tenant
#         # New starters/leavers
#         starters = StarterLeaver.objects.filter(tenant=tenant, type='starter').count()
#         leavers = StarterLeaver.objects.filter(tenant=tenant, type='leaver').count()
#         turnover = (leavers / (starters + leavers) * 100) if (starters + leavers) else 0
#         # Leave trends
#         sick_trends = LeaveRequest.objects.filter(
#             tenant=tenant, leave_type__name='sick'
#         ).aggregate(avg_bradford=Avg('bradford_factor'), total_absences=Count('id'))
#         leave_taken = LeaveRequest.objects.filter(tenant=tenant, status='approved').aggregate(taken=Sum('days_requested'))['taken'] or 0
#         # Sickness absence trends (Bradford insights)
#         high_risk_users = LeaveRequest.objects.filter(
#             tenant=tenant, bradford_factor__gt=100
#         ).values('user_id').distinct().count()
#         # Outstanding balances (aggregate)
#         outstanding = sum(lr.get_balance() for lr in LeaveRequest.objects.filter(tenant=tenant)[:100])  # Sample
#         return Response({
#             'turnover_rate': round(turnover, 2),
#             'sick_trends': sick_trends,
#             'leave_taken': leave_taken,
#             'high_risk_users': high_risk_users,
#             'outstanding_balances': outstanding,
#         })

import logging
import jwt
import requests
import uuid
from django.db import close_old_connections, connection, transaction, models
from django.conf import settings
from django.utils import timezone
from rest_framework import generics, viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from urllib.parse import urlparse, urlencode



from .models import (
    LeaveType, LeaveRequest, Contract, Equipment, Policy, 
    PolicyAcknowledgment, EscalationAlert, DisciplinaryWarning,
    ProbationPeriod, PerformanceReview, EmployeeRelationCase, StarterLeaver
)
from .serializers import (
    LeaveTypeSerializer, LeaveRequestSerializer, ContractSerializer,
    EquipmentSerializer, PolicySerializer, PolicyAcknowledgmentSerializer,
    EscalationAlertSerializer, DisciplinaryWarningSerializer,
    ProbationPeriodSerializer, PerformanceReviewSerializer,
    EmployeeRelationCaseSerializer, StarterLeaverSerializer
)

logger = logging.getLogger('hr')

# Reuse the same utility functions from talent_engine
def ensure_db_connection():
    """Ensure database connection is alive"""
    try:
        close_old_connections()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {str(e)}")
        connection.close()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            return True
        except Exception as e2:
            logger.error(f"Database reconnection failed: {str(e2)}")
            return False

def get_tenant_id_from_jwt(request):
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        raise ValidationError('No valid Bearer token provided.')
    token = auth_header.split(' ')[1]
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        return payload.get('tenant_unique_id')
    except Exception:
        raise ValidationError('Invalid JWT token.')

def get_user_data_from_jwt(request):
    """Extract user data from JWT payload."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise serializers.ValidationError("No valid Bearer token provided.")
    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        user_data = payload.get("user", {})
        return {
            'email': user_data.get('email', ''),
            'first_name': user_data.get('first_name', ''),
            'last_name': user_data.get('last_name', ''),
            'job_role': user_data.get('job_role', ''),
            'id': user_data.get('id', None)
        }
    except Exception as e:
        logger.error(f"Failed to decode JWT for user data: {str(e)}")
        raise serializers.ValidationError("Invalid JWT token for user data.")

# Reuse the same pagination class
class CustomPagination(PageNumberPagination):
    page_size = 100

    def get_next_link(self):
        if not self.page.has_next():
            return None
        gateway_url = getattr(settings, 'GATEWAY_URL', None)
        if not gateway_url:
            return super().get_next_link()
        
        request = self.request
        path = request.path
        query_params = request.query_params.copy()
        query_params['page'] = self.page.next_page_number()
        query_string = urlencode(query_params, doseq=True)

        parsed_gateway = urlparse(gateway_url)
        full_url = f"{parsed_gateway.scheme}://{parsed_gateway.netloc}{path}?{query_string}"
        return full_url

    def get_previous_link(self):
        if not self.page.has_previous():
            return None
        gateway_url = getattr(settings, 'GATEWAY_URL', None)
        if not gateway_url:
            return super().get_previous_link()

        request = self.request
        path = request.path
        query_params = request.query_params.copy()
        query_params['page'] = self.page.previous_page_number()
        query_string = urlencode(query_params, doseq=True)

        parsed_gateway = urlparse(gateway_url)
        full_url = f"{parsed_gateway.scheme}://{parsed_gateway.netloc}{path}?{query_string}"
        return full_url

# Base ViewSet for HR models
class HRBaseViewSet(viewsets.ModelViewSet):
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, SearchFilter]
    
    def get_queryset(self):
        """Filter by tenant_id from JWT"""
        if not ensure_db_connection():
            logger.error("Database connection unavailable")
            return self.queryset.model.objects.none()
            
        if getattr(self, "swagger_fake_view", False):
            return self.queryset.model.objects.none()
            
        jwt_payload = getattr(self.request, 'jwt_payload', {})
        tenant_id = str(jwt_payload.get('tenant_unique_id')) if jwt_payload.get('tenant_unique_id') is not None else None
        
        if not tenant_id:
            return self.queryset.model.objects.none()
            
        return self.queryset.filter(tenant_id=tenant_id)

# Leave Type Views
class LeaveTypeViewSet(HRBaseViewSet):
    queryset = LeaveType.objects.all()
    serializer_class = LeaveTypeSerializer
    search_fields = ['name']
    filterset_fields = ['is_paid', 'requires_approval', 'carry_over_allowed']

    @action(detail=True, methods=['post'])
    def calculate_entitlement(self, request, pk=None):
        """Calculate pro-rata entitlement for a specific hire date"""
        leave_type = self.get_object()
        hire_date = request.data.get('hire_date')
        current_date = request.data.get('current_date', timezone.now().date())
        
        if not hire_date:
            return Response({"error": "hire_date is required"}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            hire_date = timezone.datetime.strptime(hire_date, '%Y-%m-%d').date()
            entitlement = leave_type.calculate_entitlement(hire_date, current_date)
            return Response({
                "leave_type": leave_type.name,
                "hire_date": hire_date,
                "current_date": current_date,
                "entitlement_days": entitlement,
                "max_days": leave_type.max_days
            })
        except ValueError:
            return Response({"error": "Invalid date format. Use YYYY-MM-DD"}, status=status.HTTP_400_BAD_REQUEST)

# Leave Request Views
class LeaveRequestViewSet(HRBaseViewSet):
    queryset = LeaveRequest.objects.all()
    serializer_class = LeaveRequestSerializer
    search_fields = ['leave_type__name', 'status', 'notes']
    filterset_fields = ['status', 'leave_type_id', 'start_date', 'end_date']

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by user_id if provided
        user_id = self.request.query_params.get('user_id')
        if user_id:
            queryset = queryset.filter(user_id=user_id)
            
        return queryset

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        leave_request = self.get_object()
        leave_request.status = 'approved'
        leave_request.approved_by_id = get_user_data_from_jwt(request)['id']
        leave_request.save()
        
        logger.info(f"Leave request {pk} approved by {leave_request.approved_by_id}")
        return Response({"status": "approved", "balance": leave_request.get_balance()})

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        leave_request = self.get_object()
        leave_request.status = 'rejected'
        leave_request.save()
        
        logger.info(f"Leave request {pk} rejected")
        return Response({"status": "rejected"})

    @action(detail=False, methods=['get'])
    def balance(self, request):
        """Get leave balance for current user"""
        user_data = get_user_data_from_jwt(request)
        user_id = user_data['id']
        
        leave_balances = []
        leave_types = LeaveType.objects.filter(tenant_id=get_tenant_id_from_jwt(request))
        
        for leave_type in leave_types:
            # This would need actual hire date from user profile
            # For demo, using current date as hire date
            hire_date = timezone.now().date() - timezone.timedelta(days=180)  # 6 months ago
            entitlement = leave_type.calculate_entitlement(hire_date, timezone.now().date())
            
            taken = LeaveRequest.objects.filter(
                user_id=user_id, 
                leave_type=leave_type, 
                status='approved'
            ).aggregate(taken=models.Sum('days_requested'))['taken'] or 0
            
            leave_balances.append({
                'leave_type': leave_type.name,
                'entitlement': entitlement,
                'taken': taken,
                'balance': entitlement - taken
            })
            
        return Response(leave_balances)

# Contract Views
class ContractViewSet(HRBaseViewSet):
    queryset = Contract.objects.all()
    serializer_class = ContractSerializer
    search_fields = ['type', 'probation_status']
    filterset_fields = ['type', 'is_signed', 'probation_status']

    @action(detail=True, methods=['post'])
    def generate_contract(self, request, pk=None):
        """Generate and initiate e-sign process"""
        contract = self.get_object()
        try:
            contract.generate_and_sign()
            return Response({"status": "contract_generation_initiated"})
        except Exception as e:
            logger.error(f"Contract generation failed: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def mark_signed(self, request, pk=None):
        """Mark contract as signed (typically called via webhook)"""
        contract = self.get_object()
        contract.is_signed = True
        contract.signed_at = timezone.now()
        contract.save()
        
        logger.info(f"Contract {pk} marked as signed")
        return Response({"status": "signed"})

# Equipment Views
class EquipmentViewSet(HRBaseViewSet):
    queryset = Equipment.objects.all()
    serializer_class = EquipmentSerializer
    search_fields = ['item_name', 'serial_number', 'rfid_tag']
    filterset_fields = ['is_returned', 'acceptance_signed']

    @action(detail=True, methods=['post'])
    def issue_equipment(self, request, pk=None):
        """Issue equipment and initiate acceptance process"""
        equipment = self.get_object()
        try:
            equipment.issue()
            return Response({"status": "equipment_issuance_initiated"})
        except Exception as e:
            logger.error(f"Equipment issuance failed: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def mark_returned(self, request, pk=None):
        """Mark equipment as returned"""
        equipment = self.get_object()
        equipment.is_returned = True
        equipment.return_date = timezone.now().date()
        equipment.save()
        
        logger.info(f"Equipment {pk} marked as returned")
        return Response({"status": "returned"})

# Policy Views
class PolicyViewSet(HRBaseViewSet):
    queryset = Policy.objects.all()
    serializer_class = PolicySerializer
    search_fields = ['title', 'content']
    filterset_fields = ['requires_acknowledgment', 'quiz_required']

# Policy Acknowledgment Views
class PolicyAcknowledgmentViewSet(HRBaseViewSet):
    queryset = PolicyAcknowledgment.objects.all()
    serializer_class = PolicyAcknowledgmentSerializer
    search_fields = ['policy__title']
    filterset_fields = ['is_compliant']

    @action(detail=True, methods=['post'])
    def submit_quiz(self, request, pk=None):
        """Submit quiz answers and calculate score"""
        acknowledgment = self.get_object()
        answers = request.data.get('answers', [])
        
        # Calculate score (simplified)
        total_questions = len(acknowledgment.policy.quiz_questions)
        correct_answers = 0
        
        for i, question in enumerate(acknowledgment.policy.quiz_questions):
            if i < len(answers) and answers[i] == question.get('correct_answer'):
                correct_answers += 1
                
        score = (correct_answers / total_questions) * 100 if total_questions > 0 else 0
        acknowledgment.quiz_score = score
        acknowledgment.save()
        
        return Response({
            "score": score,
            "is_compliant": acknowledgment.is_compliant,
            "correct_answers": correct_answers,
            "total_questions": total_questions
        })

# Escalation Alert Views
class EscalationAlertViewSet(HRBaseViewSet):
    queryset = EscalationAlert.objects.all()
    serializer_class = EscalationAlertSerializer
    search_fields = ['type', 'description']
    filterset_fields = ['type', 'severity', 'resolved']

    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Resolve an escalation alert"""
        alert = self.get_object()
        alert.resolved = True
        alert.resolved_at = timezone.now()
        alert.save()
        
        logger.info(f"Escalation alert {pk} resolved")
        return Response({"status": "resolved"})

    @action(detail=False, methods=['get'])
    def unresolved(self, request):
        """Get unresolved alerts"""
        queryset = self.get_queryset().filter(resolved=False)
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
            
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

# Disciplinary Warning Views
class DisciplinaryWarningViewSet(HRBaseViewSet):
    queryset = DisciplinaryWarning.objects.all()
    serializer_class = DisciplinaryWarningSerializer
    search_fields = ['reason']
    filterset_fields = ['is_active']

# Probation Period Views
class ProbationPeriodViewSet(HRBaseViewSet):
    queryset = ProbationPeriod.objects.all()
    serializer_class = ProbationPeriodSerializer
    search_fields = ['status', 'review_notes']
    filterset_fields = ['status']

    @action(detail=True, methods=['post'])
    def complete_review(self, request, pk=None):
        """Complete probation review"""
        probation = self.get_object()
        status = request.data.get('status')
        review_notes = request.data.get('review_notes', '')
        
        if status not in ['passed', 'failed']:
            return Response({"error": "Status must be 'passed' or 'failed'"}, status=status.HTTP_400_BAD_REQUEST)
            
        probation.status = status
        probation.review_notes = review_notes
        probation.save()
        
        logger.info(f"Probation {pk} marked as {status}")
        return Response({"status": status})

# Performance Review Views
class PerformanceReviewViewSet(HRBaseViewSet):
    queryset = PerformanceReview.objects.all()
    serializer_class = PerformanceReviewSerializer
    search_fields = ['feedback']
    filterset_fields = ['training_completed']

# Employee Relation Case Views
class EmployeeRelationCaseViewSet(HRBaseViewSet):
    queryset = EmployeeRelationCase.objects.all()
    serializer_class = EmployeeRelationCaseSerializer
    search_fields = ['title', 'description']
    filterset_fields = ['status']

    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        """Assign ER case to someone"""
        case = self.get_object()
        assigned_to_id = request.data.get('assigned_to_id')
        
        if not assigned_to_id:
            return Response({"error": "assigned_to_id is required"}, status=status.HTTP_400_BAD_REQUEST)
            
        case.assigned_to_id = assigned_to_id
        case.status = 'in_progress'
        case.save()
        
        logger.info(f"ER case {pk} assigned to {assigned_to_id}")
        return Response({"status": "assigned"})

# Starter Leaver Views
class StarterLeaverViewSet(HRBaseViewSet):
    queryset = StarterLeaver.objects.all()
    serializer_class = StarterLeaverSerializer
    search_fields = ['type', 'reason']
    filterset_fields = ['type']

# Analytics and Dashboard Views
class HRAnalyticsView(APIView):
    def get(self, request):
        tenant_id = get_tenant_id_from_jwt(request)
        
        # Leave analytics
        leave_stats = LeaveRequest.objects.filter(tenant_id=tenant_id).aggregate(
            total_requests=models.Count('id'),
            pending_requests=models.Count('id', filter=models.Q(status='pending')),
            approved_requests=models.Count('id', filter=models.Q(status='approved'))
        )
        
        # Equipment analytics
        equipment_stats = Equipment.objects.filter(tenant_id=tenant_id).aggregate(
            total_equipment=models.Count('id'),
            issued_equipment=models.Count('id', filter=models.Q(is_returned=False)),
            returned_equipment=models.Count('id', filter=models.Q(is_returned=True))
        )
        
        # Policy compliance
        policy_stats = PolicyAcknowledgment.objects.filter(tenant_id=tenant_id).aggregate(
            total_acknowledgments=models.Count('id'),
            compliant_acknowledgments=models.Count('id', filter=models.Q(is_compliant=True))
        )
        
        # Escalation alerts
        alert_stats = EscalationAlert.objects.filter(tenant_id=tenant_id).aggregate(
            total_alerts=models.Count('id'),
            resolved_alerts=models.Count('id', filter=models.Q(resolved=True)),
            high_severity_alerts=models.Count('id', filter=models.Q(severity='high'))
        )
        
        return Response({
            'leave_analytics': leave_stats,
            'equipment_analytics': equipment_stats,
            'policy_compliance': policy_stats,
            'escalation_alerts': alert_stats
        })

# Public endpoints for certain HR data (if needed)
class PublicLeavePoliciesView(APIView):
    permission_classes = []  # No authentication required
    
    def get(self, request, tenant_unique_id):
        close_old_connections()
        
        try:
            policies = Policy.objects.filter(
                tenant_id=tenant_unique_id,
                requires_acknowledgment=True
            )
            serializer = PolicySerializer(policies, many=True)
            
            return Response({
                "count": len(serializer.data),
                "results": serializer.data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error fetching public policies for tenant {tenant_unique_id}: {str(e)}")
            return Response({"detail": "An error occurred."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
# views.py
class HRAnalyticsDashboardView(APIView):
    def get(self, request):
        tenant_id = get_tenant_id_from_jwt(request)
        
        # Headcount analytics
        headcount_data = {
            'total_employees': self.get_total_employees(tenant_id),
            'department_breakdown': self.get_department_breakdown(tenant_id),
            'turnover_rate': self.get_turnover_rate(tenant_id),
            'diversity_metrics': self.get_diversity_metrics(tenant_id),
        }
        
        # Leave analytics
        leave_analytics = {
            'leave_utilization': self.get_leave_utilization(tenant_id),
            'sick_leave_trends': self.get_sick_leave_trends(tenant_id),
            'department_leave_comparison': self.get_department_leave_comparison(tenant_id),
        }
        
        # Performance analytics
        performance_analytics = {
            'average_performance_score': self.get_avg_performance_score(tenant_id),
            'high_performers': self.get_high_performers(tenant_id),
            'improvement_areas': self.get_improvement_areas(tenant_id),
        }
        
        return Response({
            'headcount_analytics': headcount_data,
            'leave_analytics': leave_analytics,
            'performance_analytics': performance_analytics,
            'cost_analytics': self.get_cost_analytics(tenant_id)
        })
    
