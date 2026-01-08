# 📚 LMS API Documentation - Learning Management System

## Overview

The LMS (Learning Management System) microservice provides comprehensive course management, enrollment, messaging, scheduling, and payment processing capabilities for educational platforms. It supports multi-tenancy, SCORM content, gamification features, and integrates with authentication and notification services.

## Base URL
```
http://localhost:9090/api/lms/
```

## Authentication

The LMS service uses JWT-based authentication provided by the auth-service. All API requests require a valid JWT token in the Authorization header.

**Header:**
```
Authorization: Bearer YOUR_JWT_TOKEN
```

---

## Course Management

### List Courses
**Purpose:** Retrieves paginated list of courses with enrollment counts and FAQ statistics.
**Method:** GET
**URL:** `http://localhost:9090/api/lms/courses/`

**Query Parameters:**
- `page` (optional): Page number (default: 1)
- `page_size` (optional): Items per page (default: 10, max: 100)

**Response:**
```json
{
  "count": 25,
  "next": "http://localhost:9090/api/lms/courses/?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "title": "Introduction to Python Programming",
      "description": "Learn the basics of Python programming",
      "slug": "introduction-to-python-programming",
      "code": "PY101",
      "level": "Beginner",
      "status": "Published",
      "is_free": true,
      "price": "0.00",
      "currency": "USD",
      "thumbnail_url": "https://storage.example.com/courses/tenant1/introduction-to-python-programming/thumbnails/abc123_image.jpg",
      "category": {
        "id": 1,
        "name": "Programming",
        "slug": "programming"
      },
      "total_enrollments": 150,
      "faq_count": 5,
      "created_at": "2024-01-15T10:00:00Z",
      "updated_at": "2024-01-20T14:30:00Z"
    }
  ],
  "total_all_enrollments": 1250
}
```

---

### Create Course
**Purpose:** Creates a new course with basic information.
**Method:** POST
**URL:** `http://localhost:9090/api/lms/courses/`

**Request Body:**
```json
{
  "title": "Advanced JavaScript Concepts",
  "description": "Deep dive into advanced JavaScript features and patterns",
  "short_description": "Master advanced JS concepts",
  "category_id": 2,
  "level": "Advanced",
  "status": "Draft",
  "is_free": false,
  "price": "99.99",
  "currency": "USD",
  "learning_outcomes": [
    "Understand closures and scope",
    "Master asynchronous programming",
    "Implement design patterns"
  ],
  "prerequisites": [
    "Basic JavaScript knowledge",
    "HTML and CSS fundamentals"
  ]
}
```

**Response:**
```json
{
  "id": 26,
  "title": "Advanced JavaScript Concepts",
  "description": "Deep dive into advanced JavaScript features and patterns",
  "slug": "advanced-javascript-concepts",
  "code": "JS201",
  "level": "Advanced",
  "status": "Draft",
  "is_free": false,
  "price": "99.99",
  "currency": "USD",
  "thumbnail_url": "",
  "category": {
    "id": 2,
    "name": "Web Development",
    "slug": "web-development"
  },
  "total_enrollments": 0,
  "faq_count": 0,
  "created_at": "2024-01-25T09:00:00Z",
  "updated_at": "2024-01-25T09:00:00Z"
}
```

---

### Get Course Details
**Purpose:** Retrieves detailed information for a specific course including modules, resources, and instructors.
**Method:** GET
**URL:** `http://localhost:9090/api/lms/courses/{course_id}/`

**Response:**
```json
{
  "id": 1,
  "title": "Introduction to Python Programming",
  "description": "Learn the basics of Python programming",
  "slug": "introduction-to-python-programming",
  "code": "PY101",
  "level": "Beginner",
  "status": "Published",
  "is_free": true,
  "price": "0.00",
  "currency": "USD",
  "thumbnail_url": "https://storage.example.com/courses/tenant1/introduction-to-python-programming/thumbnails/abc123_image.jpg",
  "category": {
    "id": 1,
    "name": "Programming",
    "slug": "programming"
  },
  "learning_outcomes": [
    "Write basic Python scripts",
    "Understand data types and variables",
    "Use control structures"
  ],
  "prerequisites": [
    "Basic computer literacy"
  ],
  "modules": [
    {
      "id": 1,
      "title": "Getting Started with Python",
      "description": "Installation and basic setup",
      "order": 1,
      "is_published": true,
      "lessons": [
        {
          "id": 1,
          "title": "Installing Python",
          "lesson_type": "text",
          "duration": 15,
          "order": 1,
          "is_published": true
        }
      ]
    }
  ],
  "resources": [
    {
      "id": 1,
      "title": "Python Cheat Sheet",
      "resource_type": "file",
      "url": "",
      "file_url": "https://storage.example.com/courses/tenant1/introduction-to-python-programming/resources/cheat_sheet.pdf",
      "order": 1
    }
  ],
  "course_instructors": [
    {
      "id": "user123",
      "email": "instructor@example.com",
      "first_name": "John",
      "last_name": "Doe",
      "avatar_url": "https://storage.example.com/avatars/john_doe.jpg",
      "phone": "+1234567890"
    }
  ],
  "certificate_settings": {
    "id": 1,
    "is_active": true,
    "template": "default",
    "custom_text": "Congratulations on completing the course!",
    "show_date": true,
    "show_course_name": true,
    "show_completion_hours": true,
    "min_score": 80,
    "require_all_modules": true
  },
  "total_enrollments": 150,
  "faq_count": 5
}
```

