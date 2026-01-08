# TECHNICAL COMPLIANCE QUESTIONNAIRE RESPONSE: DATA PRIVACY & SECURITY REQUIREMENTS FOR PROLIANCE / E3OS ERP SYSTEM

**Date:** January 7, 2026  
**Respondent:** Abraham Ekene-onwon Hanson (Backend Software Engineer)  
**Service:** Auth Service (Authentication and User Management Microservice)  

---

## 1. Data Security & Encryption

### Encryption at Rest:
- **Current Implementation:** The auth service uses PostgreSQL as the primary database. Database encryption is not explicitly configured with AES-256 in the current setup. Data is stored in plain text within the database schema.
- **Recommendation:** Implement AES-256 encryption for database volumes and backups. This can be achieved by configuring PostgreSQL with pgcrypto extension or using encrypted file systems (e.g., LUKS on Linux). Backups should be encrypted using tools like pg_dump with encryption options.
- **Compliance Gap:** Not currently compliant. Requires infrastructure changes.

### Encryption in Transit:
- **Current Implementation:** All API endpoints use HTTPS with TLS 1.2+ via Django's SECURE_SSL_REDIRECT and related settings. JWT tokens are signed using RSA keys, but data transmission relies on HTTPS.
- **Recommendation:** Ensure all client-server communication uses TLS 1.3 where possible. The current setup meets the minimum TLS 1.2 requirement.
- **Compliance Status:** Compliant.

### Key Management:
- **Current Implementation:** RSA key pairs are generated and managed internally by the system. Keys are stored in the database and rotated periodically. No customer-managed keys (CMK) are supported.
- **Recommendation:** For enhanced security, implement support for customer-managed keys using AWS KMS, Azure Key Vault, or similar services. Current implementation uses provider-managed keys.
- **Compliance Gap:** Provider-managed only. CMK support would require significant architectural changes.

---

## 2. Access Control (SOC 2 & HIPAA)

### MFA:
- **Current Implementation:** Multi-Factor Authentication is supported via the `two_factor_enabled` field in user models. However, it is not natively enforced for all user roles and API/Service accounts. MFA is optional and user-configurable.
- **Recommendation:** Implement mandatory MFA for all user roles, including administrators and API accounts. Integrate with TOTP (Time-based One-Time Password) or SMS-based MFA.
- **Compliance Gap:** Not mandatory for all roles. Requires policy enforcement.

### Session Management:
- **Current Implementation:** JWT tokens have a lifetime of 120 minutes (ACCESS_TOKEN_LIFETIME). There is no automatic session termination based on inactivity. Sessions are managed via token expiration only.
- **Recommendation:** Implement session timeout after 15 minutes of inactivity. Add session monitoring and automatic logout functionality.
- **Compliance Gap:** No inactivity timeout. Requires frontend and backend changes.

### Role-Based Access (RBAC):
- **Current Implementation:** The system implements role-based access control with roles like 'admin', 'team_manager', 'recruiter', 'client', etc. Permissions are enforced at the API level, but field-level masking (e.g., hiding PII/PHI fields) is not implemented.
- **Recommendation:** Implement field-level access control using Django's permission system or third-party libraries like django-guardian. Add data masking for sensitive fields based on user roles.
- **Compliance Gap:** No field-level masking. Requires model-level permissions.

---

## 3. Data Privacy & Sovereignty (GDPR & NDPA)

### Data Residency:
- **Current Implementation:** Data residency is not explicitly controlled. The system uses multi-tenant architecture with PostgreSQL schemas, but hosting location depends on the deployment environment (e.g., cloud provider regions).
- **Recommendation:** Implement geo-fencing controls to ensure data is hosted in specified regions (e.g., Nigeria, EU, US). Use cloud provider features like AWS Regions or Azure Geography controls.
- **Compliance Gap:** Not guaranteed. Requires deployment configuration.

### Data Subject Rights:
- **Current Implementation:** No automated processes for "Right to Erasure" or "Data Portability". User data deletion requires manual database operations. Audit logs are maintained but not structured for automated export.
- **Recommendation:** Implement automated workflows for data erasure (soft delete with anonymization) and data portability (JSON/CSV export). Add APIs for data subject requests.
- **Compliance Gap:** Manual processes only. Requires new features.

### Log Integrity:
- **Current Implementation:** User activities are logged in the `UserActivity` model, including logins, data views, and exports. Logs include timestamps, IP addresses, and user agents. However, logs are not immutable - they can be modified by administrators.
- **Recommendation:** Implement immutable audit logs using append-only databases (e.g., Amazon S3 with versioning) or blockchain-based logging. Prevent log tampering by administrators.
- **Compliance Gap:** Not immutable. Requires external logging system.

---

## 4. Certifications & Legal

### Audit Reports:
- **Current Implementation:** No SOC 2 Type II reports are available. The system has not undergone external security audits.
- **Recommendation:** Pursue SOC 2 Type II certification through an accredited auditor. Implement security controls aligned with SOC 2 requirements.
- **Compliance Gap:** No certifications. Requires audit process.

### Agreements:
- **Current Implementation:** No Business Associate Agreement (BAA) templates or Data Processing Agreement (DPA) templates are included. Legal agreements are not part of the codebase.
- **Recommendation:** Prepare BAA and DPA templates for HIPAA and GDPR/NDPA compliance. Include clauses for data processing, security measures, and breach notification.
- **Compliance Gap:** Not available. Requires legal documentation.

### Sub-processors:
- **Current Implementation:** The system uses several third-party services including PostgreSQL, Redis, Kafka, and potentially cloud storage (Supabase). A complete list of sub-processors is not documented.
- **Recommendation:** Maintain a comprehensive list of all third-party sub-processors, including their locations, data processing purposes, and compliance certifications.
- **Compliance Gap:** Not documented. Requires vendor assessment.

---

## Implementation Roadmap

### Phase 1: Immediate Actions (1-3 months)
1. Implement AES-256 encryption for database and backups
2. Make MFA mandatory for all administrative roles
3. Add session inactivity timeout (15 minutes)
4. Document sub-processor list

### Phase 2: Short-term (3-6 months)
1. Implement field-level access control and data masking
2. Add automated data erasure and portability features
3. Implement immutable audit logging
4. Pursue SOC 2 Type II certification

### Phase 3: Long-term (6-12 months)
1. Add customer-managed key support
2. Implement geo-fencing for data residency
3. Prepare BAA and DPA templates
4. Achieve full GDPR/NDPA/HIPAA compliance

---

## Conclusion

The auth service provides a solid foundation for user authentication and management but requires significant enhancements to meet full compliance with GDPR, NDPA, HIPAA, and SOC 2 standards. Current gaps are primarily in encryption at rest, mandatory MFA, session management, data subject rights automation, and certifications. We recommend prioritizing security controls and pursuing formal certifications to ensure regulatory compliance.

**Contact:** For detailed implementation plans or technical specifications, please contact the development team.