# # Document Management API Documentation

# This documentation provides a comprehensive guide to using the Document Management API endpoints. The API is built with Django REST Framework and assumes JWT-based authentication (via `Authorization: Bearer <token>` header). All endpoints are tenant-isolated: the `tenant_id` is extracted from the JWT token and used for filtering/validation.

# ## Base URL
# All endpoints are relative to `/api/documents/` (adjust based on your URL configuration).

# ## Authentication & Permissions
# - **Authentication**: Required for all endpoints. Use JWT tokens containing user details (e.g., `id`, `email`, `first_name`, `last_name`, `job_role`, `tenant_id`).
# - **Permissions**:
#   - `IsAuthenticated`: Basic user access (e.g., acknowledgments).
#   - `IsAdminUser`: Admin-only (e.g., listing, updating, deleting documents).
# - **Error Responses**:
#   - 401 Unauthorized: Invalid/missing token.
#   - 403 Forbidden: Insufficient permissions or tenant mismatch.
#   - 400 Bad Request: Validation errors (e.g., invalid file type, user not in tenant).
#   - 404 Not Found: Resource not found.
#   - 500 Internal Server Error: Server issues (logged for debugging).

# ## Common Request/Response Formats
# - **Content-Type**: `application/json` for JSON payloads; `multipart/form-data` for file uploads.
# - **User Data**: References `CustomUser` model (assumes fields like `id`, `email`, `first_name`, `last_name`, `profile.job_role`).
# - **Permission Levels**: `'view'` (read-only, no download) or `'view_download'` (view + download).
# - **Examples**: Use tools like Postman or curl. Replace placeholders (e.g., `<token>`, `<id>`) with real values.

# ---

# ## 1. List and Create Documents
# **Endpoint**: `GET/POST /documents/`

# ### GET: List All Documents
# - **Description**: Retrieve a paginated list of all documents for the current tenant. Includes nested `permissions` (user access details) and `acknowledgments`.
# - **Permissions**: `IsAdminUser`.
# - **Query Parameters**: None (optional pagination via DRF defaults if configured).
# - **Request Body**: None.
# - **Response**:
#   - 200 OK: Array of document objects.
# - **Example Request** (curl):
#   ```
#   curl -H "Authorization: Bearer <token>" https://yourapi.com/api/documents/
#   ```
# - **Example Response**:
#   ```json
#   [
#     {
#       "id": 1,
#       "title": "Confidential Report",
#       "file_url": "https://storage.example.com/report_v1.pdf",
#       "version": 1,
#       "status": "active",
#       "uploaded_at": "2025-10-08T10:00:00Z",
#       "permissions": [
#         {
#           "user_id": "user123",
#           "email": "user@example.com",
#           "first_name": "John",
#           "last_name": "Doe",
#           "role": "Manager",
#           "permission_level": "view_download",
#           "created_at": "2025-10-08T10:00:00Z"
#         }
#       ],
#       "acknowledgments": [
#         {
#           "id": 1,
#           "user_id": "user123",
#           "email": "user@example.com",
#           "first_name": "John",
#           "last_name": "Doe",
#           "role": "Manager",
#           "acknowledged_at": "2025-10-08T11:00:00Z"
#         }
#       ]
#     }
#   ]
#   ```

# ### POST: Create a Document
# - **Description**: Create a new document. Optionally upload a file and assign bulk permissions to users.
# - **Permissions**: `IsAdminUser`.
# - **Query Parameters**: None.
# - **Request Body** (JSON or multipart/form-data):
#   - Required: `title` (string).
#   - Optional: `file` (file upload, PDF/image only, ≤10MB), `expiring_date` (datetime string, ISO 8601), `status` (string, default "active"), `document_number` (string, unique per tenant).
#   - Optional: `permissions_write` (array of objects for bulk user assignment):
#     ```json
#     [
#       {"user_id": "user123", "permission_level": "view"},
#       {"user_id": "user456", "permission_level": "view_download"}
#     ]
#     ```
# - **Response**:
#   - 201 Created: Full document object, including new `permissions` and version 1.
# - **Example Request** (curl with file and permissions):
#   ```
#   curl -X POST -H "Authorization: Bearer <token>" \
#     -F "title=New Report" \
#     -F "file=@/path/to/report.pdf" \
#     -F 'permissions_write=[{"user_id":"user123","permission_level":"view_download"}]' \
#     https://yourapi.com/api/documents/
#   ```
# - **Notes**: 
#   - File upload creates version 1 automatically.
#   - Permissions are fetched from `CustomUser` and stored with user details (email, name, role).
#   - Validation: Users must exist and belong to the tenant.

