Based on your messaging microservice code, here are the key endpoints to start testing and using the service:

## 📋 HTTP REST Endpoints

### 1. **Authentication & Base Routes**
- `GET /` - Redirects to API documentation
- `GET /api-docs` - Swagger UI documentation
- `GET /docs.json` - OpenAPI spec in JSON format

### 2. **User Management**
- `GET /api/v1/users` - Get all users
  ```bash
  curl -X GET http://localhost:3500/api/v1/users \
    -H "Authorization: Bearer <your-jwt-token>"
  ```

### 3. **Chat Management**
- `GET /api/v1/chats` - Get all chats
- `GET /api/chats` - Get user's chats (authenticated user)
- `POST /api/chats/direct` - Create/get direct chat
  ```bash
  curl -X POST http://localhost:3500/api/chats/direct \
    -H "Authorization: Bearer <token>" \
    -H "Content-Type: application/json" \
    -d '{"participantId": "123"}'
  ```

### 4. **Message Management**
- `GET /api/v1/messages/{chatId}` - Get messages for a chat
- `PATCH /api/chats/{chatId}/messages/{messageId}/read` - Mark messages as read

## 🔌 WebSocket Events (Real-time)

### **Connection & Authentication**
```javascript
// Connect to WebSocket
const socket = io('http://localhost:3500', {
  auth: {
    token: 'your-jwt-token'
  }
});

// Authenticate (if using separate auth event)
socket.emit('authenticate', { token: 'your-jwt-token' }, (response) => {
  console.log('Auth result:', response);
});
```

### **Presence Events**
```javascript
// Go online and join rooms
socket.emit('online', (response) => {
  console.log('Online status:', response);
});

// Get user's online status
socket.emit('get_online_status', { userId: '123' }, (response) => {
  console.log('User status:', response);
});

// Get all users in tenant
socket.emit('get_users', (response) => {
  console.log('Users list:', response);
});

// Listen for status changes
socket.on('user_status_change', (data) => {
  console.log('User status changed:', data);
});
```

### **Chat Events**
```javascript
// Get user's chats
socket.emit('get_chats', (response) => {
  console.log('User chats:', response);
});

// Create or get direct chat
socket.emit('get_or_create_chat', 
  { participantId: '123' }, 
  (response) => {
    console.log('Chat created/found:', response);
  }
);
```

### **Message Events**
```javascript
// Send message to user (creates chat if needed)
socket.emit('send_message_to_user', {
  recipientId: '123', // or recipientEmail: 'user@example.com'
  content: 'Hello there!'
}, (response) => {
  console.log('Message sent:', response);
});

// Send message to existing chat
socket.emit('send_message', {
  chatId: 'chat-uuid',
  content: 'Hello in existing chat!'
}, (response) => {
  console.log('Message sent to chat:', response);
});

// Get message history
socket.emit('get_messages', {
  chatId: 'chat-uuid',
  limit: 50,
  offset: 0
}, (response) => {
  console.log('Messages:', response);
});

// Mark messages as read
socket.emit('mark_as_read', {
  chatId: 'chat-uuid',
  messageIds: ['msg-id-1', 'msg-id-2'] // or single messageId
}, (response) => {
  console.log('Messages marked read:', response);
});

// Listen for new messages
socket.on('new_message', (data) => {
  console.log('New message received:', data);
});

// Listen for read receipts
socket.on('messages_read', (data) => {
  console.log('Messages were read:', data);
});
```

## 🚀 Quick Start Testing Guide

### 1. **Prerequisites**
```bash
# Ensure required environment variables
JWT_SECRET=your-jwt-secret
AUTH_SERVICE_URL=http://auth-service:8001
DB_HOST=localhost
DB_USER=postgres
DB_PASSWORD=password
DB_NAME=messaging_db
DB_PORT=5432
```

### 2. **Start the Services**
```bash
docker-compose up -d
```

### 3. **Test HTTP Endpoints**
```bash
# Get all users
curl -X GET http://localhost:3500/api/v1/users

# Get all chats
curl -X GET http://localhost:3500/api/v1/chats

# Get messages for a chat
curl -X GET http://localhost:3500/api/v1/messages/chat-uuid-here
```

### 4. **Test WebSocket Connection**
```javascript
// Using Socket.IO client
import { io } from 'socket.io-client';

const socket = io('http://localhost:3500', {
  auth: {
    token: 'your-valid-jwt-token'
  }
});

socket.on('connect', () => {
  console.log('Connected to messaging service');
  
  // Go online
  socket.emit('online');
  
  // Get user's chats
  socket.emit('get_chats', (response) => {
    console.log('Chats:', response);
  });
});

socket.on('new_message', (data) => {
  console.log('New message:', data);
});
```

### 5. **Complete Test Flow**
```javascript
// 1. Connect and authenticate
const socket = io('http://localhost:3500', { auth: { token } });

// 2. Go online
socket.emit('online');

// 3. Get available users
socket.emit('get_users', (usersResponse) => {
  const otherUser = usersResponse.data[0];
  
  // 4. Start chat with user
  socket.emit('get_or_create_chat', 
    { participantId: otherUser.id }, 
    (chatResponse) => {
      const chat = chatResponse.data;
      
      // 5. Send message
      socket.emit('send_message_to_user', {
        recipientId: otherUser.id,
        content: 'Hello! This is a test message.'
      }, (messageResponse) => {
        console.log('Message sent successfully!');
      });
    }
  );
});
```

## 📊 Testing Tools

### **Use the Built-in Tester**
The service includes a tester on port 3501:
```bash
# Access the tester interface
http://localhost:3501
```

### **WebSocket Testing Tools**
- Use **Postman** (Native support for WebSockets)
- Use **websocat** CLI tool:
  ```bash
  websocat ws://localhost:3500
  ```
- Use browser developer tools with Socket.IO client

## 🔐 Authentication Notes

- All endpoints require JWT authentication
- WebSocket connections require token in connection params or `authenticate` event
- The token should contain user ID and tenant context
- Token validation happens via the auth service at `AUTH_SERVICE_URL`

Start with the WebSocket presence events (`online`, `get_users`) to see available users, then use the chat and message events to test the full messaging flow!