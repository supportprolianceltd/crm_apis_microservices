# 🚀 Socket.IO Messaging System Tester

A comprehensive web-based testing interface for your Socket.IO messaging system.

## 🎯 Features

✅ **Complete Authentication Flow** - JWT token input and automatic injection
✅ **Real-time Event Testing** - Test all socket events with live responses
✅ **JSON Payload Editor** - Edit event payloads with syntax highlighting
✅ **Event Templates** - Pre-built templates for common events
✅ **Real-time Logging** - See all sent/received events and responses
✅ **Connection Management** - Connect/disconnect with status indicators
✅ **Response Handling** - Support for both callback and event-based responses

## 🚀 Quick Start

### Step 1: Start the Testing Server

```bash
cd /home/jayjaychukwu/dev/proliance/crm_apis_microservices/messaging
node server-tester.js
```

This will start a simple HTTP server on `http://localhost:3001`.

### Step 2: Open the Tester Interface

Open your browser and go to: `http://localhost:3001`

You should see the Socket.IO testing interface.

### Step 3: Get Your JWT Token

1. **Authenticate** with your main application to get a JWT token
2. **Copy the token** from your browser's dev tools or API response
3. **Paste it** into the token input field in the tester

### Step 4: Connect to Socket.IO

1. **Enter your JWT token** in the input field
2. **Click "Connect"**
3. **Wait for connection** - you should see "Connected" status

### Step 5: Test Events

1. **Select an event** from the dropdown (or use template buttons)
2. **Edit the JSON payload** as needed
3. **Click "Send Event"**
4. **View responses** in the right panel

## 📋 Available Events

| Event | Description | Example Payload |
|-------|-------------|-----------------|
| `authenticate` | Authenticate user | `{ "data": { "token": "jwt" } }` |
| `online` | Mark user as online | `{ "data": {} }` |
| `get_users` | Get all users in tenant | `{ "data": {} }` |
| `get_online_status` | Get specific user status | `{ "data": { "userId": "id" } }` |
| `get_chats` | Get user's chats | `{ "data": {} }` |
| `send_message_to_user` | Send message to user | `{ "data": { "recipientEmail": "user@domain.com", "content": "Hello!" } }` |
| `send_message` | Send message to chat | `{ "data": { "chatId": "id", "content": "Hello!" } }` |
| `mark_as_read` | Mark messages as read | `{ "data": { "chatId": "id", "messageIds": ["id1", "id2"] } }` |

## 🎨 Interface Features

### **Authentication Section**

- **Token Input**: Enter your JWT token here
- **Connection Controls**: Connect/Disconnect buttons
- **Status Indicator**: Shows connection status

### **Event Templates**

- **Quick Templates**: One-click loading of common event payloads
- **Event Selector**: Dropdown to choose which event to test
- **JSON Editor**: Edit event payloads with proper formatting

### **Real-time Logging**

- **Color-coded Logs**: Different colors for sent/received/error messages
- **Timestamps**: When each event occurred
- **Auto-scroll**: Automatically scrolls to show latest events

## 🔧 Customization

### **Adding New Events**

1. **Add to dropdown** in `tester.html`:

   ```html
   <option value="new_event">new_event</option>
   ```

2. **Add template** in the JavaScript:

   ```javascript
   new_event: {
     // your custom payload here
   }
   ```

3. **Add event listener** in the server if needed

### **Modifying Templates**

Edit the `templates` object in the JavaScript to customize default payloads:

```javascript
const templates = {
    your_event: {
        // your custom payload here
    }
};
```

## 🐛 Troubleshooting

### **Connection Issues**

- ✅ Make sure your main Socket.IO server is running on port 3500
- ✅ Check that your JWT token is valid and not expired
- ✅ Verify the token contains required fields (`user_id`, `tenant_id`, `role`)

### **Authentication Errors**

- ✅ Check server logs for authentication errors
- ✅ Ensure `AUTH_SERVICE_URL` and `JWT_SECRET` are configured
- ✅ Verify the auth service is accessible

### **Event Not Working**

- ✅ Check that the event handler exists in your server
- ✅ Verify the event name matches exactly
- ✅ Check server logs for any error messages

## 📊 Response Examples

### **Success Response**

```json
{
  "status": "success",
  "data": [
    {
      "id": "user-123",
      "username": "john_doe",
      "email": "john@example.com",
      "online": true,
      "role": "staff"
    }
  ]
}
```

### **Error Response**

```json
{
  "status": "error",
  "message": "User not authenticated - please connect with a valid JWT token"
}
```

## 🎯 Testing Workflow

1. **Start your main Socket.IO server** (port 3500)
2. **Start the tester server** (port 3001)
3. **Get a valid JWT token** from your application
4. **Open the tester interface**
5. **Connect with your token**
6. **Test events** using templates or custom payloads
7. **View real-time responses** and debug issues

## 🔗 Integration

This tester can be used alongside your main application to:

- ✅ Test new socket events before deployment
- ✅ Debug authentication issues
- ✅ Verify real-time functionality
- ✅ Test edge cases and error scenarios
- ✅ Validate API responses

The tester is completely independent and can be run in any environment where you have access to your Socket.IO server.
