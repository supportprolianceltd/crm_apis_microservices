import os

PROJECT_NAME = "notifications_service"
APPS = ["notifications", "messaging"]
FILES = {
    "Dockerfile": """FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

RUN mkdir -p /app/logs /app/media /app/staticfiles
RUN chmod +x entrypoint.sh

CMD ["/app/entrypoint.sh"]
""",

    "entrypoint.sh": """#!/bin/bash

echo "Applying migrations..."
python manage.py migrate

echo "Starting Celery worker..."
celery -A notifications_service worker -l info &

echo "Starting Django server..."
daphne -b 0.0.0.0 -p 8004 notifications_service.asgi:application
""",

    "docker-compose.yaml": """version: '3.8'

services:
  messaging:
    build: .
    container_name: messaging
    ports:
      - "8004:8004"
    volumes:
      - .:/app
    environment:
      - DEBUG=True
      - DJANGO_SETTINGS_MODULE=notifications_service.settings
      - REDIS_HOST=redis
      - KAFKA_BROKER=kafka:9092
    depends_on:
      - redis
      - kafka
    networks:
      - auth_service_default

  redis:
    image: redis:7
    container_name: redis
    ports:
      - "6379:6379"
    networks:
      - auth_service_default

  kafka:
    image: bitnami/kafka:latest
    environment:
      - KAFKA_CFG_ZOOKEEPER_CONNECT=zookeeper:2181
      - ALLOW_PLAINTEXT_LISTENER=yes
    ports:
      - "9092:9092"
    depends_on:
      - zookeeper
    networks:
      - auth_service_default

  zookeeper:
    image: bitnami/zookeeper:latest
    ports:
      - "2181:2181"
    networks:
      - auth_service_default

networks:
  auth_service_default:
    external: true
""",

    "requirements.txt": """Django>=5.2,<6
djangorestframework
channels
channels_redis
celery
redis
kafka-python
requests
gunicorn
daphne
""",

    ".env": """DEBUG=True
DJANGO_SETTINGS_MODULE=notifications_service.settings
REDIS_HOST=redis
KAFKA_BROKER=kafka:9092
""",
}

def create_dirs_and_files():
    os.makedirs(PROJECT_NAME, exist_ok=True)

    for app in APPS:
        os.makedirs(f"{app}/migrations", exist_ok=True)
        open(f"{app}/__init__.py", "w").close()
        open(f"{app}/migrations/__init__.py", "w").close()
        for module in ["models.py", "views.py", "urls.py", "serializers.py", "consumers.py", "tasks.py"]:
            with open(f"{app}/{module}", "w") as f:
                f.write(f"# {module} for {app}\n")

    # Create settings project dir
    for file in ["__init__.py", "asgi.py", "settings.py", "routing.py", "wsgi.py"]:
        with open(f"{PROJECT_NAME}/{file}", "w") as f:
            f.write(f"# {file} for {PROJECT_NAME}\n")

    # Write root-level files
    for filename, content in FILES.items():
        with open(filename, "w") as f:
            f.write(content)

    os.chmod("entrypoint.sh", 0o775)
    print("✅ Project scaffolding complete!")

if __name__ == "__main__":
    create_dirs_and_files()
