from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from users.models import BlacklistedToken, RSAKeyPair
from core.models import Tenant
import jwt
import datetime
from jwt import InvalidTokenError, ExpiredSignatureError, InvalidSignatureError

DEFAULT_ALGORITHM = "RS256"
DEFAULT_EXP_SECONDS = 3600  # 1 hour

def generate_rsa_keypair(key_size: int = 2048):
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size
    )
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()  # Use encryption in production!
    ).decode('utf-8')
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode('utf-8')
    return private_pem, public_pem

def create_and_store_keypair(tenant: Tenant, key_size: int = 2048, active: bool = True) -> RSAKeyPair:
    priv, pub = generate_rsa_keypair(key_size)
    kp = RSAKeyPair.objects.create(
        tenant=tenant,
        private_key_pem=priv,
        public_key_pem=pub,
        active=active
    )
    return kp

def issue_rsa_jwt(payload: dict, tenant: Tenant, exp_seconds: int = None):
    """
    Signs payload with the tenant's active private RSA key.
    """
    if exp_seconds is None:
        exp_seconds = DEFAULT_EXP_SECONDS
    keypair = RSAKeyPair.objects.filter(tenant=tenant, active=True).order_by('-created_at').first()
    if not keypair:
        raise RuntimeError("No active RSA keypair available for tenant")
    now = datetime.datetime.utcnow()
    claims = payload.copy()
    claims.setdefault('iat', now)
    claims.setdefault('exp', now + datetime.timedelta(seconds=exp_seconds))
    claims.setdefault('tenant_id', tenant.id)
    token = jwt.encode(
        claims,
        keypair.private_key_pem,
        algorithm=DEFAULT_ALGORITHM,
        headers={'kid': keypair.kid}
    )
    return token

def get_keypair_by_kid_and_tenant(kid: str, tenant: Tenant) -> RSAKeyPair | None:
    try:
        return RSAKeyPair.objects.get(kid=kid, tenant=tenant)
    except RSAKeyPair.DoesNotExist:
        return None

def validate_rsa_jwt(token: str):
    """
    Validates JWT by looking up the public key via kid and tenant_id.
    Returns decoded claims on success, raises jwt.InvalidTokenError on failure.
    """
    try:
        unverified_header = jwt.get_unverified_header(token)
    except jwt.InvalidTokenError as e:
        raise InvalidTokenError("Malformed token header") from e
    kid = unverified_header.get('kid')
    if not kid:
        raise InvalidTokenError("No 'kid' header present")
    # Decode payload without verification to get tenant_id
    unverified_payload = jwt.decode(token, options={"verify_signature": False})
    tenant_id = unverified_payload.get('tenant_id')
    if not tenant_id:
        raise InvalidTokenError("No tenant_id in token payload")
    from core.models import Tenant
    try:
        tenant = Tenant.objects.get(id=tenant_id)
    except Tenant.DoesNotExist:
        raise InvalidTokenError("Unknown tenant_id")
    keypair = get_keypair_by_kid_and_tenant(kid, tenant)
    if not keypair:
        raise InvalidTokenError("Unknown 'kid' for tenant")
    public_key = keypair.public_key_pem
    try:
        decoded = jwt.decode(
            token,
            public_key,
            algorithms=[DEFAULT_ALGORITHM],
            options={"verify_aud": False}
        )
        return decoded
    except ExpiredSignatureError:
        raise
    except InvalidSignatureError:
        raise
    except InvalidTokenError:
        raise

def decode_rsa_jwt(token):
    unverified_header = jwt.get_unverified_header(token)
    kid = unverified_header.get("kid")
    if not kid:
        raise Exception("No kid in JWT header")
    keypair = RSAKeyPair.objects.filter(kid=kid, active=True).first()
    if not keypair:
        raise Exception("No matching RSA keypair found")
    public_key = keypair.public_key_pem
    payload = jwt.decode(token, public_key, algorithms=["RS256"])
    return payload


def blacklist_refresh_token(refresh_token):
    payload = decode_rsa_jwt(refresh_token)
    jti = payload.get("jti")
    exp = datetime.fromtimestamp(payload["exp"])
    BlacklistedToken.objects.create(jti=jti, expires_at=exp)


