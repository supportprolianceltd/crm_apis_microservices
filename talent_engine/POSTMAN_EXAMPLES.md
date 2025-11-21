# 📮 Postman Request Examples - Talent Engine Service

## Authentication

All Talent Engine endpoints require JWT authentication via the Authorization header:
```
Authorization: Bearer YOUR_JWT_TOKEN
```

---

## Job Requisitions Management

### Create Job Requisition
**Purpose:** Creates a new job requisition with automatic ID generation, tenant validation, and user tracking. The system generates unique codes, links, and populates user details from JWT.
**Method:** POST
**URL:** `http://localhost:8002/api/talent-engine/requisitions/`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Request Body:**
```json
{
  "title": "Senior Python Developer",
  "job_type": "full_time",
  "position_type": "permanent",
  "location_type": "remote",
  "job_description": "We are looking for an experienced Python developer to join our team...",
  "requirements": [
    "5+ years Python development experience",
    "Django/Flask framework expertise",
    "PostgreSQL database experience"
  ],
  "responsibilities": [
    "Develop and maintain web applications",
    "Collaborate with cross-functional teams",
    "Code review and mentoring"
  ],
  "qualification_requirement": "Bachelor's degree in Computer Science or equivalent experience",
  "experience_requirement": "5+ years software development experience",
  "knowledge_requirement": "REST APIs, Git, Agile methodologies",
  "number_of_candidates": 3,
  "urgency_level": "high",
  "company_name": "TechCorp Ltd",
  "company_address": "123 Business Park, London, SW1A 1AA",
  "job_location": "London, UK (Remote)",
  "salary_range": "£60,000 - £80,000",
  "deadline_date": "2025-12-31",
  "start_date": "2026-01-15",
  "reason": "Team expansion due to increased demand",
  "comment": "Urgent hiring needed",
  "status": "draft",
  "role": "staff",
  "documents_required": [
    "Curriculum Vitae (CV)",
    "Cover Letter",
    "Portfolio"
  ],
  "compliance_checklist": [
    {
      "name": "DBS Check",
      "description": "Disclosure and Barring Service background check",
      "required": true
    },
    {
      "name": "References",
      "description": "Professional references verification",
      "required": true
    }
  ],
  "approval_workflow": {
    "stages": [
      {
        "name": "Manager Approval",
        "approvers": ["manager@company.com"],
        "required": true
      },
      {
        "name": "HR Approval",
        "approvers": ["hr@company.com"],
        "required": true
      }
    ]
  }
}
```

**Response:**
```json
{
  "id": "APP-JR-0001",
  "requisition_number": "REQ-20251115-0001",
  "job_requisition_code": "APP-JR-0001",
  "job_application_code": "APP-JA-0001",
  "tenant_id": "27f05a25-748e-4a98-9f01-5c479950e215",
  "tenant_domain": "appbrew.com",
  "title": "Senior Python Developer",
  "unique_link": "27f05a25-748e-4a98-9f01-5c479950e215APP-JR-0001senior-python-developer-abc123def",
  "status": "draft",
  "role": "staff",
  "requested_by_id": "1",
  "created_by_id": "1",
  "updated_by_id": "1",
  "requested_by": {
    "id": "1",
    "email": "support@appbrew.com",
    "first_name": "Mahummed",
    "last_name": "Mahummed",
    "job_role": "co-admin"
  },
  "created_by": {
    "id": "1",
    "email": "support@appbrew.com",
    "first_name": "Mahummed",
    "last_name": "Mahummed",
    "job_role": "co-admin"
  },
  "updated_by": {
    "id": "1",
    "email": "support@appbrew.com",
    "first_name": "Mahummed",
    "last_name": "Mahummed",
    "job_role": "co-admin"
  },
  "job_type": "full_time",
  "position_type": "permanent",
  "location_type": "remote",
  "job_description": "We are looking for an experienced Python developer to join our team...",
  "requirements": [
    "5+ years Python development experience",
    "Django/Flask framework expertise",
    "PostgreSQL database experience"
  ],
  "responsibilities": [
    "Develop and maintain web applications",
    "Collaborate with cross-functional teams",
    "Code review and mentoring"
  ],
  "qualification_requirement": "Bachelor's degree in Computer Science or equivalent experience",
  "experience_requirement": "5+ years software development experience",
  "knowledge_requirement": "REST APIs, Git, Agile methodologies",
  "number_of_candidates": 3,
  "urgency_level": "high",
  "company_name": "TechCorp Ltd",
  "company_address": "123 Business Park, London, SW1A 1AA",
  "job_location": "London, UK (Remote)",
  "salary_range": "£60,000 - £80,000",
  "deadline_date": "2025-12-31",
  "start_date": "2026-01-15",
  "reason": "Team expansion due to increased demand",
  "comment": "Urgent hiring needed",
  "documents_required": [
    "CV",
    "Cover Letter",
    "Portfolio"
  ],
  "compliance_checklist": [
    {
      "id": "uuid-123",
      "name": "DBS Check",
      "description": "Disclosure and Barring Service background check",
      "required": true,
      "status": "pending"
    },
    {
      "id": "uuid-456",
      "name": "References",
      "description": "Professional references verification",
      "required": true,
      "status": "pending"
    }
  ],
  "approval_workflow": {
    "stages": [
      {
        "name": "Manager Approval",
        "approvers": ["manager@company.com"],
        "required": true
      },
      {
        "name": "HR Approval",
        "approvers": ["hr@company.com"],
        "required": true
      }
    ]
  },
  "requested_date": "2025-11-15",
  "publish_status": false,
  "is_deleted": false,
  "created_at": "2025-11-15T03:45:00.000Z",
  "updated_at": "2025-11-15T03:45:00.000Z"
}
```

