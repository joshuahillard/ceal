# Céal — Engineering Rules
**Hard constraints that apply to every task, every sprint, every AI session**
*Last updated: April 16, 2026 — merged from top-level + in-repo drafts, Sprints 9-10 additions preserved*

---

## Cross-Reference

These rules apply to ALL AI assistants working on Céal (Claude, Codex, Gemini). Each one was learned the hard way.

The Core Contract in `docs/prompts/RUNTIME_PROMPTS.md` contains a compact runtime-formatted version of Part I rules (~300 tokens) for pasting into AI sessions. This file is the expanded reference with rationale, incident history, and codebase constraints. **Both must stay in sync** — if a Part I rule changes here, update the Core Contract too.

---

## Part I — AI Session Meta-Rules (Core Contract v1.1)

These rules govern how AI assistants operate within a session. They are pasted into every session via the Core Contract.

| # | Rule | Rationale |
|---|------|-----------|
| 1 | Read each file before editing it. Search before assuming symbols exist. | Prevents fabricated code references. AI models confidently reference functions that don't exist. Files may also have been modified by another AI assistant since the last session. |
| 2 | Pydantic v2 at module boundaries. No raw dict payloads across modules. | Zero-defect culture. Runtime type checking catches what static typing misses, especially with LLM JSON. |
| 3 | LLM output is untrusted. Parse JSON, validate fields and score bounds. | Claude claimed `xyz_format: true` on malformed bullets (Sprint 1 incident). Never trust LLM self-assessment. |
| 4 | DB writes are idempotent (ON CONFLICT). No duplicate records. | Running the scraper 10x must produce the same DB state. Duplicates corrupt every downstream query. |
| 5 | Keep diffs minimal and local to the task. | Prevents scope creep. A bug fix shouldn't also refactor the module. |
| 6 | PowerShell 5 compatible (`$env:` syntax, no BOM encoding). | Dev environment is Windows. BOM encoding broke `.env` in Sprint 1. |
| 7 | Run targeted verification and report what actually passed. | "All tests pass" is meaningless without the command and count. Report honestly. |
| 8 | Ask one brief question only if ambiguity creates material risk. | Minimize back-and-forth. Most ambiguity can be resolved by reading the code. |
| 9 | Do not fabricate file paths, function names, or test results. | AI hallucination is the #1 failure mode. If uncertain, search first. |
| 10 | Do not modify `schema.sql` without also updating `schema_postgres.sql`. | Dual-schema system (ADR-003). SQLite dev and PostgreSQL prod must stay in sync. |

---

## Part II — Codebase Constraints

Concrete rules that apply to Céal's specific Python/FastAPI/SQLAlchemy stack.

### 1. No File Duplication
Do NOT create new files that duplicate existing functionality. Canonical files are listed in `PROJECT_CONTEXT.md`. Check for existing functionality before adding a file.

### 2. Python 3.10+ Target
- Do NOT use `datetime.UTC` → use `datetime.timezone.utc`
- Do NOT use `StrEnum` → use `str, Enum`
- Do NOT use `match` statements → use `if/elif`
- Do NOT use `X | Y` union syntax in function signatures without `from __future__ import annotations`

### 3. Import Paths
All imports use `src.` prefix:
```python
from src.models.database import get_session
from src.models.compat import is_sqlite
from src.tailoring.models import TailoringResult
```
The project uses `pythonpath = ["."]` in `pyproject.toml`.

### 4. Async Everywhere
- Database uses `AsyncSession` via `aiosqlite` (SQLite) or `asyncpg` (PostgreSQL)
- All database functions are `async def`
- All FastAPI routes are `async def`
- All async tests need `@pytest.mark.asyncio` decorator

### 5. No Dialect-Specific SQL in Shared Paths
All raw SQL in `database.py` must work on BOTH SQLite and PostgreSQL, OR must be behind a backend-detection branch:
```python
from src.models.compat import is_sqlite
if is_sqlite():
    # SQLite-specific SQL
else:
    # PostgreSQL-specific SQL
```