# ---

# ## 2. Document Detail Operations
# **Endpoint**: `GET/PATCH/DELETE /documents/<int:id>/`

# - **Path Parameter**: `id` (integer, document ID).

# ### GET: Retrieve a Single Document
# - **Description**: Get full details of a document, including `permissions` and `acknowledgments`.
# - **Permissions**: `IsAdminUser`.
# - **Query Parameters**: None.
# - **Request Body**: None.
# - **Response**:
#   - 200 OK: Single document object (similar to list response).
# - **Example Request** (curl):
#   ```
#   curl -H "Authorization: Bearer <token>" https://yourapi.com/api/documents/1/
#   ```

# ### PATCH: Update a Document
# - **Description**: Partially update document metadata, file (triggers new version), or replace permissions.
# - **Permissions**: `IsAdminUser`.
# - **Query Parameters**: None.
# - **Request Body** (JSON or multipart/form-data, partial allowed):
#   - Optional: `title`, `expiring_date`, `status`, `file` (new file increments version).
#   - Optional: `permissions_write` (array; if provided—even empty—replaces all existing permissions).
# - **Response**:
#   - 200 OK: Updated document object.
# - **Example Request** (curl, update title and permissions):
#   ```
#   curl -X PATCH -H "Authorization: Bearer <token>" \
#     -H "Content-Type: application/json" \
#     -d '{"title": "Updated Report", "permissions_write": [{"user_id": "user789", "permission_level": "view"}]}' \
#     https://yourapi.com/api/documents/1/
#   ```
# - **Notes**:
#   - File update: Archives old version, creates new one, increments `version`.
#   - Permissions: Full replacement (delete old, bulk create new). Omit to keep unchanged.

# ### DELETE: Delete a Document
# - **Description**: Permanently delete the document and all related data (versions, permissions, acknowledgments via CASCADE).
# - **Permissions**: `IsAdminUser`.
# - **Query Parameters**: None.
# - **Request Body**: None.
# - **Response**:
#   - 204 No Content: Success (no body).
# - **Example Request** (curl):
#   ```
#   curl -X DELETE -H "Authorization: Bearer <token>" https://yourapi.com/api/documents/1/
#   ```

# ---

# ## 3. Document Versions
# **Endpoint**: `GET /documents/<int:document_id>/versions/`

# - **Path Parameter**: `document_id` (integer).
# - **Description**: List all versions of a document, with creator details.
# - **Permissions**: `IsAdminUser`.
# - **Query Parameters**: None.
# - **Request Body**: None.
# - **Response**:
#   - 200 OK: Array of version objects.
# - **Example Response**:
#   ```json
#   [
#     {
#       "version": 1,
#       "file_url": "https://storage.example.com/report_v1.pdf",
#       "file_type": "application/pdf",
#       "file_size": 1024000,
#       "created_at": "2025-10-08T10:00:00Z",
#       "created_by": {
#         "email": "admin@example.com",
#         "first_name": "Admin",
#         "last_name": "User",
#         "job_role": "Admin"
#       }
#     }
#   ]
#   ```
# - **Example Request** (curl):
#   ```
#   curl -H "Authorization: Bearer <token>" https://yourapi.com/api/documents/1/versions/
#   ```

# ---

