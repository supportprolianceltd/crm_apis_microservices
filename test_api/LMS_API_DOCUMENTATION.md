# 📚 Learning Management System (LMS) API Documentation

## Overview

The LMS service provides a comprehensive learning management system with multi-tenant architecture, supporting course management, scheduling, payments, forums, groups, messaging, and more. The service uses JWT-based authentication and schema-based multi-tenancy.

## Authentication

All API endpoints require JWT authentication from the auth-service.

**Headers:**
```
Authorization: Bearer YOUR_JWT_TOKEN
Content-Type: application/json
```

---

## Course Management

### Create Course
**Purpose:** Create a new course with modules, lessons, and resources.
**Method:** POST
**URL:** `http://localhost:9090/api/lms/courses/courses/`

**Request Body:**
```json
{
  "title": "Python Programming Fundamentals",
  "code": "PY101",
  "description": "Learn Python from basics to advanced concepts",
  "short_description": "Complete Python course for beginners",
  "category_id": 1,
  "level": "Beginner",
  "status": "Published",
  "price": "99.99",
  "currency": "USD",
  "completion_hours": 40
}
```

**Response:**
```json
{
  "id": 1,
  "title": "Python Programming Fundamentals",
  "slug": "python-programming-fundamentals",
  "code": "PY101",
  "description": "Learn Python from basics to advanced concepts",
  "current_price": "99.99",
  "created_at": "2025-11-15T10:00:00Z"
}
```

### Get Courses
**Purpose:** Retrieve paginated list of courses.
**Method:** GET
**URL:** `http://localhost:9090/api/lms/courses/courses/?page=1&level=Beginner`

**Response:**
```json
{
  "count": 25,
  "next": "http://localhost:9090/api/lms/courses/courses/?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "title": "Python Programming Fundamentals",
      "level": "Beginner",
      "current_price": "99.99",
      "thumbnail": "/media/courses/python-programming/thumbnail.jpg",
      "created_at": "2025-11-15T10:00:00Z"
    }
  ]
}
```

### Enroll in Course
**Purpose:** Enroll a user in a course.
**Method:** POST
**URL:** `http://localhost:9090/api/lms/courses/enrollments/course/1/`

**Response:**
```json
{
  "id": 1,
  "user": "user-123",
  "course": 1,
  "enrolled_at": "2025-11-15T10:30:00Z",
  "is_active": true
}
```

### Rate Course
**Purpose:** Submit a rating and review for a completed course.
**Method:** POST
**URL:** `http://localhost:9090/api/lms/courses/ratings/course/1/`

**Request Body:**
```json
{
  "rating": 5,
  "review": "Excellent course! Very comprehensive and well-structured."
}
```

---

## Scheduling

### Create Schedule
**Purpose:** Create a new scheduled event/meeting.
**Method:** POST
**URL:** `http://localhost:9090/api/lms/schedule/schedules/`

**Request Body:**
```json
{
  "title": "Team Meeting",
  "description": "Weekly team sync",
  "start_time": "2025-11-20T10:00:00Z",
  "end_time": "2025-11-20T11:00:00Z",
  "location": "Conference Room A",
  "is_all_day": false
}
```

**Response:**
```json
{
  "id": 1,
  "title": "Team Meeting",
  "start_time": "2025-11-20T10:00:00Z",
  "end_time": "2025-11-20T11:00:00Z",
  "status": "success"
}
```

### Add Participants
**Purpose:** Add participants to a schedule.
**Method:** POST
**URL:** `http://localhost:9090/api/lms/schedule/participants/`

**Request Body:**
```json
{
  "schedule": 1,
  "user_id": "user-456",
  "is_optional": false
}
```

---

## Forum Management

### Create Forum
**Purpose:** Create a new discussion forum.
**Method:** POST
**URL:** `http://localhost:9090/api/lms/forum/forums/`

**Request Body:**
```json
{
  "title": "General Discussion",
  "description": "General discussion forum for all users",
  "group_ids": ["group-123"],
  "is_active": true
}
```

### Create Post
**Purpose:** Create a new post in a forum.
**Method:** POST
**URL:** `http://localhost:9090/api/lms/forum/posts/`

**Request Body:**
```json
{
  "forum": 1,
  "content": "Welcome to the general discussion forum!"
}
```

---

## Activity Logging

### Get Activity Logs
**Purpose:** Retrieve activity logs for auditing and monitoring.
**Method:** GET
**URL:** `http://localhost:9090/api/lms/activitylog/logs/?activity_type=course_enrolled`

**Response:**
```json
{
  "count": 50,
  "results": [
    {
      "id": 1,
      "activity_type": "course_enrolled",
      "details": "User enrolled in Python Programming course",
      "timestamp": "2025-11-15T10:30:00Z",
      "status": "success"
    }
  ]
}
```

---

