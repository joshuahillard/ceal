# Céal Sprint 6 — Gap-Fill + Docker + Cloud SQL

## CONTEXT

You are working on the Céal project — an AI-powered career signal engine.
The project root is the `ceal/` directory containing `src/`, `tests/`, `pyproject.toml`, `requirements.txt`.

**What happened**: When we reset `main` to the `codex/semantic-fidelity-guardrail` branch, the Sprint 4 (Docker containerization) and Sprint 5 (Cloud SQL polymorphic DB) implementations were lost. This sprint reimplements them while also fixing known schema issues on the current `main`.

**Current `main` contains**:
- Phase 1 (scrape → normalize → rank pipeline)
- Phase 2 + 2B (resume tailoring engine, demo mode, batch, .docx export, persistence)
- Sprint 1 (FastAPI + Jinja2 web UI: Dashboard, Jobs, Demo — 3 routers)
- Semantic-fidelity guardrail (v1.1): rejects hallucinated metrics, semantic drift, phantom bullets

**Current `main` does NOT contain** (and this sprint does NOT add):
- Sprint 2 (CRM: applications/reminders routes, Kanban, state machine) — separate future sprint
- Sprint 3 (Auto-Apply: prefill engine, approval queue) — separate future sprint

**This sprint's scope**: Fix known schema bugs + Docker containerization + polymorphic SQLite/PostgreSQL database layer.

---

## KNOWN ISSUES (Part A of this sprint fixes these)

### ISSUE 1: `db_models.py` truncated at line 330
**Symptom**: `SkillGapTable` class is missing its `__table_args__` with the `UniqueConstraint("request_id", "skill_name")`. The file ends mid-comment at `# Idempotency: o` — the rest was lost to truncation.
**Impact**: `persistence.py` line 107 uses `ON CONFLICT(request_id, skill_name)` which fails at runtime because no matching UNIQUE constraint exists.
**Fix**: Complete the `SkillGapTable` class with `__table_args__` containing the composite unique constraint.

### ISSUE 2: `schema.sql` missing Phase 2 tables
**Symptom**: `schema.sql` has 7 Phase 1 tables but is missing the 4 Phase 2 tables (`tailoring_requests`, `tailored_bullets`, `parsed_bullets`, `skill_gaps`).
**Impact**: When `init_db()` runs `schema.sql`, Phase 2 tables don't get created.
**Fix**: Add `CREATE TABLE IF NOT EXISTS` statements for all 4 Phase 2 tables to `schema.sql`.

### ISSUE 3: No integration-level persistence test
**Symptom**: Persistence tests mock all database calls. Mock-only tests hid the Jobs tab SQL bug THREE TIMES.
**Impact**: The `ON CONFLICT` constraint mismatch in skill_gaps is invisible to the existing test suite.
**Fix**: Add a persistence round-trip integration test using a real in-memory SQLite database.

---

## CRITICAL RULES (Anti-Hallucination)

1. **READ before WRITE**: Before modifying ANY file, read it first. Never assume file contents.
2. **EXISTING FILES — DO NOT DUPLICATE OR RENAME**:
   - `src/models/database.py` — All database query functions. Modify IN PLACE.
   - `src/models/entities.py` — All Pydantic models and enums. DO NOT MODIFY.
   - `src/tailoring/engine.py` — Tailoring engine with v1.1 guardrail. DO NOT MODIFY.
   - `src/tailoring/models.py` — Tailoring Pydantic models. DO NOT MODIFY.
   - `src/tailoring/db_models.py` — SQLAlchemy ORM models. Fix truncation only.
   - `src/tailoring/persistence.py` — Tailoring save/retrieve. DO NOT MODIFY (the SQL is correct; the schema needs to match it).
   - `src/web/app.py` — FastAPI app factory. Modify ONLY to add health router.
