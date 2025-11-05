import qrcode
from PIL import Image
from io import BytesIO
from django.conf import settings
from django.core.files.base import ContentFile
from .models import Tenant  # Or import dynamically

def generate_review_qr(tenant_slug: str, size: tuple = (200, 200)) -> str:
    """Generate QR code for tenant's review page. Returns media URL."""
    review_url = f"{settings.WEB_PAGE_URL}/reviews/{tenant_slug}/submit"  # Frontend route
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(review_url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    img = img.resize(size)
    
    # Save to media (or upload to Supabase)
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    file_content = ContentFile(buffer.getvalue(), name=f"qr_{tenant_slug}.png")
    
    # Example: Save to Tenant model extension if needed, or return base64 for API
    from django.core.files.storage import default_storage
    qr_path = default_storage.save(f"qrs/{tenant_slug}.png", file_content)
    return default_storage.url(qr_path)