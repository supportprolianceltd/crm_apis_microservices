# 📅 Event Management API Documentation

## 🏦 Authentication & Multi-tenancy

### Login - User
**Purpose:** Authenticates a user and returns a JWT token for subsequent API calls.
**Method:** POST
**URL:** `http://localhost:9090/api/token/`

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
  "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": 123,
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "User",
    "role": "staff",
    "tenant": {
      "id": 1,
      "name": "Proliance Care",
      "schema_name": "proliance"
    }
  }
}
```

---

## 📅 Event Management

### Create Event
**Purpose:** Creates a new event with visibility controls and participant management.
**Method:** POST
**URL:** `http://localhost:9090/api/events/events/`

**Request Body:**
```json
{
  "title": "Team Meeting",
  "description": "Weekly team sync meeting",
  "start_datetime": "2024-12-01T10:00:00Z",
  "end_datetime": "2024-12-01T11:00:00Z",
  "location": "Conference Room A",
  "meeting_link": "https://zoom.us/j/123456789",
  "visibility": "specific_users",
  "participants": [2, 3, 4]
}
```

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Team Meeting",
  "description": "Weekly team sync meeting",
  "start_datetime": "2024-12-01T10:00:00Z",
  "end_datetime": "2024-12-01T11:00:00Z",
  "location": "Conference Room A",
  "creator": 1,
  "visibility": "specific_users",
  "participants": [2, 3, 4],
  "participants_details": [
    {
      "id": 2,
      "email": "jane@example.com",
      "first_name": "Jane",
      "last_name": "Smith",
      "role": "staff"
    },
    {
      "id": 3,
      "email": "bob@example.com",
      "first_name": "Bob",
      "last_name": "Johnson",
      "role": "carer"
    },
    {
      "id": 4,
      "email": "alice@example.com",
      "first_name": "Alice",
      "last_name": "Brown",
      "role": "hr"
    }
  ],
  "creator_details": {
    "id": 1,
    "email": "john@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "role": "admin"
  },
  "created_at": "2024-11-20T12:00:00Z",
  "updated_at": "2024-11-20T12:00:00Z",
  "last_updated_by_id": "1"
}
```

---

### Get Events
**Purpose:** Retrieves events visible to the authenticated user based on visibility settings.
**Method:** GET
**URL:** `http://localhost:9090/api/events/events/`

**Query Parameters:**
- `start_date`: Filter events from this date (YYYY-MM-DD)
- `end_date`: Filter events until this date (YYYY-MM-DD)
- `visibility`: Filter by visibility type (private, public, specific_users)
- `creator`: Filter by creator ID

**Response:**
```json
{
  "count": 3,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "Team Meeting",
      "description": "Weekly team sync meeting",
      "start_datetime": "2024-12-01T10:00:00Z",
      "end_datetime": "2024-12-01T11:00:00Z",
      "location": "Conference Room A",
      "creator": 1,
      "visibility": "specific_users",
      "participants": [2, 3, 4],
      "participants_details": [
        {
          "id": 2,
          "email": "jane@example.com",
          "first_name": "Jane",
          "last_name": "Smith",
          "role": "staff"
        }
      ],
      "creator_details": {
        "id": 1,
        "email": "john@example.com",
        "first_name": "John",
        "last_name": "Doe",
        "role": "admin"
      },
      "created_at": "2024-11-20T12:00:00Z",
      "updated_at": "2024-11-20T12:00:00Z",
      "last_updated_by_id": "1"
    },
    {
      "id": "550e8400-e29b-41d4-a716-446655440001",
      "title": "Company All-Hands",
      "description": "Monthly company meeting",
      "start_datetime": "2024-12-15T14:00:00Z",
      "end_datetime": "2024-12-15T16:00:00Z",
      "location": "Main Auditorium",
      "creator": 1,
      "visibility": "public",
      "participants": [],
      "participants_details": [],
      "creator_details": {
        "id": 1,
        "email": "john@example.com",
        "first_name": "John",
        "last_name": "Doe",
        "role": "admin"
      },
      "created_at": "2024-11-18T09:00:00Z",
      "updated_at": "2024-11-18T09:00:00Z",
      "last_updated_by_id": "1"
    }
  ]
}
```

---

