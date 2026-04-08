"""
Integration test: Regime classification round-trip.

Exercises:
    - init_db() creates all tables including new regime columns from schema
    - save_regime_classification() writes regime data to job_listings
    - get_jobs_missing_regime() returns only unclassified ranked jobs
    - get_regime_stats() returns correct tier counts
    - Reclassification overwrites cleanly (idempotent)
    - Regime columns are nullable (backward compatible)

Backend-aware: runs against SQLite locally, PostgreSQL in CI.
"""
from __future__ import annotations

import os

import pytest
import pytest_asyncio

# Default to SQLite if not already set (CI sets DATABASE_URL to PostgreSQL)
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")

from sqlalchemy import text

from src.models.database import (
    engine,
    get_jobs_missing_regime,
    get_regime_stats,
    get_session,
    init_db,
    save_regime_classification,
)
from tests.integration.conftest import drop_all_tables


@pytest_asyncio.fixture(autouse=True)
async def setup_schema():
    """Initialize database using ONLY schema — no ORM create_all."""
    async with engine.begin() as conn:
        await conn.run_sync(drop_all_tables)

    await init_db()

    # Seed required FK targets and test data — portable ON CONFLICT DO NOTHING
    async with get_session() as session:
        await session.execute(text(
            "INSERT INTO resume_profiles (id, name, version) "
            "VALUES (1, 'Test Profile', '1.0') "
            "ON CONFLICT DO NOTHING"
        ))
        # Job 1: ranked (has match_score), no regime classification
        await session.execute(text(
            "INSERT INTO job_listings "
            "(id, external_id, source, title, company_name, url, status, match_score, description_clean) "
            "VALUES (1, 'regime-001', 'manual', 'TSE at Stripe', 'Stripe', "
            "'https://example.com/1', 'ranked', 0.87, 'Technical Solutions Engineer role') "
            "ON CONFLICT DO NOTHING"
        ))
        # Job 2: ranked, no regime classification
        await session.execute(text(
            "INSERT INTO job_listings "
            "(id, external_id, source, title, company_name, url, status, match_score, description_clean) "
            "VALUES (2, 'regime-002', 'manual', 'Cloud Engineer at MongoDB', 'MongoDB', "
            "'https://example.com/2', 'ranked', 0.65, 'Cloud infrastructure role') "
            "ON CONFLICT DO NOTHING"
        ))
        # Job 3: scraped but NOT ranked (no match_score) — should not appear
        await session.execute(text(
            "INSERT INTO job_listings "
            "(id, external_id, source, title, company_name, url, status) "
            "VALUES (3, 'regime-003', 'manual', 'Unranked Job', 'Acme Corp', "
            "'https://example.com/3', 'scraped') "
            "ON CONFLICT DO NOTHING"
        ))

    yield
    await engine.dispose()


class TestRegimeColumns:
    """Verify schema changes."""

    @pytest.mark.asyncio
    @pytest.mark.sqlite_only
    async def test_regime_columns_exist(self):
        """Schema creates all 5 regime columns on job_listings (SQLite PRAGMA introspection)."""
        async with get_session() as session:
            result = await session.execute(text("PRAGMA table_info(job_listings)"))
            cols = [row[1] for row in result]

        expected = [
            "recommended_tier",
            "regime_confidence",
            "regime_reasoning",
            "regime_model_version",
            "regime_classified_at",
        ]
        for col in expected:
            assert col in cols, f"Missing column: {col}"

    @pytest.mark.asyncio
    async def test_regime_columns_nullable(self):
        """Insert a job with no regime data → no constraint error."""
        async with get_session() as session:
            await session.execute(text(
                "INSERT INTO job_listings "
                "(external_id, source, title, company_name, url, status) "
                "VALUES ('nullable-test', 'manual', 'Test Job', 'Test Co', "
                "'https://example.com/null', 'scraped')"
            ))

            result = await session.execute(text(
                "SELECT recommended_tier, regime_confidence, regime_reasoning "
                "FROM job_listings WHERE external_id = 'nullable-test'"
            ))
            row = result.first()
            assert row is not None
            assert row[0] is None  # recommended_tier
            assert row[1] is None  # regime_confidence
            assert row[2] is None  # regime_reasoning

    @pytest.mark.asyncio
    @pytest.mark.sqlite_only
    async def test_recommended_tier_index_exists(self):
        """Index on recommended_tier was created (SQLite introspection)."""
        async with get_session() as session:
            result = await session.execute(text(
                "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_job_listings_recommended_tier'"
            ))
            row = result.first()
            assert row is not None, "Index idx_job_listings_recommended_tier not found"