---

### Update Course
**Purpose:** Updates an existing course's information.
**Method:** PUT/PATCH
**URL:** `http://localhost:9090/api/lms/courses/{course_id}/`

**Request Body (PATCH example):**
```json
{
  "status": "Published",
  "price": "79.99"
}
```

**Response:** Similar to course details response.

---

### Delete Course
**Purpose:** Deletes a course and all associated content.
**Method:** DELETE
**URL:** `http://localhost:9090/api/lms/courses/{course_id}/`

**Response:** 204 No Content

---

### Get Most Popular Courses
**Purpose:** Retrieves the course with the highest enrollment count.
**Method:** GET
**URL:** `http://localhost:9090/api/lms/courses/most_popular/`

**Response:**
```json
{
  "course": {
    "id": 5,
    "title": "Data Science Fundamentals",
    "description": "Learn the basics of data science",
    "slug": "data-science-fundamentals",
    "code": "DS101",
    "level": "Intermediate",
    "status": "Published",
    "is_free": false,
    "price": "149.99",
    "currency": "USD",
    "thumbnail_url": "https://storage.example.com/courses/tenant1/data-science-fundamentals/thumbnails/ds_thumb.jpg",
    "category": {
      "id": 3,
      "name": "Data Science",
      "slug": "data-science"
    },
    "total_enrollments": 320,
    "faq_count": 12
  },
  "enrollment_count": 320
}
```

---

### Get Least Popular Courses
**Purpose:** Retrieves the course with the lowest enrollment count (among courses with enrollments).
**Method:** GET
**URL:** `http://localhost:9090/api/lms/courses/least_popular/`

**Response:** Similar to most popular response.

---

## Module Management

### List Modules for Course
**Purpose:** Retrieves all modules for a specific course.
**Method:** GET
**URL:** `http://localhost:9090/api/lms/courses/{course_id}/modules/`

**Response:**
```json
[
  {
    "id": 1,
    "title": "Getting Started with Python",
    "description": "Installation and basic setup",
    "order": 1,
    "is_published": true,
    "lessons": [
      {
        "id": 1,
        "title": "Installing Python",
        "description": "Step-by-step installation guide",
        "lesson_type": "text",
        "duration": 15,
        "content_url": "",
        "content_file": "",
        "content_file_url": "",
        "content_text": "Python can be downloaded from python.org...",
        "order": 1,
        "is_published": true
      }
    ]
  }
]
```

---

### Create Module
**Purpose:** Creates a new module for a course.
**Method:** POST
**URL:** `http://localhost:9090/api/lms/courses/{course_id}/modules/`

**Request Body:**
```json
{
  "title": "Variables and Data Types",
  "description": "Understanding Python variables and data types",
  "order": 2,
  "is_published": true
}
```

**Response:**
```json
{
  "id": 2,
  "title": "Variables and Data Types",
  "description": "Understanding Python variables and data types",
  "order": 2,
  "is_published": true,
  "lessons": []
}
```

---

### Get Module Details
**Purpose:** Retrieves detailed information for a specific module.
**Method:** GET
**URL:** `http://localhost:9090/api/lms/courses/{course_id}/modules/{module_id}/`

**Response:** Similar to module in list response.

---

### Update Module
**Purpose:** Updates module information.
**Method:** PUT/PATCH
**URL:** `http://localhost:9090/api/lms/courses/{course_id}/modules/{module_id}/`

---

### Delete Module
**Purpose:** Deletes a module and all its lessons.
**Method:** DELETE
**URL:** `http://localhost:9090/api/lms/courses/{course_id}/modules/{module_id}/`

