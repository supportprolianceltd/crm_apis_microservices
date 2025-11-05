
---

## ⚙️ **Build & Run Commands**

### 🧩 Development

```bash
# Build and start all containers
docker-compose -f docker-compose.dev.yml up -d --build

# View logs
docker-compose -f docker-compose.dev.yml logs -f

# Run Django migrations
docker-compose -f docker-compose.dev.yml exec auth-service python manage.py migrate

# Create superuser
docker-compose -f docker-compose.dev.yml exec auth-service python manage.py createsuperuser
```

---

### 🏭 Production

```bash
# Build and start all containers
docker-compose -f docker-compose.prod.yml up -d --build

# Scale Celery workers
docker-compose -f docker-compose.prod.yml up -d --scale celery-worker=3

# View logs for a specific service
docker-compose -f docker-compose.prod.yml logs -f auth-service

# Backup the database
docker-compose -f docker-compose.prod.yml exec db pg_dump -U postgres_prod auth_db_prod > backup.sql
```

---

Would you like me to generate a matching **README.md section** (with markdown headings, notes, and commands) that you can drop directly into your repo?
