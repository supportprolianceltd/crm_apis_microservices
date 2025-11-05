# 📮 Postman Request Examples - Rostering Service

## Authentication

### Login - Coordinator
**Purpose:** Authenticates a coordinator user and returns a JWT token for subsequent API calls.
**Method:** POST
**URL:** `http://localhost:9090/api/auth/token/`

**Request Body:**
```json
{
  "email": "support@prolianceltd.com",
  "password": "qwerty"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "user": {
      "id": "user-123",
      "email": "coordinator@hospital.com",
      "firstName": "John",
      "lastName": "Coordinator",
      "role": "coordinator",
      "tenantId": "tenant-123"
    },
    "expiresIn": 3600
  }
}
```

---

## Visit Management

### Create Visit Request
**Purpose:** Creates a new visit request for rostering. The request will be geocoded, assigned to a cluster (if AUTO_ASSIGN_REQUESTS=true), and automatically matched with available carers. **Data Sources:** Creates ExternalRequest record, geocodes address, assigns to cluster, triggers auto-matching.
**Method:** POST
**URL:** `http://localhost:9090/api/rostering/requests`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Request Body:**
```json
{
  "subject": "Weekly Personal Care Visit",
  "content": "Client requires assistance with personal care, medication management, and light housekeeping. Client has mobility issues and requires hoist assistance.",
  "requestorEmail": "coordinator@hospital.com",
  "requestorName": "Dr. Sarah Johnson",
  "requestorPhone": "+447123456789",
  "address": "123 Main Street, London, SW1A 1AA",
  "postcode": "SW1A 1AA",
  "urgency": "MEDIUM",
  "requirements": "Personal Care, Medication Administration, Hoist Operation, Manual Handling",
  "estimatedDuration": 60,
  "scheduledStartTime": "2025-11-05T09:00:00Z",
  "scheduledEndTime": "2025-11-05T10:00:00Z",
  "notes": "Client prefers female carers. Previous carer was Christine Williams."
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "cmhkia2qc000acas105a1zwkw",
    "tenantId": "b2d8305b-bccf-4570-8d04-4ae5b1ddba8e",
    "subject": "Weekly Personal Care Visit",
    "content": "Client requires assistance with personal care, medication management, and light housekeeping. Client has mobility issues and requires hoist assistance.",
    "requestorEmail": "coordinator@hospital.com",
    "requestorName": "Dr. Sarah Johnson",
    "requestorPhone": "+447123456789",
    "address": "123 Main Street, London, SW1A 1AA",
    "postcode": "SW1A 1AA",
    "latitude": 51.5074,
    "longitude": -0.1278,
    "urgency": "MEDIUM",
    "status": "PENDING",
    "requirements": "Personal Care, Medication Administration, Hoist Operation, Manual Handling",
    "estimatedDuration": 60,
    "scheduledStartTime": "2025-11-05T09:00:00.000Z",
    "scheduledEndTime": "2025-11-05T10:00:00.000Z",
    "notes": "Client prefers female carers. Previous carer was Christine Williams.",
    "sendToRostering": false,
    "createdAt": "2025-11-04T14:16:12.000Z",
    "updatedAt": "2025-11-04T14:16:12.000Z"
  },
  "cluster": {
    "id": "cluster_123",
    "name": "Central London",
    "location": "51.5074, -0.1278"
  },
  "message": "Request created successfully"
}
```

### Approve Visit Request
**Purpose:** Approves a pending visit request, changing its status to APPROVED and making it available for rostering. **Data Sources:** Updates ExternalRequest status, triggers auto-matching, and sets sendToRostering flag.
**Method:** POST
**URL:** `http://localhost:9090/api/rostering/requests/cmhkia2qc000acas105a1zwkw/approve`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Request Body:**
```json
{
  "approvedBy": "coordinator@hospital.com",
  "sendToRostering": true,
  "notes": "Approved for rostering - matches client requirements"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "cmhkia2qc000acas105a1zwkw",
    "status": "APPROVED",
    "approvedBy": "coordinator@hospital.com",
    "approvedAt": "2025-11-04T14:16:14.000Z",
    "sendToRostering": true,
    "processedAt": "2025-11-04T14:16:14.000Z",
    "updatedAt": "2025-11-04T14:16:14.000Z"
  },
  "message": "Request approved and set to processing"
}
```

