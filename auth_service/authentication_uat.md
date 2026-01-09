# Authentication System User Acceptance Testing (UAT)

## Overview
This document contains comprehensive User Acceptance Testing for the LUMINA Care OS Authentication Service. The system implements multi-tenant JWT authentication with OTP verification, cookie-based sessions, token refresh, account security features, and various user management capabilities.

## System Components
- **Multi-tenant Architecture**: Django-tenants with public and tenant-specific schemas
- **Authentication Methods**: Email/Username + Password + OTP (Email/Phone)
- **Token Management**: RSA-signed JWT tokens with refresh mechanism
- **Session Management**: HttpOnly cookies for secure token storage
- **Security Features**: Account locking, IP blocking, 2FA support, activity logging
- **External Integrations**: Kafka events, email notifications, SMS (planned)

## Test Environment Setup
- **Base URL**: `http://localhost:8001` (auth service)
- **Database**: PostgreSQL with tenant schemas
- **Redis**: For caching and session management
- **Kafka**: For event publishing
- **Frontend URLs**: Configured for development environment

## Test Data Prerequisites
1. Create test tenant with organizational ID
2. Create test users with different roles (admin, staff, investor, etc.)
3. Configure RSA key pairs for JWT signing
4. Set up email notification service
5. Ensure Kafka broker is running

## Authentication Endpoints
- `POST /api/login/` - Login with OTP request
- `POST /api/verify-otp/` - OTP verification and token issuance
- `POST /api/token/refresh/` - Refresh access token
- `GET /api/token/validate/` - Validate current token
- `POST /api/logout/` - Logout and blacklist tokens
- `GET /api/token/renew/` - Silent token renewal
- `POST /api/user/password/reset/` - Password reset request
- `POST /api/user/password/reset/confirm/` - Password reset confirmation

## Test Cases

### 1. Login with OTP Flow

#### TC-AUTH-001: Successful Login with Email OTP
**Test ID**: TC-AUTH-001
**Description**: Verify successful login flow with email OTP verification
**Preconditions**:
- Valid user account exists with email and password
- User has accepted terms
- Account is active and not locked
- Email notification service is configured

**Test Steps**:
1. Send POST request to `/api/login/` with valid email and password
2. Verify response contains `requires_otp: true` and user details
3. Check email is sent to user's email address
4. Send POST request to `/api/verify-otp/` with correct OTP code
5. Verify response contains access and refresh tokens
6. Check cookies are set in response (access_token, refresh_token)

**Expected Results**:
- Step 1: 200 OK, requires_otp=true, user_id and email returned
- Step 3: OTP email sent successfully
- Step 4: 200 OK, tokens returned, cookies set
- Step 6: HttpOnly cookies present in response headers

**Actual Results**:
**Pass/Fail**:
**Notes**:

#### TC-AUTH-002: Successful Login with Username OTP
**Test ID**: TC-AUTH-002
**Description**: Verify login using username instead of email
**Preconditions**:
- Valid user with username exists
- Username is indexed in UsernameIndex table

**Test Steps**:
1. POST `/api/login/` with username and password
2. Verify OTP sent to user's email
3. POST `/api/verify-otp/` with OTP code
4. Verify successful authentication

**Expected Results**:
- Username authentication works same as email
- OTP sent to correct email address

**Actual Results**:
**Pass/Fail**:
**Notes**:

#### TC-AUTH-003: Invalid Credentials Login Attempt
**Test ID**: TC-AUTH-003
**Description**: Verify system handles invalid login credentials
**Preconditions**:
- User account exists

**Test Steps**:
1. POST `/api/login/` with wrong password
2. Verify error response
3. Check UserActivity log records failed attempt

**Expected Results**:
- 400 Bad Request with "Invalid credentials" message
- No OTP sent
- Failed login activity logged

**Actual Results**:
**Pass/Fail**:
**Notes**:

#### TC-AUTH-004: Account Lock After Multiple Failed Attempts
**Test ID**: TC-AUTH-004
**Description**: Verify account locking after 5 failed login attempts
**Preconditions**:
- User account with login_attempts = 0

**Test Steps**:
1. Attempt login 5 times with wrong password
2. Verify account becomes locked
3. Attempt login with correct credentials
4. Verify login blocked due to locked account

**Expected Results**:
- After 5 failures: account status becomes locked
- Correct login attempt returns "Account is locked" error