### Get Event Details
**Purpose:** Retrieves detailed information for a specific event.
**Method:** GET
**URL:** `http://localhost:9090/api/events/events/{id}/`

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Team Meeting",
  "description": "Weekly team sync meeting",
  "start_datetime": "2024-12-01T10:00:00Z",
  "end_datetime": "2024-12-01T11:00:00Z",
  "location": "Conference Room A",
  "meeting_link": "https://zoom.us/j/123456789",
  "creator": 1,
  "visibility": "specific_users",
  "participants": [2, 3, 4],
  "participants_details": [
    {
      "id": 2,
      "email": "jane@example.com",
      "first_name": "Jane",
      "last_name": "Smith",
      "role": "staff"
    },
    {
      "id": 3,
      "email": "bob@example.com",
      "first_name": "Bob",
      "last_name": "Johnson",
      "role": "carer"
    },
    {
      "id": 4,
      "email": "alice@example.com",
      "first_name": "Alice",
      "last_name": "Brown",
      "role": "hr"
    }
  ],
  "creator_details": {
    "id": 1,
    "email": "john@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "role": "admin"
  },
  "created_at": "2024-11-20T12:00:00Z",
  "updated_at": "2024-11-20T12:00:00Z",
  "last_updated_by_id": "1"
}
```

---

### Update Event
**Purpose:** Updates an existing event (only creator or admin can update).
**Method:** PUT/PATCH
**URL:** `http://localhost:9090/api/events/events/{id}/`

**Request Body (PATCH):**
```json
{
  "title": "Updated Team Meeting",
  "description": "Updated weekly team sync meeting",
  "participants": [2, 3, 4, 5]
}
```

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Updated Team Meeting",
  "description": "Updated weekly team sync meeting",
  "start_datetime": "2024-12-01T10:00:00Z",
  "end_datetime": "2024-12-01T11:00:00Z",
  "location": "Conference Room A",
  "creator": 1,
  "visibility": "specific_users",
  "participants": [2, 3, 4, 5],
  "participants_details": [
    {
      "id": 2,
      "email": "jane@example.com",
      "first_name": "Jane",
      "last_name": "Smith",
      "role": "staff"
    },
    {
      "id": 3,
      "email": "bob@example.com",
      "first_name": "Bob",
      "last_name": "Johnson",
      "role": "carer"
    },
    {
      "id": 4,
      "email": "alice@example.com",
      "first_name": "Alice",
      "last_name": "Brown",
      "role": "hr"
    },
    {
      "id": 5,
      "email": "charlie@example.com",
      "first_name": "Charlie",
      "last_name": "Wilson",
      "role": "staff"
    }
  ],
  "creator_details": {
    "id": 1,
    "email": "john@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "role": "admin"
  },
  "created_at": "2024-11-20T12:00:00Z",
  "updated_at": "2024-11-20T12:30:00Z",
  "last_updated_by_id": "1"
}
```

---

### Delete Event
**Purpose:** Deletes an event (only creator or admin can delete).
**Method:** DELETE
**URL:** `http://localhost:9090/api/events/events/{id}/`

**Response:**
```json
{
  "message": "Event deleted successfully"
}
```

---

### Get My Events
**Purpose:** Retrieves events created by the authenticated user.
**Method:** GET
**URL:** `http://localhost:9090/api/events/events/my_events/`

**Query Parameters:**
- `start_date`: Filter events from this date (YYYY-MM-DD)
- `end_date`: Filter events until this date (YYYY-MM-DD)

**Response:**
```json
{
  "count": 2,
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "Team Meeting",
      "description": "Weekly team sync meeting",
      "start_datetime": "2024-12-01T10:00:00Z",
      "end_datetime": "2024-12-01T11:00:00Z",
      "location": "Conference Room A",
      "visibility": "specific_users",
      "participant_count": 3,
      "created_at": "2024-11-20T12:00:00Z"
    },
    {
      "id": "550e8400-e29b-41d4-a716-446655440001",
      "title": "Company All-Hands",
      "description": "Monthly company meeting",
      "start_datetime": "2024-12-15T14:00:00Z",
      "end_datetime": "2024-12-15T16:00:00Z",
      "location": "Main Auditorium",
      "visibility": "public",
      "participant_count": 0,
      "created_at": "2024-11-18T09:00:00Z"
    }
  ]
}
```

---

### Get Events I'm Invited To
**Purpose:** Retrieves events where the authenticated user is a participant.
**Method:** GET
**URL:** `http://localhost:9090/api/events/events/my_invitations/`

**Query Parameters:**
- `start_date`: Filter events from this date (YYYY-MM-DD)
- `end_date`: Filter events until this date (YYYY-MM-DD)