## Payment Configuration

### Configure Payment Gateway
**Purpose:** Configure payment gateway settings.
**Method:** POST
**URL:** `http://localhost:9090/api/lms/payments/gateways/`

**Request Body:**
```json
{
  "name": "Stripe",
  "description": "Stripe payment gateway",
  "is_active": true,
  "is_test_mode": true,
  "is_default": true
}
```

---

## Groups Management

### Create Group
**Purpose:** Create a new user group.
**Method:** POST
**URL:** `http://localhost:9090/api/lms/groups/groups/`

**Request Body:**
```json
{
  "name": "Python Developers",
  "description": "Group for Python programming enthusiasts",
  "is_active": true
}
```

### Add Member to Group
**Purpose:** Add a user to a group.
**Method:** POST
**URL:** `http://localhost:9090/api/lms/groups/members/`

**Request Body:**
```json
{
  "group": 1,
  "user_id": "user-123",
  "role": "member"
}
```

---

## Messaging

### Send Message
**Purpose:** Send a message to a user or group.
**Method:** POST
**URL:** `http://localhost:9090/api/lms/messaging/messages/`

**Request Body:**
```json
{
  "recipient_id": "user-456",
  "content": "Hello! How are you?",
  "message_type": "direct"
}
```

---

## AI Chat

### Start Chat Session
**Purpose:** Initiate an AI chat session.
**Method:** POST
**URL:** `http://localhost:9090/api/lms/ai_chat/sessions/`

**Request Body:**
```json
{
  "topic": "Python Programming Help",
  "difficulty_level": "beginner"
}
```

### Send Chat Message
**Purpose:** Send a message to the AI chat.
**Method:** POST
**URL:** `http://localhost:9090/api/lms/ai_chat/messages/`

**Request Body:**
```json
{
  "session": 1,
  "message": "How do I create a function in Python?",
  "sender_type": "user"
}
```

---

## Shopping Cart

### Add to Cart
**Purpose:** Add a course to the shopping cart.
**Method:** POST
**URL:** `http://localhost:9090/api/lms/carts/cart-items/`

**Request Body:**
```json
{
  "course": 1,
  "quantity": 1
}
```

### Checkout
**Purpose:** Process cart checkout and payment.
**Method:** POST
**URL:** `http://localhost:9090/api/lms/carts/checkout/`

**Request Body:**
```json
{
  "payment_method": "stripe",
  "billing_address": {
    "street": "123 Main St",
    "city": "London",
    "country": "UK"
  }
}
```

---

## Audit Logging

### Get Audit Logs
**Purpose:** Retrieve audit logs for compliance and security monitoring.
**Method:** GET
**URL:** `http://localhost:9090/api/lms/auditlog/logs/?action_type=user_login`

**Response:**
```json
{
  "count": 100,
  "results": [
    {
      "id": 1,
      "action_type": "user_login",
      "details": "User logged in from web browser",
      "timestamp": "2025-11-15T09:00:00Z",
      "ip_address": "192.168.1.1"
    }
  ]
}
```

---

## Error Responses

### Authentication Error
```json
{
  "detail": "Authentication credentials were not provided.",
  "status": 401
}
```

### Validation Error
```json
{
  "field_name": ["This field is required."],
  "status": 400
}
```

### Not Found Error
```json
{
  "detail": "Not found.",
  "status": 404
}
```

### Permission Denied
```json
{
  "detail": "You do not have permission to perform this action.",
  "status": 403
}
```

---

## WebSocket Endpoints

The LMS service supports real-time communication via WebSockets for features like live chat, notifications, and collaborative learning.

### Forum Live Chat
**URL:** `ws://localhost:9090/ws/lms/forum/{forum_id}/`

### Course Notifications
**URL:** `ws://localhost:9090/ws/lms/course/{course_id}/notifications/`

### Group Chat
**URL:** `ws://localhost:9090/ws/lms/group/{group_id}/chat/`

---

## File Upload Endpoints

### Course Thumbnail Upload
**Method:** POST
**URL:** `http://localhost:9090/api/lms/courses/courses/{id}/upload-thumbnail/`
**Content-Type:** multipart/form-data

### Lesson File Upload
**Method:** POST
**URL:** `http://localhost:9090/api/lms/courses/lessons/{id}/upload-file/`
**Content-Type:** multipart/form-data

---

## Health Check

### Service Health
**Method:** GET
**URL:** `http://localhost:9090/health/lms/`

**Response:**
```json
{
  "status": "healthy",
  "service": "lms",
  "version": "1.0.0",
  "database": "connected",
  "timestamp": "2025-11-15T10:00:00Z"
}
```

This documentation covers the core functionality of the LMS service. Each app provides RESTful APIs with proper authentication, validation, and error handling. The service supports multi-tenancy, real-time features, and comprehensive logging for auditing and monitoring.