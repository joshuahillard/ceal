# Ceal Sprint 8 - CRM + Auto-Apply Reimplementation (Reference-Locked)

## CONTEXT

You are working on the Ceal project - an AI-powered career signal engine.
The project root is the `ceal/` directory containing `src/`, `tests/`, `pyproject.toml`, and `requirements.txt`.

Read these onboarding docs before starting:
- `docs/ai-onboarding/PROJECT_CONTEXT.md`
- `docs/ai-onboarding/PERSONAS.md`
- `docs/ai-onboarding/RULES.md`
- `docs/ai-onboarding/DEBRIEF_TEMPLATE.md`

Recent commits on `main`:
- `1a23012` docs: add mandatory session notes rule to all AI prompts + debrief template
- `8344b67` docs: add continuation session notes (merge + multi-AI onboarding)
- `3b89465` docs: add multi-AI onboarding package for Claude, Codex, and Gemini
- `98177d4` feat: Docker + polymorphic Cloud SQL support (Sprint 6)
- `a123b96` fix: add Phase 2 DDL to schema.sql, add persistence integration test

Current `main` contains:
- Phase 1 pipeline: scrape -> normalize -> rank
- Phase 2 tailoring engine, persistence, demo mode, batch mode, export
- Sprint 1 web UI: dashboard, jobs, demo, health
- Sprint 6 infra: Docker, SQLite/PostgreSQL compatibility, health endpoint

Current `main` does NOT contain:
- CRM routes and Kanban board
- stale follow-up reminders
- auto-apply approval queue
- prefill engine package

