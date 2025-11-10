# 📮 Postman Request Examples - Messaging Service

## Authentication

All endpoints require JWT authentication via Bearer token in the Authorization header.

### Authentication Flow
**Purpose:** The messaging service uses JWT tokens issued by the auth service. Include the token in the Authorization header for all requests.

**Header:**
```
Authorization: Bearer YOUR_JWT_TOKEN
```

---

## User Management

### Get All Users
**Purpose:** Retrieves paginated users from the auth service for messaging purposes (finding users to chat with).
**Method:** GET
**URL:** `http://localhost:9090/api/messaging/users?page=1&page_size=50&search=jane`

**Query Parameters:**
- `page` (optional): Page number (default: 1)
- `page_size` (optional): Users per page, max 100 (default: 50)
- `search` (optional): Search term to filter by name or email

**Example URLs:**
- `http://localhost:9090/api/messaging/users` - Get first page with 50 users
- `http://localhost:9090/api/messaging/users?page=2&page_size=20` - Get page 2 with 20 users
- `http://localhost:9090/api/messaging/users?search=jane` - Search for users with "jane" in name/email

**Response:**
```json
{
  "count": 12,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 50,
      "username": "jdoe0947",
      "email": "ekeneonwon@appbrew.com",
      "first_name": "Jane",
      "last_name": "Doe",
      "role": "carer",
      "job_role": "Senior Carer",
      "tenant": "appbrew",
      "status": "active",
      "online": false,
      "createdAt": "2025-11-10T12:14:28.059Z",
      "updatedAt": "2025-11-10T12:51:25.105Z"
    }
  ]
}
```

**Pagination Response Fields:**
- `count`: Total number of users
- `next`: URL for next page (null if no more pages)
- `previous`: URL for previous page (null if first page)
- `results`: Array of user objects for current page

---

## Chat Management

### Get User's Chats
**Purpose:** Retrieves all chats for the authenticated user with participant information and unread counts.
**Method:** GET
**URL:** `http://localhost:9090/api/messaging/chats`

**Response:**
```json
{
  "status": "success",
  "data": [
    {
      "id": "chat_123",
      "name": "Jane Doe",
      "type": "DIRECT",
      "unreadCount": 2,
      "participants": [
        {
          "id": 50,
          "username": "jdoe0947",
          "email": "ekeneonwon@appbrew.com",
          "online": true,
          "lastSeen": null,
          "firstName": "Jane",
          "lastName": "Doe"
        }
      ],
      "lastMessage": {
        "id": "msg_456",
        "content": "Hello, how are you?",
        "createdAt": "2025-11-10T12:00:00.000Z"
      },
      "updatedAt": "2025-11-10T12:00:00.000Z"
    }
  ]
}
```

### Create Direct Chat
**Purpose:** Creates or retrieves an existing direct chat with another user.
**Method:** POST
**URL:** `http://localhost:9090/api/messaging/chats/direct`

**Request Body:**
```json
{
  "participantId": 50
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "id": "chat_123",
    "type": "DIRECT",
    "createdAt": "2025-11-10T12:00:00.000Z",
    "users": [
      {
        "userId": 2,
        "role": "MEMBER"
      },
      {
        "userId": 50,
        "role": "MEMBER"
      }
    ]
  }
}
```

### Mark Messages as Read
**Purpose:** Marks specific messages as read in a chat, updating unread counts.
**Method:** PATCH
**URL:** `http://localhost:9090/api/messaging/chats/{chatId}/messages/{messageId}/read`

**Response:**
```json
{
  "status": "success",
  "message": "Messages marked as read"
}
```

---

## Message Management

### Get Chat Messages
**Purpose:** Retrieves paginated messages for a specific chat with full message details.
**Method:** GET
**URL:** `http://localhost:9090/api/messaging/messages/{chatId}?limit=50&offset=0`

**Query Parameters:**
- `limit` (optional): Number of messages to return (default: 50, max: 100)
- `offset` (optional): Number of messages to skip (default: 0)
- `before` (optional): ISO date string to get messages before this timestamp

**Response:**
```json
{
  "status": "success",
  "data": {
    "messages": [
      {
        "id": "msg_456",
        "content": "Hello, how are you?",
        "createdAt": "2025-11-10T12:00:00.000Z",
        "author": {
          "id": 2,
          "username": "aachmed2759",
          "email": "support@appbrew.com",
          "firstName": "Abib",
          "lastName": "Achmed"
        }
      }
    ],
    "hasMore": false,
    "total": 1,
    "limit": 50,
    "offset": 0
  }
}
```

### Send Message to User
**Purpose:** Sends a message to another user, creating a chat if one doesn't exist.
**Method:** POST
**URL:** `http://localhost:9090/api/messaging/messages/send`

