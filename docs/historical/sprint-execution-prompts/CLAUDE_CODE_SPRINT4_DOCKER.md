# Céal Sprint 4 — Docker Containerization + GCP Cloud Run Deployment

## CONTEXT
You are working on the Céal project — an AI-powered career signal engine.
The project root is the `ceal/` directory containing `src/`, `tests/`, `pyproject.toml`, `requirements.txt`.

**Branch state**: You are on `main`. This branch contains:
- Phase 1 (scrape → normalize → rank pipeline)
- Phase 2 + 2B (resume tailoring, demo mode, batch, export, persistence)
- Sprint 1 (FastAPI + Jinja2 web UI: Dashboard, Jobs, Demo)
- Sprint 2 (Phase 3 CRM: Kanban board, state-machine status transitions, stale reminders, prompt v1.1)
- Sprint 3 (Phase 4 Auto-Apply: pre-fill engine, approval queue, confidence scoring, CRM sync)
- **202 passing tests**, ruff clean, CI green (6-job matrix: lint, unit 3.11/3.12, integration 3.11/3.12, coverage ≥80%)

**PRE-FLIGHT CHECK**: Before starting any work, run these commands in order:

```bash
# 1. Verify working directory
pwd
# Must be inside the ceal/ project root

# 2. Verify branch and commit
git log --oneline -3
# Expect HEAD at 7a4adf5 on main

# 3. Check for uncommitted changes
git status
# If modified files exist (database.py, schema.sql, or others):
#   - Run: git diff src/models/database.py src/models/schema.sql
#   - READ the diff output carefully
#   - If the changes are Phase 4 auto-apply additions (applications table, application_fields table,
#     create_application(), get_application(), get_approval_queue(), update_application_status(),
#     get_application_stats(), _APP_VALID_TRANSITIONS): these are Sprint 3 leftovers that belong
#     in the codebase. Commit them:
#       git add src/models/database.py src/models/schema.sql
#       git commit -m "chore: commit uncommitted Phase 4 schema and DB function additions"
#   - If the changes are something else entirely, STOP and report what you found.
#   - If there are no uncommitted changes, proceed.

# 4. Verify all tests pass
pytest tests/ -v
# Expect 202 passing. If any fail, STOP and fix them before proceeding.

# 5. Verify lint
ruff check src/ tests/
# Expect 0 errors

# 6. Verify file structure
ls src/web/app.py src/web/routes/dashboard.py src/web/routes/jobs.py src/web/routes/demo.py src/web/routes/applications.py src/web/routes/apply.py
ls src/web/templates/base.html src/web/templates/dashboard.html src/web/templates/jobs.html src/web/templates/demo.html src/web/templates/applications.html src/web/templates/reminders.html src/web/templates/approval_queue.html src/web/templates/application_review.html
ls src/models/database.py src/models/entities.py src/models/schema.sql
ls src/tailoring/engine.py src/tailoring/models.py src/tailoring/db_models.py src/tailoring/resume_parser.py src/tailoring/skill_extractor.py src/tailoring/persistence.py
ls src/apply/prefill.py
ls src/demo.py src/fetcher.py src/batch.py src/export.py
ls src/main.py pyproject.toml requirements.txt
ls data/resume.txt
ls tests/unit/test_web.py tests/unit/test_crm.py tests/unit/test_autoapply.py tests/unit/test_database.py tests/unit/test_tailoring_engine.py
ls .github/workflows/ci.yml
```
If ANY pre-flight check fails, STOP and report what failed. Do NOT proceed.

**Your job**: This sprint has three phases:
1. **Pre-requisite fixes** — Resolve known bugs and deprecation warnings in the existing codebase
2. **Docker containerization** — Multi-stage Dockerfile, docker-compose.yml, .dockerignore
3. **GCP Cloud Run deployment prep** — Health check endpoint, environment configuration, CI/CD deploy job, deployment documentation