---

## Lesson Management

### List Lessons for Module
**Purpose:** Retrieves all lessons for a specific module.
**Method:** GET
**URL:** `http://localhost:9090/api/lms/courses/{course_id}/modules/{module_id}/lessons/`

**Response:**
```json
[
  {
    "id": 1,
    "title": "Installing Python",
    "description": "Step-by-step installation guide",
    "lesson_type": "text",
    "duration": 15,
    "content_url": "",
    "content_file": "",
    "content_file_url": "",
    "content_text": "Python can be downloaded from python.org...",
    "order": 1,
    "is_published": true
  }
]
```

---

### Create Lesson
**Purpose:** Creates a new lesson for a module.
**Method:** POST
**URL:** `http://localhost:9090/api/lms/courses/{course_id}/modules/{module_id}/lessons/`

**Request Body:**
```json
{
  "title": "Hello World Program",
  "description": "Writing your first Python program",
  "lesson_type": "text",
  "duration": 20,
  "content_text": "print('Hello, World!')",
  "order": 2,
  "is_published": true
}
```

**Response:**
```json
{
  "id": 2,
  "title": "Hello World Program",
  "description": "Writing your first Python program",
  "lesson_type": "text",
  "duration": 20,
  "content_url": "",
  "content_file": "",
  "content_file_url": "",
  "content_text": "print('Hello, World!')",
  "order": 2,
  "is_published": true
}
```

---

### Get Lesson Details
**Purpose:** Retrieves detailed information for a specific lesson.
**Method:** GET
**URL:** `http://localhost:9090/api/lms/courses/{course_id}/modules/{module_id}/lessons/{lesson_id}/`

---

### Update Lesson
**Purpose:** Updates lesson information.
**Method:** PUT/PATCH
**URL:** `http://localhost:9090/api/lms/courses/{course_id}/modules/{module_id}/lessons/{lesson_id}/`

---

### Delete Lesson
**Purpose:** Deletes a lesson.
**Method:** DELETE
**URL:** `http://localhost:9090/api/lms/courses/{course_id}/modules/{module_id}/lessons/{lesson_id}/`

---

## Enrollment Management

### List User Enrollments
**Purpose:** Retrieves all enrollments for the authenticated user.
**Method:** GET
**URL:** `http://localhost:9090/api/lms/enrollments/for/user/`

**Response:**
```json
[
  {
    "id": 1,
    "course": {
      "id": 1,
      "title": "Introduction to Python Programming",
      "description": "Learn the basics of Python programming",
      "thumbnail": "python_thumb.jpg",
      "thumbnail_url": "https://storage.example.com/courses/tenant1/introduction-to-python-programming/thumbnails/python_thumb.jpg",
      "resources": [
        {
          "id": 1,
          "title": "Python Cheat Sheet",
          "type": "file",
          "url": "",
          "file": "cheat_sheet.pdf",
          "file_url": "https://storage.example.com/courses/tenant1/introduction-to-python-programming/resources/cheat_sheet.pdf",
          "order": 1
        }
      ],
      "modules": [
        {
          "id": 1,
          "title": "Getting Started",
          "order": 1,
          "lessons": [
            {
              "id": 1,
              "title": "Installation",
              "type": "text",
              "duration": 15,
              "order": 1,
              "is_published": true,
              "content_url": "",
              "content_file": "",
              "content_file_url": ""
            }
          ]
        }
      ],
      "instructors": [
        {
          "id": "user123",
          "name": "John Doe",
          "bio": "Senior Python Developer"
        }
      ]
    },
    "enrolled_at": "2024-01-20T10:00:00Z",
    "completed_at": null
  }
]
```

---

### Enroll User to Course
**Purpose:** Enrolls a user to a published course.
**Method:** POST
**URL:** `http://localhost:9090/api/lms/enrollments/course/{course_id}/enroll/`

**Request Body:**
```json
{
  "user_id": "user456"
}
```

**Response:**
```json
{
  "id": 2,
  "user_id": "user456",
  "user_name": "Jane Smith",
  "course": {
    "id": 1,
    "title": "Introduction to Python Programming",
    "description": "Learn the basics of Python programming"
  },
  "course_id": 1,
  "enrolled_at": "2024-01-25T14:30:00Z",
  "started_at": null,
  "completed_at": null,
  "is_active": true
}
```

---

### Bulk Enroll Users
**Purpose:** Enrolls multiple users to a course at once.
**Method:** POST
**URL:** `http://localhost:9090/api/lms/enrollments/course/{course_id}/bulk/`

