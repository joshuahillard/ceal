# Céal Sprint 3 — Phase 4 Auto-Apply with Approval Queue

## CONTEXT
You are working on the Céal project — an AI-powered career signal engine.
The project root is the `ceal/` directory containing `src/`, `tests/`, `pyproject.toml`, `requirements.txt`.

**Branch state**: You are on `main`. This branch contains:
- Phase 1 (scrape → normalize → rank pipeline)
- Phase 2 + 2B (resume tailoring, demo mode, batch, export, persistence)
- Sprint 1 (FastAPI + Jinja2 web UI: Dashboard, Jobs, Demo)
- Sprint 2 (Phase 3 CRM: Kanban board, state-machine status transitions, stale reminders, prompt v1.1)
- **179 passing tests**, ruff clean, CI green (6-job matrix: lint, unit 3.11/3.12, integration 3.11/3.12, coverage ≥80%)

**PRE-FLIGHT CHECK**: Before starting any work, verify these files exist:
```bash
ls src/web/app.py src/web/routes/dashboard.py src/web/routes/jobs.py src/web/routes/demo.py src/web/routes/applications.py
ls src/web/templates/base.html src/web/templates/dashboard.html src/web/templates/jobs.html src/web/templates/demo.html src/web/templates/applications.html src/web/templates/reminders.html
ls src/models/database.py src/models/entities.py src/models/schema.sql
ls src/tailoring/engine.py src/tailoring/models.py src/tailoring/db_models.py src/tailoring/resume_parser.py src/tailoring/skill_extractor.py src/tailoring/persistence.py
ls src/demo.py src/fetcher.py src/batch.py src/export.py
ls src/main.py pyproject.toml requirements.txt
ls data/resume.txt
ls tests/unit/test_web.py tests/unit/test_crm.py tests/unit/test_database.py tests/unit/test_tailoring_engine.py
ls .github/workflows/ci.yml
```
If ANY of those files are missing, STOP and report which ones. Do NOT proceed without them.

**Your job**: Build Phase 4 Auto-Apply — an application form data model, a pre-fill engine that maps resume + tailored bullets to common ATS fields, an approval queue web UI for human review before submit, and comprehensive documentation updates to bring README + synthesis doc up to date.

---

## CRITICAL RULES (Anti-Hallucination)

1. **READ before WRITE**: Before modifying ANY file, read it first. Never assume file contents.
2. **EXISTING FILES — DO NOT DUPLICATE OR RENAME**:
   - `src/models/database.py` — contains: `get_session()`, `init_db()`, `upsert_job()`, `upsert_jobs_batch()`, `get_unranked_jobs()`, `update_job_ranking()`, `assign_company_tiers()`, `get_top_matches()`, `log_scrape_run()`, `create_resume_profile()`, `link_resume_skill()`, `get_pipeline_stats()`, `VALID_TRANSITIONS` dict, `update_job_status()`, `get_jobs_by_status()`, `get_application_summary()`, `get_stale_applications()`
   - `src/models/entities.py` — contains: `JobStatus` enum (8 states: SCRAPED, RANKED, APPLIED, RESPONDED, INTERVIEWING, OFFER, REJECTED, ARCHIVED), `JobSource`, `RemoteType`, `SkillCategory`, `Proficiency` enums, plus `RawJobListing`, `JobListingCreate`, `JobListing`, `RankedResult`, `ScrapeLogCreate` models
   - `src/models/schema.sql` — Phase 1 DDL with 7 tables: `job_listings` (status CHECK constraint with all 8 states, `updated_at` trigger), `skills`, `job_skills`, `resume_profiles`, `resume_skills`, `company_tiers`, `scrape_log`. Uses `IF NOT EXISTS`.
   - `src/web/app.py` — FastAPI app factory `create_app()` with lifespan calling `init_db()`. Registers 4 routers: dashboard, jobs, applications, demo. `templates = Jinja2Templates(...)`.
   - `src/web/routes/dashboard.py` — `GET /` wired to `get_pipeline_stats()`, `get_application_summary()`, `get_stale_applications()`
   - `src/web/routes/jobs.py` — `GET /jobs` wired to `get_top_matches()` with tier/score/limit query params
   - `src/web/routes/applications.py` — `GET /applications` (Kanban board), `POST /applications/{job_id}/status` (state-machine transition), `GET /applications/reminders` (stale applications)
   - `src/web/routes/demo.py` — `GET /demo`, `POST /demo` wired to ResumeProfileParser + SkillOverlapAnalyzer + TailoringEngine
   - `src/web/templates/base.html` — Shared layout with nav: Dashboard, Jobs, Applications, Demo
   - `src/web/templates/applications.html` — Kanban board with 7 status columns, tier-colored borders, transition buttons
   - `src/tailoring/engine.py` — `TailoringEngine` class, `CURRENT_PROMPT_VERSION = "v1.1"`, `_SYSTEM_PROMPT` (anti-keyword-stuffing), `_TIER_PROMPTS` (3 tiers), `_parse_llm_response()` (validates xyz_format claims), `_call_claude_api()` via httpx
   - `src/tailoring/models.py` — Pydantic v2: `TailoringRequest`, `TailoredBullet` (with `enforce_xyz_compliance`), `TailoringResult`, `SkillGap`, `ParsedBullet`, `ParsedResume`
   - `src/tailoring/db_models.py` — SQLAlchemy ORM: `Base`, `ParsedBulletTable`, `TailoringRequestTable`, `TailoredBulletTable`, `SkillGapTable`
   - `src/tailoring/resume_parser.py` — `ResumeProfileParser` class
   - `src/tailoring/skill_extractor.py` — `SkillOverlapAnalyzer` class
   - `src/tailoring/persistence.py` — `save_tailoring_result()`, `get_tailoring_results()`, `list_tailored_jobs()`
   - `src/demo.py` — Demo mode orchestrator
   - `src/batch.py` — Batch tailoring with semaphore rate limiting
   - `src/export.py` — `.docx` export via python-docx
   - `src/main.py` — CLI entry with flags: `--query`, `--location`, `--max-results`, `--rank-only`, `--no-rank`, `--tailor`, `--top`, `--web`, `--port`, `--demo`, `--job-url`, `--batch`, `--export`
   - `data/resume.txt` — Josh's resume in parser-compatible format
