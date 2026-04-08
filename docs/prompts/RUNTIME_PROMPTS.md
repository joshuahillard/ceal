# Ceal Runtime Prompts
**Copy-paste blocks for AI sessions. Nothing in this file is for humans to read — it's all model input.**
*Version: 1.1 | April 3, 2026*

---

## CORE CONTRACT

Paste once at session start. Stable across sprints — only update when the stack or rules change.

```
CEAL CORE v1.1

Project: Ceal is an async career-signal engine for job listings.
Core flow: Scrape -> Normalize -> Rank.
Extended modules: tailoring, CRM, auto-apply, PDF generation.
Web UI: FastAPI + Jinja2 (6 routes + health).

Stack: Python 3.10+, FastAPI/Jinja2, asyncio/aiohttp, Pydantic v2,
SQLAlchemy 2.0 async, SQLite dev (WAL) / PostgreSQL prod (Cloud SQL),
Docker, GitHub Actions CI, Claude API via httpx, Vertex AI.

Rules:
- Read each file before editing it. Search before assuming symbols exist.
- Pydantic v2 at module boundaries. No raw dict payloads across modules.
- LLM output is untrusted. Parse JSON, validate fields and score bounds.
- DB writes are idempotent (ON CONFLICT). No duplicate records.
- Keep diffs minimal and local to the task.
- PowerShell 5 compatible ($env: syntax, no BOM encoding).
- Run targeted verification and report what actually passed.
- Ask one brief question only if ambiguity creates material risk.

Key paths:
- Pipeline: src/pipeline.py, src/scraper/, src/normalizer.py, src/ranker/
- Tailoring: src/tailoring/ (models, parser, extractor, engine)
- Web: src/web/ (app.py, routes/, templates/)
- DB: src/models/ (database.py, schema.sql, schema_postgres.sql, compat.py)
- Tests: tests/unit/, tests/integration/
- Docs: docs/ai-onboarding/
```

---

## TASK CARD TEMPLATE

One per unit of work. Fill in and paste after the Core Contract.

```
TASK: [short title]

Goal: [what and why, 1-2 sentences]
Scope: [what's in bounds]
Out of scope: [what to leave alone]

Inspect first:
- path/to/file.py::SymbolName
- path/to/other.py::function_name
- [max 3-5 references]

Acceptance:
- [testable outcome 1]
- [testable outcome 2]
- [testable outcome 3]

Verify:
- [targeted test command or check, specific to this task]
- [second check if needed]

Deliver:
- implement changes
- summarize touched files
- report verification honestly
```

---

## MODE PACKS

Append one or more after the Task Card when the task enters a specific domain.

### MODE: db
```
MODE: db
- All writes use ON CONFLICT upserts. No duplicates, no lock contention.
- Schema changes go in BOTH schema.sql and schema_postgres.sql.
- Use WAL mode for SQLite. Connection pooling for PostgreSQL.
- Migrations via Alembic. Test migration up and down.
- Verify with targeted DB integration tests, not just mocked returns.
- Never await sync methods (e.g., result.scalar() is sync). Match await to actual coroutines.
- PostgreSQL gotchas: ROUND() requires CAST(x AS numeric), CREATE TRIGGER must not be split across statements in schema loaders.
```

### MODE: ml
```
MODE: ml
- Version any prompt change and log to RANKER_VERSION / prompt registry.
- Strip markdown code fences before JSON parsing.
- Validate all fields: scores 0.0-1.0, booleans verified structurally.
- Test: empty response, malformed JSON, timeout, 429 handling.
- Enrichment features fail open (return None). Core features fail closed (raise).
- Use frozen fixtures in unit tests. Never live API calls.
```

### MODE: web
```
MODE: web
- Routes return proper HTTP status codes (200, 400, 404, 500).
- Form inputs validated server-side. Empty strings -> None conversion.
- Templates extend base.html. No inline styles.
- Test routes with httpx AsyncClient against real DB where SQL matters.
- Health endpoint at /health always returns 200 with status JSON.
```

### MODE: product
```
MODE: product
- Owner: Josh Hillard, targeting Google L5 TPM / Stripe-Datadog TSE.
- Every feature must map to Tier 1/2/3 role strategy.
- Frame output as X-Y-Z bullet: "Accomplished [X] measured by [Y] by doing [Z]."
- Career narrative coherence: can this be explained in 60 seconds to a hiring manager?
- Update CEAL_PROJECT_LEDGER.md after shipping.
```

