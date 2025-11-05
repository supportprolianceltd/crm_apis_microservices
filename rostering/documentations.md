# Rostering Service - Complete API Documentation

## Overview

The Rostering Service is a comprehensive microservice designed to handle automated care visit scheduling, optimization, and real-time management for healthcare organizations. It integrates with multiple other services in your microservices architecture to provide end-to-end rostering capabilities.

## Architecture

### Core Components

1. **Controllers**: Handle HTTP requests and business logic
2. **Services**: Core business logic and external integrations
3. **Routes**: API endpoint definitions with middleware
4. **Middleware**: Authentication, validation, and request processing
5. **Workers**: Background job processing (email notifications)
6. **Types**: TypeScript interfaces and type definitions

### Key Features

- **AI-Powered Clustering**: Automatically groups care visits by location and time
- **Real-Time Optimization**: Dynamic roster adjustments based on disruptions
- **Emergency Handling**: Automated responses to urgent care needs
- **Continuity Tracking**: Ensures consistent carer-client relationships
- **Multi-Tenant Support**: Isolated data and operations per tenant
- **Live Operations**: Real-time roster monitoring and status updates

## API Endpoints

### Base URL
```
http://localhost:3005/api/rostering
```

### Authentication
All endpoints (except health checks and documentation) require JWT authentication via Bearer token:
```
Authorization: Bearer <jwt_token>
```

---

## 🚀 **Complete Demonstration Guide**

### Prerequisites
1. **Start the services**: `cd rostering && docker-compose up -d`
2. **Verify services are running**: `docker-compose ps`
3. **Check health**: `curl http://localhost:3005/health`

### Step 1: Database Setup & Seeding

#### Option A: API Endpoints for Seeding (Recommended)

**POST `/api/rostering/demo/seed-carers`**
Seed sample carers for demonstration
```bash
curl -X POST http://localhost:3005/api/rostering/demo/seed-carers \
  -H "Authorization: Bearer $TOKEN"
```

**POST `/api/rostering/demo/seed-visits`**
Seed sample care visits for demonstration
```bash
curl -X POST http://localhost:3005/api/rostering/demo/seed-visits \
  -H "Authorization: Bearer $TOKEN"
```

**POST `/api/rostering/demo/seed-constraints`**
Seed rostering constraints for demonstration
```bash
curl -X POST http://localhost:3005/api/rostering/demo/seed-constraints \
  -H "Authorization: Bearer $TOKEN"
```

**POST `/api/rostering/demo/seed-all`**
One-click seeding of all demo data
```bash
curl -X POST http://localhost:3005/api/rostering/demo/seed-all \
  -H "Authorization: Bearer $TOKEN"
```

**GET `/api/rostering/demo/status`**
Check seeding status and data counts
```bash
curl -X GET http://localhost:3005/api/rostering/demo/status \
  -H "Authorization: Bearer $TOKEN"
```

#### Option B: Direct Database Seeding (Advanced)

If you prefer direct database access, run these commands in the rostering container:
```bash
# Access the container
docker-compose exec rostering bash

# Run the seeding script
node -e "
const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

async function seed() {
  // Carers
  await prisma.carer.createMany({
    data: [
      {
        tenantId: '4',
        firstName: 'Robert',
        lastName: 'Johnson',
        email: 'robert.johnson@appbrew.com',
        phone: '+441234567890',
        skills: ['Personal Care', 'Medication Administration', 'Dementia Care', 'Mobility Support'],
        maxTravelDistance: 15000,
        latitude: 51.5074,
        longitude: -0.1278,
        isActive: true
      },
      {
        tenantId: '4',
        firstName: 'Christine',
        lastName: 'Williams',
        email: 'christine.williams@appbrew.com',
        phone: '+441234567891',
        skills: ['Personal Care', 'Complex Care', 'Palliative Care', 'Diabetes Management'],
        maxTravelDistance: 10000,
        latitude: 51.5155,
        longitude: -0.0922,
        isActive: true
      }
    ]
  });

  // Visits for today
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  await prisma.externalRequest.createMany({
    data: [
      {
        tenantId: '4',
        subject: 'Morning Personal Care',
        content: 'Regular personal care and medication',
        requestorEmail: 'margaret.smith@appbrew.com',
        requestorName: 'Margaret Smith',
        address: '123 Main St, London',
        postcode: 'SW1A 1AA',
        latitude: 51.5074,
        longitude: -0.1278,
        urgency: 'MEDIUM',
        status: 'APPROVED',
        requirements: 'Personal Care, Medication Administration',
        estimatedDuration: 60,
        scheduledStartTime: new Date(today.getTime() + 9 * 60 * 60 * 1000),
        sendToRostering: true
      },
      {
        tenantId: '4',
        subject: 'Afternoon Palliative Care',
        content: 'Palliative care support',
        requestorEmail: 'dorothy.davis@appbrew.com',
        requestorName: 'Dorothy Davis',
        address: '15 Ealing Broadway, London',
        postcode: 'W5 5NN',
        latitude: 51.5155,
        longitude: -0.0922,
        urgency: 'HIGH',
        status: 'APPROVED',
        requirements: 'Palliative Care, Complex Care',
        estimatedDuration: 120,
        scheduledStartTime: new Date(today.getTime() + 14 * 60 * 60 * 1000),
        sendToRostering: true
      }
    ]
  });

  // Constraints
  await prisma.rosteringConstraints.create({
    data: {
      tenantId: '4',
      name: 'Default Rules',
      wtdMaxHoursPerWeek: 48,
      restPeriodHours: 11,
      bufferMinutes: 15,
      travelMaxMinutes: 30,
      continuityTargetPercent: 80,
      isActive: true
    }
  });

  console.log('✅ Database seeded successfully');
  process.exit(0);
}

seed().catch(console.error);
"
```

