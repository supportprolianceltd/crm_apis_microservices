Document Management API Documentation
Overview
The Document Management API provides endpoints for creating, updating, retrieving, and acknowledging documents within a multi-tenant system. It includes version control to retain and label previous document versions when updates are made, ensuring old files remain accessible.
Key Components
Models

Document: Stores the latest document metadata, including title, file_url, file_path, file_type, file_size, version, tenant_id, uploaded_by_id, updated_by_id, uploaded_at, updated_at, expiring_date, status, and document_number.
DocumentVersion: Stores version-specific data for each document, including version, file_url, file_path, file_type, file_size, created_at, and created_by_id. Linked to Document via a foreign key.
DocumentAcknowledgment: Tracks user acknowledgments of documents, including document, user, tenant, and acknowledged_at.

Serializers

DocumentSerializer: Handles serialization for Document, including file validation (PDF/image, <10MB), tenant validation, and user metadata fetching from an external auth service. Manages creation and updates with version control.
DocumentVersionSerializer: Serializes DocumentVersion records, including created_by user details.
DocumentAcknowledgmentSerializer: Serializes acknowledgment data, ensuring tenant and user validation.

Views

DocumentListCreateView: Handles GET (list documents) and POST (create new document) requests.
DocumentDetailView: Handles GET (retrieve document), PATCH (update document), and DELETE (delete document) requests.
DocumentVersionListView: Handles GET requests to retrieve all versions of a document.
DocumentAcknowledgeView: Handles POST requests to acknowledge a document.

Endpoints
1. List/Create Documents

URL: /documents/
Methods:
GET: Lists all documents for the authenticated tenant.
POST: Creates a new document with an uploaded file.


Permissions: Requires IsAuthenticated and IsAdminUser.
Behavior:
Creates a new Document with version=1.
Uploads file to storage with _v1 appended (e.g., policy_v1.pdf).
Creates a corresponding DocumentVersion record.


Response:
GET: 200 OK with list of documents.
POST: 201 Created with document data, or 400 Bad Request for validation errors.



2. Document Details

URL: /documents/<id>/
Methods:
GET: Retrieves a specific document.
PATCH: Updates a document, optionally replacing the file.
DELETE: Deletes a document.


Permissions: Requires IsAuthenticated and IsAdminUser.
Behavior (PATCH):
Saves current file details to a new DocumentVersion record.
Increments version and uploads new file with _v<version> (e.g., policy_v2.pdf).
Updates Document with new file details and creates a new DocumentVersion.


Response:
GET: 200 OK with document data.
PATCH: 200 OK with updated document data.
DELETE: 204 No Content.



3. List Document Versions

URL: /documents/<document_id>/versions/
Method: GET
Permissions: Requires IsAuthenticated and IsAdminUser.
Behavior: Retrieves all DocumentVersion records for a document, including file URLs and version numbers.
Response: 200 OK with list of versions (e.g., [{version: 1, file_url: ".../policy_v1.pdf"}, {version: 2, file_url: ".../policy_v2.pdf"}]).

4. Acknowledge Document

URL: /documents/<document_id>/acknowledge/
Method: POST
Permissions: Requires IsAuthenticated.
Behavior: Creates a DocumentAcknowledgment record if the user hasn’t acknowledged the document.
Response: 201 Created with acknowledgment data, or 400 Bad Request if already acknowledged.

Version Control

Creation: New documents start with version=1. A DocumentVersion record is created with the file details.
Update: When updating with a new file:
The current file is saved as a DocumentVersion with the current version.
The version is incremented.
The new file is uploaded with _v<version> in the name.
A new DocumentVersion record is created for the updated file.


Retrieval: Use /documents/<document_id>/versions/ to access all versions, each labeled with its version number and file URL.

Notes

File Storage: Files are stored with versioned names (e.g., policy_v1.pdf, policy_v2.pdf) to ensure old versions remain accessible. No automatic deletion of old files occurs.
Acknowledgments: Updates to documents may require re-acknowledgment by users (not implemented in current code).
Database: Ensure migrations are applied for the DocumentVersion model. Index DocumentVersion.document and DocumentVersion.version for performance.
Storage Costs: Retaining all versions increases storage usage. Consider cleanup policies for old versions if needed.






## Comprehensive List of Microservice Implementations

Here is the detailed report of implemented features in our E3OS microservices (API Gateway, Auth Service, Talent Engine/Requisition Service, Job Applications Service, and Notification Service) SAAS Architecture that are ready for deployment:

