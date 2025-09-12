FROM python:3.11-slim

WORKDIR /app

# Install system dependencies, including postgresql-client for pg_isready
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    postgresql-client \
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
ENV DJANGO_SETTINGS_MODULE=lumina_care.settings

# Expose port for lms-app
EXPOSE 8004

# Make entrypoint executable
RUN chmod +x entrypoint.sh

# Set entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]