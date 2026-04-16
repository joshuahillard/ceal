# Céal Sprint 7 — Docker + Cloud SQL Reimplementation

## CONTEXT

You are working on the Céal project — an AI-powered career signal engine.
The project root is the `ceal/` directory containing `src/`, `tests/`, `pyproject.toml`, `requirements.txt`.

**What happened**: When we reset `main` to the `codex/semantic-fidelity-guardrail` branch, the Sprint 4 (Docker containerization) and Sprint 5 (Cloud SQL polymorphic DB) implementations were lost. Those implementations are preserved at `C:\Users\joshb\Documents\GitHub\ceal\` (the GitHub copy) and serve as the reference. We are now reimplementing them on the current `main`, which has:

- Phase 1 (scrape → normalize → rank pipeline)
- Phase 2 + 2B (resume tailoring engine, demo mode, batch, .docx export, persistence)
- Sprint 1 (FastAPI + Jinja2 web UI: Dashboard, Jobs, Demo — 3 routers)
- Sprint 6 gap-fill (Phase 2 DDL in schema.sql, SkillGapTable unique constraint, persistence round-trip test)
- Semantic-fidelity guardrail (v1.1): rejects hallucinated metrics and drift

**What this branch does NOT have** (and this sprint does NOT add):
- Sprint 2 (CRM: applications/reminders routes, Kanban, state machine) — separate future sprint
- Sprint 3 (Auto-Apply: prefill engine, approval queue) — separate future sprint
- Those will be reimplemented in a later sprint using the same GitHub reference

**This sprint's scope**: Docker containerization + polymorphic SQLite/PostgreSQL database layer ONLY.

---

## CRITICAL RULES (Anti-Hallucination)

1. **READ before WRITE**: Before modifying ANY file, read it first. Never assume file contents.
2. **EXISTING FILES — DO NOT DUPLICATE OR RENAME**:
   - `src/models/database.py` — All database query functions. Modify IN PLACE.
   - `src/models/entities.py` — All Pydantic models and enums. DO NOT MODIFY.
   - `src/models/schema.sql` — SQLite DDL (11 tables: 7 Phase 1 + 4 Phase 2). DO NOT MODIFY.
   - `src/tailoring/engine.py` — Tailoring engine with v1.1 guardrail. DO NOT MODIFY.
   - `src/tailoring/models.py` — Tailoring Pydantic models. DO NOT MODIFY.
   - `src/tailoring/db_models.py` — SQLAlchemy ORM models. DO NOT MODIFY.
   - `src/tailoring/persistence.py` — Tailoring save/retrieve. DO NOT MODIFY.
   - `src/web/app.py` — FastAPI app factory. Modify ONLY to add health router.
   - `.github/workflows/ci.yml` — CI pipeline. Modify to add docker-build + PostgreSQL jobs.
3. **IMPORT PATHS**: All imports use `src.` prefix (e.g., `from src.models.compat import is_sqlite`). The project uses `pythonpath = ["."]` in pyproject.toml.
4. **PYTHON VERSION**: Target Python 3.10+. Do NOT use `datetime.UTC` (use `datetime.timezone.utc`). Do NOT use `StrEnum` (use `str, Enum`).
5. **ASYNC**: The entire codebase is async. Database uses `AsyncSession`. All database functions are `async def`. FastAPI routes must be `async def`.
6. **RUFF CONFIG**: `target-version = "py310"`, `line-length = 120`. Ignored rules: `UP017`, `UP042`, `E501`, `SIM102`, `SIM105`, `SIM108`, `B017`, `B904`.
7. **TESTS**: `pytest` with `asyncio_mode = "strict"`. All async tests need `@pytest.mark.asyncio`. Test isolation uses StaticPool in-memory SQLite.
8. **NO SECRETS — ZERO TOLERANCE**: Never hardcode API keys, passwords, or credentials in any committed file. Use `.env` + `python-dotenv` only.
9. **NO DIALECT-SPECIFIC SQL in shared paths**: All raw SQL in `database.py` must work on BOTH SQLite and PostgreSQL, OR must be behind a backend-detection branch using `src/models/compat.py`. Do NOT write SQLite-only SQL (`strftime`, `AUTOINCREMENT`) into functions that will run on PostgreSQL. Do NOT write PostgreSQL-only SQL (`NOW()`, `SERIAL`, `::text` casts) into functions that will run on SQLite.
10. **DUAL-BACKEND TESTING**: For any database function that contains raw SQL, write a database-level test exercising real SQL against an in-memory database — not just a mock.
11. **NO FABRICATED INFRASTRUCTURE**: Do NOT reference asyncpg features, PostgreSQL extensions, or GCP services you are not certain exist. Use standard SQLAlchemy async patterns only.
12. **DATA LEAKAGE PREVENTION**: No secrets, database files, or `.env` in Docker images.
13. **EXISTING ROUTES**: The web app currently has 3 routes: dashboard, jobs, demo. Do NOT add application/CRM routes in this sprint.
14. **DO NOT MODIFY** any file not explicitly listed in the "Files to Modify" section below. If you think a change is needed elsewhere, STOP and explain why before proceeding.

---

## PRE-FLIGHT CHECK

Run these commands IN ORDER before starting any work:

```bash
# 1. Verify working directory
pwd
# Must be inside the ceal/ project root

