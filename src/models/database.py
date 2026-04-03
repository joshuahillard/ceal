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

from src.models.compat import get_database_url, is_sqlite
from src.models.entities import (
    JobListingCreate,
    RankedResult,
    ScrapeLogCreate,
)

load_dotenv()
logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Engine Configuration
# ---------------------------------------------------------------------------


def _create_engine():
    """Create the async engine based on DATABASE_URL backend."""
    url = get_database_url()
    kwargs: dict = {"echo": False}

    if url == "sqlite+aiosqlite://":
        # In-memory: single shared connection for test isolation
        kwargs["poolclass"] = StaticPool
        kwargs["connect_args"] = {"check_same_thread": False}
    elif is_sqlite():
        kwargs["pool_pre_ping"] = True
    else:
        # PostgreSQL — asyncpg connection pool
        kwargs["pool_pre_ping"] = True
        kwargs["pool_size"] = 5
        kwargs["max_overflow"] = 10

    return create_async_engine(url, **kwargs)


engine = _create_engine()


# ---------------------------------------------------------------------------
# SQLite PRAGMA configuration — runs on every new connection
# ---------------------------------------------------------------------------
# Why: SQLite PRAGMAs are per-connection, not per-database. If you set WAL
# once and never again, new connections revert to the default journal mode.
# This event listener guarantees every connection is configured correctly.

if is_sqlite():
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
    Auto-selects schema.sql (SQLite) or schema_postgres.sql (PostgreSQL).
    Idempotent — safe to call on every startup.
    """
    if schema_path is None:
        if is_sqlite():
            schema_path = str(Path(__file__).parent / "schema.sql")
        else:
            schema_path = str(Path(__file__).parent / "schema_postgres.sql")

    schema_sql = Path(schema_path).read_text()
    statements = _split_sql_statements(schema_sql)

    if is_sqlite():
        async with get_session() as session:
            for stmt in statements:
                if stmt:
                    await session.execute(text(stmt))
    else:
        # PostgreSQL: use engine.begin() for DDL outside session manager
        async with engine.begin() as conn:
            for stmt in statements:
                if stmt:
                    await conn.execute(text(stmt))

    logger.info("database_initialized", schema=schema_path)


def _split_sql_statements(sql: str) -> list[str]:
    """
    Split SQL into statements, correctly handling:
    - SQLite BEGIN...END trigger blocks
    - PostgreSQL $$ dollar-quoted function bodies
    """
    statements: list[str] = []
    current: list[str] = []
    in_trigger = False
    in_dollar_quote = False

    for line in sql.split("\n"):
        stripped = line.strip()

        # Skip pure comment lines
        if stripped.startswith("--"):
            continue

        # Remove inline comments (but not inside dollar-quoted blocks)
        if "--" in stripped and not in_dollar_quote:
            stripped = stripped[: stripped.index("--")].strip()

        if not stripped:
            continue

        # Track dollar-quoted blocks (PostgreSQL function bodies)
        dollar_count = stripped.count("$$")
        if dollar_count % 2 == 1:
            in_dollar_quote = not in_dollar_quote

        # Track SQLite trigger blocks
        if stripped.upper().startswith("CREATE TRIGGER"):
            in_trigger = True

        current.append(stripped)

        if in_dollar_quote:
            # Inside a dollar-quoted block — keep accumulating
            continue

        if in_trigger:
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
    min_score: float = 0.5,
    tier: int | None = None,
    limit: int = 20,
) -> list[dict]:
    """
    Get the highest-ranked jobs, optionally filtered by tier.
    This powers the "what should I apply to today?" query.
    """
    params: dict = {"min_score": min_score, "limit": limit}

    tier_clause = ""
    if tier is not None:
        tier_clause = "AND company_tier = :tier"
        params["tier"] = tier

    async with get_session() as session:
        result = await session.execute(
            text(f"""
                SELECT id, title, company_name, company_tier,
                       match_score, match_reasoning, url, location,
                       remote_type, salary_min, salary_max, status
                FROM job_listings
                WHERE match_score >= :min_score
                  AND status IN ('ranked', 'scraped')
                  {tier_clause}
                ORDER BY match_score DESC, company_tier ASC
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
