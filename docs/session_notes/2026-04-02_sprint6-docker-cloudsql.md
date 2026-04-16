# Céal Session Notes — 2026-04-02

## Session: Sprint 6 — Schema Gap-Fill + Docker + Cloud SQL
**Date:** Wednesday, April 2, 2026
**AI platform:** Claude Code + Cowork
**Tag:** `v2.6.0-sprint6-infra`
**Commit:** `98177d4`
**Personas Tagged In:** DevOps/Infrastructure Engineer (Lead), ETL Architect (Support), Backend Engineer (Support)

---

## Objective
Reimplement Docker containerization (Sprint 4) and Cloud SQL polymorphic DB (Sprint 5) after the branch reset to `codex/semantic-fidelity-guardrail`. Fix known schema bugs first, then layer infrastructure on a clean baseline.

## Pre-Flight Findings

| Check | Result |
|-------|--------|
| Branch | `main` at `a123b96` |
| Tests | 177 passing, 0 failures |
| Lint | Clean (ruff 0 errors) |
| ISSUE 1 (db_models.py truncation) | **Already fixed** — `SkillGapTable.__table_args__` present with `UniqueConstraint("request_id", "skill_name")` |
| ISSUE 2 (schema.sql missing Phase 2) | **Already fixed** — All 11 tables present (commit a123b96) |
| ISSUE 3 (no integration test) | **Already fixed** — `test_persistence_roundtrip.py` exists with 5 tests |

**Part A was already resolved by prior commit a123b96.** Sprint focused entirely on Part B.

## Tasks Completed

| # | Task | Files | Status |
|---|------|-------|--------|
| 4 | Create `src/models/compat.py` — backend detection | 1 new | Done |
| 5 | Update `database.py` — polymorphic engine factory, PRAGMA guard, dual-schema `init_db()`, `$$` dollar-quote SQL splitter | 1 modified | Done |
| 6 | Create `GET /health` endpoint + tests + register in `app.py` | 3 new/modified | Done |
| 7 | Create `schema_postgres.sql` — all 11 tables with PG syntax | 1 new | Done |
| 8 | Create Docker files — Dockerfile, docker-compose.yml, .dockerignore, .env.example, deploy/cloudrun.sh | 5 new | Done |
| 9 | Add `asyncpg==0.30.0` to requirements.txt | 1 modified | Done |
| 10 | Add `docker-build` + `db-tests-postgres` CI jobs | 1 modified | Done |

## Files Changed (13 total, +712 lines)

### New Files (9)
| File | Lines | Purpose |
|------|-------|---------|
| `src/models/compat.py` | 35 | `get_database_url()`, `is_postgres()`, `is_sqlite()` — zero-import backend detection |
| `src/models/schema_postgres.sql` | 230 | PostgreSQL DDL for all 11 tables, trigger function, seed data |
| `src/web/routes/health.py` | 42 | `GET /health` — status, version, DB connectivity probe |
| `tests/unit/test_health.py` | 42 | Health endpoint tests (200 OK + degraded on DB failure) |
| `Dockerfile` | 50 | Multi-stage build: builder (gcc+libpq-dev) -> runtime (python:3.11-slim), non-root user, HEALTHCHECK |
| `docker-compose.yml` | 38 | PostgreSQL 16-alpine + web service with health checks |
| `.dockerignore` | 50 | Excludes secrets, DB files, tests, CI, docs |
| `.env.example` | 22 | Documents DATABASE_URL, LLM_API_KEY, PORT, GCP vars |
| `deploy/cloudrun.sh` | 48 | GCP Cloud Run deployment script (Artifact Registry + gcloud run deploy) |

### Modified Files (4)
| File | Changes |
|------|---------|
| `src/models/database.py` | Replaced hardcoded `DATABASE_URL` with compat-based `_create_engine()` factory. Guarded PRAGMAs with `is_sqlite()`. Upgraded `init_db()` for dual-schema selection. Added `$$` dollar-quote handling to `_split_sql_statements()`. |
| `src/web/app.py` | Registered health router (4 routers: dashboard, jobs, demo, health). Bumped version to 2.6.0. |
| `requirements.txt` | Added `asyncpg==0.30.0` |
| `.github/workflows/ci.yml` | Added Stage 5 (Docker Build) and Stage 6 (PostgreSQL DB Tests with service container) |

