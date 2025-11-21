import requests
from django.conf import settings
from functools import lru_cache

class AuthServiceError(Exception):
    pass

@lru_cache(maxsize=128)
def get_user_details(user_id, token):
    """Get user details from auth-service with caching"""
    headers = {'Authorization': f'Bearer {token}'}
    try:
        resp = requests.get(
            f'{settings.AUTH_SERVICE_URL}/api/users/{user_id}/',
            headers=headers,
            timeout=5
        )
        if resp.status_code == 200:
            data = resp.json()
            return {
                'id': str(data.get('id') or data.get('pk') or data.get('kid')),
                'first_name': data.get('first_name') or '',
                'last_name': data.get('last_name') or '',
                'email': data.get('email') or '',
            }
        return None
    except requests.exceptions.RequestException:
        return None

def get_user_from_token(token):
    """Get current user details from token"""
    headers = {'Authorization': f'Bearer {token}'}
    try:
        resp = requests.get(
            f'{settings.AUTH_SERVICE_URL}/api/users/me/',
            headers=headers,
            timeout=5
        )
        if resp.status_code == 200:
            data = resp.json()
            return {
                'id': str(data.get('id') or data.get('pk') or data.get('kid')),
                'first_name': data.get('first_name') or '',
                'last_name': data.get('last_name') or '',
                'email': data.get('email') or '',
            }
        return None
    except requests.exceptions.RequestException:
        return None

def verify_token(token):
    """Verify token with auth-service"""
    headers = {'Authorization': f'Bearer {token}'}
    try:
        resp = requests.get(
            f'{settings.AUTH_SERVICE_URL}/api/users/me/',
            headers=headers,
            timeout=5
        )
        return resp.status_code == 200
    except requests.exceptions.RequestException:
        return False