### 1. API Gateway Service
- **Routing Infrastructure**: Django-based API gateway providing unified interface for client requests to backend services
- **Dockerized Deployment**: Containerized with Docker Compose for easy scaling and deployment
- **Basic Configuration**: Environment-based settings for development/production modes
- **Documentation Setup**: Swagger UI integration for API documentation

### 2. Authentication Service (Auth Service)
- **Multi-Tenant Architecture**: Complete schema-based tenant isolation with PostgreSQL
- **JWT Authentication**: Secure token-based authentication with RSA key pairs for signing/validation
- **User Management System**:
  - Custom user model with roles (root-admin, co-admin, staff etc.), only root-admin can manage permissions, but he can designate a co-admin to manage permissions too.
  - Comprehensive user profiles with personal info, employment details, qualifications
  - Document management for onboarding.
  - Client profiles with automatic assignment to cluster for the rostering Microservice.
- **Security Features**:
  - Two-factor authentication support
  - Account locking/deactivation for suspicious activity
  - RSA key management for JWT
- **Event Management**:
  - Calendar integration with event scheduling.
- **Document Management**:
  - File upload/storage with versioning
  - Permission-based access control
  - Document acknowledgment tracking
- **Kafka Integration**: Event-driven architecture for real-time processing

### 3. Talent Engine Service (Requisition Service)
- **Job Requisition Management**:
  - Job creation and publishing with detailed descriptions
  - Approval workflows for job postings
  - Multi-organization support with data isolation
- **Leave Management System**:
  - Leave request processing with approval workflows
- **Equipment Management**:
  - Equipment request, and approval
- **Service Management**:
  - Service request, and approval

### 4. Job Applications Service
- **Application Processing**:
  - Job application submission with document uploads
  - Resume and cover letter handling
  - Application status tracking through multiple stages
- **Intelligent Screening**:
  - AI-powered resume evaluation with scoring
  - Automated candidate ranking
  - Status history tracking
- **Interview Scheduling**:
  - Virtual and physical meeting scheduling
  - Automated notifications
  - Meeting link management
- **Compliance and Documentation**:
  - Document verification tracking
  - Compliance status monitoring
  - Audit trails for all application activities
- **Kafka Integration**: Asynchronous processing for screening and notifications
- **RESTful API**: Complete endpoints for application management

### 5. Notification Service
- **Multi-Tenant Notification System**: Isolated notification handling per tenant with customizable branding
- **Multi-Channel Support**: Email notifications with extensible architecture for SMS and push notifications
- **Template Management**: Dynamic Handlebars-based templates for personalized notifications
- **Queue-Based Processing**: Redis-backed BullMQ job queues for reliable asynchronous processing
- **Event-Driven API**: RESTful endpoints for receiving and processing notification events
- **Tenant Configuration**:
  - Custom branding per tenant (logos, colors, contact info)
  - Multiple email provider support (SMTP configurations)
  - Tenant-specific settings and preferences
- **Comprehensive Audit Trail**: Full logging of notification attempts, delivery status, and failures
- **Email Processing**: SMTP-based email delivery with provider response tracking
- **Template System**: Localized templates with dynamic content replacement
- **Health Monitoring**: Service health checks and metrics endpoints

### Cross-Service Integrations
- **Inter-Service Communication**: All services communicate via REST APIs and Kafka events
- **Shared Authentication**: JWT tokens validated across services
- **Tenant Isolation**: Consistent multi-tenant data separation
- **Document Storage**: Unified document management across services
- **Notification System**: Centralized notification handling

### Technical Infrastructure
- **Containerization**: All services dockerized with Docker Compose
- **Database**: PostgreSQL with schema-based multi-tenancy (Django services) and Prisma ORM (NestJS)
- **Message Queue**: Kafka for event-driven processing, Redis/BullMQ for job queues
- **Caching**: Redis integration for performance optimization
- **API Documentation**: Swagger/OpenAPI for all services
- **Logging**: Comprehensive logging with rotation
- **Background Processing**: Celery for asynchronous tasks, BullMQ for notification queues

### Deployment Readiness
All services above are ready for deployment and they include:
- Production-ready Docker configurations
- Environment-based settings
- Database migrations
- Health checks and monitoring setup
- Error handling and logging
- Security configurations (CORS, authentication, etc.)