---

### Bulk Create Job Requisitions
**Purpose:** Creates multiple job requisitions in a single request with automatic ID generation and validation. Useful for bulk hiring initiatives.
**Method:** POST
**URL:** `http://localhost:8002/api/talent-engine/requisitions/bulk-create/`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Request Body:**
```json
[
  {
    "title": "Frontend Developer",
    "job_type": "full_time",
    "position_type": "permanent",
    "location_type": "hybrid",
    "job_description": "React.js developer needed for user interface development",
    "requirements": ["React.js", "JavaScript", "CSS"],
    "number_of_candidates": 2,
    "urgency_level": "medium",
    "company_name": "TechCorp Ltd",
    "job_location": "London, UK",
    "salary_range": "£45,000 - £55,000"
  },
  {
    "title": "DevOps Engineer",
    "job_type": "full_time",
    "position_type": "permanent",
    "location_type": "remote",
    "job_description": "Infrastructure automation and deployment specialist",
    "requirements": ["AWS", "Docker", "Kubernetes", "CI/CD"],
    "number_of_candidates": 1,
    "urgency_level": "high",
    "company_name": "TechCorp Ltd",
    "job_location": "London, UK (Remote)",
    "salary_range": "£65,000 - £75,000"
  }
]
```

**Response:**
```json
[
  {
    "id": "APP-JR-0002",
    "requisition_number": "REQ-20251115-0002",
    "job_requisition_code": "APP-JR-0002",
    "job_application_code": "APP-JA-0002",
    "tenant_id": "27f05a25-748e-4a98-9f01-5c479950e215",
    "title": "Frontend Developer",
    "unique_link": "27f05a25-748e-4a98-9f01-5c479950e215APP-JR-0002frontend-developer-def456ghi",
    "status": "draft",
    "role": "staff",
    "requested_by_id": "1",
    "created_by_id": "1",
    "job_type": "full_time",
    "position_type": "permanent",
    "location_type": "hybrid",
    "job_description": "React.js developer needed for user interface development",
    "requirements": ["React.js", "JavaScript", "CSS"],
    "number_of_candidates": 2,
    "urgency_level": "medium",
    "company_name": "TechCorp Ltd",
    "job_location": "London, UK",
    "salary_range": "£45,000 - £55,000",
    "requested_date": "2025-11-15",
    "created_at": "2025-11-15T03:50:00.000Z",
    "updated_at": "2025-11-15T03:50:00.000Z"
  },
  {
    "id": "APP-JR-0003",
    "requisition_number": "REQ-20251115-0003",
    "job_requisition_code": "APP-JR-0003",
    "job_application_code": "APP-JA-0003",
    "tenant_id": "27f05a25-748e-4a98-9f01-5c479950e215",
    "title": "DevOps Engineer",
    "unique_link": "27f05a25-748e-4a98-9f01-5c479950e215APP-JR-0003devops-engineer-jkl789mno",
    "status": "draft",
    "role": "staff",
    "requested_by_id": "1",
    "created_by_id": "1",
    "job_type": "full_time",
    "position_type": "permanent",
    "location_type": "remote",
    "job_description": "Infrastructure automation and deployment specialist",
    "requirements": ["AWS", "Docker", "Kubernetes", "CI/CD"],
    "number_of_candidates": 1,
    "urgency_level": "high",
    "company_name": "TechCorp Ltd",
    "job_location": "London, UK (Remote)",
    "salary_range": "£65,000 - £75,000",
    "requested_date": "2025-11-15",
    "created_at": "2025-11-15T03:50:00.000Z",
    "updated_at": "2025-11-15T03:50:00.000Z"
  }
]
```