---

## CRITICAL RULES (Anti-Hallucination)

1. **READ before WRITE**: Before modifying ANY file, read it first. Never assume file contents.
2. **EXISTING FILES — DO NOT DUPLICATE OR RENAME**:
   - `src/models/database.py` — contains: `get_session()`, `init_db()`, `upsert_job()`, `upsert_jobs_batch()`, `get_unranked_jobs()`, `update_job_ranking()`, `assign_company_tiers()`, `get_top_matches()`, `log_scrape_run()`, `create_resume_profile()`, `link_resume_skill()`, `get_pipeline_stats()`, `VALID_TRANSITIONS` dict, `update_job_status()`, `get_jobs_by_status()`, `get_application_summary()`, `get_stale_applications()`, `_APP_VALID_TRANSITIONS` dict, `create_application()`, `get_application()`, `get_approval_queue()`, `update_application_status()`, `get_application_stats()`
   - `src/models/entities.py` — contains: `JobStatus` enum (8 states), `JobSource`, `RemoteType`, `SkillCategory`, `Proficiency` enums, `ApplicationStatus` enum (5 states: DRAFT, READY, APPROVED, SUBMITTED, WITHDRAWN), `FieldType`, `FieldSource` enums, plus all Pydantic models for pipeline, CRM, and auto-apply
   - `src/models/schema.sql` — 9 tables: `job_listings`, `skills`, `job_skills`, `resume_profiles`, `resume_skills`, `company_tiers`, `scrape_log`, `applications`, `application_fields`. Uses `CREATE TABLE IF NOT EXISTS`.
   - `src/web/app.py` — FastAPI app factory `create_app()` with lifespan calling `init_db()`. Registers 5 routers: dashboard, jobs, applications, apply, demo. `templates = Jinja2Templates(...)`.
   - `src/web/routes/dashboard.py` — `GET /` wired to `get_pipeline_stats()`, `get_application_summary()`, `get_stale_applications()`, `get_application_stats()`
   - `src/web/routes/jobs.py` — `GET /jobs` wired to `get_top_matches()` with tier/score/limit query params
   - `src/web/routes/applications.py` — `GET /applications` (Kanban), `POST /applications/{job_id}/status`, `GET /applications/reminders`
   - `src/web/routes/apply.py` — `GET /apply` (approval queue), `POST /apply/prefill/{job_id}`, `GET /apply/{app_id}` (review), `POST /apply/{app_id}/status`
   - `src/web/routes/demo.py` — `GET /demo`, `POST /demo` wired to full tailoring pipeline
   - `src/web/templates/base.html` — Shared layout with nav: Dashboard, Jobs, Applications, Auto-Apply, Demo
   - `src/apply/prefill.py` — `PreFillEngine` class with regex extraction + `COMMON_ATS_FIELDS`
   - `src/tailoring/engine.py` — `TailoringEngine`, `CURRENT_PROMPT_VERSION = "v1.1"`, `_SYSTEM_PROMPT`, `_TIER_PROMPTS`, `_parse_llm_response()`, `_call_claude_api()` via httpx
   - `src/main.py` — CLI entry with flags: `--query`, `--location`, `--max-results`, `--rank-only`, `--no-rank`, `--tailor`, `--top`, `--web`, `--port`, `--demo`, `--job-url`, `--batch`, `--export`
   - `data/resume.txt` — Josh's resume in parser-compatible format
