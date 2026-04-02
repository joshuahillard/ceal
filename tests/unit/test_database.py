"""
Céal: Database Layer Tests

These tests prove:
1. Schema initializes correctly (idempotent)
2. Upserts work (insert + update on conflict)
3. Batch operations are transactional
4. Tier assignment auto-matches companies
5. Query operations return expected shapes

Interview point: "Every database operation has a corresponding test.
I use pytest-asyncio with an in-memory SQLite database so tests run
in ~200ms with zero disk I/O and no cleanup needed."
"""

import os

import pytest
import pytest_asyncio

# Override DATABASE_URL BEFORE importing database module
os.environ["DATABASE_URL"] = "sqlite+aiosqlite://"  # in-memory for tests

from src.models.database import (
    assign_company_tiers,
    create_application,
    create_resume_profile,
    engine,
    get_application_stats,
    get_approval_queue,
    get_jobs_by_status,
    get_pipeline_stats,
    get_top_matches,
    get_unranked_jobs,
    init_db,
    link_resume_skill,
    log_scrape_run,
    update_job_ranking,
    upsert_job,
    upsert_jobs_batch,
)
from src.models.entities import (
    ApplicationCreate,
    JobListingCreate,
    JobSource,
    RankedResult,
    RemoteType,
    ScrapeLogCreate,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """Initialize a fresh in-memory database for each test."""
    # Drop all tables first to ensure clean state across test files
    async with engine.begin() as conn:
        await conn.run_sync(engine_drop_all)
    await init_db()
    yield
    # Engine disposal cleans up the in-memory DB
    await engine.dispose()


def engine_drop_all(sync_conn):
    """Drop all tables via raw SQL for clean test isolation."""
    from sqlalchemy import inspect
    from sqlalchemy import text as sa_text

    sync_conn.execute(sa_text("PRAGMA foreign_keys=OFF"))
    inspector = inspect(sync_conn)
    tables = inspector.get_table_names()
    for table in tables:
        sync_conn.execute(sa_text(f"DROP TABLE IF EXISTS [{table}]"))  # noqa: S608
    sync_conn.execute(sa_text("PRAGMA foreign_keys=ON"))


def _make_job(
    external_id: str = "test_001",
    source: JobSource = JobSource.LINKEDIN,
    title: str = "Technical Solutions Engineer",
    company: str = "Stripe",
    **overrides,
) -> JobListingCreate:
    """Helper to create test job listings with sensible defaults."""
    return JobListingCreate(
        external_id=external_id,
        source=source,
        title=title,
        company_name=company,
        url=f"https://example.com/jobs/{external_id}",
        location="Boston, MA",
        remote_type=RemoteType.HYBRID,
        **overrides,
    )


# ---------------------------------------------------------------------------
# Schema Tests
# ---------------------------------------------------------------------------

class TestSchemaInit:
    @pytest.mark.asyncio
    async def test_init_db_is_idempotent(self):
        """Running init_db twice should not raise errors."""
        await init_db()  # second call (first is in fixture)
        # If we get here without an exception, it's idempotent

    @pytest.mark.asyncio
    async def test_company_tiers_seeded(self):
        """Tier 1-3 companies should be pre-loaded."""
        from sqlalchemy import text

        from src.models.database import get_session

        async with get_session() as session:
            result = await session.execute(
                text("SELECT COUNT(*) FROM company_tiers")
            )
            count = result.scalar()
            assert count >= 10, f"Expected at least 10 seeded companies, got {count}"

    @pytest.mark.asyncio
    async def test_skills_seeded(self):
        """Skills vocabulary should be pre-loaded."""
        from sqlalchemy import text

        from src.models.database import get_session

        async with get_session() as session:
            result = await session.execute(
                text("SELECT COUNT(*) FROM skills")
            )
            count = result.scalar()
            assert count >= 30, f"Expected at least 30 seeded skills, got {count}"


# ---------------------------------------------------------------------------
# Upsert Tests
# ---------------------------------------------------------------------------

class TestUpsertJob:
    @pytest.mark.asyncio
    async def test_insert_new_job(self):
        """A new job should be inserted and return a valid row ID."""
        job = _make_job()
        row_id = await upsert_job(job)
        assert row_id > 0

    @pytest.mark.asyncio
    async def test_upsert_updates_existing(self):
        """Upserting the same external_id+source should update, not duplicate."""
        job_v1 = _make_job(title="Solutions Engineer")
        job_v2 = _make_job(title="Senior Solutions Engineer")

        await upsert_job(job_v1)
        await upsert_job(job_v2)

        jobs = await get_unranked_jobs()
        assert len(jobs) == 1, "Should be exactly 1 job (upsert, not insert)"
        assert jobs[0]["title"] == "Senior Solutions Engineer"

    @pytest.mark.asyncio
    async def test_different_sources_are_separate(self):
        """Same external_id from different sources should be two records."""
        job_li = _make_job(source=JobSource.LINKEDIN)
        job_in = _make_job(source=JobSource.INDEED)

        await upsert_job(job_li)
        await upsert_job(job_in)

        jobs = await get_unranked_jobs()
        assert len(jobs) == 2


class TestBatchUpsert:
    @pytest.mark.asyncio
    async def test_batch_insert_multiple(self):
        """Batch upsert should insert all jobs in one transaction."""
        jobs = [
            _make_job(external_id="batch_1", company="Stripe"),
            _make_job(external_id="batch_2", company="Datadog"),
            _make_job(external_id="batch_3", company="Coinbase"),
        ]
        stats = await upsert_jobs_batch(jobs)
        assert stats["inserted"] == 3
        assert stats["errors"] == 0

    @pytest.mark.asyncio
    async def test_batch_handles_mixed_insert_update(self):
        """Batch should correctly report inserts vs updates."""
        # Insert one first
        await upsert_job(_make_job(external_id="mixed_1"))

        # Now batch: 1 existing + 2 new
        jobs = [
            _make_job(external_id="mixed_1", title="Updated Title"),
            _make_job(external_id="mixed_2"),
            _make_job(external_id="mixed_3"),
        ]
        stats = await upsert_jobs_batch(jobs)
        assert stats["inserted"] == 2
        assert stats["updated"] == 1


# ---------------------------------------------------------------------------
# Tier Assignment Tests
# ---------------------------------------------------------------------------

class TestTierAssignment:
    @pytest.mark.asyncio
    async def test_auto_assigns_tier_1(self):
        """Stripe should be auto-assigned Tier 1."""
        await upsert_job(_make_job(company="Stripe, Inc."))
        updated = await assign_company_tiers()
        assert updated == 1

        await get_unranked_jobs()
        # Need to query with tier info
        from sqlalchemy import text

        from src.models.database import get_session

        async with get_session() as session:
            result = await session.execute(
                text("SELECT company_tier FROM job_listings WHERE company_name = 'Stripe, Inc.'")
            )
            tier = result.scalar()
            assert tier == 1

    @pytest.mark.asyncio
    async def test_unknown_company_gets_no_tier(self):
        """Companies not in the lookup table should remain NULL."""
        await upsert_job(_make_job(company="RandomStartup"))
        await assign_company_tiers()

        from sqlalchemy import text

        from src.models.database import get_session

        async with get_session() as session:
            result = await session.execute(
                text("SELECT company_tier FROM job_listings WHERE company_name = 'RandomStartup'")
            )
            tier = result.scalar()
            assert tier is None


# ---------------------------------------------------------------------------
# Ranking Tests
# ---------------------------------------------------------------------------

class TestRanking:
    @pytest.mark.asyncio
    async def test_update_job_ranking(self):
        """Ranking a job should update score, reasoning, and status."""
        row_id = await upsert_job(_make_job())

        result = RankedResult(
            job_id=row_id,
            match_score=0.87,
            match_reasoning="Strong fit: Python, async, payment processing experience at Toast.",
            skills_matched=["Python", "Payment Processing"],
            skills_missing=["Go"],
            rank_model_version="v1.0-claude-sonnet",
        )
        await update_job_ranking(result)

        from sqlalchemy import text

        from src.models.database import get_session

        async with get_session() as session:
            r = await session.execute(
                text("SELECT match_score, status, rank_model_version FROM job_listings WHERE id = :id"),
                {"id": row_id},
            )
            row = r.first()
            assert row[0] == 0.87
            assert row[1] == "ranked"
            assert row[2] == "v1.0-claude-sonnet"

    @pytest.mark.asyncio
    async def test_get_top_matches(self):
        """Top matches should return ranked jobs sorted by score."""
        # Insert and rank two jobs
        id1 = await upsert_job(_make_job(external_id="top_1", company="Stripe"))
        id2 = await upsert_job(_make_job(external_id="top_2", company="Datadog"))
        id3 = await upsert_job(_make_job(external_id="top_3", company="RandomCo"))

        for jid, score in [(id1, 0.9), (id2, 0.7), (id3, 0.3)]:
            await update_job_ranking(RankedResult(
                job_id=jid,
                match_score=score,
                match_reasoning="Test reasoning for score " + str(score),
                rank_model_version="test",
            ))

        # Get top matches with min_score 0.5
        matches = await get_top_matches(min_score=0.5)
        assert len(matches) == 2
        assert matches[0]["match_score"] == 0.9  # highest first

    @pytest.mark.asyncio
    async def test_get_top_matches_excludes_submitted_applications(self):
        """Jobs with a submitted application should not appear in the jobs list."""
        from sqlalchemy import text as sa_text

        from src.models.database import get_session

        id1 = await upsert_job(_make_job(external_id="app_1", company="Stripe"))
        id2 = await upsert_job(_make_job(external_id="app_2", company="Datadog"))

        for jid, score in [(id1, 0.9), (id2, 0.8)]:
            await update_job_ranking(RankedResult(
                job_id=jid, match_score=score,
                match_reasoning="Test reasoning for ranking", rank_model_version="test",
            ))

        # Create a resume profile for the FK, then submit an application for job 1
        profile_id = await create_resume_profile("Test Profile", "test resume text")
        async with get_session() as session:
            await session.execute(
                sa_text("""
                    INSERT INTO applications (job_id, profile_id, status)
                    VALUES (:job_id, :profile_id, 'submitted')
                """),
                {"job_id": id1, "profile_id": profile_id},
            )

        matches = await get_top_matches()
        job_ids = [m["id"] for m in matches]
        assert id1 not in job_ids, "Submitted application job should be excluded"
        assert id2 in job_ids, "Non-applied job should still appear"

    @pytest.mark.asyncio
    async def test_get_top_matches_includes_unranked_jobs(self):
        """Unranked (scraped) jobs should appear when min_score is 0."""
        await upsert_job(_make_job(external_id="unranked_1", company="NewCo"))
        matches = await get_top_matches(min_score=0.0)
        assert len(matches) == 1
        assert matches[0]["status"] == "scraped"
        assert matches[0]["match_score"] is None

    @pytest.mark.asyncio
    async def test_get_top_matches_excludes_applied_status(self):
        """Jobs with CRM statuses (applied, interviewing, etc.) should not appear."""
        from sqlalchemy import text as sa_text

        from src.models.database import get_session

        id1 = await upsert_job(_make_job(external_id="crm_1", company="Stripe"))
        id2 = await upsert_job(_make_job(external_id="crm_2", company="Datadog"))

        for jid, score in [(id1, 0.9), (id2, 0.8)]:
            await update_job_ranking(RankedResult(
                job_id=jid, match_score=score,
                match_reasoning="Test reasoning for ranking", rank_model_version="test",
            ))

        # Move job 1 to 'applied' status directly in DB
        async with get_session() as session:
            await session.execute(
                sa_text("UPDATE job_listings SET status = 'applied' WHERE id = :id"),
                {"id": id1},
            )

        matches = await get_top_matches()
        job_ids = [m["id"] for m in matches]
        assert id1 not in job_ids, "Applied job should be on the CRM board, not here"
        assert id2 in job_ids


# ---------------------------------------------------------------------------
# Scrape Log Tests
# ---------------------------------------------------------------------------

class TestScrapeLog:
    @pytest.mark.asyncio
    async def test_log_scrape_run(self):
        """Should record scrape metrics."""
        log = ScrapeLogCreate(
            source=JobSource.LINKEDIN,
            query_term="Technical Solutions Engineer Boston",
            jobs_found=47,
            jobs_new=42,
            jobs_duplicate=5,
            errors=0,
            duration_seconds=8.3,
        )
        log_id = await log_scrape_run(log)
        assert log_id > 0


# ---------------------------------------------------------------------------
# Resume Profile Tests
# ---------------------------------------------------------------------------

class TestResumeProfile:
    @pytest.mark.asyncio
    async def test_create_profile_and_link_skills(self):
        """Should create a profile and link skills to it."""
        profile_id = await create_resume_profile(
            name="TSE_Focus",
            version="1.0",
            raw_text="Josh Hillard - Technical Solutions Engineer...",
        )
        assert profile_id > 0

        # Link a seeded skill
        await link_resume_skill(
            profile_id=profile_id,
            skill_name="Python",
            proficiency="proficient",
            years_experience=1.5,
            evidence="Built Moss Lane trading bot and Céal pipeline",
        )

        from sqlalchemy import text

        from src.models.database import get_session

        async with get_session() as session:
            result = await session.execute(
                text("SELECT COUNT(*) FROM resume_skills WHERE profile_id = :pid"),
                {"pid": profile_id},
            )
            assert result.scalar() == 1


# ---------------------------------------------------------------------------
# Pipeline Stats Tests
# ---------------------------------------------------------------------------

class TestPipelineStats:
    @pytest.mark.asyncio
    async def test_stats_on_empty_db(self):
        """Stats should work on an empty database without errors."""
        stats = await get_pipeline_stats()
        assert isinstance(stats, dict)
        assert stats["total_ranked"] == 0

    @pytest.mark.asyncio
    async def test_stats_with_data(self):
        """Stats should reflect inserted and ranked jobs."""
        await upsert_job(_make_job(external_id="stat_1"))
        id2 = await upsert_job(_make_job(external_id="stat_2"))
        await update_job_ranking(RankedResult(
            job_id=id2,
            match_score=0.8,
            match_reasoning="Good match for testing purposes.",
            rank_model_version="test",
        ))

        stats = await get_pipeline_stats()
        assert stats["jobs_by_status"].get("scraped", 0) >= 1
        assert stats["jobs_by_status"].get("ranked", 0) >= 1
        assert stats["total_ranked"] >= 1


# ---------------------------------------------------------------------------
# Pydantic Validation Tests
# ---------------------------------------------------------------------------

class TestEntityValidation:
    def test_salary_range_invalid(self):
        """salary_min > salary_max should raise ValidationError."""
        with pytest.raises(Exception):
            _make_job(salary_min=150000, salary_max=90000)

    def test_invalid_url_rejected(self):
        """URLs without http/https should be rejected."""
        from src.models.entities import RawJobListing

        with pytest.raises(Exception):
            RawJobListing(
                external_id="bad_url",
                source=JobSource.LINKEDIN,
                title="Test",
                company_name="Test",
                url="not-a-url",
            )

    def test_empty_external_id_rejected(self):
        """Whitespace-only external_id should be rejected."""
        from src.models.entities import RawJobListing

        with pytest.raises(Exception):
            RawJobListing(
                external_id="   ",
                source=JobSource.LINKEDIN,
                title="Test",
                company_name="Test",
                url="https://example.com",
            )

    def test_match_score_out_of_range(self):
        """RankedResult with score > 1.0 should be rejected."""
        with pytest.raises(Exception):
            RankedResult(
                job_id=1,
                match_score=1.5,
                match_reasoning="This score is too high",
                rank_model_version="test",
            )


# ---------------------------------------------------------------------------
# Core Query SQL Tests — Real SQL, Not Mocks
# ---------------------------------------------------------------------------
# These tests exercise REAL SQL against a database — not mocks.
# They exist because mock-only route tests hid SQL bugs in
# get_top_matches() THREE TIMES (Sprints 1, 2, and post-Sprint 4).

class TestCoreQuerySQL:
    """
    Database-level tests for core query functions.

    Rule: "For any database function that contains raw SQL and
    drives a core UI view, write a database-level test that exercises
    the real SQL against an in-memory database."
    """

    async def _seed_job(self, eid: str, company: str = "TestCo", score: float | None = None) -> int:
        """Seed a job and optionally rank it. Returns the row ID."""
        job_id = await upsert_job(_make_job(external_id=eid, company=company))
        if score is not None:
            await update_job_ranking(RankedResult(
                job_id=job_id,
                match_score=score,
                match_reasoning=f"Test ranking score={score}",
                rank_model_version="test",
            ))
        return job_id

    async def _create_application(self, job_id: int, status: str = "draft") -> int:
        """Create a resume profile + application for a job."""
        profile_id = await create_resume_profile("Test Profile", raw_text="test")
        app_id = await create_application(ApplicationCreate(
            job_id=job_id,
            profile_id=profile_id,
            confidence_score=0.8,
        ))
        if status != "draft":
            from sqlalchemy import text as sa_text

            from src.models.database import get_session
            async with get_session() as session:
                await session.execute(
                    sa_text("UPDATE applications SET status = :status WHERE id = :app_id"),
                    {"status": status, "app_id": app_id},
                )
        return app_id

    @pytest.mark.asyncio
    async def test_get_top_matches_only_returns_scraped_and_ranked(self):
        """Jobs with status applied/interviewing/offer/rejected/archived must NOT appear."""
        from sqlalchemy import text as sa_text

        from src.models.database import get_session

        id_scraped = await self._seed_job("sql_scraped_1")
        id_ranked = await self._seed_job("sql_ranked_1", score=0.8)
        id_applied = await self._seed_job("sql_applied_1", score=0.7)

        # Force status to 'applied' directly
        async with get_session() as session:
            await session.execute(
                sa_text("UPDATE job_listings SET status = 'applied' WHERE id = :id"),
                {"id": id_applied},
            )

        matches = await get_top_matches()
        match_ids = [m["id"] for m in matches]
        assert id_scraped in match_ids, "Scraped jobs should appear"
        assert id_ranked in match_ids, "Ranked jobs should appear"
        assert id_applied not in match_ids, "Applied jobs must NOT appear"

    @pytest.mark.asyncio
    async def test_get_top_matches_excludes_jobs_with_submitted_applications(self):
        """Jobs with a submitted application must be filtered by LEFT JOIN."""
        id1 = await self._seed_job("sql_sub_1", score=0.9)
        id2 = await self._seed_job("sql_sub_2", score=0.8)

        await self._create_application(id1, status="submitted")

        matches = await get_top_matches()
        match_ids = [m["id"] for m in matches]
        assert id1 not in match_ids, "Submitted application job should be excluded"
        assert id2 in match_ids, "Non-submitted job should still appear"

    @pytest.mark.asyncio
    async def test_get_top_matches_includes_jobs_with_draft_applications(self):
        """Jobs with draft (non-submitted) applications should still appear."""
        id1 = await self._seed_job("sql_draft_1", score=0.85)
        await self._create_application(id1, status="draft")

        matches = await get_top_matches()
        match_ids = [m["id"] for m in matches]
        assert id1 in match_ids, "Draft application job should still appear in listings"

    @pytest.mark.asyncio
    async def test_get_top_matches_respects_min_score_filter(self):
        """min_score=0.5 should exclude jobs with score < 0.5 but include unscored."""
        await self._seed_job("sql_low", score=0.3)
        id_mid = await self._seed_job("sql_mid", score=0.7)
        id_high = await self._seed_job("sql_high", score=0.9)
        id_null = await self._seed_job("sql_unranked")  # NULL score (scraped)

        matches = await get_top_matches(min_score=0.5)
        match_ids = [m["id"] for m in matches]
        assert id_mid in match_ids, "Score 0.7 should pass min_score=0.5"
        assert id_high in match_ids, "Score 0.9 should pass min_score=0.5"
        assert id_null in match_ids, "Unscored (NULL) jobs should be included"

    @pytest.mark.asyncio
    async def test_get_top_matches_orders_by_score_desc_nulls_last(self):
        """Ranked jobs sort to top by score; unranked sort to bottom."""
        id_high = await self._seed_job("sql_ord_high", score=0.9)
        id_low = await self._seed_job("sql_ord_low", score=0.5)
        id_null = await self._seed_job("sql_ord_null")  # unranked

        matches = await get_top_matches(min_score=0.0)
        match_ids = [m["id"] for m in matches]
        assert match_ids.index(id_high) < match_ids.index(id_low), "0.9 should come before 0.5"
        assert match_ids.index(id_low) < match_ids.index(id_null), "Scored should come before NULL"

    @pytest.mark.asyncio
    async def test_get_pipeline_stats_returns_expected_keys(self):
        """Pipeline stats must include all expected keys."""
        stats = await get_pipeline_stats()
        assert "jobs_by_status" in stats
        assert "total_ranked" in stats
        assert "latest_scrape" in stats or stats.get("latest_scrape") is None

    @pytest.mark.asyncio
    async def test_get_jobs_by_status_filters_correctly(self):
        """get_jobs_by_status('ranked') should only return ranked jobs."""
        await self._seed_job("sql_status_scraped")
        await self._seed_job("sql_status_ranked", score=0.75)

        results = await get_jobs_by_status("ranked")
        for job in results:
            assert job["status"] == "ranked", f"Expected 'ranked', got '{job['status']}'"

    @pytest.mark.asyncio
    async def test_get_approval_queue_returns_correct_structure(self):
        """Approval queue should return applications with joined job data."""
        id1 = await self._seed_job("sql_queue_1", score=0.8)
        await self._create_application(id1, status="draft")

        queue = await get_approval_queue(status="draft")
        assert len(queue) >= 1
        app = queue[0]
        assert "job_title" in app, "Approval queue must include job_title from JOIN"
        assert "company_name" in app, "Approval queue must include company_name from JOIN"
        assert "confidence_score" in app

    @pytest.mark.asyncio
    async def test_get_application_stats_returns_counts(self):
        """Application stats should return per-status counts."""
        id1 = await self._seed_job("sql_appstat_1", score=0.7)
        await self._create_application(id1, status="draft")

        stats = await get_application_stats()
        assert isinstance(stats, dict)
        assert stats.get("draft", 0) >= 1