3. **IMPORT PATHS**: All imports use `src.` prefix (e.g., `from src.models.database import get_pipeline_stats`). The project uses `pythonpath = ["."]` in pyproject.toml.
4. **PYTHON VERSION**: Target Python 3.10+. Do NOT use `datetime.UTC` (use `datetime.timezone.utc`). Do NOT use `StrEnum` (use `str, Enum`). CHECK `src/tailoring/db_models.py` — if `_utcnow()` uses `datetime.UTC`, fix it to `datetime.timezone.utc`.
5. **ASYNC**: The entire codebase is async. Database uses `AsyncSession` with `aiosqlite`. All database functions are `async def`. FastAPI routes that call database functions must be `async def`.
6. **DATABASE**: SQLite via `sqlite+aiosqlite:///data/ceal.db`. Phase 1 tables in `schema.sql`. Phase 2 tables managed by Alembic. New Phase 4 tables go in `schema.sql` using `CREATE TABLE IF NOT EXISTS` (same pattern as Phase 1 tables). The `job_listings.status` column already supports all 8 lifecycle states.
7. **RUFF CONFIG**: `target-version = "py310"`, `line-length = 120`. Ignored rules: `UP017`, `UP042`, `E501`, `SIM102`, `SIM105`, `SIM108`, `B017`, `B904`. Run `ruff check src/ tests/` before committing.
8. **TESTS**: `pytest` with `asyncio_mode = "strict"`. All async tests need `@pytest.mark.asyncio`. Test isolation uses StaticPool in-memory SQLite with explicit table drops (FK checks disabled) between test classes. Web route tests MUST mock all database functions (CI has no `data/ceal.db`).
9. **NO SECRETS**: Never hardcode API keys. Load from environment only.
10. **WEB PATTERNS**: Follow Sprint 1/2 patterns exactly — route modules in `src/web/routes/`, templates extending `base.html`, router registered in `app.py` via `app.include_router()`.
11. **CRM INTEGRATION**: The approval queue must integrate with the existing CRM. When an application is approved, use `update_job_status()` to transition the job to `"applied"` status via the existing state machine. The `VALID_TRANSITIONS` dict must be respected — do NOT bypass it.

---

## TASK 1: Add Phase 4 Schema — `src/models/schema.sql`

**Read first**: `src/models/schema.sql` — read the ENTIRE file to understand existing table patterns

Add these tables AFTER the existing `scrape_log` table and BEFORE any seed data. Use `CREATE TABLE IF NOT EXISTS` to match existing patterns.

### 1a. `applications` table

```sql
-- ---------------------------------------------------------------------------
-- Phase 4: Auto-Apply
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES job_listings(id),
    profile_id INTEGER NOT NULL REFERENCES resume_profiles(id),
    status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft', 'ready', 'approved', 'submitted', 'withdrawn')),
    cover_letter TEXT,
    confidence_score REAL CHECK(confidence_score IS NULL OR (confidence_score >= 0.0 AND confidence_score <= 1.0)),
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    submitted_at TEXT,
    UNIQUE(job_id, profile_id)
);

CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status);
CREATE INDEX IF NOT EXISTS idx_applications_job_id ON applications(job_id);
```

### 1b. `application_fields` table

```sql
CREATE TABLE IF NOT EXISTS application_fields (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    field_name TEXT NOT NULL,
    field_type TEXT NOT NULL DEFAULT 'text' CHECK(field_type IN ('text', 'textarea', 'select', 'checkbox', 'radio', 'file', 'date', 'email', 'phone', 'url')),
    field_value TEXT,
    confidence REAL CHECK(confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)),
    source TEXT CHECK(source IS NULL OR source IN ('resume', 'profile', 'tailored', 'manual', 'ai_generated')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(application_id, field_name)
);

CREATE INDEX IF NOT EXISTS idx_appfields_application_id ON application_fields(application_id);
```

### 1c. `updated_at` trigger for applications