---

### List Job Requisitions
**Purpose:** Retrieves paginated list of job requisitions for the authenticated user's tenant with filtering and search capabilities.
**Method:** GET
**URL:** `http://localhost:8002/api/talent-engine/requisitions/?page=1&status=draft`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Query Parameters:**
- `page`: Page number for pagination
- `status`: Filter by requisition status (draft, pending, approved, etc.)
- `role`: Filter by job role (staff, admin)
- `search`: Search in title, status, requested_by email, role, interview_location

**Response:**
```json
{
  "count": 3,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "APP-JR-0001",
      "requisition_number": "REQ-20251115-0001",
      "job_requisition_code": "APP-JR-0001",
      "tenant_id": "27f05a25-748e-4a98-9f01-5c479950e215",
      "title": "Senior Python Developer",
      "unique_link": "27f05a25-748e-4a98-9f01-5c479950e215APP-JR-0001senior-python-developer-abc123def",
      "status": "draft",
      "role": "staff",
      "requested_by_id": "1",
      "created_by_id": "1",
      "updated_by_id": "1",
      "requested_by": {
        "id": "1",
        "email": "support@appbrew.com",
        "first_name": "Mahummed",
        "last_name": "Mahummed",
        "job_role": "co-admin"
      },
      "created_by": {
        "id": "1",
        "email": "support@appbrew.com",
        "first_name": "Mahummed",
        "last_name": "Mahummed",
        "job_role": "co-admin"
      },
      "updated_by": {
        "id": "1",
        "email": "support@appbrew.com",
        "first_name": "Mahummed",
        "last_name": "Mahummed",
        "job_role": "co-admin"
      },
      "job_type": "full_time",
      "position_type": "permanent",
      "location_type": "remote",
      "number_of_candidates": 3,
      "urgency_level": "high",
      "company_name": "TechCorp Ltd",
      "job_location": "London, UK (Remote)",
      "salary_range": "£60,000 - £80,000",
      "deadline_date": "2025-12-31",
      "requested_date": "2025-11-15",
      "publish_status": false,
      "is_deleted": false,
      "created_at": "2025-11-15T03:45:00.000Z",
      "updated_at": "2025-11-15T03:45:00.000Z"
    }
  ]
}
```

---

### Get Job Requisition by ID
**Purpose:** Retrieves detailed information for a specific job requisition including all user details and compliance information.
**Method:** GET
**URL:** `http://localhost:8002/api/talent-engine/requisitions/APP-JR-0001/`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Response:** (Same structure as individual item in list response, with full details)

---

### Update Job Requisition
**Purpose:** Updates an existing job requisition with new information. Automatically tracks the user who made the update and handles approval workflow updates.
**Method:** PUT/PATCH
**URL:** `http://localhost:8002/api/talent-engine/requisitions/APP-JR-0001/`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Request Body (PATCH example):**
```json
{
  "status": "approved",
  "approved_by_id": "2",
  "approval_date": "2025-11-15T04:00:00Z",
  "comment": "Approved for publishing",
  "publish_status": true
}
```

**Response:**
```json
{
  "id": "APP-JR-0001",
  "requisition_number": "REQ-20251115-0001",
  "job_requisition_code": "APP-JR-0001",
  "tenant_id": "27f05a25-748e-4a98-9f01-5c479950e215",
  "title": "Senior Python Developer",
  "status": "approved",
  "approved_by_id": "2",
  "approved_by": {
    "id": "2",
    "email": "manager@appbrew.com",
    "first_name": "Jane",
    "last_name": "Smith",
    "job_role": "manager"
  },
  "approval_date": "2025-11-15T04:00:00.000Z",
  "publish_status": true,
  "updated_by_id": "1",
  "updated_by": {
    "id": "1",
    "email": "support@appbrew.com",
    "first_name": "Mahummed",
    "last_name": "Mahummed",
    "job_role": "co-admin"
  },
  "comment": "Approved for publishing",
  "updated_at": "2025-11-15T04:00:00.000Z"
}
```

---

### Delete Job Requisition
**Purpose:** Soft deletes a job requisition (marks as deleted without removing from database). Only the tenant owner can permanently delete.
**Method:** DELETE
**URL:** `http://localhost:8002/api/talent-engine/requisitions/APP-JR-0001/`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Response:**
```json
{
  "detail": "Job requisition soft-deleted successfully"
}
```

