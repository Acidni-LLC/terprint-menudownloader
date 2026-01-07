# Terprint Menu Downloader - Container App
# Multi-stage build for smaller image size

# =============================================================================
# Stage 1: Build stage with dependencies
# =============================================================================
FROM python:3.11-slim as builder

# Build argument for Azure Artifacts PAT token
ARG AZURE_ARTIFACTS_PAT

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Configure pip to use Azure Artifacts with the PAT token
RUN pip config set global.extra-index-url "https://terprint:${AZURE_ARTIFACTS_PAT}@pkgs.dev.azure.com/acidni/Terprint/_packaging/terprint/pypi/simple/" \
    && pip config set install.trusted-host "pkgs.dev.azure.com"

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt

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
COPY main.py .

# Create writable directories for logs and downloads BEFORE switching to non-root
# The terprint_menu_downloader package may try to create logs in its install location
RUN mkdir -p /tmp/logs /tmp/downloads \
    && chmod 777 /tmp/logs /tmp/downloads \
    && chown -R appuser:appuser /tmp/logs /tmp/downloads

# Create logs directory in the package location with correct permissions
# This handles the case where the package creates logs at import time
RUN mkdir -p /usr/local/lib/python3.11/site-packages/terprint_menu_downloader/logs \
    && chmod 777 /usr/local/lib/python3.11/site-packages/terprint_menu_downloader/logs \
    && chown -R appuser:appuser /usr/local/lib/python3.11/site-packages/terprint_menu_downloader/logs

# Set ownership
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Environment variables for log and temp directories
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
