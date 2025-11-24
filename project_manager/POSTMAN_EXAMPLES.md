# 📮 Postman Request Examples - Project Manager Service (Tasks & Knowledge Base)

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

## Task Management

### Create Task
**Purpose:** Creates a new task in the project management system. Tasks can be assigned to users or left unassigned for later assignment.
**Method:** POST
**URL:** `http://localhost:9090/api/project-manager/api/tasks/`

**Request Body (Assigned Task):**
```json
{
  "title": "Implement User Authentication",
  "description": "Implement JWT-based authentication system for the application with role-based access control",
  "assigned_to_id": "user-456",
  "start_date": "2025-11-15",
  "due_date": "2025-11-30",
  "priority": "high",
  "status": "not_started"
}
```

**Request Body (Unassigned Task):**
```json
{
  "title": "Design System Architecture",
  "description": "Create high-level system architecture diagram and documentation",
  "start_date": "2025-11-20",
  "due_date": "2025-12-15",
  "priority": "medium",
  "status": "not_started"
}
```
*Note: `assigned_to_id` is optional. Omit it or set to `null`/`""` to create an unassigned task.*

**Required Fields:**
- `title`: Task title (string)

**Optional Fields:**
- `description`: Task description (string)
- `assigned_to_id`: User ID to assign task to (string, optional - omit for unassigned tasks)
- `start_date`: Task start date (date)
- `due_date`: Task due date (date)
- `priority`: Task priority - 'low', 'medium', 'high' (string, default: 'medium')
- `status`: Task status - 'not_started', 'in_progress', 'completed', 'blocked' (string, default: 'not_started')

**Example Response (Assigned Task):**
```json
{
  "id": "APP-TASK-000001",
  "title": "Implement User Authentication",
  "description": "Implement JWT-based authentication system for the application with role-based access control",
  "assigned_to_id": "user-456",
  "assigned_to_first_name": "Jane",
  "assigned_to_last_name": "Doe",
  "assigned_to_email": "jane.doe@company.com",
  "assigned_by_id": "user-123",
  "assigned_by_first_name": "John",
  "assigned_by_last_name": "Coordinator",
  "assigned_by_email": "coordinator@hospital.com",
  "start_date": "2025-11-15",
  "due_date": "2025-11-30",
  "priority": "high",
  "status": "not_started",
  "progress_percentage": 0,
  "created_at": "2025-11-12T10:30:00.000Z",
  "updated_at": "2025-11-12T10:30:00.000Z"
}
```

**Example Response (Unassigned Task):**
```json
{
  "id": "APP-TASK-000002",
  "title": "Design System Architecture",
  "description": "Create high-level system architecture diagram and documentation",
  "assigned_to_id": null,
  "assigned_to_first_name": "",
  "assigned_to_last_name": "",
  "assigned_to_email": "",
  "assigned_by_id": "user-123",
  "assigned_by_first_name": "John",
  "assigned_by_last_name": "Coordinator",
  "assigned_by_email": "coordinator@hospital.com",
  "start_date": "2025-11-20",
  "due_date": "2025-12-15",
  "priority": "medium",
  "status": "not_started",
  "progress_percentage": 0,
  "created_at": "2025-11-12T10:35:00.000Z",
  "updated_at": "2025-11-12T10:35:00.000Z"
}
```

---

### Get All Tasks
**Purpose:** Retrieves a paginated list of all tasks with optional filtering. Supports admin dashboard analytics and task management filtering.
**Method:** GET
**URL:** `http://localhost:9090/api/project-manager/api/tasks/`

**Optional Query Parameters:**
- `status`: Filter by task status (not_started, in_progress, completed, blocked)
- `assigned_to_id`: Filter by assigned user ID (used for user analytics)
- `ordering`: Sort results (default: -created_at for most recent first)
- `page`: Page number for pagination (default: 1)
- `page_size`: Number of items per page (default: 20, max: 100)

**Example URLs:**
- All tasks: `http://localhost:9090/api/project-manager/api/tasks/`
- Filter by status: `http://localhost:9090/api/project-manager/api/tasks/?status=in_progress`
- Filter by user (Analytics): `http://localhost:9090/api/project-manager/api/tasks/?assigned_to_id=user-456`
- Combined filters: `http://localhost:9090/api/project-manager/api/tasks/?status=completed&assigned_to_id=user-456`
- Pagination: `http://localhost:9090/api/project-manager/api/tasks/?page=2&page_size=10`

