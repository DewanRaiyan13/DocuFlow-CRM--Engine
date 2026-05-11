# ──────────────────────────────────────────────────────────────────
# DocuFlow-CRM — Multi-stage Dockerfile
# ──────────────────────────────────────────────────────────────────
# Stage 1: Base image with system dependencies
# Stage 2: Application layer
# ──────────────────────────────────────────────────────────────────

FROM python:3.12-slim AS base

# Prevent Python from writing .pyc files and enable unbuffered stdout
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System deps for PyMuPDF and python-docx
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# ──────────────────────────────────────────────────────────────────
FROM base AS app

WORKDIR /app

# Install Python dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create watch directory
RUN mkdir -p /app/watch_directory

# Default: run the FastAPI server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
