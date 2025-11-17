# 📮 Postman Request Examples - Rostering Service

## Authentication

### Login - Coordinator
**Purpose:** Authenticates a coordinator user and returns a JWT token for subsequent API calls.
**Method:** POST
**URL:** `http://localhost:9090/api/auth/token/`

**Request Body:**
```json
{
  "email": "support@appbrew.com",
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

### Create Visit
**Purpose:** Creates a new visit directly (not from an approved request). Useful for emergency visits or manual scheduling.
**Method:** POST
**URL:** `http://localhost:9090/api/rostering/visits`

**Request Body:**
```json
{
  "subject": "Emergency Personal Care Visit",
  "content": "Client requires immediate personal care assistance due to family emergency",
  "requestorEmail": "client@example.com",
  "requestorName": "John Smith",
  "requestorPhone": "+447123456789",
  "address": "123 Main Street, London, SW1A 1AA",
  "postcode": "SW1A 1AA",
  "latitude": 51.5074,
  "longitude": -0.1278,
  "urgency": "HIGH",
  "requirements": "Personal Care, Emergency Response",
  "requiredSkills": ["Personal Care", "Emergency Response"],
  "estimatedDuration": 60,
  "scheduledStartTime": "2025-11-07T10:00:00Z",
  "scheduledEndTime": "2025-11-07T11:00:00Z",
  "recurrencePattern": null,
  "notes": "Emergency visit - family requested immediate assistance",
  "clusterId": "cluster-123"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "VISIT-20251106-ABC123",
    "subject": "Emergency Personal Care Visit",
    "content": "Client requires immediate personal care assistance due to family emergency",
    "requestorEmail": "client@example.com",
    "requestorName": "John Smith",
    "requestorPhone": "+447123456789",
    "address": "123 Main Street, London, SW1A 1AA",
    "postcode": "SW1A 1AA",
    "latitude": 51.5074,
    "longitude": -0.1278,
    "urgency": "HIGH",
    "requirements": "Personal Care, Emergency Response",
    "requiredSkills": ["Personal Care", "Emergency Response"],
    "estimatedDuration": 60,
    "scheduledStartTime": "2025-11-07T10:00:00Z",
    "scheduledEndTime": "2025-11-07T11:00:00Z",
    "recurrencePattern": null,
    "notes": "Emergency visit - family requested immediate assistance",
    "status": "SCHEDULED",
    "clusterId": "cluster-123",
    "createdBy": "user-123",
    "createdByEmail": "coordinator@hospital.com",
    "createdAt": "2025-11-07T10:00:00.000Z",
    "updatedAt": "2025-11-07T10:00:00.000Z"
  },
  "message": "Visit created successfully"
}
```

---

### Get Visits by Client ID
**Purpose:** Retrieves all visits for a specific client using their email address (requestorEmail).
**Method:** GET
**URL:** `http://localhost:9090/api/rostering/visits/client/{clientId}`

**Example URL:** `http://localhost:9090/api/rostering/visits/client/client@example.com`

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": "VISIT-20251106-ABC123",
      "subject": "Weekly Personal Care Visit",
      "scheduledStartTime": "2025-11-07T10:00:00.000Z",
      "status": "SCHEDULED",
      "externalRequest": {
        "id": "REQ-20251106-97ZZF",
        "subject": "Care request",
        "status": "APPROVED",
        "approvedAt": "2025-11-06T15:30:00.000Z"
      },
      "cluster": {
        "id": "cluster-123",
        "name": "North London"
      },
      "assignments": [
        {
          "id": "assignment-123",
          "carerId": "carer-456",
          "scheduledTime": "2025-11-07T10:00:00.000Z",
          "status": "ACCEPTED"
        }
      ]
    }
  ],
  "clientId": "client@example.com",
  "total": 1
}
```

---

### Assign Carer to Visit
**Purpose:** Manually assign a carer to a specific visit. This creates an assignment record linking the carer to the visit with scheduled times. The assignment will proceed even if skills don't match or availability requirements aren't met, but warnings will be generated.
**Method:** POST
**URL:** `http://localhost:9090/api/rostering/roster/assignments`

**Request Body:**
```json
{
  "visitId": "VISIT-20251106-ABC123",
  "carerId": "carer-456",
  "scheduledTime": "2025-11-07T10:00:00Z"
}
```

**Response (Successful with warnings):**
```json
{
  "success": true,
  "data": {
    "id": "assignment-123",
    "visitId": "VISIT-20251106-ABC123",
    "carerId": "carer-456",
    "scheduledTime": "2025-11-07T10:00:00.000Z",
    "estimatedEndTime": "2025-11-07T11:00:00.000Z",
    "status": "PENDING",
    "travelFromPrevious": 0,
    "manuallyAssigned": true,
    "warnings": [
      "Carer does not have all required skills",
      "Request time (10:00-11:00) does not match required availability slots for monday"
    ],
    "errors": []
  },
  "message": "Assignment created with warnings"
}
```

**Response (Successful without warnings):**
```json
{
  "success": true,
  "data": {
    "id": "assignment-123",
    "visitId": "VISIT-20251106-ABC123",
    "carerId": "carer-456",
    "scheduledTime": "2025-11-07T10:00:00.000Z",
    "estimatedEndTime": "2025-11-07T11:00:00.000Z",
    "status": "PENDING",
    "travelFromPrevious": 0,
    "manuallyAssigned": true,
    "warnings": [],
    "errors": []
  },
  "message": "Assignment created successfully"
}
```

---

### Generate Roster with Automatic Assignments
**Purpose:** Generate a complete roster for a date range with automatic carer assignments using optimization algorithms. This creates assignments for all eligible visits.
**Method:** POST
**URL:** `http://localhost:9090/api/rostering/roster/generate`

**Request Body:**
```json
{
  "startDate": "2025-11-07T00:00:00Z",
  "endDate": "2025-11-07T23:59:59Z",
  "strategy": "BALANCED",
  "includeTravelOptimization": true,
  "maxTravelTimeMinutes": 30
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "roster": {
      "id": "roster-123",
      "name": "Auto-generated Roster 2025-11-07",
      "startDate": "2025-11-07T00:00:00.000Z",
      "endDate": "2025-11-07T23:59:59.000Z",
      "status": "DRAFT",
      "totalAssignments": 15,
      "totalTravelMinutes": 45,
      "continuityScore": 78.5,
      "qualityScore": 85.2
    },
    "assignments": [
      {
        "id": "assignment-123",
        "visitId": "VISIT-20251106-ABC123",
        "carerId": "carer-456",
        "scheduledTime": "2025-11-07T10:00:00.000Z",
        "estimatedEndTime": "2025-11-07T11:00:00.000Z",
        "travelFromPrevious": 5,
        "status": "PENDING"
      }
    ],
    "metrics": {
      "totalTravelTime": 45,
      "continuityScore": 78.5,
      "violations": {
        "hard": 0,
        "soft": 2
      }
    }
  },
  "message": "Roster generated successfully with 15 assignments"
}
```

---

### Publish Roster for Carer Acceptance
**Purpose:** Publish a generated roster to carers for acceptance. Carers will receive notifications and can accept or decline their assignments.
**Method:** POST
**URL:** `http://localhost:9090/api/rostering/roster/{rosterId}/publish`