**Pagination Response:**
```json
{
  "count": 45,
  "next": "http://localhost:9090/api/project-manager/api/tasks/?page=2",
  "previous": null,
  "results": [
    {
      "id": "APP-TASK-000001",
      "title": "Implement User Authentication",
      "description": "Implement JWT-based authentication system for the application with role-based access control",
      "assigned_to_id": "user-456",
      "assigned_to_first_name": "Jane",
      "assigned_to_last_name": "Doe",
      "assigned_to_email": "jane.doe@company.com",
      "assigned_by_id": "user-123",
      "assigned_by_first_name": "John",
      "assigned_by_last_name": "Coordinator",
      "assigned_by_email": "coordinator@hospital.com",
      "start_date": "2025-11-15",
      "due_date": "2025-11-30",
      "priority": "high",
      "status": "in_progress",
      "progress_percentage": 25,
      "created_at": "2025-11-12T10:30:00.000Z",
      "updated_at": "2025-11-12T11:00:00.000Z",
      "comments": [],
      "daily_reports": []
    },
    {
      "id": "APP-TASK-000002",
      "title": "Database Migration",
      "description": "Migrate legacy database to new PostgreSQL schema",
      "assigned_to_id": "user-789",
      "assigned_to_first_name": "Bob",
      "assigned_to_last_name": "Smith",
      "assigned_to_email": "bob.smith@company.com",
      "assigned_by_id": "user-123",
      "assigned_by_first_name": "John",
      "assigned_by_last_name": "Coordinator",
      "assigned_by_email": "coordinator@hospital.com",
      "start_date": "2025-11-10",
      "due_date": "2025-11-25",
      "priority": "medium",
      "status": "completed",
      "progress_percentage": 100,
      "created_at": "2025-11-11T09:00:00.000Z",
      "updated_at": "2025-11-12T09:30:00.000Z",
      "comments": [],
      "daily_reports": []
    }
  ]
}
```

---

### Get Task by ID
**Purpose:** Retrieves detailed information for a specific task including comments and daily reports.
**Method:** GET
**URL:** `http://localhost:9090/api/project-manager/api/tasks/{task_id}/`

**Example URL:** `http://localhost:9090/api/project-manager/api/tasks/APP-TASK-000001/`

**Response:**
```json
{
  "id": "APP-TASK-000001",
  "title": "Implement User Authentication",
  "description": "Implement JWT-based authentication system for the application with role-based access control",
  "assigned_to_id": "user-456",
  "assigned_to_first_name": "Jane",
  "assigned_to_last_name": "Doe",
  "assigned_to_email": "jane.doe@company.com",
  "assigned_by_id": "user-123",
  "assigned_by_first_name": "John",
  "assigned_by_last_name": "Coordinator",
  "assigned_by_email": "coordinator@hospital.com",
  "start_date": "2025-11-15",
  "due_date": "2025-11-30",
  "priority": "high",
  "status": "in_progress",
  "progress_percentage": 25,
  "created_at": "2025-11-12T10:30:00.000Z",
  "updated_at": "2025-11-12T11:00:00.000Z",
  "comments": [
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "task": "APP-TASK-000001",
      "user_id": "user-456",
      "user_first_name": "Jane",
      "user_last_name": "Doe",
      "user_email": "jane.doe@company.com",
      "text": "Started working on the JWT implementation",
      "created_at": "2025-11-12T11:00:00.000Z"
    }
  ],
  "daily_reports": [
    {
      "id": "b2c3d4e5-f6g7-8901-bcde-f23456789012",
      "task": "APP-TASK-000001",
      "date": "2025-11-12",
      "updated_by_id": "user-456",
      "updated_by_first_name": "Jane",
      "updated_by_last_name": "Doe",
      "updated_by_email": "jane.doe@company.com",
      "completed_description": "Set up basic JWT authentication structure",
      "remaining_description": "Implement token refresh and role-based permissions",
      "reason_for_incompletion": "",
      "next_action_plan": "Complete token refresh logic tomorrow",
      "status": "in_progress",
      "attachments": [],
      "created_at": "2025-11-12T17:00:00.000Z"
    }
  ]
}
```

---

### Get Tasks by User (Analytics)
**Purpose:** Retrieves all tasks assigned to a specific user for performance analytics and reporting. Used by admin dashboard for user performance tracking.
**Method:** GET
**URL:** `http://localhost:9090/api/project-manager/api/users/{user_id}/tasks/`