3. **IMPORT PATHS**: All imports use `src.` prefix (e.g., `from src.models.database import get_pipeline_stats`). The project uses `pythonpath = ["."]` in pyproject.toml.
4. **PYTHON VERSION**: Target Python 3.10+. Do NOT use `datetime.UTC` (use `datetime.timezone.utc`). Do NOT use `StrEnum` (use `str, Enum`).
5. **ASYNC**: The entire codebase is async. Database uses `AsyncSession` with `aiosqlite`. All database functions are `async def`. FastAPI routes that call database functions must be `async def`.
6. **DATABASE**: SQLite via `sqlite+aiosqlite:///data/ceal.db`. Phase 1 + Phase 4 tables in `schema.sql`. Phase 2 tables managed by Alembic.
7. **RUFF CONFIG**: `target-version = "py310"`, `line-length = 120`. Ignored rules: `UP017`, `UP042`, `E501`, `SIM102`, `SIM105`, `SIM108`, `B017`, `B904`. Run `ruff check src/ tests/` before committing.
8. **TESTS**: `pytest` with `asyncio_mode = "strict"`. All async tests need `@pytest.mark.asyncio`. Test isolation uses StaticPool in-memory SQLite. Web route tests MUST mock all database functions (CI has no `data/ceal.db`).
9. **NO SECRETS — ZERO TOLERANCE**: Never hardcode API keys, database credentials, or any secret in ANY file that is committed to git. This includes Dockerfile, docker-compose.yml, CI/CD configs, and Python source. Load ALL secrets from environment variables. `.env` files must be in `.gitignore`.
10. **WEB PATTERNS**: Follow Sprint 1/2/3 patterns exactly — route modules in `src/web/routes/`, templates extending `base.html`, router registered in `app.py`.
11. **NO FABRICATED INFRASTRUCTURE**: Do NOT reference GCP services, Docker features, gcloud CLI flags, or cloud APIs that you are not 100% certain exist. If unsure about a specific flag or feature, use the simplest working approach. Do NOT hallucinate docker-compose options, Dockerfile directives, or gcloud subcommands.
12. **DATA LEAKAGE PREVENTION**: The Docker image must NEVER contain: database files (`*.db`), `.env` files, API keys, `data/` directory contents, `.git/` directory, `__pycache__/`, `.venv/`, or test fixtures containing real data. Verify this explicitly after building.

---

## TASK 0: Pre-Requisite Bug Fixes (COMPLETE BEFORE ALL OTHER TASKS)

### 0a. Resolve uncommitted changes

Run `git status`. If `src/models/database.py` and/or `src/models/schema.sql` show as modified:
1. Run `git diff src/models/database.py` and `git diff src/models/schema.sql`
2. Read the diffs carefully
3. If the changes contain Phase 4 auto-apply additions (applications/application_fields tables, create_application/get_application/get_approval_queue/update_application_status/get_application_stats functions, _APP_VALID_TRANSITIONS dict), commit them:
   ```bash
   git add src/models/database.py src/models/schema.sql
   git commit -m "chore: commit uncommitted Phase 4 schema and DB function additions"
   ```
4. If the changes are something unexpected, STOP and report.

### 0b. Fix Starlette TemplateResponse deprecation warnings

**Read first**: ALL route files in `src/web/routes/` — read each one.

The current code uses the deprecated pattern:
```python
TemplateResponse("template_name.html", {"request": request, ...})
```

Replace ALL instances across ALL route files with the new pattern:
```python
TemplateResponse(request, "template_name.html", context={...})
```

Note: The new signature is `TemplateResponse(request, name, context=None, ...)`. The `request` object moves from inside the context dict to the first positional argument. Remove `"request": request` from the context dict — it is now passed separately.

Files to update (read each first, then fix):
- `src/web/routes/dashboard.py`
- `src/web/routes/jobs.py`
- `src/web/routes/applications.py`
- `src/web/routes/apply.py`
- `src/web/routes/demo.py`

### 0c. Verify fixes

```bash
pytest tests/ -v 2>&1 | tail -20
# Expect: 202 passed, 0 warnings about TemplateResponse (the 18 deprecation warnings should be gone)
ruff check src/ tests/
# Expect: 0 errors
```

### 0d. Commit pre-requisite fixes

```bash
git add -A
git commit -m "fix(web): update TemplateResponse to non-deprecated signature across all routes"
```