### 6. No Secrets in Code
- Never hardcode API keys, passwords, or credentials
- Use `.env` + `python-dotenv`
- `.env` is in `.gitignore`
- `.env.example` documents required variables without values

### 7. Ruff Configuration
```
target-version = "py310"
line-length = 120
```
Ignored rules: `UP017`, `UP042`, `E501`, `SIM102`, `SIM105`, `SIM108`, `B017`, `B904`

### 8. Test Isolation
- StaticPool in-memory SQLite for unit tests
- All sessions share the same in-memory connection
- `@pytest.mark.asyncio` with `asyncio_mode = "strict"`

### 9. Dual-Backend Testing
For any database function containing raw SQL, write a database-level test exercising real SQL — not just a mock. **This rule exists because mock-only tests hid SQL bugs three times** (see the Jobs Tab incident in Part III).

---

## Part III — Incident-Driven Rules

Rules that emerged from specific failures during development. Organized chronologically.

### From Phase 1 (March 28-29, 2026)

**Rule 11: Validate LLM boolean claims structurally.**
- *Incident:* Claude API returned `xyz_format: true` on bullets that lacked the "by doing [Z]" clause.
- *Rule:* Check the actual text for structural markers. Don't trust the LLM's boolean self-report.
- *ADR:* ADR-004 (LLM Output Treated as Untrusted Input)

### From Sprint 1 (April 1, 2026)

**Rule 12: Never use `echo` for file writes on Windows.**
- *Incident:* PowerShell `echo` added BOM encoding to `.env`, corrupting the file for Python.
- *Rule:* Use Python for all file writes. `echo` / `cat >` is unsafe on Windows.

**Rule 13: Rotate API keys immediately if exposed in any chat or log.**
- *Incident:* API key accidentally pasted into a chat session.
- *Rule:* Key rotation is immediate, not "when convenient."

### From Sprint 6 (April 2, 2026)

**Rule 14: Never force-push without a backup branch.**
- *Incident:* `main` was reset to `codex/semantic-fidelity-guardrail`, losing Sprints 2-5 commit history. Had to reimplement Docker + Cloud SQL from scratch.
- *Rule:* Before any force-push: `git branch backup-[date]` first. Tag before any destructive operation. Use merge or cherry-pick instead of reset when reconciling branches.
- *ADR:* ADR-008 (Branch Reset Recovery Strategy)

### From Sprint 9 (April 3, 2026)

**Rule 15: Enrichment features fail open; core features fail closed.**
- *Incident:* Vertex AI regime classification was designed as an enrichment — it should never block the pipeline.
- *Rule:* Optional enrichments (Vertex AI, etc.) return `None` on any failure. Core pipeline stages (scrape, normalize, rank) raise exceptions on failure.
- *ADR:* ADR-007 (Vertex AI Fail-Open Architecture)

**Rule 16: Version every LLM prompt change and log it.**
- *Rule:* Every prompt modification gets a version bump (`PROMPT_VERSION`, `RANKER_VERSION`, or equivalent). Log the version alongside output for A/B testing. Track in `docs/prompts/PROMPT_REGISTRY.md`.

**Rule 16b: Schema additive-only for enrichment columns.**
- *Context:* Regime columns were added to `job_listings` as nullable columns.
- *Rule:* Enrichment columns added by optional features must be nullable with no default constraints. Existing queries must not break when enrichment columns are NULL.

### From Sprint 10 (April 3, 2026)

**Rule 17: Mock-only route tests are insufficient for SQL-dependent routes.**
- *Incident:* Jobs tab had a SQL bug (LEFT JOIN caused submitted applications to reappear in the jobs list) that mock-only route tests didn't catch. The bug recurred three times because mock tests kept passing. Required post-sprint hotfix.
- *Rule:* Routes that execute SQL queries need at least one integration test hitting a real database. Mock tests verify routing logic; DB tests verify query correctness.
- *Tech debt:* TD-001 (open)

