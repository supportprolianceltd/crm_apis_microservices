from datetime import timedelta
from .models import UserSession

def get_daily_usage(user, date):
    sessions = UserSession.objects.filter(user=user, date=date)
    total = timedelta()
    for session in sessions:
        if session.duration:
            total += session.duration
    return total