```sql
CREATE TRIGGER IF NOT EXISTS trg_applications_updated_at
    AFTER UPDATE ON applications
    FOR EACH ROW
BEGIN
    UPDATE applications SET updated_at = datetime('now') WHERE id = OLD.id;
END;
```

**Verification**: Run `python -c "import asyncio; from src.models.database import init_db; asyncio.run(init_db())"` — should create tables without error.

---

## TASK 2: Add Phase 4 Pydantic Models — `src/models/entities.py`

**Read first**: `src/models/entities.py` — read the ENTIRE file

Add these models AFTER the existing `ScrapeLog` model, at the end of the file:

### 2a. `ApplicationStatus` enum

```python
class ApplicationStatus(str, Enum):
    """Status lifecycle for auto-apply applications."""
    DRAFT = "draft"           # Pre-filled, awaiting review
    READY = "ready"           # Reviewed and edited, awaiting approval
    APPROVED = "approved"     # Human approved, ready to submit
    SUBMITTED = "submitted"   # Application sent
    WITHDRAWN = "withdrawn"   # User cancelled
```

### 2b. `FieldType` enum

```python
class FieldType(str, Enum):
    """Common ATS form field types."""
    TEXT = "text"
    TEXTAREA = "textarea"
    SELECT = "select"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    FILE = "file"
    DATE = "date"
    EMAIL = "email"
    PHONE = "phone"
    URL = "url"
```

### 2c. `FieldSource` enum

```python
class FieldSource(str, Enum):
    """Where the pre-filled value came from."""
    RESUME = "resume"           # Pulled from resume.txt
    PROFILE = "profile"         # From resume_profiles table
    TAILORED = "tailored"       # From Phase 2 tailoring output
    MANUAL = "manual"           # User typed it
    AI_GENERATED = "ai_generated"  # LLM generated (e.g., cover letter)
```

### 2d. Pydantic models

```python
class ApplicationFieldCreate(BaseModel):
    """A single pre-filled form field."""
    field_name: str = Field(..., min_length=1, max_length=200)
    field_type: FieldType = FieldType.TEXT
    field_value: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    source: FieldSource | None = None


class ApplicationCreate(BaseModel):
    """Create a new auto-apply application draft."""
    job_id: int
    profile_id: int = 1  # Default to primary resume profile
    cover_letter: str | None = None
    confidence_score: float | None = Field(default=None, ge=0.0, le=1.0)
    fields: list[ApplicationFieldCreate] = Field(default_factory=list)
    notes: str | None = None


class Application(BaseModel):
    """Full application record from database."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    profile_id: int
    status: ApplicationStatus
    cover_letter: str | None = None
    confidence_score: float | None = None
    notes: str | None = None
    created_at: str
    updated_at: str
    submitted_at: str | None = None
    fields: list[ApplicationFieldCreate] = Field(default_factory=list)

    # Joined fields from job_listings (populated by queries)
    job_title: str | None = None
    company_name: str | None = None
    company_tier: int | None = None
    match_score: float | None = None
    url: str | None = None
```

**Verification**: `ruff check src/models/entities.py` and `python -c "from src.models.entities import ApplicationCreate, ApplicationStatus; print('OK')"`

---

## TASK 3: Add Phase 4 Database Functions — `src/models/database.py`

**Read first**: `src/models/database.py` — read the ENTIRE file

Add these functions AFTER the existing `get_stale_applications()` function:

### 3a. `create_application()`

```python
# ---------------------------------------------------------------------------
# Phase 4: Auto-Apply
# ---------------------------------------------------------------------------

async def create_application(app: "ApplicationCreate") -> int:
    """
    Create a new application draft with pre-filled fields.

    Returns the application ID.

    Interview point: "Applications are idempotent per (job_id, profile_id).
    Re-running pre-fill on the same job updates the existing draft rather
    than creating duplicates — same ON CONFLICT pattern as the scraper."
    """
    from src.models.entities import ApplicationCreate  # noqa: F811 — deferred to avoid circular

    async with get_session() as session:
        result = await session.execute(
            text("""
                INSERT INTO applications (job_id, profile_id, cover_letter, confidence_score, notes)
                VALUES (:job_id, :profile_id, :cover_letter, :confidence_score, :notes)
                ON CONFLICT(job_id, profile_id) DO UPDATE SET
                    cover_letter = :cover_letter,
                    confidence_score = :confidence_score,
                    notes = :notes,
                    status = 'draft'
                RETURNING id
            """),
            {
                "job_id": app.job_id,
                "profile_id": app.profile_id,
                "cover_letter": app.cover_letter,
                "confidence_score": app.confidence_score,
                "notes": app.notes,
            },
        )
        app_id = result.scalar_one()

        # Upsert fields
        for field in app.fields:
            await session.execute(
                text("""
                    INSERT INTO application_fields (application_id, field_name, field_type, field_value, confidence, source)
                    VALUES (:app_id, :field_name, :field_type, :field_value, :confidence, :source)
                    ON CONFLICT(application_id, field_name) DO UPDATE SET
                        field_value = :field_value,
                        confidence = :confidence,
                        source = :source
                """),
                {
                    "app_id": app_id,
                    "field_name": field.field_name,
                    "field_type": field.field_type.value,
                    "field_value": field.field_value,
                    "confidence": field.confidence,
                    "source": field.source.value if field.source else None,
                },
            )

    logger.info("application_created", app_id=app_id, job_id=app.job_id)
    return app_id
```

