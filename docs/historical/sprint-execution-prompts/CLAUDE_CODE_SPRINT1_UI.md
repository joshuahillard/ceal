# Céal Sprint 1 — FastAPI UI Foundation

## CONTEXT
You are working on the Céal project — an AI-powered career signal engine.
The project root is the `ceal/` directory containing `src/`, `tests/`, `pyproject.toml`, `requirements.txt`.

**Branch state**: You are on `feature/ci-pipeline`. This branch contains all Phase 2B work (demo.py, fetcher.py, batch.py, export.py, persistence.py) plus 158 passing tests. CI is green.

**PRE-FLIGHT CHECK**: Before starting any work, verify these Phase 2B files exist:
```bash
ls src/demo.py src/fetcher.py src/batch.py src/export.py src/tailoring/persistence.py data/resume.txt data/sample_job.txt
```
If ANY of those files are missing, STOP and report which ones. Do NOT proceed without them — they contain patterns you must reuse.

**Your job**: Build a FastAPI + Jinja2 web application in `src/web/` that replaces PowerShell CLI interaction with a browser UI. Wire it to EXISTING database functions and pipeline components. Do NOT rewrite any existing modules.

---

## CRITICAL RULES (Anti-Hallucination)

1. **READ before WRITE**: Before modifying ANY file, read it first. Never assume file contents.
2. **EXISTING FILES ONLY**: The following files exist — do not create duplicates or rename them:
   - `src/models/database.py` — contains `get_pipeline_stats()`, `get_top_matches()`, `get_session()`, `init_db()`
   - `src/models/entities.py` — contains `JobStatus`, `JobSource`, `RemoteType`, `SkillCategory`, `Proficiency`, `RawJobListing`, `JobListingCreate`, `JobListing`
   - `src/tailoring/models.py` — contains `ParsedBullet`, `ParsedResume`, `SkillGap`, `TailoringRequest`, `TailoredBullet`, `TailoringResult`
   - `src/tailoring/engine.py` — contains `TailoringEngine` class, `CURRENT_PROMPT_VERSION`
   - `src/tailoring/resume_parser.py` — contains `ResumeProfileParser` class
   - `src/tailoring/skill_extractor.py` — contains `SkillOverlapAnalyzer` class
   - `src/tailoring/db_models.py` — contains SQLAlchemy ORM models for Phase 2 tables
   - `src/tailoring/persistence.py` — contains `save_tailoring_result()`, `get_tailoring_results()`, `list_tailored_jobs()`
   - `src/demo.py` — contains demo mode orchestrator (ResumeProfileParser → SkillOverlapAnalyzer → TailoringEngine)
   - `src/fetcher.py` — contains `fetch_job_description(url)` for URL-based job descriptions
   - `src/batch.py` — contains `run_batch_tailoring(resume_path, limit, min_score)`
   - `src/export.py` — contains `export_tailored_resume()` and `export_skill_gap_table()` using python-docx
   - `src/main.py` — CLI entry point with `--demo`, `--job-url`, `--batch`, `--export` flags
   - `data/resume.txt` — Josh's resume in parser-compatible format
   - `data/sample_job.txt` — Stripe TSE sample posting
3. **IMPORT PATHS**: All imports use `src.` prefix (e.g., `from src.models.database import get_pipeline_stats`). The project uses `pythonpath = ["."]` in pyproject.toml.
4. **PYTHON VERSION**: Target Python 3.10+. Do NOT use `datetime.UTC` (use `datetime.timezone.utc`). Do NOT use `StrEnum` (use `str, Enum`).
5. **ASYNC**: The entire codebase is async. Database uses `AsyncSession` with `aiosqlite`. All database functions are `async def`. FastAPI routes that call database functions must be `async def`.
6. **DATABASE**: SQLite via `sqlite+aiosqlite:///data/ceal.db`. Connection configured in `src/models/database.py`. Phase 1 tables in `src/models/schema.sql`. Phase 2 tables managed by Alembic. Use `init_db()` from database.py to initialize.
7. **ENV**: API key loaded from `.env` as `LLM_API_KEY`. Database URL from `DATABASE_URL`. Use `python-dotenv` (already in requirements.txt).
8. **RUFF CONFIG**: `target-version = "py310"`, `line-length = 120`. Ignored rules: `UP017`, `UP042`, `E501`, `SIM102`, `SIM105`, `SIM108`, `B017`, `B904`. Run `ruff check src/ tests/` before committing.
9. **TESTS**: `pytest` with `asyncio_mode = "strict"`. All async tests need `@pytest.mark.asyncio`. Test isolation uses StaticPool in-memory SQLite with explicit table drops (FK checks disabled) between test classes.
10. **NO SECRETS**: Never hardcode API keys. Load from environment only.

