
```markdown
# 📬 Notifications & Messaging Service

This microservice handles real-time **in-app notifications**, **email notifications**, and **user-to-user chat** for a multi-tenant CRM system.

Built using **Django**, **Django Channels**, **Celery**, **Redis**, and **Kafka**, it supports tenant-specific email configurations, real-time WebSocket delivery, and decoupled event-based communication.

---

## 🚀 Features

- ✅ **Real-time notifications** (WebSockets via Django Channels)
- ✅ **In-app notification center** for users
- ✅ **Email notifications** using tenant-specific SMTP configs (from Auth Service)
- ✅ **1-on-1 chat system** (messaging module)
- ✅ **Kafka/RabbitMQ event queue integration**
- ✅ **Celery for asynchronous task processing**
- ✅ **Single database multi-tenancy** (`tenant_id` field)
- ✅ **Fully containerized** with Docker & Docker Compose

---

## 🧱 Architecture

```

```
                      ┌────────────┐
                      │ Other CRMs │
                      └────┬───────┘
                           ▼
                    ┌───────────────┐
                    │ API Gateway   │
                    └────┬──────────┘
                         ▼
       ┌────────────────────────────────────┐
       │    🧠 Messaging & Notification Svc   │
       │ ─────────────────────────────────── │
       │  - Real-time WebSocket (Channels)   │
       │  - In-app DB Notification storage   │
       │  - Email via Celery + SMTP          │
       └────────────────────────────────────┘
           ▲      ▲             ▲
           │      │             │
       Kafka   Auth Svc      Redis (WS + Celery)
```

```

---

## ⚙️ Technologies Used

- **Django** 5.x
- **Django Channels** (for WebSockets)
- **Celery** + **Redis** (for background tasks)
- **Kafka** (or RabbitMQ) for event queuing
- **Docker / Docker Compose**
- **PostgreSQL** (with `tenant_id`-based filtering)
- **JWT Auth** via API Gateway or Auth Service

---

## 📁 Project Structure

```

notifications\_service/
├── notifications/            # In-app notifications
├── messaging/                # Real-time 1-on-1 chat
├── notifications\_service/    # Core settings
│   ├── asgi.py               # ASGI config (Channels)
│   ├── routing.py            # WebSocket routing
│   └── settings.py
├── docker-compose.yaml
├── Dockerfile
└── entrypoint.sh

````

---

## 📦 Installation (Development)

### 🔧 Requirements

- Docker & Docker Compose
- Python 3.11+ (if running locally)

### 🛠️ Setup Steps

1. Clone the repo:
   ```bash
   git clone https://github.com/your-org/notifications-service.git
   cd notifications-service
````

2. Start the containers:

   ```bash
   docker-compose up --build
   ```

3. Access the service:

   * WebSocket Port: `ws://localhost:8004/ws/notifications/`
   * REST API (e.g.): `http://localhost:8004/api/notifications/`

---

## 🧪 API Overview

| Endpoint                                   | Method | Description                       |
| ------------------------------------------ | ------ | --------------------------------- |
| `/api/notifications/`                      | GET    | Fetch user's in-app notifications |
| `/api/notifications/mark-as-read/`         | POST   | Mark notifications as read        |
| `/api/messages/send/`                      | POST   | Send a direct message             |
| `/ws/notifications/{tenant_id}/{user_id}/` | WS     | Real-time notification channel    |

---

## ✉️ Sending Email via Celery

The service pulls **email templates** and **SMTP credentials** from the `auth-service`.

```python
send_notification_email.delay(
    tenant_id='TEN-0001',
    to_email='user@example.com',
    subject='Interview Invitation',
    template_key='interviewScheduling',
    context={
        "Candidate Name": "John Doe",
        "Position": "Senior Developer",
        "Company": "Lumina Care"
    }
)
```

---

## 🧠 Multi-Tenant Aware

Every notification, message, and email record is scoped by `tenant_id`. This enables single-database multi-tenancy with data isolation.

---

## 🐳 Dockerized

### Dockerfile

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install -r requirements.txt
COPY . .
RUN chmod +x entrypoint.sh
CMD ["/app/entrypoint.sh"]
```

### docker-compose.yaml (snippet)

```yaml
services:
  messaging:
    build: .
    ports:
      - "8004:8004"
    environment:
      - REDIS_HOST=redis
      - KAFKA_BROKER=kafka:9092
    depends_on:
      - redis
      - kafka
```

---

## 📜 License

This project is licensed under the MIT License.

---

## 🤝 Contributing

PRs are welcome! Open an issue first to discuss changes. Please follow the existing coding style and naming conventions.

---

## 📬 Contact

For questions, feedback or support, contact the maintainer:

**Ekene-Onwon Abraham**
Email: `ekenehanson@gmail.com`

---

