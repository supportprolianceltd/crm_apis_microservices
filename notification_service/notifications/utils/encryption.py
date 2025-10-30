from cryptography.fernet import Fernet
from django.conf import settings
import base64

def generate_key():
    return Fernet.generate_key().decode()

def encrypt_data(data: str, key: bytes = None) -> str:
    if key is None:
        key = settings.ENCRYPTION_KEY.encode()  # Set in .env: ENCRYPTION_KEY=your_fernet_key
    f = Fernet(key)
    return f.encrypt(data.encode()).decode()

def decrypt_data(encrypted_data: str, key: bytes = None) -> str:
    if key is None:
        key = settings.ENCRYPTION_KEY.encode()
    f = Fernet(key)
    return f.decrypt(encrypted_data.encode()).decode()