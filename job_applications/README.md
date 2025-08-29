# Job Applications Microservice

This microservice handles job applications, scheduling, and related operations for a multi-tenant Django CRM system. It is designed to work alongside other services such as `auth_service` and `talent_engine`.

## Prerequisites

- **Docker** and **Docker Compose** installed
- **Python 3.11** (for local development, optional)
- **Git** (for cloning the repository)
- Ensure ports `8002` (job_applications), `5434` (PostgreSQL), `9092` (Kafka), and `2181` (Zookeeper) are available

## Project Structure

```
job_applications/
├── job_application/           # Django project root
│   ├── __init__.py
│   ├── asgi.py
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── ...
├── job_applications/          # Django app for job applications
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── consumer.py
│   ├── migrations/
│   ├── models.py
│   ├── serializers.py
│   ├── tests.py
│   ├── views.py
│   └── ...
├── logs/
├── media/
├── staticfiles/
├── manage.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env
├── readme.md
```
## Setup Instructions

### 1. Clone the Repository

```sh
git clone <your-repo-url> job_applications
cd job_applications
```

### 2. Create the `.env` File

Create a `.env` file in the root directory with the following content:

```
DJANGO_SECRET_KEY=your-secret-key-here
DEBUG=True
DB_NAME=job_app_db
DB_USER=postgres
DB_PASSWORD=password
DB_HOST=job_app_postgres
DB_PORT=5432
ALLOWED_HOSTS=localhost,127.0.0.1,*
AUTH_SERVICE_URL=http://auth-service:8000
TALENT_ENGINE_URL=http://talent_engine:8001
KAFKA_BOOTSTRAP_SERVERS=kafka:9092
CORS_ALLOWED_ORIGINS=http://localhost:5173,https://crm-frontend-react.vercel.app,http://localhost:8000
```

Replace `your-secret-key-here` with a secure key (generate with `python -c "import secrets; print(secrets.token_hex(32))"`).

### 3. Build and Start the Services

```sh
docker-compose up -d --build
```

This will start:
- The Django job_applications service (port 8002)
- PostgreSQL database (port 5434)
- Kafka and Zookeeper (if included in your main docker-compose setup)

### 4. Apply Migrations

Enter the running container and apply migrations:

```sh
docker exec -it job_applications bash
python manage.py makemigrations
python manage.py migrate
```

### 5. Access the Service

- API: http://localhost:8002/
- Swagger/OpenAPI docs (if enabled): http://localhost:8002/api/docs/

### 6. Environment Variables

Key environment variables (see `.env`):

- `DJANGO_SECRET_KEY`: Django secret key
- `DEBUG`: Set to `True` for development
- `DB_*`: Database connection settings
- `ALLOWED_HOSTS`: Comma-separated list of allowed hosts
- `AUTH_SERVICE_URL`: URL of the authentication service
- `TALENT_ENGINE_URL`: URL of the talent engine service
- `KAFKA_BOOTSTRAP_SERVERS`: Kafka broker address
- `CORS_ALLOWED_ORIGINS`: Comma-separated list of allowed CORS origins

### 7. Useful Commands

- **View logs:**  
  `docker logs job_applications`
- **Stop services:**  
  `docker-compose down`
- **Rebuild:**  
  `docker-compose up -d --build`

### 8. Troubleshooting

- **Database connection errors:**  
  Ensure `job_app_postgres` is healthy (`docker ps` and `docker logs job_app_postgres`).
- **CORS errors:**  
  Make sure your frontend URL is in `CORS_ALLOWED_ORIGINS`.
- **Port conflicts:**  
  Change the exposed ports in `docker-compose.yml` if needed.

---

## License

MIT License

---

## Authors

- Your Name / Team

For more details, see the `docker-compose.yml` and