### Get Visit Requests
**Purpose:** Retrieves paginated list of visit requests for the tenant with optional filtering. **Data Sources:** Queries ExternalRequest table with optional status, date, and search filters.
**Method:** GET
**URL:** `http://localhost:9090/api/rostering/requests?page=1&limit=20&status=APPROVED`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Response:**
```json
{
  "data": [
    {
      "id": "cmhkia2qc000acas105a1zwkw",
      "subject": "Weekly Personal Care Visit",
      "requestorEmail": "coordinator@hospital.com",
      "address": "123 Main Street, London, SW1A 1AA",
      "status": "APPROVED",
      "urgency": "MEDIUM",
      "requirements": "Personal Care, Medication Administration",
      "estimatedDuration": 60,
      "scheduledStartTime": "2025-11-05T09:00:00.000Z",
      "createdAt": "2025-11-04T14:16:12.000Z",
      "matches": [
        {
          "id": "match_123",
          "status": "PENDING",
          "matchScore": 0.85,
          "distance": 2.3,
          "carer": {
            "id": "carer_456",
            "email": "carer@test.com",
            "firstName": "Christine",
            "lastName": "Williams"
          }
        }
      ]
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 1,
    "pages": 1,
    "hasNext": false,
    "hasPrev": false
  }
}
```

---

## Roster Generation

### Generate Balanced Scenarios
**Purpose:** Generates optimized roster scenarios using OR-Tools constraint programming with balanced weights for travel, continuity, and workload. **Data Sources:** Queries database for approved visits in date range, active carers, travel matrices, and historical carer-client matches.
**Method:** POST
**URL:** `http://localhost:9090/api/rostering/roster/generate`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Request Body:**
```json
{
  "startDate": "2024-12-05T00:00:00Z",
  "endDate": "2024-12-11T23:59:59Z",
  "strategy": "balanced",
  "generateScenarios": true,
  "clusterId": "cluster-123"
}
```

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": "scenario_balanced_1733356800000",
      "label": "Balanced (OR-Tools Optimized)",
      "strategy": "balanced",
      "assignments": [
        {
          "id": "assignment_123",
          "visitId": "visit-456",
          "carerId": "carer-789",
          "carerName": "Sarah Johnson",
          "scheduledTime": "2024-12-05T09:00:00.000Z",
          "estimatedEndTime": "2024-12-05T10:00:00.000Z",
          "travelFromPrevious": 15,
          "complianceChecks": {
            "wtdCompliant": true,
            "restPeriodOK": true,
            "travelTimeOK": true,
            "skillsMatch": true,
            "warnings": ["Optimized by OR-Tools constraint solver"]
          },
          "visitDetails": {
            "clientName": "Mary Smith",
            "address": "123 Main St, London",
            "duration": 60,
            "requirements": "Personal care, medication assistance"
          }
        }
      ],
      "metrics": {
        "totalTravel": 245,
        "continuityScore": 78.5,
        "violations": {
          "hard": 0,
          "soft": 2
        },
        "overtimeMinutes": 0,
        "averageCarerWorkload": 45.2
      },
      "score": 87.3
    }
  ]
}
```

### Generate Continuity Scenarios
**Purpose:** Generates roster scenarios prioritizing continuity of care (same carer-client relationships) using OR-Tools optimization. **Data Sources:** Queries database for approved visits in date range, active carers, travel matrices, and historical carer-client matches.
**Method:** POST
**URL:** `http://localhost:9090/api/rostering/roster/generate`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Request Body:**
```json
{
  "startDate": "2024-12-05T00:00:00Z",
  "endDate": "2024-12-11T23:59:59Z",
  "strategy": "continuity",
  "generateScenarios": true
}
```

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": "scenario_continuity_1733356800000",
      "label": "Continuity-First (OR-Tools Optimized)",
      "strategy": "continuity",
      "assignments": [...],
      "metrics": {
        "totalTravel": 312,
        "continuityScore": 92.1,
        "violations": {
          "hard": 0,
          "soft": 0
        },
        "overtimeMinutes": 0,
        "averageCarerWorkload": 48.7
      },
      "score": 89.8
    }
  ]
}
```

### Generate Travel Scenarios
**Purpose:** Generates roster scenarios minimizing carer travel time between visits using OR-Tools optimization. **Data Sources:** Queries database for approved visits in date range, active carers, travel matrices, and historical carer-client matches.
**Method:** POST
**URL:** `http://localhost:9090/api/rostering/roster/generate`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Request Body:**
```json
{
  "startDate": "2024-12-05T00:00:00Z",
  "endDate": "2024-12-11T23:59:59Z",
  "strategy": "travel",
  "generateScenarios": true
}
```

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": "scenario_travel_1733356800000",
      "label": "Travel-First (OR-Tools Optimized)",
      "strategy": "travel",
      "assignments": [...],
      "metrics": {
        "totalTravel": 189,
        "continuityScore": 65.4,
        "violations": {
          "hard": 0,
          "soft": 1
        },
        "overtimeMinutes": 0,
        "averageCarerWorkload": 42.1
      },
      "score": 85.6
    }
  ]
}
```

---

## Live Operations

### Update Carer Location
**Purpose:** Records real-time GPS location updates from carer mobile devices for live tracking and route optimization. **Data Sources:** Stores location data in CarerLocationUpdate table for real-time tracking and lateness prediction.
**Method:** POST
**URL:** `http://localhost:9090/api/rostering/live/location/carer-123`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Request Body:**
```json
{
  "latitude": 51.5074,
  "longitude": -0.1278,
  "accuracy": 10,
  "speed": 25,
  "heading": 90,
  "timestamp": "2024-12-05T10:30:00Z"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "carerId": "carer-123",
    "latitude": 51.5074,
    "longitude": -0.1278,
    "accuracy": 10,
    "recordedAt": "2024-12-05T10:30:00.000Z",
    "currentVisitId": "visit-456",
    "status": "on_time"
  }
}
```