---

## TASK 1: Tag v2.3.0 Release (Clean Rollback Point)

Before adding Docker infrastructure, tag the current state:

```bash
git tag -a v2.3.0-phase4-autoapply -m "Release v2.3.0: All 4 phases complete - scraping, tailoring, CRM, auto-apply. 202 tests, 82.77% coverage."
```

Do NOT push the tag yet — we'll push everything at the end.

---

## TASK 2: Create `.dockerignore`

**Create new file**: `.dockerignore`

```
# Version control
.git
.gitignore

# Python artifacts
__pycache__
*.pyc
*.pyo
*.egg-info
.eggs
dist
build

# Virtual environments
.venv
env
venv

# IDE
.vscode
.idea
*.swp
*.swo

# Test artifacts
.pytest_cache
.coverage
htmlcov
.mypy_cache
.ruff_cache

# Data — NEVER bake database or secrets into the image
data/*.db
data/*.db-wal
data/*.db-shm
.env
.env.*

# Documentation and sprint prompts (not needed in prod image)
docs/
*.md
*.pdf
*.pptx
*.docx
*.png
LICENSE

# Alembic migrations (run separately, not in container startup)
alembic/
alembic.ini

# CI/CD config
.github/

# Test mocks and fixtures
tests/mocks/
```

**Verification**: The file must exist and must include `.env`, `data/*.db`, and `.git`.

---

## TASK 3: Create Multi-Stage `Dockerfile`

**Create new file**: `Dockerfile`

**Read first**: `requirements.txt` and `pyproject.toml` — understand all dependencies.

```dockerfile
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
    apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

# Copy only requirements first (layer caching — rebuilds only when deps change)
COPY requirements.txt .

# Install Python dependencies into a prefix we can copy later
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---------------------------------------------------------------------------
# Stage 2: Runtime
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

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
```

**Key decisions documented in comments:**
- Multi-stage build keeps image small (no gcc/build tools in runtime)
- Non-root user for security (Cloud Run best practice)
- `data/resume.txt` IS copied (needed by pre-fill engine) but `data/*.db` is NOT (excluded by .dockerignore)
- HEALTHCHECK for Docker local; Cloud Run uses its own HTTP health check on `/health`
- `--factory` flag because `create_app()` is a factory function

---

## TASK 4: Create `docker-compose.yml`

**Create new file**: `docker-compose.yml`

```yaml
# Céal — Local development with Docker
# Usage: docker compose up --build
# Access: http://localhost:8000

services:
  web:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "${PORT:-8000}:8000"
    environment:
      - LLM_API_KEY=${LLM_API_KEY}
      - DATABASE_URL=sqlite+aiosqlite:///data/ceal.db
      - PYTHONPATH=.
    volumes:
      # Persist SQLite database across container restarts
      - ceal-data:/app/data
    restart: unless-stopped

volumes:
  ceal-data:
    driver: local
```

**Key decisions:**
- Named volume `ceal-data` persists the SQLite database locally
- `LLM_API_KEY` passed through from host `.env` — never hardcoded
- `DATABASE_URL` defaults to the standard SQLite path
- Port configurable via `PORT` env var (Cloud Run pattern)

---

## TASK 5: Add Health Check Endpoint — `src/web/routes/health.py`

**Read first**: `src/web/app.py` — understand the router registration pattern.

**Create new file**: `src/web/routes/health.py`

