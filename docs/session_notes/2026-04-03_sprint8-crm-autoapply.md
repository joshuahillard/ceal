# Ceal Session Notes — Friday April 3, 2026

**Session type:** Sprint execution
**AI platform:** Codex
**Commit(s):** Not committed yet

## Objective
Reimplement the missing CRM and auto-apply surfaces on `main` using the locked reference copy at `C:\Users\joshb\Documents\GitHub\ceal\` as the sole feature source. Deliver the state machines, persistence, deterministic prefill engine, web routes/templates, and real-SQL integration coverage without inventing behavior.

## Tasks Completed
| # | Task | Files | Status |
|---|------|-------|--------|
| 1 | Added CRM and auto-apply entities, schema tables, indexes, and triggers | `src/models/entities.py`, `src/models/schema.sql`, `src/models/schema_postgres.sql` | Complete |
| 2 | Ported CRM and approval-queue database queries with portable ordering and idempotent application upserts | `src/models/database.py` | Complete |
| 3 | Rebuilt deterministic ATS prefill package from the reference copy | `src/apply/__init__.py`, `src/apply/prefill.py` | Complete |
| 4 | Wired CRM Kanban, reminders, approval queue, and review routes into the FastAPI app | `src/web/app.py`, `src/web/routes/dashboard.py`, `src/web/routes/applications.py`, `src/web/routes/apply.py` | Complete |
| 5 | Extended the UI for Applications and Auto-Apply without regressing existing branding or pages | `src/web/templates/base.html`, `src/web/templates/dashboard.html`, `src/web/templates/jobs.html`, `src/web/templates/applications.html`, `src/web/templates/reminders.html`, `src/web/templates/approval_queue.html`, `src/web/templates/application_review.html`, `src/web/static/style.css` | Complete |
| 6 | Added unit coverage for CRM, auto-apply, and expanded dashboard/jobs behavior | `tests/unit/test_crm.py`, `tests/unit/test_autoapply.py`, `tests/unit/test_web.py` | Complete |
| 7 | Added real SQLite roundtrip coverage for CRM and auto-apply raw SQL paths | `tests/integration/test_crm_autoapply_roundtrip.py` | Complete |
| 8 | Resolved remaining Starlette `TemplateResponse` deprecation warnings in the web layer | `src/web/routes/jobs.py`, `src/web/routes/demo.py` | Complete |

## Files Changed
- `src/apply/__init__.py` — 1 line — package marker for auto-apply logic
- `src/apply/prefill.py` — 146 lines — deterministic resume-to-ATS prefill engine
- `src/models/entities.py` — 283 lines — added application enums and Pydantic models
- `src/models/database.py` — 852 lines — added CRM/application state machines and queries
- `src/models/schema.sql` — 256 lines — added SQLite CRM/application tables, indexes, and trigger
- `src/models/schema_postgres.sql` — 282 lines — added PostgreSQL CRM/application tables, indexes, and trigger
- `src/web/app.py` — 49 lines — registered CRM and auto-apply routers
- `src/web/routes/dashboard.py` — 28 lines — expanded dashboard context with CRM/apply summaries
- `src/web/routes/demo.py` — 127 lines — converted remaining template responses to request-first form
- `src/web/routes/jobs.py` — 27 lines — converted template response to request-first form
- `src/web/routes/applications.py` — 75 lines — CRM Kanban and reminders routes
- `src/web/routes/apply.py` — 65 lines — prefill, approval queue, and review routes
- `src/web/templates/base.html` — 27 lines — added Applications and Auto-Apply nav links
- `src/web/templates/dashboard.html` — 115 lines — added Application Pipeline, Auto-Apply Pipeline, and reminders cards
- `src/web/templates/jobs.html` — 78 lines — added `Pre-Fill` action column
- `src/web/templates/applications.html` — 69 lines — Kanban board UI
- `src/web/templates/reminders.html` — 56 lines — stale follow-up reminders UI
- `src/web/templates/approval_queue.html` — 102 lines — approval queue UI
- `src/web/templates/application_review.html` — 139 lines — application review screen
- `src/web/static/style.css` — 296 lines — CRM/apply board, queue, status, and confidence styling
- `tests/unit/test_web.py` — 227 lines — updated dashboard mocks and `Pre-Fill` assertion
- `tests/unit/test_crm.py` — 187 lines — CRM state machine, route, and stale-query tests
- `tests/unit/test_autoapply.py` — 451 lines — prefill, application persistence, route, and model tests
- `tests/integration/test_crm_autoapply_roundtrip.py` — 222 lines — real SQL schema and roundtrip coverage

## Test Results
| Metric | Value |
|--------|-------|
| Total tests | 220 |
| Passed | 220 |
| Failed | 0 |
| Lint errors | 0 |

## Architecture Decisions
- Kept the implementation reference-locked to the old GitHub copy and current `main`; no CRM/apply behavior was added beyond the documented field sets, statuses, routes, and templates.
- Rewrote reference `NULLS LAST` ordering into portable `CASE WHEN ... IS NULL THEN 1 ELSE 0 END` ordering so the same SQL works on SQLite and PostgreSQL.
- Made `create_application()` idempotent on `(job_id, profile_id)` with a deterministic follow-up `SELECT id ...` instead of relying on backend-specific `RETURNING` behavior.
- Preserved deterministic-only prefill behavior: regex extraction plus the four explicit profile defaults, with no LLM calls, ATS automation, or invented applicant content.
- Synced CRM and approval flow by moving the parent job to `applied` when an application is approved, matching the reference state-machine behavior.
- Standardized all remaining web `TemplateResponse` call sites to Starlette's request-first signature so the suite runs without deprecation warnings.

## What's NOT in This Session
- No browser automation or submission to external ATS platforms
- No LLM-generated cover letters or inferred applicant prose
- No `document_templates` or `generated_documents` reintroduction
- No changes to `src/tailoring/engine.py` or `src/tailoring/models.py`
- No commit, tag, or push yet

## Career Translation (X-Y-Z Bullet)
> Accomplished CRM and approval-flow recovery on `main` as measured by 41 net-new tests and a clean 220/220 passing suite, by porting the missing job-tracking and deterministic auto-apply surfaces from a locked reference implementation into portable SQLite/PostgreSQL-safe code.