### Step 2: Authentication Setup

#### Get JWT Token (Example for tenant 4)
```bash
# This is a sample token - in production, get from auth service
TOKEN="eyJhbGciOiJSUzI1NiIsImtpZCI6IjQ2OTU3YWUwNWY5NTQwYjNiNzVkN2E5YzZhZjg3ODI3IiwidHlwIjoiSldUIn0.eyJqdGkiOiI2M2UzMDQxZS0yODUwLTRhMzItOGY3Mi1kZjBlZDJiZGEzOTEiLCJzdWIiOiJzdXBwb3J0QGFwcGJyZXcuY29tIiwidXNlcm5hbWUiOiJwZ29kc29uNjkxOSIsInJvbGUiOiJhZG1pbiIsInN0YXR1cyI6ImFjdGl2ZSIsInRlbmFudF9pZCI6NCwidGVuYW50X29yZ2FuaXphdGlvbmFsX2lkIjoiVEVOLTAwMDQiLCJ0ZW5hbnRfbmFtZSI6ImFwcGJyZXciLCJ0ZW5hbnRfdW5pcXVlX2lkIjoiYjJkODMwNWItYmNjZi00NTcwLThkMDQtNGFlNWIxZGRiYThlIiwidGVuYW50X3NjaGVtYSI6ImFwcGJyZXciLCJ0ZW5hbnRfZG9tYWluIjoiYXBwYnJldy5jb20iLCJoYXNfYWNjZXB0ZWRfdGVybXMiOmZhbHNlLCJ1c2VyX3R5cGUiOiJ0ZW5hbnQiLCJlbWFpbCI6InN1cHBvcnRAYXBwYnJldy5jb20iLCJ0eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzYyMTEzNzAwLjcxNzQzMywiaWF0IjoxNzYyMTAyOTAwfQ.qgCDPoXBlP5SaO5NUQjvfJeUmHYp6Pe_PwCjQr6aVEq8n3t2RQrizpHegHdx6CzReQEx8J6cBEfAgYl1uRPo4xcHnJvETNX3cpUswE3T91QgURhDq4tHOSqjfbInVob9tEsyfyrcyyyyz_CR8baGs5ry2opVqaYLs3N6vmxdIRSGcAUK2PR4gaU1bz12C5Nej-kuGDiJz7UhoUT4-b7kO8zMyH1p5VyabHpZtQBM3TJYVkiuyJf00TRGm6pVAZb22k0SNRD4O77JvsNk4SCsHZ_WN4cgE5QaIWUmWduNAQmJLX2JvZvVsl1Uy_i8Yh5XN0lGOqnPGvT30RyP_UVYkA"
```

### Step 3: Core API Demonstrations

#### 1. Health Check
```bash
curl -X GET http://localhost:3005/health
```

#### 2. Authenticated Status Check
```bash
curl -X GET http://localhost:3005/api/rostering/status \
  -H "Authorization: Bearer $TOKEN"
```

#### 3. View Available Carers
```bash
curl -X GET "http://localhost:3005/api/rostering/carers/search?query=" \
  -H "Authorization: Bearer $TOKEN"
```

#### 4. View Care Requests
```bash
curl -X GET http://localhost:3005/api/rostering/requests \
  -H "Authorization: Bearer $TOKEN"
```

#### 5. **🎯 MAIN DEMO: Generate Optimized Roster**
```bash
# Generate roster for today with multiple scenarios
curl -X POST http://localhost:3005/api/rostering/roster/generate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "startDate": "'$(date +%Y-%m-%d)'T00:00:00Z",
    "endDate": "'$(date +%Y-%m-%d)'T23:59:59Z",
    "strategy": "balanced",
    "generateScenarios": true
  }'
```

#### 6. View Rostering Constraints
```bash
curl -X GET http://localhost:3005/api/rostering/constraints \
  -H "Authorization: Bearer $TOKEN"
```

#### 7. Test Emergency Handling
```bash
curl -X POST http://localhost:3005/api/rostering/roster/emergency-visit \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "clientId": "emergency_client_123",
    "address": "123 Emergency St, London",
    "postcode": "SW1A 1AA",
    "urgency": "URGENT",
    "scheduledStartTime": "'$(date +%Y-%m-%d)'T15:00:00.000Z",
    "estimatedDuration": 45,
    "requirements": "Immediate care needed"
  }'
```

### Step 4: Advanced Features

#### Real-Time Optimization
```bash
curl -X POST http://localhost:3005/api/rostering/roster/optimize-now \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "dateRange": {
      "start": "'$(date +%Y-%m-%d)'T00:00:00Z",
      "end": "'$(date +%Y-%m-%d)'T23:59:59Z"
    },
    "strategy": "continuity"
  }'
```

#### Continuity Tracking
```bash
curl -X POST http://localhost:3005/api/rostering/roster/continuity/report \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "dateFrom": "'$(date +%Y-%m-%d)'T00:00:00Z",
    "dateTo": "'$(date +%Y-%m-%d)'T23:59:59Z"
  }'
```

