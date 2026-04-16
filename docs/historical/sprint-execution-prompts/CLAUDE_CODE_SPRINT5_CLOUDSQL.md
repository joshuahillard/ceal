# Céal Sprint 5 — Cloud SQL (PostgreSQL) Migration

## CONTEXT
You are working on the Céal project — an AI-powered career signal engine.
The project root is the `ceal/` directory containing `src/`, `tests/`, `pyproject.toml`, `requirements.txt`.

**Branch state**: You are on `main`. This branch contains:
- Phase 1 (scrape → normalize → rank pipeline)
- Phase 2 + 2B (resume tailoring, demo mode, batch, export, persistence)
- Sprint 1 (FastAPI + Jinja2 web UI: Dashboard, Jobs, Demo)
- Sprint 2 (Phase 3 CRM: Kanban board, state-machine status transitions, stale reminders, prompt v1.1)
- Sprint 3 (Phase 4 Auto-Apply: pre-fill engine, approval queue, confidence scoring, CRM sync)
- Sprint 4 (Docker: multi-stage Dockerfile, docker-compose.yml, GCP Cloud Run deployment, health endpoint)
- Jobs tab permanent fix (LEFT JOIN exclusion for submitted applications, database-level tests)
- **208 passing tests**, ruff clean, CI green (7-job matrix: lint, unit 3.11/3.12, integration 3.11/3.12, coverage ≥80%, docker-build)

**PRE-FLIGHT CHECK**: Before starting any work, run these commands in order:

```bash
# 1. Verify working directory
pwd
# Must be inside the ceal/ project root

# 2. Verify branch and commit
git log --oneline -5
# Expect HEAD on main, most recent commits should include the docker and jobs tab fix commits

# 3. Check for uncommitted changes
git status
# If any modified files exist, read the diffs and decide:
#   - If they are legitimate additions, commit them with a descriptive message
#   - If they are unexpected, STOP and report
# If clean, proceed.

# 4. Verify all tests pass
pytest tests/ -v
# Expect 208 passing. If any fail, STOP and fix them before proceeding.

# 5. Verify lint
ruff check src/ tests/
# Expect 0 errors

# 6. Verify file structure — core infrastructure
ls src/web/app.py src/web/routes/dashboard.py src/web/routes/jobs.py src/web/routes/demo.py src/web/routes/applications.py src/web/routes/apply.py src/web/routes/health.py
ls src/web/templates/base.html src/web/templates/dashboard.html src/web/templates/jobs.html src/web/templates/demo.html src/web/templates/applications.html src/web/templates/reminders.html src/web/templates/approval_queue.html src/web/templates/application_review.html
ls src/models/database.py src/models/entities.py src/models/schema.sql
ls src/tailoring/engine.py src/tailoring/models.py src/tailoring/db_models.py src/tailoring/resume_parser.py src/tailoring/skill_extractor.py src/tailoring/persistence.py
ls src/apply/prefill.py
ls src/demo.py src/fetcher.py src/batch.py src/export.py
ls src/main.py pyproject.toml requirements.txt
ls data/resume.txt
ls tests/unit/test_web.py tests/unit/test_crm.py tests/unit/test_autoapply.py tests/unit/test_database.py tests/unit/test_tailoring_engine.py tests/unit/test_health.py
ls .github/workflows/ci.yml
ls Dockerfile docker-compose.yml .dockerignore .env.example deploy/cloudrun.sh

# 7. Verify Docker files exist (Sprint 4 deliverables)
# If Dockerfile is missing, STOP — Sprint 4 was not completed.

# 8. Verify these files do NOT exist yet (Sprint 5 creates them):
ls src/models/compat.py 2>/dev/null && echo "WARNING: compat.py already exists" || echo "OK: compat.py does not exist yet"
```
If ANY pre-flight check fails (steps 1-7), STOP and report what failed. Do NOT proceed.

**Your job**: Migrate Céal from SQLite-only to a polymorphic database layer that supports both SQLite (local development, tests) and PostgreSQL (Cloud Run production via Cloud SQL). The migration must:
1. Keep SQLite working for local dev and the existing test suite
2. Add PostgreSQL support via `asyncpg` for production
3. Update docker-compose.yml to include a PostgreSQL service
4. Update CI to test against both backends
5. Write database-level tests for all core query functions

---

## CRITICAL RULES (Anti-Hallucination)

