from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ReviewViewSet, QRCodeViewSet, ReviewSettingsViewSet, qr_submit_view  # Added: Import the new qr_submit_view

router = DefaultRouter()
router.register(r'reviews', ReviewViewSet, basename='reviews')
router.register(r'qrcodes', QRCodeViewSet, basename='qrcodes')
router.register(r'settings', ReviewSettingsViewSet, basename='review-settings')

urlpatterns = [
    path('', include(router.urls)),
    # Public submission (no auth)
    path('public/submit/', ReviewViewSet.as_view({'post': 'create'}), name='public_review_submit'),
    # New: QR scan handler (GET for form load/increment actual_scan_count)
    path('submit/', qr_submit_view, name='qr_submit'),  # Handles /submit/?token=... for scans
]

# Add explicit routes for custom actions to ensure they're accessible
urlpatterns += [
    path('reviews/analytics/', ReviewViewSet.as_view({'get': 'analytics'}), name='reviews-analytics'),
    path('reviews/export/', ReviewViewSet.as_view({'get': 'export'}), name='reviews-export'),
    path('reviews/<uuid:pk>/approve/', ReviewViewSet.as_view({'post': 'approve'}), name='review-approve'),
]