### Step 5: Monitoring & Analytics

#### Live Operations Status
```bash
# Get roster ID from previous generation response, then:
curl -X GET http://localhost:3005/api/rostering/roster/live-status/{rosterId} \
  -H "Authorization: Bearer $TOKEN"
```

#### API Documentation
```bash
# View interactive API docs
open http://localhost:3005/api/rostering/docs
```

### Step 6: Database Inspection

#### View Generated Roster Data
```bash
# Access PostgreSQL
docker-compose exec rostering-db psql -U postgres -d rostering_dev

# View rosters
SELECT id, name, strategy, "totalAssignments", "continuityScore", "qualityScore" FROM rosters WHERE "tenantId" = '4';

# View assignments
SELECT a.id, a."scheduledTime", c."firstName", c."lastName", er.subject
FROM assignments a
JOIN carers c ON a."carerId" = c.id
JOIN external_requests er ON a."visitId" = er.id
WHERE a."tenantId" = '4'
ORDER BY a."scheduledTime";
```

### Expected Results

#### Roster Generation Response
```json
{
  "success": true,
  "data": {
    "scenarios": [
      {
        "id": "scenario_xxx",
        "label": "Balanced (recommended)",
        "strategy": "balanced",
        "assignments": [
          {
            "visitId": "visit_xxx",
            "carerId": "carer_xxx",
            "carerName": "Robert Johnson",
            "scheduledTime": "2025-11-02T09:00:00.000Z",
            "estimatedEndTime": "2025-11-02T10:00:00.000Z",
            "travelFromPrevious": 0,
            "complianceChecks": {
              "wtdCompliant": true,
              "restPeriodOK": true,
              "travelTimeOK": true,
              "skillsMatch": true,
              "warnings": []
            },
            "visitDetails": {
              "clientName": "Margaret Smith",
              "address": "123 Main St, London",
              "duration": 60,
              "requirements": "Personal Care, Medication Administration"
            }
          }
        ],
        "metrics": {
          "totalTravel": 15,
          "continuityScore": 85,
          "violations": { "hard": 0, "soft": 0 },
          "overtimeMinutes": 0,
          "averageCarerWorkload": 90
        },
        "score": 92.5
      }
    ],
    "summary": {
      "totalScenarios": 3,
      "recommended": "scenario_xxx",
      "totalAssignments": 2
    }
  }
}
```

### Troubleshooting

#### Common Issues:
1. **"No visits to schedule"**: Check date ranges and visit dates
2. **401 Unauthorized**: Verify JWT token is valid and not expired
3. **Container not running**: `docker-compose ps` and `docker-compose logs`
4. **Database connection**: Check PostgreSQL container is healthy

#### Debug Commands:
```bash
# Check service logs
docker-compose logs rostering --tail 20

# Check database
docker-compose exec rostering-db psql -U postgres -d rostering_dev -c "SELECT COUNT(*) FROM carers WHERE \"tenantId\" = '4';"

# Test API connectivity
curl -v http://localhost:3005/health
```

This demonstration showcases the complete AI-powered rostering workflow from data seeding through intelligent optimization to real-time operations management.

---

## 1. Health & Status Endpoints

### GET `/health`
**Public endpoint** - No authentication required

**Response:**
```json
{
  "success": true,
  "service": "rostering-service",
  "version": "1.0.0",
  "timestamp": "2025-10-31T12:00:00.000Z",
  "status": "healthy"
}
```

### GET `/status`
**Requires authentication**

**Response:**
```json
{
  "success": true,
  "service": "rostering-service",
  "tenant": "tenant_123",
  "user": "user@example.com",
  "timestamp": "2025-10-31T12:00:00.000Z",
  "status": "authenticated"
}
```

---

## 2. Request Management

### GET `/requests`
Get all requests for the authenticated user's tenant

**Query Parameters:**
- `status` (optional): Filter by status (PENDING, APPROVED, DECLINED)
- `limit` (optional): Number of results (default: 50)
- `offset` (optional): Pagination offset (default: 0)

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": "req_123",
      "subject": "Care Visit Request",
      "content": "Regular care visit needed",
      "requestorEmail": "client@example.com",
      "address": "123 Main St",
      "postcode": "SW1A 1AA",
      "status": "APPROVED",
      "scheduledStartTime": "2025-10-31T14:00:00.000Z",
      "estimatedDuration": 60,
      "requirements": "Mobility assistance",
      "createdAt": "2025-10-30T10:00:00.000Z"
    }
  ],
  "pagination": {
    "total": 25,
    "limit": 50,
    "offset": 0
  }
}
```

### POST `/requests`
Create a new care request

**Request Body:**
```json
{
  "subject": "Emergency Care Visit",
  "content": "Urgent care needed",
  "requestorEmail": "client@example.com",
  "requestorName": "John Doe",
  "address": "123 Main St, London",
  "postcode": "SW1A 1AA",
  "scheduledStartTime": "2025-10-31T14:00:00.000Z",
  "estimatedDuration": 60,
  "requirements": "Medication assistance",
  "urgency": "HIGH",
  "sendToRostering": true
}
```

### GET `/requests/search`
Search requests with filters

**Query Parameters:**
- `query`: Search term
- `status`: Filter by status
- `dateFrom`: Start date filter
- `dateTo`: End date filter

### GET `/requests/:id`
Get specific request details

### PUT `/requests/:id`
Update request (partial update supported)

### DELETE `/requests/:id`
Delete request

### POST `/requests/:id/approve`
Approve a request

### POST `/requests/:id/decline`
Decline a request

---

## 3. Carer Management

### GET `/carers/search`
Search carers by skills, location, or availability

**Query Parameters:**
- `query`: Search term (name, email, skills)
- `latitude`: Client latitude for distance filtering
- `longitude`: Client longitude for distance filtering
- `radius`: Search radius in meters (default: 5000)

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": "carer_123",
      "firstName": "Sarah",
      "lastName": "Johnson",
      "email": "sarah@example.com",
      "phone": "+44 123 456 7890",
      "skills": ["Medication", "Mobility"],
      "maxTravelDistance": 10000,
      "latitude": 51.5074,
      "longitude": -0.1278,
      "isActive": true
    }
  ]
}
```

