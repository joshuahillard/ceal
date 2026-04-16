# Céal Sprint 2 — Phase 3 CRM + Prompt Quality Tuning

## CONTEXT
You are working on the Céal project — an AI-powered career signal engine.
The project root is the `ceal/` directory containing `src/`, `tests/`, `pyproject.toml`, `requirements.txt`.

**Branch state**: You are on `main`. This branch contains Sprint 1 UI (FastAPI + Jinja2), Phase 2B work, and 167+ passing tests. CI is green.

**PRE-FLIGHT CHECK**: Before starting any work, verify these files exist:
```bash
ls src/web/app.py src/web/routes/dashboard.py src/web/routes/jobs.py src/web/routes/demo.py
ls src/web/templates/base.html src/web/templates/dashboard.html src/web/templates/jobs.html src/web/templates/demo.html
ls src/demo.py src/fetcher.py src/batch.py src/export.py src/tailoring/persistence.py
ls data/resume.txt data/sample_job.txt
ls tests/unit/test_web.py
```
If ANY of those files are missing, STOP and report which ones. Do NOT proceed without them.

**Your job**: Two objectives:
1. **Prompt quality tuning** — Fix LLM keyword-stuffing in `src/tailoring/engine.py`
2. **Phase 3 CRM** — Build application tracking with status transitions, Kanban board, follow-up reminders, and dashboard integration

---

## CRITICAL RULES (Anti-Hallucination)

1. **READ before WRITE**: Before modifying ANY file, read it first. Never assume file contents.
2. **EXISTING FILES — DO NOT DUPLICATE OR RENAME**:
   - `src/models/database.py` — contains `get_pipeline_stats()` (line ~573), `get_top_matches()` (line ~449), `get_session()` (line ~103), `init_db()` (line ~132), `upsert_job()`, `upsert_jobs_batch()`, `get_unranked_jobs()`, `update_job_ranking()`, `assign_company_tiers()`, `log_scrape_run()`, `create_resume_profile()`, `link_resume_skill()`
   - `src/models/entities.py` — contains `JobStatus` enum with 8 states: SCRAPED, RANKED, APPLIED, RESPONDED, INTERVIEWING, OFFER, REJECTED, ARCHIVED
   - `src/models/schema.sql` — Phase 1 DDL. The `job_listings` table already has `status TEXT NOT NULL DEFAULT 'scraped' CHECK(status IN ('scraped','ranked','applied','responded','interviewing','offer','rejected','archived'))` and `updated_at` column with auto-update trigger
   - `src/web/app.py` — FastAPI app factory with `create_app()`, `templates` (Jinja2Templates), `lifespan()` (calls `init_db()`)
   - `src/web/routes/dashboard.py` — Dashboard route `GET /` wired to `get_pipeline_stats()`
   - `src/web/routes/jobs.py` — Jobs route `GET /jobs` wired to `get_top_matches()`
   - `src/web/routes/demo.py` — Demo route `GET /demo`, `POST /demo`
   - `src/web/templates/base.html` — Shared layout with nav links (Dashboard, Jobs, Demo)
   - `src/tailoring/engine.py` — `TailoringEngine` class, `_TIER_PROMPTS` dict (lines ~49-70), `_SYSTEM_PROMPT` (lines ~72-102), `CURRENT_PROMPT_VERSION = "v1.0"` (line ~43), `_parse_llm_response()` (line ~249), `strip_code_fences()`
   - `src/tailoring/models.py` — Pydantic v2 models: `TailoredBullet` with `enforce_xyz_compliance` validator
   - `src/tailoring/db_models.py` — SQLAlchemy ORM for Phase 2. Contains `Base` (declarative base), `PHASE1_STUB_TABLES`, `_utcnow()` function
   - `alembic/env.py` — Async migration runner, imports `Base` and `PHASE1_STUB_TABLES` from db_models, `include_object()` excludes Phase 1 stubs, `render_as_batch=True`