**Response:**
```json
{
  "count": 1,
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440002",
      "title": "HR Training Session",
      "description": "Mandatory HR training for all staff",
      "start_datetime": "2024-12-05T09:00:00Z",
      "end_datetime": "2024-12-05T12:00:00Z",
      "location": "Training Room B",
      "creator_details": {
        "id": 4,
        "email": "alice@example.com",
        "first_name": "Alice",
        "last_name": "Brown",
        "role": "hr"
      },
      "visibility": "specific_users",
      "created_at": "2024-11-19T10:00:00Z"
    }
  ]
}
```

---

### Get Public Events
**Purpose:** Retrieves all public events in the tenant.
**Method:** GET
**URL:** `http://localhost:9090/api/events/events/public_events/`

**Query Parameters:**
- `start_date`: Filter events from this date (YYYY-MM-DD)
- `end_date`: Filter events until this date (YYYY-MM-DD)

**Response:**
```json
{
  "count": 2,
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440001",
      "title": "Company All-Hands",
      "description": "Monthly company meeting",
      "start_datetime": "2024-12-15T14:00:00Z",
      "end_datetime": "2024-12-15T16:00:00Z",
      "location": "Main Auditorium",
      "creator_details": {
        "id": 1,
        "email": "john@example.com",
        "first_name": "John",
        "last_name": "Doe",
        "role": "admin"
      },
      "created_at": "2024-11-18T09:00:00Z"
    },
    {
      "id": "550e8400-e29b-41d4-a716-446655440003",
      "title": "Holiday Party",
      "description": "Annual company holiday party",
      "start_datetime": "2024-12-20T18:00:00Z",
      "end_datetime": "2024-12-20T22:00:00Z",
      "location": "Grand Ballroom",
      "creator_details": {
        "id": 1,
        "email": "john@example.com",
        "first_name": "John",
        "last_name": "Doe",
        "role": "admin"
      },
      "created_at": "2024-11-15T14:00:00Z"
    }
  ]
}
```

---

## 📊 Event Analytics & Reports

### Event Dashboard
**Purpose:** Get comprehensive event dashboard with metrics and analytics (Admin Only).
**Method:** GET
**URL:** `http://localhost:9090/api/events/dashboard/`

**Response:**
```json
{
  "metrics": {
    "total_events": 25,
    "upcoming_events": 8,
    "past_events": 17,
    "public_events": 5,
    "private_events": 12,
    "specific_user_events": 8,
    "total_participants": 156,
    "average_participants_per_event": 6.24
  },
  "upcoming_events": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "Team Meeting",
      "start_datetime": "2024-12-01T10:00:00Z",
      "participant_count": 3,
      "creator_name": "John Doe"
    },
    {
      "id": "550e8400-e29b-41d4-a716-446655440001",
      "title": "Company All-Hands",
      "start_datetime": "2024-12-15T14:00:00Z",
      "participant_count": 0,
      "creator_name": "John Doe"
    }
  ],
  "event_types_breakdown": {
    "public": 5,
    "private": 12,
    "specific_users": 8
  },
  "monthly_event_creation": [
    {
      "month": "2024-11",
      "count": 15
    },
    {
      "month": "2024-12",
      "count": 10
    }
  ]
}
```

---

### Event Calendar View
**Purpose:** Get events formatted for calendar display.
**Method:** GET
**URL:** `http://localhost:9090/api/events/calendar/`

**Query Parameters:**
- `start_date`: Start date for calendar view (YYYY-MM-DD)
- `end_date`: End date for calendar view (YYYY-MM-DD)

**Response:**
```json
{
  "events": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "Team Meeting",
      "start": "2024-12-01T10:00:00Z",
      "end": "2024-12-01T11:00:00Z",
      "location": "Conference Room A",
      "visibility": "specific_users",
      "creator": "John Doe",
      "participants_count": 3,
      "is_creator": true,
      "is_participant": true
    },
    {
      "id": "550e8400-e29b-41d4-a716-446655440001",
      "title": "Company All-Hands",
      "start": "2024-12-15T14:00:00Z",
      "end": "2024-12-15T16:00:00Z",
      "location": "Main Auditorium",
      "visibility": "public",
      "creator": "John Doe",
      "participants_count": 0,
      "is_creator": true,
      "is_participant": false
    }
  ]
}
```

---

## 🔧 Event Business Logic

### Visibility Rules
- **Private:** Only creator can see the event
- **Public:** All users in the tenant can see the event
- **Specific Users:** Only creator and selected participants can see the event

### Access Control
- **Create:** Any authenticated user can create events
- **Read:** Based on visibility settings and user permissions
- **Update:** Only event creator or tenant admin can update
- **Delete:** Only event creator or tenant admin can delete