### Visit Check-in
**Purpose:** Records carer arrival at client location with GPS verification and geofencing validation. **Data Sources:** Creates VisitCheckIn record and updates assignment status for real-time monitoring.
**Method:** POST
**URL:** `http://localhost:9090/api/rostering/live/visits/visit-123/check-in`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Request Body:**
```json
{
  "carerId": "carer-123",
  "latitude": 51.5074,
  "longitude": -0.1278,
  "accuracy": 5,
  "notes": "Arrived on time, client ready",
  "withinGeofence": true,
  "distanceFromVisit": 45
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "visitId": "visit-123",
    "carerId": "carer-123",
    "checkInTime": "2024-12-05T09:02:15.000Z",
    "latitude": 51.5074,
    "longitude": -0.1278,
    "withinGeofence": true,
    "distanceFromVisit": 45,
    "notes": "Arrived on time, client ready",
    "requiresApproval": false
  }
}
```

### Visit Check-out
**Purpose:** Records visit completion with actual duration, tasks performed, and incident reporting. **Data Sources:** Creates VisitCheckOut record, updates assignment with actual duration, and triggers timesheet calculations.
**Method:** POST
**URL:** `http://localhost:9090/api/rostering/live/visits/visit-123/check-out`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Request Body:**
```json
{
  "carerId": "carer-123",
  "latitude": 51.5074,
  "longitude": -0.1278,
  "actualDuration": 65,
  "tasksCompleted": ["Personal care", "Medication", "Light housekeeping"],
  "incidentReported": false,
  "notes": "Visit completed successfully"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "visitId": "visit-123",
    "carerId": "carer-123",
    "checkOutTime": "2024-12-05T10:07:30.000Z",
    "actualDuration": 65,
    "tasksCompleted": ["Personal care", "Medication", "Light housekeeping"],
    "incidentReported": false,
    "notes": "Visit completed successfully",
    "location": {
      "latitude": 51.5074,
      "longitude": -0.1278
    }
  }
}
```