3. **IMPORT PATHS**: All imports use `src.` prefix (e.g., `from src.models.compat import is_sqlite`). The project uses `pythonpath = ["."]` in pyproject.toml.
4. **PYTHON VERSION**: Target Python 3.10+. Do NOT use `datetime.UTC` (use `datetime.timezone.utc`). Do NOT use `StrEnum` (use `str, Enum`).
5. **ASYNC**: The entire codebase is async. Database uses `AsyncSession`. All database functions are `async def`. FastAPI routes must be `async def`.
6. **RUFF CONFIG**: `target-version = "py310"`, `line-length = 120`. Ignored rules: `UP017`, `UP042`, `E501`, `SIM102`, `SIM105`, `SIM108`, `B017`, `B904`.
7. **TESTS**: `pytest` with `asyncio_mode = "strict"`. All async tests need `@pytest.mark.asyncio`. Test isolation uses StaticPool in-memory SQLite.
8. **NO SECRETS — ZERO TOLERANCE**: Never hardcode API keys, passwords, or credentials in any committed file.
9. **NO DIALECT-SPECIFIC SQL in shared paths**: All raw SQL in `database.py` must work on BOTH SQLite and PostgreSQL, OR must be behind a backend-detection branch using `src/models/compat.py`.
10. **DUAL-BACKEND TESTING**: For any database function containing raw SQL, write a database-level test exercising real SQL against an in-memory database — not just a mock.
11. **NO FABRICATED INFRASTRUCTURE**: Do NOT reference asyncpg features, PostgreSQL extensions, or GCP services you are not certain exist. Use standard SQLAlchemy async patterns only.
12. **DATA LEAKAGE PREVENTION**: No secrets, database files, or `.env` in Docker images.
13. **EXISTING ROUTES**: The web app currently has 3 routers (dashboard, jobs, demo). Do NOT add application/CRM routes in this sprint.
14. **DO NOT MODIFY** any file not explicitly listed in the file inventory below. If you think a change is needed elsewhere, STOP and explain why.

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

# 3. Verify recent commits
git log --oneline -5
# Expect the semantic-fidelity guardrail commit (ed58fc6) or a merge containing it

# 4. Check for uncommitted changes
git status
# If modified files exist, read diffs and decide:
#   - Legitimate additions → commit with descriptive message
#   - Unexpected → STOP and report
# If clean, proceed.

# 5. Run all tests
pytest tests/ -v 2>&1 | tail -20
# Record count and failures. Some may fail due to KNOWN ISSUES — that's expected.
# Document which tests fail and confirm they match the known issues.

# 6. Verify lint
ruff check src/ tests/
# Expect 0 errors

# 7. Verify existing file structure
ls src/models/database.py src/models/entities.py src/models/schema.sql
ls src/tailoring/engine.py src/tailoring/models.py src/tailoring/db_models.py
ls src/tailoring/persistence.py src/tailoring/resume_parser.py src/tailoring/skill_extractor.py
ls src/web/app.py src/web/routes/dashboard.py src/web/routes/jobs.py src/web/routes/demo.py
ls .github/workflows/ci.yml

# 8. Confirm the truncation bug in db_models.py
tail -5 src/tailoring/db_models.py
# If the last line is a truncated comment (e.g., "# Idempotency: o"), ISSUE 1 is confirmed.
# If it ends with a proper __table_args__, ISSUE 1 may already be fixed — skip Task 1.

# 9. Check which Phase 2 tables exist in schema.sql
grep "CREATE TABLE" src/models/schema.sql
# If skill_gaps/tailoring_requests/tailored_bullets/parsed_bullets are missing, ISSUE 2 is confirmed.
# If all 11 tables present, skip Task 2.