### Participant Management
- **Adding Participants:** Only creator can add/remove participants
- **Participant Limits:** No limit on number of participants
- **Self-Removal:** Participants cannot remove themselves (only creator can)

### Date/Time Validation
- **End after Start:** End datetime must be after start datetime
- **Timezone:** All datetimes stored in UTC
- **Duration:** Minimum 15 minutes, maximum 24 hours

---

## 📋 API Endpoints Summary

### Event Management
- `GET /api/events/events/` - List events (filtered by visibility) ✅ **Frontend Implemented**
- `POST /api/events/events/` - Create event ✅ **Frontend Implemented**
- `GET /api/events/events/{id}/` - Get event details ✅ **Frontend Implemented**
- `PUT /api/events/events/{id}/` - Update event ✅ **Frontend Implemented**
- `PATCH /api/events/events/{id}/` - Partial update event ✅ **Frontend Implemented**
- `DELETE /api/events/events/{id}/` - Delete event ✅ **Frontend Implemented**
- `GET /api/events/events/my_events/` - Get events created by user ✅ **Frontend Implemented**
- `GET /api/events/events/my_invitations/` - Get events user is invited to ✅ **Frontend Implemented**
- `GET /api/events/events/public_events/` - Get all public events ✅ **Frontend Implemented**

### Analytics & Reports
- `GET /api/events/dashboard/` - Event dashboard metrics ✅ **Frontend Implemented**
- `GET /api/events/calendar/` - Calendar view of events ✅ **Frontend Implemented**

---

## 💻 Frontend Implementation Status

### ✅ **Fully Implemented Features**

#### **Core Event Management**
- ✅ **Event CRUD Operations**: Create, Read, Update, Delete events
- ✅ **Visibility Controls**: Private, Public, Specific Users
- ✅ **Participant Management**: Add/remove participants with search
- ✅ **Calendar Integration**: Full calendar view with event display
- ✅ **Dashboard Analytics**: Real-time metrics and upcoming events
- ✅ **Responsive Design**: Mobile-friendly interface

#### **User Interface Components**
- ✅ **Event Creation Modal**: Comprehensive form with validation
- ✅ **Event List View**: Filterable and searchable event list
- ✅ **Calendar Component**: Interactive calendar with event details
- ✅ **Participant Selector**: User search and selection interface
- ✅ **Event Details Modal**: Full event information display
- ✅ **Dashboard Widgets**: Metrics cards and upcoming events

#### **API Integration**
- ✅ **EventApiService**: Complete service layer for event operations
- ✅ **Error Handling**: Comprehensive error handling and user feedback
- ✅ **Loading States**: Proper loading indicators for all async operations
- ✅ **Real-time Updates**: Automatic UI updates after operations

### 📊 **Implementation Coverage**

| Component | Status | Coverage |
|-----------|--------|----------|
| **Event CRUD** | ✅ Complete | 100% |
| **Visibility System** | ✅ Complete | 100% |
| **Participant Management** | ✅ Complete | 100% |
| **Calendar View** | ✅ Complete | 100% |
| **Dashboard** | ✅ Complete | 100% |
| **UI Components** | ✅ Complete | 100% |
| **Mobile Responsiveness** | ✅ Complete | 100% |
| **API Integration** | ✅ Complete | 100% |
| **Error Handling** | ✅ Complete | 100% |

### 🔧 **Technical Implementation**

#### **Frontend Architecture**
- **React Hooks**: Modern functional components with custom hooks
- **Service Layer**: Centralized API services (`EventApiService`)
- **State Management**: Local state with proper data flow
- **Calendar Library**: FullCalendar integration for event display
- **Responsive Design**: CSS Grid/Flexbox with mobile-first approach
- **Form Validation**: Real-time validation with error feedback

#### **Key Features Implemented**
- **Multi-visibility Events**: Support for private, public, and specific user events
- **Participant Search**: Real-time user search with role filtering
- **Calendar Navigation**: Month/week/day views with event details
- **Bulk Operations**: Efficient handling of multiple participants
- **Real-time Updates**: UI updates after create/update/delete operations

#### **Mobile Optimization**
- **Responsive Calendar**: Touch-friendly calendar navigation
- **Mobile Modals**: Optimized modal positioning for mobile screens
- **Touch Controls**: Proper button sizes and gesture support
- **Adaptive Layout**: Card-based layouts for smaller screens

### 🚀 **Production Ready Features**

