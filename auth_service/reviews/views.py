from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db.models import Avg, Count
from django_tenants.utils import tenant_context
from django.utils import timezone
from django.db.models.functions import TruncMonth
from .models import Review, QRCode, ReviewSettings
from .serializers import ReviewSerializer, ReviewCreateSerializer, QRCodeSerializer, ReviewSettingsSerializer
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
import csv
from django.conf import settings
from django.http import HttpResponse, JsonResponse
import requests
import uuid
import logging
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods
from cryptography.fernet import Fernet
from cryptography.fernet import InvalidToken
import json
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from rest_framework.pagination import PageNumberPagination
from django.core.cache import cache  # Added for dedup (already used in code)

logger = logging.getLogger(__name__)


@require_http_methods(["GET"])
def qr_submit_view(request):
    token = request.GET.get('token')
    if not token:
        logger.warning("❌ No token provided in QR submit request")
        return JsonResponse({'error': 'Invalid QR code'}, status=400)

    try:
        # Decode token (in public schema—fine, no tenant data needed yet)
        fernet = Fernet(settings.QR_ENCRYPTION_KEY.encode())
        payload = fernet.decrypt(token.encode('utf-8')).decode('utf-8')
        decoded_data = json.loads(payload)
        tenant_unique_id = decoded_data['tenant_id']
        qr_unique_id = decoded_data['qr_id']
        logger.debug(f"🔓 Decoded token: tenant_id={tenant_unique_id}, qr_id={qr_unique_id}")  # Dev log

        # Fetch tenant (from public schema)
        from core.models import Tenant
        tenant = get_object_or_404(Tenant, unique_id=tenant_unique_id)

        # FIXED: Switch to tenant schema for QR/review data
        with tenant_context(tenant):
            qr = get_object_or_404(QRCode, tenant=tenant, unique_id=qr_unique_id, is_active=True)
            logger.debug(f"✅ QR found: {qr.id} ({qr.unique_id}) in schema {tenant.schema_name}")

            # Deduplication
            ip = request.META.get('REMOTE_ADDR', 'unknown')
            cache_key = f"qr_scan:{qr.id}:{ip}"
            if cache.get(cache_key) is None:
                qr.increment_actual_scan()
                cache.set(cache_key, True, 3600)
                logger.info(f"📱 Actual QR scan incremented for {qr.unique_id} (IP: {ip}): now {qr.actual_scan_count}")
            else:
                logger.debug(f"🔄 QR scan deduped for {qr.unique_id} (IP: {ip})")

            # Settings (in tenant schema)
            try:
                review_settings = tenant.review_settings
                enable_anonymous = review_settings.enable_anonymous
                max_attachments = review_settings.max_attachments
                approval_required = review_settings.approval_required
            except ReviewSettings.DoesNotExist:  # FIXED: Direct model exception
                logger.warning(f"⚠️ No ReviewSettings for tenant {tenant.unique_id}; using defaults")
                enable_anonymous = True
                max_attachments = 3
                approval_required = True

            qr_description = json.loads(qr.qr_data).get('description', 'Scan to review')

        # Response (back in public schema—fine)
        return JsonResponse({
            'success': True,
            'qr_id': str(qr.id),
            'tenant_id': str(tenant.unique_id),  # NEW: For submit context
            'description': qr_description,
            'enable_anonymous': enable_anonymous,
            'max_attachments': max_attachments,
            'approval_required': approval_required,
        })

    except (QRCode.DoesNotExist, Tenant.DoesNotExist):  # NEW: Specific handling for 404
        logger.error(f"❌ Invalid QR code: tenant={tenant_unique_id}, qr_id={qr_unique_id}")
        return JsonResponse({'error': 'Invalid QR code'}, status=400)
    except InvalidToken:
        logger.error(f"❌ Invalid token in QR submit: {token[:10]}...")
        return JsonResponse({'error': 'Invalid QR code'}, status=400)
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"❌ Decode error in QR submit: {str(e)}")
        return JsonResponse({'error': 'Invalid QR code'}, status=400)
    except Exception as e:
        logger.error(f"❌ Unexpected error in QR submit: {str(e)}", exc_info=True)
        return JsonResponse({'error': 'Server error'}, status=500)