### Get Live Dashboard
**Purpose:** Retrieves real-time operational metrics including active visits, on-time performance, and lateness alerts. **Data Sources:** Aggregates data from CarerLocationUpdate, VisitCheckIn, VisitCheckOut, and Assignment tables for live operational view.
**Method:** GET
**URL:** `http://localhost:9090/api/rostering/live/dashboard`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Response:**
```json
{
  "success": true,
  "data": {
    "activeVisits": 23,
    "completedToday": 145,
    "onTimePercentage": 0.87,
    "latenessAlerts": {
      "total": 12,
      "resolved": 10,
      "averageDelay": 8.5
    },
    "activeCarers": 18,
    "upcomingVisits": 45,
    "lastUpdated": "2024-12-05T10:35:00.000Z"
  }
}
```

---

## Disruption Management

### Report Carer Sick
**Purpose:** Reports carer unavailability due to illness, triggering automatic roster re-optimization and visit reassignment. **Data Sources:** Creates Disruption record and analyzes impact on assignments, then generates resolution options.
**Method:** POST
**URL:** `http://localhost:9090/api/rostering/disruptions`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Request Body:**
```json
{
  "type": "carer_sick",
  "severity": "high",
  "title": "Carer called in sick",
  "description": "Carer reported sick with flu symptoms",
  "affectedCarers": ["carer-123"],
  "affectedVisits": ["visit-123", "visit-124", "visit-125"],
  "impactData": {
    "visitsAffected": 3,
    "clientsAffected": 2,
    "estimatedDelay": 120
  },
  "location": {
    "latitude": 51.5074,
    "longitude": -0.1278
  }
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "disruption_1733356800000",
    "type": "carer_sick",
    "severity": "high",
    "title": "Carer called in sick",
    "description": "Carer reported sick with flu symptoms",
    "affectedCarers": ["carer-123"],
    "affectedVisits": ["visit-123", "visit-124", "visit-125"],
    "status": "reported",
    "reportedAt": "2024-12-05T10:40:00.000Z",
    "reportedBy": "coordinator-456",
    "impactData": {
      "visitsAffected": 3,
      "clientsAffected": 2,
      "estimatedDelay": 120
    },
    "resolutionOptions": [
      {
        "id": "res_redistribute_123",
        "type": "redistribute",
        "description": "Reassign visits to available carers",
        "estimatedTime": 30,
        "successProbability": 0.85
      },
      {
        "id": "res_cancel_123",
        "type": "cancel",
        "description": "Cancel affected visits",
        "estimatedTime": 5,
        "successProbability": 1.0
      }
    ]
  }
}
```

### Get Active Disruptions
**Purpose:** Retrieves all currently active disruptions requiring attention or resolution. **Data Sources:** Queries Disruption table for records with status 'REPORTED', 'ACKNOWLEDGED', or 'ANALYZING'.
**Method:** GET
**URL:** `http://localhost:9090/api/rostering/disruptions/active`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": "disruption_1733356800000",
      "type": "carer_sick",
      "severity": "high",
      "title": "Carer called in sick",
      "affectedVisits": 3,
      "status": "reported",
      "reportedAt": "2024-12-05T10:40:00.000Z",
      "timeSinceReport": "5 minutes ago"
    },
    {
      "id": "disruption_1733356900000",
      "type": "visit_cancelled",
      "severity": "medium",
      "title": "Client visit cancelled",
      "affectedVisits": 1,
      "status": "resolved",
      "resolvedAt": "2024-12-05T10:45:00.000Z",
      "timeSinceReport": "10 minutes ago"
    }
  ]
}
```

### Resolve Disruption
**Purpose:** Applies a resolution to a disruption, executing automated actions like visit reassignment. **Data Sources:** Updates Disruption record, creates DisruptionAction records, and triggers roster re-optimization if needed.
**Method:** POST
**URL:** `http://localhost:9090/api/rostering/disruptions/disruption-123/resolve`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Request Body:**
```json
{
  "resolutionId": "res_redistribute_123",
  "notes": "Visits reassigned to available carers",
  "resolvedBy": "coordinator-456"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "disruption_1733356800000",
    "status": "resolved",
    "resolvedAt": "2024-12-05T10:50:00.000Z",
    "resolvedBy": "coordinator-456",
    "resolution": "res_redistribute_123",
    "notes": "Visits reassigned to available carers",
    "actions": [
      {
        "id": "action_1733356800001",
        "actionType": "reassign_visit",
        "actionData": {
          "visitId": "visit-123",
          "fromCarerId": "carer-123",
          "toCarerId": "carer-789"
        },
        "performedAt": "2024-12-05T10:50:00.000Z",
        "success": true
      }
    ]
  }
}
```