**Actual Results**:
**Pass/Fail**:
**Notes**:

#### TC-AUTH-005: IP Blocking After Multiple Failed Attempts
**Test ID**: TC-AUTH-005
**Description**: Verify IP blocking functionality
**Preconditions**:
- Clean IP address (not blocked)

**Test Steps**:
1. Make multiple failed login attempts from same IP
2. Verify IP gets blocked
3. Attempt login from blocked IP
4. Verify "IP address blocked" error

**Expected Results**:
- IP blocked after threshold reached
- Subsequent requests from blocked IP rejected

**Actual Results**:
**Pass/Fail**:
**Notes**:

#### TC-AUTH-006: Remember Me Functionality
**Test ID**: TC-AUTH-006
**Description**: Verify extended token lifetime with remember_me
**Preconditions**:
- Valid user account

**Test Steps**:
1. Login with remember_me=true
2. Check refresh token expiry (should be 30 days)
3. Login with remember_me=false
4. Check refresh token expiry (should be 7 days)

**Expected Results**:
- remember_me=true: refresh token expires in 30 days
- remember_me=false: refresh token expires in 7 days

**Actual Results**:
**Pass/Fail**:
**Notes**:

### 2. Token Management

#### TC-AUTH-007: Token Refresh
**Test ID**: TC-AUTH-007
**Description**: Verify token refresh functionality
**Preconditions**:
- Valid refresh token in cookie

**Test Steps**:
1. POST `/api/token/refresh/` with valid refresh token
2. Verify new access and refresh tokens returned
3. Check old refresh token blacklisted
4. Verify new cookies set

**Expected Results**:
- 200 OK with new tokens
- Old refresh token in BlacklistedToken table
- New HttpOnly cookies set

**Actual Results**:
**Pass/Fail**:
**Notes**:

#### TC-AUTH-008: Token Validation
**Test ID**: TC-AUTH-008
**Description**: Verify token validation endpoint
**Preconditions**:
- Valid access token

**Test Steps**:
1. GET `/api/token/validate/` with valid token
2. Verify user data and tenant info returned
3. GET with invalid token
4. Verify 401 Unauthorized

**Expected Results**:
- Valid token: 200 OK with user/tenant data
- Invalid token: 401 Unauthorized

**Actual Results**:
**Pass/Fail**:
**Notes**:

#### TC-AUTH-009: Silent Token Renewal
**Test ID**: TC-AUTH-009
**Description**: Verify background token renewal
**Preconditions**:
- Valid refresh token in cookie

**Test Steps**:
1. GET `/api/token/renew/` with valid refresh token
2. Verify 204 No Content response
3. Check new tokens set in cookies
4. Verify old token blacklisted

**Expected Results**:
- 204 No Content (no JSON body)
- New cookies set silently
- Old refresh token blacklisted

**Actual Results**:
**Pass/Fail**:
**Notes**:

#### TC-AUTH-010: Expired Token Handling
**Test ID**: TC-AUTH-010
**Description**: Verify handling of expired tokens
**Preconditions**:
- Expired access token

**Test Steps**:
1. Use expired access token in request
2. Verify 401 Unauthorized response
3. Use expired refresh token
4. Verify refresh fails

**Expected Results**:
- Expired access token: 401 error
- Expired refresh token: refresh fails

**Actual Results**:
**Pass/Fail**:
**Notes**:

### 3. Logout Functionality

#### TC-AUTH-011: Successful Logout
**Test ID**: TC-AUTH-011
**Description**: Verify logout clears tokens and cookies
**Preconditions**:
- Authenticated user with valid tokens

**Test Steps**:
1. POST `/api/logout/` with valid refresh token
2. Verify 200 OK response
3. Check cookies deleted
4. Verify refresh token blacklisted
5. Attempt to use old tokens
6. Verify tokens no longer work

**Expected Results**:
- 200 OK response
- Cookies cleared (set to expired)
- Refresh token in BlacklistedToken table
- Old tokens invalid

**Actual Results**:
**Pass/Fail**:
**Notes**:

#### TC-AUTH-012: Logout with Invalid Token
**Test ID**: TC-AUTH-012
**Description**: Verify logout handles invalid tokens gracefully
**Preconditions**:
- Invalid or missing refresh token

**Test Steps**:
1. POST `/api/logout/` with invalid token
2. Verify appropriate error response

**Expected Results**:
- 400 Bad Request or 401 Unauthorized