**Request Body:**
```json
{
  "acceptanceDeadline": "2025-11-06T18:00:00Z",
  "notificationChannels": ["push", "email"],
  "notes": "Please accept assignments by 6 PM"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "publication": {
      "id": "publication-123",
      "rosterId": "roster-123",
      "status": "ACTIVE",
      "acceptanceDeadline": "2025-11-06T18:00:00.000Z",
      "totalAssignments": 15,
      "acceptedCount": 0,
      "declinedCount": 0,
      "pendingCount": 15
    },
    "notificationsSent": 8,
    "carersNotified": 8
  },
  "message": "Roster published successfully"
}
```

---

### Accept Assignment (by Carer)
**Purpose:** Carer accepts a published assignment. This confirms the carer will perform the visit.
**Method:** POST
**URL:** `http://localhost:9090/api/rostering/publications/assignments/{assignmentId}/accept`

**Response:**
```json
{
  "success": true,
  "data": {
    "assignment": {
      "id": "assignment-123",
      "visitId": "VISIT-20251106-ABC123",
      "carerId": "carer-456",
      "status": "ACCEPTED",
      "acceptedAt": "2025-11-06T14:30:00.000Z"
    }
  },
  "message": "Assignment accepted successfully"
}
```

---

### Decline Assignment (by Carer)
**Purpose:** Carer declines a published assignment with an optional reason.
**Method:** POST
**URL:** `http://localhost:9090/api/rostering/publications/assignments/{assignmentId}/decline`

**Request Body:**
```json
{
  "reason": "Prior commitment"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "assignment": {
      "id": "assignment-123",
      "visitId": "VISIT-20251106-ABC123",
      "carerId": "carer-456",
      "status": "DECLINED",
      "declineReason": "Prior commitment",
      "declinedAt": "2025-11-06T14:30:00.000Z"
    }
  },
  "message": "Assignment declined"
}
```

---

### Reassign Visit to Different Carer
**Purpose:** Move an existing assignment from one carer to another. Useful for handling carer unavailability or optimization.
**Method:** POST
**URL:** `http://localhost:9090/api/rostering/roster/reassign`

**Request Body:**
```json
{
  "assignmentId": "assignment-123",
  "newCarerId": "carer-789"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "oldAssignment": {
      "id": "assignment-123",
      "carerId": "carer-456",
      "status": "CANCELLED"
    },
    "newAssignment": {
      "id": "assignment-456",
      "carerId": "carer-789",
      "status": "PENDING"
    }
  },
  "message": "Visit reassigned successfully"
}
```

---

### Create Public Visit Request
**Purpose:** Creates a new visit request publicly without authentication. The tenant ID is encoded in the request body. The request will be geocoded, assigned to a cluster (if AUTO_ASSIGN_REQUESTS=true), and automatically matched with available carers. **Data Sources:** Creates ExternalRequest record, geocodes address, assigns to cluster, triggers auto-matching.
**Method:** POST
**URL:** `http://localhost:9090/api/rostering/requests/public`
**Headers:** None (public endpoint)

**Request Body:**
```json
{
  "tenantId": "your-tenant-id-here",
  "subject": "Weekly Personal Care Visit",
  "content": "Client requires assistance with personal care, medication management, and light housekeeping. Client has mobility issues and requires hoist assistance.",
  "requestorEmail": "coordinator@hospital.com",
  "requestorName": "Dr. Sarah Johnson",
  "requestorPhone": "+447123456789",
  "address": "123 Main Street, London, SW1A 1AA",
  "postcode": "SW1A 1AA",
  "urgency": "MEDIUM",
  "requirements": "Personal Care, Medication Administration, Hoist Operation, Manual Handling",
  "requestTypes": "Personal Care, Medication Management",
  "estimatedDuration": 60,
  "scheduledStartTime": "2025-11-05T09:00:00Z",
  "scheduledEndTime": "2025-11-05T10:00:00Z",
  "notes": "Client prefers female carers. Previous carer was Christine Williams.",
  "availabilityRequirements": {
    "monday": [
      { "start": "08:00", "end": "09:00" },
      { "start": "12:00", "end": "14:00" },
      { "start": "16:00", "end": "21:00" }
    ],
    "tuesday": [
      { "start": "08:00", "end": "09:00" },
      { "start": "12:00", "end": "14:00" },
      { "start": "16:00", "end": "21:00" }
    ],
    "wednesday": null,
    "thursday": null,
    "friday": [
      { "start": "08:00", "end": "09:00" },
      { "start": "12:00", "end": "14:00" },
      { "start": "16:00", "end": "21:00" }
    ],
    "saturday": null,
    "sunday": null
  }
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "REQ-20251106-97ZZF",
    "tenantId": "your-tenant-id-here",
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
    "requestTypes": "Personal Care, Medication Management",
    "estimatedDuration": 60,
    "scheduledStartTime": "2025-11-05T09:00:00.000Z",
    "scheduledEndTime": "2025-11-05T10:00:00.000Z",
    "notes": "Client prefers female carers. Previous carer was Christine Williams.",
    "availabilityRequirements": {
      "monday": [
        { "start": "08:00", "end": "09:00" },
        { "start": "12:00", "end": "14:00" },
        { "start": "16:00", "end": "21:00" }
      ],
      "tuesday": [
        { "start": "08:00", "end": "09:00" },
        { "start": "12:00", "end": "14:00" },
        { "start": "16:00", "end": "21:00" }
      ],
      "wednesday": null,
      "thursday": null,
      "friday": [
        { "start": "08:00", "end": "09:00" },
        { "start": "12:00", "end": "14:00" },
        { "start": "16:00", "end": "21:00" }
      ],
      "saturday": null,
      "sunday": null
    },
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

---

### Create Visit
**Purpose:** Creates a new visit directly (bypassing the request approval process). Useful for emergency visits or when you need to create visits programmatically. **Data Sources:** Creates Visit record directly with provided details, links to external request if specified.
**Method:** POST
**URL:** `http://localhost:9090/api/rostering/visits`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Request Body:**
```json
{
  "subject": "Emergency Personal Care Visit",
  "content": "Client requires immediate personal care assistance due to family emergency",
  "requestorEmail": "client@example.com",
  "requestorName": "John Smith",
  "requestorPhone": "+447123456789",
  "address": "123 Main Street, London, SW1A 1AA",
  "postcode": "SW1A 1AA",
  "latitude": 51.5074,
  "longitude": -0.1278,
  "urgency": "HIGH",
  "requirements": "Personal Care, Emergency Response",
  "requiredSkills": ["Personal Care", "Emergency Response"],
  "estimatedDuration": 60,
  "scheduledStartTime": "2025-11-07T10:00:00Z",
  "scheduledEndTime": "2025-11-07T11:00:00Z",
  "recurrencePattern": null,
  "notes": "Emergency visit - family requested immediate assistance",
  "clusterId": "cluster-123"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "VISIT-20251107-ABC123",
    "tenantId": "b2d8305b-bccf-4570-8d04-4ae5b1ddba8e",
    "externalRequestId": "REQ-20251106-97ZZF",
    "subject": "Emergency Personal Care Visit",
    "content": "Client requires immediate personal care assistance due to family emergency",
    "requestorEmail": "client@example.com",
    "requestorName": "John Smith",
    "requestorPhone": "+447123456789",
    "address": "123 Main Street, London, SW1A 1AA",
    "postcode": "SW1A 1AA",
    "latitude": 51.5074,
    "longitude": -0.1278,
    "urgency": "HIGH",
    "status": "SCHEDULED",
    "isActive": true,
    "requirements": "Personal Care, Emergency Response",
    "requiredSkills": ["Personal Care", "Emergency Response"],
    "estimatedDuration": 60,
    "scheduledStartTime": "2025-11-07T10:00:00.000Z",
    "scheduledEndTime": "2025-11-07T11:00:00.000Z",
    "recurrencePattern": null,
    "notes": "Emergency visit - family requested immediate assistance",
    "clusterId": "cluster-123",
    "createdAt": "2025-11-07T09:00:00.000Z",
    "updatedAt": "2025-11-07T09:00:00.000Z",
    "createdBy": "coordinator-123",
    "createdByEmail": "coordinator@hospital.com"
  },
  "message": "Visit created successfully"
}
```