### GET `/carers/:id`
Get carer details

### GET `/carers/:id/availability`
Get carer availability schedule

---

## 4. Cluster Management

### GET `/clusters`
Get cluster overview for tenant

**Response:**
```json
{
  "success": true,
  "data": {
    "totalClusters": 5,
    "totalActiveRequests": 45,
    "totalActiveCarers": 12,
    "clusters": [
      {
        "id": "cluster_123",
        "name": "Central London",
        "postcode": "SW1A",
        "activeRequestCount": 12,
        "activeCarerCount": 3,
        "lastActivityAt": "2025-10-31T10:00:00.000Z"
      }
    ]
  }
}
```

### POST `/clusters`
Create new cluster

**Request Body:**
```json
{
  "name": "North London",
  "description": "North London care cluster",
  "postcode": "N1 1AA",
  "latitude": 51.5474,
  "longitude": -0.0878,
  "radiusMeters": 5000
}
```

### GET `/clusters/:clusterId`
Get detailed cluster information

### GET `/clusters/:clusterId/carers`
Get carers assigned to cluster

### PUT `/clusters/:clusterId`
Update cluster metadata

### DELETE `/clusters/:clusterId`
Delete cluster (only if no active requests)

### POST `/clusters/assign-carer/:carerId`
Assign carer to cluster based on location

**Request Body:**
```json
{
  "latitude": 51.5074,
  "longitude": -0.1278
}
```

### POST `/clusters/:clusterId/assign-request/:requestId`
Manually assign request to cluster

### POST `/clusters/generate`
Generate AI-powered clusters

**Request Body:**
```json
{
  "startDate": "2025-11-01",
  "endDate": "2025-11-07",
  "maxTravelTime": 30,
  "timeWindowTolerance": 15,
  "minClusterSize": 2,
  "maxClusterSize": 8,
  "epsilon": 0.1,
  "minPoints": 2
}
```

### POST `/clusters/generate/optimized`
Generate optimized clusters with AI

---

## 5. Roster Generation & Management

### POST `/roster/generate`
Generate roster scenarios

**Request Body:**
```json
{
  "clusterId": "cluster_123",
  "startDate": "2025-11-01",
  "endDate": "2025-11-07",
  "strategy": "continuity",
  "generateScenarios": true
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "scenarios": [
      {
        "id": "scenario_123",
        "name": "Continuity Optimized",
        "metrics": {
          "totalTravel": 45.2,
          "continuityScore": 85.5,
          "violations": {
            "hard": 0,
            "soft": 2
          }
        },
        "assignments": [
          {
            "visitId": "visit_123",
            "carerId": "carer_456",
            "scheduledTime": "2025-11-01T09:00:00.000Z",
            "estimatedDuration": 60
          }
        ]
      }
    ],
    "summary": {
      "totalScenarios": 3,
      "recommended": "scenario_123",
      "totalAssignments": 45
    }
  }
}
```

### GET `/roster/:id`
Get roster details

### POST `/roster/:id/publish`
Publish roster to carers (Phase 2 feature)

### GET `/roster/:id/acceptance`
Get acceptance status (Phase 2 feature)

### POST `/roster/compare`
Compare two roster scenarios

---

## 6. Real-Time Optimization

### POST `/roster/optimize-now`
Run immediate roster optimization

**Request Body:**
```json
{
  "clusterId": "cluster_123",
  "dateRange": {
    "start": "2025-11-01",
    "end": "2025-11-07"
  },
  "strategy": "balanced"
}
```

### GET `/roster/optimization-status/:tenantId`
Get current optimization status

---

## 7. Emergency Handling

### POST `/roster/emergency-visit`
Add emergency visit

**Request Body:**
```json
{
  "clientId": "client_123",
  "address": "123 Emergency St",
  "postcode": "SW1A 1AA",
  "urgency": "URGENT",
  "scheduledStartTime": "2025-10-31T15:00:00.000Z",
  "estimatedDuration": 45,
  "requirements": "Immediate care needed"
}
```

### POST `/roster/carer-unavailable`
Handle carer unavailability

**Request Body:**
```json
{
  "carerId": "carer_123",
  "reason": "sick",
  "affectedDate": "2025-10-31"
}
```

### POST `/roster/emergency-options`
Get emergency resolution options

### POST `/roster/apply-emergency-resolution`
Apply emergency resolution

---

## 8. Manual Overrides

### POST `/roster/swap-assignments`
Swap two assignments

**Request Body:**
```json
{
  "assignmentIdA": "assignment_123",
  "assignmentIdB": "assignment_456"
}
```

### POST `/roster/reassign`
Reassign visit to different carer