**Actual Results**:
**Pass/Fail**:
**Notes**:

### 4. Password Reset Flow

#### TC-AUTH-013: Password Reset Request
**Test ID**: TC-AUTH-013
**Description**: Verify password reset request sends email
**Preconditions**:
- Valid user email

**Test Steps**:
1. POST `/api/user/password/reset/` with email
2. Verify reset token created
3. Check email sent with reset link

**Expected Results**:
- 200 OK response
- PasswordResetToken created
- Reset email sent

**Actual Results**:
**Pass/Fail**:
**Notes**:

#### TC-AUTH-014: Password Reset Confirmation
**Test ID**: TC-AUTH-014
**Description**: Verify password reset with valid token
**Preconditions**:
- Valid reset token

**Test Steps**:
1. POST `/api/user/password/reset/confirm/` with token and new password
2. Verify password updated
3. Attempt login with new password
4. Verify successful login

**Expected Results**:
- Password updated successfully
- Login with new password works
- Reset token marked as used

**Actual Results**:
**Pass/Fail**:
**Notes**:

#### TC-AUTH-015: Invalid Reset Token
**Test ID**: TC-AUTH-015
**Description**: Verify handling of invalid reset tokens
**Preconditions**:
- Invalid or expired reset token

**Test Steps**:
1. POST `/api/user/password/reset/confirm/` with invalid token
2. Verify error response

**Expected Results**:
- 400 Bad Request with appropriate error

**Actual Results**:
**Pass/Fail**:
**Notes**:

### 5. Multi-Tenancy Testing

#### TC-AUTH-016: Cross-Tenant Access Prevention
**Test ID**: TC-AUTH-016
**Description**: Verify users cannot access other tenants' data
**Preconditions**:
- Multiple tenants with users

**Test Steps**:
1. Login as user from tenant A
2. Attempt to access tenant B's resources
3. Verify access denied

**Expected Results**:
- 403 Forbidden or tenant mismatch error

**Actual Results**:
**Pass/Fail**:
**Notes**:

#### TC-AUTH-017: Tenant-Specific Token Validation
**Test ID**: TC-AUTH-017
**Description**: Verify tokens are tenant-specific
**Preconditions**:
- Tokens from different tenants

**Test Steps**:
1. Use tenant A token to access tenant B endpoint
2. Verify authentication fails

**Expected Results**:
- Token validation fails for wrong tenant

**Actual Results**:
**Pass/Fail**:
**Notes**:

### 6. Cookie Security

#### TC-AUTH-018: Cookie Attributes
**Test ID**: TC-AUTH-018
**Description**: Verify cookies have correct security attributes
**Preconditions**:
- Successful login

**Test Steps**:
1. Check cookie headers in login response
2. Verify HttpOnly, Secure, SameSite attributes

**Expected Results**:
- Development: HttpOnly=true, Secure=false, SameSite=Lax
- Production: HttpOnly=true, Secure=true, SameSite=None

**Actual Results**:
**Pass/Fail**:
**Notes**:

#### TC-AUTH-019: Cookie Domain Handling
**Test ID**: TC-AUTH-019
**Description**: Verify cookie domain settings for different environments
**Preconditions**:
- Different deployment environments

**Test Steps**:
1. Check cookie domain in development
2. Check cookie domain in production

**Expected Results**:
- Development: domain=None
- Production: domain set appropriately

**Actual Results**:
**Pass/Fail**:
**Notes**:

### 7. Error Scenarios

#### TC-AUTH-020: Suspended Account Login
**Test ID**: TC-AUTH-020
**Description**: Verify suspended accounts cannot login
**Preconditions**:
- User account with status='suspended'

**Test Steps**:
1. Attempt login with suspended account
2. Verify login blocked

**Expected Results**:
- "Account is locked or suspended" error

**Actual Results**:
**Pass/Fail**:
**Notes**:

#### TC-AUTH-021: OTP Code Expiration
**Test ID**: TC-AUTH-021
**Description**: Verify OTP codes expire after 5 minutes
**Preconditions**:
- OTP code generated

**Test Steps**:
1. Wait 5+ minutes after OTP generation
2. Attempt to verify expired OTP
3. Verify error response

**Expected Results**:
- "Invalid or expired OTP code" error

**Actual Results**:
**Pass/Fail**:
**Notes**:

