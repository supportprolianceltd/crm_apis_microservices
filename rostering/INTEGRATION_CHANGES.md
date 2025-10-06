# Auth Service Integration & Notification Service Changes

This document outlines the comprehensive changes made to integrate with the existing auth service and notification microservice, removing manual carer management and centralizing email configurations.

## Overview

- **Auth Service Integration**: Carers are now synced from the auth service instead of being created manually
- **Notification Service**: All notifications now use the external notification microservice at `http://notify/events`
- **Database Email Configuration**: Email settings are now stored per-tenant in the database instead of environment variables
- **Read-Only Carer Management**: Carer controller is now read-only; all updates come from auth service sync

## Database Schema Changes

### New Model: TenantEmailConfig
```prisma
model TenantEmailConfig {
  id            String   @id @default(cuid())
  tenantId      String   @unique
  imapHost      String
  imapPort      Int      @default(993)
  imapUser      String
  imapPassword  String   // Encrypted
  imapTls       Boolean  @default(true)
  pollInterval  Int      @default(300) // seconds
  isActive      Boolean  @default(true)
  lastChecked   DateTime?
  lastError     String?
  createdAt     DateTime @default(now())
  updatedAt     DateTime @updatedAt
}
```

### Updated Carer Model
- **Added**: `authUserId` field to reference auth service user
- **Removed**: All notification preference fields (handled by notification service)

## New Services Created

### 1. AuthSyncService (`src/services/auth-sync.service.ts`)
- Syncs carer data from auth service to local database
- Handles geocoding of addresses during sync
- Provides bulk sync and individual carer sync methods
- Validates carer data and handles conflicts

**Key Methods**:
- `syncCarersFromAuthService(tenantId, authToken)` - Bulk sync all carers
- `syncSingleCarer(carerId, tenantId, authToken)` - Sync individual carer
- `getCarerSyncStatus(tenantId, authToken)` - Get sync statistics

### 2. NotificationService (`src/services/notification.service.ts`)
- Interfaces with external notification microservice at `http://notify/events`
- Replaces all local email/SMS notification handling
- Standardized notification payload format

**Key Methods**:
- `notifyCarerMatch(matchData)` - Notify carer of new match
- `notifyRequestAssigned(assignmentData)` - Notify about assignment
- `notifyUrgentRequest(requestData)` - Urgent request notifications
- `sendTestNotification(email, tenantId)` - Test notification endpoint

### 3. TenantEmailConfigService (`src/services/tenant-email-config.service.ts`)
- Manages tenant-specific email configurations in database
- Encrypts/decrypts email passwords for security
- Provides email connection testing

**Key Methods**:
- `upsertTenantEmailConfig(tenantId, config)` - Create/update config
- `getTenantEmailConfig(tenantId)` - Get tenant configuration
- `testEmailConnection(tenantId)` - Test IMAP connection
- `deleteTenantEmailConfig(tenantId)` - Remove configuration

## Updated Services

### EmailService
- **Before**: Used environment variables for SMTP/IMAP configuration
- **After**: Uses TenantEmailConfigService for database-stored configurations
- Enhanced with per-tenant email settings and notification service integration

### EmailWorker
- Updated to use new tenant-based email configuration approach
- Integrates with NotificationService for sending notifications

## Updated Controllers

### CarerController
- **Before**: Full CRUD operations for manual carer management
- **After**: Read-only operations (get, search, availability)
- **Removed Methods**: createCarer, updateCarer, deleteCarer, toggleCarerStatus
- **Remaining Methods**: getCarer, searchCarers, getCarerAvailability

## New API Routes

### Sync Routes (`/api/v1/sync/`)
- `POST /sync-carers` - Trigger bulk carer sync from auth service
- `GET /sync-status` - Get carer sync status and statistics
- `POST /sync-carer/:carerId` - Sync individual carer
- `PUT /email-config` - Create/update tenant email configuration
- `GET /email-config` - Get tenant email configuration
- `POST /test-email` - Test email connection
- `DELETE /email-config` - Delete email configuration
- `POST /test-notification` - Send test notification

## Environment Variable Changes

### Removed (now database-configured per tenant):
- `SMTP_HOST`
- `SMTP_PORT` 
- `SMTP_USER`
- `SMTP_PASSWORD`
- `SMTP_FROM_EMAIL`
- `SMTP_FROM_NAME`
- `IMAP_HOST`
- `IMAP_PORT`
- `IMAP_USER`
- `IMAP_PASSWORD`

### Added:
- `NOTIFICATION_SERVICE_URL` - URL for notification microservice (default: http://notify/events)
- `AUTH_SERVICE_URL` - URL for auth service API
- `ENCRYPTION_KEY` - Key for encrypting email passwords

## Migration Requirements

1. **Database Migration**: Run Prisma migration to apply schema changes
```bash
npx prisma migrate dev --name "integrate-auth-service-and-email-configs"
```

2. **Environment Update**: Update `.env` file to remove SMTP variables and add new ones

3. **Initial Sync**: After deployment, trigger initial carer sync for each tenant:
```bash
POST /api/v1/sync/sync-carers
Authorization: Bearer <tenant-auth-token>
```

4. **Email Configuration**: Set up email configurations for each tenant:
```bash
PUT /api/v1/sync/email-config
Content-Type: application/json
Authorization: Bearer <tenant-auth-token>

{
  "imapHost": "imap.gmail.com",
  "imapPort": 993,
  "imapUser": "tenant@example.com",
  "imapPassword": "password",
  "imapTls": true,
  "pollInterval": 300,
  "isActive": true
}
```

## Benefits

1. **Centralized User Management**: All user data managed in auth service
2. **Eliminated Data Duplication**: No manual carer creation reducing conflicts
3. **Microservice Architecture**: Proper separation of concerns
4. **Tenant Isolation**: Per-tenant email configurations
5. **Enhanced Security**: Encrypted email passwords
6. **Scalability**: External notification service handles all messaging
7. **Maintainability**: Clear service boundaries and responsibilities

## API Authentication

All sync endpoints require:
- Valid JWT token in Authorization header
- Token must include tenantId claim
- Auth token used for communicating with auth service

## Error Handling

Enhanced error handling with:
- Detailed logging for sync operations
- Graceful handling of auth service unavailability
- Email configuration validation and testing
- Notification service fallback strategies

## Testing

To test the integration:

1. **Carer Sync**: Use `/api/v1/sync/sync-carers` endpoint
2. **Email Config**: Use `/api/v1/sync/test-email` endpoint  
3. **Notifications**: Use `/api/v1/sync/test-notification` endpoint
4. **Read-Only Access**: Verify carer endpoints are read-only

This integration provides a robust, scalable solution that properly leverages existing microservices while maintaining data consistency and security.