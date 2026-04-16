# Céal Sprint 6 — Deployment Verification & Gap-Fill

## CONTEXT
You are working on the Céal project — an AI-powered career signal engine.
The project root is the `ceal/` directory containing `src/`, `tests/`, `pyproject.toml`, `requirements.txt`.

**Branch state**: You should be on `main` after merging `codex/semantic-fidelity-guardrail`.
If you are NOT on `main`, run:
```bash
git checkout main
git merge codex/semantic-fidelity-guardrail --no-edit
```

This branch contains the FULL Phase 1–5 pipeline plus the semantic-fidelity guardrail:
- Phase 1 (scrape → normalize → rank pipeline)
- Phase 2 + 2B (resume tailoring engine, demo mode, batch, .docx export, persistence)
- Sprint 1 (FastAPI + Jinja2 web UI: Dashboard, Jobs, Demo)
- Sprint 2 (Phase 3 CRM: Kanban board, state-machine status transitions, stale reminders)
- Sprint 3 (Phase 4 Auto-Apply: pre-fill engine, approval queue, confidence scoring)
- Sprint 4 (Docker: multi-stage Dockerfile, docker-compose.yml, GCP Cloud Run deployment)
- Sprint 5 (Cloud SQL: polymorphic SQLite/PostgreSQL, `compat.py` backend detection)
- Semantic-fidelity guardrail (v1.1): rejects hallucinated metrics, semantic drift, phantom bullets

---

## KNOWN ISSUES (This sprint fixes these)

### ISSUE 1: `db_models.py` truncated at line 330
**Symptom**: `SkillGapTable` class is missing its `__table_args__` with the `UniqueConstraint("request_id", "skill_name")`.
The file ends mid-comment at `# Idempotency: o` — the rest was lost to truncation.
**Impact**: `persistence.py` line 107 uses `ON CONFLICT(request_id, skill_name)` which fails at runtime because no matching UNIQUE constraint exists in the schema.
**Fix required**: Complete the `SkillGapTable` class with `__table_args__` containing the composite unique constraint, matching the pattern used by `TailoringRequestTable` (which has `UniqueConstraint("job_id", "profile_id")`).

### ISSUE 2: `schema.sql` missing Phase 2 tables
**Symptom**: `schema.sql` only has 9 Phase 1 tables. The 4 Phase 2 tables (`tailoring_requests`, `tailored_bullets`, `parsed_bullets`, `skill_gaps`) are defined in the ORM (`db_models.py`) but have no corresponding DDL in `schema.sql`.
**Impact**: When `init_db()` runs `schema.sql` to create tables, the Phase 2 tables don't exist. The ORM's `Base.metadata.create_all()` handles this in Alembic/test contexts, but the raw SQL path used by the main app will fail.
**Fix required**: Add `CREATE TABLE IF NOT EXISTS` statements for all 4 Phase 2 tables to `schema.sql`, with the correct unique constraints, foreign keys, and indexes. Use SQLite syntax (matching the existing tables in the file).

### ISSUE 3: No integration-level smoke test for the web app
**Symptom**: Web route tests mock all database calls. This was the testing strategy that caused the Jobs tab to break THREE TIMES.
**Impact**: If any SQL in `database.py` or `persistence.py` has a syntax error or constraint mismatch, mock-only tests will still pass.
**Fix required**: Add at minimum a health-check integration test and a persistence round-trip test that use a real in-memory SQLite database.

---

## CRITICAL RULES (Anti-Hallucination)

1. **READ before WRITE**: Before modifying ANY file, read it first. Never assume file contents.
2. **EXISTING FILES — DO NOT DUPLICATE OR RENAME**:
   - `src/models/database.py` — All database query functions. Do NOT create a second database module.
   - `src/models/entities.py` — All Pydantic models and enums. Do NOT create duplicate enum files.
   - `src/models/schema.sql` — SQLite DDL. Append to this file, do NOT create a new schema file.
   - `src/tailoring/db_models.py` — SQLAlchemy ORM models. Fix the truncation IN THIS FILE.
   - `src/tailoring/persistence.py` — Tailoring save/retrieve. The ON CONFLICT SQL is correct; the schema needs to match it.
   - `src/tailoring/engine.py` — Tailoring engine with v1.1 guardrail. DO NOT MODIFY.
   - `src/tailoring/models.py` — Pydantic models for tailoring. DO NOT MODIFY.
3. **IMPORT PATHS**: All imports use `src.` prefix (e.g., `from src.models.database import init_db`). The project uses `pythonpath = ["."]` in pyproject.toml.
4. **PYTHON VERSION**: Target Python 3.10+. Do NOT use `datetime.UTC` (use `datetime.timezone.utc`). Do NOT use `StrEnum` (use `str, Enum`).
5. **ASYNC**: The entire codebase is async. Database uses `AsyncSession`. All database functions are `async def`.
6. **RUFF CONFIG**: `target-version = "py310"`, `line-length = 120`. Ignored rules: `UP017`, `UP042`, `E501`, `SIM102`, `SIM105`, `SIM108`, `B017`, `B904`.
7. **TESTS**: `pytest` with `asyncio_mode = "strict"`. All async tests need `@pytest.mark.asyncio`. Test isolation uses StaticPool in-memory SQLite.
8. **NO SECRETS — ZERO TOLERANCE**: Never hardcode credentials in any committed file.
9. **NO DIALECT-SPECIFIC SQL in shared paths**: All raw SQL in `database.py` must work on BOTH SQLite and PostgreSQL, OR must be behind a backend-detection branch in `src/models/compat.py`.
10. **DUAL-BACKEND TESTING**: For any database function containing raw SQL, write a database-level test exercising real SQL against an in-memory database — not just a mock.

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