3. **IMPORT PATHS**: All imports use `src.` prefix (e.g., `from src.models.database import get_pipeline_stats`). The project uses `pythonpath = ["."]` in pyproject.toml.
4. **PYTHON VERSION**: Target Python 3.10+. Do NOT use `datetime.UTC` (use `datetime.timezone.utc`). Do NOT use `StrEnum` (use `str, Enum`). CHECK `src/tailoring/db_models.py` line ~87 — if `_utcnow()` uses `datetime.UTC`, fix it to `datetime.timezone.utc`.
5. **ASYNC**: The entire codebase is async. Database uses `AsyncSession` with `aiosqlite`. All database functions are `async def`. FastAPI routes that call database functions must be `async def`.
6. **DATABASE**: SQLite via `sqlite+aiosqlite:///data/ceal.db`. Phase 1 tables in `schema.sql`. Phase 2 tables managed by Alembic. `job_listings.status` already supports the full lifecycle — NO new table needed for basic CRM.
7. **RUFF CONFIG**: `target-version = "py310"`, `line-length = 120`. Ignored rules: `UP017`, `UP042`, `E501`, `SIM102`, `SIM105`, `SIM108`, `B017`, `B904`. Run `ruff check src/ tests/` before committing.
8. **TESTS**: `pytest` with `asyncio_mode = "strict"`. All async tests need `@pytest.mark.asyncio`. Test isolation uses StaticPool in-memory SQLite with explicit table drops (FK checks disabled) between test classes.
9. **NO SECRETS**: Never hardcode API keys. Load from environment only.
10. **WEB PATTERNS**: Follow Sprint 1 patterns exactly — route modules in `src/web/routes/`, templates extending `base.html`, router registered in `app.py` via `app.include_router()`.

---

## TASK 1: Prompt Quality Tuning — Fix LLM Keyword Stuffing

**Read first**: `src/tailoring/engine.py` — read the ENTIRE file

**Problem**: The LLM inserts job requirement keywords (GCP, troubleshooting, etc.) into every bullet regardless of whether the candidate actually has that experience. Example: "Managed escalation workflows... using GCP-based incident management systems" — the candidate never used GCP at Toast.

**Changes required**:

### 1a. Update `_SYSTEM_PROMPT` (line ~72)

Add these rules to the existing rules section (AFTER "Output valid JSON only"):
```
- ONLY reference skills and tools the candidate ACTUALLY has (listed in "Candidate has" section). NEVER fabricate tool usage, platform experience, or technical claims.
- Do NOT rewrite section headers (e.g., "[EXPERIENCE] Toast, Inc. — Manager II"). Only rewrite actual bullet points.
- If a bullet has low relevance to the job, set a low relevance_score — do NOT force-fit keywords to inflate the score.
- BAD example (keyword stuffing): "Managed escalation workflows using GCP-based incident management systems" when candidate never used GCP
- GOOD example (honest reframing): "Managed escalation workflows across Engineering, Product, and Customer Success — directly transferable to cross-functional incident response"
```

### 1b. Update `_TIER_PROMPTS` (lines ~49-70)

For all three tiers, add at the END of each string:
```
Do NOT insert skills the candidate does not have. Reframe existing experience for relevance instead.
```

### 1c. Bump version

Change `CURRENT_PROMPT_VERSION = "v1.0"` to `CURRENT_PROMPT_VERSION = "v1.1"`

### 1d. Verify `_parse_llm_response()`

**Read the function** at line ~249. After the engine fix (`bff21db`), it should validate `xyz_format` claims by checking the text for "measured by" AND "by doing" before accepting. If this validation is NOT present, add it:

```python
# Inside _parse_llm_response, after json.loads:
for bullet in parsed.get("tailored_bullets", []):
    if bullet.get("xyz_format"):
        text_lower = bullet.get("rewritten_text", "").lower()
        if "measured by" not in text_lower or "by doing" not in text_lower:
            bullet["xyz_format"] = False
```

If the validation IS already present, leave it alone.

**Verification**: Run `ruff check src/tailoring/engine.py` and `pytest tests/unit/test_tailoring_engine.py -v`

---

## TASK 2: Add CRM Database Functions to `src/models/database.py`

**Read first**: `src/models/database.py` — read the ENTIRE file to understand the existing function patterns

**Read second**: `src/models/entities.py` — confirm `JobStatus` enum values

The `job_listings` table already has `status` with CHECK constraint and `updated_at` with auto-trigger. We need functions to manage status transitions.

Add these functions to `src/models/database.py`, AFTER the existing `get_pipeline_stats()` function:

### 2a. Valid transitions map

```python
# ---------------------------------------------------------------------------
# CRM: Application Status Tracking
# ---------------------------------------------------------------------------

# State machine: only valid forward transitions allowed.
# This prevents data corruption (e.g., scraped → offer skips the entire process).
VALID_TRANSITIONS: dict[str, set[str]] = {
    "scraped": {"ranked", "archived"},
    "ranked": {"applied", "archived"},
    "applied": {"responded", "interviewing", "rejected", "archived"},
    "responded": {"interviewing", "rejected", "archived"},
    "interviewing": {"offer", "rejected", "archived"},
    "offer": {"archived"},
    "rejected": {"archived"},
    "archived": set(),  # Terminal state
}
```

