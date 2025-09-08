FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    tesseract-ocr \
    libffi-dev \
    libssl-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install pytesseract pillow

# Pre-download ML models during build
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
RUN python -c "from transformers import AutoTokenizer, AutoModelForTokenClassification; AutoTokenizer.from_pretrained('dslim/bert-base-NER'); AutoModelForTokenClassification.from_pretrained('dslim/bert-base-NER')"

# Copy project files
COPY . .
COPY .env .env

# Create directories for logs and media
RUN mkdir -p /app/logs /app/media /app/staticfiles

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=job_applications.settings

# Expose port
EXPOSE 8003

# Make entrypoint script executable
RUN chmod +x entrypoint.sh

# Use entrypoint script to run migrations and start server
ENTRYPOINT ["/app/entrypoint.sh"]