---

## Analytics & Reporting

### Get Travel Analytics
**Purpose:** Retrieves travel time analytics showing OR-Tools optimization impact, cost savings, and travel distribution. **Data Sources:** Aggregates travel data from Assignment, TravelMatrixCache, and historical optimization results.
**Method:** GET
**URL:** `http://localhost:9090/api/rostering/analytics/travel`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Response:**
```json
{
  "success": true,
  "data": {
    "totalTravelTime": 12450,
    "averageTravelPerVisit": 18.5,
    "travelDistribution": {
      "0-10min": 234,
      "10-20min": 456,
      "20-30min": 123,
      "30min+": 45
    },
    "optimizationImpact": {
      "beforeORTools": 22.3,
      "afterORTools": 18.5,
      "improvement": 17.0,
      "costSavings": 1250
    },
    "period": "2024-11-01 to 2024-11-30",
    "lastUpdated": "2024-12-05T10:55:00.000Z"
  }
}
```

### Get WTD Compliance Report
**Purpose:** Generates Working Time Directive compliance report showing overtime violations and weekly breakdowns. **Data Sources:** Analyzes Timesheet, Assignment, and RosteringConstraints tables for compliance calculations.
**Method:** GET
**URL:** `http://localhost:9090/api/rostering/compliance/wtd?period=current_week`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Response:**
```json
{
  "success": true,
  "data": {
    "period": {
      "start": "2024-12-02T00:00:00.000Z",
      "end": "2024-12-08T23:59:59.000Z"
    },
    "complianceRate": 0.97,
    "totalCarers": 25,
    "compliantCarers": 24,
    "violations": [
      {
        "carerId": "carer-123",
        "carerName": "John Smith",
        "hoursWorked": 52.5,
        "limit": 48,
        "overtime": 4.5,
        "violations": 1
      }
    ],
    "weeklyBreakdown": [
      {
        "week": "2024-W49",
        "complianceRate": 0.96,
        "totalViolations": 1
      },
      {
        "week": "2024-W48",
        "complianceRate": 1.0,
        "totalViolations": 0
      }
    ],
    "generatedAt": "2024-12-05T11:00:00.000Z"
  }
}
```

### Get Quality Scores
**Purpose:** Retrieves overall roster quality metrics including continuity, travel efficiency, and improvement recommendations. **Data Sources:** Calculates metrics from Assignment, RequestCarerMatch, and historical optimization data.
**Method:** GET
**URL:** `http://localhost:9090/api/rostering/quality/scores`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Response:**
```json
{
  "success": true,
  "data": {
    "overallScore": 87.3,
    "components": {
      "continuity": 92.1,
      "travelEfficiency": 85.4,
      "workloadBalance": 88.7,
      "constraintCompliance": 95.2,
      "carerSatisfaction": 78.9
    },
    "trends": {
      "vsLastWeek": 2.1,
      "vsLastMonth": 5.3,
      "target": 90.0
    },
    "improvementOpportunities": [
      {
        "area": "carer_satisfaction",
        "current": 78.9,
        "target": 85.0,
        "recommendation": "Increase continuity preference weighting"
      }
    ],
    "period": "2024-11-01 to 2024-11-30",
    "lastUpdated": "2024-12-05T11:05:00.000Z"
  }
}
```

---

## System Health

### Health Check
**Purpose:** Performs basic service health check to verify the rostering service is running and responsive. **Data Sources:** Returns service status, uptime, memory usage, and basic connectivity information.
**Method:** GET
**URL:** `http://localhost:9090/health`