---

### Bulk Delete Job Requisitions
**Purpose:** Soft deletes multiple job requisitions in a single request.
**Method:** POST
**URL:** `http://localhost:8002/api/talent-engine/requisitions/bulk/bulk-delete/`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Request Body:**
```json
{
  "ids": ["APP-JR-0002", "APP-JR-0003"]
}
```

**Response:**
```json
{
  "detail": "Soft-deleted 2 requisition(s)."
}
```

---

### List Soft Deleted Job Requisitions
**Purpose:** Retrieves all soft deleted job requisitions for the tenant (for recovery purposes).
**Method:** GET
**URL:** `http://localhost:8002/api/talent-engine/requisitions/deleted/soft_deleted/`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Response:**
```json
{
  "count": 2,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "APP-JR-0002",
      "title": "Frontend Developer",
      "is_deleted": true,
      "deleted_at": "2025-11-15T04:05:00.000Z"
    },
    {
      "id": "APP-JR-0003",
      "title": "DevOps Engineer",
      "is_deleted": true,
      "deleted_at": "2025-11-15T04:05:00.000Z"
    }
  ]
}
```

---

### Recover Soft Deleted Job Requisitions
**Purpose:** Restores soft deleted job requisitions back to active status.
**Method:** POST
**URL:** `http://localhost:8002/api/talent-engine/requisitions/recover/requisition/`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Request Body:**
```json
{
  "ids": ["APP-JR-0002", "APP-JR-0003"]
}
```

**Response:**
```json
{
  "detail": "Successfully recovered 2 requisition(s)."
}
```

---

### Permanently Delete Job Requisitions
**Purpose:** Permanently removes soft deleted job requisitions from the database. This action cannot be undone.
**Method:** POST
**URL:** `http://localhost:8002/api/talent-engine/requisitions/permanent-delete/requisition/`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Request Body:**
```json
{
  "ids": ["APP-JR-0002", "APP-JR-0003"]
}
```

**Response:**
```json
{
  "detail": "Successfully permanently deleted 2 requisition(s)."
}
```

---

### Get My Job Requisitions
**Purpose:** Retrieves all job requisitions created by the authenticated user.
**Method:** GET
**URL:** `http://localhost:8002/api/talent-engine/requisitions-per-user/`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Response:** (Same structure as list requisitions, filtered by requested_by_id)

---

### Get Published Job Requisitions
**Purpose:** Retrieves all published job requisitions for the tenant (available for public viewing).
**Method:** GET
**URL:** `http://localhost:8002/api/talent-engine/requisitions/published/requisition/`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Response:** (Same structure as list requisitions, filtered by publish_status=true)

---

## Public Job Requisitions

### Get Public Published Job Requisitions
**Purpose:** Retrieves published job requisitions that are currently accepting applications (public endpoint, no authentication required).
**Method:** GET
**URL:** `http://localhost:8002/api/talent-engine/requisitions/public/published/`

**Response:**
```json
{
  "count": 5,
  "results": [
    {
      "id": "APP-JR-0001",
      "requisition_number": "REQ-20251115-0001",
      "job_requisition_code": "APP-JR-0001",
      "job_application_code": "APP-JA-0001",
      "tenant_id": "27f05a25-748e-4a98-9f01-5c479950e215",
      "title": "Senior Python Developer",
      "unique_link": "27f05a25-748e-4a98-9f01-5c479950e215APP-JR-0001senior-python-developer-abc123def",
      "status": "open",
      "job_type": "full_time",
      "position_type": "permanent",
      "location_type": "remote",
      "job_description": "We are looking for an experienced Python developer...",
      "requirements": [
        "5+ years Python development experience",
        "Django/Flask framework expertise"
      ],
      "qualification_requirement": "Bachelor's degree in Computer Science",
      "experience_requirement": "5+ years software development experience",
      "number_of_candidates": 3,
      "urgency_level": "high",
      "company_name": "TechCorp Ltd",
      "job_location": "London, UK (Remote)",
      "salary_range": "£60,000 - £80,000",
      "deadline_date": "2025-12-31",
      "responsibilities": [
        "Develop and maintain web applications",
        "Collaborate with cross-functional teams"
      ],
      "documents_required": ["CV", "Cover Letter"],
      "compliance_checklist": [
        {
          "name": "DBS Check",
          "description": "Background check required",
          "required": true
        }
      ],
      "approval_workflow": {
        "stages": [
          {
            "name": "Manager Approval",
            "required": true
          }
        ]
      },
      "num_of_applications": 12,
      "publish_status": true,
      "created_at": "2025-11-15T03:45:00.000Z"
    }
  ]
}
```