Authoritative reference for the missing CRM and auto-apply features exists on Josh's machine at:
`C:\Users\joshb\Documents\GitHub\ceal\`

For this sprint, the ONLY authoritative source for missing product behavior is the combination of:
- current `main`
- the reference files listed below from `C:\Users\joshb\Documents\GitHub\ceal\`
- the repo rules in `docs/ai-onboarding/RULES.md`

If a route, field, enum, SQL clause, or UI behavior is not provable from those sources, STOP and report it. Do NOT invent it.

Explicit permission is granted for this sprint to modify these normally protected files:
- `src/models/entities.py`
- `src/models/schema.sql`
- `src/models/schema_postgres.sql`

This sprint's scope:
- Reimplement the CRM Kanban board and job status state machine
- Reimplement stale reminder views and supporting queries
- Reimplement the deterministic auto-apply prefill engine
- Reimplement the approval queue, review screen, and application status state machine
- Add real SQL integration coverage for the new raw SQL paths

This sprint is explicitly OUT OF SCOPE:
- actual browser automation or form submission to external ATS sites
- LLM-generated cover letters or inferred applicant prose
- document template / generated document features from the old reference copy
- changes to `src/tailoring/engine.py`
- changes to `src/tailoring/models.py`
- any new feature not already evidenced by the reference files listed below

Stakeholders active for this sprint:
- DPM (lead)
- Backend Engineer
- AI Architect
- QA Lead
- ETL Architect

## CRITICAL RULES (Anti-Hallucination)

1. READ before WRITE. Before modifying any file, read it first.
2. Reference-locked implementation only. Use the old GitHub copy strictly as a source of truth for CRM and auto-apply surfaces.
3. Do NOT infer user data. If resume text does not contain a field, leave it blank / `None` unless the reference prefill engine provides an explicit default.
4. Do NOT invent ATS fields. The authoritative field set is `COMMON_ATS_FIELDS` from the reference `src/apply/prefill.py`.
5. Do NOT invent status values. Use only:
   - Job CRM statuses: `scraped`, `ranked`, `applied`, `responded`, `interviewing`, `offer`, `rejected`, `archived`
   - Auto-apply statuses: `draft`, `ready`, `approved`, `submitted`, `withdrawn`
6. Do NOT reintroduce unrelated reference features. In particular, do NOT port `document_templates` or `generated_documents` in this sprint.
7. Preserve current-main metadata when the reference is stale. Do NOT blindly overwrite current version strings or branding with the older reference values.
8. All imports must use `src.` prefixes.
9. Python target is 3.10+. No `datetime.UTC`, no `StrEnum`, no `match`.
10. All new SQL must work on BOTH SQLite and PostgreSQL. If the reference SQL uses backend-specific ordering such as `NULLS LAST`, rewrite it to a portable form or branch safely via `compat.py`.
11. Every new raw-SQL database function needs real SQL coverage, not only mocks. The new CRM / auto-apply queries must have at least one integration-level test file against in-memory SQLite.
12. Do NOT modify `src/tailoring/engine.py` or `src/tailoring/models.py`.
13. In touched routes, use the request-first `TemplateResponse(request, "name.html", context={...})` form. Do not add more deprecated call sites.
14. Leave unrelated working tree files alone. If `git status` shows only the existing untracked session notes, do not delete or rewrite them.
15. No secrets in code, no external API calls for prefill, no browser automation, no fabricated cover letters.

## REFERENCE LOCK

Before writing code, read these reference files from the old GitHub copy. These are the allowed feature sources for CRM + auto-apply:

Current repo files:
- `src/models/entities.py`
- `src/models/database.py`
- `src/models/schema.sql`
- `src/models/schema_postgres.sql`
- `src/web/app.py`
- `src/web/routes/dashboard.py`
- `src/web/templates/base.html`
- `src/web/templates/dashboard.html`
- `src/web/templates/jobs.html`
- `src/web/static/style.css`
- `tests/unit/test_web.py`

Reference files:
- `C:\Users\joshb\Documents\GitHub\ceal\src\models\entities.py`
- `C:\Users\joshb\Documents\GitHub\ceal\src\models\database.py`
- `C:\Users\joshb\Documents\GitHub\ceal\src\models\schema.sql`
- `C:\Users\joshb\Documents\GitHub\ceal\src\models\schema_postgres.sql`
- `C:\Users\joshb\Documents\GitHub\ceal\src\apply\prefill.py`
- `C:\Users\joshb\Documents\GitHub\ceal\src\web\app.py`
- `C:\Users\joshb\Documents\GitHub\ceal\src\web\routes\applications.py`
- `C:\Users\joshb\Documents\GitHub\ceal\src\web\routes\apply.py`
- `C:\Users\joshb\Documents\GitHub\ceal\src\web\routes\dashboard.py`
- `C:\Users\joshb\Documents\GitHub\ceal\src\web\templates\base.html`
- `C:\Users\joshb\Documents\GitHub\ceal\src\web\templates\dashboard.html`
- `C:\Users\joshb\Documents\GitHub\ceal\src\web\templates\jobs.html`
- `C:\Users\joshb\Documents\GitHub\ceal\src\web\templates\applications.html`
- `C:\Users\joshb\Documents\GitHub\ceal\src\web\templates\reminders.html`
- `C:\Users\joshb\Documents\GitHub\ceal\src\web\templates\approval_queue.html`
- `C:\Users\joshb\Documents\GitHub\ceal\src\web\templates\application_review.html`
- `C:\Users\joshb\Documents\GitHub\ceal\src\web\static\style.css`
- `C:\Users\joshb\Documents\GitHub\ceal\tests\unit\test_crm.py`
- `C:\Users\joshb\Documents\GitHub\ceal\tests\unit\test_autoapply.py`

## PRE-FLIGHT CHECK

```bash
# 1. Verify working directory
pwd

# 2. Verify branch
git branch --show-current

# 3. Recent commits
git log --oneline -5

# 4. Uncommitted changes
git status
# If the only untracked files are:
#   docs/session_notes/2026-03-30_ci-pipeline.md
#   docs/session_notes/2026-04-02_sprint6-docker-cloudsql.md
# leave them alone and proceed.

# 5. Baseline tests
pytest tests/ -v 2>&1 | tail -20

# 6. Baseline lint
ruff check src/ tests/

# 7. Verify current files that this sprint will modify exist
ls src/models/entities.py
ls src/models/database.py
ls src/models/schema.sql
ls src/models/schema_postgres.sql
ls src/web/app.py
ls src/web/routes/dashboard.py
ls src/web/templates/base.html
ls src/web/templates/dashboard.html
ls src/web/templates/jobs.html
ls src/web/static/style.css
ls tests/unit/test_web.py