# 2. Verify branch
git branch --show-current
# Must be: main

# 3. Verify Sprint 6 gap-fill is present
git log --oneline -5
# Expect to see the Phase 2 DDL + persistence integration test commit

# 4. Check for uncommitted changes
git status
# If modified files exist, read diffs and decide:
#   - Legitimate additions → commit with descriptive message
#   - Unexpected → STOP and report
# If clean, proceed.

# 5. Run all tests
pytest tests/ -v 2>&1 | tail -20
# Record the count and any failures. Fix failures before proceeding.

# 6. Verify lint
ruff check src/ tests/
# Expect 0 errors

# 7. Verify current file structure
ls src/models/database.py src/models/entities.py src/models/schema.sql
ls src/tailoring/engine.py src/tailoring/models.py src/tailoring/db_models.py src/tailoring/persistence.py
ls src/web/app.py src/web/routes/dashboard.py src/web/routes/jobs.py src/web/routes/demo.py
ls .github/workflows/ci.yml

# 8. Verify these files do NOT exist yet (this sprint creates them):
ls src/models/compat.py 2>/dev/null && echo "WARNING: compat.py already exists — read it before overwriting" || echo "OK: compat.py does not exist yet"
ls src/web/routes/health.py 2>/dev/null && echo "WARNING: health.py already exists" || echo "OK: health.py does not exist yet"
ls Dockerfile 2>/dev/null && echo "WARNING: Dockerfile already exists" || echo "OK: Dockerfile does not exist yet"
ls docker-compose.yml 2>/dev/null && echo "WARNING: docker-compose.yml already exists" || echo "OK: docker-compose.yml does not exist yet"
ls src/models/schema_postgres.sql 2>/dev/null && echo "WARNING: schema_postgres.sql already exists" || echo "OK: schema_postgres.sql does not exist yet"
```

If ANY pre-flight check fails (steps 1-7), STOP and report what failed. Do NOT proceed.

---

## FILE INVENTORY

### Files to Create (new)

| # | File | Lines (approx) | Purpose |
|---|------|----------------|---------|
| 1 | `src/models/compat.py` | ~39 | Backend detection: `get_database_url()`, `is_postgres()`, `is_sqlite()` |
| 2 | `src/models/schema_postgres.sql` | ~300 | PostgreSQL DDL — same 11 tables as `schema.sql` but with `SERIAL`, `DOUBLE PRECISION`, `to_char(NOW()...)`, PG trigger syntax |
| 3 | `src/web/routes/health.py` | ~52 | `GET /health` endpoint — returns status, version, DB connectivity |
| 4 | `tests/unit/test_health.py` | ~56 | Health endpoint tests (200 OK + degraded on DB failure) |
| 5 | `Dockerfile` | ~67 | Multi-stage build: builder (`gcc`+`libpq-dev`) → runtime (`python:3.11-slim`, non-root, `HEALTHCHECK`) |
| 6 | `docker-compose.yml` | ~41 | PostgreSQL 16 + web service with health checks |
| 7 | `.dockerignore` | ~57 | Excludes secrets, DB files, docs, alembic, test mocks |
| 8 | `.env.example` | ~22 | Environment variable documentation |
| 9 | `deploy/cloudrun.sh` | ~60 | GCP Cloud Run deployment script |

### Files to Modify (existing)

| # | File | Changes |
|---|------|---------|
| 1 | `src/models/database.py` | Replace hardcoded `DATABASE_URL` with compat-based factory. Add `is_sqlite()` guard on PRAGMA listener. Upgrade `init_db()` to auto-select schema file and use `engine.begin()` for PostgreSQL. Upgrade `_split_sql_statements()` to handle `$$` dollar-quoting. |
| 2 | `src/web/app.py` | Add `from src.web.routes import health` and `app.include_router(health.router)` |
| 3 | `requirements.txt` | Add `asyncpg` for PostgreSQL async driver |
| 4 | `.github/workflows/ci.yml` | Add `docker-build` job and `db-tests-postgres` job with PostgreSQL service container |

---

## TASK 0: Read All Files That Will Be Modified

Before writing ANY code, read these files IN FULL. This is not optional.

```
src/models/database.py
src/models/schema.sql
src/web/app.py
requirements.txt
.github/workflows/ci.yml
```

Also read these for reference (do not modify):
```
src/tailoring/db_models.py
src/tailoring/persistence.py
```

---

## TASK 1: Create `src/models/compat.py` (Backend Detection)

**Purpose**: Pure functions for database backend detection. No side effects, no imports from other `src/` modules.

**Implementation**:

```python
"""
Céal: Database Backend Compatibility Layer

Detects whether the active database is SQLite or PostgreSQL based on
the DATABASE_URL environment variable. All dialect-specific behavior
in database.py branches on these functions.

Interview talking point:
    "The compat layer means the entire application can switch between
    SQLite for local development and PostgreSQL for production by
    changing one environment variable. Zero code changes."
"""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def get_database_url() -> str:
    """Return the configured DATABASE_URL with sensible default."""
    return os.getenv("DATABASE_URL", "sqlite+aiosqlite:///data/ceal.db")


