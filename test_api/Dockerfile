# ============================================================================
# LMS Service - Multi-Stage Production Dockerfile
# ============================================================================

# Stage 1: Builder
# ============================================================================
FROM python:3.11-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --user --default-timeout=200 --no-cache-dir -r requirements.txt


# Stage 2: Runtime
# ============================================================================
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DJANGO_SETTINGS_MODULE=complete_lms.settings \
    PATH=/home/appuser/.local/bin:$PATH

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Copy Python dependencies from builder
COPY --from=builder /root/.local /home/appuser/.local

# Copy application code
COPY --chown=appuser:appuser . .

# Convert line endings and set permissions
RUN sed -i 's/\r$//' /app/entrypoint.sh && \
    sed -i 's/\r$//' /app/consumer-entrypoint.sh && \
    chmod +x /app/entrypoint.sh /app/consumer-entrypoint.sh

# Switch to non-root user
USER appuser

EXPOSE 8004

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8004/health/ || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:8004", "--workers", "4", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "complete_lms.wsgi:application"]