---

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
  "requestTypes": "Personal Care, Medication Management",
  "estimatedDuration": 60,
  "scheduledStartTime": "2025-11-05T09:00:00Z",
  "scheduledEndTime": "2025-11-05T10:00:00Z",
  "notes": "Client prefers female carers. Previous carer was Christine Williams.",
  "availabilityRequirements": {
    "monday": [
      { "start": "08:00", "end": "09:00" },
      { "start": "12:00", "end": "14:00" },
      { "start": "16:00", "end": "21:00" }
    ],
    "tuesday": [
      { "start": "08:00", "end": "09:00" },
      { "start": "12:00", "end": "14:00" },
      { "start": "16:00", "end": "21:00" }
    ],
    "wednesday": null,
    "thursday": null,
    "friday": [
      { "start": "08:00", "end": "09:00" },
      { "start": "12:00", "end": "14:00" },
      { "start": "16:00", "end": "21:00" }
    ],
    "saturday": null,
    "sunday": null
  }
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "REQ-20251106-97ZZF",
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
    "requestTypes": "Personal Care, Medication Management",
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
**URL:** `http://localhost:9090/api/rostering/requests/REQ-20251106-97ZZF/approve`
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
    "id": "REQ-20251106-97ZZF",
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


### **Check Request Feasibility with Comprehensive Scoring**

**Purpose:** Analyzes which carers can handle a specific visit request using a comprehensive scoring system (max 100 points) that evaluates:
- **Skills matching** (40 points)
- **Availability** (20 points) 
- **Cluster proximity** (15 points)
- **Continuity of care** (10 points)
- **Workload penalties** (up to -20 points)

**Method:** GET  
**URL:** `http://localhost:9090/api/rostering/requests/{requestId}/feasibility?includeScheduleCheck=true`  
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Query Parameters:**
- `includeScheduleCheck` (optional): Set to `true` to include detailed schedule conflict checking

---

## **Response Structure with Scoring Details**

### **Summary Section**
```json
"summary": {
  "totalCarers": 25,
  "preFilteredCarers": 20,
  "eligibleCarers": 3,
  "ineligibleCarers": 17,
  "alternativeOptions": 8,
  "checkedSchedule": true,
  "scoringUsed": true  // Indicates comprehensive scoring is active
}
```

### **Eligible Carers with Full Scoring Breakdown**
Each eligible carer includes complete scoring details:

```json
{
  "carerId": "carer-123",
  "carerName": "Jane Doe",
  "email": "jane.doe@careagency.com",
  
  // SCORING COMPONENTS:
  "employment": {
    "isEmployed": true,  // Blocking requirement - must be true
    "reason": ""
  },
  
  "skillsMatch": {
    "hasSomeRequired": true,      // +40 points if true
    "missingSkills": ["Medication Administration", "First Aid & CPR"],
    "matchingSkills": ["dementia care", "patient hygiene assistance"],
    "requirementsMatch": true
  },
  
  "availability": {
    "isAvailable": true,          // +20 points if true
    "conflicts": [],
    "suggestions": [],
    "availableHours": { ... }
  },
  
  "cluster": {
    "carerClusterId": "cluster-central",
    "visitClusterId": "cluster-central",
    "sameCluster": true,          // +15 points if true
    "bonus": 15
  },
  
  "continuity": {
    "bonus": 10,                  // Up to +10 points
    "previousVisits": 2           // 2 visits × 5 points = 10 points
  },
  
  "workload": {
    "currentWeeklyHours": 32.5,
    "utilizationPercent": 67.7,
    "penalty": 0                  // No penalty for moderate workload
  },
  
  // FINAL SCORE CALCULATION:
  "score": 85,                    // 40 + 20 + 15 + 10 + 0 = 85
  "overallEligible": true
}
```

### **Score Calculation Example**
```
Skills Match:      40 ✅ (hasSomeRequired: true)
Availability:      20 ✅ (isAvailable: true)  
Cluster Bonus:     15 ✅ (sameCluster: true)
Continuity:        10 ✅ (2 previous visits × 5)
Workload Penalty:   0 ✅ (32.5 hours - no penalty)
─────────────────────────────────────────────
TOTAL SCORE:       85 ✅
```

### **Ineligible Carers with Reasons**
Shows why carers were excluded and their partial scores:

```json
{
  "carerId": "carer-456",
  "carerName": "John Smith",
  "score": 0,
  "overallEligible": false,
  "skillsMatch": {
    "hasSomeRequired": false,     // ❌ Missing required skills = 0 points
    "missingSkills": ["Dementia Care", "Patient Hygiene Assistance", ...],
    "matchingSkills": []
  },
  "availability": {
    "isAvailable": false,         // ❌ Not available = 0 points
    "conflicts": ["Request time (8:00-11:00) is outside carer availability..."]
  },
  "workload": {
    "currentWeeklyHours": 45.0,
    "penalty": 20                 // ⚠️ High workload penalty
  }
}
```

### **Alternative Time Suggestions**
When carers aren't available at the requested time but have other availability:

```json
"alternativeOptions": [
  {
    "carerId": "carer-789",
    "carerName": "Emma Wilson",
    "score": 75,                  // Score for alternative time slot
    "skillsMatch": { ... },
    "day": "tuesday",
    "date": "2025-11-11",
    "startTime": "09:00",
    "endTime": "12:00",
    "duration": 3,
    "isPrimaryTime": false
  }
]
```

---

## **Key Features Visible in Response**

✅ **Full scoring breakdown** for each carer  
✅ **Individual component scores** (skills, availability, cluster, continuity, workload)  
✅ **Detailed eligibility reasons** for ineligible carers  
✅ **Alternative time suggestions** with scoring  
✅ **Workload utilization percentages**  
✅ **Skill matching details** (exact matches and missing skills)  
✅ **Cluster assignment information**  
✅ **Continuity history** (previous visits count)  

---

## **Scoring Thresholds & Eligibility**

- **Overall Eligible**: Requires ALL of:
  - ✅ `employment.isEmployed: true` (blocking requirement)
  - ✅ `skillsMatch.hasSomeRequired: true` (+40 points)
  - ✅ `availability.isAvailable: true` (+20 points)