# 10. Verify these files do NOT exist yet (this sprint creates them)
ls src/models/compat.py 2>/dev/null && echo "WARNING: compat.py exists — read before overwriting" || echo "OK: compat.py not yet created"
ls src/web/routes/health.py 2>/dev/null && echo "WARNING: health.py exists" || echo "OK: health.py not yet created"
ls Dockerfile 2>/dev/null && echo "WARNING: Dockerfile exists" || echo "OK: Dockerfile not yet created"
ls docker-compose.yml 2>/dev/null && echo "WARNING: docker-compose.yml exists" || echo "OK: docker-compose.yml not yet created"
ls src/models/schema_postgres.sql 2>/dev/null && echo "WARNING: schema_postgres.sql exists" || echo "OK: schema_postgres.sql not yet created"
```

If ANY pre-flight check fails unexpectedly (steps 1-7), STOP and report. Do NOT proceed.

---

## FILE INVENTORY

### Files to Create (new — 9 files)

| # | File | Lines (approx) | Purpose |
|---|------|----------------|---------|
| 1 | `src/models/compat.py` | ~39 | Backend detection: `get_database_url()`, `is_postgres()`, `is_sqlite()` |
| 2 | `src/models/schema_postgres.sql` | ~300 | PostgreSQL DDL — same 11 tables as schema.sql with PG syntax |
| 3 | `src/web/routes/health.py` | ~52 | `GET /health` — status, version, DB connectivity |
| 4 | `tests/unit/test_health.py` | ~56 | Health endpoint tests (200 OK + degraded on DB failure) |
| 5 | `tests/integration/test_persistence_roundtrip.py` | ~80 | ON CONFLICT upsert exercised against real SQLite |
| 6 | `Dockerfile` | ~67 | Multi-stage build: builder (gcc+libpq-dev) → runtime (python:3.11-slim) |
| 7 | `docker-compose.yml` | ~41 | PostgreSQL 16 + web service with health checks |
| 8 | `.dockerignore` | ~57 | Excludes secrets, DB files, docs, test mocks |
| 9 | `.env.example` | ~22 | Environment variable documentation |
| 10 | `deploy/cloudrun.sh` | ~60 | GCP Cloud Run deployment script |

### Files to Modify (existing — 5 files)

| # | File | Changes |
|---|------|---------|
| 1 | `src/tailoring/db_models.py` | Fix truncation: add `__table_args__` with `UniqueConstraint` to `SkillGapTable` |
| 2 | `src/models/schema.sql` | Add 4 Phase 2 tables if missing (parsed_bullets, tailoring_requests, tailored_bullets, skill_gaps) |
| 3 | `src/models/database.py` | Replace hardcoded `DATABASE_URL` with compat-based factory. Guard PRAGMAs. Upgrade `init_db()` and `_split_sql_statements()`. |
| 4 | `src/web/app.py` | Add health router registration |
| 5 | `requirements.txt` | Add `asyncpg` |
| 6 | `.github/workflows/ci.yml` | Add `docker-build` and `db-tests-postgres` jobs |

---

## TASK 0: Read All Files That Will Be Modified

Before writing ANY code, read these files IN FULL. This is not optional.

```
src/tailoring/db_models.py
src/models/schema.sql
src/models/database.py
src/web/app.py
requirements.txt
.github/workflows/ci.yml
```

Also read for reference (do not modify):
```
src/tailoring/persistence.py
src/models/entities.py
```

---

# ═══════════════════════════════════════════════════════════════════
# PART A: SCHEMA GAP-FILL (Fix known issues before adding new infra)
# ═══════════════════════════════════════════════════════════════════

## TASK 1: Fix `db_models.py` Truncation (ISSUE 1)

**Read first**: `src/tailoring/db_models.py` (FULL file)

The `SkillGapTable` class is missing its closing `__table_args__`. The pattern to follow is `TailoringRequestTable`, which has:

```python
    __table_args__ = (
        UniqueConstraint("job_id", "profile_id", name="uq_tailoring_request_identity"),
    )
```

**What to add** at the end of `SkillGapTable` (replacing the truncated comment):

```python
    __table_args__ = (
        UniqueConstraint("request_id", "skill_name", name="uq_skill_gap_identity"),
    )
```

This must match the `ON CONFLICT(request_id, skill_name)` in `persistence.py` line 107.

**Verification**:
```bash
python -c "from src.tailoring.db_models import SkillGapTable; print('OK:', SkillGapTable.__table_args__)"
# Should print the UniqueConstraint tuple
```

---

## TASK 2: Add Phase 2 Tables to `schema.sql` (ISSUE 2)

**Read first**: `src/models/schema.sql` AND `src/tailoring/db_models.py`

If the pre-flight (step 9) confirmed the tables are missing, append the 4 Phase 2 tables to `schema.sql` AFTER the existing tables and indexes, BEFORE the seed data inserts.

**Tables to add** (in FK-dependency order):
1. `parsed_bullets` — depends on `resume_profiles`
2. `tailoring_requests` — depends on `job_listings` and `resume_profiles`
3. `tailored_bullets` — depends on `tailoring_requests`
4. `skill_gaps` — depends on `tailoring_requests`

**Critical constraints**:
- `tailoring_requests`: `UNIQUE(job_id, profile_id)`
- `skill_gaps`: `UNIQUE(request_id, skill_name)`
- `parsed_bullets`: `UNIQUE(profile_id, original_text)`
- All foreign keys with `ON DELETE CASCADE`
- CHECK constraints matching the ORM's `CheckConstraint` definitions

Use SQLite syntax matching the existing tables in the file (e.g., `INTEGER PRIMARY KEY AUTOINCREMENT`, `TEXT NOT NULL DEFAULT (strftime(...))`, `REAL`).

Also add indexes for the new tables:
```sql
CREATE INDEX IF NOT EXISTS idx_parsed_bullets_profile ON parsed_bullets(profile_id);
CREATE INDEX IF NOT EXISTS idx_tailoring_requests_job ON tailoring_requests(job_id);
CREATE INDEX IF NOT EXISTS idx_tailoring_requests_profile ON tailoring_requests(profile_id);
CREATE INDEX IF NOT EXISTS idx_tailored_bullets_request ON tailored_bullets(request_id);
CREATE INDEX IF NOT EXISTS idx_skill_gaps_request ON skill_gaps(request_id);
```

**Verification**:
```bash
python -c "
import sqlite3
conn = sqlite3.connect(':memory:')
with open('src/models/schema.sql') as f:
    conn.executescript(f.read())