## Architecture Decisions

### 1. Compat Layer (`compat.py`)
Single `DATABASE_URL` env var switches the entire app between SQLite (dev) and PostgreSQL (prod). All dialect-specific behavior branches on `is_sqlite()` / `is_postgres()` — no code changes needed to deploy.

**Interview talking point:** "The compat layer means zero code changes between local SQLite and production PostgreSQL — just one environment variable."

### 2. Polymorphic Engine Factory
`_create_engine()` configures different pool settings per backend:
- SQLite in-memory: `StaticPool` for test isolation
- SQLite file: `pool_pre_ping`
- PostgreSQL: `pool_pre_ping` + `pool_size=5` + `max_overflow=10`

### 3. PRAGMA Guard
SQLite PRAGMAs (`WAL`, `foreign_keys`, etc.) are wrapped in `if is_sqlite():` — without this, they crash PostgreSQL connections.

### 4. Dual-Schema Init
`init_db()` auto-selects `schema.sql` (SQLite) or `schema_postgres.sql` (PostgreSQL). PostgreSQL DDL uses `engine.begin()` for DDL outside the session manager. The SQL splitter handles both SQLite `BEGIN...END` triggers and PostgreSQL `$$` dollar-quoted function bodies.

### 5. Multi-Stage Docker Build
Builder stage installs gcc + libpq-dev for asyncpg compilation. Runtime stage is python:3.11-slim with only libpq5 + curl. Non-root `ceal` user. HEALTHCHECK probes `/health`.

### 6. Health Endpoint
Returns 200 always (even on DB failure) with `status: "healthy"` or `status: "degraded"`. Probes actual DB connectivity with `SELECT 1`, not just process liveness.

## CI Pipeline (6 stages)
```
Stage 1: Lint (ruff)
Stage 2: Unit Tests (Python 3.11 + 3.12 matrix)
Stage 3: Integration Tests (Python 3.11 + 3.12 matrix)
Stage 4: Coverage (80% threshold)
Stage 5: Docker Build (NEW — verify image builds)
Stage 6: PostgreSQL DB Tests (NEW — integration tests against PG 16 service container)
```

## Test Results

| Metric | Value |
|--------|-------|
| Total tests | 179 (177 baseline + 2 new health tests) |
| Passed | 179 |
| Failed | 0 |
| Lint errors | 0 |

## What's NOT in This Sprint
- Sprint 2 (CRM: applications/reminders routes, Kanban) — future sprint
- Sprint 3 (Auto-Apply: prefill engine, approval queue) — future sprint
- No Alembic migrations yet — schema files handle DDL directly
- Docker smoke test skipped (Docker not available in session)

## Deployment Checklist

- [x] `compat.py` — `is_sqlite()` returns True locally
- [x] `database.py` — Uses `_create_engine()` factory, PRAGMAs guarded
- [x] `schema_postgres.sql` — All 11 tables with PostgreSQL syntax
- [x] `health.py` — `GET /health` returns status + version + DB probe
- [x] `app.py` — 4 routers registered (dashboard, jobs, demo, health)
- [x] `Dockerfile` — Multi-stage, non-root user, HEALTHCHECK
- [x] `docker-compose.yml` — PostgreSQL 16 + web with health checks
- [x] `.dockerignore` — Excludes secrets, DB files
- [x] `.env.example` — Documents all env vars
- [x] `deploy/cloudrun.sh` — Executable, correct GCP vars
- [x] `requirements.txt` — Includes asyncpg
- [x] `ci.yml` — docker-build + db-tests-postgres jobs
- [x] 179 tests pass, 0 lint errors
- [x] Committed and tagged `v2.6.0-sprint6-infra`
- [x] Pushed to origin/main
