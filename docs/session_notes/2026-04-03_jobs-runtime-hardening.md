# Ceal Session Notes — Friday April 3, 2026

**Session type:** Runtime stabilization / Jobs tab hardening
**AI platform:** Codex
**Commit(s):** Pending current commit

## Objective
Stabilize the web runtime after Sprint 10 by fixing startup issues tied to older local SQLite files, making auto-apply resilient on fresh databases, and hardening the Jobs tab so live refresh remains usable even when filters are blank or LLM credentials fail.

## Tasks Completed
| # | Task | Files | Status |
|---|------|-------|--------|
| 1 | Repair additive SQLite schema drift during startup | `src/models/database.py` | Done |
| 2 | Seed and recover the default resume profile used by auto-apply | `src/models/database.py` | Done |
| 3 | Ensure application creation recreates the default profile when missing | `src/models/database.py` | Done |
| 4 | Return stable row IDs from job upserts | `src/models/database.py` | Done |
| 5 | Add Jobs-page fallback queries for ranked + unranked listings | `src/models/database.py` | Done |
| 6 | Replace strict Jobs query parsing with safe manual parsing | `src/web/routes/jobs.py` | Done |
| 7 | Run live LinkedIn refresh on Jobs page load with cached fallback | `src/web/routes/jobs.py` | Done |
| 8 | Fail open when Anthropic rejects the configured key | `src/web/routes/jobs.py` | Done |
| 9 | Remove `/jobs` redirect dependency in nav and form actions | `src/web/routes/jobs.py`, `src/web/templates/base.html`, `src/web/templates/jobs.html` | Done |
| 10 | Add UI messaging for live refresh state and pending scores | `src/web/templates/jobs.html`, `src/web/static/style.css` | Done |
| 11 | Add regression coverage for startup recovery and Jobs-tab failures | `tests/unit/test_database.py`, `tests/unit/test_web.py`, `tests/integration/test_crm_autoapply_roundtrip.py` | Done |
| 12 | Append post-release hardening details to Sprint 10 sign-off note | `docs/session_notes/2026-04-03_sprint10-release-signoff.md` | Done |

## Files Changed
- `src/models/database.py` — added legacy SQLite reconciliation, default resume profile seeding/recovery, stable upsert row-ID lookup, Jobs-page query helpers
- `src/web/routes/jobs.py` — added safe filter parsing, live refresh on page load, cached fallback, LLM auth fail-open behavior, direct `/jobs` support
- `src/web/templates/base.html` — updated Jobs nav link to canonical route
- `src/web/templates/jobs.html` — added live refresh summary, query/location controls, warning handling, pending score rendering
- `src/web/static/style.css` — added filter input styling and neutral badge styling
- `tests/unit/test_database.py` — added schema-repair, default-profile, and Jobs-query regression tests
- `tests/unit/test_web.py` — added Jobs filter, direct route, live query, and Anthropic-auth failure regression tests
- `tests/integration/test_crm_autoapply_roundtrip.py` — added application/profile recovery integration coverage
- `docs/session_notes/2026-04-03_sprint10-release-signoff.md` — appended Jobs-tab hardening addendum

## Test Results
| Metric | Value |
|--------|-------|
| Total tests | 295 |
| Passed | 295 |
| Failed | 0 |
| Lint errors | 0 |
| Live `/jobs` smoke test | 200 OK |
| Live `/jobs?tier=` smoke test | 200 OK |

## Architecture Decisions
- **SQLite additive repair before schema replay:** existing local DB files are reconciled before indexes run so older files do not crash startup when new columns are added.
- **Default profile as a runtime invariant:** auto-apply now treats `resume_profiles.id = 1` as recoverable state rather than assuming it already exists.
- **Jobs page as live-search surface:** the Jobs tab now refreshes the current query and location on load instead of behaving like a static report over stale rows.
- **Fail-open ranking behavior:** rejected Anthropic credentials disable ranking for the current process and keep fresh jobs visible with pending scores instead of producing repeated per-job failures.
- **Route-level filter parsing:** blank form values are normalized before validation so the Jobs UI cannot be taken down by empty query-string fields.

## What's NOT in This Session
- No changes to the tailoring engine or tailoring models
- No changes to the `.docx` export path
- No change to the PDF generators themselves
- No attempt to add browser automation or ATS submission

## Career Translation (X-Y-Z Bullet)
> Hardened the live job-search and application runtime as measured by 295 passing tests and successful live `/jobs` smoke tests, by repairing legacy SQLite startup drift, recovering default resume profile state, and making live ranking fail open when external credentials are invalid.