### MODE: infra
```
MODE: infra
- Docker images build in < 3 min. Health check required.
- CI must pass before merge (lint + targeted tests + docker build).
- All config externalized via env vars. No hardcoded secrets.
- Every deployment needs a documented rollback procedure.
- Update .env.example when adding new env vars.
```

---

## SNAPSHOT (optional)

Attach only when the task depends on volatile repo state.

```
SNAPSHOT:
- Branch: main | Tag: v2.10.0-sprint10-pdf-generation
- Tests: 246 passing, 0 warnings, ruff clean
- Known issues: [list any relevant failing tests, open bugs, or blockers]
- Recent context: [1-2 sentences if prior work in this session matters]
```

---

## CONTINUATION (for multi-message tasks)

When a task spans multiple messages, keep continuations minimal.

```
Continue from commit [hash].
[Part/step] done. Now: [next objective].
State: [1-2 sentences of what changed].
```

---

## EXAMPLES

### Example 1: Simple route fix (Core + Task Card only, ~500 tokens)
```
CEAL CORE v1.1
[...core contract...]

TASK: Fix jobs tab tier filter crash

Goal: Empty tier dropdown sends tier="" which crashes the route. Convert empty string to None server-side.
Scope: src/web/routes/jobs.py, tests/unit/test_web.py
Out of scope: Dashboard, demo, other routes.

Inspect first:
- src/web/routes/jobs.py::get_jobs
- tests/unit/test_web.py::test_jobs

Acceptance:
- GET /jobs?tier= returns 200 with all jobs (no crash)
- GET /jobs?tier=1 still filters correctly
- Existing jobs route tests pass

Verify:
- python -m pytest tests/unit/test_web.py -v -k "jobs"
- ruff check src/web/routes/jobs.py

Deliver:
- implement changes
- summarize touched files
- report verification honestly
```

### Example 2: ML integration task (Core + Task Card + MODE: ml, ~660 tokens)
```
CEAL CORE v1.1
[...core contract...]

TASK: Add semantic fidelity check to tailoring engine

Goal: Verify LLM-generated bullets don't fabricate skills the candidate doesn't have.
Scope: src/tailoring/engine.py, tests/unit/test_tailoring_engine.py
Out of scope: Ranker scoring, regime classification.

Inspect first:
- src/tailoring/engine.py::TailoringEngine
- src/tailoring/engine.py::_generate_bullets
- src/tailoring/models.py::TailoredBullet

Acceptance:
- Bullets referencing skills not in parsed resume are flagged
- Flagged bullets get relevance_score reduced by 0.3
- New test covers fabricated-skill detection

Verify:
- python -m pytest tests/unit/test_tailoring_engine.py -v
- ruff check src/tailoring/

Deliver:
- implement changes
- summarize touched files
- report verification honestly

MODE: ml
[...ml mode pack...]
```

### Example 3: Multi-message sprint (Core + Task Card + continuation)
```
Message 1:
CEAL CORE v1.1
[...core contract...]

TASK: Sprint 11 — Alembic migration system

Goal: Replace manual schema.sql with Alembic-managed migrations for both SQLite and PostgreSQL.
Scope: alembic/, src/models/database.py, schema files
Out of scope: Web routes, tailoring engine, CLI flags.

[...task card...]

SNAPSHOT:
- Branch: main | Tag: v2.10.0-sprint10-pdf-generation
- Tests: 246 passing
- Known issues: CREATE TABLE IF NOT EXISTS doesn't ALTER for new columns (TD-003)

Implement Part A only: Alembic config + initial migration. Stop after committing.

---

Message 2:
Continue from commit abc1234.
Part A done (Alembic config + initial migration committed). Now: Part B — migration for Sprint 9 regime columns.
State: alembic/ directory exists, env.py configured for both SQLite and PostgreSQL.

---

Message 3:
Continue from commit def5678.
Parts A and B done. Now: Part C — update database.py to use Alembic on startup, full test suite, final commit.
State: 2 migrations exist (initial + regime columns). Need to wire auto-migrate into app startup.
```

---

*Runtime prompts v1.1. See MASTER_PROMPT_ARCHITECTURE.md for design rationale.*
