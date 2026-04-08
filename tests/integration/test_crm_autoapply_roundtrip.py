"""
Integration test: CRM + auto-apply round-trip.

Exercises the real schema and raw SQL query path for:
    - CRM state transitions
    - application draft persistence
    - application field persistence
    - approval sync back to CRM
    - stale reminder queries

Backend-aware: runs against SQLite locally, PostgreSQL in CI.
"""
from __future__ import annotations

import os

import pytest
import pytest_asyncio
from sqlalchemy import text

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")

from src.models.database import (  # noqa: E402
    create_application,
    engine,
    get_application,
    get_session,
    get_stale_applications,
    init_db,
    update_application_status,
    update_job_ranking,
    update_job_status,
    upsert_job,
)
from src.models.entities import (  # noqa: E402
    ApplicationCreate,
    ApplicationFieldCreate,
    JobListingCreate,
    JobSource,
    RankedResult,
    RemoteType,
)
from tests.integration.conftest import drop_all_tables  # noqa: E402


@pytest_asyncio.fixture(autouse=True)
async def setup_schema_sql_only():
    """Initialize a fresh database using the appropriate schema."""
    async with engine.begin() as conn:
        await conn.run_sync(drop_all_tables)

    await init_db()

    async with get_session() as session:
        await session.execute(
            text(
                "INSERT INTO resume_profiles (id, name, version) VALUES (1, 'Josh Hillard', '1.0') "
                "ON CONFLICT DO NOTHING"
            )
        )

    yield
    await engine.dispose()


async def _create_ranked_job(external_id: str, company: str = "Stripe") -> int:
    """Insert a job and rank it so CRM transitions can operate on it."""
    job_id = await upsert_job(
        JobListingCreate(
            external_id=external_id,
            source=JobSource.MANUAL,
            title="Technical Solutions Engineer",
            company_name=company,
            url=f"https://example.com/jobs/{external_id}",
            location="Boston, MA",
            remote_type=RemoteType.HYBRID,
            description_raw="Test description",
            description_clean="Test description",
        )
    )
    await update_job_ranking(
        RankedResult(
            job_id=job_id,
            match_score=0.87,
            match_reasoning="Strong fit for Python, SQL, and API-heavy technical customer work.",
            rank_model_version="test",
        )
    )
    return job_id