**Request Body:**
```json
{
  "assignmentId": "assignment_123",
  "newCarerId": "carer_789",
  "reason": "Carer unavailable"
}
```

### POST `/roster/assignments/:id/lock`
Lock assignment to prevent auto-optimization

### DELETE `/roster/assignments/:id/lock`
Unlock assignment

### GET `/roster/locked-assignments/:rosterId`
Get all locked assignments

### POST `/roster/validate-manual-change`
Validate manual change before applying

### POST `/roster/bulk-update`
Bulk update assignments

---

## 9. Continuity Tracking

### GET `/roster/continuity/client/:clientId`
Get client continuity score

### POST `/roster/continuity/report`
Get continuity report for date range

**Request Body:**
```json
{
  "dateFrom": "2025-10-01",
  "dateTo": "2025-10-31"
}
```

### GET `/roster/continuity/alerts/:tenantId`
Get continuity alerts

---

## 10. Live Operations

### GET `/roster/live-status/:rosterId`
Get real-time roster status

**Response:**
```json
{
  "success": true,
  "data": {
    "rosterId": "roster_123",
    "totalAssignments": 45,
    "completed": 32,
    "inProgress": 8,
    "upcoming": 5,
    "delayed": 0,
    "completionRate": 71,
    "onTimeRate": 100
  }
}
```

### PATCH `/roster/visits/:visitId/status`
Update visit status

**Request Body:**
```json
{
  "status": "STARTED",
  "notes": "Client arrived on time"
}
```

### GET `/roster/at-risk-visits/:rosterId`
Get visits at risk of being late

---

## 11. Constraints Management

### GET `/constraints`
Get active constraints for tenant

**Response:**
```json
{
  "success": true,
  "data": {
    "wtdMaxHoursPerWeek": 48,
    "restPeriodHours": 11,
    "bufferMinutes": 15,
    "travelMaxMinutes": 30,
    "continuityTargetPercent": 80
  }
}
```

### PUT `/constraints`
Update constraints

### POST `/constraints/rule-sets`
Create new rule set

### GET `/constraints/rule-sets`
Get all rule sets

### POST `/constraints/validate-assignment`
Validate assignment against constraints

---

## 13. Demonstration & Seeding Endpoints

### Demo Data Management

#### POST `/api/rostering/demo/seed-carers`
**Seed sample carers for demonstration**

**Request Body (optional - uses defaults if not provided):**
```json
{
  "tenantId": "4",
  "carers": [
    {
      "firstName": "Robert",
      "lastName": "Johnson",
      "email": "robert.johnson@appbrew.com",
      "phone": "+441234567890",
      "skills": ["Personal Care", "Medication Administration", "Dementia Care", "Mobility Support"],
      "maxTravelDistance": 15000,
      "latitude": 51.5074,
      "longitude": -0.1278
    },
    {
      "firstName": "Christine",
      "lastName": "Williams",
      "email": "christine.williams@appbrew.com",
      "phone": "+441234567891",
      "skills": ["Personal Care", "Complex Care", "Palliative Care", "Diabetes Management"],
      "maxTravelDistance": 10000,
      "latitude": 51.5155,
      "longitude": -0.0922
    },
    {
      "firstName": "Hasan",
      "lastName": "Ahmed",
      "email": "hasan.ahmed@appbrew.com",
      "phone": "+441234567892",
      "skills": ["Personal Care", "Mobility Support", "Companionship"],
      "maxTravelDistance": 12000,
      "latitude": 51.5465,
      "longitude": -0.1058
    },
    {
      "firstName": "Janet",
      "lastName": "Thompson",
      "email": "janet.thompson@appbrew.com",
      "phone": "+441234567893",
      "skills": ["Hoist Operation", "Bariatric Care", "Complex Mobility"],
      "maxTravelDistance": 20000,
      "latitude": 51.5528,
      "longitude": -0.1122
    },
    {
      "firstName": "Michael",
      "lastName": "Wilson",
      "email": "michael.wilson@appbrew.com",
      "phone": "+441234567894",
      "skills": ["Personal Care", "Mobility Support", "Dementia Care"],
      "maxTravelDistance": 15000,
      "latitude": 51.5283,
      "longitude": -0.1422
    }
  ]
}
```

**cURL Command:**
```bash
curl -X POST http://localhost:3005/api/rostering/demo/seed-carers \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "tenantId": "4",
    "carers": [
      {
        "firstName": "Robert",
        "lastName": "Johnson",
        "email": "robert.johnson@appbrew.com",
        "phone": "+441234567890",
        "skills": ["Personal Care", "Medication Administration", "Dementia Care", "Mobility Support"],
        "maxTravelDistance": 15000,
        "latitude": 51.5074,
        "longitude": -0.1278
      }
    ]
  }'
```

**Response:**
```json
{
  "success": true,
  "message": "Seeded 5 carers successfully",
  "data": {
    "carersCreated": 5,
    "tenantId": "4",
    "carers": [
      {
        "id": "carer_xxx",
        "firstName": "Robert",
        "lastName": "Johnson",
        "email": "robert.johnson@appbrew.com",
        "skills": ["Personal Care", "Medication Administration", "Dementia Care", "Mobility Support"],
        "isActive": true
      }
    ]
  }
}
```

#### POST `/api/rostering/demo/seed-visits`
**Seed sample care visits for demonstration**

