"""
Céal: Async Database Layer

This module provides the async SQLAlchemy engine, session management,
and all database operations for the pipeline.

Architecture decisions (interview-defensible):

1. AsyncSession with aiosqlite — DB I/O doesn't block the event loop
   while the scraper is concurrently fetching 50+ job listings.

2. Context-managed sessions — if the process crashes mid-write, the
   connection is properly closed and the transaction is rolled back.
   This is Resource Management 101 for production systems.

3. Batch upsert with ON CONFLICT — the scraper is idempotent. Run it
   10 times, get the same result. No duplicates, no corruption.

4. WAL mode + PRAGMAs set at connection time — concurrent readers
   (ranker) don't block the writer (scraper).
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from dotenv import load_dotenv
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from src.models.entities import (
    ApplicationCreate,
    JobListingCreate,
    RankedResult,
    ScrapeLogCreate,
)

load_dotenv()
logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Engine Configuration
# ---------------------------------------------------------------------------

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite+aiosqlite:///data/ceal.db",
)

# For in-memory SQLite (tests), we need StaticPool so all sessions
# share the same connection — otherwise each connection gets its own
# empty database. For file-based SQLite, standard pooling is fine.
_engine_kwargs: dict = {"echo": False}
if DATABASE_URL == "sqlite+aiosqlite://":
    # In-memory: single shared connection
    _engine_kwargs["poolclass"] = StaticPool
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    _engine_kwargs["pool_pre_ping"] = True

engine = create_async_engine(DATABASE_URL, **_engine_kwargs)


# ---------------------------------------------------------------------------
# SQLite PRAGMA configuration — runs on every new connection
# ---------------------------------------------------------------------------
# Why: SQLite PRAGMAs are per-connection, not per-database. If you set WAL
# once and never again, new connections revert to the default journal mode.
# This event listener guarantees every connection is configured correctly.

@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragmas(dbapi_conn, connection_record):
    """Configure SQLite for concurrent async access."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")       # concurrent reads + writes
    cursor.execute("PRAGMA foreign_keys=ON")         # enforce referential integrity
    cursor.execute("PRAGMA busy_timeout=5000")       # 5s retry on lock
    cursor.execute("PRAGMA synchronous=NORMAL")      # safe with WAL, 2x faster
    cursor.execute("PRAGMA cache_size=-64000")       # 64MB page cache
    cursor.close()