- **No minimum score threshold** - eligibility is binary based on the three requirements above
- **Higher scores** indicate better matches considering cluster, continuity, and workload factors




The API provides complete transparency into the matching logic, making it easy to understand why specific carers were selected or excluded.
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
      "id": "REQ-20251106-97ZZF",
      "subject": "Weekly Personal Care Visit",
      "requestorEmail": "coordinator@hospital.com",
      "address": "123 Main Street, London, SW1A 1AA",
      "status": "APPROVED",
      "urgency": "MEDIUM",
      "requirements": "Personal Care, Medication Administration",
      "requestTypes": "Personal Care, Medication Management",
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

## Visit Management

### List Visits
**Purpose:** Retrieves paginated list of visits for the tenant with optional filtering. Only returns active visits (isActive: true). **Data Sources:** Queries Visit table with optional status, date, and search filters, including assigned carer information when available.
**Method:** GET
**URL:** `http://localhost:9090/api/rostering/visits?page=1&limit=20&status=SCHEDULED`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Response:**
```json
{
  "data": [
    {
      "id": "visit-123",
      "tenantId": "tenant-456",
      "externalRequestId": "req-789",
      "subject": "Weekly Personal Care Visit",
      "content": "Client requires assistance with personal care and medication",
      "requestorEmail": "coordinator@hospital.com",
      "requestorName": "Dr. Sarah Johnson",
      "address": "123 Main Street, London, SW1A 1AA",
      "postcode": "SW1A 1AA",
      "latitude": 51.5074,
      "longitude": -0.1278,
      "urgency": "MEDIUM",
      "status": "ASSIGNED",
      "isActive": true,
      "assignmentStatus": "ACCEPTED",
      "assignedAt": "2025-11-05T10:30:00.000Z",
      "travelFromPrevious": 15,
      "complianceChecks": {
        "wtdCompliant": true,
        "restPeriodOK": true,
        "travelTimeOK": true,
        "skillsMatch": true
      },
      "scheduledStartTime": "2025-11-05T09:00:00.000Z",
      "scheduledEndTime": "2025-11-05T10:00:00.000Z",
      "estimatedDuration": 60,
      "createdAt": "2025-11-04T14:16:12.000Z",
      "updatedAt": "2025-11-05T10:30:00.000Z",
      "assignedCarerId": "carer-123",
      "assignedCarerFirstName": "Jane",
      "assignedCarerLastName": "Doe",
      "assignedCarerEmail": "jane.doe@example.com",
      "assignedCarerSkills": ["Dementia Care", "Personal Care", "Medication Admin"],
      "assignedCarerAvailability": {
        "monday": {"start": "08:00", "end": "16:00", "available": true},
        "tuesday": {"start": "08:00", "end": "16:00", "available": true},
        "wednesday": {"start": "09:00", "end": "17:00", "available": true}
      },
      "externalRequest": {
        "id": "req-789",
        "subject": "Weekly Personal Care Request",
        "status": "APPROVED"
      },
      "cluster": {
        "id": "cluster-123",
        "name": "Central London"
      }
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

### Get Visit by ID
**Purpose:** Retrieves detailed information for a specific visit including assigned carer data when available. **Data Sources:** Queries Visit table with related ExternalRequest and Cluster data, including denormalized carer information.
**Method:** GET
**URL:** `http://localhost:9090/api/rostering/visits/VISIT-20251106-5777K`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Request Body:**
```json
{
  "assignmentStatus": "OFFERED",
  "travelFromPrevious": 20,
  "complianceChecks": {
    "wtdCompliant": true,
    "restPeriodOK": true,
    "travelTimeOK": true,
    "skillsMatch": true,
    "warnings": ["Optimized by OR-Tools"]
  },
  "notes": "Visit offered to carer for acceptance"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "visit-123",
    "tenantId": "tenant-456",
    "externalRequestId": "req-789",
    "subject": "Weekly Personal Care Visit",
    "content": "Client requires assistance with personal care and medication",
    "requestorEmail": "coordinator@hospital.com",
    "requestorName": "Dr. Sarah Johnson",
    "address": "123 Main Street, London, SW1A 1AA",
    "postcode": "SW1A 1AA",
    "latitude": 51.5074,
    "longitude": -0.1278,
    "urgency": "MEDIUM",
    "status": "ASSIGNED",
    "isActive": true,
    "assignmentStatus": "ACCEPTED",
    "assignedAt": "2025-11-05T10:30:00.000Z",
    "travelFromPrevious": 15,
    "complianceChecks": {
      "wtdCompliant": true,
      "restPeriodOK": true,
      "travelTimeOK": true,
      "skillsMatch": true
    },
    "scheduledStartTime": "2025-11-05T09:00:00.000Z",
    "scheduledEndTime": "2025-11-05T10:00:00.000Z",
    "estimatedDuration": 60,
    "createdAt": "2025-11-04T14:16:12.000Z",
    "updatedAt": "2025-11-05T10:30:00.000Z",
    "assignedCarerId": "carer-123",
    "assignedCarerFirstName": "Jane",
    "assignedCarerLastName": "Doe",
    "assignedCarerEmail": "jane.doe@example.com",
    "assignedCarerSkills": ["Dementia Care", "Personal Care", "Medication Admin"],
    "assignedCarerAvailability": {
      "monday": {"start": "08:00", "end": "16:00", "available": true},
      "tuesday": {"start": "08:00", "end": "16:00", "available": true},
      "wednesday": {"start": "09:00", "end": "17:00", "available": true}
    },
    "externalRequest": {
      "id": "req-789",
      "subject": "Weekly Personal Care Request",
      "status": "APPROVED",
      "approvedAt": "2025-11-04T15:00:00.000Z"
    },
    "assignments": [
      {
        "id": "assignment-456",
        "carerId": "carer-123",
        "scheduledTime": "2025-11-05T09:00:00.000Z",
        "status": "ACCEPTED"
      }
    ],
    "cluster": {
      "id": "cluster-123",
      "name": "Central London"
    }
  }
}
```

### Update Visit
**Purpose:** Updates visit information including assignment status, compliance checks, and carer assignment details. **Data Sources:** Updates Visit record with new field values, including denormalized carer data when assignment status changes.
**Method:** PUT
**URL:** `http://localhost:9090/api/rostering/visits/VISIT-20251106-5777K`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Request Body:**
```json
{
  "assignmentStatus": "OFFERED",
  "travelFromPrevious": 20,
  "complianceChecks": {
    "wtdCompliant": true,
    "restPeriodOK": true,
    "travelTimeOK": true,
    "skillsMatch": true,
    "warnings": ["Optimized by OR-Tools"]
  },
  "notes": "Visit offered to carer for acceptance"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "visit-123",
    "assignmentStatus": "OFFERED",
    "travelFromPrevious": 20,
    "complianceChecks": {
      "wtdCompliant": true,
      "restPeriodOK": true,
      "travelTimeOK": true,
      "skillsMatch": true,
      "warnings": ["Optimized by OR-Tools"]
    },
    "notes": "Visit offered to carer for acceptance",
    "updatedAt": "2025-11-05T11:00:00.000Z"
  },
  "message": "Visit updated successfully"
}
```