**URL Parameters:**
- `user_id`: The user ID to filter tasks by (passed in URL path)

**Example URLs:**
- `http://localhost:9090/api/project-manager/api/users/54/tasks/` (for user ID "54")
- `http://localhost:9090/api/project-manager/api/users/51/tasks/` (for user ID "51")
- `http://localhost:9090/api/project-manager/api/users/support@appbrew.com/tasks/` (for email-based user ID)

**Response:**
```json
[
  {
    "id": "APP-TASK-000001",
    "title": "Implement User Authentication",
    "description": "Implement JWT-based authentication system for the application with role-based access control",
    "assigned_to_id": "user-456",
    "assigned_to_first_name": "Jane",
    "assigned_to_last_name": "Doe",
    "assigned_to_email": "jane.doe@company.com",
    "assigned_by_id": "user-123",
    "assigned_by_first_name": "John",
    "assigned_by_last_name": "Coordinator",
    "assigned_by_email": "coordinator@hospital.com",
    "start_date": "2025-11-15",
    "due_date": "2025-11-30",
    "priority": "high",
    "status": "completed",
    "progress_percentage": 100,
    "created_at": "2025-11-12T10:30:00.000Z",
    "updated_at": "2025-11-12T14:30:00.000Z",
    "comments": [],
    "daily_reports": []
  },
  {
    "id": "APP-TASK-000003",
    "title": "API Documentation",
    "description": "Create comprehensive API documentation for all endpoints",
    "assigned_to_id": "user-456",
    "assigned_to_first_name": "Jane",
    "assigned_to_last_name": "Doe",
    "assigned_to_email": "jane.doe@company.com",
    "assigned_by_id": "user-123",
    "assigned_by_first_name": "John",
    "assigned_by_last_name": "Coordinator",
    "assigned_by_email": "coordinator@hospital.com",
    "start_date": "2025-11-20",
    "due_date": "2025-11-28",
    "priority": "medium",
    "status": "in_progress",
    "progress_percentage": 60,
    "created_at": "2025-11-13T09:00:00.000Z",
    "updated_at": "2025-11-14T16:00:00.000Z",
    "comments": [],
    "daily_reports": []
  },
  {
    "id": "APP-TASK-000005",
    "title": "Database Optimization",
    "description": "Optimize database queries and add proper indexing",
    "assigned_to_id": "user-456",
    "assigned_to_first_name": "Jane",
    "assigned_to_last_name": "Doe",
    "assigned_to_email": "jane.doe@company.com",
    "assigned_by_id": "user-123",
    "assigned_by_first_name": "John",
    "assigned_by_last_name": "Coordinator",
    "assigned_by_email": "coordinator@hospital.com",
    "start_date": "2025-11-18",
    "due_date": "2025-11-25",
    "priority": "high",
    "status": "blocked",
    "progress_percentage": 30,
    "created_at": "2025-11-14T11:00:00.000Z",
    "updated_at": "2025-11-15T10:00:00.000Z",
    "comments": [],
    "daily_reports": []
  }
]
```

**Analytics Use Case:** This endpoint is used by the admin dashboard to calculate user performance metrics including:
- Completion rate: `(completed tasks / total tasks) * 100`
- Average progress: `sum of all progress percentages / total tasks`
- Overdue tasks: Tasks with `due_date < current_date` and `status != 'completed'`
- Performance score: Weighted calculation of completion rate, progress, and timeliness

---

### Get My Tasks
**Purpose:** Retrieves all tasks assigned to the currently authenticated user.
**Method:** GET
**URL:** `http://localhost:9090/api/project-manager/api/tasks/my_tasks/`

**Response:**
```json
[
  {
    "id": "APP-TASK-000001",
    "title": "Implement User Authentication",
    "description": "Implement JWT-based authentication system for the application with role-based access control",
    "assigned_to_id": "user-456",
    "assigned_to_first_name": "Jane",
    "assigned_to_last_name": "Doe",
    "assigned_to_email": "jane.doe@company.com",
    "assigned_by_id": "user-123",
    "assigned_by_first_name": "John",
    "assigned_by_last_name": "Coordinator",
    "assigned_by_email": "coordinator@hospital.com",
    "start_date": "2025-11-15",
    "due_date": "2025-11-30",
    "priority": "high",
    "status": "in_progress",
    "progress_percentage": 25,
    "created_at": "2025-11-12T10:30:00.000Z",
    "updated_at": "2025-11-12T11:00:00.000Z",
    "comments": [],
    "daily_reports": []
  }
]
```