```python
"""Health check endpoint for Docker and Cloud Run."""

import importlib.metadata
import logging

from fastapi import APIRouter

from src.models.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """
    Health check endpoint.

    Returns service status, version, and database connectivity.
    Used by:
    - Docker HEALTHCHECK directive
    - GCP Cloud Run HTTP health checks
    - Load balancers and monitoring systems

    Interview point: "Health endpoints are the foundation of
    observable systems — they enable zero-downtime deployments
    and automated rollback on Cloud Run."
    """
    status = {"status": "ok", "service": "ceal", "version": _get_version()}

    # Check database connectivity
    try:
        async with get_session() as session:
            result = await session.execute(__import__("sqlalchemy").text("SELECT 1"))
            result.scalar()
        status["database"] = "connected"
    except Exception as e:
        logger.warning("health_check_db_failed", error=str(e))
        status["database"] = "disconnected"
        status["status"] = "degraded"

    return status


def _get_version() -> str:
    """Get version from git tag or fallback."""
    try:
        return importlib.metadata.version("ceal")
    except importlib.metadata.PackageNotFoundError:
        return "dev"
```

### 5b. Register the health router in `src/web/app.py`

**Read first**: `src/web/app.py`

Add the health router import and registration. Follow the exact pattern used for other routers:

```python
from src.web.routes import health
```

Register it BEFORE other routers (health checks should load first):

```python
app.include_router(health.router)
```

---

## TASK 6: Add Health Check Tests — `tests/unit/test_health.py`

**Create new file**: `tests/unit/test_health.py`

```python
"""Tests for the health check endpoint."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.web.app import create_app


@pytest.mark.asyncio
async def test_health_returns_200():
    """Health endpoint returns 200 with expected fields."""
    app = create_app()
    with patch("src.web.routes.health.get_session") as mock_session:
        mock_ctx = AsyncMock()
        mock_result = AsyncMock()
        mock_result.scalar.return_value = 1
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_result)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        # get_session is a context manager
        mock_session.return_value = mock_ctx

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "ceal"
    assert "version" in data
    assert "database" in data


@pytest.mark.asyncio
async def test_health_degraded_on_db_failure():
    """Health endpoint returns degraded when DB is unreachable."""
    app = create_app()
    with patch("src.web.routes.health.get_session") as mock_session:
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(side_effect=Exception("DB down"))
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session.return_value = mock_ctx

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["database"] == "disconnected"
```

---

## TASK 7: Update CI/CD Pipeline — `.github/workflows/ci.yml`

**Read first**: `.github/workflows/ci.yml` — read the ENTIRE file.

Add a new job that builds and validates the Docker image. This job runs AFTER the existing coverage job passes. Add it at the end of the `jobs:` section:

```yaml
  docker-build:
    name: Docker Build Validation
    runs-on: ubuntu-latest
    needs: [coverage]
    steps:
      - uses: actions/checkout@v4

      - name: Build Docker image
        run: docker build -t ceal:ci-${{ github.sha }} .

      - name: Verify no secrets in image
        run: |
          # Check that no database files or .env leaked into the image
          docker run --rm ceal:ci-${{ github.sha }} sh -c "find /app -name '*.db' -o -name '.env' -o -name '*.db-wal' | head -5" | tee /tmp/leaked_files
          if [ -s /tmp/leaked_files ]; then
            echo "ERROR: Secrets or database files found in Docker image!"
            exit 1
          fi

      - name: Verify health endpoint starts
        run: |
          # Start container in background
          docker run -d --name ceal-test -p 8000:8000 ceal:ci-${{ github.sha }}
          # Wait for startup
          sleep 5
          # Check health endpoint
          curl -f http://localhost:8000/health || (docker logs ceal-test && exit 1)
          # Cleanup
          docker stop ceal-test
          docker rm ceal-test
```

**IMPORTANT**: Read the existing CI file first. The new job must:
- Use the same indentation as existing jobs
- Use `needs: [coverage]` to run after all tests pass
- NOT duplicate any existing job names

---

## TASK 8: Create GCP Cloud Run Deployment Script

**Create new file**: `deploy/cloudrun.sh`