**Request Body (optional - uses defaults if not provided):**
```json
{
  "tenantId": "4",
  "date": "2025-11-02",
  "visits": [
    {
      "subject": "Morning Personal Care",
      "content": "Regular personal care and medication",
      "requestorEmail": "margaret.smith@appbrew.com",
      "requestorName": "Margaret Smith",
      "address": "123 Main St, London",
      "postcode": "SW1A 1AA",
      "latitude": 51.5074,
      "longitude": -0.1278,
      "urgency": "MEDIUM",
      "requirements": "Personal Care, Medication Administration",
      "estimatedDuration": 60,
      "scheduledHour": 9
    },
    {
      "subject": "Dementia Support Visit",
      "content": "Specialized dementia care",
      "requestorEmail": "arthur.johnson@appbrew.com",
      "requestorName": "Arthur Johnson",
      "address": "42 Finchley Road, London",
      "postcode": "NW4 2BJ",
      "latitude": 51.5095,
      "longitude": -0.1278,
      "urgency": "MEDIUM",
      "requirements": "Dementia Care, Personal Care",
      "estimatedDuration": 75,
      "scheduledHour": 10
    },
    {
      "subject": "Complex Mobility Support",
      "content": "Hoist operation and mobility assistance",
      "requestorEmail": "barbara.wilson@appbrew.com",
      "requestorName": "Barbara Wilson",
      "address": "18 Harrow View, Harrow",
      "postcode": "HA2 6DX",
      "latitude": 51.5465,
      "longitude": -0.1058,
      "urgency": "HIGH",
      "requirements": "Hoist Operation, Complex Mobility",
      "estimatedDuration": 90,
      "scheduledHour": 11
    },
    {
      "subject": "Afternoon Palliative Care",
      "content": "Palliative care support",
      "requestorEmail": "dorothy.davis@appbrew.com",
      "requestorName": "Dorothy Davis",
      "address": "15 Ealing Broadway, London",
      "postcode": "W5 5NN",
      "latitude": 51.5155,
      "longitude": -0.0922,
      "urgency": "HIGH",
      "requirements": "Palliative Care, Complex Care",
      "estimatedDuration": 120,
      "scheduledHour": 14
    },
    {
      "subject": "Evening Companionship",
      "content": "Social companionship visit",
      "requestorEmail": "thomas.miller@appbrew.com",
      "requestorName": "Thomas Miller",
      "address": "29 Northolt Road, Harrow",
      "postcode": "HA2 8EQ",
      "latitude": 51.5528,
      "longitude": -0.1122,
      "urgency": "LOW",
      "requirements": "Companionship, Personal Care",
      "estimatedDuration": 45,
      "scheduledHour": 16
    },
    {
      "subject": "Diabetes Management Visit",
      "content": "Blood sugar monitoring and insulin administration",
      "requestorEmail": "james.brown@appbrew.com",
      "requestorName": "James Brown",
      "address": "73 Roxeth Hill, Harrow",
      "postcode": "HA2 0JL",
      "latitude": 51.5283,
      "longitude": -0.1422,
      "urgency": "MEDIUM",
      "requirements": "Diabetes Management, Medication Administration",
      "estimatedDuration": 60,
      "scheduledHour": 15
    }
  ]
}
```

**cURL Command:**
```bash
curl -X POST http://localhost:3005/api/rostering/demo/seed-visits \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "tenantId": "4",
    "date": "2025-11-02",
    "visits": [
      {
        "subject": "Morning Personal Care",
        "content": "Regular personal care and medication",
        "requestorEmail": "margaret.smith@appbrew.com",
        "requestorName": "Margaret Smith",
        "address": "123 Main St, London",
        "postcode": "SW1A 1AA",
        "latitude": 51.5074,
        "longitude": -0.1278,
        "urgency": "MEDIUM",
        "requirements": "Personal Care, Medication Administration",
        "estimatedDuration": 60,
        "scheduledHour": 9
      }
    ]
  }'
```

**Response:**
```json
{
  "success": true,
  "message": "Seeded 6 visits successfully",
  "data": {
    "visitsCreated": 6,
    "tenantId": "4",
    "dateRange": "2025-11-02",
    "visits": [
      {
        "id": "visit_xxx",
        "subject": "Morning Personal Care",
        "scheduledStartTime": "2025-11-02T09:00:00.000Z",
        "requirements": "Personal Care, Medication Administration",
        "status": "APPROVED"
      }
    ]
  }
}
```

#### POST `/api/rostering/demo/seed-constraints`
**Seed rostering constraints for demonstration**

**Request Body (optional - uses defaults if not provided):**
```json
{
  "tenantId": "4",
  "constraints": {
    "name": "Default Rules",
    "wtdMaxHoursPerWeek": 48,
    "restPeriodHours": 11,
    "bufferMinutes": 15,
    "travelMaxMinutes": 30,
    "continuityTargetPercent": 80,
    "maxDailyHours": 10,
    "minRestBetweenVisits": 0,
    "maxTravelTimePerVisit": 60,
    "isActive": true
  }
}
```

**cURL Command:**
```bash
curl -X POST http://localhost:3005/api/rostering/demo/seed-constraints \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "tenantId": "4",
    "constraints": {
      "name": "Healthcare Compliance Rules",
      "wtdMaxHoursPerWeek": 48,
      "restPeriodHours": 11,
      "bufferMinutes": 15,
      "travelMaxMinutes": 30,
      "continuityTargetPercent": 80,
      "isActive": true
    }
  }'
```