**Request Body:**
```json
{
  "user_ids": ["user456", "user789", "user101"]
}
```

**Response:**
```json
{
  "detail": "Enrolled 3 users",
  "created": 3,
  "already_enrolled": 0
}
```

---

### Get Course Enrollments
**Purpose:** Retrieves all enrollments for a specific course (admin only).
**Method:** GET
**URL:** `http://localhost:9090/api/lms/enrollments/course/{course_id}/`

---

### Get User Courses
**Purpose:** Retrieves courses enrolled by the authenticated user with progress information.
**Method:** GET
**URL:** `http://localhost:9090/api/lms/enrollments/my-courses/`

**Response:**
```json
[
  {
    "id": 1,
    "title": "Introduction to Python Programming",
    "description": "Learn the basics of Python programming",
    "slug": "introduction-to-python-programming",
    "level": "Beginner",
    "thumbnail_url": "https://storage.example.com/courses/tenant1/introduction-to-python-programming/thumbnails/python_thumb.jpg",
    "progress": 65,
    "enrolled_at": "2024-01-20T10:00:00Z",
    "completed_at": null
  }
]
```

---

### Mark Lesson as Completed
**Purpose:** Marks a lesson as completed for the authenticated user.
**Method:** POST
**URL:** `http://localhost:9090/api/lms/enrollments/lesson-completion/`

**Request Body:**
```json
{
  "lesson": 1
}
```

**Response:**
```json
{
  "detail": "Lesson marked as completed"
}
```

---

## Assignment Management

### List Assignments
**Purpose:** Retrieves assignments for courses the user is enrolled in or all assignments for instructors.
**Method:** GET
**URL:** `http://localhost:9090/api/lms/assignments/`

**Query Parameters:**
- `course` (optional): Filter by course ID
- `module` (optional): Filter by module ID

**Response:**
```json
[
  {
    "id": 1,
    "title": "Python Variables Exercise",
    "description": "Practice creating and using variables in Python",
    "course": 1,
    "module": 2,
    "due_date": "2024-02-15T23:59:59Z",
    "course_name": "Introduction to Python Programming",
    "module_name": "Variables and Data Types",
    "instructions_file_url": "https://storage.example.com/courses/tenant1/introduction-to-python-programming/assignments/instructions.pdf",
    "created_at": "2024-01-25T10:00:00Z"
  }
]
```

---

### Create Assignment
**Purpose:** Creates a new assignment for a course/module.
**Method:** POST
**URL:** `http://localhost:9090/api/lms/assignments/`

**Request Body:**
```json
{
  "title": "Functions Practice",
  "description": "Write Python functions to solve the given problems",
  "course": 1,
  "module": 3,
  "due_date": "2024-02-20T23:59:59Z"
}
```

---

### Submit Assignment
**Purpose:** Submits an assignment solution.
**Method:** POST
**URL:** `http://localhost:9090/api/lms/assignment-submissions/`

**Request Body:**
```json
{
  "assignment": 1,
  "response_text": "Here is my solution...",
  "submission_file": "solution.py"
}
```

**Response:**
```json
{
  "id": 1,
  "assignment": {
    "id": 1,
    "title": "Python Variables Exercise",
    "course_name": "Introduction to Python Programming",
    "module_name": "Variables and Data Types"
  },
  "student_id": "user456",
  "student_name": "Jane Smith",
  "submitted_at": "2024-02-10T15:30:00Z",
  "response_text": "Here is my solution...",
  "submission_file_url": "https://storage.example.com/courses/tenant1/introduction-to-python-programming/assignments/submissions/solution.py",
  "grade": null,
  "feedback": "",
  "is_graded": false
}
```

---

## Category Management

### List Categories
**Purpose:** Retrieves all course categories with course counts.
**Method:** GET
**URL:** `http://localhost:9090/api/lms/categories/`

**Response:**
```json
[
  {
    "id": 1,
    "name": "Programming",
    "slug": "programming",
    "description": "Courses related to programming languages and development",
    "course_count": 15
  },
  {
    "id": 2,
    "name": "Web Development",
    "slug": "web-development",
    "description": "Frontend and backend web development courses",
    "course_count": 8
  }
]
```

---

### Create Category
**Purpose:** Creates a new course category.
**Method:** POST
**URL:** `http://localhost:9090/api/lms/categories/`

**Request Body:**
```json
{
  "name": "Data Science",
  "description": "Courses covering data analysis, machine learning, and statistics"
}
```

---

## Certificate Management