1. **READ before WRITE**: Before modifying ANY file, read it first. Never assume file contents.
2. **EXISTING FILES — DO NOT DUPLICATE OR RENAME**:
   - `src/models/database.py` — contains: `get_session()`, `init_db()`, `upsert_job()`, `upsert_jobs_batch()`, `get_unranked_jobs()`, `update_job_ranking()`, `assign_company_tiers()`, `get_top_matches()`, `log_scrape_run()`, `create_resume_profile()`, `link_resume_skill()`, `get_pipeline_stats()`, `VALID_TRANSITIONS` dict, `update_job_status()`, `get_jobs_by_status()`, `get_application_summary()`, `get_stale_applications()`, `_APP_VALID_TRANSITIONS` dict, `create_application()`, `get_application()`, `get_approval_queue()`, `update_application_status()`, `get_application_stats()`
   - `src/models/entities.py` — contains: `JobStatus` enum (8 states), `JobSource`, `RemoteType`, `SkillCategory`, `Proficiency` enums, `ApplicationStatus` enum (5 states: DRAFT, READY, APPROVED, SUBMITTED, WITHDRAWN), `FieldType`, `FieldSource` enums, plus all Pydantic models
   - `src/models/schema.sql` — 9 tables: `job_listings`, `skills`, `job_skills`, `resume_profiles`, `resume_skills`, `company_tiers`, `scrape_log`, `applications`, `application_fields`. Uses `CREATE TABLE IF NOT EXISTS` with SQLite-specific syntax (`AUTOINCREMENT`, `datetime('now')` defaults, SQLite triggers).
   - `src/web/app.py` — FastAPI app factory `create_app()` with lifespan calling `init_db()`. Registers 6 routers: dashboard, jobs, applications, apply, demo, health.
   - `src/web/routes/health.py` — `GET /health` with DB connectivity check via `get_session()` + `SELECT 1`
   - `src/web/routes/dashboard.py` — `GET /` wired to `get_pipeline_stats()`, `get_application_summary()`, `get_stale_applications()`, `get_application_stats()`
   - `src/web/routes/jobs.py` — `GET /jobs` wired to `get_top_matches()` with tier/score/limit params. Uses `LEFT JOIN applications` to exclude submitted jobs.
   - `src/web/routes/applications.py` — `GET /applications` (Kanban), `POST /applications/{job_id}/status`, `GET /applications/reminders`
   - `src/web/routes/apply.py` — `GET /apply` (approval queue), `POST /apply/prefill/{job_id}`, `GET /apply/{app_id}`, `POST /apply/{app_id}/status`
   - `src/web/routes/demo.py` — `GET /demo`, `POST /demo` wired to full tailoring pipeline
   - `src/apply/prefill.py` — `PreFillEngine` class
   - `src/tailoring/engine.py` — `TailoringEngine`, `CURRENT_PROMPT_VERSION = "v1.1"`
   - `src/tailoring/db_models.py` — SQLAlchemy ORM: `Base`, `PHASE1_STUB_TABLES`, `_utcnow()`. Alembic uses `render_as_batch=True` (SQLite-specific).
   - `src/main.py` — CLI entry with all flags including `--web`, `--port`
   - `Dockerfile` — Multi-stage build, python:3.11-slim, non-root user, HEALTHCHECK
   - `docker-compose.yml` — Single `web` service with `ceal-data` volume
   - `deploy/cloudrun.sh` — GCP deployment script with `--set-secrets` for LLM_API_KEY
   - `.env.example` — Documents `LLM_API_KEY`, `DATABASE_URL`, `PORT`, `GCP_PROJECT_ID`
   - `data/resume.txt` — Josh's resume in parser-compatible format