tables = [r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()]
print('Tables:', sorted(tables))
assert 'skill_gaps' in tables, 'skill_gaps missing!'
assert 'tailoring_requests' in tables, 'tailoring_requests missing!'
assert 'tailored_bullets' in tables, 'tailored_bullets missing!'
assert 'parsed_bullets' in tables, 'parsed_bullets missing!'
print('ALL PHASE 2 TABLES PRESENT')
"
```

---

## TASK 3: Persistence Round-Trip Integration Test (ISSUE 3)

**Read first**: `src/tailoring/persistence.py`, `tests/unit/test_persistence.py` (if it exists)

Create `tests/integration/test_persistence_roundtrip.py` that:

1. Creates a real in-memory SQLite database using `init_db()` (not mocks)
2. Seeds a minimal job listing and resume profile (using raw SQL inserts)
3. Calls `save_tailoring_result()` with a valid `TailoringResult` containing skill gaps
4. Calls `get_tailoring_result()` and verifies the round-trip
5. Calls `save_tailoring_result()` AGAIN with updated data and verifies the `ON CONFLICT` upsert works (no duplicate rows, data updated)

This test exercises the exact SQL path that was broken — the `ON CONFLICT(request_id, skill_name)`.

**Verification**:
```bash
pytest tests/integration/test_persistence_roundtrip.py -v
# All tests must pass
```

---

## TASK 3b: Verify Part A

Run the full test suite and lint BEFORE proceeding to Part B:

```bash
pytest tests/ -v 2>&1
ruff check src/ tests/
```

**Gate**: ALL tests must pass and lint must be clean. If anything fails, fix it now. Do NOT proceed to Part B with failures.

---

# ═══════════════════════════════════════════════════════════════════
# PART B: DOCKER + CLOUD SQL (New infrastructure on clean baseline)
# ═══════════════════════════════════════════════════════════════════

## TASK 4: Create `src/models/compat.py` (Backend Detection)

**Purpose**: Pure functions for database backend detection. No side effects, no imports from other `src/` modules.

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

## TASK 5: Update `src/models/database.py` (Polymorphic Engine Factory)

**Read first**: `src/models/database.py` (full file)

Preserve ALL existing query functions exactly as they are. The changes are ONLY to: engine creation, PRAGMA listener, `init_db()`, and `_split_sql_statements()`.

### 5a. Replace module-level engine creation

**Find and replace** the current block (approximately lines 53-69):
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

Remove the old `DATABASE_URL = os.getenv(...)` variable — `compat.py` owns that now.

### 5b. Guard PRAGMA listener with `is_sqlite()`

**Find** the current PRAGMA listener (approximately lines 79-88):
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

Without this guard, PRAGMAs fire on PostgreSQL connections and crash.

### 5c. Upgrade `init_db()` to select schema file by backend

**Replace** the current `init_db()` with:

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

### 5d. Upgrade `_split_sql_statements()` for dollar-quoting

The PostgreSQL schema uses `$$` dollar-quoted blocks for trigger functions. **Replace** the current `_split_sql_statements()` with:

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

### 5e. Clean up imports

Remove the now-unused direct `os` import for DATABASE_URL if `os` is not used elsewhere. The `compat` import goes at the top with other `src.` imports.

**Verification**:
```bash
python -c "from src.models.database import engine, init_db; print('Engine URL:', engine.url)"
pytest tests/unit/test_database.py -v
```

---

## TASK 6: Create `src/web/routes/health.py` + Register in `app.py`

### 6a. Create health endpoint

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
    return {
        "status": status,
        "version": "2.6.0",
        "database": "connected" if db_ok else f"error: {db_error}",
    }
```