---

### Update Task Status
**Purpose:** Updates the status and progress percentage of a task. Automatically creates a daily report when status changes to 'completed' or 'blocked'.
**Method:** PATCH
**URL:** `http://localhost:9090/api/project-manager/api/tasks/{task_id}/update_status/`

**Example URL:** `http://localhost:9090/api/project-manager/api/tasks/APP-TASK-000001/update_status/`

**Request Body:**
```json
{
  "status": "completed",
  "progress_percentage": 100
}
```

**Response:**
```json
{
  "id": "APP-TASK-000001",
  "title": "Implement User Authentication",
  "description": "Implement JWT-based authentication system for the application with role-based access control",
  "assigned_to_id": "user-456",
  "assigned_to_first_name": "Jane",
  "assigned_to_last_name": "Doe",
  "assigned_to_email": "jane.doe@company.com",
  "assigned_by_id": "user-123",
  "assigned_by_first_name": "John",
  "assigned_by_last_name": "Coordinator",
  "assigned_by_email": "coordinator@hospital.com",
  "start_date": "2025-11-15",
  "due_date": "2025-11-30",
  "priority": "high",
  "status": "completed",
  "progress_percentage": 100,
  "created_at": "2025-11-12T10:30:00.000Z",
  "updated_at": "2025-11-12T14:30:00.000Z",
  "comments": [],
  "daily_reports": []
}
```

---

### Update Task
**Purpose:** Updates task information including title, description, dates, and priority.
**Method:** PUT
**URL:** `http://localhost:9090/api/project-manager/api/tasks/{task_id}/`

**Example URL:** `http://localhost:9090/api/project-manager/api/tasks/APP-TASK-000001/`

**Request Body:**
```json
{
  "title": "Implement JWT Authentication with Role-Based Access",
  "description": "Implement JWT-based authentication system for the application with comprehensive role-based access control and token refresh functionality",
  "due_date": "2025-12-05",
  "priority": "high"
}
```

**Response:**
```json
{
  "id": "APP-TASK-000001",
  "title": "Implement JWT Authentication with Role-Based Access",
  "description": "Implement JWT-based authentication system for the application with comprehensive role-based access control and token refresh functionality",
  "assigned_to_id": "user-456",
  "assigned_to_first_name": "Jane",
  "assigned_to_last_name": "Doe",
  "assigned_to_email": "jane.doe@company.com",
  "assigned_by_id": "user-123",
  "assigned_by_first_name": "John",
  "assigned_by_last_name": "Coordinator",
  "assigned_by_email": "coordinator@hospital.com",
  "start_date": "2025-11-15",
  "due_date": "2025-12-05",
  "priority": "high",
  "status": "completed",
  "progress_percentage": 100,
  "created_at": "2025-11-12T10:30:00.000Z",
  "updated_at": "2025-11-12T15:00:00.000Z",
  "comments": [],
  "daily_reports": []
}
```

---

### Delete Task
**Purpose:** Deletes a task and all associated comments and daily reports.
**Method:** DELETE
**URL:** `http://localhost:9090/api/project-manager/api/tasks/{task_id}/`

**Example URL:** `http://localhost:9090/api/project-manager/api/tasks/APP-TASK-000001/`

**Response:** 204 No Content

---

## Comment Management

### Add Comment to Task
**Purpose:** Adds a comment to a specific task.
**Method:** POST
**URL:** `http://localhost:9090/api/project-manager/api/tasks/{task_id}/comment/`

**Example URL:** `http://localhost:9090/api/project-manager/api/tasks/APP-TASK-000001/comment/`

**Request Body:**
```json
{
  "text": "I've completed the JWT implementation and added role-based permissions. Ready for testing."
}
```

**Response:**
```json
{
  "id": "c3d4e5f6-g7h8-9012-cdef-345678901234",
  "task": "APP-TASK-000001",
  "user_id": "user-456",
  "user_first_name": "Jane",
  "user_last_name": "Doe",
  "user_email": "jane.doe@company.com",
  "text": "I've completed the JWT implementation and added role-based permissions. Ready for testing.",
  "created_at": "2025-11-12T16:00:00.000Z"
}
```

---