### Get User Certificates
**Purpose:** Retrieves certificates earned by the authenticated user.
**Method:** GET
**URL:** `http://localhost:9090/api/lms/certificates/`

**Response:**
```json
[
  {
    "id": 1,
    "enrollment": 1,
    "course_title": "Introduction to Python Programming",
    "issued_at": "2024-02-01T10:00:00Z",
    "certificate_id": "CERT-PY101-001",
    "pdf_file_url": "https://storage.example.com/certificates/tenant1/CERT-PY101-001.pdf"
  }
]
```

---

### Get Certificate Template
**Purpose:** Retrieves certificate template settings for a course.
**Method:** GET
**URL:** `http://localhost:9090/api/lms/certificates/course/{course_id}/template/`

---

### Update Certificate Template
**Purpose:** Updates certificate template settings for a course.
**Method:** PATCH
**URL:** `http://localhost:9090/api/lms/certificates/course/{course_id}/template/`

**Request Body:**
```json
{
  "custom_text": "Congratulations on successfully completing this comprehensive course!",
  "min_score": 85,
  "require_all_modules": true
}
```

---

## FAQ Management

### List Course FAQs
**Purpose:** Retrieves FAQs for a specific course.
**Method:** GET
**URL:** `http://localhost:9090/api/lms/courses/{course_id}/faqs/`

---

### Create FAQ
**Purpose:** Creates a new FAQ for a course.
**Method:** POST
**URL:** `http://localhost:9090/api/lms/courses/{course_id}/faqs/`

**Request Body:**
```json
{
  "question": "How do I reset my password?",
  "answer": "You can reset your password by clicking 'Forgot Password' on the login page.",
  "order": 1
}
```

---

### Reorder FAQs
**Purpose:** Updates the order of FAQs for a course.
**Method:** POST
**URL:** `http://localhost:9090/api/lms/courses/{course_id}/faqs/reorder/`

**Request Body:**
```json
{
  "faqs": [
    {"id": 1, "order": 2},
    {"id": 2, "order": 1}
  ]
}
```

---

## Resource Management

### List Course Resources
**Purpose:** Retrieves resources for a specific course.
**Method:** GET
**URL:** `http://localhost:9090/api/lms/courses/{course_id}/resources/`

---

### Create Resource
**Purpose:** Creates a new resource for a course.
**Method:** POST
**URL:** `http://localhost:9090/api/lms/courses/{course_id}/resources/`

**Request Body:**
```json
{
  "title": "Python Reference Guide",
  "resource_type": "file",
  "order": 1
}
```

---

### Reorder Resources
**Purpose:** Updates the order of resources for a course.
**Method:** POST
**URL:** `http://localhost:9090/api/lms/courses/{course_id}/resources/reorder/`

**Request Body:**
```json
{
  "resources": [
    {"id": 1, "order": 2},
    {"id": 2, "order": 1}
  ]
}
```

---

## Learning Path Management

### List Learning Paths
**Purpose:** Retrieves all active learning paths.
**Method:** GET
**URL:** `http://localhost:9090/api/lms/learning-paths/`

---

### Create Learning Path
**Purpose:** Creates a new learning path with associated courses.
**Method:** POST
**URL:** `http://localhost:9090/api/lms/learning-paths/`

**Request Body:**
```json
{
  "title": "Full Stack Web Development",
  "description": "Complete path from frontend to backend development",
  "course_ids": [1, 2, 3],
  "is_active": true,
  "order": 1
}
```

---

## Badge and Points System

### List Badges
**Purpose:** Retrieves all available badges.
**Method:** GET
**URL:** `http://localhost:9090/api/lms/badges/`

---

### List User Badges
**Purpose:** Retrieves badges earned by the authenticated user.
**Method:** GET
**URL:** `http://localhost:9090/api/lms/user-badges/`

---

### List User Points
**Purpose:** Retrieves points earned by the authenticated user.
**Method:** GET
**URL:** `http://localhost:9090/api/lms/user-points/`

---

### Get Leaderboard
**Purpose:** Retrieves top users by total points.
**Method:** GET
**URL:** `http://localhost:9090/api/lms/user-points/leaderboard/`

**Query Parameters:**
- `course_id` (optional): Filter by specific course

---

## SCORM Content Management

### Upload SCORM Package
**Purpose:** Uploads and extracts a SCORM package for a course.
**Method:** POST
**URL:** `http://localhost:9090/api/lms/courses/{course_id}/scorm/upload/`

**Request Body (Form Data):**
- `package`: SCORM zip file