### 6b. Register in `app.py`

**Find** the current router registration in `create_app()`:
```python
    from src.web.routes import dashboard, demo, jobs
    app.include_router(dashboard.router)
    app.include_router(jobs.router)
    app.include_router(demo.router)
```

**Replace with**:
```python
    from src.web.routes import dashboard, demo, health, jobs
    app.include_router(dashboard.router)
    app.include_router(jobs.router)
    app.include_router(demo.router)
    app.include_router(health.router)
```

### 6c. Create `tests/unit/test_health.py`

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

## TASK 7: Create `src/models/schema_postgres.sql`

**Read first**: `src/models/schema.sql` (the SQLite version — should now have 11 tables after Task 2)

Create the PostgreSQL equivalent. Every table in `schema.sql` must have a counterpart.

**Syntax mapping**:

| SQLite | PostgreSQL |
|--------|-----------|
| `INTEGER PRIMARY KEY AUTOINCREMENT` | `SERIAL PRIMARY KEY` |
| `REAL` | `DOUBLE PRECISION` |
| `TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))` | `TIMESTAMPTZ NOT NULL DEFAULT NOW()` |
| `CREATE TRIGGER ... BEGIN ... END;` | `CREATE OR REPLACE FUNCTION ... $$ ... $$ LANGUAGE plpgsql;` + `CREATE TRIGGER ...` |
| `INSERT OR IGNORE INTO` | `INSERT INTO ... ON CONFLICT DO NOTHING` |
| `BOOLEAN` (stored as 0/1) | `BOOLEAN` (native) |

**All 11 tables** (in FK-dependency order):
1. `job_listings` — `UNIQUE(external_id, source)`
2. `skills` — `UNIQUE(name)`
3. `job_skills` — `UNIQUE(job_id, skill_id)`, FK to job_listings + skills
4. `resume_profiles`
5. `resume_skills` — `UNIQUE(profile_id, skill_id)`, FK to resume_profiles + skills
6. `scrape_log`
7. `company_tiers` — `UNIQUE(company_pattern)`
8. `parsed_bullets` — `UNIQUE(profile_id, original_text)`, FK to resume_profiles
9. `tailoring_requests` — `UNIQUE(job_id, profile_id)`, FK to job_listings + resume_profiles
10. `tailored_bullets` — FK to tailoring_requests
11. `skill_gaps` — `UNIQUE(request_id, skill_name)`, FK to tailoring_requests

**Also include**:
- All indexes from `schema.sql` (use `CREATE INDEX IF NOT EXISTS`)
- The `updated_at` trigger function (PostgreSQL syntax with `$$` dollar-quoting)
- All seed data (company_tiers + skills) using `INSERT INTO ... ON CONFLICT DO NOTHING`

**Verification**:
```bash
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

## TASK 8: Create Docker Files

### 8a. `Dockerfile`

```dockerfile
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
```

### 8b. `docker-compose.yml`

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

### 8c. `.dockerignore`

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

# Alembic
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

# Deployment scripts
deploy/
```

### 8d. `.env.example`

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

### 8e. `deploy/cloudrun.sh`

Create the `deploy/` directory first:
```bash
mkdir -p deploy
```

```bash
#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Céal — GCP Cloud Run Deployment
# ---------------------------------------------------------------------------
set -euo pipefail

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

echo "Building Docker image..."
docker build -t "${IMAGE}" .

echo "Pushing to Artifact Registry..."
docker push "${IMAGE}"

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

```bash
chmod +x deploy/cloudrun.sh
```

**Verification**:
```bash
ls Dockerfile docker-compose.yml .dockerignore .env.example deploy/cloudrun.sh
```

---

## TASK 9: Update `requirements.txt`

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

## TASK 10: Update `.github/workflows/ci.yml`

**Read first**: `.github/workflows/ci.yml`

Add two new jobs AFTER the existing `coverage` job:

### 10a. Docker build job

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

### 10b. PostgreSQL integration test job

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
grep -c "docker-build\|db-tests-postgres" .github/workflows/ci.yml
# Should return 2 or more
```

---