### Get All Comments
**Purpose:** Retrieves all comments across all tasks.
**Method:** GET
**URL:** `http://localhost:9090/api/project-manager/api/comments/`

**Response:**
```json
[
  {
    "id": "c3d4e5f6-g7h8-9012-cdef-345678901234",
    "task": "APP-TASK-000001",
    "user_id": "user-456",
    "user_first_name": "Jane",
    "user_last_name": "Doe",
    "user_email": "jane.doe@company.com",
    "text": "I've completed the JWT implementation and added role-based permissions. Ready for testing.",
    "created_at": "2025-11-12T16:00:00.000Z"
  },
  {
    "id": "d4e5f6g7-h8i9-0123-def0-456789012345",
    "task": "APP-TASK-000002",
    "user_id": "user-123",
    "user_first_name": "John",
    "user_last_name": "Coordinator",
    "user_email": "coordinator@hospital.com",
    "text": "Please review the database migration script before proceeding.",
    "created_at": "2025-11-12T16:30:00.000Z"
  }
]
```

---

## Daily Report Management

### Create Daily Report
**Purpose:** Creates a daily progress report for a task, updating task status if changed.
**Method:** POST
**URL:** `http://localhost:9090/api/project-manager/api/tasks/{task_id}/report/`

**Example URL:** `http://localhost:9090/api/project-manager/api/tasks/APP-TASK-000001/report/`

**Request Body:**
```json
{
  "completed_description": "Completed JWT token validation and refresh logic. Added comprehensive error handling.",
  "remaining_description": "Write unit tests and integration tests for the authentication system.",
  "reason_for_incompletion": "",
  "next_action_plan": "Start writing tests tomorrow morning. Focus on edge cases and security vulnerabilities.",
  "status": "in_progress"
}
```

**Response:**
```json
{
  "id": "e5f6g7h8-i9j0-1234-ef01-567890123456",
  "task": "APP-TASK-000001",
  "date": "2025-11-12",
  "updated_by_id": "user-456",
  "updated_by_first_name": "Jane",
  "updated_by_last_name": "Doe",
  "updated_by_email": "jane.doe@company.com",
  "completed_description": "Completed JWT token validation and refresh logic. Added comprehensive error handling.",
  "remaining_description": "Write unit tests and integration tests for the authentication system.",
  "reason_for_incompletion": "",
  "next_action_plan": "Start writing tests tomorrow morning. Focus on edge cases and security vulnerabilities.",
  "status": "in_progress",
  "attachments": [],
  "created_at": "2025-11-12T17:30:00.000Z"
}
```

---

### Get All Daily Reports
**Purpose:** Retrieves all daily reports across all tasks.
**Method:** GET
**URL:** `http://localhost:9090/api/project-manager/api/reports/`

**Response:**
```json
[
  {
    "id": "e5f6g7h8-i9j0-1234-ef01-567890123456",
    "task": "APP-TASK-000001",
    "date": "2025-11-12",
    "updated_by_id": "user-456",
    "updated_by_first_name": "Jane",
    "updated_by_last_name": "Doe",
    "updated_by_email": "jane.doe@company.com",
    "completed_description": "Completed JWT token validation and refresh logic. Added comprehensive error handling.",
    "remaining_description": "Write unit tests and integration tests for the authentication system.",
    "reason_for_incompletion": "",
    "next_action_plan": "Start writing tests tomorrow morning. Focus on edge cases and security vulnerabilities.",
    "status": "in_progress",
    "attachments": [],
    "created_at": "2025-11-12T17:30:00.000Z"
  },
  {
    "id": "f6g7h8i9-j0k1-2345-f012-678901234567",
    "task": "APP-TASK-000002",
    "date": "2025-11-12",
    "updated_by_id": "user-789",
    "updated_by_first_name": "Bob",
    "updated_by_last_name": "Smith",
    "updated_by_email": "bob.smith@company.com",
    "completed_description": "Successfully migrated all tables to new PostgreSQL schema. Verified data integrity.",
    "remaining_description": "Update application code to use new column names and relationships.",
    "reason_for_incompletion": "",
    "next_action_plan": "Deploy migration to staging environment and test thoroughly.",
    "status": "completed",
    "attachments": [],
    "created_at": "2025-11-12T18:00:00.000Z"
  }
]
```

---

## API Documentation

