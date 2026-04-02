"""
Ceal Phase 2: Tailoring Persistence Layer Tests

Tests save/retrieve round-trip, idempotency, and list operations
for the tailoring persistence module.
"""
from __future__ import annotations

import os

import pytest
import pytest_asyncio

# Override DATABASE_URL BEFORE importing database module
os.environ["DATABASE_URL"] = "sqlite+aiosqlite://"

from sqlalchemy import text

from src.models.database import engine, get_session, init_db
from src.models.entities import Proficiency, SkillCategory
from src.tailoring.db_models import Base
from src.tailoring.models import (
    SkillGap,
    TailoredBullet,
    TailoringRequest,
    TailoringResult,
)
from src.tailoring.persistence import (
    get_tailoring_results,
    list_tailored_jobs,
    save_tailoring_result,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """Initialize Phase 1 schema + Phase 2 ORM tables for each test."""
    # Phase 1 tables (from schema.sql)
    await init_db()
    # Phase 2 tables (from ORM metadata)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Seed a job_listing and resume_profile for FK references
    async with get_session() as session:
        await session.execute(text(
            "INSERT OR IGNORE INTO resume_profiles (id, name, version) "
            "VALUES (1, 'Josh Hillard', '1.0')"
        ))
        await session.execute(text(
            "INSERT OR IGNORE INTO job_listings "
            "(id, external_id, source, title, company_name, url, status) "
            "VALUES (1, 'test-001', 'manual', 'TSE at Stripe', 'Stripe', "
            "'https://example.com/1', 'ranked')"
        ))
        await session.execute(text(
            "INSERT OR IGNORE INTO job_listings "
            "(id, external_id, source, title, company_name, url, status, company_tier) "
            "VALUES (2, 'test-002', 'manual', 'SE at Datadog', 'Datadog', "
            "'https://example.com/2', 'ranked', 1)"
        ))
    yield
    await engine.dispose()


def _make_result(job_id: int = 1, profile_id: int = 1) -> TailoringResult:
    """Build a minimal TailoringResult for testing."""
    return TailoringResult(
        request=TailoringRequest(
            job_id=job_id,
            profile_id=profile_id,
            target_tier=1,
            emphasis_areas=["Python", "REST APIs"],
        ),
        tailored_bullets=[
            TailoredBullet(
                original="Managed escalation workflows across Engineering",
                rewritten_text="Managed technical escalation workflows for payment API integrations",
                xyz_format=False,
                relevance_score=0.85,
            ),
            TailoredBullet(
                original="Saved Toast estimated $12 million",
                rewritten_text=(
                    "Accomplished $12M cost savings as measured by defect "
                    "remediation impact, by doing systematic firmware debugging"
                ),
                xyz_format=True,
                relevance_score=0.95,
            ),
        ],
        skill_gaps=[
            SkillGap(
                skill_name="Python",
                category=SkillCategory.LANGUAGE,
                job_requires=True,
                resume_has=True,
                proficiency=Proficiency.PROFICIENT,
            ),
            SkillGap(
                skill_name="AWS",
                category=SkillCategory.CLOUD,
                job_requires=True,
                resume_has=False,
                proficiency=None,
            ),
        ],
        tailoring_version="v1.0",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSaveAndRetrieve:
    """Round-trip save + get tests."""

    @pytest.mark.asyncio
    async def test_save_and_retrieve_tailoring_result(self):
        """Save a result and retrieve it, verify data integrity."""
        result = _make_result()
        request_id = await save_tailoring_result(result)
        assert request_id > 0

        loaded = await get_tailoring_results(job_id=1, profile_id=1)
        assert loaded is not None
        assert loaded.request.job_id == 1
        assert loaded.request.target_tier == 1
        assert loaded.request.emphasis_areas == ["Python", "REST APIs"]
        assert len(loaded.tailored_bullets) == 2
        assert len(loaded.skill_gaps) == 2
        assert loaded.tailored_bullets[1].xyz_format is True
        assert loaded.skill_gaps[0].resume_has is True
        assert loaded.skill_gaps[1].resume_has is False

    @pytest.mark.asyncio
    async def test_save_is_idempotent(self):
        """Saving the same result twice doesn't create duplicates."""
        result = _make_result()
        id1 = await save_tailoring_result(result)
        id2 = await save_tailoring_result(result)
        assert id1 == id2

        loaded = await get_tailoring_results(job_id=1, profile_id=1)
        assert loaded is not None
        assert len(loaded.tailored_bullets) == 2
        assert len(loaded.skill_gaps) == 2

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_none(self):
        """Requesting a result for a job that hasn't been tailored returns None."""
        loaded = await get_tailoring_results(job_id=999, profile_id=1)
        assert loaded is None


class TestListTailoredJobs:
    """Tests for the list_tailored_jobs function."""

    @pytest.mark.asyncio
    async def test_list_tailored_jobs_empty(self):
        """Returns empty list when no results exist."""
        jobs = await list_tailored_jobs()
        assert jobs == []

    @pytest.mark.asyncio
    async def test_list_tailored_jobs_with_data(self):
        """Returns job info after saving tailoring results."""
        await save_tailoring_result(_make_result(job_id=1))
        await save_tailoring_result(_make_result(job_id=2))

        jobs = await list_tailored_jobs()
        assert len(jobs) == 2
        assert all("title" in j for j in jobs)
        assert all("bullet_count" in j for j in jobs)
        assert jobs[0]["bullet_count"] == 2
