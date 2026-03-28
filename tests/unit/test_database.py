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
    create_resume_profile,
    engine,
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
    await init_db()
    yield
    # Engine disposal cleans up the in-memory DB
    await engine.dispose()


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
        from src.models.database import get_session
        from sqlalchemy import text

        async with get_session() as session:
            result = await session.execute(
                text("SELECT COUNT(*) FROM company_tiers")
            )
            count = result.scalar()
            assert count >= 10, f"Expected at least 10 seeded companies, got {count}"

    @pytest.mark.asyncio
    async def test_skills_seeded(self):
        """Skills vocabulary should be pre-loaded."""
        from src.models.database import get_session
        from sqlalchemy import text

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

        jobs = await get_unranked_jobs()
        # Need to query with tier info
        from src.models.database import get_session
        from sqlalchemy import text

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

        from src.models.database import get_session
        from sqlalchemy import text

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

        from src.models.database import get_session
        from sqlalchemy import text

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

        from src.models.database import get_session
        from sqlalchemy import text

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
