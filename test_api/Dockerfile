# lms-service/Dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    postgresql-client \
    netcat-openbsd \
    dos2unix \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN dos2unix /app/entrypoint.sh && \
    dos2unix /app/consumer-entrypoint.sh && \
    chmod +x /app/entrypoint.sh /app/consumer-entrypoint.sh

ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=complete_lms.settings

EXPOSE 8004

ENTRYPOINT ["/app/entrypoint.sh"]