- ✅ **Complete API Integration**: All documented endpoints implemented
- ✅ **Error Handling**: Comprehensive error states and user feedback
- ✅ **Loading States**: Proper loading indicators throughout the app
- ✅ **Responsive Design**: Works seamlessly on all device sizes
- ✅ **Accessibility**: ARIA labels and keyboard navigation support
- ✅ **Performance**: Optimized rendering and efficient API calls
- ✅ **Security**: Proper authentication and tenant isolation

---

## 🗂️ Data Models

### Event
- `id`: UUID primary key
- `title`: Event title (max 255 chars)
- `description`: Event description (text field)
- `start_datetime`: Event start date and time (UTC)
- `end_datetime`: Event end date and time (UTC)
- `location`: Event location (max 255 chars, optional)
- `meeting_link`: URL field for virtual meetings (Zoom, Teams, Google Meet, etc.) - optional, nullable, blankable
- `creator`: ForeignKey to CustomUser (event creator)
- `tenant`: ForeignKey to Tenant (multi-tenancy support)
- `visibility`: Choice field (private, public, specific_users)
- `participants`: ManyToMany to CustomUser (event participants)
- `created_at`: Auto timestamp
- `updated_at`: Auto timestamp
- `last_updated_by_id`: Last user to update (optional)

---

## 🔧 Configuration & Settings

### Environment Variables
- `DEFAULT_FROM_EMAIL`: Email address for notifications
- `GATEWAY_URL`: Base URL for pagination links

### Tenant Configuration
- **Data Isolation**: Complete tenant separation at database level
- **User Filtering**: Participants limited to tenant users
- **Event Scoping**: All events scoped to tenant schema

### Database Indexes
- `tenant + creator + start_datetime`: Optimized for creator's events
- `tenant + start_datetime + end_datetime`: Optimized for date range queries
- `tenant + visibility`: Optimized for visibility filtering

---

## 📈 Performance Considerations

### Database Optimization
- **Tenant Filtering**: All queries include tenant_id for data isolation
- **Select Related**: Creator and participant data pre-loaded
- **Index Usage**: Optimized indexes for common query patterns

### Caching Strategy
- **Event Lists**: Cached per user with tenant scope
- **Public Events**: Cached globally within tenant
- **Dashboard Metrics**: Cached with short TTL for real-time feel

### Scalability Features
- **Pagination**: Large event lists paginated
- **Background Processing**: Potential for notification sending
- **Efficient Queries**: Optimized database queries with proper indexing

---

## 🧪 Testing & Quality Assurance

### Test Coverage
- **Unit Tests:** Individual model and serializer methods
- **Integration Tests:** API endpoint testing with tenant context
- **Visibility Logic:** Event visibility rules validation
- **Multi-tenancy:** Tenant isolation verification

### Data Validation
- **Date/Time Logic:** Start before end, reasonable duration
- **Participant Validation:** Users exist and belong to tenant
- **Visibility Rules:** Proper access control enforcement

---

## 🚀 Future Enhancements

### Planned Features
- **Recurring Events:** Support for recurring event patterns
- **Event Reminders:** Email/SMS notifications for upcoming events
- **Event Categories:** Tagging and categorization system
- **File Attachments:** Document sharing for events
- **Event Templates:** Pre-defined event templates
- **External Calendar Sync:** Google Calendar/Outlook integration
- **Event Attendance:** RSVP and attendance tracking
- **Event Analytics:** Detailed participation and engagement metrics

### Technical Improvements
- **Real-time Updates:** WebSocket notifications for event changes
- **Advanced Search:** Full-text search across event fields
- **Bulk Operations:** Mass event creation and updates
- **API Versioning:** v2 API with enhanced features
- **Rate Limiting:** API throttling for security
- **Audit Logging:** Comprehensive activity tracking

---

*This documentation is continuously updated. Last updated: November 2025*

*Frontend Implementation: 100% Complete - All documented APIs and features implemented*

*🔗 API Integration: 100% Complete - All endpoints fully integrated with responsive UI*

## 📊 Event Dashboard & Analytics

### Event Dashboard Metrics
**Purpose:** Get comprehensive event dashboard with metrics and analytics.
**Method:** GET
**URL:** `http://localhost:9090/api/events/dashboard/`