# ---------------------------------------------------------------------------
# Session Factory
# ---------------------------------------------------------------------------

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Don't expire objects after commit (avoids lazy-load issues in async)
)


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager for database sessions.

    Usage:
        async with get_session() as session:
            await session.execute(...)
            # auto-commits on clean exit, rolls back on exception

    Interview point: "I use an async context manager so the session lifecycle
    is deterministic — commit on success, rollback on failure, close always.
    There's no way to accidentally leave a transaction open."
    """
    session = AsyncSessionLocal()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        logger.exception("database_session_error")
        raise
    finally:
        await session.close()


# ---------------------------------------------------------------------------
# Schema Initialization
# ---------------------------------------------------------------------------

async def init_db(schema_path: str | None = None) -> None:
    """
    Initialize the database from the SQL schema file.
    Idempotent — safe to call on every startup because all CREATE statements
    use IF NOT EXISTS.

    Args:
        schema_path: Path to schema.sql. Defaults to src/models/schema.sql.
    """
    if schema_path is None:
        schema_path = str(
            Path(__file__).parent / "schema.sql"
        )

    schema_sql = Path(schema_path).read_text()

    # We need a smart SQL splitter because TRIGGER bodies contain
    # semicolons inside BEGIN...END blocks. Naive split on ";" breaks them.
    statements = _split_sql_statements(schema_sql)

    async with get_session() as session:
        for stmt in statements:
            if stmt:
                await session.execute(text(stmt))

    logger.info("database_initialized", schema=schema_path)


def _split_sql_statements(sql: str) -> list[str]:
    """
    Split SQL into statements, correctly handling BEGIN...END blocks
    in triggers. Standard semicolons split statements, but semicolons
    inside CREATE TRIGGER ... BEGIN ... END are kept together.
    """
    statements: list[str] = []
    current: list[str] = []
    in_trigger = False

    for line in sql.split("\n"):
        stripped = line.strip()

        # Skip pure comment lines
        if stripped.startswith("--"):
            continue

        # Remove inline comments
        if "--" in stripped:
            stripped = stripped[: stripped.index("--")].strip()

        if not stripped:
            continue

        # Track whether we're inside a trigger block
        if stripped.upper().startswith("CREATE TRIGGER"):
            in_trigger = True

        current.append(stripped)

        if in_trigger:
            # Trigger ends with "END;" on its own line
            if stripped.upper().rstrip(";") == "END":
                in_trigger = False
                full = " ".join(current).rstrip(";")
                if full.strip():
                    statements.append(full)
                current = []
        elif stripped.endswith(";"):
            full = " ".join(current).rstrip(";")
            if full.strip():
                statements.append(full)
            current = []

    # Anything remaining
    if current:
        full = " ".join(current).rstrip(";")
        if full.strip():
            statements.append(full)

    return statements


# ---------------------------------------------------------------------------
# Job Listing Operations
# ---------------------------------------------------------------------------

async def upsert_job(job: JobListingCreate) -> int:
    """
    Insert a job listing, or update it if it already exists.

    Uses SQLite's ON CONFLICT (UPSERT) so the scraper is idempotent.
    Returns the row ID (new or existing).

    Interview point: "The upsert is atomic at the database level — there's
    no read-then-write race condition. ON CONFLICT handles the entire
    check-and-act in a single statement."
    """
    async with get_session() as session:
        result = await session.execute(
            text("""
                INSERT INTO job_listings (
                    external_id, source, title, company_name, url,
                    location, remote_type, salary_min, salary_max,
                    salary_currency, description_raw, description_clean,
                    posting_date, expiry_date
                ) VALUES (
                    :external_id, :source, :title, :company_name, :url,
                    :location, :remote_type, :salary_min, :salary_max,
                    :salary_currency, :description_raw, :description_clean,
                    :posting_date, :expiry_date
                )
                ON CONFLICT(external_id, source) DO UPDATE SET
                    title = excluded.title,
                    company_name = excluded.company_name,
                    url = excluded.url,
                    description_raw = excluded.description_raw,
                    description_clean = excluded.description_clean,
                    salary_min = excluded.salary_min,
                    salary_max = excluded.salary_max
            """),
            {
                "external_id": job.external_id,
                "source": job.source.value,
                "title": job.title,
                "company_name": job.company_name,
                "url": job.url,
                "location": job.location,
                "remote_type": job.remote_type.value,
                "salary_min": job.salary_min,
                "salary_max": job.salary_max,
                "salary_currency": job.salary_currency,
                "description_raw": job.description_raw,
                "description_clean": job.description_clean,
                "posting_date": job.posting_date,
                "expiry_date": job.expiry_date,
            },
        )
        row_id = result.lastrowid or 0

    logger.info(
        "job_upserted",
        external_id=job.external_id,
        source=job.source.value,
        company=job.company_name,
    )
    return row_id


async def upsert_jobs_batch(jobs: list[JobListingCreate]) -> dict:
    """
    Batch upsert multiple jobs in a single transaction.

    Why batch? The scraper finds 50+ jobs per query. Committing each one
    individually means 50 disk syncs. Batching them means ONE disk sync.
    On SQLite with WAL, this is ~10x faster.

    Returns:
        {"inserted": int, "updated": int, "errors": int}
    """
    stats = {"inserted": 0, "updated": 0, "errors": 0}

    async with get_session() as session:
        for job in jobs:
            try:
                # Check if exists first (for accurate stats)
                existing = await session.execute(
                    text(
                        "SELECT id FROM job_listings "
                        "WHERE external_id = :eid AND source = :src"
                    ),
                    {"eid": job.external_id, "src": job.source.value},
                )
                row = existing.first()

                await session.execute(
                    text("""
                        INSERT INTO job_listings (
                            external_id, source, title, company_name, url,
                            location, remote_type, salary_min, salary_max,
                            salary_currency, description_raw, description_clean,
                            posting_date, expiry_date
                        ) VALUES (
                            :external_id, :source, :title, :company_name, :url,
                            :location, :remote_type, :salary_min, :salary_max,
                            :salary_currency, :description_raw, :description_clean,
                            :posting_date, :expiry_date
                        )
                        ON CONFLICT(external_id, source) DO UPDATE SET
                            title = excluded.title,
                            company_name = excluded.company_name,
                            url = excluded.url,
                            description_raw = excluded.description_raw,
                            description_clean = excluded.description_clean,
                            salary_min = excluded.salary_min,
                            salary_max = excluded.salary_max
                    """),
                    {
                        "external_id": job.external_id,
                        "source": job.source.value,
                        "title": job.title,
                        "company_name": job.company_name,
                        "url": job.url,
                        "location": job.location,
                        "remote_type": job.remote_type.value,
                        "salary_min": job.salary_min,
                        "salary_max": job.salary_max,
                        "salary_currency": job.salary_currency,
                        "description_raw": job.description_raw,
                        "description_clean": job.description_clean,
                        "posting_date": job.posting_date,
                        "expiry_date": job.expiry_date,
                    },
                )

                if row:
                    stats["updated"] += 1
                else:
                    stats["inserted"] += 1

            except Exception as exc:
                stats["errors"] += 1
                logger.warning(
                    "job_upsert_failed",
                    external_id=job.external_id,
                    error=str(exc),
                )

    logger.info("batch_upsert_complete", **stats)
    return stats


# ---------------------------------------------------------------------------
# Query Operations
# ---------------------------------------------------------------------------

async def get_unranked_jobs(limit: int = 50) -> list[dict]:
    """
    Fetch jobs that haven't been scored by the LLM ranker yet.

    Returns dicts (not ORM objects) because the ranker stage
    doesn't need the full ORM overhead — it just reads fields
    and produces a RankedResult.
    """
    async with get_session() as session:
        result = await session.execute(
            text("""
                SELECT id, external_id, source, title, company_name,
                       location, remote_type, url,
                       description_clean, description_raw
                FROM job_listings
                WHERE status = 'scraped' AND match_score IS NULL
                ORDER BY scraped_at DESC
                LIMIT :limit
            """),
            {"limit": limit},
        )
        return [dict(row._mapping) for row in result]


async def update_job_ranking(result: RankedResult) -> None:
    """
    Apply the LLM ranker's output to a job listing.
    Updates score, reasoning, model version, and status in one statement.
    """
    async with get_session() as session:
        await session.execute(
            text("""
                UPDATE job_listings
                SET match_score = :score,
                    match_reasoning = :reasoning,
                    rank_model_version = :model_version,
                    status = 'ranked',
                    ranked_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
                WHERE id = :job_id
            """),
            {
                "score": result.match_score,
                "reasoning": result.match_reasoning,
                "model_version": result.rank_model_version,
                "job_id": result.job_id,
            },
        )
    logger.info(
        "job_ranked",
        job_id=result.job_id,
        score=result.match_score,
    )


async def assign_company_tiers() -> int:
    """
    Auto-assign company tiers based on the company_tiers lookup table.
    Uses LIKE matching so 'Stripe' matches 'Stripe, Inc.'.

    Returns the number of jobs updated.
    """
    async with get_session() as session:
        result = await session.execute(
            text("""
                UPDATE job_listings
                SET company_tier = (
                    SELECT ct.tier
                    FROM company_tiers ct
                    WHERE job_listings.company_name LIKE '%' || ct.company_pattern || '%'
                    LIMIT 1
                )
                WHERE company_tier IS NULL
                  AND EXISTS (
                    SELECT 1 FROM company_tiers ct
                    WHERE job_listings.company_name LIKE '%' || ct.company_pattern || '%'
                  )
            """)
        )
        updated = result.rowcount
    logger.info("tiers_assigned", jobs_updated=updated)
    return updated


async def get_top_matches(
    min_score: float = 0.0,
    tier: int | None = None,
    limit: int = 50,
) -> list[dict]:
    """
    Get jobs that are still actionable — scraped or ranked, not yet in the
    application pipeline.  Jobs with a submitted application belong on the
    CRM board, not here.

    Filters:
      - status IN ('scraped', 'ranked') — pre-pipeline jobs only
      - match_score >= min_score  (unranked jobs have NULL score and are
        included when min_score == 0)
      - optional company_tier filter
      - excludes any job that already has a submitted application
    """
    params: dict = {"min_score": min_score, "limit": limit}

    tier_clause = ""
    if tier is not None:
        tier_clause = "AND jl.company_tier = :tier"
        params["tier"] = tier

    async with get_session() as session:
        result = await session.execute(
            text(f"""
                SELECT jl.id, jl.title, jl.company_name, jl.company_tier,
                       jl.match_score, jl.match_reasoning, jl.url, jl.location,
                       jl.remote_type, jl.salary_min, jl.salary_max, jl.status
                FROM job_listings jl
                LEFT JOIN applications app
                  ON app.job_id = jl.id AND app.status = 'submitted'
                WHERE jl.status IN ('scraped', 'ranked')
                  AND (jl.match_score >= :min_score OR jl.match_score IS NULL)
                  AND app.id IS NULL
                  {tier_clause}
                ORDER BY jl.match_score DESC NULLS LAST, jl.company_tier ASC
                LIMIT :limit
            """),
            params,
        )
        return [dict(row._mapping) for row in result]


# ---------------------------------------------------------------------------
# Scrape Log Operations
# ---------------------------------------------------------------------------

async def log_scrape_run(log: ScrapeLogCreate) -> int:
    """Record metrics from a scrape run for operational observability."""
    async with get_session() as session:
        result = await session.execute(
            text("""
                INSERT INTO scrape_log (
                    source, query_term, jobs_found, jobs_new,
                    jobs_duplicate, errors, error_details, duration_seconds
                ) VALUES (
                    :source, :query_term, :jobs_found, :jobs_new,
                    :jobs_duplicate, :errors, :error_details, :duration_seconds
                )
            """),
            {
                "source": log.source.value,
                "query_term": log.query_term,
                "jobs_found": log.jobs_found,
                "jobs_new": log.jobs_new,
                "jobs_duplicate": log.jobs_duplicate,
                "errors": log.errors,
                "error_details": log.error_details,
                "duration_seconds": log.duration_seconds,
            },
        )
        return result.lastrowid or 0


# ---------------------------------------------------------------------------
# Resume Profile Operations
# ---------------------------------------------------------------------------

async def create_resume_profile(
    name: str, version: str = "1.0", raw_text: str | None = None
) -> int:
    """Create a resume profile for matching jobs against."""
    async with get_session() as session:
        result = await session.execute(
            text("""
                INSERT INTO resume_profiles (name, version, raw_text)
                VALUES (:name, :version, :raw_text)
            """),
            {"name": name, "version": version, "raw_text": raw_text},
        )
        return result.lastrowid or 0


async def link_resume_skill(
    profile_id: int,
    skill_name: str,
    proficiency: str,
    years_experience: float | None = None,
    evidence: str | None = None,
) -> None:
    """Link a skill to a resume profile. Looks up skill by name."""
    async with get_session() as session:
        # Look up skill ID by name
        skill_result = await session.execute(
            text("SELECT id FROM skills WHERE name = :name"),
            {"name": skill_name},
        )
        skill_row = skill_result.first()

        if skill_row is None:
            logger.warning("skill_not_found", skill_name=skill_name)
            return

        await session.execute(
            text("""
                INSERT OR IGNORE INTO resume_skills
                    (profile_id, skill_id, proficiency, years_experience, evidence)
                VALUES (:pid, :sid, :prof, :years, :evidence)
            """),
            {
                "pid": profile_id,
                "sid": skill_row[0],
                "prof": proficiency,
                "years": years_experience,
                "evidence": evidence,
            },
        )


# ---------------------------------------------------------------------------
# Stats / Dashboard Queries
# ---------------------------------------------------------------------------

async def get_pipeline_stats() -> dict:
    """
    Get a snapshot of the pipeline's current state.
    Powers the future CLI dashboard.
    """
    async with get_session() as session:
        # Job counts by status
        status_result = await session.execute(
            text("""
                SELECT status, COUNT(*) as count
                FROM job_listings
                GROUP BY status
            """)
        )
        status_counts = {row[0]: row[1] for row in status_result}

        # Jobs by tier
        tier_result = await session.execute(
            text("""
                SELECT company_tier, COUNT(*) as count
                FROM job_listings
                WHERE company_tier IS NOT NULL
                GROUP BY company_tier
            """)
        )
        tier_counts = {f"tier_{row[0]}": row[1] for row in tier_result}

        # Average match score
        score_result = await session.execute(
            text("""
                SELECT ROUND(AVG(match_score), 3), COUNT(*)
                FROM job_listings
                WHERE match_score IS NOT NULL
            """)
        )
        score_row = score_result.first()

        # Latest scrape
        scrape_result = await session.execute(
            text("""
                SELECT source, query_term, jobs_found, jobs_new, completed_at
                FROM scrape_log
                ORDER BY completed_at DESC
                LIMIT 1
            """)
        )
        latest_scrape = scrape_result.first()

        return {
            "jobs_by_status": status_counts,
            "jobs_by_tier": tier_counts,
            "avg_match_score": score_row[0] if score_row else None,
            "total_ranked": score_row[1] if score_row else 0,
            "latest_scrape": dict(latest_scrape._mapping) if latest_scrape else None,
        }


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
    "archived": {"ranked"},  # Can restore to ranked for re-evaluation
}


async def update_job_status(job_id: int, new_status: str, notes: str | None = None) -> dict:
    """
    Transition a job to a new status with state-machine validation.

    Returns the updated job dict or raises ValueError for invalid transitions.
    """
    async with get_session() as session:
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


# ---------------------------------------------------------------------------
# Phase 4: Auto-Apply
# ---------------------------------------------------------------------------

async def create_application(app: ApplicationCreate) -> int:
    """
    Create a new application draft with pre-filled fields.

    Returns the application ID.

    Interview point: "Applications are idempotent per (job_id, profile_id).
    Re-running pre-fill on the same job updates the existing draft rather
    than creating duplicates — same ON CONFLICT pattern as the scraper."
    """
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


_APP_VALID_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"ready", "withdrawn"},
    "ready": {"approved", "draft", "withdrawn"},
    "approved": {"submitted", "draft", "withdrawn"},
    "submitted": {"withdrawn"},
    "withdrawn": {"draft"},
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


# ---------------------------------------------------------------------------
# Document Templates & Generated Documents
# ---------------------------------------------------------------------------

async def save_document_template(doc_type: str, filename: str, file_blob: bytes, content_type: str) -> int:
    """Upsert a document template (one per doc_type)."""
    async with get_session() as session:
        result = await session.execute(
            text("""
                INSERT INTO document_templates (doc_type, filename, file_blob, content_type)
                VALUES (:doc_type, :filename, :file_blob, :content_type)
                ON CONFLICT(doc_type) DO UPDATE SET
                    filename = :filename,
                    file_blob = :file_blob,
                    content_type = :content_type,
                    uploaded_at = datetime('now')
                RETURNING id
            """),
            {"doc_type": doc_type, "filename": filename, "file_blob": file_blob, "content_type": content_type},
        )
        return result.scalar_one()


async def get_document_template(doc_type: str) -> dict | None:
    """Get a document template by type."""
    async with get_session() as session:
        result = await session.execute(
            text("SELECT id, doc_type, filename, file_blob, content_type, uploaded_at FROM document_templates WHERE doc_type = :doc_type"),
            {"doc_type": doc_type},
        )
        row = result.first()
        return dict(row._mapping) if row else None


async def get_all_document_templates() -> list[dict]:
    """Get all uploaded document templates (without blobs for listing)."""
    async with get_session() as session:
        result = await session.execute(
            text("SELECT id, doc_type, filename, content_type, uploaded_at FROM document_templates ORDER BY doc_type")
        )
        return [dict(row._mapping) for row in result]


async def save_generated_document(application_id: int, doc_type: str, filename: str, file_blob: bytes, content_type: str) -> int:
    """Upsert a generated document for an application."""
    async with get_session() as session:
        result = await session.execute(
            text("""
                INSERT INTO generated_documents (application_id, doc_type, filename, file_blob, content_type)
                VALUES (:app_id, :doc_type, :filename, :file_blob, :content_type)
                ON CONFLICT(application_id, doc_type) DO UPDATE SET
                    filename = :filename,
                    file_blob = :file_blob,
                    content_type = :content_type,
                    generated_at = datetime('now')
                RETURNING id
            """),
            {"app_id": application_id, "doc_type": doc_type, "filename": filename, "file_blob": file_blob, "content_type": content_type},
        )
        return result.scalar_one()


async def get_generated_documents(application_id: int) -> list[dict]:
    """Get generated documents for an application (without blobs for listing)."""
    async with get_session() as session:
        result = await session.execute(
            text("SELECT id, application_id, doc_type, filename, content_type, generated_at FROM generated_documents WHERE application_id = :app_id ORDER BY doc_type"),
            {"app_id": application_id},
        )
        return [dict(row._mapping) for row in result]


async def get_generated_document(doc_id: int) -> dict | None:
    """Get a single generated document with its blob."""
    async with get_session() as session:
        result = await session.execute(
            text("SELECT id, application_id, doc_type, filename, file_blob, content_type, generated_at FROM generated_documents WHERE id = :doc_id"),
            {"doc_id": doc_id},
        )
        row = result.first()
        return dict(row._mapping) if row else None