---

### Get Upcoming Public Job Requisitions
**Purpose:** Retrieves published job requisitions with upcoming deadlines (public endpoint, no authentication required).
**Method:** GET
**URL:** `http://localhost:8002/api/talent-engine/requisitions/upcoming/public/jobs/`

**Response:** (Same structure as public published, filtered by deadline_date >= today)

---

### Get Public Job Requisitions by Tenant
**Purpose:** Retrieves published job requisitions for a specific tenant (public endpoint, no authentication required).
**Method:** GET
**URL:** `http://localhost:8002/api/talent-engine/requisitions/public/published/27f05a25-748e-4a98-9f01-5c479950e215/`

**Response:**
```json
{
  "tenant": {
    "id": "27f05a25-748e-4a98-9f01-5c479950e215",
    "name": "AppBrew",
    "domain": "appbrew.com",
    "logo_url": "https://appbrew.com/logo.png"
  },
  "count": 3,
  "results": [
    {
      "id": "APP-JR-0001",
      "title": "Senior Python Developer",
      "job_type": "full_time",
      "location_type": "remote",
      "job_description": "We are looking for an experienced Python developer...",
      "company_name": "TechCorp Ltd",
      "job_location": "London, UK (Remote)",
      "salary_range": "£60,000 - £80,000",
      "deadline_date": "2025-12-31",
      "num_of_applications": 12,
      "created_at": "2025-11-15T03:45:00.000Z"
    }
  ]
}
```

---

### Get Job Requisition by Unique Link
**Purpose:** Retrieves a specific job requisition using its unique public link (public endpoint, no authentication required).
**Method:** GET
**URL:** `http://localhost:8002/api/talent-engine/requisitions/by-link/27f05a25-748e-4a98-9f01-5c479950e215APP-JR-0001senior-python-developer-abc123def/`

**Response:** (Same structure as public published individual item)

---

### Increment Application Count
**Purpose:** Increments the application count for a job requisition when someone applies via the public link (public endpoint, no authentication required).
**Method:** POST
**URL:** `http://localhost:8002/api/talent-engine/requisitions/public/update-applications/27f05a25-748e-4a98-9f01-5c479950e215APP-JR-0001senior-python-developer-abc123def/`

**Response:**
```json
{
  "detail": "Incremented num_of_applications to 13",
  "data": {
    "id": "APP-JR-0001",
    "title": "Senior Python Developer",
    "num_of_applications": 13,
    "updated_at": "2025-11-15T04:15:00.000Z"
  }
}
```

---

### Close Job Requisition (Public)
**Purpose:** Allows public closure of a job requisition (useful for automated systems or public interfaces).
**Method:** POST
**URL:** `http://localhost:8002/api/talent-engine/requisitions/public/close/APP-JR-0001/`

**Response:**
```json
{
  "detail": "Job requisition APP-JR-0001 status changed to closed.",
  "id": "APP-JR-0001",
  "status": "closed"
}
```

---

### Batch Close Job Requisitions (Public)
**Purpose:** Closes multiple job requisitions in a single request (public endpoint).
**Method:** POST
**URL:** `http://localhost:8002/api/talent-engine/requisitions/public/close/batch/`

**Request Body:**
```json
{
  "job_requisition_ids": ["APP-JR-0002", "APP-JR-0003"]
}
```

**Response:**
```json
{
  "closed_jobs": ["APP-JR-0002", "APP-JR-0003"],
  "not_found_jobs": []
}
```

---

## Compliance Management

### Add Compliance Item
**Purpose:** Adds a new compliance checklist item to a job requisition for tracking required checks (DBS, references, etc.).
**Method:** POST
**URL:** `http://localhost:8002/api/talent-engine/requisitions/APP-JR-0001/compliance-items/`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Request Body:**
```json
{
  "name": "Enhanced DBS Check",
  "description": "Enhanced Disclosure and Barring Service check with children's barred list",
  "required": true,
  "status": "pending"
}
```

**Response:**
```json
{
  "id": "uuid-789",
  "name": "Enhanced DBS Check",
  "description": "Enhanced Disclosure and Barring Service check with children's barred list",
  "required": true,
  "status": "pending",
  "checked_by_id": null,
  "checked_at": null
}
```

---