**Request Body:**
```json
{
  "recipientId": 50,
  "content": "Hello, how are you doing today?"
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "message": {
      "id": "msg_456",
      "content": "Hello, how are you doing today?",
      "chatId": "chat_123",
      "authorId": 2,
      "status": "DELIVERED",
      "createdAt": "2025-11-10T12:00:00.000Z"
    },
    "chat": {
      "id": "chat_123",
      "type": "DIRECT"
    }
  }
}
```

### Send Message by Email
**Purpose:** Sends a message to a user by their email address.
**Method:** POST
**URL:** `http://localhost:9090/api/messaging/messages/send-by-email`

**Request Body:**
```json
{
  "recipientEmail": "ekeneonwon@appbrew.com",
  "content": "Hello, this is a message sent by email!"
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "message": {
      "id": "msg_457",
      "content": "Hello, this is a message sent by email!",
      "chatId": "chat_123",
      "authorId": 2,
      "status": "DELIVERED",
      "createdAt": "2025-11-10T12:05:00.000Z"
    },
    "chat": {
      "id": "chat_123",
      "type": "DIRECT"
    }
  }
}
```

---

## WebSocket Events

### Real-time Messaging
The messaging service uses Socket.IO for real-time communication. Connect to `ws://localhost:3500` with JWT token authentication.

#### Authentication
```javascript
const socket = io('http://localhost:3500', {
  auth: {
    token: 'YOUR_JWT_TOKEN'
  }
});
```

#### Available Events

##### Client → Server Events

**get_chats**
- **Purpose:** Request user's chat list
- **Payload:** `{}` (empty object)
- **Response Event:** `get_chats_response` or `get_chats_error`

**send_message_to_user**
- **Purpose:** Send message to another user
- **Payload:** `{ recipientId: 50, content: "Hello!" }`
- **Response Event:** `send_message_to_user_response` or `send_message_to_user_error`

**get_or_create_chat**
- **Purpose:** Create or get existing direct chat
- **Payload:** `{ participantId: 50 }`
- **Response Event:** `get_or_create_chat_response` or `get_or_create_chat_error`

**get_messages**
- **Purpose:** Get chat messages with pagination
- **Payload:** `{ chatId: "chat_123", limit: 50, offset: 0 }`
- **Response Event:** `get_messages_response` or `get_messages_error`

**send_message**
- **Purpose:** Send message to existing chat
- **Payload:** `{ chatId: "chat_123", content: "Hello!" }`
- **Response Event:** `send_message_response` or `send_message_error`

**mark_as_read**
- **Purpose:** Mark messages as read
- **Payload:** `{ chatId: "chat_123", messageIds: ["msg_456"] }`
- **Response Event:** `mark_as_read_response` or `mark_as_read_error`

**online**
- **Purpose:** Mark user as online
- **Payload:** `{}` (empty object)
- **Response Event:** `online_response` or `online_error`

**get_online_status**
- **Purpose:** Check if user is online
- **Payload:** `{ userId: 50 }`
- **Response Event:** `get_online_status_response` or `get_online_status_error`

**get_users**
- **Purpose:** Get all users in tenant
- **Payload:** `{}` (empty object)
- **Response Event:** `get_users_response` or `get_users_error`

##### Server → Client Events

**new_message**
- **Purpose:** New message received
- **Payload:** `{ chatId: "chat_123", message: {...}, unreadCount: 1 }`

**messages_read**
- **Purpose:** Messages marked as read by another user
- **Payload:** `{ chatId: "chat_123", messageIds: ["msg_456"], readBy: 50, readAt: "2025-11-10T12:00:00.000Z" }`

**user_status_change**
- **Purpose:** User online/offline status changed
- **Payload:** `{ userId: 50, isOnline: true, lastSeen: null, timestamp: "2025-11-10T12:00:00.000Z" }`

---

## Error Responses

### Authentication Error
**Status:** 401 Unauthorized
```json
{
  "status": "error",
  "message": "Authentication failed"
}
```

### Validation Error
**Status:** 400 Bad Request
```json
{
  "status": "error",
  "message": "recipientId and content are required"
}
```

### Access Denied
**Status:** 403 Forbidden
```json
{
  "status": "error",
  "message": "Chat not found or access denied"
}
```

### Server Error
**Status:** 500 Internal Server Error
```json
{
  "status": "error",
  "message": "Failed to fetch chats",
  "error": "Detailed error message (development only)"
}
```

---

## Service Architecture

### Database Schema
- **Users**: Messaging service users (synced from auth service)
- **Tenants**: Multi-tenant isolation
- **Chats**: Direct/group conversations
- **Messages**: Individual messages with status tracking
- **UsersOnChats**: Chat membership and unread counts

### Key Features
- **Real-time messaging** via WebSocket
- **Multi-tenant support** with data isolation
- **Message persistence** with delivery status
- **Unread message tracking**
- **User presence** (online/offline status)
- **Message pagination** for performance
- **JWT authentication** with auth service integration

### Service Dependencies
- **Auth Service**: User authentication and user data
- **PostgreSQL**: Message and chat data storage
- **Redis**: Session storage and caching
- **API Gateway**: Request routing and load balancing