### 3b. `get_application()`

```python
async def get_application(app_id: int) -> dict | None:
    """Get a single application with its fields and joined job data."""
    async with get_session() as session:
        result = await session.execute(
            text("""
                SELECT a.id, a.job_id, a.profile_id, a.status, a.cover_letter,
                       a.confidence_score, a.notes, a.created_at, a.updated_at, a.submitted_at,
                       j.title as job_title, j.company_name, j.company_tier,
                       j.match_score, j.url
                FROM applications a
                JOIN job_listings j ON a.job_id = j.id
                WHERE a.id = :app_id
            """),
            {"app_id": app_id},
        )
        app_row = result.first()
        if not app_row:
            return None

        app_dict = dict(app_row._mapping)

        # Fetch fields
        fields_result = await session.execute(
            text("""
                SELECT field_name, field_type, field_value, confidence, source
                FROM application_fields
                WHERE application_id = :app_id
                ORDER BY id
            """),
            {"app_id": app_id},
        )
        app_dict["fields"] = [dict(row._mapping) for row in fields_result]

    return app_dict
```

### 3c. `get_approval_queue()`

```python
async def get_approval_queue(status: str = "draft") -> list[dict]:
    """
    Get all applications awaiting review, with joined job data.
    Default: show drafts (pre-filled, not yet reviewed).
    """
    async with get_session() as session:
        result = await session.execute(
            text("""
                SELECT a.id, a.job_id, a.profile_id, a.status, a.cover_letter,
                       a.confidence_score, a.notes, a.created_at, a.updated_at,
                       j.title as job_title, j.company_name, j.company_tier,
                       j.match_score, j.url
                FROM applications a
                JOIN job_listings j ON a.job_id = j.id
                WHERE a.status = :status
                ORDER BY a.confidence_score DESC NULLS LAST, j.match_score DESC NULLS LAST
            """),
            {"status": status},
        )
        return [dict(row._mapping) for row in result]
```

### 3d. `update_application_status()`

```python
_APP_VALID_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"ready", "withdrawn"},
    "ready": {"approved", "draft", "withdrawn"},
    "approved": {"submitted", "draft", "withdrawn"},
    "submitted": {"withdrawn"},
    "withdrawn": {"draft"},  # Allow re-drafting a withdrawn application
}


async def update_application_status(app_id: int, new_status: str) -> dict:
    """
    Transition an application with state-machine validation.

    When transitioning to 'approved', also transitions the parent job_listing
    to 'applied' status via update_job_status() — keeping CRM in sync.
    """
    async with get_session() as session:
        result = await session.execute(
            text("SELECT id, status, job_id FROM applications WHERE id = :app_id"),
            {"app_id": app_id},
        )
        app = result.first()
        if not app:
            raise ValueError(f"Application {app_id} not found")

        current_status = app[1]
        valid_next = _APP_VALID_TRANSITIONS.get(current_status, set())

        if new_status not in valid_next:
            raise ValueError(
                f"Invalid application transition: {current_status} → {new_status}. "
                f"Valid: {valid_next or 'none'}"
            )

        update_fields = {"new_status": new_status, "app_id": app_id}

        if new_status == "submitted":
            await session.execute(
                text("UPDATE applications SET status = :new_status, submitted_at = datetime('now') WHERE id = :app_id"),
                update_fields,
            )
        else:
            await session.execute(
                text("UPDATE applications SET status = :new_status WHERE id = :app_id"),
                update_fields,
            )

    # Sync CRM: when approved, mark the job as "applied"
    if new_status == "approved":
        job_id = app[2]
        try:
            await update_job_status(job_id, "applied")
        except ValueError:
            pass  # Job may already be in a later state — that's OK

    logger.info("application_status_updated", app_id=app_id, from_status=current_status, to_status=new_status)
    return {"app_id": app_id, "previous_status": current_status, "new_status": new_status}
```

### 3e. `get_application_stats()`

```python
async def get_application_stats() -> dict:
    """Get application counts by status for the dashboard."""
    async with get_session() as session:
        result = await session.execute(
            text("""
                SELECT status, COUNT(*) as count
                FROM applications
                GROUP BY status
            """)
        )
        return {row[0]: row[1] for row in result}
```

**Verification**: `ruff check src/models/database.py`

---

## TASK 4: Build Pre-Fill Engine — `src/apply/prefill.py`

**Read first**: `data/resume.txt` — understand the resume format
**Read second**: `src/tailoring/engine.py` — understand the LLM call pattern

Create directory `src/apply/` with `__init__.py` and `prefill.py`:

### 4a. `src/apply/__init__.py`

```python
"""Phase 4: Auto-Apply with approval queue."""
```

### 4b. `src/apply/prefill.py`