### 2b. `update_job_status()`

```python
async def update_job_status(job_id: int, new_status: str, notes: str | None = None) -> dict:
    """
    Transition a job to a new status with state-machine validation.

    Returns the updated job dict or raises ValueError for invalid transitions.

    Interview point: "Status transitions are validated at the application layer
    before hitting the database. The CHECK constraint is the last line of defense,
    but the state machine logic catches invalid jumps like scraped→offer before
    they ever reach SQL."
    """
    async with get_session() as session:
        # Get current status
        result = await session.execute(
            text("SELECT id, status, title, company_name FROM job_listings WHERE id = :job_id"),
            {"job_id": job_id},
        )
        job = result.first()
        if not job:
            raise ValueError(f"Job {job_id} not found")

        current_status = job[1]
        valid_next = VALID_TRANSITIONS.get(current_status, set())

        if new_status not in valid_next:
            raise ValueError(
                f"Invalid transition: {current_status} → {new_status}. "
                f"Valid transitions from '{current_status}': {valid_next or 'none (terminal state)'}"
            )

        await session.execute(
            text("""
                UPDATE job_listings
                SET status = :new_status
                WHERE id = :job_id
            """),
            {"new_status": new_status, "job_id": job_id},
        )

    logger.info("job_status_updated", job_id=job_id, from_status=current_status, to_status=new_status)
    return {"job_id": job_id, "previous_status": current_status, "new_status": new_status}
```

### 2c. `get_jobs_by_status()`

```python
async def get_jobs_by_status(status: str, limit: int = 100) -> list[dict]:
    """Get all jobs with a specific status, ordered by match_score descending."""
    async with get_session() as session:
        result = await session.execute(
            text("""
                SELECT id, title, company_name, company_tier, match_score,
                       match_reasoning, url, location, remote_type,
                       salary_min, salary_max, status, updated_at
                FROM job_listings
                WHERE status = :status
                ORDER BY
                    CASE WHEN match_score IS NOT NULL THEN match_score ELSE 0 END DESC,
                    company_tier ASC NULLS LAST
                LIMIT :limit
            """),
            {"status": status, "limit": limit},
        )
        return [dict(row._mapping) for row in result]
```

### 2d. `get_application_summary()`

```python
async def get_application_summary() -> dict:
    """
    Get counts for each status in the application lifecycle.
    Powers the CRM Kanban board columns.
    """
    async with get_session() as session:
        result = await session.execute(
            text("""
                SELECT status, COUNT(*) as count
                FROM job_listings
                GROUP BY status
                ORDER BY CASE status
                    WHEN 'scraped' THEN 1
                    WHEN 'ranked' THEN 2
                    WHEN 'applied' THEN 3
                    WHEN 'responded' THEN 4
                    WHEN 'interviewing' THEN 5
                    WHEN 'offer' THEN 6
                    WHEN 'rejected' THEN 7
                    WHEN 'archived' THEN 8
                END
            """)
        )
        return {row[0]: row[1] for row in result}
```

### 2e. `get_stale_applications()`

```python
async def get_stale_applications(days: int = 7) -> list[dict]:
    """
    Find applications that haven't been updated in N days.
    Powers the follow-up reminder system.

    Only flags jobs in active states (applied, responded, interviewing) —
    not scraped/ranked (pre-application) or terminal states (offer/rejected/archived).
    """
    async with get_session() as session:
        result = await session.execute(
            text("""
                SELECT id, title, company_name, company_tier, match_score,
                       status, updated_at,
                       CAST(julianday('now') - julianday(updated_at) AS INTEGER) as days_stale
                FROM job_listings
                WHERE status IN ('applied', 'responded', 'interviewing')
                  AND julianday('now') - julianday(updated_at) >= :days
                ORDER BY updated_at ASC
            """),
            {"days": days},
        )
        return [dict(row._mapping) for row in result]
```

**Verification**: `ruff check src/models/database.py`

---

## TASK 3: Build CRM Route — `src/web/routes/applications.py`

**Read first**: `src/web/routes/jobs.py` — follow the exact same pattern for imports and structure

Create `src/web/routes/applications.py`:

```python
"""Application tracking CRM routes — Kanban board + status transitions."""
from __future__ import annotations

import os

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import RedirectResponse

from src.models.database import (
    get_application_summary,
    get_jobs_by_status,
    get_stale_applications,
    get_top_matches,
    update_job_status,
)
from src.web.app import templates

router = APIRouter(prefix="/applications", tags=["applications"])


@router.get("/")
async def kanban_board(request: Request):
    """Render the Kanban board with jobs grouped by status."""
    summary = await get_application_summary()

    # Fetch jobs for each active column
    columns = {}
    for status in ["scraped", "ranked", "applied", "responded", "interviewing", "offer", "rejected"]:
        if summary.get(status, 0) > 0:
            columns[status] = await get_jobs_by_status(status, limit=50)
        else:
            columns[status] = []

    stale = await get_stale_applications(days=7)

    return templates.TemplateResponse(
        "applications.html",
        {
            "request": request,
            "summary": summary,
            "columns": columns,
            "stale_jobs": stale,
            "stale_count": len(stale),
        },
    )


@router.post("/{job_id}/status")
async def update_status(
    request: Request,
    job_id: int,
    new_status: str = Form(...),
):
    """Transition a job to a new status."""
    try:
        result = await update_job_status(job_id, new_status)
        # Redirect back to Kanban board after status change
        return RedirectResponse(url="/applications", status_code=303)
    except ValueError as e:
        # Invalid transition — show error on Kanban board
        summary = await get_application_summary()
        columns = {}
        for status in ["scraped", "ranked", "applied", "responded", "interviewing", "offer", "rejected"]:
            columns[status] = await get_jobs_by_status(status, limit=50) if summary.get(status, 0) > 0 else []
        stale = await get_stale_applications(days=7)

        return templates.TemplateResponse(
            "applications.html",
            {
                "request": request,
                "summary": summary,
                "columns": columns,
                "stale_jobs": stale,
                "stale_count": len(stale),
                "error": str(e),
            },
        )


@router.get("/reminders")
async def reminders(
    request: Request,
    days: int = Query(7, ge=1, le=30, description="Days before flagging as stale"),
):
    """Show stale applications needing follow-up."""
    stale = await get_stale_applications(days=days)
    return templates.TemplateResponse(
        "reminders.html",
        {
            "request": request,
            "stale_jobs": stale,
            "days_threshold": days,
        },
    )
```

---

## TASK 4: Register CRM Route in App Factory

**Read first**: `src/web/app.py` — find the `create_app()` function and the route registration section

Add the applications router import and registration:

```python
from src.web.routes import applications, dashboard, demo, jobs
# ...
app.include_router(applications.router)
```

---

## TASK 5: Update Dashboard with CRM Data

**Read first**: `src/web/routes/dashboard.py` — read the current route handler

Update the dashboard route to include application tracking data:

```python
from src.models.database import get_application_summary, get_pipeline_stats, get_stale_applications

@router.get("/")
async def dashboard(request: Request):
    """Render pipeline statistics dashboard with CRM overview."""
    stats = await get_pipeline_stats()
    app_summary = await get_application_summary()
    stale = await get_stale_applications(days=7)
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "stats": stats,
            "app_summary": app_summary,
            "stale_count": len(stale),
        },
    )
```

---

## TASK 6: Build CRM Templates

**Read first**: `src/web/templates/base.html` — understand the nav structure and block names

### 6a. Update `src/web/templates/base.html`

Add "Applications" link to the navigation bar, between "Jobs" and "Demo":

```html
<a href="/applications">Applications</a>
```

### 6b. Update `src/web/templates/dashboard.html`

**Read first**: the current dashboard.html to understand the existing card layout

Add a new section AFTER the existing stats cards:

- **Application Pipeline** card showing counts per status (from `app_summary`)
- **Follow-Up Reminders** badge showing `stale_count` with warning styling if > 0
- Link to `/applications` for the full Kanban view

### 6c. Create `src/web/templates/applications.html`

Extends `base.html`. Kanban-style layout:

- **Error banner** at top if `error` variable is set (invalid transition)
- **Summary bar** showing total counts per status
- **Kanban columns**: Ranked | Applied | Responded | Interviewing | Offer | Rejected
  - Each column header shows status name + count
  - Each card shows: Company name, Job title, Match score (as %), Tier badge (if assigned), Days since last update
  - Each card has status transition buttons showing ONLY valid next states (use the VALID_TRANSITIONS map)
  - Each button submits a POST form to `/applications/{job_id}/status`
  - Tier 1 cards get a green left-border accent
  - Tier 3 cards get a blue left-border accent
- **Stale Applications** section at bottom (if `stale_count > 0`):
  - Warning banner: "X applications haven't been updated in 7+ days"
  - List of stale jobs with "Follow Up" action buttons