### Search Visits
**Purpose:** Searches visits with advanced filtering options. Only returns active visits. **Data Sources:** Queries Visit table with multiple filter criteria including assignment status, date ranges, and carer information.
**Method:** GET
**URL:** `http://localhost:9090/api/rostering/visits/search?assignmentStatus=ACCEPTED&dateFrom=2025-11-01T00:00:00Z&dateTo=2025-11-30T23:59:59Z`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": "visit-123",
      "subject": "Weekly Personal Care Visit",
      "assignmentStatus": "ACCEPTED",
      "assignedCarerFirstName": "Jane",
      "assignedCarerLastName": "Doe",
      "scheduledStartTime": "2025-11-05T09:00:00.000Z",
      "status": "ASSIGNED",
      "isActive": true
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

### Get Visits by Status
**Purpose:** Retrieves all visits with a specific status. Only returns active visits. **Data Sources:** Queries Visit table filtered by status and tenant, including assigned carer information.
**Method:** GET
**URL:** `http://localhost:9090/api/rostering/visits/status/ASSIGNED`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": "VISIT-20251106-5777K",
      "subject": "Weekly Personal Care Visit",
      "assignmentStatus": "ACCEPTED",
      "assignedCarerFirstName": "Jane",
      "assignedCarerLastName": "Doe",
      "assignedCarerEmail": "jane.doe@example.com",
      "scheduledStartTime": "2025-11-05T09:00:00.000Z",
      "status": "ASSIGNED",
      "isActive": true,
      "cluster": {
        "id": "cluster-123",
        "name": "Central London"
      }
    }
  ]
}
```

### Get Visits by Client ID
**Purpose:** Retrieves all visits for a specific client using their email address (client ID). Only returns active visits. **Data Sources:** Queries Visit table filtered by requestorEmail (client identifier) and tenant, including related external request and assignment information.
**Method:** GET
**URL:** `http://localhost:9090/api/rostering/visits/client/client@example.com`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": "VISIT-20251106-5777K",
      "tenantId": "b2d8305b-bccf-4570-8d04-4ae5b1ddba8e",
      "externalRequestId": "REQ-20251106-97ZZF",
      "subject": "Weekly Personal Care Visit",
      "content": "Client requires assistance with personal care and medication",
      "requestorEmail": "client@example.com",
      "requestorName": "John Smith",
      "address": "123 Main Street, London, SW1A 1AA",
      "postcode": "SW1A 1AA",
      "latitude": 51.5074,
      "longitude": -0.1278,
      "urgency": "MEDIUM",
      "status": "ASSIGNED",
      "isActive": true,
      "assignmentStatus": "ACCEPTED",
      "assignedAt": "2025-11-05T10:30:00.000Z",
      "scheduledStartTime": "2025-11-05T09:00:00.000Z",
      "scheduledEndTime": "2025-11-05T10:00:00.000Z",
      "estimatedDuration": 60,
      "createdAt": "2025-11-04T14:16:12.000Z",
      "updatedAt": "2025-11-05T10:30:00.000Z",
      "externalRequest": {
        "id": "REQ-20251106-97ZZF",
        "subject": "Weekly Personal Care Request",
        "status": "APPROVED",
        "approvedAt": "2025-11-04T15:00:00.000Z"
      },
      "assignments": [
        {
          "id": "assignment-456",
          "carerId": "carer-123",
          "scheduledTime": "2025-11-05T09:00:00.000Z",
          "status": "ACCEPTED"
        }
      ],
      "cluster": {
        "id": "cluster-123",
        "name": "Central London"
      }
    }
  ],
  "clientId": "client@example.com",
  "total": 1
}
```

---

## Carer Assignment Management

### Accept Visit Offer
**Purpose:** Allows a carer to accept a visit offer that has been assigned to them. Updates visit assignment status and populates assigned carer information. **Data Sources:** Updates Visit record with ACCEPTED status and denormalizes carer data from auth service.
**Method:** PUT
**URL:** `http://localhost:9090/api/rostering/carers/carer-123/visits/VISIT-20251106-5777K/accept`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "visit-456",
    "assignmentStatus": "ACCEPTED",
    "assignedAt": "2025-11-05T14:30:00.000Z",
    "status": "ASSIGNED",
    "assignedCarerId": "carer-123",
    "assignedCarerFirstName": "Jane",
    "assignedCarerLastName": "Doe",
    "assignedCarerEmail": "jane.doe@example.com",
    "assignedCarerSkills": ["Dementia Care", "Personal Care", "Medication Admin"],
    "assignedCarerAvailability": {
      "monday": {"start": "08:00", "end": "16:00", "available": true},
      "tuesday": {"start": "08:00", "end": "16:00", "available": true}
    },
    "updatedAt": "2025-11-05T14:30:00.000Z"
  },
  "message": "Visit offer accepted successfully"
}
```

### Decline Visit Offer
**Purpose:** Allows a carer to decline a visit offer with an optional reason. Updates visit assignment status and stores decline information. **Data Sources:** Updates Visit record with DECLINED status and stores decline reason in complianceChecks.
**Method:** PUT
**URL:** `http://localhost:9090/api/rostering/carers/carer-123/visits/VISIT-20251106-5777K/decline`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Request Body:**
```json
{
  "reason": "Schedule conflict with existing appointment"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "VISIT-20251106-5777K",
    "assignmentStatus": "DECLINED",
    "complianceChecks": {
      "declinedReason": "Schedule conflict with existing appointment",
      "declinedAt": "2025-11-05T14:35:00.000Z",
      "declinedBy": "carer-123"
    },
    "updatedAt": "2025-11-05T14:35:00.000Z"
  },
  "message": "Visit offer declined successfully"
}
```

### Get Offered Visits for Carer
**Purpose:** Retrieves all visit offers currently available for a specific carer to accept or decline. **Data Sources:** Queries Visit table for records with assignmentStatus=OFFERED and isActive=true for the specified carer.
**Method:** GET
**URL:** `http://localhost:9090/api/rostering/carers/carer-123/visits/offered`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": "VISIT-20251106-5777K",
      "subject": "Weekly Personal Care Visit",
      "content": "Client requires assistance with personal care and medication",
      "address": "123 Main Street, London, SW1A 1AA",
      "scheduledStartTime": "2025-11-05T09:00:00.000Z",
      "scheduledEndTime": "2025-11-05T10:00:00.000Z",
      "estimatedDuration": 60,
      "urgency": "MEDIUM",
      "assignmentStatus": "OFFERED",
      "travelFromPrevious": 15,
      "complianceChecks": {
        "wtdCompliant": true,
        "restPeriodOK": true,
        "travelTimeOK": true,
        "skillsMatch": true
      },
      "externalRequest": {
        "id": "req-789",
        "subject": "Weekly Personal Care Request",
        "status": "APPROVED"
      },
      "cluster": {
        "id": "cluster-123",
        "name": "Central London"
      }
    }
  ]
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

## Cluster Assignment & Distance Calculation