**Response (Admin View):**
```json
{
  "metrics": {
    "total_events": 25,
    "upcoming_events": 8,
    "past_events": 17,
    "public_events": 5,
    "private_events": 12,
    "specific_user_events": 8,
    "total_participants": 156,
    "average_participants_per_event": 6.24,
    "events_this_month": 15,
    "events_last_month": 10
  },
  "upcoming_events": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "Team Meeting",
      "start_datetime": "2024-12-01T10:00:00Z",
      "participant_count": 3,
      "creator_name": "John Doe",
      "visibility": "specific_users"
    },
    {
      "id": "550e8400-e29b-41d4-a716-446655440001",
      "title": "Company All-Hands",
      "start_datetime": "2024-12-15T14:00:00Z",
      "participant_count": 0,
      "creator_name": "John Doe",
      "visibility": "public"
    }
  ],
  "event_types_breakdown": {
    "public": 5,
    "private": 12,
    "specific_users": 8
  },
  "monthly_event_creation": [
    {
      "month": "2024-11",
      "count": 15
    },
    {
      "month": "2024-12",
      "count": 10
    }
  ],
  "top_creators": [
    {
      "user_id": 1,
      "name": "John Doe",
      "event_count": 12
    },
    {
      "user_id": 4,
      "name": "Alice Brown",
      "event_count": 8
    }
  ]
}
```

**Response (User View):**
```json
{
  "metrics": {
    "my_events": 5,
    "invited_events": 8,
    "upcoming_events": 6,
    "past_events": 7
  },
  "my_upcoming_events": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "Team Meeting",
      "start_datetime": "2024-12-01T10:00:00Z",
      "participant_count": 3,
      "visibility": "specific_users"
    }
  ],
  "invited_to_upcoming": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440002",
      "title": "HR Training Session",
      "start_datetime": "2024-12-05T09:00:00Z",
      "creator_name": "Alice Brown",
      "visibility": "specific_users"
    }
  ]
}
```

---

### Calendar Data Feed
**Purpose:** Get events formatted for calendar integration.
**Method:** GET
**URL:** `http://localhost:9090/api/events/calendar/`

**Query Parameters:**
- `start_date`: Start date (YYYY-MM-DD)
- `end_date`: End date (YYYY-MM-DD)
- `user_id`: Filter for specific user (admin only)

**Response:**
```json
{
  "events": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "Team Meeting",
      "start": "2024-12-01T10:00:00Z",
      "end": "2024-12-01T11:00:00Z",
      "location": "Conference Room A",
      "description": "Weekly team sync meeting",
      "visibility": "specific_users",
      "creator": {
        "id": 1,
        "name": "John Doe",
        "email": "john@example.com"
      },
      "participants": [
        {
          "id": 2,
          "name": "Jane Smith",
          "email": "jane@example.com"
        },
        {
          "id": 3,
          "name": "Bob Johnson",
          "email": "bob@example.com"
        }
      ],
      "is_creator": true,
      "is_participant": true,
      "can_edit": true,
      "backgroundColor": "#3788d8",
      "borderColor": "#3788d8",
      "textColor": "#ffffff"
    },
    {
      "id": "550e8400-e29b-41d4-a716-446655440001",
      "title": "Company All-Hands",
      "start": "2024-12-15T14:00:00Z",
      "end": "2024-12-15T16:00:00Z",
      "location": "Main Auditorium",
      "description": "Monthly company meeting",
      "visibility": "public",
      "creator": {
        "id": 1,
        "name": "John Doe",
        "email": "john@example.com"
      },
      "participants": [],
      "is_creator": true,
      "is_participant": false,
      "can_edit": true,
      "backgroundColor": "#28a745",
      "borderColor": "#28a745",
      "textColor": "#ffffff"
    }
  ],
  "meta": {
    "total_events": 25,
    "filtered_events": 8,
    "date_range": {
      "start": "2024-12-01",
      "end": "2024-12-31"
    }
  }
}
```

---

## 🔧 Event Business Rules & Features

### Visibility Logic
- **Private Events:** Only creator can view and edit
- **Public Events:** All tenant users can view, only creator can edit
- **Specific Users Events:** Creator and selected participants can view, only creator can edit

### Access Control Matrix

| Action | Private Event | Public Event | Specific Users Event |
|--------|---------------|--------------|---------------------|
| **View** | Creator only | All users | Creator + Participants |
| **Edit** | Creator only | Creator only | Creator only |
| **Delete** | Creator only | Creator only | Creator only |
| **Add Participants** | N/A | N/A | Creator only |
| **Remove Participants** | N/A | N/A | Creator only |

### Date/Time Validation Rules
- **Start < End:** End datetime must be after start datetime
- **Minimum Duration:** 15 minutes minimum
- **Maximum Duration:** 24 hours maximum (configurable)
- **Timezone:** All times stored in UTC
- **Past Events:** Cannot create events in the past (optional validation)