### Swagger UI
**Purpose:** Interactive API documentation with testing capabilities.
**Method:** GET
**URL:** `http://localhost:9090/api/project-manager/api/schema/swagger-ui/`

### ReDoc
**Purpose:** Alternative API documentation view.
**Method:** GET
**URL:** `http://localhost:9090/api/project-manager/api/schema/redoc/`

### OpenAPI Schema
**Purpose:** Raw OpenAPI schema for the API.
**Method:** GET
**URL:** `http://localhost:9090/api/project-manager/api/schema/`

---

## Error Responses

### Authentication Error
**Status:** 401 Unauthorized

**Response:**
```json
{
  "detail": "Authentication required"
}
```

### Validation Error
**Status:** 400 Bad Request

**Response:**
```json
{
  "title": ["This field is required."],
  "assigned_to_id": ["User with this ID does not exist."]
}
```

### Not Found Error
**Status:** 404 Not Found

**Response:**
```json
{
  "detail": "Not found."
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

---

## Notes

- All endpoints require JWT authentication via the `Authorization: Bearer <token>` header
- Task IDs are auto-generated in the format `{TENANT_PREFIX}-TASK-{SEQUENTIAL_NUMBER}` (e.g., APP-TASK-000001)
- Comments and daily reports are automatically associated with the authenticated user
- Daily reports automatically update the task status if a new status is provided
- Status updates to 'completed' or 'blocked' automatically create a daily report
- The service supports multi-tenancy with schema-based separation

## Analytics & Performance Metrics

### User Performance Calculation
The admin dashboard calculates user performance metrics using the following formulas:

**Completion Rate:** `(completed tasks / total assigned tasks) × 100`

**Average Progress:** `Σ(progress_percentage) / total tasks`

**Performance Score:** Weighted calculation where:
- Completion Rate: 40% weight
- Average Progress: 40% weight
- Timeliness (inverse of overdue ratio): 20% weight

**Overdue Tasks:** Tasks with `due_date < current_date` and `status ≠ 'completed'`

### Analytics API Usage
- `GET /api/project-manager/api/users/{userId}/tasks/` - Retrieves all tasks for a specific user
- Used by admin dashboard for real-time performance analytics
- Returns direct array of tasks (not paginated) for efficient client-side processing
- Data is aggregated client-side for performance metrics and visualizations

---

## Pagination

### Overview
The Task Management API supports pagination for large datasets. Pagination is automatically applied to the main task listing endpoint (`/tasks/`) with a default page size of 20 items.

### Pagination Parameters
- `page`: The page number to retrieve (default: 1)
- `page_size`: Number of items per page (default: 20, maximum: 100)

### Pagination Response Format
```json
{
  "count": 150,  // Total number of items across all pages
  "next": "http://localhost:9090/api/project-manager/api/tasks/?page=2",  // Next page URL
  "previous": null,  // Previous page URL (null if on first page)
  "results": [...]  // Array of task objects for current page
}
```

### Pagination Examples
- First page: `GET /api/project-manager/api/tasks/`
- Second page: `GET /api/project-manager/api/tasks/?page=2`
- Custom page size: `GET /api/project-manager/api/tasks/?page_size=50`
- Combined with filters: `GET /api/project-manager/api/tasks/?status=completed&page=3&page_size=25`

### Frontend Implementation
Both AdminDashboard and Dashboard components include uniform pagination controls:
- Page navigation buttons (First, Previous, Next, Last)
- Page number buttons with ellipsis for large page ranges
- Items per page information
- Loading states during pagination
- Consistent styling and behavior across components

---

## Knowledge Base Management

The Knowledge Base API follows the same gateway routing pattern as the Task Management API, providing a comprehensive content management system with categories, tags, and rich articles.

### Create Category
**Purpose:** Creates a new category for organizing articles.
**Method:** POST
**URL:** `http://localhost:9090/api/project-manager/api/categories/`

**Production URL:** `https://server1.prolianceltd.com/api/project-manager/api/categories/`

**Request Body:**
```json
{
  "name": "Technology",
  "description": "Articles about technology, programming, and software development"
}
```

**Response:**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "name": "Technology",
  "description": "Articles about technology, programming, and software development",
  "created_at": "2025-11-24T08:30:00.000Z",
  "updated_at": "2025-11-24T08:30:00.000Z"
}
```

---

### Get All Categories
**Purpose:** Retrieves all categories for organizing articles.
**Method:** GET
**URL:** `http://localhost:9090/api/project-manager/api/categories/`

