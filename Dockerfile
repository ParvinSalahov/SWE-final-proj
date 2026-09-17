# =====================================================================
# Dockerfile for AI Engineering Final Project - Smart Lost & Found
# =====================================================================

# ---- Base image -----------------------------------------------------
FROM python:3.12-slim

# ---- Build-time labels ----------------------------------------------
LABEL org.opencontainers.image.title="Smart Lost & Found - AI Engineering Final Project"
LABEL org.opencontainers.image.version="1.0"

# ---- Set sensible defaults for Python in a container ----------------
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ---- System dependencies --------------------------------------------
# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ---- Working directory ----------------------------------------------
WORKDIR /app

# ---- Install Python dependencies BEFORE copying the code ------------
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- Copy the rest of the project -----------------------------------
COPY . .

# ---- Network port (HTTP server) --------------------------------------
EXPOSE 8000

# ---- Non-root user (security best practice) -------------------------
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app
USER appuser

# ---- Healthcheck ----------------------------------------------------
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://localhost:8000/ || exit 1

# ---- Default command (HTTP server) ---------------------------------
CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000"]

# =====================================================================
# Build and run:
#   docker build -t lostfound .
#   docker-compose up -d
#   docker run --env-file .env -p 8000:8000 lostfound
#
# Verify before submission:
#   docker run --env-file .env lostfound pytest tests/test_ai_smoke.py
# =====================================================================
