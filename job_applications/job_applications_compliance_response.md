# Technical Compliance Questionnaire Response: Data Privacy & Security Requirements for Proliance / E3OS ERP System

**Date:** January 7, 2026  
**Respondent:** Abraham Ekene-onwon Hanson (Backend Software Engineer)  
**Contact:** Steven W. Gott, Head, Information Management Services  

---

## 1. Data Security & Encryption

### Encryption at Rest:
- **Database Volumes and Backups:** The job-applications microservice uses PostgreSQL with django-tenants for multi-tenancy. Database encryption is not explicitly configured in the service; it relies on the underlying PostgreSQL instance for encryption. No AES-256 enforcement is implemented at the application level. Sensitive data like resumes and compliance documents are stored in external storage (Supabase) with potential encryption depending on the provider's configuration. We recommend enabling PostgreSQL's pgcrypto or Transparent Data Encryption (TDE) for database-level encryption.

### Encryption in Transit:
- **Data Transmission:** The service communicates via REST APIs, and data in transit relies on the underlying infrastructure (e.g., Docker containers, gateways). No explicit TLS configuration is visible in the code; it assumes HTTPS is handled at the gateway or server level. File uploads to Supabase may use HTTPS depending on the storage configuration. For compliance, ensure all endpoints are served over TLS 1.2+.

### Key Management:
- **Customer-Managed Keys (CMK) vs. Provider-Managed:** The service does not handle encryption keys directly; authentication is delegated to the auth-service. File storage keys (Supabase) are managed by the provider. No CMK implementation is present. For sensitive data, integrate with cloud KMS (e.g., AWS KMS) for key management.

---

## 2. Access Control (SOC 2 & HIPAA)

### MFA (Multi-Factor Authentication):
- **Native Support:** MFA is not implemented in this microservice. Authentication is handled by the auth-service, which supports MFA. This service relies on JWT tokens from auth-service for access control. No additional MFA is enforced at the job-applications level.

### Session Management:
- **Automatic Termination:** Sessions are managed via JWT tokens issued by auth-service. No session timeout logic is implemented in this service beyond token expiry. Inactivity-based termination is not supported. The service does not track user sessions independently.

### Role-Based Access (RBAC):
- **Field-Level Restrictions:** Access is role-based, with roles like 'recruiter' and 'admin' restricting data based on tenant and branch. Permissions are enforced via custom permission classes (e.g., `IsMicroserviceAuthenticated`). Field-level masking is not implemented; access is at the record level. For example, recruiters can only access applications in their branch. No granular field-level controls are present.

---

## 3. Data Privacy & Sovereignty (GDPR & NDPA)

### Data Residency:
- **Hosting Guarantee:** Uses multi-tenant PostgreSQL schemas for data isolation. Data residency depends on the cloud provider (e.g., Supabase for files). No specific region guarantees are implemented; deployment must ensure hosting in compliant regions (e.g., Nigeria or EU). Files are stored in Supabase, which may not guarantee residency without configuration.

### Data Subject Rights:
- **Right to Erasure and Data Portability:** No automated processes for "Right to Erasure" or "Data Portability." Job applications and related data (e.g., schedules, compliance documents) are stored in models. Erasure requires manual deletion or soft-deletion (via `is_deleted` flag). Data export is not implemented; users cannot retrieve their data in structured formats. Compliance workflows handle document uploads but not data portability. We recommend adding API endpoints for data export and automated deletion.

### Log Integrity:
- **Immutable Audit Logs:** Logging is configured with file and console handlers, capturing application events (e.g., screenings, uploads). Logs include timestamps and details but are not immutable; they can be modified. No blockchain or external immutable logging is implemented. For compliance, integrate with immutable logging systems.

---

## 4. Certifications & Legal

### Audit Reports:
- **SOC 2 Type II Report:** No SOC 2 certification has been obtained for this service. Security audits are pending. The service is in development, and no audit reports are available.

### Agreements:
- **Business Associate Agreement (BAA) for HIPAA:** We are willing to sign a BAA for HIPAA compliance, as the service handles health-related compliance documents.  
- **Data Processing Agreement (DPA) for GDPR/NDPA:** We are willing to sign a DPA for GDPR and NDPA compliance.

### Sub-processors:
- **Third-Party Sub-processors:** The service relies on:  
  - PostgreSQL (database)  
  - Supabase (file storage)  
  - Kafka (event streaming)  
  - Auth-service (authentication)  
  - Talent-engine (requisition data)  
  - Email providers (notifications)  
  - Cloud infrastructure providers (e.g., DigitalOcean)  
  A full list with data processing details will be provided upon request.

---

## Additional Notes

- **Compliance Gaps:** The service lacks encryption enforcement, automated data subject rights, and immutable logging. It delegates security to other services (e.g., auth-service for MFA). File storage in Supabase may not meet residency requirements without configuration.
- **Implementation Recommendations:** Follow Appendix 1 guidelines. Enhance access controls, implement data export APIs, and ensure encryption for stored data. Integrate with auth-service for consistent security.
- **Supporting Documents:** README.md, settings.py, and models.py are included for reference.

We appreciate the opportunity to address these requirements and are committed to enhancing compliance. Please contact us for further discussions or demonstrations.

**Best regards,**  
Proliance Ltd. Team