class CustomPagination(PageNumberPagination):
    page_size = 20  # Adjust as needed

    def get_next_link(self):
        """Override to use gateway base URL."""
        if not self.page.has_next():
            return None
        gateway_url = getattr(settings, 'GATEWAY_URL', None)
        if not gateway_url:
            return super().get_next_link()  # Fallback to default

        request = self.request
        # Build base path from current request (e.g., /api/user/users/)
        path = request.path
        # Get query params, update 'page', preserve others
        query_params = request.query_params.copy()
        query_params['page'] = self.page.next_page_number()
        query_string = urlencode(query_params, doseq=True)

        # Reconstruct full URL with gateway scheme/host
        parsed_gateway = urlparse(gateway_url)
        full_url = f"{parsed_gateway.scheme}://{parsed_gateway.netloc}{path}?{query_string}"
        return full_url

    def get_previous_link(self):
        """Override to use gateway base URL."""
        if not self.page.has_previous():
            return None
        gateway_url = getattr(settings, 'GATEWAY_URL', None)
        if not gateway_url:
            return super().get_previous_link()  # Fallback to default

        request = self.request
        path = request.path
        query_params = request.query_params.copy()
        query_params['page'] = self.page.previous_page_number()
        query_string = urlencode(query_params, doseq=True)

        parsed_gateway = urlparse(gateway_url)
        full_url = f"{parsed_gateway.scheme}://{parsed_gateway.netloc}{path}?{query_string}"
        return full_url

    def get_paginated_response(self, data):
        """Ensure the full response uses overridden links."""
        response = super().get_paginated_response(data)
        gateway_url = getattr(settings, 'GATEWAY_URL', None)
        if gateway_url:
            response['next'] = self.get_next_link()
            response['previous'] = self.get_previous_link()
        return response



def send_review_notification(event_type, review, user=None, extra_data=None):
    """Send event to notifications service."""
    try:
        logger.info(f"📨 Sending {event_type} notification for review {review.id}")
        
        tenant_id = str(review.tenant.unique_id)
        event_id = f"evt-{uuid.uuid4().hex[:8]}"
        now = timezone.now().isoformat()

        payload = {
            "metadata": {
                "event_id": event_id,
                "event_type": event_type,
                "event_version": "1.0",
                "created_at": now,
                "source": "reviews-service",
                "tenant_id": tenant_id,
                "timestamp": now,
            },
            "data": {
                "review_id": str(review.id),
                "reviewer_email": review.reviewer_email,
                "rating": review.rating,
                "comment_preview": review.comment[:100] + "..." if len(review.comment) > 100 else review.comment,
                "submitted_at": review.submitted_at.isoformat() if review.submitted_at else now,
                **(extra_data or {}),
            },
        }

        if user:
            payload["data"]["performed_by"] = user.email

        url = f"{settings.NOTIFICATIONS_SERVICE_URL}/events/"
        logger.debug(f"Notification payload: {payload}")
        response = requests.post(url, json=payload, timeout=5)
        response.raise_for_status()
        logger.info(f"✅ Successfully sent {event_type} for review {review.id}: {response.status_code}")
    except Exception as e:
        logger.error(f"❌ Failed to send {event_type} for review {review.id}: {str(e)}")