**Response:**
```json
[
  {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "name": "Technology",
    "description": "Articles about technology, programming, and software development",
    "created_at": "2025-11-24T08:30:00.000Z",
    "updated_at": "2025-11-24T08:30:00.000Z"
  },
  {
    "id": "b2c3d4e5-f6g7-8901-bcde-f23456789012",
    "name": "Business",
    "description": "Business strategy, management, and entrepreneurship articles",
    "created_at": "2025-11-24T08:35:00.000Z",
    "updated_at": "2025-11-24T08:35:00.000Z"
  }
]
```

---

### Create Tag
**Purpose:** Creates a new tag for flexible article categorization.
**Method:** POST
**URL:** `http://localhost:9090/api/project-manager/api/tags/`

**Request Body:**
```json
{
  "name": "django"
}
```

**Response:**
```json
{
  "id": "c3d4e5f6-g7h8-9012-cdef-345678901234",
  "name": "django",
  "created_at": "2025-11-24T08:40:00.000Z"
}
```

---

### Get All Tags
**Purpose:** Retrieves all available tags.
**Method:** GET
**URL:** `http://localhost:9090/api/project-manager/api/tags/`

**Response:**
```json
[
  {
    "id": "c3d4e5f6-g7h8-9012-cdef-345678901234",
    "name": "django",
    "created_at": "2025-11-24T08:40:00.000Z"
  },
  {
    "id": "d4e5f6g7-h8i9-0123-def0-456789012345",
    "name": "react",
    "created_at": "2025-11-24T08:45:00.000Z"
  }
]
```

---

### Create Article
**Purpose:** Creates a new article with rich content and metadata.
**Method:** POST
**URL:** `http://localhost:9090/api/project-manager/api/articles/`

**Production URL:** `https://server1.prolianceltd.com/api/project-manager/api/articles/`

**Request Body:**
```json
{
  "title": "Getting Started with Django REST Framework",
  "content": "<h1>Introduction</h1><p>Django REST Framework is a powerful toolkit for building Web APIs...</p>",
  "excerpt": "Learn how to build robust APIs with Django REST Framework",
  "category": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "tags": ["django", "api", "python"],
  "status": "published",
  "featured_image": "https://example.com/django-rest-framework.jpg",
  "reading_time": 5,
  "published_at": "2025-11-24T09:00:00.000Z"
}
```

**Response:**
```json
{
  "id": "e5f6g7h8-i9j0-1234-ef01-567890123456",
  "title": "Getting Started with Django REST Framework",
  "slug": "getting-started-with-django-rest-framework",
  "content": "<h1>Introduction</h1><p>Django REST Framework is a powerful toolkit for building Web APIs...</p>",
  "excerpt": "Learn how to build robust APIs with Django REST Framework",
  "author_id": "user-123",
  "author_first_name": "John",
  "author_last_name": "Doe",
  "author_email": "john.doe@company.com",
  "category": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "category_name": "Technology",
  "tags": ["c3d4e5f6-g7h8-9012-cdef-345678901234", "d4e5f6g7-h8i9-0123-def0-456789012345"],
  "tags_list": ["django", "api"],
  "status": "published",
  "featured_image": "https://example.com/django-rest-framework.jpg",
  "reading_time": 5,
  "view_count": 0,
  "published_at": "2025-11-24T09:00:00.000Z",
  "created_at": "2025-11-24T08:50:00.000Z",
  "updated_at": "2025-11-24T08:50:00.000Z"
}
```

---

### Get All Articles
**Purpose:** Retrieves articles with optional filtering and pagination.
**Method:** GET
**URL:** `http://localhost:9090/api/project-manager/api/articles/`

**Production URL:** `https://server1.prolianceltd.com/api/project-manager/api/articles/`

**Optional Query Parameters:**
- `status`: Filter by status (draft, published, archived)
- `category`: Filter by category ID
- `author`: Filter by author ID
- `search`: Full-text search in title, content, and excerpt
- `tags`: Filter by tag names (comma-separated)
- `page`: Page number for pagination
- `page_size`: Items per page (default: 20, max: 100)

**Example URLs:**
- All articles: `http://localhost:9090/api/project-manager/api/articles/`
- Published only: `http://localhost:9090/api/project-manager/api/articles/?status=published`
- By category: `http://localhost:9090/api/project-manager/api/articles/?category=a1b2c3d4-e5f6-7890-abcd-ef1234567890`
- Search: `http://localhost:9090/api/project-manager/api/articles/?search=django`
- By tags: `http://localhost:9090/api/project-manager/api/articles/?tags=django,api`