---

### Launch SCORM Content
**Purpose:** Gets the launch URL for SCORM content.
**Method:** GET
**URL:** `http://localhost:9090/api/lms/courses/{course_id}/scorm/launch/`

---

### Track SCORM Progress
**Purpose:** Records SCORM tracking data (progress, score, completion).
**Method:** POST
**URL:** `http://localhost:9090/api/lms/courses/{course_id}/scorm/track/`

**Request Body:**
```json
{
  "progress": 75,
  "score": 85,
  "completed": false
}
```

---

### Export Course as SCORM
**Purpose:** Exports a course as a SCORM package.
**Method:** GET
**URL:** `http://localhost:9090/api/lms/courses/{course_id}/scorm/export/`

---

## Messaging System

### List Messages
**Purpose:** Retrieves messages for the authenticated user.
**Method:** GET
**URL:** `http://localhost:9090/api/lms/messaging/messages/`

---

### Send Message
**Purpose:** Sends a new message.
**Method:** POST
**URL:** `http://localhost:9090/api/lms/messaging/messages/`

**Request Body:**
```json
{
  "recipient": "user123",
  "subject": "Question about assignment",
  "content": "I need help with the Python assignment...",
  "message_type": "direct"
}
```

---

### List Message Types
**Purpose:** Retrieves available message types.
**Method:** GET
**URL:** `http://localhost:9090/api/lms/messaging/message-types/`

---

## Schedule Management

### List Schedules
**Purpose:** Retrieves schedules for the tenant.
**Method:** GET
**URL:** `http://localhost:9090/api/lms/schedule/schedules/`

---

### Create Schedule
**Purpose:** Creates a new schedule entry.
**Method:** POST
**URL:** `http://localhost:9090/api/lms/schedule/schedules/`

**Request Body:**
```json
{
  "title": "Python Class Session",
  "description": "Live Q&A session for Python course",
  "scheduled_date": "2024-02-15T14:00:00Z",
  "duration": 60,
  "location": "Virtual",
  "max_attendees": 50
}
```

---

### Get Upcoming Schedules
**Purpose:** Retrieves upcoming schedule entries.
**Method:** GET
**URL:** `http://localhost:9090/api/lms/schedule/schedules/upcoming/`

---

## Group Management

### List Groups
**Purpose:** Retrieves all groups for the tenant.
**Method:** GET
**URL:** `http://localhost:9090/api/lms/groups/groups/`

---

### Create Group
**Purpose:** Creates a new group.
**Method:** POST
**URL:** `http://localhost:9090/api/lms/groups/groups/`

**Request Body:**
```json
{
  "name": "Python Study Group",
  "description": "Group for Python learners to collaborate",
  "is_private": false,
  "max_members": 20
}
```

---

### List Roles
**Purpose:** Retrieves available group roles.
**Method:** GET
**URL:** `http://localhost:9090/api/lms/groups/roles/`

---

## Payment Processing

### List Payment Gateways
**Purpose:** Retrieves configured payment gateways.
**Method:** GET
**URL:** `http://localhost:9090/api/lms/payments/payment-gateways/`

---

### Configure Payment Gateway
**Purpose:** Updates payment gateway configuration.
**Method:** PATCH
**URL:** `http://localhost:9090/api/lms/payments/payment-gateways/{gateway_id}/config/`

**Request Body:**
```json
{
  "config": {
    "api_key": "sk_test_...",
    "webhook_secret": "whsec_..."
  }
}
```

---

### List Site Currencies
**Purpose:** Retrieves available currencies for the site.
**Method:** GET
**URL:** `http://localhost:9090/api/lms/payments/site-currency/`

---

## Forum Management

### List Forums
**Purpose:** Retrieves all forums.
**Method:** GET
**URL:** `http://localhost:9090/api/lms/forums/forums/`

---

### Create Forum
**Purpose:** Creates a new forum.
**Method:** POST
**URL:** `http://localhost:9090/api/lms/forums/forums/`

**Request Body:**
```json
{
  "title": "General Discussion",
  "description": "General discussion forum for all topics",
  "is_active": true
}
```

---

### List Forum Posts
**Purpose:** Retrieves posts for a specific forum.
**Method:** GET
**URL:** `http://localhost:9090/api/lms/forums/posts/?forum={forum_id}`

---

### Create Forum Post
**Purpose:** Creates a new post in a forum.
**Method:** POST
**URL:** `http://localhost:9090/api/lms/forums/posts/`

