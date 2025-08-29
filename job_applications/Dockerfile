FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .
COPY .env .env

# Create directories for logs and media
RUN mkdir -p /app/logs /app/media /app/staticfiles

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=job_applications.settings

# Expose port
EXPOSE 8002

# Make entrypoint script executable
RUN chmod +x entrypoint.sh

# Use entrypoint script to run migrations and start server
ENTRYPOINT ["/app/entrypoint.sh"]