- Don't show "scraped" column (pre-pipeline, too many items) — the Kanban starts at "ranked"

### 6d. Create `src/web/templates/reminders.html`

Extends `base.html`. Dedicated reminders view:

- Filter: days threshold slider (1-30, default 7)
- Table: Job Title, Company, Status, Last Updated, Days Stale, Action buttons
- Action buttons: advance to next status or archive
- Empty state: "No stale applications — you're on top of things!"

### 6e. Update `src/web/static/style.css`

**Read first**: the current CSS file

Add styles for:
- `.kanban-board` — flexbox row, horizontal scroll on overflow
- `.kanban-column` — min-width: 220px, vertical card stack
- `.kanban-card` — card with shadow, company/title/score/tier
- `.tier-1-accent` — green left border (4px solid #22c55e)
- `.tier-2-accent` — yellow left border (4px solid #eab308)
- `.tier-3-accent` — blue left border (4px solid #3b82f6)
- `.stale-warning` — amber background banner
- `.status-btn` — small button for status transitions
- `.reminder-badge` — red notification badge

---

## TASK 7: Write CRM Tests

**Read first**: `tests/unit/test_web.py` — follow the exact same test patterns (httpx AsyncClient, mocking)

Create `tests/unit/test_crm.py`:

1. **Test `VALID_TRANSITIONS` map**:
   - `test_scraped_can_transition_to_ranked`
   - `test_scraped_cannot_skip_to_offer`
   - `test_archived_is_terminal`
   - `test_all_statuses_have_transition_entry`

2. **Test `update_job_status()`**:
   - `test_valid_transition_updates_status` — insert a job, transition scraped→ranked
   - `test_invalid_transition_raises_valueerror` — try scraped→offer
   - `test_nonexistent_job_raises_valueerror`

3. **Test web routes**:
   - `test_kanban_board_returns_200`
   - `test_status_update_redirects_on_success`
   - `test_status_update_shows_error_on_invalid`
   - `test_reminders_returns_200`

4. **Test `get_stale_applications()`**:
   - `test_stale_only_returns_active_statuses` — insert jobs with status=applied (old updated_at) and status=scraped (old updated_at), verify only applied is returned

All tests must be `async def` with `@pytest.mark.asyncio`. Mock database functions for web route tests. Use real database (StaticPool in-memory) for database function tests.

---

## TASK 8: Lint and Test

Run these commands IN ORDER:

```bash
ruff check src/ tests/ --fix
ruff check src/ tests/
pytest tests/unit/ -v --tb=short
pytest tests/integration/ -v --tb=short
pytest tests/ --cov=src --cov-report=term-missing
```

Fix any failures before proceeding. ALL existing tests (167+) must continue to pass plus the new CRM tests.

---

## TASK 9: Commit

```bash
git add -A
git diff --cached --stat
git commit -m "feat(crm): add application tracking with Kanban board + prompt v1.1

- Kanban board at /applications with status transition buttons
- State-machine validation (VALID_TRANSITIONS prevents invalid jumps)
- Follow-up reminders for stale applications (7+ days)
- Dashboard enhanced with application pipeline summary
- Prompt v1.1: anti-keyword-stuffing constraints in engine.py
- Reminders page at /applications/reminders

Phase: Sprint 2 — CRM + Prompt Quality
Personas: Data Engineer, Backend Engineer, AI Architect, DPM"
git push origin main
```

---

## VERIFICATION CHECKLIST

Before you say you're done, confirm ALL of these:

- [ ] `ruff check src/ tests/` exits clean (zero errors)
- [ ] `pytest tests/unit/ -v` passes (all existing + new CRM tests)
- [ ] `pytest tests/integration/ -v` passes
- [ ] `python -m src.main --web` starts server on port 8000
- [ ] `http://localhost:8000/` shows dashboard with application pipeline card
- [ ] `http://localhost:8000/applications` shows Kanban board with job cards
- [ ] Status transition buttons work (click "Applied" on a ranked job → card moves)
- [ ] Invalid transitions show error banner (not crash)
- [ ] `http://localhost:8000/applications/reminders` shows stale application list
- [ ] Navigation bar has 4 links: Dashboard, Jobs, Applications, Demo
- [ ] `CURRENT_PROMPT_VERSION` is `"v1.1"` in engine.py
- [ ] `_SYSTEM_PROMPT` contains anti-keyword-stuffing rules
- [ ] No `datetime.UTC` usage anywhere (grep for it)
- [ ] No hardcoded API keys
- [ ] All imports use `src.` prefix
- [ ] Git push to `origin main` successful