#### TC-AUTH-022: Concurrent Login Sessions
**Test ID**: TC-AUTH-022
**Description**: Verify multiple concurrent sessions allowed
**Preconditions**:
- Valid user account

**Test Steps**:
1. Login from multiple browsers/devices
2. Verify all sessions work independently
3. Logout from one session
4. Verify other sessions still work

**Expected Results**:
- Multiple concurrent sessions allowed
- Logout affects only specific session

**Actual Results**:
**Pass/Fail**:
**Notes**:

### 8. Activity Logging

#### TC-AUTH-023: Login Activity Logging
**Test ID**: TC-AUTH-023
**Description**: Verify all login attempts are logged
**Preconditions**:
- User account

**Test Steps**:
1. Perform various login scenarios
2. Check UserActivity table for entries
3. Verify correct details logged

**Expected Results**:
- All authentication events logged with correct details

**Actual Results**:
**Pass/Fail**:
**Notes**:

#### TC-AUTH-024: Security Event Logging
**Test ID**: TC-AUTH-024
**Description**: Verify security events are logged to Kafka
**Preconditions**:
- Kafka broker running

**Test Steps**:
1. Perform security-related actions
2. Check Kafka topics for events
3. Verify event structure and data

**Expected Results**:
- Security events published to Kafka topics

**Actual Results**:
**Pass/Fail**:
**Notes**:

## Test Execution Summary

| Test Case ID | Description | Status | Tester | Date |
|-------------|-------------|--------|--------|------|
| TC-AUTH-001 | Successful Login with Email OTP | | | |
| TC-AUTH-002 | Successful Login with Username OTP | | | |
| TC-AUTH-003 | Invalid Credentials Login Attempt | | | |
| TC-AUTH-004 | Account Lock After Multiple Failed Attempts | | | |
| TC-AUTH-005 | IP Blocking After Multiple Failed Attempts | | | |
| TC-AUTH-006 | Remember Me Functionality | | | |
| TC-AUTH-007 | Token Refresh | | | |
| TC-AUTH-008 | Token Validation | | | |
| TC-AUTH-009 | Silent Token Renewal | | | |
| TC-AUTH-010 | Expired Token Handling | | | |
| TC-AUTH-011 | Successful Logout | | | |
| TC-AUTH-012 | Logout with Invalid Token | | | |
| TC-AUTH-013 | Password Reset Request | | | |
| TC-AUTH-014 | Password Reset Confirmation | | | |
| TC-AUTH-015 | Invalid Reset Token | | | |
| TC-AUTH-016 | Cross-Tenant Access Prevention | | | |
| TC-AUTH-017 | Tenant-Specific Token Validation | | | |
| TC-AUTH-018 | Cookie Attributes | | | |
| TC-AUTH-019 | Cookie Domain Handling | | | |
| TC-AUTH-020 | Suspended Account Login | | | |
| TC-AUTH-021 | OTP Code Expiration | | | |
| TC-AUTH-022 | Concurrent Login Sessions | | | |
| TC-AUTH-023 | Login Activity Logging | | | |
| TC-AUTH-024 | Security Event Logging | | | |

## UAT Sign-Off

**Tested By**: ___________________________ **Date**: ____________

**Approved By**: ___________________________ **Date**: ____________

**Comments/Issues Found**:
_______________________________________________________________
_______________________________________________________________
_______________________________________________________________

## Appendix A: API Reference

### Login Request
```json
POST /api/login/
{
  "email": "user@example.com",
  "password": "password123",
  "remember_me": false,
  "otp_method": "email"
}
```

### OTP Verification
```json
POST /api/verify-otp/
{
  "email": "user@example.com",
  "otp_code": "123456"
}
```

### Token Refresh
```json
POST /api/token/refresh/
{
  "refresh": "refresh_token_here"
}
```

## Appendix B: Test Data

### Test Users
- Admin User: admin@tenant.com / password123
- Staff User: staff@tenant.com / password123
- Investor User: investor@tenant.com / password123

### Test Tenants
- Primary Tenant: organizational_id = "TENANT001"
- Secondary Tenant: organizational_id = "TENANT002"

## Appendix C: Environment Configuration

### Development Settings
- DEBUG = True
- COOKIE_SECURE = False
- CORS_ALLOWED_ORIGINS = localhost URLs

### Production Settings
- DEBUG = False
- COOKIE_SECURE = True
- CORS_ALLOWED_ORIGINS = production domains