**Response:**
```json
{
  "success": true,
  "message": "Seeded constraints successfully",
  "data": {
    "constraintsCreated": 1,
    "tenantId": "4",
    "constraints": {
      "id": "constraint_xxx",
      "name": "Healthcare Compliance Rules",
      "wtdMaxHoursPerWeek": 48,
      "restPeriodHours": 11,
      "bufferMinutes": 15,
      "travelMaxMinutes": 30,
      "continuityTargetPercent": 80,
      "isActive": true
    }
  }
}
```

#### POST `/api/rostering/demo/seed-all`
**One-click seeding of all demo data**

**Request Body (optional - uses comprehensive defaults if not provided):**
```json
{
  "tenantId": "4",
  "date": "2025-11-02",
  "includeCarers": true,
  "includeVisits": true,
  "includeConstraints": true,
  "carers": [...],  // Same as seed-carers endpoint
  "visits": [...],  // Same as seed-visits endpoint
  "constraints": {...}  // Same as seed-constraints endpoint
}
```

**cURL Command (Simple - uses defaults):**
```bash
curl -X POST http://localhost:3005/api/rostering/demo/seed-all \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "tenantId": "4",
    "date": "2025-11-02"
  }'
```

**cURL Command (Custom data):**
```bash
curl -X POST http://localhost:3005/api/rostering/demo/seed-all \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "tenantId": "4",
    "date": "2025-11-02",
    "carers": [
      {
        "firstName": "Sarah",
        "lastName": "Connor",
        "email": "sarah.connor@demo.com",
        "skills": ["Personal Care", "Emergency Response"],
        "maxTravelDistance": 10000,
        "latitude": 51.5074,
        "longitude": -0.1278
      }
    ],
    "visits": [
      {
        "subject": "Demo Care Visit",
        "requestorEmail": "client@demo.com",
        "requirements": "Personal Care",
        "estimatedDuration": 60,
        "scheduledHour": 10
      }
    ]
  }'
```

**Response:**
```json
{
  "success": true,
  "message": "Complete demo seeding successful",
  "data": {
    "carersCreated": 5,
    "visitsCreated": 6,
    "constraintsCreated": 1,
    "tenantId": "4",
    "dateRange": "2025-11-02",
    "readyForDemo": true
  }
}
```

#### GET `/api/rostering/demo/status`
**Check seeding status and data counts**