class TestRegimeClassificationRoundTrip:
    """Prove save/read/stats work on real SQLite."""

    @pytest.mark.asyncio
    async def test_save_and_read_classification(self):
        """save_regime_classification → SELECT confirms data persisted."""
        classification = {
            "job_id": 1,
            "recommended_tier": 1,
            "confidence": 0.92,
            "reasoning": "Strong FinTech domain overlap",
            "model_version": "vertex-ai/gemini-2.0-flash/2026-04-03",
        }

        async with get_session() as session:
            await save_regime_classification(session, classification)

        # Verify persisted
        async with get_session() as session:
            result = await session.execute(text(
                "SELECT recommended_tier, regime_confidence, regime_reasoning, "
                "regime_model_version, regime_classified_at "
                "FROM job_listings WHERE id = 1"
            ))
            row = result.first()

        assert row is not None
        assert row[0] == 1  # recommended_tier
        assert abs(row[1] - 0.92) < 0.001  # regime_confidence
        assert "FinTech" in row[2]  # regime_reasoning
        assert "vertex-ai/" in row[3]  # regime_model_version
        assert row[4] is not None  # regime_classified_at

    @pytest.mark.asyncio
    async def test_get_jobs_missing_regime(self):
        """Only unclassified ranked jobs returned."""
        async with get_session() as session:
            jobs = await get_jobs_missing_regime(session)

        # Jobs 1 and 2 are ranked but unclassified
        # Job 3 is unranked (no match_score) — should NOT appear
        job_ids = [j["id"] for j in jobs]
        assert 1 in job_ids
        assert 2 in job_ids
        assert 3 not in job_ids

    @pytest.mark.asyncio
    async def test_get_jobs_missing_regime_excludes_classified(self):
        """After classification, job no longer appears in missing list."""
        # Classify job 1
        async with get_session() as session:
            await save_regime_classification(session, {
                "job_id": 1,
                "recommended_tier": 1,
                "confidence": 0.92,
                "reasoning": "Test",
                "model_version": "vertex-ai/test/2026-04-03",
            })

        # Now only job 2 should be missing
        async with get_session() as session:
            jobs = await get_jobs_missing_regime(session)

        job_ids = [j["id"] for j in jobs]
        assert 1 not in job_ids
        assert 2 in job_ids

    @pytest.mark.asyncio
    async def test_get_regime_stats(self):
        """Correct counts per tier after inserting test data."""
        # Classify both jobs
        async with get_session() as session:
            await save_regime_classification(session, {
                "job_id": 1,
                "recommended_tier": 1,
                "confidence": 0.92,
                "reasoning": "Tier 1",
                "model_version": "vertex-ai/test/2026-04-03",
            })
            await save_regime_classification(session, {
                "job_id": 2,
                "recommended_tier": 2,
                "confidence": 0.75,
                "reasoning": "Tier 2",
                "model_version": "vertex-ai/test/2026-04-03",
            })

        async with get_session() as session:
            stats = await get_regime_stats(session)

        assert stats["tier_1_count"] == 1
        assert stats["tier_2_count"] == 1
        assert stats["tier_3_count"] == 0
        assert stats["unclassified_count"] == 0  # Job 3 is unranked, not counted
        assert stats["total_classified"] == 2

    @pytest.mark.asyncio
    async def test_reclassification_overwrites(self):
        """Running classification twice on same job overwrites cleanly."""
        # First classification
        async with get_session() as session:
            await save_regime_classification(session, {
                "job_id": 1,
                "recommended_tier": 1,
                "confidence": 0.92,
                "reasoning": "First pass",
                "model_version": "vertex-ai/gemini-2.0-flash/2026-04-03",
            })

        # Reclassify with different tier
        async with get_session() as session:
            await save_regime_classification(session, {
                "job_id": 1,
                "recommended_tier": 3,
                "confidence": 0.60,
                "reasoning": "Revised to campaign tier",
                "model_version": "vertex-ai/gemini-2.0-flash/2026-04-03",
            })

        # Verify overwritten
        async with get_session() as session:
            result = await session.execute(text(
                "SELECT recommended_tier, regime_confidence, regime_reasoning "
                "FROM job_listings WHERE id = 1"
            ))
            row = result.first()

        assert row[0] == 3  # Overwritten to tier 3
        assert abs(row[1] - 0.60) < 0.001
        assert "Revised" in row[2]