3. **IMPORT PATHS**: All imports use `src.` prefix (e.g., `from src.models.database import get_pipeline_stats`). The project uses `pythonpath = ["."]` in pyproject.toml.
4. **PYTHON VERSION**: Target Python 3.10+. Do NOT use `datetime.UTC` (use `datetime.timezone.utc`). Do NOT use `StrEnum` (use `str, Enum`).
5. **ASYNC**: The entire codebase is async. Database uses `AsyncSession`. All database functions are `async def`. FastAPI routes must be `async def`.
6. **DATABASE**: Currently SQLite via `sqlite+aiosqlite:///data/ceal.db`. After Sprint 5, the DATABASE_URL determines the backend: `sqlite+aiosqlite://` for local, `postgresql+asyncpg://` for production.
7. **RUFF CONFIG**: `target-version = "py310"`, `line-length = 120`. Ignored rules: `UP017`, `UP042`, `E501`, `SIM102`, `SIM105`, `SIM108`, `B017`, `B904`.
8. **TESTS**: `pytest` with `asyncio_mode = "strict"`. All async tests need `@pytest.mark.asyncio`. Test isolation uses StaticPool in-memory SQLite. Web route tests MUST mock all database functions.
9. **NO SECRETS — ZERO TOLERANCE**: Never hardcode credentials in any committed file.
10. **WEB PATTERNS**: Follow existing patterns exactly.
11. **NO FABRICATED INFRASTRUCTURE**: Do NOT reference asyncpg features, PostgreSQL extensions, or GCP services you are not certain exist. Use standard SQLAlchemy async patterns only.
12. **DATA LEAKAGE PREVENTION**: No secrets or database files in Docker images.
13. **NO DIALECT-SPECIFIC SQL**: All raw SQL in `database.py` must work on BOTH SQLite and PostgreSQL, OR must be behind a backend-detection branch in `src/models/compat.py`. Do NOT write SQLite-only SQL (`datetime('now')`, `AUTOINCREMENT`) into functions that will run on PostgreSQL. Do NOT write PostgreSQL-only SQL (`NOW()`, `SERIAL`, `::text` casts) into functions that will run on SQLite.
14. **DUAL-BACKEND TESTING**: For any database function that contains raw SQL and drives a core UI view, write a database-level test that exercises the real SQL against an in-memory database — not just a mock. Route-level mocks are acceptable for HTTP contract testing but do NOT replace SQL correctness tests. This rule exists because the Jobs tab broke THREE TIMES due to mock-only tests hiding SQL bugs.

---

## TASK 0: Pre-Requisite Verification

### 0a. Verify clean state

```bash
git status
pytest tests/ -v 2>&1 | tail -5
ruff check src/ tests/
```

All must pass. If there are uncommitted changes, read the diffs and commit if they are legitimate. If tests fail, fix them first.

### 0b. Read all files that will be modified

Before proceeding to Task 1, read these files IN FULL:
- `src/models/database.py`
- `src/models/schema.sql`
- `src/tailoring/db_models.py`
- `alembic/env.py`
- `docker-compose.yml`
- `.github/workflows/ci.yml`
- `.env.example`
- `Dockerfile`
- `deploy/cloudrun.sh`
- `requirements.txt`

This is not optional. You MUST read all 10 files before writing any code.

---

## TASK 1: Add PostgreSQL Dependencies — `requirements.txt`

**Read first**: `requirements.txt`

Append these packages (do NOT remove existing packages):
```
asyncpg==0.30.0
psycopg2-binary==2.9.10
```

Note: `asyncpg` is the async PostgreSQL driver for SQLAlchemy. `psycopg2-binary` is needed by Alembic for sync migrations.

Then run:
```bash
pip install asyncpg psycopg2-binary
```

**Verification**: `python -c "import asyncpg; print(asyncpg.__version__)"`

---

## TASK 2: Create Database Compatibility Layer — `src/models/compat.py`

**Create new file**: `src/models/compat.py`

This module detects the database backend and provides dialect-aware helpers.