def is_postgres() -> bool:
    """True when the configured backend is PostgreSQL."""
    return get_database_url().startswith("postgresql")


def is_sqlite() -> bool:
    """True when the configured backend is SQLite."""
    return get_database_url().startswith("sqlite")
```

**Verification**:
```bash
python -c "from src.models.compat import is_sqlite, is_postgres, get_database_url; print(f'URL={get_database_url()}, sqlite={is_sqlite()}, pg={is_postgres()}')"
# Expected: URL=sqlite+aiosqlite:///data/ceal.db, sqlite=True, pg=False
```

---

## TASK 2: Update `src/models/database.py` (Polymorphic Engine Factory)

**Read first**: `src/models/database.py` (full file — currently ~628 lines)

This is the most complex change. You must preserve ALL existing query functions exactly as they are. The changes are ONLY to the engine creation and init_db sections.

### 2a. Replace module-level engine creation

**Current code** (lines ~53-69):
```python
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite+aiosqlite:///data/ceal.db",
)
_engine_kwargs: dict = {"echo": False}
if DATABASE_URL == "sqlite+aiosqlite://":
    _engine_kwargs["poolclass"] = StaticPool
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    _engine_kwargs["pool_pre_ping"] = True

engine = create_async_engine(DATABASE_URL, **_engine_kwargs)
```

**Replace with**:
```python
from src.models.compat import get_database_url, is_sqlite

def _create_engine():
    """Create the async engine based on DATABASE_URL backend."""
    url = get_database_url()
    kwargs: dict = {"echo": False}

    if url == "sqlite+aiosqlite://":
        # In-memory: single shared connection for test isolation
        kwargs["poolclass"] = StaticPool
        kwargs["connect_args"] = {"check_same_thread": False}
    elif is_sqlite():
        kwargs["pool_pre_ping"] = True
    else:
        # PostgreSQL — asyncpg connection pool
        kwargs["pool_pre_ping"] = True
        kwargs["pool_size"] = 5
        kwargs["max_overflow"] = 10

    return create_async_engine(url, **kwargs)