class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
    permission_classes = [AllowAny]
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['is_approved', 'rating']
    search_fields = ['comment']
    ordering_fields = ['submitted_at', 'rating']

    def get_queryset(self):
        logger.debug(f"🔍 Getting reviews queryset for user: {self.request.user}, tenant: {getattr(self.request.user, 'tenant', 'No tenant')}")
        tenant = self.request.user.tenant
        with tenant_context(tenant):
            qs = super().get_queryset().filter(tenant=tenant)
            if not self.request.user.is_superuser and self.request.user.role != 'admin':
                logger.debug("👀 Non-admin user - filtering to show only approved reviews")
                qs = qs.filter(is_approved=True)  # Non-admins see only approved
            logger.debug(f"📊 Returning {qs.count()} reviews")
            return qs

    def get_permissions(self):
        """
        Instant permissions are determined by the type of action.
        Overrides to allow anon for public create.
        """
        logger.debug(f"🔐 Getting permissions for action: {self.action}")
        if self.action == 'create' and self.request.data.get('qr_id'):
            logger.info("🌐 Allowing public access for QR-based review creation")
            permission_classes = [AllowAny]
            return [permission() for permission in permission_classes]
        return super().get_permissions()

    def get_serializer_class(self):
        logger.debug(f"📝 Getting serializer class for action: {self.action}")
        if self.action == 'create':
            logger.debug("🆕 Using ReviewCreateSerializer for create action")
            return ReviewCreateSerializer
        return self.serializer_class

    def create(self, request, *args, **kwargs):
        logger.info(f"🆕 Creating new review. User: {request.user}, Data keys: {list(request.data.keys())}")
        
        # Get tenant_id from request (from QR response)
        tenant_id_str = request.data.get('tenant_id')
        if not tenant_id_str:
            return Response({'error': 'Missing tenant_id for public submission'}, status=status.HTTP_400_BAD_REQUEST)
        
        from core.models import Tenant
        try:
            tenant = Tenant.objects.get(unique_id=tenant_id_str)
        except Tenant.DoesNotExist:
            return Response({'error': 'Invalid tenant for submission'}, status=status.HTTP_400_BAD_REQUEST)
        
        # FIXED: Switch schema for ENTIRE serializer process (validation + creation)
        with tenant_context(tenant):
            # Set context for serializer
            serializer_context = {'request': request}
            if request.data.get('qr_id'):
                try:
                    qr_id = request.data['qr_id']
                    logger.debug(f"🔍 Looking up QR code with ID: {qr_id} in tenant {tenant.schema_name}")
                    qr = QRCode.objects.get(id=qr_id)  # Now safe in tenant context
                    serializer_context.update({
                        'qr_code': qr,
                        'tenant': tenant,
                    })
                    logger.info(f"✅ QR code found: {qr.unique_id} for tenant: {tenant.name}")
                except QRCode.DoesNotExist:
                    logger.error(f"❌ Invalid QR code ID: {qr_id}")
                    return Response({'error': 'Invalid QR code ID'}, status=status.HTTP_400_BAD_REQUEST)
            
            logger.debug("📦 Creating review with serializer")
            serializer = self.get_serializer(data=request.data, context=serializer_context)
            serializer.is_valid(raise_exception=True)  # Validation now in tenant schema
            self.perform_create(serializer)  # Creation in tenant schema
            headers = self.get_success_headers(serializer.data)
            
            # Use full serializer for response (still in tenant schema, fine)
            full_serializer = ReviewSerializer(serializer.instance)
        
        # Response outside context (public schema, no issue)
        return Response(full_serializer.data, status=status.HTTP_201_CREATED, headers=headers)


    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def approve(self, request, pk=None):
        logger.info(f"✅ Approve action called for review {pk} by user {request.user}")
        review = self.get_object()
        
        if request.user.role not in ['admin', 'super-admin']:
            logger.warning(f"⛔ User {request.user} with role {request.user.role} attempted to approve review without permission")
            return Response({'error': 'Insufficient permissions'}, status=status.HTTP_403_FORBIDDEN)
        
        logger.debug(f"👍 Approving review {review.id} by user {request.user}")
        review.approve(request.user)
        
        # Send approval notification
        send_review_notification("reviews.approved", review, user=request.user)
        if review.qr_code:
            send_review_notification("reviews.qr_scanned", review, extra_data={"qr_id": str(review.qr_code.id)})
        
        logger.info(f"✅ Review {review.id} approved successfully")
        return Response({'status': 'approved'}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def analytics(self, request):
        logger.info(f"📊 Analytics endpoint called by user: {request.user}, tenant: {getattr(request.user, 'tenant', 'No tenant')}")
        tenant = request.user.tenant
        
        with tenant_context(tenant):
            try:
                logger.debug("🔍 Fetching approved reviews for analytics")
                approved_reviews = Review.objects.filter(tenant=tenant, is_approved=True)
                total = approved_reviews.count()
                avg_rating = approved_reviews.aggregate(Avg('rating'))['rating__avg'] or 0
                avg_sentiment = approved_reviews.aggregate(Avg('sentiment_score'))['sentiment_score__avg'] or 0
                
                logger.debug("📈 Calculating sentiment distribution")
                sentiment_dist = approved_reviews.values('sentiment_score').annotate(count=Count('id')).order_by()
                
                logger.debug("📅 Calculating monthly trends")
                trends = list(approved_reviews
                          .annotate(month=TruncMonth('submitted_at'))
                          .values('month')
                          .annotate(
                              count=Count('id'),
                              avg_rating=Avg('rating'),
                              avg_sentiment=Avg('sentiment_score')
                          )
                          .order_by('month'))
                
                analytics_data = {
                    'total_reviews': total,
                    'avg_rating': round(avg_rating, 2),
                    'avg_sentiment': round(avg_sentiment, 2),
                    'sentiment_distribution': list(sentiment_dist),
                    'trends': trends,
                }
                
                logger.info(f"📊 Analytics generated: {total} reviews, avg rating: {avg_rating}, avg sentiment: {avg_sentiment}")
                logger.debug(f"📋 Analytics data: {analytics_data}")
                
                return Response(analytics_data)
                
            except Exception as e:
                logger.error(f"❌ Error generating analytics: {str(e)}", exc_info=True)
                return Response(
                    {'error': 'Failed to generate analytics'}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

    @action(detail=False, methods=['get'])
    def export(self, request):
        logger.info(f"📤 Export endpoint called by user: {request.user}")
        tenant = request.user.tenant
        
        with tenant_context(tenant):
            try:
                logger.debug("🔍 Fetching approved reviews for export")
                reviews = Review.objects.filter(tenant=tenant, is_approved=True).values(
                    'reviewer_email', 'rating', 'comment', 'submitted_at'
                )
                
                filename = f"reviews_{tenant.schema_name}_{timezone.now().date()}.csv"
                logger.info(f"💾 Generating CSV export: {filename} with {reviews.count()} reviews")
                
                response = HttpResponse(content_type='text/csv')
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                
                writer = csv.writer(response)
                writer.writerow(['Email', 'Rating', 'Comment', 'Submitted At'])
                writer.writerows(reviews)
                
                logger.info(f"✅ CSV export completed: {filename}")
                return response
                
            except Exception as e:
                logger.error(f"❌ Error generating export: {str(e)}", exc_info=True)
                return Response(
                    {'error': 'Failed to generate export'}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

    def list(self, request, *args, **kwargs):
        logger.debug(f"📋 List reviews called with params: {request.query_params}")
        response = super().list(request, *args, **kwargs)
        logger.debug(f"📋 Returning {len(response.data)} reviews in list response")
        return response

    def retrieve(self, request, *args, **kwargs):
        logger.debug(f"🔍 Retrieve review called for pk: {kwargs.get('pk')}")
        response = super().retrieve(request, *args, **kwargs)
        logger.debug(f"🔍 Returning review data for {kwargs.get('pk')}")
        return response

    def update(self, request, *args, **kwargs):
        logger.info(f"✏️ Update review called for pk: {kwargs.get('pk')} by user: {request.user}")
        response = super().update(request, *args, **kwargs)
        logger.info(f"✅ Review {kwargs.get('pk')} updated successfully")
        return response

    def destroy(self, request, *args, **kwargs):
        logger.warning(f"🗑️ Delete review called for pk: {kwargs.get('pk')} by user: {request.user}")
        response = super().destroy(request, *args, **kwargs)
        logger.warning(f"✅ Review {kwargs.get('pk')} deleted successfully")
        return response



class QRCodeViewSet(viewsets.ModelViewSet):
    queryset = QRCode.objects.all()
    serializer_class = QRCodeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        logger.debug(f"🔍 Getting QR codes for user: {self.request.user}, tenant: {self.request.user.tenant}")
        qs = self.queryset.filter(tenant=self.request.user.tenant, is_active=True)
        logger.debug(f"📊 Returning {qs.count()} active QR codes")
        return qs

    def create(self, request, *args, **kwargs):
        logger.info(f"🆕 Creating new QR code. User: {request.user}, Data: {request.data}")
        response = super().create(request, *args, **kwargs)
        logger.info(f"✅ QR code created successfully: {response.data.get('id')}")
        return response

    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        logger.info(f"📊 QR code stats called for pk: {pk} by user: {request.user}")
        qr = self.get_object()
        
        reviews_count = qr.reviews.filter(is_approved=True).count()
        avg_rating = qr.reviews.filter(is_approved=True).aggregate(Avg('rating'))['rating__avg'] or 0
        
        stats_data = {
            'actual_scan_count': qr.actual_scan_count,  # New: True scans (form loads)
            'scan_count': qr.scan_count,                # Existing: Approved reviews
            'reviews_count': reviews_count, 
            'conversion_rate': round((reviews_count / max(qr.actual_scan_count, 1)) * 100, 2) if qr.actual_scan_count > 0 else 0,  # % of scans leading to approved reviews
            'avg_rating': round(avg_rating, 2)
        }
        
        logger.info(f"📊 QR code {qr.unique_id} stats: {stats_data}")
        return Response(stats_data)

    def list(self, request, *args, **kwargs):
        logger.debug(f"📋 List QR codes called by user: {request.user}")
        response = super().list(request, *args, **kwargs)
        logger.debug(f"📋 Returning {len(response.data)} QR codes in list response")
        return response

    def retrieve(self, request, *args, **kwargs):
        logger.debug(f"🔍 Retrieve QR code called for pk: {kwargs.get('pk')}")
        response = super().retrieve(request, *args, **kwargs)
        logger.debug(f"🔍 Returning QR code data for {kwargs.get('pk')}")
        return response

    def update(self, request, *args, **kwargs):
        logger.info(f"✏️ Update QR code called for pk: {kwargs.get('pk')} by user: {request.user}")
        response = super().update(request, *args, **kwargs)
        logger.info(f"✅ QR code {kwargs.get('pk')} updated successfully")
        return response

    def destroy(self, request, *args, **kwargs):
        logger.warning(f"🗑️ Delete QR code called for pk: {kwargs.get('pk')} by user: {request.user}")
        # Soft delete by setting is_active to False
        instance = self.get_object()
        instance.is_active = False
        instance.save()
        logger.warning(f"✅ QR code {kwargs.get('pk')} soft deleted (is_active=False)")
        return Response(status=status.HTTP_204_NO_CONTENT)



class ReviewSettingsViewSet(viewsets.ModelViewSet):
    queryset = ReviewSettings.objects.all()
    serializer_class = ReviewSettingsSerializer
    permission_classes = [AllowAny]
    pagination_class = CustomPagination

    def get_queryset(self):
        logger.debug(f"🔍 Getting review settings for user: {self.request.user}, tenant: {self.request.user.tenant}")
        qs = self.queryset.filter(tenant=self.request.user.tenant)
        logger.debug(f"📊 Returning {qs.count()} review settings")
        return qs

    def retrieve(self, request, *args, **kwargs):
        logger.debug(f"🔍 Retrieve review settings called by user: {request.user}")
        response = super().retrieve(request, *args, **kwargs)
        logger.debug(f"🔍 Returning review settings for tenant: {request.user.tenant}")
        return response

    def update(self, request, *args, **kwargs):
        logger.info(f"✏️ Update review settings called by user: {request.user}, data: {request.data}")
        response = super().update(request, *args, **kwargs)
        logger.info(f"✅ Review settings updated successfully for tenant: {request.user.tenant}")
        return response

    def create(self, request, *args, **kwargs):
        logger.info(f"🆕 Create review settings called by user: {request.user}")
        # Typically settings are created automatically, but handle if needed
        response = super().create(request, *args, **kwargs)
        logger.info(f"✅ Review settings created successfully for tenant: {request.user.tenant}")
        return response