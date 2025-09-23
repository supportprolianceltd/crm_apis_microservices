from django.db import models
from django.utils import timezone
import logging
from activitylog.models import ActivityLog

logger = logging.getLogger('carts')

class Cart(models.Model):
    id = models.AutoField(primary_key=True)
    tenant_id = models.CharField(max_length=36, blank=False, null=False)  # Store Tenant ID
    tenant_name = models.CharField(max_length=255, blank=True, null=True, help_text="Tenant name for reference")
    user_id = models.CharField(max_length=36, blank=False, null=False)  # Store User ID from auth-service
    course_id = models.CharField(max_length=36, blank=False, null=False)  # Store Course ID
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('tenant_id', 'user_id', 'course_id')
        indexes = [
            models.Index(fields=['tenant_id', 'user_id'], name='idx_cart_tenant_user'),
            models.Index(fields=['course_id'], name='idx_cart_course'),
        ]

    def __str__(self):
        return f"Cart {self.id} for user {self.user_id} (Tenant: {self.tenant_id})"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        activity_type = 'cart_created' if is_new else 'cart_updated'
        ActivityLog.objects.create(
            tenant_id=self.tenant_id,
            tenant_name=self.tenant_name,
            user_id=self.user_id,
            activity_type=activity_type,
            details=f"Cart item for course {self.course_id} {'created' if is_new else 'updated'}",
            status='success'
        )
        logger.info(f"Cart {self.id} {'created' if is_new else 'updated'} for tenant {self.tenant_id} by user {self.user_id}")

    def delete(self, *args, **kwargs):
        ActivityLog.objects.create(
            tenant_id=self.tenant_id,
            tenant_name=self.tenant_name,
            user_id=self.user_id,
            activity_type='cart_deleted',
            details=f"Cart item for course {self.course_id} deleted",
            status='success'
        )
        logger.info(f"Cart {self.id} deleted for tenant {self.tenant_id} by user {self.user_id}")
        super().delete(*args, **kwargs)

class Wishlist(models.Model):
    id = models.AutoField(primary_key=True)
    tenant_id = models.CharField(max_length=36, blank=False, null=False)  # Store Tenant ID
    tenant_name = models.CharField(max_length=255, blank=True, null=True, help_text="Tenant name for reference")
    user_id = models.CharField(max_length=36, blank=False, null=False)  # Store User ID from auth-service
    course_id = models.CharField(max_length=36, blank=False, null=False)  # Store Course ID
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('tenant_id', 'user_id', 'course_id')
        indexes = [
            models.Index(fields=['tenant_id', 'user_id'], name='idx_wishlist_tenant_user'),
            models.Index(fields=['course_id'], name='idx_wishlist_course'),
        ]

    def __str__(self):
        return f"Wishlist {self.id} for user {self.user_id} (Tenant: {self.tenant_id})"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        activity_type = 'wishlist_created' if is_new else 'wishlist_updated'
        ActivityLog.objects.create(
            tenant_id=self.tenant_id,
            tenant_name=self.tenant_name,
            user_id=self.user_id,
            activity_type=activity_type,
            details=f"Wishlist item for course {self.course_id} {'created' if is_new else 'updated'}",
            status='success'
        )
        logger.info(f"Wishlist {self.id} {'created' if is_new else 'updated'} for tenant {self.tenant_id} by user {self.user_id}")

    def delete(self, *args, **kwargs):
        ActivityLog.objects.create(
            tenant_id=self.tenant_id,
            tenant_name=self.tenant_name,
            user_id=self.user_id,
            activity_type='wishlist_deleted',
            details=f"Wishlist item for course {self.course_id} deleted",
            status='success'
        )
        logger.info(f"Wishlist {self.id} deleted for tenant {self.tenant_id} by user {self.user_id}")
        super().delete(*args, **kwargs)

class Coupon(models.Model):
    id = models.AutoField(primary_key=True)
    tenant_id = models.CharField(max_length=36, blank=False, null=False)  # Store Tenant ID
    tenant_name = models.CharField(max_length=255, blank=True, null=True, help_text="Tenant name for reference")
    code = models.CharField(max_length=32, unique=True)
    discount_percent = models.PositiveIntegerField()
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()
    active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=['tenant_id', 'code'], name='idx_coupon_tenant_code'),
            models.Index(fields=['valid_from', 'valid_to'], name='idx_coupon_validity'),
        ]

    def __str__(self):
        return f"{self.code} (Tenant: {self.tenant_id})"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        activity_type = 'coupon_created' if is_new else 'coupon_updated'
        ActivityLog.objects.create(
            tenant_id=self.tenant_id,
            tenant_name=self.tenant_name,
            user_id=None,  # Coupons may be created by admins, user_id can be added if needed
            activity_type=activity_type,
            details=f"Coupon {self.code} {'created' if is_new else 'updated'}",
            status='success'
        )
        logger.info(f"Coupon {self.id} {'created' if is_new else 'updated'} for tenant {self.tenant_id}")

    def delete(self, *args, **kwargs):
        ActivityLog.objects.create(
            tenant_id=self.tenant_id,
            tenant_name=self.tenant_name,
            user_id=None,
            activity_type='coupon_deleted',
            details=f"Coupon {self.code} deleted",
            status='success'
        )
        logger.info(f"Coupon {self.id} deleted for tenant {self.tenant_id}")
        super().delete(*args, **kwargs)