### Update Compliance Item
**Purpose:** Updates an existing compliance checklist item, typically to mark it as completed with checker details.
**Method:** PUT
**URL:** `http://localhost:8002/api/talent-engine/requisitions/APP-JR-0001/compliance-items/uuid-789/`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Request Body:**
```json
{
  "status": "completed",
  "checked_by_id": "2",
  "checked_at": "2025-11-15T04:20:00Z",
  "notes": "DBS check completed successfully"
}
```

**Response:**
```json
{
  "id": "uuid-789",
  "name": "Enhanced DBS Check",
  "description": "Enhanced Disclosure and Barring Service check with children's barred list",
  "required": true,
  "status": "completed",
  "checked_by_id": "2",
  "checked_at": "2025-11-15T04:20:00.000Z"
}
```

---

### Delete Compliance Item
**Purpose:** Removes a compliance checklist item from a job requisition.
**Method:** DELETE
**URL:** `http://localhost:8002/api/talent-engine/requisitions/APP-JR-0001/compliance-items/uuid-789/`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Response:**
```json
204 No Content
```

---

## Video Sessions Management

### Create Video Session
**Purpose:** Creates a new video interview session for a job application with automatic meeting ID generation.
**Method:** POST
**URL:** `http://localhost:8002/api/talent-engine/video-sessions/`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Request Body:**
```json
{
  "job_application_id": "JA-20251115-0001",
  "meeting_id": "meet_abc123def456",
  "scores": {
    "technical": 4,
    "communication": 5,
    "problemSolving": 4
  },
  "notes": "Strong technical background, excellent communication skills",
  "tags": ["Technical Interview", "Senior Developer", "Python Expert"]
}
```

**Response:**
```json
{
  "id": "uuid-session-123",
  "job_application_id": "JA-20251115-0001",
  "tenant_id": "27f05a25-748e-4a98-9f01-5c479950e215",
  "meeting_id": "meet_abc123def456",
  "is_active": true,
  "scores": {
    "technical": 4,
    "communication": 5,
    "problemSolving": 4
  },
  "notes": "Strong technical background, excellent communication skills",
  "tags": ["Technical Interview", "Senior Developer", "Python Expert"],
  "created_at": "2025-11-15T04:25:00.000Z",
  "ended_at": null,
  "recording_url": null
}
```

---

### List Video Sessions
**Purpose:** Retrieves paginated list of video sessions for the tenant.
**Method:** GET
**URL:** `http://localhost:8002/api/talent-engine/video-sessions/`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Response:**
```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "uuid-session-123",
      "job_application_id": "JA-20251115-0001",
      "tenant_id": "27f05a25-748e-4a98-9f01-5c479950e215",
      "meeting_id": "meet_abc123def456",
      "is_active": true,
      "scores": {
        "technical": 4,
        "communication": 5,
        "problemSolving": 4
      },
      "notes": "Strong technical background, excellent communication skills",
      "tags": ["Technical Interview", "Senior Developer", "Python Expert"],
      "created_at": "2025-11-15T04:25:00.000Z",
      "ended_at": null,
      "recording_url": null,
      "participants": []
    }
  ]
}
```

---

### Get Video Session Details
**Purpose:** Retrieves detailed information for a specific video session including participants.
**Method:** GET
**URL:** `http://localhost:8002/api/talent-engine/video-sessions/uuid-session-123/`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Response:** (Same structure as list item with full participant details)

---

### Update Video Session
**Purpose:** Updates video session information including scores, notes, and tags.
**Method:** PUT/PATCH
**URL:** `http://localhost:8002/api/talent-engine/video-sessions/uuid-session-123/`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Request Body:**
```json
{
  "scores": {
    "technical": 5,
    "communication": 5,
    "problemSolving": 5
  },
  "notes": "Exceptional candidate - excellent technical skills and communication",
  "tags": ["Technical Interview", "Senior Developer", "Python Expert", "Top Candidate"]
}
```

**Response:** (Updated session object)

---

### Start Recording
**Purpose:** Initiates recording for an active video session and stores the recording URL.
**Method:** POST
**URL:** `http://localhost:8002/api/talent-engine/video-sessions/start_recording/`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Request Body:**
```json
{
  "session_id": "uuid-session-123"
}
```

**Response:**
```json
{
  "recording_url": "https://storage.example.com/recordings/uuid-session-123.webm"
}
```

---