class TestCrmAutoApplyRoundTrip:
    @pytest.mark.asyncio
    @pytest.mark.sqlite_only
    async def test_tables_exist_after_init_db(self):
        """applications and application_fields should exist after schema init (SQLite introspection)."""
        async with get_session() as session:
            result = await session.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            )
            tables = [row[0] for row in result]

        assert "applications" in tables
        assert "application_fields" in tables

    @pytest.mark.asyncio
    async def test_ranked_job_transitions_to_applied_via_valid_crm_flow(self):
        """A ranked job can move to applied, while invalid jumps still fail."""
        job_id = await _create_ranked_job("crm-001")
        result = await update_job_status(job_id, "applied")
        assert result["previous_status"] == "ranked"
        assert result["new_status"] == "applied"

        other_job_id = await upsert_job(
            JobListingCreate(
                external_id="crm-002",
                source=JobSource.MANUAL,
                title="Solutions Engineer",
                company_name="Datadog",
                url="https://example.com/jobs/crm-002",
                location="New York, NY",
                remote_type=RemoteType.REMOTE,
                description_raw="Test description",
                description_clean="Test description",
            )
        )
        with pytest.raises(ValueError, match="Invalid transition"):
            await update_job_status(other_job_id, "offer")

    @pytest.mark.asyncio
    async def test_create_application_is_idempotent_and_fields_round_trip(self):
        """Application upsert should return the same ID and preserve field data."""
        job_id = await _create_ranked_job("apply-001")

        app_create = ApplicationCreate(
            job_id=job_id,
            profile_id=1,
            confidence_score=0.82,
            notes="Auto pre-filled 3/16 fields",
            fields=[
                ApplicationFieldCreate(
                    field_name="full_name",
                    field_value="Josh Hillard",
                    confidence=0.95,
                    field_type="text",
                    source="resume",
                ),
                ApplicationFieldCreate(
                    field_name="resume_text",
                    field_value="Resume body",
                    confidence=1.0,
                    field_type="textarea",
                    source="resume",
                ),
            ],
        )

        app_id_1 = await create_application(app_create)
        app_id_2 = await create_application(app_create)
        application = await get_application(app_id_1)

        assert app_id_1 == app_id_2
        assert application is not None
        assert application["job_id"] == job_id
        assert len(application["fields"]) == 2
        assert {field["field_name"] for field in application["fields"]} == {"full_name", "resume_text"}

    @pytest.mark.asyncio
    async def test_create_application_recovers_default_profile_if_missing(self):
        """create_application should recreate the default profile when startup state is incomplete."""
        job_id = await _create_ranked_job("apply-default-profile")

        async with get_session() as session:
            await session.execute(text("DELETE FROM resume_profiles WHERE id = 1"))

        app_id = await create_application(ApplicationCreate(job_id=job_id, profile_id=1))
        application = await get_application(app_id)

        async with get_session() as session:
            result = await session.execute(text("SELECT id FROM resume_profiles WHERE id = 1"))
            profile_row = result.first()

        assert app_id > 0
        assert application is not None
        assert profile_row is not None

    @pytest.mark.asyncio
    async def test_approving_application_syncs_parent_job_to_applied(self):
        """Approving an application should move the linked job into applied."""
        job_id = await _create_ranked_job("apply-002")
        app_id = await create_application(ApplicationCreate(job_id=job_id, profile_id=1))

        await update_application_status(app_id, "ready")
        await update_application_status(app_id, "approved")

        async with get_session() as session:
            result = await session.execute(text("SELECT status FROM job_listings WHERE id = :job_id"), {"job_id": job_id})
            job_status = result.scalar_one()

        assert job_status == "applied"

    @pytest.mark.asyncio
    async def test_submitted_application_persists_submitted_at(self):
        """Submitting an approved application should populate submitted_at."""
        job_id = await _create_ranked_job("apply-003")
        app_id = await create_application(ApplicationCreate(job_id=job_id, profile_id=1))

        await update_application_status(app_id, "ready")
        await update_application_status(app_id, "approved")
        await update_application_status(app_id, "submitted")

        async with get_session() as session:
            result = await session.execute(
                text("SELECT status, submitted_at FROM applications WHERE id = :app_id"),
                {"app_id": app_id},
            )
            row = result.first()

        assert row is not None
        assert row[0] == "submitted"
        assert row[1] is not None

    @pytest.mark.asyncio
    async def test_get_stale_applications_only_returns_active_statuses_with_days(self):
        """Stale reminders should only surface active statuses and include days_stale."""
        async with get_session() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO job_listings (
                        id, external_id, source, title, company_name, url,
                        location, remote_type, description_raw, description_clean,
                        match_score, match_reasoning, rank_model_version, status,
                        created_at, updated_at, scraped_at, ranked_at
                    ) VALUES (
                        101, 'stale-001', 'manual', 'Technical Solutions Engineer', 'Stripe',
                        'https://example.com/jobs/stale-001', 'Boston, MA', 'hybrid',
                        'Test description', 'Test description',
                        0.87, 'Strong fit for Python, SQL, and API-heavy technical customer work.', 'test', 'applied',
                        '2026-03-20T00:00:00Z', '2026-03-20T00:00:00Z',
                        '2026-03-20T00:00:00Z', '2026-03-20T00:00:00Z'
                    )
                    """
                ),
            )
            await session.execute(
                text(
                    """
                    INSERT INTO job_listings (
                        id, external_id, source, title, company_name, url,
                        location, remote_type, description_raw, description_clean,
                        match_score, match_reasoning, rank_model_version, status,
                        created_at, updated_at, scraped_at, ranked_at
                    ) VALUES (
                        102, 'stale-002', 'manual', 'Solutions Engineer', 'HubSpot',
                        'https://example.com/jobs/stale-002', 'Cambridge, MA', 'remote',
                        'Test description', 'Test description',
                        0.81, 'Good fit for technical customer-facing platform work.', 'test', 'archived',
                        '2026-03-20T00:00:00Z', '2026-03-20T00:00:00Z',
                        '2026-03-20T00:00:00Z', '2026-03-20T00:00:00Z'
                    )
                    """
                ),
            )

        stale_jobs = await get_stale_applications(days=7)

        assert len(stale_jobs) == 1
        assert stale_jobs[0]["id"] == 101
        assert stale_jobs[0]["status"] == "applied"
        assert stale_jobs[0]["days_stale"] >= 7
