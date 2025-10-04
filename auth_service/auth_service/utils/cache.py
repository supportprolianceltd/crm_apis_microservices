import hashlib
from django.conf import settings
from django.core.cache import cache
from django_redis import get_redis_connection
import logging

logger = logging.getLogger(__name__)

def get_cache_key(tenant_schema, entity, identifier=None, version='v1'):
    """
    Generate tenant-isolated cache key.
    e.g., get_cache_key('example_user', 'customuser', 'user_123') -> 'authservice:v1:tenant:example_user:customuser:user_123'
    """
    base = f"{settings.CACHES['default']['KEY_PREFIX']}{settings.TENANT_CACHE_PREFIX.format(tenant_schema)}{entity}"
    if identifier:
        # Hash long IDs for brevity
        if len(identifier) > 32:
            identifier = hashlib.sha256(identifier.encode()).hexdigest()[:16]
        base += f":{identifier}"
    return f"{base}:{version}"

def get_from_cache(key, default=None, timeout=None):
    """Cache get with logging."""
    if not settings.CACHE_ENABLED:
        return default
    value = cache.get(key)
    if value is None:
        logger.debug(f"Cache miss for key: {key}")
    else:
        logger.debug(f"Cache hit for key: {key}")
    return value

def set_to_cache(key, value, timeout=None):
    """Cache set with logging."""
    if not settings.CACHE_ENABLED:
        return
    cache.set(key, value, timeout)
    logger.debug(f"Cache set for key: {key}, TTL: {timeout}")

def delete_cache_key(key):
    """Delete specific key."""
    if not settings.CACHE_ENABLED:
        return
    cache.delete(key)
    logger.debug(f"Cache deleted for key: {key}")

def delete_tenant_cache(tenant_schema, entity=None):
    """Bulk delete tenant keys (pattern-based)."""
    if not settings.CACHE_ENABLED:
        return
    prefix = get_cache_key(tenant_schema, entity or '', version='')
    # Use Redis pipeline for efficiency (direct via django-redis)
    
    r = get_redis_connection('default')
    keys = r.keys(f"{prefix}*")
    if keys:
        r.delete(*keys)
        logger.info(f"Deleted {len(keys)} cache keys for tenant {tenant_schema}:{entity}")