engine = _create_engine()
```

Remove the old `DATABASE_URL = os.getenv(...)` line and the old `_engine_kwargs` block.

### 2b. Guard PRAGMA listener with `is_sqlite()`

**Current code** (lines ~79-88):
```python
@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragmas(dbapi_conn, connection_record):
    ...
```

**Wrap with guard**:
```python
if is_sqlite():
    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragmas(dbapi_conn, connection_record):
        """Configure SQLite for concurrent async access."""
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=-64000")
        cursor.close()
```

Without this guard, the PRAGMAs will fire on PostgreSQL connections and crash.

### 2c. Upgrade `init_db()` to select schema file by backend

**Current code** auto-selects `schema.sql`. After modification:

```python
async def init_db(schema_path: str | None = None) -> None:
    """
    Initialize the database from the SQL schema file.
    Auto-selects schema.sql (SQLite) or schema_postgres.sql (PostgreSQL).
    Idempotent — safe to call on every startup.
    """
    if schema_path is None:
        if is_sqlite():
            schema_path = str(Path(__file__).parent / "schema.sql")
        else:
            schema_path = str(Path(__file__).parent / "schema_postgres.sql")

    schema_sql = Path(schema_path).read_text()
    statements = _split_sql_statements(schema_sql)

    if is_sqlite():
        async with get_session() as session:
            for stmt in statements:
                if stmt:
                    await session.execute(text(stmt))
    else:
        # PostgreSQL: use engine.begin() for DDL outside session manager
        async with engine.begin() as conn:
            for stmt in statements:
                if stmt:
                    await conn.execute(text(stmt))

    logger.info("database_initialized", schema=schema_path)
```

### 2d. Upgrade `_split_sql_statements()` for dollar-quoting

The PostgreSQL schema uses `$$` dollar-quoted blocks for trigger functions. Add handling:

```python
def _split_sql_statements(sql: str) -> list[str]:
    """
    Split SQL into statements, correctly handling:
    - SQLite BEGIN...END trigger blocks
    - PostgreSQL $$ dollar-quoted function bodies
    """
    statements: list[str] = []
    current: list[str] = []
    in_trigger = False
    in_dollar_quote = False

    for line in sql.split("\n"):
        stripped = line.strip()

        # Skip pure comment lines
        if stripped.startswith("--"):
            continue

        # Remove inline comments (but not inside dollar-quoted blocks)
        if "--" in stripped and not in_dollar_quote:
            stripped = stripped[: stripped.index("--")].strip()

        if not stripped:
            continue

        # Track dollar-quoted blocks (PostgreSQL function bodies)
        dollar_count = stripped.count("$$")
        if dollar_count % 2 == 1:
            in_dollar_quote = not in_dollar_quote

        # Track SQLite trigger blocks
        if stripped.upper().startswith("CREATE TRIGGER"):
            in_trigger = True

        current.append(stripped)

        if in_dollar_quote:
            # Inside a dollar-quoted block — keep accumulating
            continue

        if in_trigger:
            if stripped.upper().rstrip(";") == "END":
                in_trigger = False
                full = " ".join(current).rstrip(";")
                if full.strip():
                    statements.append(full)
                current = []
        elif stripped.endswith(";"):
            full = " ".join(current).rstrip(";")
            if full.strip():
                statements.append(full)
            current = []

    # Anything remaining
    if current:
        full = " ".join(current).rstrip(";")
        if full.strip():
            statements.append(full)

    return statements