**Response:**
```json
{
  "status": "healthy",
  "service": "rostering",
  "timestamp": "2024-12-05T11:10:00.000Z",
  "uptime": 86400,
  "version": "2.1.0",
  "memory": {
    "rss": 156000000,
    "heapTotal": 128000000,
    "heapUsed": 89000000,
    "external": 2000000
  },
  "environment": "development"
}
```

### Service Status
**Purpose:** Retrieves detailed service status including feature availability, database connectivity, and WebSocket metrics. **Data Sources:** Checks database connections, WebSocket server status, and feature flag configurations.
**Method:** GET
**URL:** `http://localhost:9090/api/rostering/status`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Response:**
```json
{
  "success": true,
  "data": {
    "service": "rostering",
    "status": "operational",
    "version": "2.1.0",
    "features": {
      "dataValidation": true,
      "travelMatrix": true,
      "eligibilityPrecomputation": true,
      "clusterMetrics": true,
      "advancedOptimization": true,
      "publicationWorkflow": true,
      "liveOperations": true,
      "realTimeWebsockets": true,
      "disruptionManagement": true
    },
    "database": "connected",
    "websockets": {
      "available": true,
      "totalConnections": 15,
      "activeTenants": 3
    },
    "uptime": 86400,
    "lastHealthCheck": "2024-12-05T11:10:00.000Z"
  }
}
```

### WebSocket Status
**Purpose:** Retrieves real-time WebSocket connection metrics including active connections, message rates, and latency. **Data Sources:** Queries WebSocket server for active connections, tenant distribution, and performance metrics.
**Method:** GET
**URL:** `http://localhost:9090/api/rostering/ws/status`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Response:**
```json
{
  "success": true,
  "data": {
    "totalConnections": 15,
    "activeTenants": 3,
    "connectedTenants": ["tenant-1", "tenant-2", "tenant-3"],
    "connectionsByRole": {
      "carer": 8,
      "coordinator": 4,
      "manager": 3
    },
    "uptime": 345600,
    "messagesPerSecond": 2.3,
    "averageLatency": 45,
    "lastUpdated": "2024-12-05T11:15:00.000Z"
  }
}
```

### OR-Tools Optimizer Health
**Purpose:** Checks the health and performance metrics of the Google OR-Tools constraint programming solver. **Data Sources:** Returns OR-Tools service status, version info, optimization statistics, and performance metrics.
**Method:** GET
**URL:** `http://localhost:5000/health`

**Response:**
```json
{
  "status": "healthy",
  "service": "ortools-optimizer",
  "version": "1.0.0",
  "ortools_version": "9.8.3296",
  "uptime_seconds": 86400,
  "total_optimizations": 1247,
  "average_solve_time": 3.2,
  "success_rate": 0.98,
  "active_workers": 4,
  "last_health_check": "2024-12-05T11:20:00.000Z"
}
```

---

## Error Responses

### Authentication Error
**Status:** 401 Unauthorized

**Response:**
```json
{
  "success": false,
  "error": {
    "code": "AUTHENTICATION_FAILED",
    "message": "Invalid credentials provided",
    "details": "Email or password is incorrect"
  }
}
```

### Validation Error
**Status:** 400 Bad Request

**Response:**
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": {
      "startDate": "Start date must be in the future",
      "endDate": "End date must be after start date"
    }
  }
}
```

### OR-Tools Optimization Error
**Status:** 500 Internal Server Error

**Response:**
```json
{
  "success": false,
  "error": {
    "code": "OPTIMIZATION_FAILED",
    "message": "Failed to generate roster scenarios",
    "details": "OR-Tools solver could not find feasible solution. Consider relaxing constraints.",
    "optimizationDetails": {
      "status": "INFEASIBLE",
      "solveTime": 45.2,
      "constraintsChecked": 1250,
      "violationsFound": 3
    }
  }
}
```

### Rate Limit Exceeded
**Status:** 429 Too Many Requests

**Response:**
```json
{
  "success": false,
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests",
    "details": "Rate limit of 100 requests per 15 minutes exceeded",
    "retryAfter": 300
  }
}