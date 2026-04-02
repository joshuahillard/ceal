# ============================================================================
# Céal — Multi-stage Docker build
# Stage 1: Build dependencies in a full image
# Stage 2: Copy only what's needed into a slim runtime image
# ============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Builder
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies (some pip packages need gcc for C extensions)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Copy only requirements first (layer caching — rebuilds only when deps change)
COPY requirements.txt .

# Install Python dependencies into a prefix we can copy later
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---------------------------------------------------------------------------
# Stage 2: Runtime
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

# Install runtime dependency for asyncpg (PostgreSQL client library)
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 && \
    rm -rf /var/lib/apt/lists/*

# Security: run as non-root user
RUN groupadd -r ceal && useradd -r -g ceal -d /app -s /sbin/nologin ceal

WORKDIR /app

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy application source code
COPY src/ ./src/
COPY pyproject.toml ./

# Create data directory for SQLite (will be ephemeral on Cloud Run)
RUN mkdir -p /app/data && chown -R ceal:ceal /app

# Copy resume data file (needed for pre-fill engine)
COPY data/resume.txt ./data/

# Switch to non-root user
USER ceal

# FastAPI default port
EXPOSE 8000

# Health check — Cloud Run uses HTTP health checks, Docker uses this for local
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Run the web server
# - Host 0.0.0.0 required for Docker networking
# - PORT env var is set by Cloud Run (defaults to 8000)
CMD ["python", "-m", "uvicorn", "src.web.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