**Query Parameters:**
- `tenantId` (optional): Specific tenant to check (default: authenticated user's tenant)

**cURL Command:**
```bash
curl -X GET "http://localhost:3005/api/rostering/demo/status?tenantId=4" \
  -H "Authorization: Bearer $TOKEN"
```

**Response:**
```json
{
  "success": true,
  "data": {
    "tenantId": "4",
    "timestamp": "2025-11-02T17:48:00.000Z",
    "carers": {
      "total": 5,
      "active": 5,
      "withSkills": 5,
      "withLocations": 5,
      "skillBreakdown": {
        "Personal Care": 5,
        "Medication Administration": 3,
        "Dementia Care": 2,
        "Mobility Support": 3
      }
    },
    "visits": {
      "total": 6,
      "approved": 6,
      "pending": 0,
      "declined": 0,
      "today": 6,
      "thisWeek": 6,
      "urgencyBreakdown": {
        "HIGH": 2,
        "MEDIUM": 3,
        "LOW": 1
      }
    },
    "constraints": {
      "active": 1,
      "total": 1,
      "rules": {
        "wtdMaxHoursPerWeek": 48,
        "restPeriodHours": 11,
        "bufferMinutes": 15,
        "travelMaxMinutes": 30,
        "continuityTargetPercent": 80
      }
    },
    "rosters": {
      "total": 0,
      "draft": 0,
      "published": 0,
      "active": 0,
      "recent": null
    },
    "optimization": {
      "ready": true,
      "estimatedScenarios": 3,
      "expectedAssignments": 6
    },
    "readyForDemo": true,
    "issues": []
  }
}
```

#### DELETE `/api/rostering/demo/clear`
**Clear all demo data (for reset)**

**Request Body (optional):**
```json
{
  "tenantId": "4",
  "clearCarers": true,
  "clearVisits": true,
  "clearConstraints": true,
  "clearRosters": true,
  "clearAssignments": true
}
```

**cURL Command (Clear all):**
```bash
curl -X DELETE http://localhost:3005/api/rostering/demo/clear \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "tenantId": "4",
    "clearCarers": true,
    "clearVisits": true,
    "clearConstraints": true,
    "clearRosters": true
  }'
```

**cURL Command (Selective clear):**
```bash
curl -X DELETE http://localhost:3005/api/rostering/demo/clear \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "tenantId": "4",
    "clearCarers": false,
    "clearVisits": true,
    "clearConstraints": false,
    "clearRosters": true
  }'
```

**Response:**
```json
{
  "success": true,
  "message": "Demo data cleared successfully",
  "data": {
    "tenantId": "4",
    "carersDeleted": 5,
    "visitsDeleted": 6,
    "constraintsDeleted": 1,
    "rostersDeleted": 0,
    "assignmentsDeleted": 0,
    "totalDeleted": 12
  }
}
```

## 12. Synchronization & Integration

### POST `/sync/sync-carers`
Manually sync carers from auth service

### GET `/sync/sync-status`
Get carer sync status

### POST `/sync/sync-carer/:carerId`
Sync single carer

### PUT `/sync/email-config`
Configure tenant email settings

**Request Body:**
```json
{
  "imapHost": "imap.gmail.com",
  "imapPort": 993,
  "imapUser": "tenant@example.com",
  "imapPassword": "app-password",
  "imapTls": true,
  "pollInterval": 300,
  "isActive": true
}
```

### GET `/sync/email-config`
Get email configuration

### POST `/sync/test-email`
Test email connection

### DELETE `/sync/email-config`
Delete email configuration

### POST `/sync/test-notification`
Send test notification

---

## Data Models

### Request (ExternalRequest)
```typescript
{
  id: string;
  tenantId: string;
  subject: string;
  content: string;
  requestorEmail: string;
  requestorName?: string;
  address: string;
  postcode: string;
  latitude?: number;
  longitude?: number;
  urgency: 'LOW' | 'MEDIUM' | 'HIGH' | 'URGENT';
  status: 'PENDING' | 'APPROVED' | 'DECLINED';
  scheduledStartTime: Date;
  estimatedDuration: number;
  requirements?: string;
  sendToRostering: boolean;
  clusterId?: string;
  createdAt: Date;
  updatedAt: Date;
}
```

### Carer
```typescript
{
  id: string;
  tenantId: string;
  firstName: string;
  lastName: string;
  email: string;
  phone: string;
  skills: string[];
  maxTravelDistance: number;
  latitude?: number;
  longitude?: number;
  clusterId?: string;
  isActive: boolean;
  createdAt: Date;
  updatedAt: Date;
}
```

### Cluster
```typescript
{
  id: string;
  tenantId: string;
  name: string;
  description?: string;
  postcode?: string;
  latitude?: number;
  longitude?: number;
  radiusMeters: number;
  activeRequestCount: number;
  totalRequestCount: number;
  activeCarerCount: number;
  totalCarerCount: number;
  lastActivityAt: Date;
  createdAt: Date;
  updatedAt: Date;
}
```

### Roster
```typescript
{
  id: string;
  tenantId: string;
  clusterId?: string;
  name: string;
  status: 'DRAFT' | 'PENDING_APPROVAL' | 'APPROVED' | 'PUBLISHED' | 'ACTIVE';
  startDate: Date;
  endDate: Date;
  strategy: string;
  metrics: {
    totalTravel: number;
    continuityScore: number;
    violations: {
      hard: number;
      soft: number;
    };
  };
  createdAt: Date;
  updatedAt: Date;
}
```

### Assignment
```typescript
{
  id: string;
  rosterId: string;
  visitId: string;
  carerId: string;
  tenantId: string;
  scheduledTime: Date;
  estimatedEndTime: Date;
  status: 'PENDING' | 'OFFERED' | 'ACCEPTED' | 'STARTED' | 'COMPLETED' | 'CANCELLED';
  warnings: string[];
  notes?: string;
  createdAt: Date;
  updatedAt: Date;
}
```

## Error Handling

All endpoints return standardized error responses:

```json
{
  "success": false,
  "error": "Error type",
  "message": "Human-readable error message",
  "details": "Additional error details (optional)"
}
```

Common HTTP status codes:
- `200`: Success
- `400`: Bad Request (validation errors)
- `401`: Unauthorized (missing/invalid token)
- `403`: Forbidden (insufficient permissions)
- `404`: Not Found
- `409`: Conflict (duplicate resources)
- `500`: Internal Server Error

## Rate Limiting

- General API: 300 requests per 15 minutes
- POST endpoints: 100 requests per minute

## WebSocket Integration

The service includes WebSocket support for real-time updates:
- Live roster status updates
- Emergency notifications
- Assignment changes
- Disruption alerts

## Background Workers

### Email Worker
- Processes email notifications asynchronously
- Handles carer assignment notifications
- Manages emergency alerts
- Sends continuity reports

## Configuration

### Environment Variables
```bash
NODE_ENV=development
PORT=3005
DATABASE_URL=postgresql://username:password@localhost:5432/rostering_db
REDIS_URL=redis://localhost:6379
AUTH_SERVICE_URL=http://auth-service:8001
JWT_RS256_PUBLIC_KEY_URL=http://auth-service:8001/auth/public-key/
JWT_SECRET=your-secret-key
GATEWAY_URL=http://api_gateway:8000
LOG_LEVEL=info
```

## Monitoring & Health Checks

### Health Endpoints
- `/health`: Basic service health
- `/status`: Authenticated status check

### Metrics
- Request counts and response times
- Circuit breaker status
- Database connection health
- External service connectivity

## Security Features

- JWT-based authentication with RS256/H256 fallback
- Tenant isolation
- Rate limiting
- Input validation
- CORS protection
- SQL injection prevention

## Performance Optimizations

- Connection pooling for database and external services
- Request streaming for large responses
- Background job processing
- Circuit breaker pattern for external service calls
- Compression for responses (except Swagger docs)

## Integration Points

### Auth Service
- User authentication and authorization
- Carer data synchronization
- Permission management

### Job Applications Service
- Care request data
- Client information

### Talent Engine Service
- Additional carer data
- Job requisition integration

### Messaging Service
- Notification delivery
- Real-time updates

### HR Service
- Employee data integration
- Compliance tracking

This comprehensive rostering service provides a complete solution for automated care visit scheduling with AI-powered optimization, real-time management, and robust emergency handling capabilities.