---

## TASK 1: Add FastAPI Dependencies

**Read first**: `requirements.txt`

Add these packages to `requirements.txt` (append, do not replace existing):
```
fastapi==0.115.12
uvicorn[standard]==0.34.3
jinja2==3.1.6
python-multipart==0.0.20
```

Then run: `pip install -r requirements.txt`

**Verification**: `python -c "import fastapi; print(fastapi.__version__)"`

---

## TASK 2: Create Web Application Structure

Create the following directory structure inside `src/web/`:

```
src/web/
├── __init__.py          (empty)
├── app.py               (FastAPI application factory)
├── routes/
│   ├── __init__.py      (empty)
│   ├── dashboard.py     (GET / — pipeline stats dashboard)
│   ├── jobs.py          (GET /jobs — job listings with filters)
│   └── demo.py          (GET /demo, POST /demo — demo mode UI)
├── templates/
│   ├── base.html        (shared layout with nav)
│   ├── dashboard.html   (pipeline stats view)
│   ├── jobs.html        (job listings table)
│   └── demo.html        (demo mode form + results)
└── static/
    └── style.css        (minimal clean CSS)
```

---

## TASK 3: Build `src/web/app.py` — Application Factory

**Read first**: `src/models/database.py` (lines 1-80 for engine setup and `init_db()`)

Create `src/web/app.py`:

```python
"""
Céal Web Application Factory

Creates and configures the FastAPI app with Jinja2 templates,
static files, and route registration.

Interview talking point:
    "I used the application factory pattern so the web layer
    is independently testable — the same pattern Django and
    Flask use for production applications."
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

load_dotenv()

# Template and static file paths (relative to this file)
_WEB_DIR = Path(__file__).parent
_TEMPLATE_DIR = _WEB_DIR / "templates"
_STATIC_DIR = _WEB_DIR / "static"

templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    from src.models.database import init_db
    await init_db()
    yield


def create_app() -> FastAPI:
    """Application factory — creates and configures the FastAPI app."""
    app = FastAPI(
        title="Céal — Career Signal Engine",
        description="AI-powered job matching and resume tailoring pipeline",
        version="2.1.0",
        lifespan=lifespan,
    )

    # Mount static files
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    # Register route modules
    from src.web.routes import dashboard, demo, jobs
    app.include_router(dashboard.router)
    app.include_router(jobs.router)
    app.include_router(demo.router)

    return app


# Default app instance for uvicorn
app = create_app()
```

---

## TASK 4: Build Dashboard Route — `src/web/routes/dashboard.py`

**Read first**: `src/models/database.py` — find `get_pipeline_stats()` (around line 573). Note its return type is `dict` with keys: `jobs_by_status`, `jobs_by_tier`, `avg_match_score`, `total_ranked`, `latest_scrape`.

```python
"""Dashboard route — pipeline overview."""
from __future__ import annotations

from fastapi import APIRouter, Request

from src.models.database import get_pipeline_stats
from src.web.app import templates

router = APIRouter()


@router.get("/")
async def dashboard(request: Request):
    """Render pipeline statistics dashboard."""
    stats = await get_pipeline_stats()
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "stats": stats,
        },
    )
```

---

## TASK 5: Build Jobs Route — `src/web/routes/jobs.py`

**Read first**: `src/models/database.py` — find `get_top_matches()` (around line 449). Signature: `async def get_top_matches(min_score: float = 0.5, tier: int | None = None, limit: int = 20) -> list[dict]`. Returns dicts with keys: `id`, `title`, `company_name`, `company_tier`, `match_score`, `match_reasoning`, `url`, `location`, `remote_type`, `salary_min`, `salary_max`, `status`.