**Response:**
```json
{
  "count": 25,
  "next": "http://localhost:9090/api/project-manager/api/articles/?page=2",
  "previous": null,
  "results": [
    {
      "id": "e5f6g7h8-i9j0-1234-ef01-567890123456",
      "title": "Getting Started with Django REST Framework",
      "slug": "getting-started-with-django-rest-framework",
      "excerpt": "Learn how to build robust APIs with Django REST Framework",
      "author_name": "John Doe",
      "category_name": "Technology",
      "status": "published",
      "published_at": "2025-11-24T09:00:00.000Z",
      "created_at": "2025-11-24T08:50:00.000Z",
      "view_count": 42,
      "tags_count": 3
    }
  ]
}
```

---

### Get Published Articles
**Purpose:** Retrieves only published articles for public consumption.
**Method:** GET
**URL:** `http://localhost:9090/api/project-manager/api/articles/published/`

**Response:** Same pagination format as Get All Articles, but filtered to published status only.

---

### Get My Articles
**Purpose:** Retrieves articles authored by the current user.
**Method:** GET
**URL:** `http://localhost:9090/api/project-manager/api/articles/my_articles/`

**Response:** Same pagination format as Get All Articles, but filtered to current user's articles.

---

### Get Featured Articles
**Purpose:** Retrieves featured articles (published with featured images).
**Method:** GET
**URL:** `http://localhost:9090/api/project-manager/api/articles/featured/`

**Response:**
```json
[
  {
    "id": "e5f6g7h8-i9j0-1234-ef01-567890123456",
    "title": "Getting Started with Django REST Framework",
    "slug": "getting-started-with-django-rest-framework",
    "excerpt": "Learn how to build robust APIs with Django REST Framework",
    "author_name": "John Doe",
    "category_name": "Technology",
    "published_at": "2025-11-24T09:00:00.000Z",
    "created_at": "2025-11-24T08:50:00.000Z",
    "view_count": 42,
    "tags_count": 3
  }
]
```

---

### Get Article by ID
**Purpose:** Retrieves detailed information for a specific article.
**Method:** GET
**URL:** `http://localhost:9090/api/project-manager/api/articles/{article_id}/`

**Example URL:** `http://localhost:9090/api/project-manager/api/articles/e5f6g7h8-i9j0-1234-ef01-567890123456/`

**Response:**
```json
{
  "id": "e5f6g7h8-i9j0-1234-ef01-567890123456",
  "title": "Getting Started with Django REST Framework",
  "slug": "getting-started-with-django-rest-framework",
  "content": "<h1>Introduction</h1><p>Django REST Framework is a powerful toolkit for building Web APIs...</p>",
  "excerpt": "Learn how to build robust APIs with Django REST Framework",
  "author_id": "user-123",
  "author_first_name": "John",
  "author_last_name": "Doe",
  "author_email": "john.doe@company.com",
  "category": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "category_name": "Technology",
  "tags": ["c3d4e5f6-g7h8-9012-cdef-345678901234", "d4e5f6g7-h8i9-0123-def0-456789012345"],
  "tags_list": ["django", "api"],
  "status": "published",
  "featured_image": "https://example.com/django-rest-framework.jpg",
  "reading_time": 5,
  "view_count": 42,
  "published_at": "2025-11-24T09:00:00.000Z",
  "created_at": "2025-11-24T08:50:00.000Z",
  "updated_at": "2025-11-24T08:50:00.000Z"
}
```

---

### Update Article
**Purpose:** Updates an existing article.
**Method:** PUT
**URL:** `http://localhost:9090/api/project-manager/api/articles/{article_id}/`

**Request Body:** Same as Create Article, but all fields are optional for partial updates.

**Response:** Updated article object.

---

### Delete Article
**Purpose:** Deletes an article.
**Method:** DELETE
**URL:** `http://localhost:9090/api/project-manager/api/articles/{article_id}/`

**Response:** 204 No Content

---

### Increment Article View Count
**Purpose:** Increments the view count when an article is read.
**Method:** POST
**URL:** `http://localhost:9090/api/project-manager/api/articles/{article_id}/increment_view/`

**Response:**
```json
{
  "view_count": 43
}
```