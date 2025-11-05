# check_token.py
from rest_framework_simplejwt.tokens import AccessToken, TokenError
import sys
import json

# Paste your JWT token here
token_str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzU1OTc2MjQyLCJpYXQiOjE3NTU5NjkwNDIsImp0aSI6IjExZDgyZWZkYzc3NDRmYjk4ZjNlOTA1NWRhYmExZGEzIiwidXNlcl9pZCI6IjIiLCJ0ZW5hbnRfaWQiOjIsInRlbmFudF9zY2hlbWEiOiJwcm9saWFuY2UifQ.l-xIeOD7qd5m3MUx6ll91XKWgJFg9K2FbTsTNb74g5k"

try:
    # Try decoding as AccessToken
    token = AccessToken(token_str)
    print("✅ Token is valid as AccessToken!")
    print("Payload:")
    print(json.dumps(token.payload, indent=4))
except TokenError as e:
    print("❌ Token is INVALID!")
    print("Reason:", str(e))
    # Sometimes it could be expired, wrong type, etc.
    if hasattr(e, 'args') and e.args:
        print("Error details:", e.args[0])