```python
"""Pre-fill engine: maps resume data + tailored bullets to common ATS form fields."""
from __future__ import annotations

import os
import re
from pathlib import Path

import structlog

from src.models.entities import ApplicationCreate, ApplicationFieldCreate, FieldSource, FieldType

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Common ATS field definitions
# ---------------------------------------------------------------------------

# Standard fields found on most job application forms.
# Each tuple: (field_name, field_type, source_strategy)
COMMON_ATS_FIELDS: list[tuple[str, FieldType, FieldSource]] = [
    ("full_name", FieldType.TEXT, FieldSource.RESUME),
    ("email", FieldType.EMAIL, FieldSource.RESUME),
    ("phone", FieldType.PHONE, FieldSource.RESUME),
    ("location", FieldType.TEXT, FieldSource.RESUME),
    ("linkedin_url", FieldType.URL, FieldSource.RESUME),
    ("portfolio_url", FieldType.URL, FieldSource.PROFILE),
    ("current_company", FieldType.TEXT, FieldSource.RESUME),
    ("current_title", FieldType.TEXT, FieldSource.RESUME),
    ("years_experience", FieldType.TEXT, FieldSource.RESUME),
    ("education", FieldType.TEXT, FieldSource.RESUME),
    ("work_authorization", FieldType.SELECT, FieldSource.PROFILE),
    ("requires_sponsorship", FieldType.CHECKBOX, FieldSource.PROFILE),
    ("desired_salary", FieldType.TEXT, FieldSource.PROFILE),
    ("start_date", FieldType.TEXT, FieldSource.PROFILE),
    ("resume_text", FieldType.TEXTAREA, FieldSource.RESUME),
    ("cover_letter", FieldType.TEXTAREA, FieldSource.AI_GENERATED),
]


class PreFillEngine:
    """
    Maps resume data to common ATS form fields with confidence scoring.

    Interview point: "The pre-fill engine uses a deterministic extraction
    pipeline for structured fields (name, email, phone) and reserves LLM
    calls only for unstructured content (cover letters). This keeps the
    system predictable and testable while using AI where it adds value."
    """

    def __init__(self, resume_path: str | None = None):
        self._resume_path = resume_path or str(Path("data") / "resume.txt")
        self._resume_text: str | None = None
        self._parsed_fields: dict[str, str] = {}

    def _load_resume(self) -> str:
        """Load and cache resume text."""
        if self._resume_text is None:
            with open(self._resume_path) as f:
                self._resume_text = f.read()
            self._parse_resume_fields()
        return self._resume_text

    def _parse_resume_fields(self) -> None:
        """Extract structured fields from resume text using regex."""
        text = self._resume_text or ""

        # Name: first non-empty line
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        if lines:
            self._parsed_fields["full_name"] = lines[0]

        # Email
        email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
        if email_match:
            self._parsed_fields["email"] = email_match.group()

        # Phone
        phone_match = re.search(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", text)
        if phone_match:
            self._parsed_fields["phone"] = phone_match.group()

        # LinkedIn URL
        linkedin_match = re.search(r"linkedin\.com/in/[\w-]+", text, re.IGNORECASE)
        if linkedin_match:
            self._parsed_fields["linkedin_url"] = "https://" + linkedin_match.group()

        # Location: look for "City, ST" pattern
        location_match = re.search(r"([A-Z][a-z]+(?:\s[A-Z][a-z]+)*,\s*[A-Z]{2})", text)
        if location_match:
            self._parsed_fields["location"] = location_match.group()

        # Current company + title: look for most recent experience
        exp_match = re.search(r"(?:EXPERIENCE|Experience).*?\n+(.+?)(?:\s*[—–-]\s*)(.+?)(?:\s*\(|\n)", text, re.DOTALL)
        if exp_match:
            self._parsed_fields["current_company"] = exp_match.group(1).strip()
            self._parsed_fields["current_title"] = exp_match.group(2).strip()

        # Education
        edu_match = re.search(r"(?:EDUCATION|Education).*?\n+(.+?)(?:\n\n|\Z)", text, re.DOTALL)
        if edu_match:
            self._parsed_fields["education"] = edu_match.group(1).strip().split("\n")[0].strip()

    def prefill_application(self, job_id: int, profile_id: int = 1) -> ApplicationCreate:
        """
        Generate a pre-filled application for a job listing.

        Returns an ApplicationCreate with all extractable fields populated
        and confidence scores reflecting extraction reliability.
        """
        self._load_resume()

        fields: list[ApplicationFieldCreate] = []
        total_confidence = 0.0
        field_count = 0

        for field_name, field_type, source in COMMON_ATS_FIELDS:
            value = self._parsed_fields.get(field_name)
            confidence: float | None = None

            if field_name == "resume_text":
                value = self._resume_text
                confidence = 1.0
            elif field_name == "cover_letter":
                value = None  # Placeholder — filled by LLM in future
                confidence = None
                source = FieldSource.AI_GENERATED
            elif field_name in ("work_authorization", "requires_sponsorship", "desired_salary", "start_date"):
                # Profile fields — default placeholders
                value = self._get_profile_default(field_name)
                confidence = 0.6  # User should verify
            elif value:
                confidence = 0.95 if field_name in ("email", "phone", "full_name") else 0.8
            else:
                confidence = 0.0
                value = None

            if confidence is not None:
                total_confidence += confidence
                field_count += 1

            fields.append(
                ApplicationFieldCreate(
                    field_name=field_name,
                    field_type=field_type,
                    field_value=value,
                    confidence=confidence,
                    source=source if value else None,
                )
            )

        avg_confidence = total_confidence / field_count if field_count > 0 else 0.0

        logger.info(
            "application_prefilled",
            job_id=job_id,
            fields_populated=sum(1 for f in fields if f.field_value),
            fields_total=len(fields),
            avg_confidence=round(avg_confidence, 2),
        )

        return ApplicationCreate(
            job_id=job_id,
            profile_id=profile_id,
            confidence_score=round(avg_confidence, 2),
            fields=fields,
            notes=f"Auto pre-filled {sum(1 for f in fields if f.field_value)}/{len(fields)} fields",
        )

    @staticmethod
    def _get_profile_default(field_name: str) -> str | None:
        """Return sensible defaults for profile-level fields."""
        defaults = {
            "work_authorization": "Authorized to work in the US",
            "requires_sponsorship": "No",
            "desired_salary": "",
            "start_date": "Immediately available",
        }
        return defaults.get(field_name)
```

