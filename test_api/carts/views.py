from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.utils import timezone
from django.db import IntegrityError
from .models import Cart, Wishlist, Coupon
from .serializers import CartSerializer, WishlistSerializer, CouponSerializer, get_tenant_id_from_jwt
from courses.views import StandardResultsPagination, TenantBaseView
import logging

logger = logging.getLogger('carts')

class CartViewSet(TenantBaseView, viewsets.ModelViewSet):
    serializer_class = CartSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Cart.objects.none()
        tenant_id = self.request.jwt_payload.get('tenant_unique_id')
        if not tenant_id:
            logger.error("No tenant_unique_id in JWT payload")
            raise serializers.ValidationError("Tenant ID not found in token.")
        user_id = self.request.jwt_payload.get('user', {}).get('id')
        if not user_id:
            logger.error("No user_id in JWT payload")
            raise serializers.ValidationError("User ID not found in token.")
        return Cart.objects.filter(tenant_id=tenant_id, user_id=user_id)

    def perform_create(self, serializer):
        serializer.save()

    def create(self, request, *args, **kwargs):
        tenant_id = request.jwt_payload.get('tenant_unique_id')
        try:
            response = super().create(request, *args, **kwargs)
            logger.info(f"[Tenant {tenant_id}] Cart item created for user {request.jwt_payload.get('user', {}).get('id')}")
            return response
        except IntegrityError:
            logger.warning(f"[Tenant {tenant_id}] Duplicate cart item attempted")
            return Response(
                {"detail": "This course is already in your cart."},
                status=status.HTTP_400_BAD_REQUEST
            )

class WishlistViewSet(TenantBaseView, viewsets.ModelViewSet):
    serializer_class = WishlistSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Wishlist.objects.none()
        tenant_id = self.request.jwt_payload.get('tenant_unique_id')
        if not tenant_id:
            logger.error("No tenant_unique_id in JWT payload")
            raise serializers.ValidationError("Tenant ID not found in token.")
        user_id = self.request.jwt_payload.get('user', {}).get('id')
        if not user_id:
            logger.error("No user_id in JWT payload")
            raise serializers.ValidationError("User ID not found in token.")
        return Wishlist.objects.filter(tenant_id=tenant_id, user_id=user_id)

    def perform_create(self, serializer):
        serializer.save()

    def create(self, request, *args, **kwargs):
        tenant_id = request.jwt_payload.get('tenant_unique_id')
        try:
            response = super().create(request, *args, **kwargs)
            logger.info(f"[Tenant {tenant_id}] Wishlist item created for user {request.jwt_payload.get('user', {}).get('id')}")
            return response
        except IntegrityError:
            logger.warning(f"[Tenant {tenant_id}] Duplicate wishlist item attempted")
            return Response(
                {"detail": "This course is already in your wishlist."},
                status=status.HTTP_400_BAD_REQUEST
            )

class CouponViewSet(TenantBaseView, viewsets.ModelViewSet):
    serializer_class = CouponSerializer
    permission_classes = [IsAdminUser]
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Coupon.objects.none()
        tenant_id = self.request.jwt_payload.get('tenant_unique_id')
        if not tenant_id:
            logger.error("No tenant_unique_id in JWT payload")
            raise serializers.ValidationError("Tenant ID not found in token.")
        return Coupon.objects.filter(tenant_id=tenant_id)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def apply_coupon(request):
    tenant_id = get_tenant_id_from_jwt(request)
    code = request.data.get('code')
    now = timezone.now()
    try:
        coupon = Coupon.objects.get(
            tenant_id=tenant_id,
            code=code,
            active=True,
            valid_from__lte=now,
            valid_to__gte=now
        )
        logger.info(f"[Tenant {tenant_id}] Coupon {code} applied successfully")
        return Response({'valid': True, 'discount_percent': coupon.discount_percent})
    except Coupon.DoesNotExist:
        logger.warning(f"[Tenant {tenant_id}] Invalid or expired coupon: {code}")
        return Response({'valid': False, 'error': 'Invalid or expired coupon.'}, status=status.HTTP_400_BAD_REQUEST)