### Get Intelligent Cluster Suggestions for Client
**Purpose:** Retrieves intelligent cluster suggestions for a specific client based on distance, skill compatibility, time windows, and carer availability. Uses multi-factor scoring algorithm to rank clusters by suitability. **Data Sources:** Queries ClientClusterDistance cache, geocodes client postcode if needed, analyzes cluster metrics and carer availability.
**Method:** GET
**URL:** `http://localhost:9090/api/rostering/clusters/clients/{clientId}/suggestions?maxSuggestions=3&maxDistanceKm=50&includeInactiveClusters=false`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Query Parameters:**
- `maxSuggestions` (optional): Maximum number of suggestions to return (default: 3)
- `maxDistanceKm` (optional): Maximum distance in kilometers to consider (default: 50)
- `includeInactiveClusters` (optional): Include clusters with no active requests (default: false)

**Example URL:** `http://localhost:9090/api/rostering/clusters/clients/REQ-20251106-97ZZF/suggestions?maxSuggestions=3&maxDistanceKm=25`

**Response:**
```json
{
  "success": true,
  "data": {
    "clientId": "REQ-20251106-97ZZF",
    "clientName": "Weekly Personal Care Visit",
    "clientPostcode": "SW1A 1AA",
    "clientCoordinates": {
      "latitude": 51.5074,
      "longitude": -0.1278
    },
    "suggestions": [
      {
        "clusterId": "cluster_123",
        "clusterName": "Central London Hub",
        "distanceKm": 2.3,
        "centroidCoordinates": {
          "latitude": 51.5080,
          "longitude": -0.1280
        },
        "score": 87.5,
        "reasoning": [
          "Within 5km - good proximity",
          "Excellent skill coverage available",
          "Time windows align well",
          "Good carer availability"
        ],
        "availableCarers": 5,
        "timeCompatibility": 0.9,
        "skillMatch": 0.85
      },
      {
        "clusterId": "cluster_456",
        "clusterName": "Westminster District",
        "distanceKm": 1.8,
        "centroidCoordinates": {
          "latitude": 51.4994,
          "longitude": -0.1245
        },
        "score": 82.3,
        "reasoning": [
          "Within 2km - excellent proximity",
          "Good skill coverage available",
          "Time windows partially compatible",
          "Limited carer availability"
        ],
        "availableCarers": 2,
        "timeCompatibility": 0.7,
        "skillMatch": 0.8
      },
      {
        "clusterId": "cluster_789",
        "clusterName": "South Bank Area",
        "distanceKm": 4.1,
        "centroidCoordinates": {
          "latitude": 51.5055,
          "longitude": -0.0754
        },
        "score": 75.8,
        "reasoning": [
          "Within 5km - good proximity",
          "Limited skill coverage - may need additional training",
          "Time windows may conflict",
          "Good carer availability"
        ],
        "availableCarers": 4,
        "timeCompatibility": 0.6,
        "skillMatch": 0.4
      }
    ],
    "topSuggestion": {
      "clusterId": "cluster_123",
      "clusterName": "Central London Hub",
      "distanceKm": 2.3,
      "centroidCoordinates": {
        "latitude": 51.5080,
        "longitude": -0.1280
      },
      "score": 87.5,
      "reasoning": [
        "Within 5km - good proximity",
        "Excellent skill coverage available",
        "Time windows align well",
        "Good carer availability"
      ],
      "availableCarers": 5,
      "timeCompatibility": 0.9,
      "skillMatch": 0.85
    }
  }
}
```

---

### Get Batch Cluster Suggestions for Multiple Clients
**Purpose:** Processes multiple clients simultaneously to get cluster suggestions, optimizing for batch geocoding and distance calculations. Useful for bulk assignment workflows. **Data Sources:** Batch processes ClientClusterDistance cache, geocodes postcodes in batches, analyzes cluster metrics for all clients.
**Method:** POST
**URL:** `http://localhost:9090/api/rostering/clusters/clients/batch-suggestions?maxSuggestions=3&maxDistanceKm=50&includeInactiveClusters=false`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Query Parameters:**
- `maxSuggestions` (optional): Maximum number of suggestions per client (default: 3)
- `maxDistanceKm` (optional): Maximum distance in kilometers to consider (default: 50)
- `includeInactiveClusters` (optional): Include clusters with no active requests (default: false)

**Request Body:**
```json
{
  "clientIds": [
    "REQ-20251106-97ZZF",
    "REQ-20251106-98XZY",
    "REQ-20251106-99ABC"
  ]
}
```

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "clientId": "REQ-20251106-97ZZF",
      "clientName": "Weekly Personal Care Visit",
      "clientPostcode": "SW1A 1AA",
      "clientCoordinates": {
        "latitude": 51.5074,
        "longitude": -0.1278
      },
      "suggestions": [
        {
          "clusterId": "cluster_123",
          "clusterName": "Central London Hub",
          "distanceKm": 2.3,
          "centroidCoordinates": {
            "latitude": 51.5080,
            "longitude": -0.1280
          },
          "score": 87.5,
          "reasoning": [
            "Within 5km - good proximity",
            "Excellent skill coverage available",
            "Time windows align well",
            "Good carer availability"
          ],
          "availableCarers": 5,
          "timeCompatibility": 0.9,
          "skillMatch": 0.85
        }
      ],
      "topSuggestion": {
        "clusterId": "cluster_123",
        "clusterName": "Central London Hub",
        "distanceKm": 2.3,
        "centroidCoordinates": {
          "latitude": 51.5080,
          "longitude": -0.1280
        },
        "score": 87.5,
        "reasoning": [
          "Within 5km - good proximity",
          "Excellent skill coverage available",
          "Time windows align well",
          "Good carer availability"
        ],
        "availableCarers": 5,
        "timeCompatibility": 0.9,
        "skillMatch": 0.85
      }
    },
    {
      "clientId": "REQ-20251106-98XZY",
      "clientName": "Dementia Care Support",
      "clientPostcode": "N1 9AL",
      "clientCoordinates": {
        "latitude": 51.5308,
        "longitude": -0.0973
      },
      "suggestions": [
        {
          "clusterId": "cluster_456",
          "clusterName": "North London District",
          "distanceKm": 1.2,
          "centroidCoordinates": {
            "latitude": 51.5280,
            "longitude": -0.0990
          },
          "score": 91.2,
          "reasoning": [
            "Within 2km - excellent proximity",
            "Excellent skill coverage available",
            "Time windows align well",
            "Good carer availability"
          ],
          "availableCarers": 6,
          "timeCompatibility": 0.95,
          "skillMatch": 0.9
        }
      ],
      "topSuggestion": {
        "clusterId": "cluster_456",
        "clusterName": "North London District",
        "distanceKm": 1.2,
        "centroidCoordinates": {
          "latitude": 51.5280,
          "longitude": -0.0990
        },
        "score": 91.2,
        "reasoning": [
          "Within 2km - excellent proximity",
          "Excellent skill coverage available",
          "Time windows align well",
          "Good carer availability"
        ],
        "availableCarers": 6,
        "timeCompatibility": 0.95,
        "skillMatch": 0.9
      }
    },
    {
      "clientId": "REQ-20251106-99ABC",
      "clientName": "Medication Management",
      "clientPostcode": "SE1 7HR",
      "clientCoordinates": {
        "latitude": 51.4994,
        "longitude": -0.1245
      },
      "suggestions": [
        {
          "clusterId": "cluster_789",
          "clusterName": "Southwark Area",
          "distanceKm": 0.8,
          "centroidCoordinates": {
            "latitude": 51.4980,
            "longitude": -0.1250
          },
          "score": 89.7,
          "reasoning": [
            "Within 2km - excellent proximity",
            "Good skill coverage available",
            "Time windows align well",
            "Excellent carer availability"
          ],
          "availableCarers": 8,
          "timeCompatibility": 0.85,
          "skillMatch": 0.75
        }
      ],
      "topSuggestion": {
        "clusterId": "cluster_789",
        "clusterName": "Southwark Area",
        "distanceKm": 0.8,
        "centroidCoordinates": {
          "latitude": 51.4980,
          "longitude": -0.1250
        },
        "score": 89.7,
        "reasoning": [
          "Within 2km - excellent proximity",
          "Good skill coverage available",
          "Time windows align well",
          "Excellent carer availability"
        ],
        "availableCarers": 8,
        "timeCompatibility": 0.85,
        "skillMatch": 0.75
      }
    }
  ],
  "summary": {
    "totalClients": 3,
    "processedClients": 3,
    "averageSuggestionsPerClient": 1,
    "averageDistanceKm": 1.43,
    "averageScore": 89.47
  }
}
```

---

### Assign Visit to Cluster
**Purpose:** Assigns an existing visit to a different cluster by updating the visit's clusterId. This reassigns visits between clusters and updates cluster statistics. **Data Sources:** Updates Visit record clusterId, updates statistics for both old and new clusters.
**Method:** POST
**URL:** `http://localhost:9090/api/rostering/clusters/{clusterId}/assign-visit/{visitId}`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Example URL:** `http://localhost:9090/api/rostering/clusters/cluster-456/assign-visit/VISIT-20251108-ABC123`

