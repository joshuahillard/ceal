# Céal — Engineering Rules

> These rules apply to ALL AI assistants working on Céal (Claude, Codex, Gemini). They exist because each one was learned the hard way.
>
> **See also:** The Core Contract in `docs/RUNTIME_PROMPTS.md` contains a compact runtime version of these rules for pasting into AI sessions. The two rule sets are complementary — this file has the full incident history and rationale; the Core Contract has the distilled paste-ready version.

## Non-Negotiable Rules

### 1. READ before WRITE
Before modifying ANY file, read it first. Never assume file contents. Files may have been modified by another AI assistant since your last session.

### 2. No File Duplication
Do NOT create new files that duplicate existing functionality. The canonical files are listed in `PROJECT_CONTEXT.md`. If you think you need a new file, check if the functionality already exists first.

### 3. Python 3.10+ Target
- Do NOT use `datetime.UTC` → use `datetime.timezone.utc`
- Do NOT use `StrEnum` → use `str, Enum`
- Do NOT use `match` statements → use `if/elif`
- Do NOT use `X | Y` union syntax in function signatures without `from __future__ import annotations`

### 4. Import Paths
All imports use `src.` prefix:
```python
from src.models.database import get_session
from src.models.compat import is_sqlite
from src.tailoring.models import TailoringResult
```
The project uses `pythonpath = ["."]` in `pyproject.toml`.

### 5. Async Everywhere
- Database uses `AsyncSession` via `aiosqlite` (SQLite) or `asyncpg` (PostgreSQL)
- All database functions are `async def`
- All FastAPI routes are `async def`
- All async tests need `@pytest.mark.asyncio` decorator

### 6. No Dialect-Specific SQL in Shared Paths
All raw SQL in `database.py` must work on BOTH SQLite and PostgreSQL, OR must be behind a backend-detection branch:
```python
from src.models.compat import is_sqlite
if is_sqlite():
    # SQLite-specific SQL
else:
    # PostgreSQL-specific SQL
```

### 7. No Secrets in Code
- Never hardcode API keys, passwords, or credentials
- Use `.env` + `python-dotenv`
- `.env` is in `.gitignore`
- `.env.example` documents required variables without values

### 8. Ruff Configuration
```
target-version = "py310"
line-length = 120
```
Ignored rules: `UP017`, `UP042`, `E501`, `SIM102`, `SIM105`, `SIM108`, `B017`, `B904`

### 9. Test Isolation
- StaticPool in-memory SQLite for unit tests
- All sessions share the same in-memory connection
- `@pytest.mark.asyncio` with `asyncio_mode = "strict"`

### 10. Dual-Backend Testing
For any database function containing raw SQL, write a database-level test exercising real SQL — not just a mock. This rule exists because **mock-only tests hid SQL bugs THREE TIMES** (the Jobs tab incident).

## Rules Learned from Incidents

### The Jobs Tab Bug (3x recurrence)
**What happened**: Mock-only route tests passed, but the actual SQL had a LEFT JOIN bug that caused submitted applications to reappear in the jobs list.
**Rule**: Core query functions need DB-level tests exercising real SQL against an in-memory SQLite database.

### The `datetime.UTC` Break
**What happened**: Tests used `datetime.UTC` which requires Python 3.11+. CI ran on 3.10 and failed.
**Rule**: Always use `datetime.timezone.utc`. The ruff rule `UP017` is ignored specifically for this.

### The `db_models.py` Truncation
**What happened**: A file write was interrupted, cutting off `SkillGapTable` mid-comment. The missing `UniqueConstraint` caused `ON CONFLICT` failures at runtime.
**Rule**: After writing any file, verify it with a Python import or syntax check. `tail -5` the file to confirm it ends properly.

### The Branch Reset Data Loss
**What happened**: Resetting `main` to a feature branch lost Sprints 2-5. Had to reimplement Docker + Cloud SQL from scratch.
**Rule**: Never reset `main` to a feature branch. Use merge or cherry-pick instead. Tag before any destructive operation.

## Rules Learned from Sprints 9-10

### Vertex AI Fail-Open Pattern (Sprint 9)
**Context**: The regime classifier is an optional enrichment step, not a core pipeline gate.
**Rule**: External AI integrations for enrichment (non-core) must fail open — if Vertex AI is unreachable, the pipeline continues without classification. Log the failure, but do not block. Core features (Claude ranker, tailoring) may fail closed.

### Schema Additive-Only for Enrichment Columns (Sprint 9)
**Context**: Regime columns were added to `job_listings` as nullable columns.
**Rule**: Enrichment columns added by optional features must be nullable with no default constraints. Existing queries must not break when enrichment columns are NULL.

### PDF Generation Isolation (Sprint 10)
**Context**: The `src/document/` module was added as a fully independent package.
**Rule**: The document generation pipeline must not import from or modify the tailoring engine. They share data via Pydantic models only, never via direct function calls.

## Files That Must Not Be Modified Without Explicit Permission

These files are architecturally load-bearing. Changing them without understanding the full dependency chain will break downstream systems:

| File | Why |
|------|-----|
| `src/tailoring/engine.py` | Semantic fidelity guardrail v1.1 — rejects hallucinated metrics |
| `src/tailoring/models.py` | Pydantic contracts used by engine, persistence, and export |
| `src/models/entities.py` | Pydantic models used by every pipeline stage |
| `src/models/compat.py` | Backend detection used by database.py, init_db, CI |
| `src/models/schema.sql` | SQLite DDL — must match `schema_postgres.sql` and `db_models.py` |
| `src/models/schema_postgres.sql` | PostgreSQL DDL — must match `schema.sql` and `db_models.py` |
