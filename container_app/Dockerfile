# Terprint Menu Downloader - Container App
# Multi-stage build for smaller image size

# =============================================================================
# Stage 1: Build stage with dependencies
# =============================================================================
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY container_app/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt

# Copy and install the local terprint-menu-downloader package from source
COPY pyproject.toml .
COPY src/ ./src/
RUN pip install --no-cache-dir --prefix=/install .

# =============================================================================
# Stage 2: Production image
# =============================================================================
FROM python:3.11-slim

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY container_app/*.py ./

# Copy configuration files
COPY container_app/menu_config.json ./menu_config.json
COPY container_app/storeid_location_list.csv ./storeid_location_list.csv

# Create writable directories for logs and downloads
RUN mkdir -p /tmp/logs /tmp/downloads \
    && chmod 777 /tmp/logs /tmp/downloads \
    && chown -R appuser:appuser /tmp/logs /tmp/downloads

# Create logs directory in the package location
RUN mkdir -p /usr/local/lib/python3.11/site-packages/terprint_menu_downloader/logs \
    && chmod 777 /usr/local/lib/python3.11/site-packages/terprint_menu_downloader/logs 2>/dev/null || true

# Set ownership
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Environment variables
ENV PORT=8000
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV LOG_DIR=/tmp/logs
ENV TEMP=/tmp
ENV TMP=/tmp

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Expose port
EXPOSE 8000

# Run the application
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