```python
"""
Database compatibility layer for SQLite ↔ PostgreSQL.

Céal supports both SQLite (local dev, tests) and PostgreSQL (Cloud Run production).
This module centralizes dialect detection and provides helpers for the few places
where raw SQL differs between backends.

Interview point: "I built a polymorphic database layer that lets the same codebase
run on SQLite for development and PostgreSQL for production — zero code changes
between environments, controlled entirely by DATABASE_URL."
"""

import os

# ---------------------------------------------------------------------------
# Backend detection
# ---------------------------------------------------------------------------

def get_database_url() -> str:
    """Return the configured DATABASE_URL, defaulting to local SQLite."""
    return os.environ.get(
        "DATABASE_URL",
        "sqlite+aiosqlite:///data/ceal.db",
    )


def is_postgres(url: str | None = None) -> bool:
    """Check if the database URL points to PostgreSQL."""
    db_url = url or get_database_url()
    return db_url.startswith("postgresql")


def is_sqlite(url: str | None = None) -> bool:
    """Check if the database URL points to SQLite."""
    db_url = url or get_database_url()
    return db_url.startswith("sqlite")


# ---------------------------------------------------------------------------
# Dialect-aware SQL helpers
# ---------------------------------------------------------------------------

def now_expression() -> str:
    """
    Return the SQL expression for 'current timestamp' appropriate to the backend.

    SQLite:     datetime('now')
    PostgreSQL: NOW()
    """
    if is_postgres():
        return "NOW()"
    return "datetime('now')"


def auto_id_column() -> str:
    """
    Return the primary key column definition appropriate to the backend.

    SQLite:     INTEGER PRIMARY KEY AUTOINCREMENT
    PostgreSQL: SERIAL PRIMARY KEY
    """
    if is_postgres():
        return "SERIAL PRIMARY KEY"
    return "INTEGER PRIMARY KEY AUTOINCREMENT"


def boolean_true() -> str:
    """SQLite uses 1, PostgreSQL uses TRUE."""
    if is_postgres():
        return "TRUE"
    return "1"


def boolean_false() -> str:
    """SQLite uses 0, PostgreSQL uses FALSE."""
    if is_postgres():
        return "FALSE"
    return "0"
```

**Verification**: `python -c "from src.models.compat import is_sqlite, is_postgres; print('sqlite:', is_sqlite()); print('postgres:', is_postgres())"`

---

## TASK 3: Refactor Database Engine Configuration — `src/models/database.py`

**Read first**: `src/models/database.py` — read the ENTIRE file.

This is the most critical task. The goal is to make the engine creation polymorphic based on `DATABASE_URL`, while keeping every existing function signature and behavior identical.

### 3a. Replace the hardcoded engine with a factory

Find the existing engine creation code (near the top of the file). It currently looks something like:
```python
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///data/ceal.db")
engine = create_async_engine(DATABASE_URL, ...)
```

Replace with:

```python
from src.models.compat import get_database_url, is_sqlite

def _create_engine():
    """
    Create the async database engine based on DATABASE_URL.

    SQLite: Uses StaticPool for tests, check_same_thread=False for async.
    PostgreSQL: Standard async pool with asyncpg driver.

    Interview point: "The engine factory detects the backend from an
    environment variable — same codebase runs SQLite locally and
    PostgreSQL in production with zero code changes."
    """
    url = get_database_url()

    if is_sqlite(url):
        connect_args = {"check_same_thread": False}
        return create_async_engine(
            url,
            connect_args=connect_args,
            echo=False,
        )
    else:
        # PostgreSQL via asyncpg
        return create_async_engine(
            url,
            echo=False,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
        )


engine = _create_engine()
```

### 3b. Update the SQLite PRAGMA listener

The existing `@event.listens_for(engine.sync_engine, "connect")` handler sets SQLite PRAGMAs (WAL, foreign_keys, busy_timeout, etc.). This handler MUST only run on SQLite — PostgreSQL does not support PRAGMAs.

Wrap it:

```python
from src.models.compat import is_sqlite

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

### 3c. Update `init_db()` to be backend-aware

The current `init_db()` reads `schema.sql` and executes it. The SQL in `schema.sql` uses SQLite-specific syntax. We need to:

1. On SQLite: execute `schema.sql` as-is (current behavior)
2. On PostgreSQL: execute a PostgreSQL-compatible version

Find `init_db()` and update it:

```python
async def init_db():
    """Initialize the database schema."""
    if is_sqlite():
        schema_path = Path(__file__).parent / "schema.sql"
        schema_sql = schema_path.read_text()
        async with engine.begin() as conn:
            await conn.execute(text(schema_sql))
        logger.info("database_initialized", schema=str(schema_path))
    else:
        schema_path = Path(__file__).parent / "schema_postgres.sql"
        schema_sql = schema_path.read_text()
        async with engine.begin() as conn:
            # PostgreSQL executes each statement separately
            for statement in schema_sql.split(";"):
                statement = statement.strip()
                if statement:
                    await conn.execute(text(statement))
        logger.info("database_initialized", schema=str(schema_path), backend="postgresql")
