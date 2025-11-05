# Talent Engine Microservice

A robust, scalable, and multi-tenant Talent Engine built with Django, designed to manage job requisitions, integrate with authentication and notification services, and support event-driven workflows for modern CRM platforms.

---

## 🚀 Features

- **Multi-tenancy Support**: Schema-based isolation using `django-tenants`
- **Job Requisition Management**: Create, update, and track job requisitions per tenant
- **Authentication Integration**: Works seamlessly with centralized `auth_service` for user and tenant data
- **Event-driven Architecture**: Kafka-powered event sync for users, tenants, and branches
- **RESTful API**: Clean, documented endpoints with Swagger UI
- **Extensible**: Easily add new modules or integrate with other microservices
- **Comprehensive Logging**: Rotating file and console logs for all operations

---

## 🏗 Architecture

```mermaid
graph TD
    A[CRM Frontend / Other Services] -->|HTTP REST API| B[Talent Engine Service]
    B --> C[PostgreSQL (Multi-tenant)]
    B --> D[Kafka Broker]
    D --> E[auth_service]
    D --> F[Notification Service]
    B --> G[Swagger UI]
```

---

## 📦 Tech Stack

- **Framework**: Django 4.x, Django REST Framework
- **Multi-tenancy**: django-tenants
- **Database**: PostgreSQL (schema-based multi-tenancy)
- **Event Bus**: Kafka (kafka-python)
- **API Docs**: drf-spectacular (Swagger/OpenAPI)
- **Containerization**: Docker & Docker Compose

---

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11 (for local dev)
- PostgreSQL 15+
- Kafka & Zookeeper (for event sync)
- Running `auth_service` and `notification_service` containers

### Installation

1. **Clone the Repository**
    ```bash
    git clone <your-repo-url> talent_engine
    cd talent_engine
    ```

2. **Environment Configuration**
    ```bash
    cp .env.example .env
    ```
    Edit `.env` with your DB, Kafka, and service URLs.

3. **Build and Start Services**
    ```bash
    docker-compose up -d --build
    ```

4. **Apply Migrations**
    ```bash
    docker exec -it talent_engine bash
    python manage.py migrate_schemas --shared
    python manage.py migrate_schemas
    ```

5. **Access Swagger UI**
    - [http://localhost:8001/api/schema/swagger-ui/](http://localhost:8001/api/schema/swagger-ui/)

---

## 📋 API Usage

### Authentication

- Obtain JWT token from `auth_service`:
    ```http
    POST /api/token/
    Content-Type: application/json

    {
      "email": "user@example.com",
      "password": "password"
    }
    ```

- Use the token for all Talent Engine requests:
    ```
    Authorization: Bearer <access_token>
    X-Tenant-ID: <tenant_id>
    ```

### Job Requisition Example

**Create a Job Requisition**
```http
POST /api/job-requisitions/
Authorization: Bearer <access_token>
X-Tenant-ID: <tenant_id>
Content-Type: application/json

{
  "title": "Software Engineer",
  "role": "staff",
  "company_name": "Tech Corp",
  "job_type": "full_time",
  "location_type": "remote",
  "salary_range": "100000-120000",
  "job_description": "Develop software"
}
```

**List Job Requisitions**
```http
GET /api/job-requisitions/
Authorization: Bearer <access_token>
X-Tenant-ID: <tenant_id>
```

---

## 🏗 Project Structure

```
talent_engine/
├── talent_engine/
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   ├── middleware.py
│   ├── consumer.py
│   ├── core/
│   ├── jobRequisitions/
├── logs/
├── media/
├── staticfiles/
├── templates/
├── manage.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env
```

---

## 🔧 Configuration

- **Multi-tenancy**: Each tenant has its own schema, managed by `django-tenants`.
- **Kafka Topics**: Used for syncing tenants, branches, and users.
- **Environment Variables**: See `.env.example` for all required settings.

---

## 🧪 Testing

- Use Swagger UI or Postman for API testing.
- Example test:
    ```bash
    curl -X GET http://localhost:8001/api/job-requisitions/ \
      -H "Authorization: Bearer <access_token>" \
      -H "X-Tenant-ID: <tenant_id>"
    ```

---

## 🚀 Deployment

- **Production**: Use Docker Compose or Kubernetes.
- **Scaling**: Stateless, can be scaled horizontally.
- **Monitoring**: Logs to file and console; integrate with ELK or Prometheus as needed.

---

## 🆘 Support

- Check the API docs at `/api/schema/swagger-ui/`
- Review logs in `logs/talent_engine.log`
- For issues, create a GitHub issue or contact the maintainer.

---

## 🎯 Roadmap

- [ ] Advanced requisition approval workflows
- [ ] Integration with external HR systems
- [ ] Analytics and reporting dashboards
- [ ] Webhook/event callback support
- [ ] Admin UI for tenant management

---

**Built with Django, DRF, and modern best practices for a scalable, maintainable codebase.**