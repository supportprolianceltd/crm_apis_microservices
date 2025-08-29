from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from django.utils import timezone
from .models import UserSession

@receiver(user_logged_in)
def create_user_session(sender, request, user, **kwargs):
    ip = request.META.get('REMOTE_ADDR')
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    UserSession.objects.create(
        user=user,
        login_time=timezone.now(),
        date=timezone.now().date(),
        ip_address=ip,
        user_agent=user_agent
    )

@receiver(user_logged_out)
def close_user_session(sender, request, user, **kwargs):
    try:
        session = UserSession.objects.filter(user=user, logout_time__isnull=True).latest('login_time')
        session.logout_time = timezone.now()
        session.save()
    except UserSession.DoesNotExist:
        pass