```

### 3d. Audit ALL raw SQL in database.py

Read every function in `database.py`. For each function that uses `text(""" ... """)`:
- Check if the SQL uses any SQLite-specific syntax
- If it does, refactor to use dialect-neutral SQL OR add a backend branch

Common patterns that need attention:
- `datetime('now')` → use the `now_expression()` helper from compat.py, OR use Python-side timestamps
- `INSERT ... ON CONFLICT ... DO UPDATE` → this works in BOTH SQLite (3.24+) and PostgreSQL. **No change needed.**
- `RETURNING id` → works in BOTH SQLite (3.35+) and PostgreSQL. **No change needed.**
- `GROUP BY` / `ORDER BY` / `LEFT JOIN` → standard SQL, works in both. **No change needed.**

The safest approach for datetime: instead of relying on database-side `datetime('now')`, pass Python-generated timestamps as parameters. This eliminates dialect differences entirely:

```python
from datetime import datetime, timezone

# Instead of: datetime('now') in SQL
# Use: datetime.now(timezone.utc).isoformat() as a parameter
```

**IMPORTANT**: Do NOT change any function signatures. Do NOT rename any functions. Do NOT change return types. Every existing caller must continue to work unchanged.

---

## TASK 4: Create PostgreSQL Schema — `src/models/schema_postgres.sql`

**Read first**: `src/models/schema.sql` — read the ENTIRE file.

Create a PostgreSQL-compatible version. The key translations:

| SQLite | PostgreSQL |
|--------|-----------|
| `INTEGER PRIMARY KEY AUTOINCREMENT` | `SERIAL PRIMARY KEY` |
| `TEXT NOT NULL DEFAULT (datetime('now'))` | `TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()` |
| `REAL` | `DOUBLE PRECISION` |
| `CREATE TRIGGER ... BEGIN ... END;` | `CREATE OR REPLACE FUNCTION ... CREATE TRIGGER ...` |

**Create new file**: `src/models/schema_postgres.sql`

Translate every table, index, trigger, and seed data statement from `schema.sql` into PostgreSQL-compatible DDL. Keep the same table names, column names, and constraint names. Use `CREATE TABLE IF NOT EXISTS` (works in both dialects).

Key rules for the translation:
- `AUTOINCREMENT` → `SERIAL` (or `GENERATED ALWAYS AS IDENTITY`)
- `datetime('now')` → `NOW()`
- `REAL` → `DOUBLE PRECISION`
- SQLite triggers use `BEGIN...END;` block syntax → PostgreSQL uses `CREATE FUNCTION` + `CREATE TRIGGER`
- `CHECK(status IN (...))` → works in both, no change needed
- `INSERT OR IGNORE` → `INSERT ... ON CONFLICT DO NOTHING`
- `UNIQUE(...)` constraints → same in both

**IMPORTANT**: Include all 9 tables, all indexes, all triggers, and all seed data (company_tiers, skills). The PostgreSQL schema must produce an identical logical database to the SQLite schema.

**Verification**: The file should be roughly the same length as `schema.sql` plus the function definitions for triggers.

---

## TASK 5: Update Alembic Configuration — `alembic/env.py`

**Read first**: `alembic/env.py` — read the ENTIRE file.

The current config uses `render_as_batch=True` which is SQLite-specific (batch mode recreates tables to work around SQLite's limited ALTER TABLE). On PostgreSQL, this is unnecessary and can cause issues.

Update the `run_migrations_online()` function to detect the backend:

```python
from src.models.compat import is_sqlite

# In run_migrations_online():
context.configure(
    connection=connection,
    target_metadata=target_metadata,
    render_as_batch=is_sqlite(),  # Only use batch mode on SQLite
    include_object=include_object,
)
```

**Verification**: `ruff check alembic/`

---

## TASK 6: Update `docker-compose.yml` — Add PostgreSQL Service

**Read first**: `docker-compose.yml`

Replace the entire file with:

```yaml
# Céal — Local development with Docker
# Usage: docker compose up --build
# Web UI: http://localhost:8000
# PostgreSQL: localhost:5432

services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: ceal
      POSTGRES_PASSWORD: ceal_dev
      POSTGRES_DB: ceal
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
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "${PORT:-8000}:8000"
    environment:
      - LLM_API_KEY=${LLM_API_KEY}
      - DATABASE_URL=postgresql+asyncpg://ceal:ceal_dev@db:5432/ceal
      - PYTHONPATH=.
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped

volumes:
  pgdata:
    driver: local