**Verification**: `ruff check src/apply/prefill.py` and `python -c "from src.apply.prefill import PreFillEngine; print('OK')"`

---

## TASK 5: Build Approval Queue Routes — `src/web/routes/apply.py`

**Read first**: `src/web/routes/applications.py` — follow the exact same pattern

Create `src/web/routes/apply.py`:

```python
"""Auto-apply approval queue routes."""
from __future__ import annotations

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import RedirectResponse

from src.apply.prefill import PreFillEngine
from src.models.database import (
    create_application,
    get_application,
    get_approval_queue,
    get_application_stats,
    get_top_matches,
    update_application_status,
)
from src.web.app import templates

router = APIRouter(prefix="/apply", tags=["apply"])


@router.get("/")
async def approval_queue(request: Request, status: str = Query("draft")):
    """Render the approval queue showing applications awaiting review."""
    queue = await get_approval_queue(status=status)
    stats = await get_application_stats()
    return templates.TemplateResponse(
        "approval_queue.html",
        {
            "request": request,
            "queue": queue,
            "stats": stats,
            "current_filter": status,
        },
    )


@router.post("/prefill/{job_id}")
async def prefill_job(request: Request, job_id: int):
    """Pre-fill an application for a specific job and redirect to review."""
    engine = PreFillEngine()
    app_create = engine.prefill_application(job_id=job_id)
    app_id = await create_application(app_create)
    return RedirectResponse(url=f"/apply/{app_id}", status_code=303)


@router.get("/{app_id}")
async def review_application(request: Request, app_id: int):
    """Render the application review page with pre-filled fields."""
    application = await get_application(app_id)
    if not application:
        return RedirectResponse(url="/apply", status_code=303)
    return templates.TemplateResponse(
        "application_review.html",
        {
            "request": request,
            "application": application,
        },
    )


@router.post("/{app_id}/status")
async def update_status(request: Request, app_id: int, new_status: str = Form(...)):
    """Transition an application status (approve, submit, withdraw, etc.)."""
    try:
        await update_application_status(app_id, new_status)
        return RedirectResponse(url="/apply", status_code=303)
    except ValueError as e:
        application = await get_application(app_id)
        return templates.TemplateResponse(
            "application_review.html",
            {
                "request": request,
                "application": application,
                "error": str(e),
            },
        )
```

---

## TASK 6: Register Apply Route + Update Nav

### 6a. Register in `src/web/app.py`

**Read first**: `src/web/app.py` — find the router imports and registrations

Add:
```python
from src.web.routes import applications, apply, dashboard, demo, jobs
# ...
app.include_router(apply.router)
```

### 6b. Update `src/web/templates/base.html`

**Read first**: `src/web/templates/base.html`

Add "Auto-Apply" link to the navigation bar, between "Applications" and "Demo":
```html
<a href="/apply">Auto-Apply</a>
```

---

## TASK 7: Build Phase 4 Templates

**Read first**: `src/web/templates/applications.html` — understand the existing card/column layout and CSS classes

### 7a. Create `src/web/templates/approval_queue.html`

Extends `base.html`. Approval queue layout:

- **Status filter tabs** at top: Draft | Ready | Approved | Submitted | Withdrawn (highlight current)
- **Stats bar**: total applications, counts per status
- **Queue cards**, one per application, sorted by confidence score descending:
  - Company name, job title, match score (as %)
  - Tier badge (Tier 1 green, Tier 2 yellow, Tier 3 blue)
  - Confidence score bar (visual indicator: green ≥0.8, yellow ≥0.5, red <0.5)
  - Pre-filled field count: "12/16 fields populated"
  - Created date
  - Action buttons based on current status:
    - Draft: "Review →" (links to /apply/{app_id}), "Withdraw"
    - Ready: "Approve ✓", "Back to Draft", "Withdraw"
    - Approved: "Mark Submitted", "Back to Draft", "Withdraw"
    - Submitted: "Withdraw"
    - Withdrawn: "Re-draft"
  - Each action button is a POST form to `/apply/{app_id}/status`