**Rule 18: `CREATE TABLE IF NOT EXISTS` doesn't ALTER existing tables.**
- *Incident:* Sprint 9 regime columns weren't added to existing databases because `CREATE TABLE IF NOT EXISTS` skips if the table already exists.
- *Rule:* New columns on existing tables require Alembic migrations or explicit `ALTER TABLE` statements.
- *Tech debt:* TD-003 (open)

**Rule 19: PDF generation isolation.**
- *Context:* The `src/document/` module was added as a fully independent package.
- *Rule:* The document generation pipeline must not import from or modify the tailoring engine. They share data via Pydantic models only, never via direct function calls.

### Recurring / Cross-Sprint Incidents

**The `datetime.UTC` break.**
- *Incident:* Tests used `datetime.UTC` which requires Python 3.11+. CI ran on 3.10 and failed.
- *Rule:* Always use `datetime.timezone.utc`. The ruff rule `UP017` is ignored specifically for this.

**The `db_models.py` truncation.**
- *Incident:* A file write was interrupted, cutting off `SkillGapTable` mid-comment. The missing `UniqueConstraint` caused `ON CONFLICT` failures at runtime.
- *Rule:* After writing any file, verify it with a Python import or syntax check. Confirm the file ends properly.

---

## Part IV — Protected Files

These files are architecturally load-bearing. Changing them without understanding the full dependency chain will break downstream systems. All six paths verified against current `src/` tree as of April 16, 2026.

| File | Why |
|------|-----|
| `src/tailoring/engine.py` | Semantic Fidelity Guardrail v1.1 — rejects hallucinated metrics |
| `src/tailoring/models.py` | Pydantic contracts used by engine, persistence, and export |
| `src/models/entities.py` | Pydantic models used by every pipeline stage |
| `src/models/compat.py` | Backend detection used by `database.py`, `init_db`, CI |
| `src/models/schema.sql` | SQLite DDL — must match `schema_postgres.sql` and `db_models.py` |
| `src/models/schema_postgres.sql` | PostgreSQL DDL — must match `schema.sql` and `db_models.py` |

---

## Part V — Mode-Specific Rules

These apply only when working in specific domains. They live in Mode Packs (see `docs/prompts/RUNTIME_PROMPTS.md`):

| Mode | Key Rules |
|------|-----------|
| `MODE: db` | ON CONFLICT upserts, dual schema files, WAL mode, Alembic migrations, test with real DB |
| `MODE: ml` | Version prompts, strip code fences, validate scores 0.0-1.0, frozen fixtures, enrichment fails open |
| `MODE: web` | Proper HTTP codes, server-side validation, extend `base.html`, test with `httpx.AsyncClient` |
| `MODE: product` | Map to Tier 1/2/3, frame as X-Y-Z bullet, update ledger |
| `MODE: infra` | Docker < 3 min build, CI before merge, config via env vars, rollback documented |

---

## Rule Sync Checklist

When adding a new rule:

1. Add it to this file with incident context (Part III) or the appropriate constraint section (Part II).
2. If it's a universal meta-rule, add it to the Core Contract in `docs/prompts/RUNTIME_PROMPTS.md` (Part I).
3. If it's domain-specific, add it to the appropriate Mode Pack in `docs/prompts/RUNTIME_PROMPTS.md` (Part V).
4. If it's architecturally significant, log an ADR in `docs/CEAL_PROJECT_LEDGER.md`.
5. Update `CLAUDE.md` if the Core Contract changed.

---

*Rules maintained by: QA Lead + Backend Engineer personas*
*Cross-reference: Core Contract in `docs/prompts/RUNTIME_PROMPTS.md`, ADRs in `docs/CEAL_PROJECT_LEDGER.md`, prompt versioning in `docs/prompts/PROMPT_REGISTRY.md`*