### Participant Management Rules
- **Creator Auto-Include:** Event creator is automatically a participant for specific_users events
- **Self-Addition:** Users cannot add themselves as participants
- **Duplicate Prevention:** Same user cannot be added multiple times
- **Tenant Boundary:** Only users from same tenant can be participants

### Multi-tenancy Features
- **Complete Isolation:** Events are fully scoped to tenant schema
- **User Filtering:** Participant selection limited to tenant users
- **Data Security:** No cross-tenant event access
- **Performance:** Tenant-specific database queries and indexes

### Security & Access Control
- **JWT Authentication:** Required for all endpoints
- **Role-Based Access:** Admin users have broader access within tenant
- **Creator Permissions:** Event creators have full control over their events
- **Participant Privacy:** Participants cannot modify event details

---

## 📧 Notification System

The event system includes automated notifications for key events:

### Event Created
- **Trigger:** When a new event is created
- **Recipients:** Event participants (for specific_users events)
- **Content:** Event details, date/time, location

### Event Updated
- **Trigger:** When event details are modified
- **Recipients:** Event participants
- **Content:** Updated event information, changes made

### Event Cancelled
- **Trigger:** When an event is deleted
- **Recipients:** Event participants
- **Content:** Cancellation notice with reason

### Upcoming Event Reminder
- **Trigger:** 24 hours before event start time
- **Recipients:** Event participants
- **Content:** Event reminder with all details

---

## ⚙️ Scheduled Operations

### Event Reminder Notifications
**Schedule:** Daily at 09:00 UTC
**Task:** `send_event_reminders`
**Function:** Send reminders for events starting in 24 hours

### Cleanup Past Events (Optional)
**Schedule:** Monthly on 1st at 02:00 UTC
**Task:** `cleanup_old_events`
**Function:** Archive or delete events older than configured period

---

## 🔄 Business Rules & Features

### Event Creation Rules
- **Title Required:** Event must have a title (1-255 characters)
- **Date/Time Required:** Start and end datetime mandatory
- **Location Optional:** Location field can be blank
- **Description Optional:** Description can be blank
- **Visibility Default:** Defaults to 'private' if not specified

### Event Update Rules
- **Creator Only:** Only event creator can update event details
- **Admin Override:** Tenant admins can update any event
- **Participant Changes:** Only creator can modify participant list
- **Date Validation:** Same validation rules as creation

### Event Deletion Rules
- **Creator Only:** Only event creator can delete their events
- **Admin Override:** Tenant admins can delete any event
- **Soft Delete:** Events marked as deleted (not hard deleted)

### Search & Filtering
- **Title Search:** Case-insensitive search in event titles
- **Date Range:** Filter events by date ranges
- **Creator Filter:** Filter by event creator
- **Visibility Filter:** Filter by visibility type
- **Participant Filter:** Find events where user is participant

---

## 📋 API Endpoints Summary

### Event CRUD Operations
- `GET /api/events/events/` - List events ✅ **Frontend Implemented**
- `POST /api/events/events/` - Create event ✅ **Frontend Implemented**
- `GET /api/events/events/{id}/` - Get event details ✅ **Frontend Implemented**
- `PUT /api/events/events/{id}/` - Update event ✅ **Frontend Implemented**
- `PATCH /api/events/events/{id}/` - Partial update event ✅ **Frontend Implemented**
- `DELETE /api/events/events/{id}/` - Delete event ✅ **Frontend Implemented**

### Specialized Event Views
- `GET /api/events/events/my_events/` - User's created events ✅ **Frontend Implemented**
- `GET /api/events/events/my_invitations/` - Events user is invited to ✅ **Frontend Implemented**
- `GET /api/events/events/public_events/` - All public events ✅ **Frontend Implemented**

### Analytics & Calendar
- `GET /api/events/dashboard/` - Event dashboard metrics ✅ **Frontend Implemented**
- `GET /api/events/calendar/` - Calendar-formatted events ✅ **Frontend Implemented**

---

## 💻 Frontend Implementation Details

### Core Components
- **EventCalendar**: FullCalendar integration with event display
- **EventModal**: Create/edit event modal with form validation
- **EventList**: Filterable event list with search
- **ParticipantSelector**: User search and selection component
- **DashboardWidgets**: Metrics and upcoming events display

### Key Features
- **Real-time Calendar**: Interactive calendar with drag-drop support
- **Multi-visibility Support**: Visual indicators for different visibility types
- **Participant Management**: Add/remove participants with search
- **Responsive Design**: Mobile-optimized interface
- **Bulk Operations**: Efficient handling of multiple participants

