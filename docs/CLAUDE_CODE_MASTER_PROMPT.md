# Claude Code Master Prompt — Ceal Project
**Paste as Claude Code custom instructions or CLAUDE.md**
*Version: 1.1 | April 3, 2026*

---

## Core Contract

You are working on Ceal, an async career-signal engine for job listings.
Core flow: Scrape -> Normalize -> Rank. Extended modules: tailoring, CRM, auto-apply, PDF generation. Web UI: FastAPI + Jinja2 (6 routes + health).

Stack: Python 3.10+, FastAPI/Jinja2, asyncio/aiohttp, Pydantic v2, SQLAlchemy 2.0 async, SQLite dev (WAL) / PostgreSQL prod (Cloud SQL), Docker, GitHub Actions CI, Claude API via httpx, Vertex AI.

Rules:
1. Read each file before editing it. Search before assuming symbols exist.
2. Pydantic v2 at module boundaries. No raw dict payloads across modules.
3. LLM output is untrusted. Parse JSON, validate fields and score bounds before use.
4. DB writes are idempotent (ON CONFLICT). No duplicate records.
5. Keep diffs minimal and local to the task.
6. PowerShell 5 compatible ($env: syntax, no BOM encoding).
7. Run targeted verification and report what actually passed.
8. Ask one brief question only if ambiguity creates material risk.
9. Do not fabricate file paths, function names, or test results.
10. Do not modify schema.sql without also updating schema_postgres.sql.

Key paths:
- Pipeline: src/pipeline.py, src/scraper/, src/normalizer.py, src/ranker/
- Tailoring: src/tailoring/ (models, parser, extractor, engine)
- Web: src/web/ (app.py, routes/, templates/)
- DB: src/models/ (database.py, schema.sql, schema_postgres.sql, compat.py)
- Tests: tests/unit/, tests/integration/
- Docs: docs/ai-onboarding/

Full project context: docs/ai-onboarding/PROJECT_CONTEXT.md (read before first task).

## Mode Packs (activate per task)

**MODE: db** — ON CONFLICT upserts, dual schema files, WAL mode, Alembic migrations, test with real DB not mocks.

**MODE: ml** — Version prompt changes, strip code fences, validate scores 0.0-1.0, verify booleans structurally, frozen fixtures, enrichment fails open / core fails closed.

**MODE: web** — Proper HTTP status codes, server-side form validation, extend base.html, test with httpx AsyncClient, /health always 200.

**MODE: product** — Owner is Josh Hillard (Google L5 TPM / Stripe TSE targets). Map features to Tier 1/2/3 strategy. Frame as X-Y-Z bullets. Update project ledger.

**MODE: infra** — Docker < 3 min build, CI before merge, config via env vars, rollback documented, update .env.example.

Full mode pack text: docs/RUNTIME_PROMPTS.md

## Task Format

Tasks follow this structure:
```
TASK: [title]
Goal: [what and why]
Scope: [in bounds]  |  Out of scope: [leave alone]
Inspect first: path::symbol (max 3-5)
Acceptance: [testable outcomes]
Verify: [targeted checks]
```

## Session Close Protocol

At session end, produce:
1. Summary: what changed, files touched, verification results
2. Updated test count if tests were added
3. Any new technical debt identified
4. Suggest NotebookLM sync if new artifacts were created

## Key Documents

| Doc | Location |
|-----|----------|
| Project Context | docs/ai-onboarding/PROJECT_CONTEXT.md |
| Project Ledger | docs/CEAL_PROJECT_LEDGER.md |
| Runtime Prompts | docs/RUNTIME_PROMPTS.md |
| Prompt Architecture | docs/MASTER_PROMPT_ARCHITECTURE.md |
| Persona Library | docs/PORTABLE_PERSONA_LIBRARY.md |
| Anti-Hallucination Rules | docs/ai-onboarding/RULES.md |
