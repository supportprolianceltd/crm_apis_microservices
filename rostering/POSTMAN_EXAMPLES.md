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

### Check Request Feasibility
**Purpose:** Analyzes which carers can handle a specific visit request based on skills, availability, and schedule compatibility. **Data Sources:** Queries auth service for carer profiles, checks skills matching against required skills, validates availability against request time, and optionally checks for schedule conflicts.
**Method:** GET
**URL:** `http://localhost:9090/api/rostering/requests/REQ-20251106-97ZZF/feasibility?includeScheduleCheck=true`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Response:**
```json
{
  "success": true,
  "data": {
    "requestId": "REQ-20251106-97ZZF",
    "requestDetails": {
      "subject": "Morning Dementia Care Support - Mr. Adewale Johnson",
      "scheduledStartTime": "2025-11-10T08:00:00.000Z",
      "scheduledEndTime": "2025-11-10T11:00:00.000Z",
      "estimatedDuration": 180,
      "requiredSkills": [
        "Dementia Care",
        "Patient Hygiene Assistance",
        "Medication Administration",
        "First Aid & CPR"
      ],
      "requirements": "Carer must be experienced in dementia and personal care, have valid DBS, and be available weekday mornings."
    },
    "summary": {
      "totalCarers": 6,
      "eligibleCarers": 1,
      "ineligibleCarers": 5,
      "checkedSchedule": true
    },
    "eligibleCarers": [
      {
        "carerId": 50,
        "carerName": "Jane Doe",
        "email": "ekeneonwon@appbrew.com",
        "skills": [
          {
            "id": 1,
            "skill_name": "Patient Hygiene Assistance",
            "proficiency_level": "expert",
            "description": "Experienced in assisting elderly patients with bathing, grooming, and personal care routines.",
            "acquired_date": "2010-01-01",
            "years_of_experience": 15,
            "certificate": null,
            "certificate_url": null,
            "last_updated_by_id": "2",
            "last_updated_by": {
              "id": 2,
              "email": "support@appbrew.com",
              "first_name": "Abib",
              "last_name": "Achmed"
            }
          },
          {
            "id": 2,
            "skill_name": "Medication Administration",
            "proficiency_level": "advanced",
            "description": "Trained and certified in safe administration of oral, topical, and injectable medications.",
            "acquired_date": "2012-05-15",
            "years_of_experience": 13,
            "certificate": null,
            "certificate_url": null,
            "last_updated_by_id": "2",
            "last_updated_by": {
              "id": 2,
              "email": "support@appbrew.com",
              "first_name": "Abib",
              "last_name": "Achmed"
            }
          },
          {
            "id": 3,
            "skill_name": "First Aid & CPR",
            "proficiency_level": "expert",
            "description": "Certified in emergency first aid and cardiopulmonary resuscitation (CPR).",
            "acquired_date": "2015-03-20",
            "years_of_experience": 10,
            "certificate": null,
            "certificate_url": null,
            "last_updated_by_id": "2",
            "last_updated_by": {
              "id": 2,
              "email": "support@appbrew.com",
              "first_name": "Abib",
              "last_name": "Achmed"
            }
          },
          {
            "id": 4,
            "skill_name": "Dementia Care",
            "proficiency_level": "intermediate",
            "description": "Specialized training in supporting patients with Alzheimer's and other forms of dementia.",
            "acquired_date": "2018-11-10",
            "years_of_experience": 7,
            "certificate": null,
            "certificate_url": null,
            "last_updated_by_id": "2",
            "last_updated_by": {
              "id": 2,
              "email": "support@appbrew.com",
              "first_name": "Abib",
              "last_name": "Achmed"
            }
          }
        ],
        "skillsMatch": {
          "hasRequiredSkills": true,
          "missingSkills": [],
          "matchingSkills": [
            "dementia care",
            "patient hygiene assistance",
            "medication administration",
            "first aid & cpr"
          ],
          "requirementsMatch": true
        },
        "availability": {
          "isAvailable": true,
          "conflicts": [],
          "availableHours": {
            "friday": {
              "end": "14:00",
              "start": "08:00",
              "available": true
            },
            "monday": {
              "end": "16:00",
              "start": "08:00",
              "available": true
            },
            "sunday": {
              "available": false
            },
            "tuesday": {
              "end": "16:00",
              "start": "08:00",
              "available": true
            },
            "saturday": {
              "available": false
            },
            "thursday": {
              "end": "17:00",
              "start": "09:00",
              "available": true
            },
            "wednesday": {
              "available": false
            }
          }
        },
        "scheduleCheck": {
          "hasConflicts": false,
          "conflicts": [],
          "conflictCount": 0
        },
        "overallEligible": true
      }
    ],
    "ineligibleCarers": [
      {
        "carerId": 48,
        "carerName": "Gerard Pique",
        "email": "gerard.pique@blaugrana-care.com",
        "skills": [],
        "skillsMatch": {
          "hasRequiredSkills": false,
          "missingSkills": [
            "dementia care",
            "patient hygiene assistance",
            "medication administration",
            "first aid & cpr"
          ],
          "matchingSkills": [],
          "requirementsMatch": false
        },
        "availability": {
          "isAvailable": false,
          "conflicts": [
            "Request time (8:00-11:00) is outside carer availability (22:00-6:00) on monday"
          ],
          "availableHours": {
            "monday": "10pm-6am",
            "sunday": "10pm-6am"
          }
        },
        "scheduleCheck": {
          "hasConflicts": false,
          "conflicts": [],
          "conflictCount": 0
        },
        "overallEligible": false
      }
    ]
  },
  "message": "Found 1 eligible carers out of 6 total carers"
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
      "id": "REQ-20251106-97ZZF",
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