# 3. Verify the semantic-fidelity guardrail commit is present
git log --oneline -3
# The most recent commit should be ed58fc6 or a merge commit containing it

# 4. Check for uncommitted changes
git status
# If modified files exist, read diffs and decide:
#   - Legitimate additions → commit with descriptive message
#   - Unexpected → STOP and report
# If clean, proceed.

# 5. Run all tests
pytest tests/ -v 2>&1 | tail -20
# Record the count. Some may fail — that's expected (the known issues above).
# Document which tests fail and confirm they match the known issues.

# 6. Verify lint
ruff check src/ tests/
# Expect 0 errors

# 7. Verify file structure — core files exist
ls src/models/database.py src/models/entities.py src/models/schema.sql
ls src/models/compat.py  # Sprint 5 deliverable
ls src/tailoring/engine.py src/tailoring/models.py src/tailoring/db_models.py
ls src/tailoring/persistence.py src/tailoring/resume_parser.py src/tailoring/skill_extractor.py
ls src/web/app.py src/web/routes/health.py
ls Dockerfile docker-compose.yml .env.example
ls tests/unit/test_tailoring_engine.py tests/unit/test_persistence.py tests/unit/test_database.py

# 8. Confirm the truncation bug in db_models.py
tail -5 src/tailoring/db_models.py
# If the last line is a truncated comment (e.g., "# Idempotency: o"), ISSUE 1 is confirmed.
# If the file ends with a proper __table_args__ and class closure, ISSUE 1 may already be fixed — skip Task 1.
```

If the pre-flight shows unexpected failures beyond the 3 known issues, STOP and report.

---

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

Append the 4 Phase 2 tables to `schema.sql` AFTER the existing Phase 1 tables and BEFORE the seed data. Use `CREATE TABLE IF NOT EXISTS` with SQLite-compatible syntax. The table definitions must match the ORM in `db_models.py` exactly:

**Tables to add** (in FK-dependency order):
1. `parsed_bullets` — depends on `resume_profiles`
2. `tailoring_requests` — depends on `job_listings` and `resume_profiles`
3. `tailored_bullets` — depends on `tailoring_requests`
4. `skill_gaps` — depends on `tailoring_requests`

**Critical constraints to include**:
- `tailoring_requests`: `UNIQUE(job_id, profile_id)`
- `skill_gaps`: `UNIQUE(request_id, skill_name)`
- `parsed_bullets`: `UNIQUE(profile_id, original_text)` (check ORM for exact columns)
- All foreign keys with `ON DELETE CASCADE`
- CHECK constraints matching the ORM's `CheckConstraint` definitions

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

**Read first**: `src/tailoring/persistence.py`, `tests/unit/test_persistence.py`

Add a new test file `tests/integration/test_persistence_roundtrip.py` that:

1. Creates a real in-memory SQLite database using `init_db()` (not mocks)
2. Seeds a minimal job listing and resume profile
3. Calls `save_tailoring_result()` with a valid `TailoringResult` containing skill gaps
4. Calls `get_tailoring_result()` and verifies the round-trip
5. Calls `save_tailoring_result()` AGAIN with updated data and verifies the `ON CONFLICT` upsert works (no duplicate rows, data updated)

This test exercises the exact SQL path that was broken — the `ON CONFLICT(request_id, skill_name)` in persistence.py.

**Verification**:
```bash
pytest tests/integration/test_persistence_roundtrip.py -v
# All tests must pass
```

---

## TASK 4: Full Test Suite + Lint Verification

Run the complete verification:

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
- Test count is >= 217 (previous baseline) + new integration tests

---

## TASK 5: Docker Smoke Test (if Docker available)

```bash
docker compose build --no-cache 2>&1 | tail -10
docker compose up -d
sleep 5
curl -s http://localhost:8000/health | python -m json.tool
docker compose down
```

If Docker is not available, skip this task and note it as a manual verification step.

---

## TASK 6: Commit and Tag

```bash
git add -A
git status
# Review staged files — should only be:
#   modified: src/tailoring/db_models.py
#   modified: src/models/schema.sql
#   new file: tests/integration/test_persistence_roundtrip.py

git commit -m "fix: complete SkillGapTable unique constraint, add Phase 2 DDL to schema.sql

- Fix db_models.py truncation: add UniqueConstraint('request_id', 'skill_name')
- Add 4 Phase 2 tables to schema.sql (parsed_bullets, tailoring_requests,
  tailored_bullets, skill_gaps) with all constraints and indexes
- Add persistence round-trip integration test exercising ON CONFLICT upsert
- Resolves: skill_gaps ON CONFLICT failure, schema.sql/ORM divergence"

git tag -a v2.6.0-sprint6-gapfill -m "Sprint 6: deployment verification gap-fill"
git push origin main --tags
```

---

## COMPLETION CHECKLIST

Before declaring this sprint complete, verify ALL of the following:

- [ ] `db_models.py` — `SkillGapTable` has `__table_args__` with `UniqueConstraint("request_id", "skill_name")`
- [ ] `schema.sql` — Contains all 13 tables (9 Phase 1 + 4 Phase 2) with matching constraints
- [ ] `test_persistence_roundtrip.py` — Exercises real SQL, ON CONFLICT upsert works
- [ ] `pytest tests/ -v` — ALL tests pass, 0 failures
- [ ] `ruff check src/ tests/` — 0 errors
- [ ] Committed and tagged on `main`
- [ ] Pushed to `origin/main`

If any check fails, fix it before proceeding. Do NOT leave known failures.