**Request Body:**
```json
{
  "forum": 1,
  "title": "Welcome to the forum!",
  "content": "This is the first post in our forum...",
  "is_pinned": false
}
```

---

### List Moderation Queue
**Purpose:** Retrieves posts awaiting moderation.
**Method:** GET
**URL:** `http://localhost:9090/api/lms/forums/queue/`

---

## Advertising System

### List Adverts
**Purpose:** Retrieves active advertisements.
**Method:** GET
**URL:** `http://localhost:9090/api/lms/adverts/api/adverts/`

---

### Create Advert
**Purpose:** Creates a new advertisement.
**Method:** POST
**URL:** `http://localhost:9090/api/lms/adverts/api/adverts/`

**Request Body:**
```json
{
  "title": "Special Discount",
  "content": "50% off on all courses this week!",
  "advert_type": "banner",
  "is_active": true,
  "start_date": "2024-02-01T00:00:00Z",
  "end_date": "2024-02-07T23:59:59Z"
}
```

---

## AI Chat System

### List Chat Sessions
**Purpose:** Retrieves chat sessions for the authenticated user.
**Method:** GET
**URL:** `http://localhost:9090/api/lms/ai_chat/chat-sessions/`

---

### Create Chat Session
**Purpose:** Creates a new AI chat session.
**Method:** POST
**URL:** `http://localhost:9090/api/lms/ai_chat/chat-sessions/`

**Request Body:**
```json
{
  "title": "Python Help Session",
  "context": "Getting help with Python programming"
}
```

---

### Send Chat Message
**Purpose:** Sends a message in a chat session.
**Method:** POST
**URL:** `http://localhost:9090/api/lms/ai_chat/chat-sessions/{session_id}/messages/`

**Request Body:**
```json
{
  "message": "How do I create a list in Python?",
  "message_type": "user"
}
```

---

## Shopping Cart

### Get Cart
**Purpose:** Retrieves the user's shopping cart.
**Method:** GET
**URL:** `http://localhost:9090/api/lms/carts/cart/`

---

### Add to Cart
**Purpose:** Adds a course to the shopping cart.
**Method:** POST
**URL:** `http://localhost:9090/api/lms/carts/cart/`

**Request Body:**
```json
{
  "course": 1,
  "quantity": 1
}
```

---

### Update Cart Item
**Purpose:** Updates quantity of an item in the cart.
**Method:** PATCH
**URL:** `http://localhost:9090/api/lms/carts/cart/{item_id}/`

---

### Remove from Cart
**Purpose:** Removes an item from the cart.
**Method:** DELETE
**URL:** `http://localhost:9090/api/lms/carts/cart/{item_id}/`

---

### Get Wishlist
**Purpose:** Retrieves the user's wishlist.
**Method:** GET
**URL:** `http://localhost:9090/api/lms/carts/wishlist/`

---

### Add to Wishlist
**Purpose:** Adds a course to the wishlist.
**Method:** POST
**URL:** `http://localhost:9090/api/lms/carts/wishlist/`

**Request Body:**
```json
{
  "course": 2
}
```

---

### Apply Coupon
**Purpose:** Applies a coupon code to the cart.
**Method:** POST
**URL:** `http://localhost:9090/api/lms/carts/apply-coupon/`

**Request Body:**
```json
{
  "code": "SAVE20"
}
```

---

## Activity Logging

### List Activity Logs
**Purpose:** Retrieves activity logs (admin only).
**Method:** GET
**URL:** `http://localhost:9090/api/lms/activitylog/activity-logs/`

**Query Parameters:**
- `user_id` (optional): Filter by user
- `activity_type` (optional): Filter by activity type
- `date_from` (optional): Filter from date
- `date_to` (optional): Filter to date

---

## System Health

### Health Check
**Purpose:** Basic service health check.
**Method:** GET
**URL:** `http://localhost:9090/api/health/`

**Response:**
```json
{
  "status": "healthy"
}
```

---

### API Schema
**Purpose:** Retrieves OpenAPI schema for the LMS API.
**Method:** GET
**URL:** `http://localhost:9090/api/schema/`

---

### API Documentation
**Purpose:** Interactive API documentation (Swagger UI).
**Method:** GET
**URL:** `http://localhost:9090/api/docs/`

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

---

### Permission Denied
**Status:** 403 Forbidden

**Response:**
```json
{
  "detail": "You do not have permission to perform this action."
}
```

---

### Not Found
**Status:** 404 Not Found

**Response:**
```json
{
  "detail": "Not found."
}
```

---

### Validation Error
**Status:** 400 Bad Request

