# ---------------------------------------------------------------------------
# Céal — Multi-Stage Docker Build
# ---------------------------------------------------------------------------
# Stage 1 (builder): Install build-time deps (gcc, libpq-dev for asyncpg)
# Stage 2 (runtime): Slim image with only runtime deps
# ---------------------------------------------------------------------------

# --- Stage 1: Builder ---
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# --- Stage 2: Runtime ---
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 curl && \
    rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY src/ src/
COPY data/ data/
COPY pyproject.toml .

# Create non-root user
RUN useradd --create-home --shell /bin/bash ceal && \
    mkdir -p /app/data && \
    chown -R ceal:ceal /app

USER ceal

ENV PORT=8000
EXPOSE ${PORT}

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

CMD ["python", "-m", "uvicorn", "src.web.app:app", "--host", "0.0.0.0", "--port", "8000"]