# ═══════════════════════════════════════════════════════════════════
# PART C: FINAL VERIFICATION
# ═══════════════════════════════════════════════════════════════════

## TASK 11: Full Test Suite + Lint

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
- Test count ≥ previous baseline + new health tests + persistence roundtrip

---

## TASK 12: Docker Smoke Test (if Docker available)

```bash
docker compose build --no-cache 2>&1 | tail -10
docker compose up -d
sleep 5
curl -s http://localhost:8000/health | python -m json.tool
docker compose down -v
```

If Docker is not available, skip and note as manual verification.

---

## TASK 13: Commit and Tag

```bash
git add -A
git status
# Review staged files — should include:
#   modified: src/tailoring/db_models.py
#   modified: src/models/schema.sql (if Phase 2 tables were missing)
#   modified: src/models/database.py
#   modified: src/web/app.py
#   modified: requirements.txt
#   modified: .github/workflows/ci.yml
#   new file: src/models/compat.py
#   new file: src/models/schema_postgres.sql
#   new file: src/web/routes/health.py
#   new file: tests/unit/test_health.py
#   new file: tests/integration/test_persistence_roundtrip.py
#   new file: Dockerfile
#   new file: docker-compose.yml
#   new file: .dockerignore
#   new file: .env.example
#   new file: deploy/cloudrun.sh

git commit -m "feat: schema gap-fill + Docker + polymorphic Cloud SQL support

Part A — Schema gap-fill:
- Fix db_models.py truncation: add UniqueConstraint on SkillGapTable
- Add 4 Phase 2 tables to schema.sql with constraints and indexes
- Add persistence round-trip integration test (ON CONFLICT upsert)

Part B — Docker + Cloud SQL:
- Add compat.py: polymorphic backend detection (SQLite/PostgreSQL)
- Add schema_postgres.sql: full PostgreSQL DDL for all 11 tables
- Update database.py: engine factory, PRAGMA guard, dual-schema init_db
- Add health endpoint: GET /health with DB connectivity probe
- Add Dockerfile: multi-stage build (builder + slim runtime)
- Add docker-compose.yml: PostgreSQL 16 + web service
- Add deploy/cloudrun.sh: GCP Cloud Run deployment script
- Update CI: docker-build + db-tests-postgres jobs
- Add asyncpg to requirements"

git tag -a v2.6.0-sprint6-infra -m "Sprint 6: schema gap-fill + Docker + Cloud SQL"
git push origin main --tags
```

---

## COMPLETION CHECKLIST

Before declaring this sprint complete, verify ALL of the following:

**Part A — Gap-Fill**:
- [ ] `db_models.py` — `SkillGapTable` has `__table_args__` with `UniqueConstraint("request_id", "skill_name")`
- [ ] `schema.sql` — Contains all 11 tables (7 Phase 1 + 4 Phase 2) with matching constraints
- [ ] `test_persistence_roundtrip.py` — Exercises real SQL, ON CONFLICT upsert works

**Part B — Docker + Cloud SQL**:
- [ ] `compat.py` — `is_sqlite()` returns True locally, `is_postgres()` returns False
- [ ] `database.py` — Uses `_create_engine()` factory, PRAGMAs guarded by `is_sqlite()`
- [ ] `schema_postgres.sql` — Contains all 11 tables with PostgreSQL syntax
- [ ] `health.py` — `GET /health` returns status + version + DB probe
- [ ] `app.py` — Health router registered (4 routers: dashboard, jobs, demo, health)
- [ ] `Dockerfile` — Multi-stage build, non-root user, HEALTHCHECK
- [ ] `docker-compose.yml` — PostgreSQL 16 + web service with health checks
- [ ] `.dockerignore` — Excludes secrets, DB files, non-essential files
- [ ] `.env.example` — Documents DATABASE_URL, LLM_API_KEY, PORT, GCP vars
- [ ] `deploy/cloudrun.sh` — Executable, references correct GCP vars
- [ ] `requirements.txt` — Includes `asyncpg`
- [ ] `ci.yml` — Has `docker-build` and `db-tests-postgres` jobs

**Final**:
- [ ] `pytest tests/ -v` — ALL tests pass, 0 failures
- [ ] `ruff check src/ tests/` — 0 errors
- [ ] Committed and tagged on `main`
- [ ] Pushed to `origin/main`

If any check fails, fix it before proceeding. Do NOT leave known failures.