**Response (Success):**
```json
{
  "success": true,
  "data": {
    "visit": {
      "id": "VISIT-20251108-ABC123",
      "tenantId": "tenant-456",
      "subject": "Weekly Personal Care Visit",
      "clusterId": "cluster-456",
      "status": "SCHEDULED",
      "updatedAt": "2025-11-08T08:50:00.000Z"
    },
    "cluster": {
      "id": "cluster-456",
      "name": "North London District",
      "previousClusterId": "cluster-123"
    }
  },
  "message": "Visit reassigned to cluster 'North London District' successfully"
}
```

**Response (Already Assigned):**
```json
{
  "success": false,
  "error": "Visit is already assigned to this cluster",
  "visitId": "VISIT-20251108-ABC123",
  "currentClusterId": "cluster-456"
}
```

---

### Batch Assign Visits to Clusters
**Purpose:** Reassigns multiple existing visits to different clusters in a single operation. Useful for bulk cluster rebalancing and optimization. **Data Sources:** Batch updates Visit records with new clusterId values, updates statistics for all affected clusters.
**Method:** POST
**URL:** `http://localhost:9090/api/rostering/clusters/batch-assign-visits`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Request Body:**
```json
{
  "assignments": [
    {
      "clusterId": "cluster-456",
      "visitId": "VISIT-20251108-ABC123"
    },
    {
      "clusterId": "cluster-789",
      "visitId": "VISIT-20251108-DEF456"
    },
    {
      "clusterId": "cluster-123",
      "visitId": "VISIT-20251108-GHI789"
    }
  ]
}
```

**Response (Success):**
```json
{
  "success": true,
  "data": {
    "successful": [
      {
        "assignment": {
          "clusterId": "cluster-456",
          "visitId": "VISIT-20251108-ABC123"
        },
        "visit": {
          "id": "VISIT-20251108-ABC123",
          "subject": "Weekly Personal Care Visit",
          "clusterId": "cluster-456",
          "status": "SCHEDULED",
          "updatedAt": "2025-11-08T08:55:00.000Z"
        },
        "cluster": {
          "id": "cluster-456",
          "name": "North London District",
          "previousClusterId": "cluster-123"
        },
        "success": true
      },
      {
        "assignment": {
          "clusterId": "cluster-789",
          "visitId": "VISIT-20251108-DEF456"
        },
        "visit": {
          "id": "VISIT-20251108-DEF456",
          "subject": "Dementia Care Support",
          "clusterId": "cluster-789",
          "status": "SCHEDULED",
          "updatedAt": "2025-11-08T08:55:00.000Z"
        },
        "cluster": {
          "id": "cluster-789",
          "name": "Southwark Area",
          "previousClusterId": "cluster-456"
        },
        "success": true
      }
    ],
    "failed": [
      {
        "assignment": {
          "clusterId": "cluster-123",
          "visitId": "VISIT-20251108-GHI789"
        },
        "error": "Visit is already assigned to this cluster",
        "currentClusterId": "cluster-123"
      }
    ],
    "summary": {
      "total": 3,
      "successful": 2,
      "failed": 1,
      "affectedClusters": ["cluster-123", "cluster-456", "cluster-789"]
    }
  },
  "message": "Batch reassignment completed: 2 successful, 1 failed"
}
```

---

### Get Cluster Distance Analytics
**Purpose:** Retrieves distance analytics showing client-to-cluster distribution, average distances by region, and optimization opportunities. **Data Sources:** Aggregates ClientClusterDistance cache data, analyzes geographic patterns and distance distributions.
**Method:** GET
**URL:** `http://localhost:9090/api/rostering/clusters/analytics/distances?period=30days`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Query Parameters:**
- `period` (optional): Time period for analysis (default: 30days, options: 7days, 30days, 90days)

**Response:**
```json
{
  "success": true,
  "data": {
    "period": {
      "start": "2025-10-09T00:00:00.000Z",
      "end": "2025-11-08T23:59:59.000Z"
    },
    "distanceMetrics": {
      "totalCalculations": 1247,
      "averageDistanceKm": 3.2,
      "medianDistanceKm": 2.8,
      "distanceDistribution": {
        "0-1km": 234,
        "1-2km": 345,
        "2-5km": 423,
        "5-10km": 198,
        "10km+": 47
      },
      "longestDistance": {
        "clientPostcode": "SW1A 1AA",
        "clusterId": "cluster_999",
        "distanceKm": 15.7
      },
      "shortestDistance": {
        "clientPostcode": "N1 9AL",
        "clusterId": "cluster_456",
        "distanceKm": 0.3
      }
    },
    "regionalAnalysis": {
      "Central London": {
        "clientCount": 156,
        "averageDistanceKm": 1.8,
        "clusters": ["cluster_123", "cluster_456"]
      },
      "North London": {
        "clientCount": 89,
        "averageDistanceKm": 2.1,
        "clusters": ["cluster_789", "cluster_012"]
      },
      "South London": {
        "clientCount": 67,
        "averageDistanceKm": 3.4,
        "clusters": ["cluster_345", "cluster_678"]
      }
    },
    "optimizationOpportunities": [
      {
        "type": "new_cluster",
        "region": "East London",
        "clientCount": 45,
        "averageDistanceToNearest": 8.2,
        "recommendedLocation": {
          "latitude": 51.5074,
          "longitude": -0.0678
        }
      },
      {
        "type": "cluster_expansion",
        "clusterId": "cluster_999",
        "currentRadiusKm": 5.0,
        "recommendedRadiusKm": 7.5,
        "additionalClients": 23
      }
    ],
    "cachePerformance": {
      "hitRate": 0.87,
      "totalQueries": 1456,
      "cacheHits": 1267,
      "cacheMisses": 189,
      "averageResponseTimeMs": 45
    },
    "lastUpdated": "2025-11-08T08:35:00.000Z"
  }
}
```