- **Empty state** per filter: "No applications in [status] — use the Pre-Fill button on the Jobs page to get started"
- **"Pre-Fill Top Matches" button** at top: links to a batch pre-fill action (stretch goal, can just link to /jobs for now)

### 7b. Create `src/web/templates/application_review.html`

Extends `base.html`. Detailed review page for a single application:

- **Error banner** if `error` variable is set
- **Header**: Company name + Job title + Match score + Tier badge + Confidence score
- **Link to original listing**: job URL (opens in new tab)
- **Cover letter section**: textarea (pre-filled or empty), editable
- **Form fields table**: one row per application_field
  - Field name (human-readable label)
  - Field type badge
  - Current value (editable input matching field_type)
  - Confidence indicator (green/yellow/red dot)
  - Source badge (resume / profile / tailored / manual / AI)
- **Action buttons at bottom**:
  - "Mark Ready" (draft → ready)
  - "Approve" (ready → approved)
  - "Withdraw" (any → withdrawn)
  - "Back to Queue" (link to /apply)
- **Notes section**: textarea for reviewer notes

### 7c. Add "Pre-Fill" button to Jobs page

**Read first**: `src/web/templates/jobs.html`

Add a "Pre-Fill Application" button to each job card/row. The button is a POST form:
```html
<form method="post" action="/apply/prefill/{{ job.id }}" style="display:inline">
    <button type="submit" class="prefill-btn">Pre-Fill</button>
</form>
```

### 7d. Update styles

**Read first**: `src/web/static/style.css` (if it exists) or the `<style>` block in `base.html`

Add styles for:
- `.confidence-bar` — horizontal bar indicator (width = confidence %)
- `.confidence-high` (≥0.8) — green background
- `.confidence-med` (≥0.5) — yellow background
- `.confidence-low` (<0.5) — red background
- `.source-badge` — small pill showing field source
- `.status-tabs` — horizontal tab bar for queue filters
- `.status-tab.active` — highlighted current tab
- `.review-field` — form field row in review page
- `.prefill-btn` — small button for pre-fill action on jobs page

---

## TASK 8: Write Phase 4 Tests

**Read first**: `tests/unit/test_crm.py` — follow the exact same patterns for database + web route testing

Create `tests/unit/test_autoapply.py`:

### 8a. Schema tests
- `test_applications_table_created` — verify applications table exists after init_db
- `test_application_fields_table_created` — verify application_fields table exists

### 8b. Pre-fill engine tests
- `test_prefill_extracts_name_from_resume` — verify full_name field extracted
- `test_prefill_extracts_email_from_resume` — verify email field extracted
- `test_prefill_extracts_phone_from_resume` — verify phone field extracted
- `test_prefill_returns_application_create_model` — verify return type is ApplicationCreate
- `test_prefill_confidence_score_between_0_and_1` — verify overall confidence
- `test_prefill_populates_common_fields` — verify at least 8 fields have values

### 8c. Database function tests
- `test_create_application_returns_id` — create and verify ID returned
- `test_create_application_idempotent` — create same (job_id, profile_id) twice, verify single record
- `test_get_application_returns_fields` — create with fields, verify fields returned
- `test_get_approval_queue_filters_by_status` — create draft + ready, verify filter works
- `test_update_application_status_valid` — draft → ready
- `test_update_application_status_invalid` — draft → submitted raises ValueError
- `test_update_application_status_approved_syncs_crm` — approved transition calls update_job_status

### 8d. Web route tests (mock database functions)
- `test_approval_queue_returns_200`
- `test_prefill_redirects_to_review`
- `test_review_application_returns_200`
- `test_status_update_redirects`
- `test_invalid_status_shows_error`

### 8e. Model tests
- `test_application_status_enum_values` — verify all 5 states
- `test_application_create_validation` — confidence must be 0.0-1.0
- `test_field_type_enum_values` — verify all 10 types

All tests must be `async def` with `@pytest.mark.asyncio`. Web route tests MUST mock all database functions.

**Verification**: `pytest tests/unit/test_autoapply.py -v`

---

## TASK 9: Update Dashboard with Auto-Apply Stats

**Read first**: `src/web/routes/dashboard.py` — read the current imports and handler

Add `get_application_stats` to the dashboard:

```python
from src.models.database import (
    get_application_stats,
    get_application_summary,
    get_pipeline_stats,
    get_stale_applications,
)

@router.get("/")
async def dashboard(request: Request):
    stats = await get_pipeline_stats()
    app_summary = await get_application_summary()
    stale = await get_stale_applications(days=7)
    apply_stats = await get_application_stats()
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "stats": stats,
            "app_summary": app_summary,
            "stale_count": len(stale),
            "apply_stats": apply_stats,
        },
    )
```

**Read first**: `src/web/templates/dashboard.html`

Add an "Auto-Apply Pipeline" card showing:
- Applications by status (draft / ready / approved / submitted)
- Link to `/apply` for the approval queue
- "Pre-fill top matches" quick action

**IMPORTANT**: Update `tests/unit/test_web.py` — the dashboard test MUST mock `get_application_stats()` in addition to existing mocks. CI has no database, so unmocked DB calls will crash.