# ## 4. Document Acknowledgment
# **Endpoint**: `POST /documents/<int:document_id>/acknowledge/`

# - **Path Parameter**: `document_id` (integer).
# - **Description**: Mark the current user as having acknowledged the document (prevents duplicates).
# - **Permissions**: `IsAuthenticated`.
# - **Query Parameters**: None.
# - **Request Body**: Empty.
# - **Response**:
#   - 201 Created: Acknowledgment object.
#   - 400 Bad Request: If already acknowledged.
# - **Example Response**:
#   ```json
#   {
#     "id": 1,
#     "document": 1,
#     "user_id": "current_user_id",
#     "email": "user@example.com",
#     "first_name": "John",
#     "last_name": "Doe",
#     "role": "Manager",
#     "acknowledged_at": "2025-10-08T11:00:00Z"
#   }
#   ```
# - **Example Request** (curl):
#   ```
#   curl -X POST -H "Authorization: Bearer <token>" https://yourapi.com/api/documents/1/acknowledge/
#   ```

# ---

# ## 5. List Acknowledgments
# **Endpoint**: `GET /documents/<int:document_id>/acknowledgments/`

# - **Path Parameter**: `document_id` (integer).
# - **Description**: List all acknowledgments for a document, sorted by `acknowledged_at` (descending).
# - **Permissions**: `IsAdminUser`.
# - **Query Parameters**: None.
# - **Request Body**: None.
# - **Response**:
#   - 200 OK: Array of acknowledgment objects (as in POST response).
# - **Example Request** (curl):
#   ```
#   curl -H "Authorization: Bearer <token>" https://yourapi.com/api/documents/1/acknowledgments/
#   ```

# ---

# ## 6. User Document Access
# **Endpoint**: `GET /documents/user-access/`

# - **Description**: Retrieve all documents a specific user has access to, based on `user_id` or `email`. Returns documents with their permissions for that user.
# - **Permissions**: `IsAdminUser`.
# - **Query Parameters** (one required):
#   - `user_id` (string): User ID.
#   - `email` (string): User email (alternative to user_id).
# - **Request Body**: None.
# - **Response**:
#   - 200 OK: Array of objects with `document` (full doc details) and `permission` (user's permission for that doc).
#   - 400 Bad Request: Missing user identifier.
#   - 404 Not Found: No access found.
# - **Example Request** (curl, by user_id):
#   ```
#   curl -H "Authorization: Bearer <token>" "https://yourapi.com/api/documents/user-access/?user_id=user123"
#   ```
# - **Example Response**:
#   ```json
#   [
#     {
#       "document": {
#         "id": 1,
#         "title": "Confidential Report",
#         "file_url": "https://storage.example.com/report_v1.pdf",
#         ...
#       },
#       "permission": {
#         "user_id": "user123",
#         "email": "user@example.com",
#         "first_name": "John",
#         "last_name": "Doe",
#         "role": "Manager",
#         "permission_level": "view_download",
#         "created_at": "2025-10-08T10:00:00Z"
#       }
#     }
#   ]
#   ```
# - **Notes**: Matches by exact user_id or email within the tenant. Useful for auditing user access.

# ---

# ## Additional Notes
# - **File Handling**: Uploads use `upload_file_dynamic` (custom function, assumed implemented). Supported: PDF, PNG, JPG, JPEG (≤10MB).
# - **Bulk Operations**: `permissions_write` supports up to DB limits (e.g., 1000 users). For large sets, paginate client-side.
# - **Enforcement**: Permissions are stored but not yet enforced (e.g., for downloads). Add custom logic (e.g., permission classes) to check `permission_level`.
# - **Migrations**: Run `python manage.py makemigrations` and `migrate` after model changes.
# - **Testing**: Use Django's test client or Postman collections. Log errors via `logger` for debugging.
# - **Extensibility**: For additive permissions (not replacement), extend the serializer with a `mode` field (e.g., "replace", "add").

# For issues or extensions, refer to the source code or contact the maintainer.