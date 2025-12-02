# OTP-Based Login System Documentation

## Overview

This document describes the enterprise-grade OTP (One-Time Password) login system implemented for the CRM application. The system provides secure, multi-channel authentication with user preferences and flexible override options.

## Architecture

The system consists of:
- **JWT-based authentication** with RSA-signed tokens
- **OTP delivery** via email or SMS
- **User preferences** stored in profile
- **Multi-tenant support** with schema isolation
- **Activity logging** for audit trails

## Authentication Flow

```
1. User submits credentials + optional OTP method
2. System validates credentials
3. System determines OTP delivery method (profile preference or override)
4. OTP sent to user via chosen channel
5. User submits OTP for verification
6. System issues JWT tokens upon successful verification
```

---

## API Endpoints

### 1. Initiate Login (OTP Request)

**Endpoint:** `POST /api/token/`

**Purpose:** Authenticate user credentials and initiate OTP verification process.

**Authentication:** None required

**Request Payload:**
```json
{
  "email": "user@company.com",
  "password": "string",
  "remember_me": false,
  "otp_method": "email"  // Optional: "email" or "phone"
}
```

**Parameters:**
- `email` (string, required): User's email address
- `password` (string, required): User's password
- `remember_me` (boolean, optional): Extend token validity to 30 days
- `otp_method` (string, optional): Override user's preferred OTP method

**Success Response (OTP Required):**
```json
{
  "requires_otp": true,
  "user_id": 123,
  "email": "user@company.com",
  "otp_method": "email",
  "message": "OTP sent to your email. Please verify to complete login."
}
```

**Error Responses:**
```json
// Invalid credentials
{
  "non_field_errors": ["Invalid credentials"]
}

// No phone number for SMS
{
  "non_field_errors": ["No phone number found. Please add a work phone number to your profile or use email verification."]
}

// Account issues
{
  "non_field_errors": ["Account is locked or suspended"]
}
```

---

### 2. Verify OTP

**Endpoint:** `POST /api/verify-otp/`

**Purpose:** Verify the OTP code and complete the login process.

**Authentication:** None required

**Request Payload:**
```json
{
  "email": "user@company.com",
  "otp_code": "123456"
}
```

**Parameters:**
- `email` (string, required): User's email address
- `otp_code` (string, required): 6-digit OTP code

**Success Response:**
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9...",
  "tenant_id": "uuid",
  "tenant_organizational_id": "string",
  "tenant_name": "Company Name",
  "tenant_unique_id": "uuid",
  "tenant_primary_color": "#hex",
  "tenant_secondary_color": "#hex",
  "tenant_schema": "schema_name",
  "tenant_domain": "domain.com",
  "user": {
    "id": 123,
    "email": "user@company.com",
    "first_name": "John",
    "last_name": "Doe",
    "username": "johndoe",
    "role": "user",
    "user_type": "tenant"
  },
  "has_accepted_terms": true,
  "remember_me": false
}
```

**Error Responses:**
```json
// Invalid or expired OTP
{
  "detail": "Invalid or expired OTP code."
}

// User not found
{
  "detail": "Invalid user."
}
```

---

### 3. Refresh Token

**Endpoint:** `POST /api/token/refresh/`

**Purpose:** Obtain new access token using refresh token.

**Authentication:** None required (reads from cookies)

**Request Payload:**
```json
{
  "refresh": "refresh_token_here"  // Optional, reads from cookies
}
```

**Success Response:** Same as login success response

---

### 4. Silent Token Renewal

**Endpoint:** `GET /api/token/renew/`

**Purpose:** Silently renew tokens before expiration (used by frontend).

**Authentication:** Valid refresh token in cookies

**Request Payload:** None

**Response:** 204 No Content (sets new cookies)

---

### 5. Token Validation

**Endpoint:** `GET /api/token/validate/`

**Purpose:** Validate current access token and return user info.

**Authentication:** Valid access token required

**Success Response:**
```json
{
  "status": "success",
  "user": {
    // Full user object
  },
  "tenant_id": "uuid",
  "tenant_organizational_id": "string",
  "tenant_name": "Company Name",
  "tenant_unique_id": "uuid",
  "tenant_schema": "schema_name"
}
```

---

### 6. Logout

**Endpoint:** `POST /api/logout/`

**Purpose:** Invalidate refresh token and clear authentication cookies.

**Authentication:** Valid refresh token

**Success Response:**
```json
{
  "detail": "Logged out successfully."
}
```

---

## User Profile Management

### OTP Preferences

Users can set their preferred OTP delivery method in their profile:

```python
class UserProfile(models.Model):
    # ... other fields ...
    preferred_otp_method = models.CharField(
        max_length=10,
        choices=[('email', 'Email'), ('phone', 'Phone')],
        default='email',
        help_text="User's preferred method for receiving OTP codes"
    )
    work_phone = models.CharField(max_length=20, blank=True)
    # ... other fields ...