---

## Travel Matrix API

### Calculate Travel Time and Distance
**Purpose:** Calculates travel time and distance between two locations using Google Maps API with intelligent caching and precision levels. Supports address, postcode, and coordinate inputs with automatic geocoding.
**Method:** POST
**URL:** `http://localhost:9090/api/rostering/travel-matrix/calculate`

**Request Body:**
```json
{
  "from": {
    "address": "123 Main Street, London, SW1A 1AA",
    "postcode": "SW1A 1AA",
    "latitude": 51.5074,
    "longitude": -0.1278
  },
  "to": {
    "address": "456 High Street, Manchester, M1 1AA",
    "postcode": "M1 1AA",
    "latitude": 53.4808,
    "longitude": -2.2426
  },
  "mode": "driving",
  "forceRefresh": false
}
```

**Response (Success):**
```json
{
  "success": true,
  "data": {
    "distance": {
      "meters": 262187,
      "kilometers": 262.187,
      "text": "262 km"
    },
    "duration": {
      "seconds": 10260,
      "minutes": 171,
      "text": "171 mins"
    },
    "trafficDuration": {
      "seconds": 10800,
      "minutes": 180,
      "text": "180 mins"
    },
    "from": {
      "address": "123 Main Street, London, SW1A 1AA",
      "postcode": "SW1A 1AA",
      "geocoded": "123 Main St, London SW1A 1AA, UK",
      "coordinates": {
        "latitude": 51.5074,
        "longitude": -0.1278
      }
    },
    "to": {
      "address": "456 High Street, Manchester, M1 1AA",
      "postcode": "M1 1AA",
      "geocoded": "456 High St, Manchester M1 1AA, UK",
      "coordinates": {
        "latitude": 53.4808,
        "longitude": -2.2426
      }
    },
    "mode": "driving",
    "precisionLevel": "ADDRESS",
    "cached": false,
    "calculatedAt": "2025-11-10T15:30:00.000Z",
    "expiresAt": "2025-11-10T16:30:00.000Z",
    "warnings": []
  }
}
```

**Response (Cached):**
```json
{
  "success": true,
  "data": {
    "distance": {
      "meters": 262187,
      "kilometers": 262.187,
      "text": "262 km"
    },
    "duration": {
      "seconds": 10260,
      "minutes": 171,
      "text": "171 mins"
    },
    "from": {
      "address": "123 Main Street, London, SW1A 1AA",
      "postcode": "SW1A 1AA",
      "geocoded": "123 Main St, London SW1A 1AA, UK",
      "coordinates": {
        "latitude": 51.5074,
        "longitude": -0.1278
      }
    },
    "to": {
      "address": "456 High Street, Manchester, M1 1AA",
      "postcode": "M1 1AA",
      "geocoded": "456 High St, Manchester M1 1AA, UK",
      "coordinates": {
        "latitude": 53.4808,
        "longitude": -2.2426
      }
    },
    "mode": "driving",
    "precisionLevel": "ADDRESS",
    "cached": true,
    "calculatedAt": "2025-11-10T15:25:00.000Z",
    "expiresAt": "2025-11-10T16:25:00.000Z",
    "warnings": []
  }
}
```

**Response (Postcode Precision):**
```json
{
  "success": true,
  "data": {
    "distance": {
      "meters": 260000,
      "kilometers": 260,
      "text": "260 km"
    },
    "duration": {
      "seconds": 10080,
      "minutes": 168,
      "text": "168 mins"
    },
    "from": {
      "postcode": "SW1A 1AA",
      "geocoded": "SW1A 1AA, UK",
      "coordinates": {
        "latitude": 51.5074,
        "longitude": -0.1278
      }
    },
    "to": {
      "postcode": "M1 1AA",
      "geocoded": "M1 1AA, UK",
      "coordinates": {
        "latitude": 53.4808,
        "longitude": -2.2426
      }
    },
    "mode": "driving",
    "precisionLevel": "POSTCODE",
    "cached": false,
    "calculatedAt": "2025-11-10T15:30:00.000Z",
    "expiresAt": "2025-11-11T15:30:00.000Z",
    "warnings": [
      {
        "type": "APPROXIMATE_LOCATION",
        "message": "Using postcode centroid - actual distance may vary by ±200-500m",
        "severity": "info"
      }
    ]
  }
}
```

**Response (Error - Invalid Input):**
```json
{
  "success": false,
  "error": "Travel Calculation Failed",
  "message": "Travel calculation failed: Invalid \"from\" location: must provide address, postcode, or coordinates",
  "stack": "Error: Travel calculation failed: Invalid \"from\" location: must provide address, postcode, or coordinates\n    at EnhancedTravelService.calculateTravel (/app/dist/services/enhanced-travel.service.js:52:19)\n    at process.processTicksAndRejections (node:internal/process/task_queues:95:5)\n    at async EnhancedTravelMatrixController.calculateTravel (/app/dist/controllers/enhanced-travel-matrix.controller.js:20:32)"
}
```

**Response (Error - Google Maps API):**
```json
{
  "success": false,
  "error": "Travel Calculation Failed",
  "message": "Travel calculation failed: Google Maps API error: REQUEST_DENIED - You must use an API key to authenticate each request to Google Maps Platform APIs. For additional information, please refer to http://g.co/dev/maps-no-account",
  "stack": "Error: Travel calculation failed: Google Maps API error: REQUEST_DENIED - You must use an API key to authenticate each request to Google Maps Platform APIs. For additional information, please refer to http://g.co/dev/maps-no-account\n    at EnhancedTravelService.calculateTravel (/app/dist/services/enhanced-travel.service.js:52:19)\n    at process.processTicksAndRejections (node:internal/process/task_queues:95:5)\n    at async EnhancedTravelMatrixController.calculateTravel (/app/dist/controllers/enhanced-travel-matrix.controller.js:20:32)"
}
```

### Get Travel Matrix Cache Statistics
**Purpose:** Retrieves statistics about the travel matrix cache including hit rates, precision levels, and expiry information.
**Method:** GET
**URL:** `http://localhost:9090/api/rostering/travel-matrix/cache/stats`

**Response:**
```json
{
  "success": true,
  "data": {
    "total": 1250,
    "byPrecision": {
      "address": 450,
      "postcode": 700,
      "coordinates": 100
    },
    "expired": 45,
    "active": 1205
  }
}
```

### Clean Up Expired Travel Matrix Cache
**Purpose:** Removes expired travel matrix cache entries to free up database space.
**Method:** DELETE
**URL:** `http://localhost:9090/api/rostering/travel-matrix/cache/cleanup`

**Response:**
```json
{
  "success": true,
  "message": "Cleaned up 45 expired cache entries",
  "data": {
    "deletedCount": 45
  }
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