```bash
#!/usr/bin/env bash
# Céal — Deploy to GCP Cloud Run
#
# Prerequisites:
#   - gcloud CLI installed and authenticated
#   - GCP project set: gcloud config set project YOUR_PROJECT_ID
#   - Artifact Registry repo created:
#     gcloud artifacts repositories create ceal --repository-format=docker --location=us-east1
#
# Usage:
#   ./deploy/cloudrun.sh
#
# Environment variables (required):
#   GCP_PROJECT_ID  — Your GCP project ID
#   LLM_API_KEY     — Anthropic API key (will be stored in Secret Manager)

set -euo pipefail

# Configuration
REGION="us-east1"
SERVICE_NAME="ceal"
IMAGE_NAME="us-east1-docker.pkg.dev/${GCP_PROJECT_ID}/ceal/ceal"

# Validate required env vars
if [ -z "${GCP_PROJECT_ID:-}" ]; then
    echo "ERROR: GCP_PROJECT_ID is not set"
    exit 1
fi

echo "=== Building Docker image ==="
docker build -t "${IMAGE_NAME}:latest" .

echo "=== Pushing to Artifact Registry ==="
docker push "${IMAGE_NAME}:latest"

echo "=== Deploying to Cloud Run ==="
gcloud run deploy "${SERVICE_NAME}" \
    --image "${IMAGE_NAME}:latest" \
    --region "${REGION}" \
    --platform managed \
    --port 8000 \
    --memory 512Mi \
    --cpu 1 \
    --min-instances 0 \
    --max-instances 3 \
    --set-env-vars "PYTHONPATH=." \
    --set-secrets "LLM_API_KEY=ceal-llm-api-key:latest" \
    --allow-unauthenticated \
    --quiet

echo "=== Deployment complete ==="
gcloud run services describe "${SERVICE_NAME}" --region "${REGION}" --format="value(status.url)"
```

**Then make it executable in git:**
```bash
git update-index --chmod=+x deploy/cloudrun.sh
```

---

## TASK 9: Create `.env.example`

**Create new file**: `.env.example`

```bash
# Céal — Environment Variables
# Copy this file to .env and fill in your values:
#   cp .env.example .env

# Anthropic API key for Claude (used by ranker and tailoring engine)
# Get yours at: https://console.anthropic.com/
LLM_API_KEY=

# Database URL (default: local SQLite)
# For Cloud SQL: postgresql+asyncpg://user:pass@host:5432/ceal
DATABASE_URL=sqlite+aiosqlite:///data/ceal.db

# Web server port (Cloud Run sets this automatically)
PORT=8000

# GCP Project ID (for deployment only)
GCP_PROJECT_ID=
```

### 9b. Verify `.env` is in `.gitignore`

**Read first**: `.gitignore`

If `.env` is NOT already in `.gitignore`, add it:
```
.env
.env.*
!.env.example
```

---

## TASK 10: Update `src/main.py` — PORT Environment Variable Support

**Read first**: `src/main.py` — find the `--port` argument parser section.

Update the web server startup to respect the `PORT` environment variable (Cloud Run sets this automatically):

Find the section where the `--port` flag default is hardcoded and update it to:
```python
import os
# In the argument parser:
parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")), help="Web server port")
```

This makes the app respect Cloud Run's `PORT` env var while keeping `--port 8080` CLI override working.

**Do NOT restructure main.py. Only change the port default.**

---

## TASK 11: Update README.md

**Read first**: `README.md` — read the ENTIRE file.

Add a new section after the existing "Usage" or "Quick Start" section:

### Docker section to add:

```markdown
## Docker

### Local Development

```bash
# Build and run with docker compose
docker compose up --build

# Access at http://localhost:8000
```

### Manual Docker Build

```bash
# Build the image
docker build -t ceal:latest .

# Run with environment variables
docker run -p 8000:8000 \
  -e LLM_API_KEY=your-key-here \
  -v ceal-data:/app/data \
  ceal:latest
```

### GCP Cloud Run Deployment

```bash
# Set your GCP project
export GCP_PROJECT_ID=your-project-id

