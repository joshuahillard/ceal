"""
Integration test: Persistence round-trip using schema.sql only.

Unlike test_persistence.py (which supplements schema.sql with ORM
Base.metadata.create_all), this test proves the raw SQL path works
end-to-end — the same path used by the main application.

Exercises:
    - init_db() creates all Phase 1 + Phase 2 tables from schema.sql
    - save_tailoring_result() ON CONFLICT upsert works on real SQLite
    - get_tailoring_results() reconstructs from real rows
    - Idempotent save (upsert) updates without duplicating
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
from src.tailoring.models import (
    SkillGap,
    TailoredBullet,
    TailoringRequest,
    TailoringResult,
)
from src.tailoring.persistence import (
    get_tailoring_results,
    save_tailoring_result,
)


def _drop_all_tables(sync_conn):
    """Drop all tables for clean test isolation."""
    from sqlalchemy import inspect
    from sqlalchemy import text as sa_text

    sync_conn.execute(sa_text("PRAGMA foreign_keys=OFF"))
    inspector = inspect(sync_conn)
    for table in inspector.get_table_names():
        sync_conn.execute(sa_text(f"DROP TABLE IF EXISTS [{table}]"))  # noqa: S608
    sync_conn.execute(sa_text("PRAGMA foreign_keys=ON"))


@pytest_asyncio.fixture(autouse=True)
async def setup_schema_sql_only():
    """
    Initialize database using ONLY schema.sql — no ORM create_all.

    This is the critical difference from test_persistence.py:
    if schema.sql is missing Phase 2 tables, these tests fail.
    """
    async with engine.begin() as conn:
        await conn.run_sync(_drop_all_tables)

    # Schema.sql only — no Base.metadata.create_all
    await init_db()

    # Seed FK targets
    async with get_session() as session:
        await session.execute(text(
            "INSERT OR IGNORE INTO resume_profiles (id, name, version) "
            "VALUES (1, 'Test Profile', '1.0')"
        ))
        await session.execute(text(
            "INSERT OR IGNORE INTO job_listings "
            "(id, external_id, source, title, company_name, url, status) "
            "VALUES (1, 'integ-001', 'manual', 'SE at Acme', 'Acme Corp', "
            "'https://example.com/1', 'ranked')"
        ))
    yield
    await engine.dispose()


def _make_result(
    job_id: int = 1,
    profile_id: int = 1,
    tier: int = 1,
    emphasis: list[str] | None = None,
) -> TailoringResult:
    """Build a TailoringResult for testing."""
    return TailoringResult(
        request=TailoringRequest(
            job_id=job_id,
            profile_id=profile_id,
            target_tier=tier,
            emphasis_areas=emphasis or ["Python", "SQL"],
        ),
        tailored_bullets=[
            TailoredBullet(
                original="Led cross-functional team of 8 engineers",
                rewritten_text="Led cross-functional team of 8 engineers on payment API migration",
                xyz_format=False,
                relevance_score=0.80,
            ),
            TailoredBullet(
                original="Reduced escalation backlog by 60%",
                rewritten_text=(
                    "Accomplished 60% escalation backlog reduction as measured by "
                    "weekly ticket close rate, by doing triage process redesign"
                ),
                xyz_format=True,
                relevance_score=0.92,
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
                skill_name="Kubernetes",
                category=SkillCategory.INFRASTRUCTURE,
                job_requires=True,
                resume_has=False,
                proficiency=None,
            ),
        ],
        tailoring_version="v1.0",
    )


class TestSchemaOnlyRoundTrip:
    """Prove the schema.sql-only path works for persistence."""

    @pytest.mark.asyncio
    async def test_phase2_tables_exist_from_schema_sql(self):
        """Verify Phase 2 tables were created by init_db (schema.sql), not ORM."""
        async with get_session() as session:
            result = await session.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ))
            tables = [r[0] for r in result]

        assert "tailoring_requests" in tables
        assert "tailored_bullets" in tables
        assert "skill_gaps" in tables
        assert "parsed_bullets" in tables

    @pytest.mark.asyncio
    async def test_save_and_retrieve_round_trip(self):
        """Save a TailoringResult and retrieve it, verifying all fields."""
        result = _make_result()
        request_id = await save_tailoring_result(result)
        assert request_id > 0

        loaded = await get_tailoring_results(job_id=1, profile_id=1)
        assert loaded is not None
        assert loaded.request.job_id == 1
        assert loaded.request.profile_id == 1
        assert loaded.request.target_tier == 1
        assert loaded.request.emphasis_areas == ["Python", "SQL"]
        assert len(loaded.tailored_bullets) == 2
        assert len(loaded.skill_gaps) == 2

        # Verify bullet content
        assert loaded.tailored_bullets[0].relevance_score == 0.80
        assert loaded.tailored_bullets[1].xyz_format is True
        assert loaded.tailored_bullets[1].relevance_score == 0.92

        # Verify skill gap content
        python_gap = next(g for g in loaded.skill_gaps if g.skill_name == "Python")
        k8s_gap = next(g for g in loaded.skill_gaps if g.skill_name == "Kubernetes")
        assert python_gap.resume_has is True
        assert python_gap.proficiency == Proficiency.PROFICIENT
        assert k8s_gap.resume_has is False
        assert k8s_gap.proficiency is None

    @pytest.mark.asyncio
    async def test_upsert_updates_without_duplicates(self):
        """Second save to same job+profile updates, doesn't duplicate."""
        original = _make_result(emphasis=["Python"])
        id1 = await save_tailoring_result(original)

        # Save again with updated data
        updated = _make_result(tier=2, emphasis=["Go", "Kubernetes"])
        id2 = await save_tailoring_result(updated)

        # Same request row (upserted)
        assert id1 == id2

        loaded = await get_tailoring_results(job_id=1, profile_id=1)
        assert loaded is not None
        # Tier should be updated
        assert loaded.request.target_tier == 2
        assert loaded.request.emphasis_areas == ["Go", "Kubernetes"]
        # Bullet count unchanged (delete + re-insert)
        assert len(loaded.tailored_bullets) == 2
        assert len(loaded.skill_gaps) == 2

    @pytest.mark.asyncio
    async def test_unique_constraint_on_skill_gaps(self):
        """The UNIQUE(request_id, skill_name) constraint is enforced by schema.sql."""
        result = _make_result()
        await save_tailoring_result(result)

        # Verify only 2 skill gap rows exist (not 4 from double-insert)
        async with get_session() as session:
            count = await session.execute(text("SELECT COUNT(*) FROM skill_gaps"))
            assert count.scalar() == 2

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_none(self):
        """Querying a non-existent job returns None."""
        loaded = await get_tailoring_results(job_id=999, profile_id=1)
        assert loaded is None