```

**Key decisions:**
- `postgres:16-alpine` — small image, latest stable PostgreSQL
- Health check ensures web doesn't start before DB is ready
- `depends_on: condition: service_healthy` prevents race conditions
- Password `ceal_dev` is for local dev only — production uses Cloud SQL IAM auth or Secret Manager
- Old `ceal-data` SQLite volume removed — PostgreSQL has its own volume

---

## TASK 7: Update Dockerfile — Add asyncpg build dependencies

**Read first**: `Dockerfile`

The builder stage needs `libpq-dev` for `psycopg2-binary` compilation. Update the builder stage's `apt-get` line:

Find:
```dockerfile
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*
```

Replace with:
```dockerfile
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*
```

Also add `libpq5` to the runtime stage (needed by asyncpg at runtime). Add this line BEFORE the `COPY --from=builder` line:

```dockerfile
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 && \
    rm -rf /var/lib/apt/lists/*
```

---

## TASK 8: Update `.env.example`

**Read first**: `.env.example`

Update the DATABASE_URL documentation:

```bash
# Céal — Environment Variables
# Copy this file to .env and fill in your values:
#   cp .env.example .env

# Anthropic API key for Claude (used by ranker and tailoring engine)
# Get yours at: https://console.anthropic.com/
LLM_API_KEY=

# Database URL
# Local SQLite (default):
DATABASE_URL=sqlite+aiosqlite:///data/ceal.db
# Docker Compose PostgreSQL:
# DATABASE_URL=postgresql+asyncpg://ceal:ceal_dev@localhost:5432/ceal
# Cloud SQL (production):
# DATABASE_URL=postgresql+asyncpg://user:pass@/ceal?host=/cloudsql/PROJECT:REGION:INSTANCE

# Web server port (Cloud Run sets this automatically)
PORT=8000

# GCP Project ID (for deployment only)
GCP_PROJECT_ID=
```

---

## TASK 9: Update `deploy/cloudrun.sh` — Cloud SQL Integration

**Read first**: `deploy/cloudrun.sh`

Update the `gcloud run deploy` command to add Cloud SQL connection:

Find the existing `gcloud run deploy` block and add these flags:

```bash
    --add-cloudsql-instances "${GCP_PROJECT_ID}:${REGION}:ceal-db" \
    --set-env-vars "DATABASE_URL=postgresql+asyncpg://ceal@/ceal?host=/cloudsql/${GCP_PROJECT_ID}:${REGION}:ceal-db,PYTHONPATH=." \
```

Also add setup instructions in the comment block at the top:

```bash
#   - Cloud SQL instance created:
#     gcloud sql instances create ceal-db --database-version=POSTGRES_16 --tier=db-f1-micro --region=us-east1
#   - Database created:
#     gcloud sql databases create ceal --instance=ceal-db
#   - User created:
#     gcloud sql users create ceal --instance=ceal-db --password=YOUR_PASSWORD
```

---

## TASK 10: Update CI/CD Pipeline — Add PostgreSQL Test Matrix

**Read first**: `.github/workflows/ci.yml` — read the ENTIRE file.

### 10a. Add PostgreSQL service to integration test jobs

Find the existing `integration` job. Add a `services` block:

```yaml
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: ceal
          POSTGRES_PASSWORD: ceal_ci
          POSTGRES_DB: ceal_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 5s
          --health-timeout 3s
          --health-retries 5
```

### 10b. Add a PostgreSQL integration test step

After the existing integration test step, add:

```yaml
      - name: Integration tests (PostgreSQL)
        env:
          DATABASE_URL: postgresql+asyncpg://ceal:ceal_ci@localhost:5432/ceal_test
        run: |
          python -m pytest tests/integration/ -v --tb=short
```

### 10c. Add a dual-backend database test job

Add a new job that runs the database-level tests against PostgreSQL:

```yaml
  db-tests-postgres:
    name: Database Tests (PostgreSQL)
    runs-on: ubuntu-latest
    needs: [lint]
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: ceal
          POSTGRES_PASSWORD: ceal_ci
          POSTGRES_DB: ceal_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 5s
          --health-timeout 3s
          --health-retries 5
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run database tests against PostgreSQL
        env:
          DATABASE_URL: postgresql+asyncpg://ceal:ceal_ci@localhost:5432/ceal_test
        run: |
          python -m pytest tests/unit/test_database.py tests/unit/test_crm.py tests/unit/test_autoapply.py -v --tb=short
```

---

## TASK 11: Write Database-Level Tests for Core Query Functions

**Read first**: `tests/unit/test_database.py` — read the ENTIRE file.

This task addresses the testing blind spot that caused the Jobs tab to break three times. Add a new test class that exercises the actual SQL in core query functions against a real (in-memory) database.

### 11a. Add tests to `tests/unit/test_database.py`

Add a new test class after the existing classes:

```python
class TestCoreQuerySQL:
    """
    Database-level tests for core query functions.

    These tests exercise REAL SQL against a database — not mocks.
    They exist because mock-only route tests hid SQL bugs in
    get_top_matches() THREE TIMES (Sprints 1, 2, and post-Sprint 4).

    Rule 14: "For any database function that contains raw SQL and
    drives a core UI view, write a database-level test that exercises
    the real SQL against an in-memory database."
    """

    @pytest.fixture(autouse=True)
    async def setup_db(self):
        """Initialize schema and seed test data."""
        await init_db()
        # Seed test jobs with different statuses
        # ... (use upsert_jobs_batch with varied statuses, scores, tiers)
        yield
        # Teardown handled by StaticPool

    @pytest.mark.asyncio
    async def test_get_top_matches_only_returns_scraped_and_ranked(self):
        """Jobs with status applied/interviewing/offer/rejected/archived must NOT appear."""
        # Insert jobs with every status
        # Call get_top_matches()
        # Assert only scraped and ranked jobs are returned

    @pytest.mark.asyncio
    async def test_get_top_matches_excludes_jobs_with_submitted_applications(self):
        """Jobs with a submitted application must be filtered by LEFT JOIN."""
        # Insert a ranked job
        # Create an application with status 'submitted' for that job
        # Call get_top_matches()
        # Assert the job is excluded

    @pytest.mark.asyncio
    async def test_get_top_matches_includes_jobs_with_draft_applications(self):
        """Jobs with draft (non-submitted) applications should still appear."""
        # Insert a ranked job
        # Create an application with status 'draft'
        # Call get_top_matches()
        # Assert the job IS included

    @pytest.mark.asyncio
    async def test_get_top_matches_respects_min_score_filter(self):
        """min_score=0.5 should exclude jobs with score < 0.5 but include unscored."""
        # Insert jobs with scores 0.3, 0.7, 0.9, and one with NULL score
        # Call get_top_matches(min_score=0.5)
        # Assert: 0.7 and 0.9 returned. 0.3 excluded. NULL-score job included (unranked).

    @pytest.mark.asyncio
    async def test_get_top_matches_orders_by_score_desc_nulls_last(self):
        """Ranked jobs sort to top by score; unranked sort to bottom."""
        # Insert ranked (0.9, 0.5) and unranked (NULL score) jobs
        # Call get_top_matches(min_score=0.0)
        # Assert order: 0.9, 0.5, NULL

    @pytest.mark.asyncio
    async def test_get_pipeline_stats_returns_expected_keys(self):
        """Pipeline stats must include all expected keys."""
        stats = await get_pipeline_stats()
        assert "total_jobs" in stats
        assert "ranked_jobs" in stats
        assert "latest_scrape" in stats

    @pytest.mark.asyncio
    async def test_get_jobs_by_status_filters_correctly(self):
        """get_jobs_by_status('ranked') should only return ranked jobs."""
        # Insert jobs with mixed statuses
        # Call get_jobs_by_status('ranked')
        # Assert only ranked jobs returned

    @pytest.mark.asyncio
    async def test_get_approval_queue_returns_correct_structure(self):
        """Approval queue should return applications with joined job data."""
        # Insert a job, create an application
        # Call get_approval_queue()
        # Assert applications have job_title, company_name fields populated
```

**IMPORTANT**: These are SKELETON tests. You must implement them fully with real database operations (upsert_job, update_job_ranking, create_application, etc.). Use the existing test patterns in the file for setup/teardown. Every assertion must be meaningful — no `assert True`.

---

## TASK 12: Update README.md

**Read first**: `README.md` — read the ENTIRE file.

Update the following sections:

### 12a. Update Tech Stack table

Add `asyncpg` and `PostgreSQL` entries.

### 12b. Update Database section

Document the polymorphic database layer:

```markdown
## Database

Céal supports two database backends:

| Backend | Use Case | Driver | URL Pattern |
|---------|----------|--------|-------------|
| SQLite | Local dev, tests | aiosqlite | `sqlite+aiosqlite:///data/ceal.db` |
| PostgreSQL | Cloud Run, production | asyncpg | `postgresql+asyncpg://user:pass@host/db` |

The backend is selected automatically from `DATABASE_URL`. Local development defaults to SQLite.
```

### 12c. Update Docker section

Update the docker-compose instructions to note that it now starts PostgreSQL:

```markdown
## Docker

### Local Development (with PostgreSQL)

```bash
docker compose up --build
# Starts PostgreSQL + Céal web app
# Web UI: http://localhost:8000
# PostgreSQL: localhost:5432
```
```

### 12d. Update test count to reflect Sprint 5 additions.

---

## TASK 13: Lint, Test, Commit, and Verify

### 13a. Lint

```bash
ruff check src/ tests/
# Fix any errors
```

### 13b. Run full test suite (SQLite)

```bash
pytest tests/ -v
# Expect: 215+ passing
```

### 13c. Run PostgreSQL tests (if Docker/PostgreSQL available)

```bash
# Start PostgreSQL
docker compose up -d db
# Wait for healthy
sleep 5
# Run database tests against PostgreSQL
DATABASE_URL=postgresql+asyncpg://ceal:ceal_dev@localhost:5432/ceal pytest tests/unit/test_database.py -v
# Teardown
docker compose down
```

If Docker is not available, skip — CI will validate.

### 13d. Commit

```bash
git add requirements.txt
git add src/models/compat.py src/models/database.py src/models/schema_postgres.sql
git add alembic/env.py
git add docker-compose.yml Dockerfile .env.example deploy/cloudrun.sh
git add .github/workflows/ci.yml
git add tests/unit/test_database.py
git add README.md
git commit -m "feat(db): add polymorphic database layer — SQLite + PostgreSQL via Cloud SQL

- src/models/compat.py: Backend detection + dialect-aware SQL helpers
- Database engine factory in database.py: SQLite (local) ↔ PostgreSQL (Cloud Run)
- schema_postgres.sql: Full PostgreSQL-compatible DDL (9 tables, indexes, triggers, seeds)
- docker-compose.yml: PostgreSQL 16 service with health checks
- Dockerfile: Added libpq for asyncpg runtime support
- CI: PostgreSQL service container + dual-backend test matrix
- Database-level tests for all core query functions (closes Jobs tab blind spot)
- Alembic: render_as_batch only on SQLite
- deploy/cloudrun.sh: Cloud SQL instance connection flags
- 215+ tests passing across both backends"
```

### 13e. Tag

```bash
git tag -a v2.5.0-sprint5-cloudsql -m "Sprint 5: Polymorphic database layer — SQLite + PostgreSQL Cloud SQL. 215+ tests."
```

### 13f. Push

```bash
git push origin main
git push origin v2.5.0-sprint5-cloudsql
```

---

## VERIFICATION CHECKLIST (Run after all tasks)

- [ ] `git status` shows clean working tree
- [ ] `pytest tests/ -v` shows 215+ passing
- [ ] `ruff check src/ tests/` shows 0 errors
- [ ] `src/models/compat.py` exists with `is_sqlite()`, `is_postgres()`, `get_database_url()`
- [ ] `src/models/schema_postgres.sql` exists with all 9 tables
- [ ] `src/models/database.py` has `_create_engine()` factory, PRAGMA listener wrapped in `if is_sqlite()`
- [ ] `docker-compose.yml` has `db` (postgres:16-alpine) and `web` services
- [ ] `Dockerfile` has `libpq-dev` in builder and `libpq5` in runtime
- [ ] `.github/workflows/ci.yml` has `db-tests-postgres` job with PostgreSQL service
- [ ] `alembic/env.py` uses `render_as_batch=is_sqlite()`
- [ ] `tests/unit/test_database.py` has `TestCoreQuerySQL` class with 8+ tests
- [ ] `deploy/cloudrun.sh` has `--add-cloudsql-instances` flag
- [ ] `.env.example` documents both SQLite and PostgreSQL URL patterns
- [ ] `README.md` documents the polymorphic database layer
- [ ] No SQLite-specific SQL (`datetime('now')`, `AUTOINCREMENT`) in `database.py` functions
- [ ] No hardcoded passwords in any file except docker-compose.yml (local dev only)
- [ ] `git log --oneline -3` shows Sprint 5 commit
- [ ] `git tag -l` includes `v2.5.0-sprint5-cloudsql`
