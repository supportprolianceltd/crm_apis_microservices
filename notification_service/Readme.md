# Multi-Tenant Notification System

[![Python](https://img.shields.io/badge/Python-3.12-brightgreen.svg)](https://www.python.org/downloads/)
[![Django](https://img.shields.io/badge/Django-5.0-blue.svg)](https://www.djangoproject.com/)
[![Celery](https://img.shields.io/badge/Celery-5.3-green.svg)](https://docs.celeryq.dev/en/stable/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://docs.docker.com/compose/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A **tenant-aware, asynchronous multi-channel notification system** built for multi-tenant CRM platforms. Supports email, SMS, push, and in-app notifications with per-tenant credentials, full tracking, retries, and analytics.

**Version:** 1.0.0  
**Status:** Production-Ready (as of October 14, 2025)  
**Author:** Ekene-onwon Abraham
**Project:** Multi-Tenant CRM — Notification Service  

---

## 📖 Table of Contents

- [Overview](#overview)
- [System Goals](#system-goals)
- [Core Components](#core-components)
- [System Architecture](#system-architecture)
- [Application Structure](#application-structure)
- [Installation & Setup](#installation--setup)
- [API Documentation](#api-documentation)
- [Logging & Monitoring](#logging--monitoring)
- [Retry & Failure Recovery](#retry--failure-recovery)
- [Analytics & Insights](#analytics--insights)
- [Infrastructure Overview](#infrastructure-overview)
- [Security](#security)
- [Extensibility Roadmap](#extensibility-roadmap)
- [Development Guidelines](#development-guidelines)
- [Example Workflow](#example-workflow)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

This project implements a **Tenant-Aware, Asynchronous Multi-Channel Notification System** designed for a **multi-tenant CRM platform**.

Each tenant (e.g., company, recruiter, or admin) can send notifications—such as **emails**, **SMS**, **push**, and **in-app messages**—using **their own communication credentials**.  

All notifications are processed **asynchronously** to ensure non-blocking performance, and all delivery results are **logged and tracked** for full observability.

Key Features:
- **Multi-Tenancy**: Isolated configs, templates, and logs per tenant.
- **Channels**: Email (SMTP), SMS (Twilio), Push (Firebase), In-App (WebSockets via Django Channels).
- **Async Processing**: Celery + Redis for queues and tasks.
- **Tracking**: Full lifecycle logging with retries and error categorization.
- **Analytics**: Per-tenant dashboards for success rates and patterns.
- **Integrations**: Kafka for event-driven triggers (e.g., from HR service).

---

## System Goals

- ✅ Support **multiple tenants**, each with isolated messaging configurations.
- ✅ Deliver messages via multiple channels (Email, SMS, Push, In-App).
- ✅ Handle notifications **asynchronously** (Celery + Redis).
- ✅ Ensure each message is **tracked, logged, and retriable**.
- ✅ Allow **per-tenant customization** of templates, sender identity, and triggers.
- ✅ Provide **auditing, monitoring, and analytics** for notifications.
- ✅ Build with **extensibility** in mind for future integrations.

---

## Core Components

### 1. Notification Orchestrator (Core Engine)
The orchestrator acts as the **central gateway** for all notifications.

Responsibilities:
- Accept notification requests from CRM modules.
- Validate tenant identity and permissions.
- Dispatch requests to the correct channel handler.
- Log request lifecycle and manage retries.

### 2. Channel Handlers
Each message channel is implemented as a **pluggable handler** following a common interface.

| Channel       | Purpose                  | Configured With                  |
|---------------|--------------------------|----------------------------------|
| **EmailHandler** | Sends tenant-based emails | Tenant SMTP credentials         |
| **SMSHandler**   | Sends text messages      | Tenant Twilio API keys           |
| **PushHandler**  | Sends mobile or web push | Firebase service account         |
| **InAppHandler** | Sends in-app alerts      | Internal Redis/WebSocket groups  |

All handlers return a **standardized response** (success/failure, error message, timestamp) for consistent processing and logging.

### 3. Message Queue (Celery + Redis)
To ensure scalability and responsiveness, all outgoing notifications are processed asynchronously.

**Workflow:**
1. Notification request saved → status: `PENDING`.
2. Task added to Celery queue.
3. Celery worker picks up the job and sends message.
4. Status updated → `SUCCESS` or `FAILED`.
5. Logs and metadata recorded in the database.

### 4. Tenant Communication Credentials
Each tenant stores its own credentials for every communication channel (encrypted at rest).

| Channel | Credential Examples |
|---------|---------------------|
| Email   | SMTP host, port, username, password, from name, from email |
| SMS     | Account SID, Auth Token, From Phone |
| Push    | Firebase service account JSON (project_id, private_key, etc.) |
| In-App  | None (uses internal service) |

### 5. Notification Templates
Tenants can create reusable templates with placeholders such as `{{ candidate_name }}` or `{{ interview_date }}`.

Template types:
- Email (HTML or text)
- SMS (short text)
- Push (title + body)
- In-App (short alerts)

Templates support:
- Version control  
- Dynamic context injection  
- Tenant-level customization  

### 6. Bulk Campaigns
Supports batch sends for large-scale notifications (e.g., promotions).

---

## System Architecture

### High-Level Flow
```
[CRM Modules (e.g., HR Service)] --> [Kafka Event] --> [Notification API/Orchestrator]
    |
    v
[Create NotificationRecord] --> [Celery Queue] --> [Channel Handler (Email/SMS/Push/In-App)]
    |                                           |
    v                                           v
[Update Status & Log] <----------------- [Provider Response] (e.g., Twilio, Firebase)
    |
    v
[Analytics & Audit Logs] --> [Tenant Dashboard]
```

### Key Layers
1. **API Layer**: Django REST endpoints for triggering/managing notifications.
2. **Orchestrator Layer**: Validation, dispatching, and logging.
3. **Handler Layer**: Pluggable per-channel senders (async-capable).
4. **Queue Layer**: Celery for async execution with Redis broker.
5. **Data Layer**: PostgreSQL for records/templates/creds; Redis for caching/WebSockets.
6. **Event Layer**: Kafka for inbound triggers (e.g., from HR) and outbound events.
7. **Monitoring Layer**: Flower for Celery, Django logs + Sentry/ELK.

### Diagram (ASCII Art)
```
+-------------------+     +-------------------+     +-------------------+
|   CRM/External    |     |   Notification    |     |   Providers       |
|   (Kafka/HTTP)    |<--->|   API/Orchestrator| <-->| (Twilio/Firebase) |
+-------------------+     +-------------------+     +-------------------+
                                 |                          ^
                                 v                          |
                           +-----------+                    |
                           | Celery    |                    |
                           | Queue     |                    |
                           +-----------+                    |
                                 |                          |
                                 v                          |
                           +-----------+                    |
                           | PostgreSQL| <------------------+
                           | (Records) |
                           +-----------+
```

For visual diagram: See `docs/MultiTenantNotificationFlowchartDesign.png` (add via Mermaid or draw.io).

---

## Application Structure

```
/notification_service/
│
├── docker-compose.yml          # Docker orchestration
├── Dockerfile                  # Build config
├── entrypoint.sh               # Container entrypoint
├── manage.py                   # Django management
├── requirements.txt            # Dependencies
├── README.md                   # This file
│
├── notification_service/       # Django project
│   ├── __init__.py
│   ├── asgi.py                 # ASGI for WebSockets
│   ├── settings.py             # Config (multi-tenant, Celery, Channels)
│   ├── urls.py                 # Root URLs (API, docs, health)
│   ├── wsgi.py                 # WSGI for sync
│   └── middleware.py           # JWT auth & DB connection
│
├── notifications/              # Main Django app
│   ├── __init__.py
│   ├── admin.py                # Django admin registration
│   ├── apps.py                 # App config
│   ├── models.py               # NotificationRecord, TenantCredentials, etc.
│   ├── tasks.py                # Celery tasks (send, bulk, retries)
│   ├── serializers.py          # DRF serializers
│   ├── routing.py              # WebSocket routes
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── views.py            # ListCreate, Analytics, etc.
│   │   ├── serializers.py      # Per-model serializers
│   │   ├── permissions.py      # Tenant isolation
│   │   └── urls.py             # API routes (/records/, /campaigns/, etc.)
│   │
│   ├── channels/               # Pluggable handlers
│   │   ├── __init__.py
│   │   ├── base_handler.py     # ABC interface
│   │   ├── email_handler.py
│   │   ├── sms_handler.py
│   │   ├── push_handler.py
│   │   └── inapp_handler.py
│   │
│   ├── orchestrator/
│   │   ├── __init__.py
│   │   ├── validator.py        # Tenant/channel validation
│   │   ├── dispatcher.py       # Route to handler
│   │   └── logger.py           # Audit logging
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── encryption.py       # AES-256 for creds
│   │   ├── context.py          # Tenant resolver
│   │   ├── exceptions.py       # Custom errors
│   │   ├── status_codes.py     # Unified codes
│   │   ├── kafka_producer.py   # Event producing
│   │   └── kafka_consumer.py   # Event consuming
│   │
│   └── consumers.py            # Kafka consumer script + WebSocket consumers
│
├── notifications_logs/         # Log volume
├── media/                      # File uploads
└── staticfiles/                # Static assets
```

---

## Installation & Setup

### Prerequisites
- Docker & Docker Compose (v2+)
- Python 3.12 (for local dev)
- External services: Kafka (in network), Auth Service (for JWT)

### Quick Start (Docker)
1. Clone the repo:
   ```
   git clone <repo-url>
   cd notification_service
   ```

2. Copy env:
   ```
   cp .env.example .env
   ```
   Edit `.env`: Set `DJANGO_SECRET_KEY`, `ENCRYPTION_KEY` (generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`), Kafka/Postgres creds if custom.

3. Build & Run:
   ```
   docker-compose up -d --build
   ```

4. Migrate:
   ```
   docker-compose exec notifications-service python manage.py makemigrations
   docker-compose exec notifications-service python manage.py migrate
   ```

5. Create Superuser (optional):
   ```
   docker-compose exec notifications-service python manage.py createsuperuser
   ```

### Local Development
1. Virtualenv: `python -m venv venv && source venv/bin/activate` (Linux/Mac) or `venv\Scripts\activate` (Windows).
2. Install: `pip install -r requirements.txt`.
3. Run DB/Redis: `docker-compose up -d notifications_postgres notifications_redis`.
4. Migrate & Run: `python manage.py migrate && python manage.py runserver 3001`.

### Health Checks
- API: `curl http://localhost:3001/api/notifications/health/`
- Swagger Docs: `http://localhost:3001/api/docs/`
- Flower (Celery): `http://localhost:5556`
- WebSocket: Connect via `ws://localhost:3001/ws/notifications/`

---

## API Documentation

### Base URL
`http://localhost:3001/api/notifications/`

### Authentication
- Bearer JWT (RS256) from Auth Service.
- Tenant isolation via `tenant_unique_id` in token.

### Endpoints

#### 1. Credentials Management
- **POST `/credentials/`**: Create tenant creds (e.g., `{"channel": "sms", "credentials": {"account_sid": "...", "auth_token": "..."}}`).
- **GET `/credentials/`**: List tenant creds (paginated).

#### 2. Templates Management
- **POST `/templates/`**: Create template (e.g., `{"name": "Interview Invite", "channel": "email", "content": {"subject": "Hi {{name}}", "body": "..."}, "placeholders": ["{{name}}"]}`).
- **GET `/templates/`**: List templates.

#### 3. Single Notifications
- **POST `/records/`**: Send notification (e.g., `{"channel": "email", "recipient": "user@example.com", "content": {"subject": "Hi {{name}}"}, "context": {"name": "John"}}`).
- **GET `/records/`**: List records (filter by `status`, `channel`; search `recipient`).
- **GET/PUT/DELETE `/records/{id}/`**: Detail/update/delete.

#### 4. Bulk Campaigns
- **POST `/campaigns/`**: Create campaign (e.g., `{"name": "Promo", "channel": "push", "content": {"title": "Offer {{name}}!"}, "recipients": [{"recipient": "token1", "context": {"name": "User1"}}]}`).
- **GET `/campaigns/`**: List campaigns (filter by `status`).

#### 5. Analytics
- **GET `/analytics/?days=30`**: Tenant stats (success rate, channel usage, failures).

#### 6. Webhooks
- **POST `/webhook/`**: External trigger (e.g., `{"tenant_id": "uuid", "channel": "sms", "recipient": "+123", "content": {...}}`).

#### 7. WebSockets (In-App)
- Connect: `ws://localhost:3001/ws/notifications/`
- Receives real-time alerts.

### Error Responses
All errors follow DRF standards: `{"detail": "Error msg", "code": "error_code"}`.

---

## Logging & Monitoring

Every message is tracked via **NotificationRecord** and **AuditLog** tables.

| Field              | Description                  |
|--------------------|------------------------------|
| `tenant_id`        | Tenant sending the message   |
| `recipient`        | Recipient’s address/phone/token |
| `channel`          | Email, SMS, Push, In-App     |
| `status`           | PENDING / SUCCESS / FAILED / RETRYING |
| `failure_reason`   | AUTH_ERROR / NETWORK_ERROR / etc. |
| `provider_response`| Raw provider feedback        |
| `retry_count`      | Retry attempts               |
| `sent_at`          | Processing timestamp         |

**Tools**:
- **Django Logs**: `./notifications_logs/notifications_service.log` (rotating).
- **Celery**: Flower dashboard.
- **Errors**: Integrate Sentry for alerts.
- **Metrics**: Prometheus + Grafana (future).

---

## Retry & Failure Recovery

- Automatic retries with **exponential backoff** (via Celery: 60s * 2^retry).
- Max retries: 3 per message.
- Persistent tracking in DB.
- Tenant admin notified on repeated failures (via internal queue).
- System alerts for infra issues (e.g., Redis down).

Failure Categories:
- `AUTH_ERROR`: Invalid creds
- `NETWORK_ERROR`: Connection issues
- `PROVIDER_ERROR`: Third-party failures
- `CONTENT_ERROR`: Invalid format
- `UNKNOWN_ERROR`: Unhandled

---

## Analytics & Insights

Per-tenant API for:
- Delivery success rate
- Average send latency
- Channel usage distribution
- Common failure patterns
- Activity heatmaps

**Future**: AI for open/click prediction (OpenAI integration stub in tasks.py).

Example Response:
```json
{
  "total_sent": 150,
  "total_failed": 5,
  "success_rate": 96.77,
  "channel_usage": {"email": 80, "sms": 40, "push": 20, "inapp": 10},
  "failure_patterns": {"network_error": 3, "content_error": 2}
}
```

---

## Infrastructure Overview

| Component      | Technology                  |
|----------------|-----------------------------|
| Backend        | Django 5.0 (Multi-Tenant)   |
| Queue          | Celery 5.3                  |
| Broker         | Redis 7                     |
| Database       | PostgreSQL 15 (tenant_id filtering) |
| Logging        | Django + Rotating Files     |
| Container      | Docker & Compose            |
| Deployment     | AWS ECS / Kubernetes        |
| Monitoring     | Flower, Prometheus/Grafana  |
| Events         | Kafka (confluent-kafka)     |
| Real-Time      | Django Channels + Redis     |

---

## Security

- **Encryption**: AES-256 (Fernet) for credentials at rest.
- **Logs**: Masked (no plaintext secrets).
- **Isolation**: Tenant_id filtering on all queries; JWT middleware.
- **Access**: Role-based (hr/admin/root-admin via JWT claims).
- **Transport**: HTTPS enforced; WebSockets wss://.
- **Compliance**: GDPR-ready (soft deletes, audit logs).

---

## Extensibility Roadmap

1. **Bulk Campaigns**: ✅ Implemented (with parallel Celery groups).
2. **WhatsApp API**: Add `whatsapp_handler.py` (Meta SDK).
3. **Webhook Triggers**: ✅ Stubbed; expand for more events.
4. **AI Analytics**: Stubbed; integrate OpenAI for optimization.
5. **Rules Engine**: Add Celery Beat for scheduled workflows.

To add a channel: Implement `base_handler.py` subclass → Update `dispatcher.py` → Add serializer validation.

---

## Development Guidelines

- **Modular Design**: Channels independent; always async enqueue.
- **Logging**: Consistent via `logger.py`; tag with tenant_id.
- **Testing**: Unit test handlers/orchestrator (pytest; coverage >80%).
- **Tenant Isolation**: Filter querysets by `tenant_id`; no cross-tenant leaks.
- **Commits**: Semantic (feat:, fix:, chore:); branch `feature/xxx`.
- **Linting**: Black + flake8; pre-commit hooks.

Run Tests: `pytest` (add `pytest-django` to reqs).

---

## Example Workflow

1. **Tenant triggers event** (e.g., HR sends reward via Kafka).
2. **Consumer** validates & creates NotificationRecord (PENDING).
3. **Orchestrator** dispatches to Celery task.
4. **Handler** sends (e.g., SMS via Twilio).
5. **Update** status to SUCCESS/FAILED; log audit.
6. **Analytics** updated; tenant dashboard reflects stats.

**Kafka Example** (Produce to `hr-events`):
```json
{"event_type": "reward_issued", "tenant_id": "uuid", "employee_details": {"phone": "+123", "name": "John"}, "value": 100}
```

---

## Troubleshooting

| Issue                          | Solution |
|--------------------------------|----------|
| **JWT Auth Fail**              | Check `AUTH_SERVICE_URL`; verify RS256 kid. |
| **Celery Not Starting**        | `docker-compose logs celery-worker`; ensure Redis up. |
| **Migrations Fail**            | `docker-compose exec notifications-service python manage.py migrate`. |
| **WebSocket Connect Error**    | Ensure Channels/Redis; use wss:// in prod. |
| **Kafka No Events**            | Verify bootstrap servers; check consumer logs. |
| **Creds Not Decrypting**       | Regenerate `ENCRYPTION_KEY`; re-save creds. |

Common Logs: `docker-compose logs -f`.

---

## Contributing

1. Fork & branch: `git checkout -b feature/new-channel`.
2. Commit & PR: Describe changes; link issues.
3. Tests: Run `pytest`; update docs.
4. Review: CI/CD via GitHub Actions (future).

Issues: [GitHub Repo](https://github.com/your-org/notification_service/issues).

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

**Questions?** Open an issue or ping @ekene-onwon. Happy notifying! 🚀