**Response:**
```json
{
  "field_name": [
    "This field is required."
  ]
}
```

---

### Server Error
**Status:** 500 Internal Server Error

**Response:**
```json
{
  "detail": "Internal server error."
}
```

---

## Rate Limiting

The LMS API implements rate limiting to prevent abuse:

- **Authenticated requests:** 1000 requests per hour
- **Unauthenticated requests:** 100 requests per hour
- **File uploads:** 50 requests per hour

When rate limit is exceeded:

**Status:** 429 Too Many Requests

**Response:**
```json
{
  "detail": "Request was throttled. Expected available in 3600 seconds."
}
```

---

## File Upload Guidelines

### Supported File Types
- **Images:** JPG, PNG, GIF (max 5MB)
- **Documents:** PDF, DOC, DOCX (max 10MB)
- **Videos:** MP4, WebM (max 100MB)
- **SCORM packages:** ZIP (max 50MB)

### Upload Headers
```
Content-Type: multipart/form-data
```

### Example Upload Request
```bash
curl -X POST \
  http://localhost:9090/api/lms/courses/1/resources/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "title=Course Manual" \
  -F "resource_type=file" \
  -F "file=@manual.pdf"
```

---

## WebSocket Support

The LMS service supports real-time communication via WebSockets for:

- Live chat messaging
- Forum notifications
- Course progress updates
- Assignment submissions

**WebSocket URL:** `ws://localhost:9090/ws/lms/`

**Connection Example:**
```javascript
const socket = new WebSocket('ws://localhost:9090/ws/lms/?token=YOUR_JWT_TOKEN');

// Listen for messages
socket.onmessage = function(event) {
  const data = JSON.parse(event.data);
  console.log('Received:', data);
};

// Send a message
socket.send(JSON.stringify({
  type: 'chat_message',
  message: 'Hello!',
  room: 'course_1'
}));
```

---

## Data Export

### Export Course Data
**Purpose:** Exports complete course data as SCORM package.
**Method:** GET
**URL:** `http://localhost:9090/api/lms/courses/{course_id}/scorm/export/`

**Response:** SCORM ZIP file download

---

## Multi-tenancy

The LMS service supports multi-tenancy with:

- **Tenant isolation:** All data is scoped to tenant
- **Tenant identification:** Via JWT token claims
- **Shared resources:** Categories and system-wide settings
- **Tenant-specific storage:** File uploads isolated by tenant

**Tenant Header (alternative to JWT):**
```
X-Tenant-ID: your-tenant-uuid
```

---

## Integration Examples

### Course Enrollment Flow
```javascript
// 1. Get available courses
fetch('/api/lms/courses/', {
  headers: { 'Authorization': 'Bearer ' + token }
})
.then(response => response.json())
.then(courses => {
  // Display courses to user
});

// 2. Enroll in course
fetch('/api/lms/enrollments/course/1/enroll/', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer ' + token,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({ user_id: userId })
})
.then(response => response.json())
.then(enrollment => {
  console.log('Enrolled successfully:', enrollment);
});
```

### Progress Tracking
```javascript
// Mark lesson as completed
fetch('/api/lms/enrollments/lesson-completion/', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer ' + token,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({ lesson: lessonId })
});

// Get course progress
fetch('/api/lms/enrollments/progress/?course=1&user=' + userId, {
  headers: { 'Authorization': 'Bearer ' + token }
})
.then(response => response.json())
.then(data => {
  console.log('Progress:', data.progress + '%');
});
```

---

## Best Practices

### Course Creation
1. Use clear, descriptive titles
2. Provide comprehensive descriptions
3. Set appropriate difficulty levels
4. Include learning outcomes and prerequisites
5. Organize content into logical modules
6. Add relevant resources and FAQs

### User Management
1. Validate user permissions for actions
2. Use appropriate user roles (student, instructor, admin)
3. Implement proper enrollment workflows
4. Track user progress and engagement

### Content Management
1. Use consistent file naming conventions
2. Compress images and videos for web delivery
3. Implement proper access controls
4. Regular backup of course content
5. Monitor storage usage

### Performance Optimization
1. Use pagination for large datasets
2. Implement caching for frequently accessed data
3. Optimize database queries
4. Compress file responses
5. Use CDN for static assets

---

## Support

For technical support or questions about the LMS API:

- **Documentation:** [API Docs URL]
- **Support Email:** support@lms-platform.com
- **Issue Tracker:** [GitHub Issues URL]

---

*This documentation is automatically generated and updated with each API change. Last updated: 2024-01-25*