# 8. Verify new files do NOT exist yet on current main
ls src/apply/__init__.py 2>/dev/null && echo "WARNING: src/apply/__init__.py exists" || echo "OK: src/apply/__init__.py missing"
ls src/apply/prefill.py 2>/dev/null && echo "WARNING: src/apply/prefill.py exists" || echo "OK: src/apply/prefill.py missing"
ls src/web/routes/applications.py 2>/dev/null && echo "WARNING: applications route exists" || echo "OK: applications route missing"
ls src/web/routes/apply.py 2>/dev/null && echo "WARNING: apply route exists" || echo "OK: apply route missing"
ls src/web/templates/applications.html 2>/dev/null && echo "WARNING: applications template exists" || echo "OK: applications template missing"
ls src/web/templates/reminders.html 2>/dev/null && echo "WARNING: reminders template exists" || echo "OK: reminders template missing"
ls src/web/templates/approval_queue.html 2>/dev/null && echo "WARNING: approval_queue template exists" || echo "OK: approval_queue template missing"
ls src/web/templates/application_review.html 2>/dev/null && echo "WARNING: application_review template exists" || echo "OK: application_review template missing"
ls tests/unit/test_crm.py 2>/dev/null && echo "WARNING: test_crm.py exists" || echo "OK: test_crm.py missing"
ls tests/unit/test_autoapply.py 2>/dev/null && echo "WARNING: test_autoapply.py exists" || echo "OK: test_autoapply.py missing"
ls tests/integration/test_crm_autoapply_roundtrip.py 2>/dev/null && echo "WARNING: CRM/apply integration test exists" || echo "OK: CRM/apply integration test missing"