### Join Video Session
**Purpose:** Adds a participant to a video session (either authenticated user or candidate via email).
**Method:** POST
**URL:** `http://localhost:8002/api/talent-engine/video-sessions/join/`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN` (for authenticated users)

**Request Body (for authenticated user):**
```json
{
  "session_id": "uuid-session-123"
}
```

**Request Body (for candidate):**
```json
{
  "session_id": "uuid-session-123",
  "email": "candidate@example.com"
}
```

**Response:**
```json
{
  "id": "uuid-participant-123",
  "session": "uuid-session-123",
  "user_id": "1",
  "username": "support@appbrew.com",
  "first_name": "Mahummed",
  "last_name": "Mahummed",
  "candidate_email": null,
  "is_muted": false,
  "is_camera_on": true,
  "joined_at": "2025-11-15T04:30:00.000Z",
  "left_at": null
}
```

---

### Leave Video Session
**Purpose:** Records when a participant leaves the video session.
**Method:** POST
**URL:** `http://localhost:8002/api/talent-engine/video-sessions/leave/`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Request Body:**
```json
{
  "session_id": "uuid-session-123"
}
```

**Response:**
```json
{
  "status": "Left session"
}
```

---

### Toggle Mute
**Purpose:** Toggles mute status for a participant in the video session.
**Method:** POST
**URL:** `http://localhost:8002/api/talent-engine/video-sessions/toggle_mute/`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Request Body:**
```json
{
  "session_id": "uuid-session-123",
  "mute": true
}
```

**Response:** (Updated participant object)

---

### Toggle Camera
**Purpose:** Toggles camera status for a participant in the video session.
**Method:** POST
**URL:** `http://localhost:8002/api/talent-engine/video-sessions/toggle_camera/`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Request Body:**
```json
{
  "session_id": "uuid-session-123",
  "camera_on": false
}
```

**Response:** (Updated participant object)

---

### Update Interview Data
**Purpose:** Updates interview scores, notes, and tags during or after the video session.
**Method:** POST
**URL:** `http://localhost:8002/api/talent-engine/video-sessions/update_interview_data/`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Request Body:**
```json
{
  "session_id": "uuid-session-123",
  "scores": {
    "technical": 5,
    "communication": 4,
    "problemSolving": 5
  },
  "notes": "Excellent technical knowledge, strong problem-solving skills",
  "tags": ["Technical Interview", "Senior Level", "Strong Candidate"]
}
```

**Response:** (Updated session object)

---

## Request Management

### Create Request
**Purpose:** Creates a new general request (material, leave, or service) with automatic ID generation and user tracking.
**Method:** POST
**URL:** `http://localhost:8002/api/talent-engine/requests/`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Request Body (Material Request):**
```json
{
  "request_type": "material",
  "title": "Office Supplies Request",
  "description": "Request for additional office supplies for the development team",
  "item_name": "Wireless Keyboard and Mouse Set",
  "material_type": "equipment",
  "quantity_needed": 5,
  "priority": "medium",
  "reason_for_request": "Current equipment is outdated and affecting productivity",
  "needed_date": "2025-11-30",
  "item_specification": "Logitech MX Keys and MX Master 3S, ergonomic design"
}
```

**Request Body (Leave Request):**
```json
{
  "request_type": "leave",
  "title": "Annual Leave Request",
  "description": "Request for annual leave during holiday period",
  "leave_category": "annual",
  "number_of_days": 10,
  "start_date": "2025-12-20",
  "resumption_date": "2025-12-30",
  "region_of_stay": "local",
  "address_during_leave": "123 Holiday Street, London, SW1A 1AA",
  "contact_phone_number": "+447123456789",
  "additional_information": "Will be available for emergencies"
}
```

**Request Body (Service Request):**
```json
{
  "request_type": "service",
  "title": "IT Support Request",
  "description": "Laptop screen flickering issue",
  "service_type": "it_support",
  "service_description": "Dell XPS 13 laptop screen has flickering issues, affecting work productivity",
  "priority_level": "high",
  "desired_completion_date": "2025-11-20",
  "requester_name": "John Smith",
  "requester_department": "Development",
  "requester_contact_info": "john.smith@company.com, ext. 1234",
  "special_instructions": "Please backup all data before repair"
}
```

**Response (Material Request):**
```json
{
  "id": "uuid-request-123",
  "tenant_id": "27f05a25-748e-4a98-9f01-5c479950e215",
  "request_type": "material",
  "title": "Office Supplies Request",
  "description": "Request for additional office supplies for the development team",
  "status": "pending",
  "item_name": "Wireless Keyboard and Mouse Set",
  "material_type": "equipment",
  "request_id": "MAT-20251115-0001",
  "quantity_needed": 5,
  "priority": "medium",
  "reason_for_request": "Current equipment is outdated and affecting productivity",
  "needed_date": "2025-11-30",
  "item_specification": "Logitech MX Keys and MX Master 3S, ergonomic design",
  "requested_by_id": "1",
  "requested_by": {
    "id": "1",
    "email": "support@appbrew.com",
    "first_name": "Mahummed",
    "last_name": "Mahummed",
    "job_role": "co-admin"
  },
  "created_at": "2025-11-15T04:35:00.000Z",
  "updated_at": "2025-11-15T04:35:00.000Z"
}
```