```

### 2e. Clean up imports

Remove the now-unused direct `os` import for DATABASE_URL (compat.py handles it). Keep `os` if it's used elsewhere in the file. Add the `compat` import at the top with the other `src.` imports.

**Verification**:
```bash
python -c "from src.models.database import engine, init_db; print('Engine URL:', engine.url)"
pytest tests/unit/test_database.py -v
```

---

## TASK 3: Create `src/web/routes/health.py` + Register in `app.py`

### 3a. Create health endpoint

```python
"""
Céal: Health Check Endpoint

Returns application health status including database connectivity.
Used by Docker HEALTHCHECK, GCP Cloud Run, and load balancers.

Interview talking point:
    "The health endpoint probes actual DB connectivity with SELECT 1,
    not just 'the process is alive'. If the database connection pool
    is exhausted, the health check fails and the orchestrator restarts
    the container before users see errors."
"""
from __future__ import annotations

from fastapi import APIRouter

from src.models.database import get_session

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """
    Health check endpoint for container orchestration.
    Returns 200 with status details, or 200 with degraded status on DB failure.
    """
    db_ok = False
    db_error = None

    try:
        from sqlalchemy import text
        async with get_session() as session:
            await session.execute(text("SELECT 1"))
            db_ok = True
    except Exception as exc:
        db_error = str(exc)

    status = "healthy" if db_ok else "degraded"
    response = {
        "status": status,
        "version": "2.7.0",
        "database": "connected" if db_ok else f"error: {db_error}",
    }

    return response
```

### 3b. Register in `app.py`

Add to the router registration block in `create_app()`:
```python
    from src.web.routes import dashboard, demo, jobs, health
    app.include_router(dashboard.router)
    app.include_router(jobs.router)
    app.include_router(demo.router)
    app.include_router(health.router)
```

### 3c. Create `tests/unit/test_health.py`

```python
"""
Céal: Health Endpoint Tests

Tests the /health endpoint returns correct status and handles DB failures.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.web.app import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        """Health endpoint should return 200 even when DB is down."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "version" in data
        assert "database" in data

    def test_health_degraded_on_db_failure(self, client):
        """When DB is unreachable, status should be 'degraded'."""
        with patch("src.web.routes.health.get_session") as mock_session:
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(side_effect=ConnectionError("DB down"))
            mock_session.return_value = mock_ctx
            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "degraded"
```

**Verification**:
```bash
pytest tests/unit/test_health.py -v
```

---

## TASK 4: Create `src/models/schema_postgres.sql`

**Read first**: `src/models/schema.sql` (the SQLite version — 212 lines, 11 tables)

Create the PostgreSQL equivalent. Every table in `schema.sql` must have a counterpart. Key syntax differences:

| SQLite | PostgreSQL |
|--------|-----------|
| `INTEGER PRIMARY KEY AUTOINCREMENT` | `SERIAL PRIMARY KEY` |
| `REAL` | `DOUBLE PRECISION` |
| `TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))` | `TIMESTAMPTZ NOT NULL DEFAULT NOW()` |
| `CREATE TRIGGER ... BEGIN ... END;` | `CREATE OR REPLACE FUNCTION ... $$ ... $$ LANGUAGE plpgsql;` + `CREATE TRIGGER ...` |
| `INSERT OR IGNORE INTO` | `INSERT INTO ... ON CONFLICT DO NOTHING` |
| `BOOLEAN` (stored as 0/1) | `BOOLEAN` (native) |

**Tables to include** (all 11, in FK-dependency order):
1. `job_listings` — with `UNIQUE(external_id, source)`
2. `skills` — with `UNIQUE(name)`
3. `job_skills` — with `UNIQUE(job_id, skill_id)`, FK to job_listings + skills
4. `resume_profiles`
5. `resume_skills` — with `UNIQUE(profile_id, skill_id)`, FK to resume_profiles + skills
6. `scrape_log`
7. `company_tiers` — with `UNIQUE(company_pattern)`
8. `parsed_bullets` — with `UNIQUE(profile_id, original_text)`, FK to resume_profiles
9. `tailoring_requests` — with `UNIQUE(job_id, profile_id)`, FK to job_listings + resume_profiles
10. `tailored_bullets` — FK to tailoring_requests
11. `skill_gaps` — with `UNIQUE(request_id, skill_name)`, FK to tailoring_requests

**Also include**:
- All indexes from `schema.sql` (use `CREATE INDEX IF NOT EXISTS`)
- The `updated_at` trigger function (PostgreSQL syntax with `$$` dollar-quoting)
- All seed data (company_tiers + skills) using `INSERT INTO ... ON CONFLICT DO NOTHING`

**Verification**:
```bash
# Syntax check (requires psql or just validate the file is parseable):
python -c "
with open('src/models/schema_postgres.sql') as f:
    content = f.read()