---

## TASK 10: Update README + Documentation

**Read first**: `README.md` — read the ENTIRE file

The README is severely outdated (still says "93 tests", only documents Phase 1). Rewrite it to reflect the current state of the project. Preserve the existing tone and structure but update ALL stale data:

### 10a. README updates

**Update these specific sections:**

1. **Tech Stack table**: Update test count from "93" to actual count after Sprint 3. Add `fastapi`, `jinja2` to the table.

2. **Project Structure**: Replace the file tree with the current structure including `src/web/`, `src/tailoring/`, `src/apply/`, all route files, all template files.

3. **Usage section**: Add ALL current CLI flags including `--web`, `--port`, `--tailor`, `--demo`, `--job-url`, `--batch`, `--export`. Add web UI launch instructions.

4. **Database Schema**: Update from "Seven normalized tables" to actual count (7 Phase 1 + Phase 2 ORM + 2 Phase 4).

5. **Running Tests**: Update command and mention CI matrix (Python 3.11 + 3.12).

6. **Roadmap**: Update all phase statuses:
   - Phase 1: ✅ Complete
   - Phase 2: ✅ Complete — demo mode, batch tailoring, .docx export, prompt v1.1
   - Phase 3: ✅ Complete — CRM Kanban board, state-machine status transitions, stale reminders
   - Phase 4: ✅ Complete — auto-apply pre-fill engine, approval queue, confidence scoring

7. **Add Web UI section**: Document the 5-page web app (Dashboard, Jobs, Applications, Auto-Apply, Demo) with launch instructions.

8. **Update Architecture diagram**: Add Phase 2 (tailoring) and Phase 4 (auto-apply) stages to the pipeline diagram.

### 10b. Update `Ceal_Plain_Language_Synthesis.md`

**Read first**: `Ceal_Plain_Language_Synthesis.md` if it exists in the project root (it may be in the parent Ceal folder, not the ceal/ repo — if you cannot find it, SKIP this subtask)

If found, update:
- Part 1 phase table: all phases marked complete
- Part 8 test suite: update counts
- Part 9 current status: update all metrics
- Part 12 "How to Read the Code": add `src/web/` and `src/apply/` entry points

---

## TASK 11: Lint, Test, Commit

Run these commands IN ORDER:

```bash
# Lint
ruff check src/ tests/ --fix
ruff check src/ tests/

# Unit tests
pytest tests/unit/ -v --tb=short

# Integration tests
pytest tests/integration/ -v --tb=short

# Coverage
pytest tests/ --cov=src --cov-report=term-missing

# Verify no datetime.UTC usage
grep -rn "datetime\.UTC" src/ tests/ || echo "No datetime.UTC found — good"

# Verify no hardcoded keys
grep -rn "sk-ant-" src/ tests/ || echo "No hardcoded keys — good"
```

Fix any failures before proceeding. ALL existing tests (179+) must continue to pass plus the new Phase 4 tests.

```bash
git add -A
git diff --cached --stat
git commit -m "feat(auto-apply): Phase 4 pre-fill engine + approval queue + docs overhaul

- Pre-fill engine extracts resume fields with confidence scoring
- Approval queue UI: draft → ready → approved → submitted lifecycle
- State-machine validation for application status transitions
- CRM sync: approved applications auto-transition job to 'applied'
- New schema: applications + application_fields tables
- 5-page web UI: Dashboard, Jobs, Applications, Auto-Apply, Demo
- README fully updated to reflect current project state
- Comprehensive test coverage for pre-fill, DB functions, web routes

Phase: Sprint 3 — Phase 4 Auto-Apply
Personas: AI Architect, Backend Engineer, Data Engineer, DPM"
git push origin main
```

---

## VERIFICATION CHECKLIST

Before you say you're done, confirm ALL of these:

- [ ] `ruff check src/ tests/` exits clean (zero errors)
- [ ] `pytest tests/unit/ -v` passes (all existing 179+ plus new auto-apply tests)
- [ ] `pytest tests/integration/ -v` passes
- [ ] `pytest tests/ --cov=src` shows ≥80% coverage
- [ ] `python -m src.main --web` starts server on port 8000
- [ ] `http://localhost:8000/` shows dashboard with auto-apply stats card
- [ ] `http://localhost:8000/jobs` shows "Pre-Fill" button on each job card
- [ ] Clicking "Pre-Fill" creates a draft application and redirects to review page
- [ ] `http://localhost:8000/apply` shows approval queue with draft applications
- [ ] Status transition buttons work (draft → ready → approved → submitted)
- [ ] Invalid transitions show error (not crash)
- [ ] `http://localhost:8000/apply/{id}` shows field-by-field review with confidence indicators
- [ ] Approving an application transitions the parent job to "applied" in CRM
- [ ] Navigation bar has 5 links: Dashboard, Jobs, Applications, Auto-Apply, Demo
- [ ] README.md reflects current project state (correct test count, all phases, full file tree)
- [ ] No `datetime.UTC` usage anywhere
- [ ] No hardcoded API keys
- [ ] All imports use `src.` prefix
- [ ] Git push to `origin main` successful