# 9. Verify the reference files exist before relying on them
ls "C:/Users/joshb/Documents/GitHub/ceal/src/apply/prefill.py"
ls "C:/Users/joshb/Documents/GitHub/ceal/src/web/routes/applications.py"
ls "C:/Users/joshb/Documents/GitHub/ceal/src/web/routes/apply.py"
ls "C:/Users/joshb/Documents/GitHub/ceal/tests/unit/test_crm.py"
ls "C:/Users/joshb/Documents/GitHub/ceal/tests/unit/test_autoapply.py"
```

If any reference file is missing, STOP and report it.

## FILE INVENTORY

### Files to Create (new)

| # | File | Lines (approx) | Purpose |
|---|------|----------------|---------|
| 1 | `src/apply/__init__.py` | ~5 | Package marker for auto-apply logic |
| 2 | `src/apply/prefill.py` | ~170 | Deterministic ATS prefill engine |
| 3 | `src/web/routes/applications.py` | ~90 | CRM Kanban routes and reminders |
| 4 | `src/web/routes/apply.py` | ~95 | Auto-apply queue and review routes |
| 5 | `src/web/templates/applications.html` | ~80 | Kanban board UI |
| 6 | `src/web/templates/reminders.html` | ~55 | Stale application reminders UI |
| 7 | `src/web/templates/approval_queue.html` | ~110 | Approval queue UI |
| 8 | `src/web/templates/application_review.html` | ~150 | Review screen for prefilled applications |
| 9 | `tests/unit/test_crm.py` | ~200 | CRM state machine and route tests |
| 10 | `tests/unit/test_autoapply.py` | ~260 | Prefill, approval queue, and model tests |
| 11 | `tests/integration/test_crm_autoapply_roundtrip.py` | ~150 | Real-SQL CRM/auto-apply roundtrip coverage |

### Files to Modify (existing)

| # | File | Changes |
|---|------|---------|
| 1 | `src/models/entities.py` | Add application enums and Pydantic models from the reference copy |
| 2 | `src/models/database.py` | Add CRM queries, job/application state machines, and auto-apply persistence queries |
| 3 | `src/models/schema.sql` | Add `applications` and `application_fields` tables, indexes, and trigger |
| 4 | `src/models/schema_postgres.sql` | Add PostgreSQL equivalents of `applications` and `application_fields` |
| 5 | `src/web/app.py` | Register `applications` and `apply` routers only; preserve current app metadata |
| 6 | `src/web/routes/dashboard.py` | Add CRM and auto-apply summary context |
| 7 | `src/web/templates/base.html` | Add nav links for Applications and Auto-Apply; preserve current footer/version text |
| 8 | `src/web/templates/dashboard.html` | Add application pipeline, queue summary, and follow-up reminder cards |
| 9 | `src/web/templates/jobs.html` | Add `Apply` column with `Pre-Fill` action |
| 10 | `src/web/static/style.css` | Extend current styles with Kanban, queue, confidence, and status UI classes |
| 11 | `tests/unit/test_web.py` | Update dashboard mocks/assertions for the expanded dashboard context |

## TASK 0: Read All Files That Will Be Modified

Before writing ANY code, read these current-main files in full:

```text
src/models/entities.py
src/models/database.py
src/models/schema.sql
src/models/schema_postgres.sql
src/web/app.py
src/web/routes/dashboard.py
src/web/templates/base.html
src/web/templates/dashboard.html
src/web/templates/jobs.html
src/web/static/style.css
tests/unit/test_web.py
```

Then read these reference files in full:

```text
C:\Users\joshb\Documents\GitHub\ceal\src\models\entities.py
C:\Users\joshb\Documents\GitHub\ceal\src\models\database.py
C:\Users\joshb\Documents\GitHub\ceal\src\models\schema.sql
C:\Users\joshb\Documents\GitHub\ceal\src\models\schema_postgres.sql
C:\Users\joshb\Documents\GitHub\ceal\src\apply\prefill.py
C:\Users\joshb\Documents\GitHub\ceal\src\web\routes\applications.py
C:\Users\joshb\Documents\GitHub\ceal\src\web\routes\apply.py
C:\Users\joshb\Documents\GitHub\ceal\src\web\routes\dashboard.py
C:\Users\joshb\Documents\GitHub\ceal\src\web\templates\base.html
C:\Users\joshb\Documents\GitHub\ceal\src\web\templates\dashboard.html
C:\Users\joshb\Documents\GitHub\ceal\src\web\templates\jobs.html
C:\Users\joshb\Documents\GitHub\ceal\src\web\templates\applications.html
C:\Users\joshb\Documents\GitHub\ceal\src\web\templates\reminders.html
C:\Users\joshb\Documents\GitHub\ceal\src\web\templates\approval_queue.html
C:\Users\joshb\Documents\GitHub\ceal\src\web\templates\application_review.html
C:\Users\joshb\Documents\GitHub\ceal\src\web\static\style.css
C:\Users\joshb\Documents\GitHub\ceal\tests\unit\test_crm.py
C:\Users\joshb\Documents\GitHub\ceal\tests\unit\test_autoapply.py
```

## TASK 1: Port the Phase 4 Enums + Models into `src/models/entities.py`

**Persona**: Backend Engineer + QA Lead

Port the auto-apply enums and models from the reference `entities.py` into current `src/models/entities.py`:
- `ApplicationStatus`
- `FieldType`
- `FieldSource`
- `ApplicationFieldCreate`
- `ApplicationCreate`
- `Application`

Rules:
- Preserve the existing `JobStatus` enum exactly as it already exists on current `main`.
- Do NOT invent extra enums or fields.
- Use the reference shapes and validations only.
- Keep `cover_letter` nullable and do NOT add generation logic.

**Verification**:

```bash
python -c "from src.models.entities import ApplicationStatus, ApplicationCreate, FieldType, FieldSource; app = ApplicationCreate(job_id=1); print(ApplicationStatus.DRAFT.value, FieldType.TEXT.value, FieldSource.RESUME.value, app.job_id)"
```

## TASK 2: Add the CRM / Auto-Apply Tables to Both Schema Files

**Persona**: ETL Architect + Backend Engineer

Update `src/models/schema.sql` and `src/models/schema_postgres.sql` by porting only the CRM / auto-apply tables evidenced in the reference copy:
- `applications`
- `application_fields`

Required constraints from the reference:
- `applications`
  - `UNIQUE(job_id, profile_id)`
  - status check limited to `draft`, `ready`, `approved`, `submitted`, `withdrawn`
  - nullable `cover_letter`
  - nullable `confidence_score` constrained to `0.0 <= x <= 1.0`
  - nullable `submitted_at`
- `application_fields`
  - FK to `applications(id)` with `ON DELETE CASCADE`
  - `UNIQUE(application_id, field_name)`
  - `field_type` limited to the 10 reference values
  - nullable `field_value`
  - nullable `confidence` constrained to `0.0 <= x <= 1.0`
  - nullable `source` limited to the 5 reference values

Also add:
- index on `applications(status)`
- index on `applications(job_id)`
- index on `application_fields(application_id)`
- the `applications.updated_at` trigger in both backends

Do NOT add:
- `document_templates`
- `generated_documents`
- any other table not required by CRM + auto-apply

Placement rules:
- In `schema.sql`, insert the new tables after the existing Phase 2 tables and before seed data.
- In `schema_postgres.sql`, insert the new tables in the equivalent schema section without disturbing current Phase 1 / Phase 2 tables.

After this task, the schema should expose 13 application tables total:
- 7 Phase 1 tables
- 4 Phase 2 tables
- 2 CRM / auto-apply tables

**Verification**:

```bash
python -c "
import sqlite3
conn = sqlite3.connect(':memory:')
with open('src/models/schema.sql') as f:
    conn.executescript(f.read())