### Technical Stack
- **React**: Modern functional components
- **FullCalendar**: Calendar library for event display
- **Axios**: HTTP client for API communication
- **React Hook Form**: Form validation and management
- **Material-UI/Ant Design**: UI component library

---

## 🗂️ Database Schema

### Event Table
```sql
CREATE TABLE events_event (
    id UUID PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    start_datetime TIMESTAMP WITH TIME ZONE NOT NULL,
    end_datetime TIMESTAMP WITH TIME ZONE NOT NULL,
    location VARCHAR(255),
    meeting_link VARCHAR(500),  -- Optional URL for virtual meetings
    creator_id INTEGER NOT NULL REFERENCES users_customuser(id),
    tenant_id INTEGER NOT NULL REFERENCES core_tenant(id),
    visibility VARCHAR(20) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_updated_by_id VARCHAR(100)
);
```

### Event Participants Table (Many-to-Many)
```sql
CREATE TABLE events_event_participants (
    id SERIAL PRIMARY KEY,
    event_id UUID NOT NULL REFERENCES events_event(id),
    customuser_id INTEGER NOT NULL REFERENCES users_customuser(id),
    UNIQUE(event_id, customuser_id)
);
```

### Indexes
```sql
CREATE INDEX idx_events_tenant_creator_start ON events_event(tenant_id, creator_id, start_datetime);
CREATE INDEX idx_events_tenant_start_end ON events_event(tenant_id, start_datetime, end_datetime);
CREATE INDEX idx_events_tenant_visibility ON events_event(tenant_id, visibility);
```

---

## 🔧 Configuration Settings

### Event Settings (in settings.py)
```python
# Event Configuration
EVENT_MIN_DURATION_MINUTES = 15
EVENT_MAX_DURATION_HOURS = 24
EVENT_ALLOW_PAST_CREATION = False
EVENT_DEFAULT_VISIBILITY = 'private'
EVENT_REMINDER_HOURS = 24
```

### Tenant-Specific Settings
- **Event Limits:** Maximum events per user per day/month
- **Participant Limits:** Maximum participants per event
- **Visibility Options:** Configurable visibility types per tenant
- **Notification Settings:** Email/SMS preferences

---

## 📈 Performance Optimization

### Database Query Optimization
- **Tenant Filtering:** All queries include tenant_id
- **Index Usage:** Optimized for common query patterns
- **Select Related:** Minimize database hits with prefetch_related

### Caching Strategy
- **Public Events:** Cached per tenant with short TTL
- **User Events:** Cached per user with invalidation on changes
- **Dashboard Data:** Cached with real-time invalidation

### API Optimization
- **Pagination:** Large result sets paginated
- **Filtering:** Server-side filtering for performance
- **Serialization:** Efficient data serialization

---

## 🧪 Testing Strategy

### Unit Tests
- **Model Methods:** Event visibility logic, date validation
- **Serializer Validation:** Form validation and data transformation
- **View Permissions:** Access control testing

### Integration Tests
- **API Endpoints:** Full CRUD operations with authentication
- **Multi-tenancy:** Tenant isolation verification
- **Visibility Rules:** Event access control testing

### End-to-End Tests
- **User Workflows:** Complete event creation and management flows
- **Calendar Integration:** Calendar display and interaction
- **Mobile Responsiveness:** Cross-device functionality

---

## 🚀 Roadmap & Future Features

### Phase 1 (Completed)
- ✅ Basic event CRUD operations
- ✅ Multi-visibility support (private/public/specific users)
- ✅ Participant management
- ✅ Calendar integration
- ✅ Dashboard analytics
- ✅ Mobile responsive design

### Phase 2 (Planned)
- 🔄 **Recurring Events:** Weekly/monthly recurring patterns
- 🔄 **Event Templates:** Pre-defined event types
- 🔄 **File Attachments:** Document sharing for events
- 🔄 **Event Categories:** Tagging and categorization
- 🔄 **Advanced Search:** Full-text search capabilities

### Phase 3 (Future)
- 📅 **External Calendar Sync:** Google Calendar/Outlook integration
- 📊 **Event Analytics:** Detailed participation metrics
- 🔔 **Push Notifications:** Real-time event notifications
- 📱 **Mobile App:** Native mobile application
- 🤖 **AI Features:** Smart event suggestions and scheduling

---

*Event Management System - Complete Implementation*

*Multi-tenancy: ✅ Fully Implemented*

*API Integration: ✅ 100% Complete*

*Frontend Implementation: ✅ 100% Complete*

*Mobile Responsive: ✅ 100% Complete*

*Last Updated: November 2025*