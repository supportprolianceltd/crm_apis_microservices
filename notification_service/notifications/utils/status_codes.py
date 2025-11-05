# HTTP-like codes for notifications
SUCCESS = 200
PENDING = 202
FAILED = 500
RETRY = 502

# Failure categories (matching enum)
FAILURE_CODES = {
    'auth_error': 401,
    'network_error': 503,
    'provider_error': 502,
    'content_error': 400,
    'unknown_error': 500,
}