tables = sorted(r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\"))
print(tables)
assert 'applications' in tables
assert 'application_fields' in tables
print('OK: CRM/apply tables present')
"
```

## TASK 3: Add CRM State Machine + Queries to `src/models/database.py`

**Persona**: ETL Architect + QA Lead

Port the CRM block from the reference `database.py`, adapted for current-main rules. Add:
- `VALID_TRANSITIONS`
- `update_job_status()`
- `get_jobs_by_status()`
- `get_application_summary()`
- `get_stale_applications()`

Behavior must match the reference:
- valid job transitions:
  - `scraped -> ranked, archived`
  - `ranked -> applied, archived`
  - `applied -> responded, interviewing, rejected, archived`
  - `responded -> interviewing, rejected, archived`
  - `interviewing -> offer, rejected, archived`
  - `offer -> archived`
  - `rejected -> archived`
  - `archived -> ranked`
- invalid transitions raise `ValueError`
- stale reminders only consider `applied`, `responded`, `interviewing`
- `days_stale` is computed in Python, not SQL

Do NOT copy backend-specific SQL blindly from the reference.

Important portability note:
- The reference uses `NULLS LAST` in ordering.
- That is NOT portable to SQLite.
- Rewrite ordering in a dual-backend-safe form, for example by sorting nulls with `CASE WHEN ... IS NULL THEN 1 ELSE 0 END`.

`get_jobs_by_status()` and any other ordered query must be portable across both SQLite and PostgreSQL.

**Verification**:

```bash
pytest tests/unit/test_crm.py -v
```

## TASK 4: Add Auto-Apply Persistence + State Machine to `src/models/database.py`

**Persona**: Backend Engineer + QA Lead

Port the auto-apply block from the reference `database.py`, adapted for current-main rules. Add:
- `create_application()`
- `get_application()`
- `get_approval_queue()`
- `_APP_VALID_TRANSITIONS`
- `update_application_status()`
- `get_application_stats()`

Required behavior:
- `create_application()` is idempotent on `(job_id, profile_id)`
- fields are upserted on `(application_id, field_name)`
- application transitions must match the reference exactly:
  - `draft -> ready, withdrawn`
  - `ready -> approved, draft, withdrawn`
  - `approved -> submitted, draft, withdrawn`
  - `submitted -> withdrawn`
  - `withdrawn -> draft`
- when an application transitions to `approved`, sync the parent job to CRM status `applied`
- when an application transitions to `submitted`, populate `submitted_at`

Important portability notes:
- The reference queue query uses `NULLS LAST`; rewrite it portably.
- If `RETURNING id` is not stable on the active SQLite build, resolve the existing / inserted application id with a deterministic follow-up `SELECT id FROM applications WHERE job_id = :job_id AND profile_id = :profile_id`.
- Do NOT invent another identity rule.

Do NOT add:
- document template queries
- generated document queries
- any browser automation

**Verification**:

```bash
pytest tests/unit/test_autoapply.py -v
```

## TASK 5: Create `src/apply/prefill.py` from the Reference Copy

**Persona**: AI Architect + Backend Engineer

Create `src/apply/prefill.py` by porting the deterministic reference implementation.

The authoritative field set is the reference `COMMON_ATS_FIELDS`:
- `full_name`
- `email`
- `phone`
- `location`
- `linkedin_url`
- `portfolio_url`
- `current_company`
- `current_title`
- `years_experience`
- `education`
- `work_authorization`
- `requires_sponsorship`
- `desired_salary`
- `start_date`
- `resume_text`
- `cover_letter`

Required behavior:
- regex / deterministic extraction only
- no LLM call
- no external network call
- use the resume file at `data/resume.txt` by default
- if a field is missing from the resume, leave it blank / `None`
- use only the explicit reference defaults for:
  - `work_authorization`
  - `requires_sponsorship`
  - `desired_salary`
  - `start_date`
- keep the `cover_letter` field placeholder as ungenerated content
- compute per-field confidence and average confidence as in the reference

This sprint's anti-hallucination rule is strongest here:
- Do NOT infer a salary, portfolio URL, sponsorship answer, or cover letter from thin air.
- Only emit what is extracted or what the reference defaults explicitly define.

Also create `src/apply/__init__.py`.

**Verification**:

```bash
python -c "from src.apply.prefill import PreFillEngine; result = PreFillEngine(resume_path='data/resume.txt').prefill_application(job_id=1); print(result.confidence_score, len(result.fields), sum(1 for f in result.fields if f.field_value))"
pytest tests/unit/test_autoapply.py -k prefill -v
```

## TASK 6: Rebuild the Web Surface Without Regressing Current Main

**Persona**: DPM + Backend Engineer

Update the web layer to expose CRM and auto-apply, using the reference templates and routes as source material while preserving current-main app metadata.

### 6a. `src/web/app.py`

Register:
- `applications.router`
- `apply.router`

Do NOT regress:
- title
- description
- current app version string
- lifespan behavior

### 6b. `src/web/routes/dashboard.py`

Port the reference dashboard behavior:
- fetch `stats = get_pipeline_stats()`
- fetch `app_summary = get_application_summary()`
- fetch `stale = get_stale_applications(days=7)`
- fetch `apply_stats = get_application_stats()`
- render all of that into `dashboard.html`

Use request-first `TemplateResponse`.

### 6c. New routes

Create from the reference copy, adapting only where needed for current-main compatibility:
- `src/web/routes/applications.py`
- `src/web/routes/apply.py`

Expected user-facing route strings from the reference:
- `/applications`
- `/applications/{job_id}/status`
- `/applications/reminders`
- `/apply`
- `/apply/prefill/{job_id}`
- `/apply/{app_id}`
- `/apply/{app_id}/status`

### 6d. Existing templates to modify

Modify these current-main templates using the reference as the source of truth for deltas:
- `src/web/templates/base.html`
  - add nav links for `Applications` and `Auto-Apply`
  - preserve current footer version branding from current main
- `src/web/templates/dashboard.html`
  - add Application Pipeline, Auto-Apply Pipeline, and Follow-Up Reminders cards
- `src/web/templates/jobs.html`
  - add an `Apply` column
  - add `POST /apply/prefill/{{ job.id }}` `Pre-Fill` buttons

### 6e. New templates to create

Create from the reference copy:
- `src/web/templates/applications.html`
- `src/web/templates/reminders.html`
- `src/web/templates/approval_queue.html`
- `src/web/templates/application_review.html`

Expected user-facing strings from the reference:
- `Application Tracker`
- `Follow-Up Reminders`
- `Auto-Apply Queue`
- `Application Review`
- `Pre-Fill`

### 6f. `src/web/static/style.css`

Extend the current stylesheet with the reference CRM / queue classes only. Add the reference classes needed for:
- Kanban board
- status buttons
- stale warning banner
- summary bar
- confidence bar and confidence dot
- status tabs
- queue grid
- tier accent borders

Do NOT replace the entire current stylesheet wholesale.

**Verification**:

```bash
pytest tests/unit/test_web.py -v
pytest tests/unit/test_crm.py -v
pytest tests/unit/test_autoapply.py -v
```

## TASK 7: Add the Required Tests, Including Real SQL Coverage

**Persona**: QA Lead

### 7a. Create the reference-backed unit tests

Create from the reference copy:
- `tests/unit/test_crm.py`
- `tests/unit/test_autoapply.py`

Adapt only when needed for:
- current app version on `main`
- request-first `TemplateResponse`
- current file/module layout
- any dual-backend-safe SQL ordering rewrites

### 7b. Update `tests/unit/test_web.py`

Current dashboard tests only patch `get_pipeline_stats()`.
After the dashboard route is expanded, update `tests/unit/test_web.py` so the dashboard tests patch:
- `get_pipeline_stats()`
- `get_application_summary()`
- `get_stale_applications()`
- `get_application_stats()`

Also add a jobs-page assertion for the `Pre-Fill` action.

### 7c. Create a real SQL integration test file

Create `tests/integration/test_crm_autoapply_roundtrip.py`.

This file must use a real in-memory SQLite database via `init_db()` and exercise the real SQL path for the new features. Cover at least:
1. `applications` and `application_fields` tables exist after `init_db()`
2. a ranked job can transition to `applied` only via valid CRM transitions
3. `create_application()` is idempotent on `(job_id, profile_id)`
4. application fields are persisted and returned by `get_application()`
5. approving an application syncs the parent job to `applied`
6. `get_stale_applications()` only returns active statuses and includes `days_stale`

Use real SQL, not mocks, for this file.

**Verification**:

```bash
pytest tests/integration/test_crm_autoapply_roundtrip.py -v
```

## TASK 8: Full Verification

Run all targeted checks first:

```bash
pytest tests/unit/test_crm.py -v
pytest tests/unit/test_autoapply.py -v
pytest tests/unit/test_web.py -v
pytest tests/integration/test_crm_autoapply_roundtrip.py -v
ruff check src/ tests/
```

Then run the full suite:

```bash
pytest tests/ -v
ruff check src/ tests/
pytest tests/ --co -q 2>&1 | tail -3
```

Acceptance criteria:
- all tests pass
- ruff is clean
- total collected tests is greater than the current baseline of 179
- no current-main functionality regressed

## TASK 9: Session Note (Mandatory Before Commit)

Before the final commit, create a session note using:
- `docs/ai-onboarding/DEBRIEF_TEMPLATE.md`

Required location:
- `docs/session_notes/YYYY-MM-DD_sprint8-crm-autoapply.md`

The session note must include:
- objective
- tasks completed
- files changed
- test results
- architecture decisions
- what is intentionally not in scope
- an X-Y-Z career bullet

## COMMIT

```bash
git add src/apply/
git add src/models/entities.py
git add src/models/database.py
git add src/models/schema.sql
git add src/models/schema_postgres.sql
git add src/web/app.py
git add src/web/routes/dashboard.py
git add src/web/routes/applications.py
git add src/web/routes/apply.py
git add src/web/templates/base.html
git add src/web/templates/dashboard.html
git add src/web/templates/jobs.html
git add src/web/templates/applications.html
git add src/web/templates/reminders.html
git add src/web/templates/approval_queue.html
git add src/web/templates/application_review.html
git add src/web/static/style.css
git add tests/unit/test_web.py
git add tests/unit/test_crm.py
git add tests/unit/test_autoapply.py
git add tests/integration/test_crm_autoapply_roundtrip.py
git add docs/session_notes/

git status

git commit -m "feat: reimplement CRM + auto-apply approval queue

- add CRM Kanban board, status transitions, and stale reminders
- add deterministic ATS prefill engine and approval queue routes
- add applications/application_fields tables to SQLite and PostgreSQL schemas
- add real SQL integration coverage for CRM and auto-apply flows
- wire dashboard and jobs UI into the new CRM/apply surfaces"

# Use a release tag only if Josh wants this sprint tagged.
git tag -a v2.8.0-sprint8-crm-autoapply -m "Sprint 8: CRM + auto-apply reimplementation"
git push origin main --tags
```

## COMPLETION CHECKLIST

- [ ] `src/models/entities.py` contains `ApplicationStatus`, `FieldType`, `FieldSource`, `ApplicationFieldCreate`, `ApplicationCreate`, `Application`
- [ ] `src/models/schema.sql` contains `applications` and `application_fields`
- [ ] `src/models/schema_postgres.sql` contains `applications` and `application_fields`
- [ ] `src/models/database.py` contains CRM and auto-apply state machine/query functions
- [ ] `src/apply/prefill.py` exists and uses deterministic extraction only
- [ ] `src/web/routes/applications.py` exists
- [ ] `src/web/routes/apply.py` exists
- [ ] `src/web/app.py` registers both new routers
- [ ] `src/web/routes/dashboard.py` renders `app_summary`, `stale_count`, and `apply_stats`
- [ ] `src/web/templates/base.html` includes nav links for `Applications` and `Auto-Apply`
- [ ] `src/web/templates/jobs.html` includes `Pre-Fill`
- [ ] `src/web/templates/applications.html` renders `Application Tracker`
- [ ] `src/web/templates/reminders.html` renders `Follow-Up Reminders`
- [ ] `src/web/templates/approval_queue.html` renders `Auto-Apply Queue`
- [ ] `src/web/templates/application_review.html` renders `Application Review`
- [ ] `tests/unit/test_crm.py` passes
- [ ] `tests/unit/test_autoapply.py` passes
- [ ] `tests/integration/test_crm_autoapply_roundtrip.py` passes
- [ ] `pytest tests/ -v` passes
- [ ] `ruff check src/ tests/` reports 0 errors
- [ ] session note created
- [ ] committed and pushed

If any requirement cannot be satisfied from current main + the reference files listed above, STOP and report the exact gap instead of inventing behavior.