```python
"""Job listings route with tier/score filtering."""
from __future__ import annotations

from fastapi import APIRouter, Query, Request

from src.models.database import get_top_matches
from src.web.app import templates

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/")
async def job_list(
    request: Request,
    min_score: float = Query(0.3, ge=0.0, le=1.0, description="Minimum match score"),
    tier: int | None = Query(None, ge=1, le=3, description="Filter by company tier"),
    limit: int = Query(50, ge=1, le=200, description="Max results"),
):
    """Render filtered job listings."""
    jobs = await get_top_matches(min_score=min_score, tier=tier, limit=limit)
    return templates.TemplateResponse(
        "jobs.html",
        {
            "request": request,
            "jobs": jobs,
            "filters": {
                "min_score": min_score,
                "tier": tier,
                "limit": limit,
            },
        },
    )
```

---

## TASK 6: Build Demo Route — `src/web/routes/demo.py`

**Read first** (ALL of these before writing):
- `src/demo.py` — understand the demo orchestration flow
- `src/tailoring/resume_parser.py` — `ResumeProfileParser.parse(profile_id: int, raw_text: str) -> ParsedResume`
- `src/tailoring/skill_extractor.py` — `SkillOverlapAnalyzer.analyze(job, resume_skills) -> list[SkillGap]`
- `src/tailoring/engine.py` — `TailoringEngine.__init__(self, api_key: str, prompt_version: str = CURRENT_PROMPT_VERSION)` and `async generate_tailored_profile(request, resume_bullets, skill_gaps) -> TailoringResult`
- `src/tailoring/models.py` — `TailoringRequest(job_id: int, profile_id: int, target_tier: int, emphasis_areas: list[str])`
- `src/fetcher.py` — `async fetch_job_description(url: str) -> str`

Build `src/web/routes/demo.py` that:
1. GET `/demo` — renders a form with:
   - Textarea for resume text (pre-populated from `data/resume.txt` if it exists)
   - Textarea for job description OR URL input field
   - Dropdown for target tier (1, 2, 3)
   - Submit button
2. POST `/demo` — processes the form:
   - If URL provided, fetch description using `fetch_job_description()`
   - Parse resume via `ResumeProfileParser().parse()`
   - Run skill gap analysis via `SkillOverlapAnalyzer().analyze()`
   - If `LLM_API_KEY` is set, call `TailoringEngine` for AI-generated bullets
   - If no API key, show skill gap analysis only (graceful degradation)
   - Render results on `demo.html`

**IMPORTANT**: The demo route must construct a minimal job-like object for the SkillOverlapAnalyzer. Read `src/demo.py` to see how `_build_demo_job()` does this — reuse that pattern, do NOT create a new approach.

**IMPORTANT**: Load `LLM_API_KEY` from `os.getenv("LLM_API_KEY")`, never hardcode.

---

## TASK 7: Build HTML Templates

Create clean, functional templates using Jinja2. Keep styling minimal but professional.

### `src/web/templates/base.html`
- HTML5 doctype
- Link to `/static/style.css`
- Navigation bar with links: Dashboard (`/`), Jobs (`/jobs`), Demo (`/demo`)
- Title block: `{% block title %}Céal{% endblock %}`
- Content block: `{% block content %}{% endblock %}`
- Footer: "Céal v2.1 — Career Signal Engine"

### `src/web/templates/dashboard.html`
- Extends `base.html`
- Display `stats.jobs_by_status` as a summary card grid
- Display `stats.jobs_by_tier` with tier labels (Tier 1: Apply Now, Tier 2: Credential, Tier 3: Campaign)
- Display `stats.avg_match_score` as percentage
- Display `stats.total_ranked` count

### `src/web/templates/jobs.html`
- Extends `base.html`
- Filter form at top: min_score slider, tier dropdown, limit input
- Table with columns: Score, Title, Company, Tier, Location, Remote, Status
- Score displayed as percentage with color coding (green ≥70%, yellow ≥50%, red <50%)
- Company names linked to job URL if available
- Empty state message if no jobs match filters