```

**Setting Preferences:**
- Default: `email`
- Can be updated via user profile API
- Requires phone number for SMS option

---

## Notification System Integration

### Email OTP Payload
```json
{
  "data": {
    "user_email": "user@company.com",
    "2fa_code": "123456",
    "2fa_method": "email",
    "ip_address": "192.168.1.1",
    "user_agent": "Mozilla/5.0...",
    "login_method": "email",
    "remember_me": false,
    "expires_in_seconds": 300
  },
  "metadata": {
    "event_id": "evt-uuid",
    "event_type": "auth.2fa.code.requested",
    "created_at": "2025-12-02T07:54:00.000Z",
    "source": "auth-service",
    "tenant_id": "tenant-uuid"
  }
}
```

### SMS OTP Payload (When Implemented)
```json
{
  "data": {
    "phone_number": "+1234567890",
    "2fa_code": "123456",
    "2fa_method": "sms",
    "ip_address": "192.168.1.1",
    "user_agent": "Mozilla/5.0...",
    "login_method": "email",
    "remember_me": false,
    "expires_in_seconds": 300
  },
  "metadata": {
    "event_id": "evt-uuid",
    "event_type": "auth.2fa.code.requested",
    "created_at": "2025-12-02T07:54:00.000Z",
    "source": "auth-service",
    "tenant_id": "tenant-uuid"
  }
}
```

---

## Security Features

### Token Security
- **RSA-signed JWTs** with kid headers
- **HttpOnly cookies** for token storage
- **Secure/SameSite** cookie attributes
- **Token blacklisting** on logout/refresh
- **72-hour access token** expiration

### OTP Security
- **6-digit numeric codes**
- **5-minute expiration**
- **Single-use** (cleared after verification)
- **Rate limiting** via activity logging
- **IP-based blocking** support

### Multi-Tenant Security
- **Schema isolation** per tenant
- **Tenant-specific keys** for JWT signing
- **Domain-based routing**
- **Tenant suspension** support

---

## Best Practices

### For Administrators

1. **User Onboarding:**
   - Set appropriate OTP preferences during user creation
   - Ensure phone numbers are collected for SMS users
   - Communicate security policies clearly

2. **Security Monitoring:**
   - Monitor failed login attempts
   - Review OTP delivery logs
   - Set up alerts for suspicious activity

3. **Token Management:**
   - Configure appropriate token lifetimes
   - Implement token rotation policies
   - Monitor for token abuse

### For Developers

1. **Frontend Integration:**
   ```javascript
   // Login flow
   const login = async (credentials) => {
     const response = await fetch('/api/token/', {
       method: 'POST',
       headers: { 'Content-Type': 'application/json' },
       body: JSON.stringify(credentials)
     });

     if (response.data.requires_otp) {
       // Show OTP input form
       const otpResponse = await verifyOTP(email, otpCode);
       // Handle success
     }
   };
   ```

2. **Error Handling:**
   - Handle network errors gracefully
   - Provide clear user feedback
   - Implement retry mechanisms

3. **Token Management:**
   - Store tokens securely (HttpOnly cookies preferred)
   - Implement automatic token renewal
   - Handle token expiration properly

### For Users

1. **OTP Method Selection:**
   - Choose preferred method in profile settings
   - Keep contact information updated
   - Use email as fallback for SMS issues

2. **Security Awareness:**
   - Never share OTP codes
   - Report suspicious activity
   - Use strong passwords

---

## Configuration

### Environment Variables
```bash
# Notification service
NOTIFICATIONS_SERVICE_URL=http://notifications:8000/events/

# SMS service (when implemented)
SMS_SERVICE_URL=http://sms-service:8000/send-otp/

# JWT settings
JWT_ACCESS_TOKEN_LIFETIME=4320  # minutes (72 hours)
JWT_REFRESH_TOKEN_LIFETIME=7    # days (30 if remember_me)
```

### Database Migrations
```bash
# Add preferred_otp_method to UserProfile
python manage.py makemigrations users
python manage.py migrate
```

---

## Monitoring & Logging

### Activity Types Logged
- `login` - Successful/failed login attempts
- `login_failed` - Authentication failures
- `logout` - User logout
- `refresh_token` - Token refresh
- `silent_renew` - Automatic token renewal

### Key Metrics to Monitor
- OTP delivery success rate
- Login success/failure rates
- Token refresh frequency
- Geographic login patterns
- Device/user agent analysis

---

## Troubleshooting

### Common Issues

1. **"Token has expired"**
   - Check middleware configuration
   - Ensure `/api/verify-otp/` is in public paths
   - Verify tenant resolution

2. **OTP not received**
   - Check notification service logs
   - Verify user contact information
   - Check spam/junk folders for email

3. **Invalid OTP**
   - Verify code expiration (5 minutes)
   - Check for typos in code entry
   - Ensure single-use (codes are cleared after use)

### Debug Commands
```bash
# Check OTP in logs
grep "OTP generated" auth_service/logs/*.log

# Verify tenant setup
python manage.py shell -c "from core.models import Tenant; print(Tenant.objects.all())"

# Test notification service
curl -X POST http://notifications:8000/events/ -H "Content-Type: application/json" -d @test_payload.json
```

---

## Future Enhancements

1. **SMS Integration:** Implement actual SMS sending via Twilio/AWS SNS
2. **OTP Apps:** Support for authenticator apps (TOTP)
3. **Biometric:** Integration with device biometrics
4. **Magic Links:** Email-based login links
5. **Step-up Auth:** Require additional verification for sensitive operations

---

*This documentation covers the complete OTP login system implementation. For additional support or questions, please refer to the codebase or contact the development team.*