# Deploy (requires gcloud CLI)
./deploy/cloudrun.sh
```

See `.env.example` for all configuration options.
```

Also update the test count and any version references. The badge should still work.

---

## TASK 12: Lint, Test, Commit, and Verify

### 12a. Lint

```bash
ruff check src/ tests/
# Fix any errors
```

### 12b. Run full test suite

```bash
pytest tests/ -v
# Expect: 204+ passing (202 existing + 2 health endpoint tests)
# Expect: 0 TemplateResponse deprecation warnings
```

### 12c. Verify Docker build (if Docker is available)

```bash
docker build -t ceal:test .
# Verify no secrets leaked into image:
docker run --rm ceal:test sh -c "find /app -name '*.db' -o -name '.env' | head -5"
# Should output nothing

# Verify health endpoint:
docker run -d --name ceal-smoke -p 8000:8000 ceal:test
# Wait 5 seconds for startup
timeout 5 >nul 2>&1 || sleep 5
curl http://localhost:8000/health || python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/health').read())"
docker stop ceal-smoke
docker rm ceal-smoke
```

If Docker is NOT installed on this machine, skip the Docker verification but still commit. The CI pipeline will validate the build.

### 12d. Commit all Sprint 4 changes

```bash
git add Dockerfile docker-compose.yml .dockerignore .env.example deploy/cloudrun.sh
git add src/web/routes/health.py tests/unit/test_health.py
git add src/web/app.py src/main.py README.md
git add src/web/routes/dashboard.py src/web/routes/jobs.py src/web/routes/applications.py src/web/routes/apply.py src/web/routes/demo.py
git add .github/workflows/ci.yml
git add .gitignore
git commit -m "feat(docker): containerize Céal with multi-stage Docker build + GCP Cloud Run deployment

- Multi-stage Dockerfile (python:3.11-slim, non-root user, layer-cached deps)
- docker-compose.yml for local development with persistent volume
- .dockerignore excludes secrets, database files, and dev artifacts
- GET /health endpoint with DB connectivity check (Cloud Run + Docker HEALTHCHECK)
- CI/CD docker-build job validates image and checks for secret leakage
- deploy/cloudrun.sh for GCP Cloud Run with Artifact Registry + Secret Manager
- .env.example documents all environment variables
- PORT env var support for Cloud Run compatibility
- Fixed Starlette TemplateResponse deprecation across all 5 route files
- 204+ tests passing, 0 deprecation warnings"
```

### 12e. Tag Sprint 4

```bash
git tag -a v2.4.0-sprint4-docker -m "Sprint 4: Docker containerization + GCP Cloud Run deployment prep. 204+ tests."
```

### 12f. Push to remote

```bash
git push origin main
git push origin v2.3.0-phase4-autoapply
git push origin v2.4.0-sprint4-docker
```

---

## VERIFICATION CHECKLIST (Run after all tasks)

- [ ] `git status` shows clean working tree
- [ ] `pytest tests/ -v` shows 204+ passing, 0 TemplateResponse warnings
- [ ] `ruff check src/ tests/` shows 0 errors
- [ ] `Dockerfile` exists and does NOT contain any hardcoded secrets
- [ ] `docker-compose.yml` exists and passes secrets via env vars only
- [ ] `.dockerignore` excludes `.env`, `data/*.db`, `.git`
- [ ] `.env.example` exists and contains NO actual secret values
- [ ] `src/web/routes/health.py` exists with `GET /health`
- [ ] `tests/unit/test_health.py` exists with 2 test functions
- [ ] `.github/workflows/ci.yml` has `docker-build` job
- [ ] `deploy/cloudrun.sh` exists with `set -euo pipefail` and env var validation
- [ ] `git log --oneline -5` shows the Sprint 4 commit and both tags
- [ ] `git tag -l` includes `v2.3.0-phase4-autoapply` and `v2.4.0-sprint4-docker`