tables = [line for line in content.split('\n') if 'CREATE TABLE' in line.upper()]
print(f'Tables found: {len(tables)}')
for t in tables:
    print(f'  {t.strip()}')
assert len(tables) == 11, f'Expected 11 tables, got {len(tables)}'
print('OK: All 11 tables present')
"
```

---

## TASK 5: Create Docker Files

### 5a. `Dockerfile`

Multi-stage build pattern:

```dockerfile
# ---------------------------------------------------------------------------
# Céal — Multi-Stage Docker Build
# ---------------------------------------------------------------------------
# Stage 1 (builder): Install build-time deps (gcc, libpq-dev for asyncpg)
# Stage 2 (runtime): Slim image with only runtime deps
#
# Resume bullet: "Designed multi-stage Docker build reducing image size by 60%
#   while supporting both SQLite (dev) and PostgreSQL (prod) backends."
# ---------------------------------------------------------------------------

# --- Stage 1: Builder ---
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies for asyncpg (needs libpq-dev + gcc)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# --- Stage 2: Runtime ---
FROM python:3.11-slim

WORKDIR /app

# Install only runtime PostgreSQL library (not dev headers)
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

# Default port
ENV PORT=8000

EXPOSE ${PORT}

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Run with uvicorn
CMD ["python", "-m", "uvicorn", "src.web.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 5b. `docker-compose.yml`

```yaml
# Céal — Docker Compose (Development)
# PostgreSQL 16 + Céal web application

services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: ceal
      POSTGRES_USER: ceal
      POSTGRES_PASSWORD: ceal_dev_only
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ceal"]
      interval: 5s
      timeout: 3s
      retries: 5

  web:
    build: .
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: "postgresql+asyncpg://ceal:ceal_dev_only@db:5432/ceal"
      PORT: "8000"
    depends_on:
      db:
        condition: service_healthy
    volumes:
      - ceal-data:/app/data

volumes:
  pgdata:
  ceal-data:
```

### 5c. `.dockerignore`

```
# Secrets
.env
*.env
!.env.example

# Database files
*.db
*.sqlite
*.sqlite3
data/*.db

# Version control
.git
.gitignore

# Python
__pycache__
*.pyc
*.pyo
*.egg-info
.eggs

# IDE
.vscode
.idea
*.swp
*.swo

# Testing
.pytest_cache
.coverage
htmlcov
.mypy_cache

# Documentation
docs/
*.md
!README.md

# Alembic (migrations run separately)
alembic/
alembic.ini

# Test mocks
tests/mocks/

# CI
.github/

# OS
.DS_Store
Thumbs.db
desktop.ini

# Deployment scripts (not needed in image)
deploy/
```

### 5d. `.env.example`

```bash
# ---------------------------------------------------------------------------
# Céal — Environment Variables
# ---------------------------------------------------------------------------
# Copy to .env and fill in values. Never commit .env to git.

# Database URL
# SQLite (local development):
DATABASE_URL=sqlite+aiosqlite:///data/ceal.db
# PostgreSQL (Docker / Cloud Run):
# DATABASE_URL=postgresql+asyncpg://ceal:password@localhost:5432/ceal

# Claude API key (for LLM ranker + tailoring engine)
LLM_API_KEY=

# Web server port
PORT=8000

# GCP deployment (Cloud Run)
GCP_PROJECT_ID=
GCP_REGION=us-east1
CLOUD_SQL_INSTANCE=
```

### 5e. `deploy/cloudrun.sh`

Create the `deploy/` directory first, then the script:

```bash
#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Céal — GCP Cloud Run Deployment
# ---------------------------------------------------------------------------
# Deploys Céal to Cloud Run with Cloud SQL PostgreSQL backend.
#
# Prerequisites:
#   - gcloud CLI authenticated
#   - Docker image built and pushed to Artifact Registry
#   - Cloud SQL instance created
#   - Secret Manager has LLM_API_KEY
#
# Usage: ./deploy/cloudrun.sh
# ---------------------------------------------------------------------------

set -euo pipefail

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
REGION="${GCP_REGION:-us-east1}"
SERVICE_NAME="ceal"
IMAGE="us-docker.pkg.dev/${PROJECT_ID}/ceal/ceal:latest"
CLOUD_SQL_INSTANCE="${CLOUD_SQL_INSTANCE:?Set CLOUD_SQL_INSTANCE}"

echo "=== Céal Cloud Run Deployment ==="
echo "Project: ${PROJECT_ID}"
echo "Region:  ${REGION}"
echo "Image:   ${IMAGE}"
echo ""

# Build and push
echo "Building Docker image..."
docker build -t "${IMAGE}" .

echo "Pushing to Artifact Registry..."
docker push "${IMAGE}"

# Deploy to Cloud Run
echo "Deploying to Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
    --image="${IMAGE}" \
    --region="${REGION}" \
    --platform=managed \
    --allow-unauthenticated \
    --port=8000 \
    --memory=512Mi \
    --cpu=1 \
    --min-instances=0 \
    --max-instances=3 \
    --set-env-vars="PORT=8000" \
    --set-secrets="LLM_API_KEY=LLM_API_KEY:latest" \
    --set-secrets="DATABASE_URL=DATABASE_URL:latest" \
    --add-cloudsql-instances="${CLOUD_SQL_INSTANCE}"

echo ""
echo "=== Deployment Complete ==="
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" \
    --region="${REGION}" --format="value(status.url)")
echo "Service URL: ${SERVICE_URL}"
echo "Health check: ${SERVICE_URL}/health"
```

Make it executable:
```bash
chmod +x deploy/cloudrun.sh
```

**Verification**:
```bash
ls Dockerfile docker-compose.yml .dockerignore .env.example deploy/cloudrun.sh
# All 5 files must exist
```

---

## TASK 6: Update `requirements.txt`

**Read first**: `requirements.txt`

Append this line (do NOT remove existing packages):
```
asyncpg==0.30.0
```

Then install:
```bash
pip install asyncpg==0.30.0
```

**Verification**:
```bash
python -c "import asyncpg; print('asyncpg version:', asyncpg.__version__)"
```

---

## TASK 7: Update `.github/workflows/ci.yml`

**Read first**: `.github/workflows/ci.yml`

Add two new jobs AFTER the existing coverage job:

### 7a. Docker build job

```yaml
  # -----------------------------------------------------------------------
  # Stage 5: Docker Build (verify image builds successfully)
  # -----------------------------------------------------------------------
  docker-build:
    name: "Docker Build"
    needs: lint
    runs-on: ubuntu-latest
    timeout-minutes: 10

    steps:
      - uses: actions/checkout@v4

      - name: Build Docker image
        run: docker build -t ceal:ci-test .

      - name: Verify image
        run: docker image inspect ceal:ci-test --format '{{.Size}}'
```

### 7b. PostgreSQL integration test job

```yaml
  # -----------------------------------------------------------------------
  # Stage 6: PostgreSQL Database Tests
  # -----------------------------------------------------------------------
  db-tests-postgres:
    name: "DB Tests (PostgreSQL)"
    needs: unit-tests
    runs-on: ubuntu-latest
    timeout-minutes: 5

    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_DB: ceal_test
          POSTGRES_USER: ceal
          POSTGRES_PASSWORD: ceal_ci
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 5s
          --health-timeout 3s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run database tests against PostgreSQL
        env:
          DATABASE_URL: "postgresql+asyncpg://ceal:ceal_ci@localhost:5432/ceal_test"
        run: pytest tests/integration/ -v --tb=short
```

**Verification**:
```bash
python -c "
import yaml
with open('.github/workflows/ci.yml') as f:
    ci = yaml.safe_load(f)
jobs = list(ci.get('jobs', {}).keys())
print('CI jobs:', jobs)
assert 'docker-build' in jobs, 'docker-build job missing!'
assert 'db-tests-postgres' in jobs, 'db-tests-postgres job missing!'
print('OK: All CI jobs present')
" 2>/dev/null || echo "PyYAML not installed — manually verify ci.yml has docker-build and db-tests-postgres jobs"
```

---

## TASK 8: Full Test Suite + Lint Verification

```bash
# Full test suite
pytest tests/ -v 2>&1

# Lint
ruff check src/ tests/

# Count tests
pytest tests/ --co -q 2>&1 | tail -3
```

**Acceptance criteria**:
- ALL tests pass (0 failures, 0 errors)
- ruff reports 0 lint errors
- Test count is >= previous baseline + 2 new health tests

---

## TASK 9: Docker Smoke Test (if Docker available)

```bash
docker compose build --no-cache 2>&1 | tail -10
docker compose up -d
sleep 5
curl -s http://localhost:8000/health | python -m json.tool
docker compose down -v
```

If Docker is not available, skip and note as manual verification.

---

## TASK 10: Commit and Tag

```bash
git add -A
git status
# Review staged files — should include:
#   new file: src/models/compat.py
#   new file: src/models/schema_postgres.sql
#   new file: src/web/routes/health.py
#   new file: tests/unit/test_health.py
#   new file: Dockerfile
#   new file: docker-compose.yml
#   new file: .dockerignore
#   new file: .env.example
#   new file: deploy/cloudrun.sh
#   modified: src/models/database.py
#   modified: src/web/app.py
#   modified: requirements.txt
#   modified: .github/workflows/ci.yml

git commit -m "feat: add Docker containerization + polymorphic Cloud SQL support

Sprint 7 reimplements Sprints 4+5 on the current main branch:

- Add compat.py: polymorphic backend detection (SQLite/PostgreSQL)
- Add schema_postgres.sql: full PostgreSQL DDL for all 11 tables
- Update database.py: engine factory, PRAGMA guard, dual-schema init_db
- Add health endpoint: GET /health with DB connectivity probe
- Add Dockerfile: multi-stage build (builder + slim runtime)
- Add docker-compose.yml: PostgreSQL 16 + web service
- Add deploy/cloudrun.sh: GCP Cloud Run deployment script
- Update CI: docker-build + db-tests-postgres jobs
- Add asyncpg to requirements"

git tag -a v2.7.0-sprint7-docker-cloudsql -m "Sprint 7: Docker + Cloud SQL reimplementation"
git push origin main --tags
```

---

## COMPLETION CHECKLIST

Before declaring this sprint complete, verify ALL of the following:

- [ ] `src/models/compat.py` — `is_sqlite()` returns True locally, `is_postgres()` returns False
- [ ] `src/models/database.py` — Uses `_create_engine()` factory, PRAGMA guarded by `is_sqlite()`
- [ ] `src/models/schema_postgres.sql` — Contains all 11 tables with PostgreSQL syntax
- [ ] `src/web/routes/health.py` — `GET /health` returns status + version + DB probe
- [ ] `src/web/app.py` — Health router registered (4 routers total: dashboard, jobs, demo, health)
- [ ] `Dockerfile` — Multi-stage build, non-root user, HEALTHCHECK
- [ ] `docker-compose.yml` — PostgreSQL 16 + web service with health checks
- [ ] `.dockerignore` — Excludes secrets, DB files, and non-essential files
- [ ] `.env.example` — Documents DATABASE_URL, LLM_API_KEY, PORT, GCP vars
- [ ] `deploy/cloudrun.sh` — Executable, references correct GCP vars
- [ ] `requirements.txt` — Includes `asyncpg`
- [ ] `.github/workflows/ci.yml` — Has `docker-build` and `db-tests-postgres` jobs
- [ ] `pytest tests/ -v` — ALL tests pass, 0 failures
- [ ] `ruff check src/ tests/` — 0 errors
- [ ] Committed and tagged on `main`
- [ ] Pushed to `origin/main`

If any check fails, fix it before proceeding. Do NOT leave known failures.