### `src/web/templates/demo.html`
- Extends `base.html`
- Form section (always visible):
  - Resume textarea (rows=15, pre-populated)
  - Job description textarea (rows=10) OR URL input (toggle between them)
  - Target tier dropdown: 1 (Apply Now), 2 (Credential Building), 3 (Campaign Target)
  - Submit button
- Results section (visible only after POST):
  - Skill Gap Analysis table: Skill Name, Category, Job Requires, Resume Has, Proficiency
  - Tailored Bullets list (if API key was available): Original → Rewritten, X-Y-Z badge, Relevance score
  - Warning banner if no LLM_API_KEY was configured

### `src/web/static/style.css`
- Clean, professional CSS (no external frameworks needed)
- CSS custom properties for colors
- Responsive layout
- Style the nav, cards, tables, forms, and badges

---

## TASK 8: Add Web Entry Point

**Read first**: `src/main.py` — check the current CLI flags (around line 668, `_async_main()`)

Add a `--web` flag to the CLI in `src/main.py`:
```python
parser.add_argument(
    "--web",
    action="store_true",
    help="Launch the web UI (default: http://localhost:8000)",
)
parser.add_argument(
    "--port",
    type=int,
    default=8000,
    help="Port for web UI (default: 8000)",
)
```

In `_async_main()`, add handling BEFORE the existing `if args.rank_only:` block:
```python
if args.web:
    import uvicorn
    from src.web.app import create_app
    web_app = create_app()
    config = uvicorn.Config(web_app, host="0.0.0.0", port=args.port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()
    return
```

---

## TASK 9: Write Tests for Web Routes

**Read first**: `tests/unit/test_database.py` — understand the test fixture pattern (StaticPool, in-memory SQLite, table setup/teardown)

Create `tests/unit/test_web.py`:

1. Use `httpx.AsyncClient` with FastAPI's `ASGITransport` for async testing
2. Test `GET /` returns 200 with dashboard content
3. Test `GET /jobs` returns 200 with job table
4. Test `GET /demo` returns 200 with demo form
5. Test `POST /demo` with resume text + job description returns results
6. Mock `get_pipeline_stats()` and `get_top_matches()` to avoid real database in unit tests
7. Mock `TailoringEngine.generate_tailored_profile()` to avoid real API calls

All tests must be `async def` with `@pytest.mark.asyncio` decorator.

Add `httpx` to test dependencies — it's already in `requirements.txt`.

---

## TASK 10: Lint and Test

Run these commands IN ORDER:

```bash
ruff check src/ tests/ --fix
ruff check src/ tests/
pytest tests/unit/ -v --tb=short
pytest tests/integration/ -v --tb=short
pytest tests/ --cov=src --cov-report=term-missing
```

Fix any failures before proceeding. All existing 158 tests must continue to pass plus the new web tests.

---

## TASK 11: Commit and Verify

```bash
git add src/web/ tests/unit/test_web.py requirements.txt
git diff --cached --stat
git commit -m "feat(web): add FastAPI + Jinja2 UI foundation

- Dashboard page with pipeline stats (get_pipeline_stats)
- Job listings page with tier/score filtering (get_top_matches)
- Demo mode page wired to resume parser + skill extractor + tailoring engine
- Shared base template with navigation
- Unit tests for all three routes
- --web CLI flag to launch UI server

Phase: Sprint 1 — UI Foundation
Persona: Lead Backend Python Engineer"
```

---

## VERIFICATION CHECKLIST

Before you say you're done, confirm ALL of these:

- [ ] `ruff check src/ tests/` exits clean (zero errors)
- [ ] `pytest tests/unit/ -v` passes (including new test_web.py)
- [ ] `pytest tests/integration/ -v` passes
- [ ] `python -m src.main --web` starts server on port 8000
- [ ] Browser to `http://localhost:8000/` shows dashboard
- [ ] Browser to `http://localhost:8000/jobs` shows job listings
- [ ] Browser to `http://localhost:8000/demo` shows demo form
- [ ] No hardcoded API keys anywhere in the codebase
- [ ] All imports use `src.` prefix
- [ ] No `datetime.UTC` usage (search for it)
- [ ] No `StrEnum` usage (search for it)