---

### List Requests
**Purpose:** Retrieves paginated list of requests for the tenant with filtering options.
**Method:** GET
**URL:** `http://localhost:8002/api/talent-engine/requests/?page=1&request_type=material&status=pending`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Query Parameters:**
- `page`: Page number for pagination
- `request_type`: Filter by request type (material, leave, service)
- `status`: Filter by status (pending, approved, rejected, cancelled, completed)
- `priority`: Filter by priority (low, medium, high)
- `search`: Search in title, description, item_name, requester_name

**Response:**
```json
{
  "count": 3,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "uuid-request-123",
      "request_type": "material",
      "title": "Office Supplies Request",
      "status": "pending",
      "priority": "medium",
      "item_name": "Wireless Keyboard and Mouse Set",
      "quantity_needed": 5,
      "requested_by": {
        "id": "1",
        "email": "support@appbrew.com",
        "first_name": "Mahummed",
        "last_name": "Mahummed",
        "job_role": "co-admin"
      },
      "created_at": "2025-11-15T04:35:00.000Z"
    }
  ]
}
```

---

### Get Request Details
**Purpose:** Retrieves detailed information for a specific request.
**Method:** GET
**URL:** `http://localhost:8002/api/talent-engine/requests/uuid-request-123/`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Response:** (Full request object with all fields based on request_type)

---

### Update Request
**Purpose:** Updates a request and handles approval/rejection workflow automatically.
**Method:** PUT/PATCH
**URL:** `http://localhost:8002/api/talent-engine/requests/uuid-request-123/`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Request Body (Approval):**
```json
{
  "status": "approved",
  "comment": "Approved - budget available"
}
```

**Request Body (Rejection):**
```json
{
  "status": "rejected",
  "comment": "Budget constraints - please use existing equipment"
}
```

**Response:**
```json
{
  "id": "uuid-request-123",
  "status": "approved",
  "approved_by_id": "2",
  "approved_by": {
    "id": "2",
    "email": "manager@appbrew.com",
    "first_name": "Jane",
    "last_name": "Smith",
    "job_role": "manager"
  },
  "comment": "Approved - budget available",
  "updated_at": "2025-11-15T04:40:00.000Z"
}
```

---

### Delete Request
**Purpose:** Soft deletes a request (marks as deleted).
**Method:** DELETE
**URL:** `http://localhost:8002/api/talent-engine/requests/uuid-request-123/`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Response:**
```json
{
  "detail": "Request soft-deleted successfully"
}
```

---

### Get My Requests
**Purpose:** Retrieves all requests created by the authenticated user.
**Method:** GET
**URL:** `http://localhost:8002/api/talent-engine/requests/user/`
**Headers:** `Authorization: Bearer YOUR_JWT_TOKEN`

**Response:** (Same structure as list requests, filtered by requested_by_id)

---

## System Health & Documentation

### API Schema
**Purpose:** Retrieves the OpenAPI schema for the Talent Engine API.
**Method:** GET
**URL:** `http://localhost:8002/api/schema/`

**Response:** (OpenAPI 3.0 JSON schema)

---

### API Documentation
**Purpose:** Interactive API documentation using Swagger UI.
**Method:** GET
**URL:** `http://localhost:8002/api/docs/`

**Response:** (HTML page with interactive API documentation)

---

## Error Responses

### Authentication Error
**Status:** 401 Unauthorized

**Response:**
```json
{
  "detail": "Authentication credentials were not provided."
}
```

### Permission Denied
**Status:** 403 Forbidden

**Response:**
```json
{
  "detail": "You do not have permission to perform this action."
}
```

### Not Found
**Status:** 404 Not Found

**Response:**
```json
{
  "detail": "Not found."
}
```

### Validation Error
**Status:** 400 Bad Request

**Response:**
```json
{
  "title": ["This field is required."],
  "job_type": ["\"invalid_type\" is not a valid choice."]
}
```

### Tenant Mismatch
**Status:** 400 Bad Request

**Response:**
```json
{
  "detail": "Tenant ID mismatch."
}
```

### Rate Limit Exceeded
**Status:** 429 Too Many Requests

**Response:**
```json
{
  "detail": "Request rate limit exceeded."
}
```

---

## Data Models

### Job Requisition Status Choices
- `draft