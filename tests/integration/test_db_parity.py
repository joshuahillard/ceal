"""
Integration tests for backend parity across SQLite and PostgreSQL.

These tests avoid SQLite-only introspection and exercise the shared
database operations that must behave identically across both engines.
"""
from __future__ import annotations

import os

import pytest
import pytest_asyncio
from sqlalchemy import text

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")

from src.models.database import (  # noqa: E402
    assign_company_tiers,
    create_application,
    engine,
    get_application,
    get_session,
    get_top_matches,
    init_db,
    update_application_status,
    update_job_ranking,
    upsert_job,
)
from src.models.entities import (  # noqa: E402
    ApplicationCreate,
    ApplicationFieldCreate,
    FieldSource,
    FieldType,
    JobListingCreate,
    JobSource,
    RankedResult,
    RemoteType,
)
from tests.integration.conftest import drop_all_tables  # noqa: E402

pytestmark = [pytest.mark.db_parity]


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """Initialize a fresh database using the active backend schema."""
    async with engine.begin() as conn:
        await conn.run_sync(drop_all_tables)

    await init_db()
    yield
    await engine.dispose()


def _make_job(external_id: str, company_name: str = "Stripe") -> JobListingCreate:
    """Build a portable job listing payload for parity tests."""
    return JobListingCreate(
        external_id=external_id,
        source=JobSource.MANUAL,
        title="Technical Solutions Engineer",
        company_name=company_name,
        url=f"https://example.com/jobs/{external_id}",
        location="Boston, MA",
        remote_type=RemoteType.HYBRID,
        description_raw="Role supporting API and database troubleshooting",
        description_clean="Role supporting API and database troubleshooting",
    )


async def _create_ranked_job(external_id: str, company_name: str = "Stripe") -> int:
    """Insert and rank a job so parity tests can exercise read paths."""
    job_id = await upsert_job(_make_job(external_id=external_id, company_name=company_name))
    await update_job_ranking(
        RankedResult(
            job_id=job_id,
            match_score=0.91,
            match_reasoning="Strong overlap with Python, SQL, and customer-facing debugging.",
            rank_model_version="parity-test",
        )
    )
    return job_id


class TestDbParity:
    @pytest.mark.asyncio
    async def test_init_db_seeds_default_profile_and_reference_data(self):
        """Startup schema init should seed the same baseline data on both backends."""
        async with get_session() as session:
            profile_result = await session.execute(
                text("SELECT id, name, raw_text FROM resume_profiles WHERE id = 1")
            )
            company_result = await session.execute(text("SELECT COUNT(*) FROM company_tiers"))
            skills_result = await session.execute(text("SELECT COUNT(*) FROM skills"))

        profile_row = profile_result.first()
        assert profile_row is not None
        assert profile_row[0] == 1
        assert profile_row[1]
        assert company_result.scalar_one() >= 10
        assert skills_result.scalar_one() >= 30

    @pytest.mark.asyncio
    async def test_job_upsert_ranking_and_top_matches_round_trip(self):
        """Shared job operations should return the same shape and state across engines."""
        job_id = await _create_ranked_job("parity-ranked-001", company_name="Stripe")
        updated_tiers = await assign_company_tiers()
        matches = await get_top_matches(min_score=0.5, limit=5)

        assert updated_tiers >= 1
        assert matches
        top_match = matches[0]
        assert top_match["id"] == job_id
        assert top_match["status"] == "ranked"
        assert top_match["company_name"] == "Stripe"
        assert top_match["company_tier"] == 1
        assert top_match["match_score"] == pytest.approx(0.91, abs=0.001)

    @pytest.mark.asyncio
    async def test_application_create_read_and_approval_flow(self):
        """Application lifecycle should stay in sync with the parent job on both engines."""
        job_id = await _create_ranked_job("parity-app-001", company_name="Datadog")

        app_id = await create_application(
            ApplicationCreate(
                job_id=job_id,
                profile_id=1,
                confidence_score=0.84,
                notes="Parity test draft",
                fields=[
                    ApplicationFieldCreate(
                        field_name="full_name",
                        field_type=FieldType.TEXT,
                        field_value="Josh Hillard",
                        confidence=0.95,
                        source=FieldSource.RESUME,
                    ),
                    ApplicationFieldCreate(
                        field_name="email",
                        field_type=FieldType.EMAIL,
                        field_value="josh@example.com",
                        confidence=0.95,
                        source=FieldSource.RESUME,
                    ),
                ],
            )
        )

        draft = await get_application(app_id)
        assert draft is not None
        assert draft["status"] == "draft"
        assert {field["field_name"] for field in draft["fields"]} == {"full_name", "email"}

        await update_application_status(app_id, "ready")
        await update_application_status(app_id, "approved")
        await update_application_status(app_id, "submitted")

        submitted = await get_application(app_id)
        assert submitted is not None
        assert submitted["status"] == "submitted"
        assert submitted["submitted_at"] is not None

        async with get_session() as session:
            job_result = await session.execute(
                text("SELECT status FROM job_listings WHERE id = :job_id"),
                {"job_id": job_id},
            )

        assert job_result.scalar_one() == "applied"

    @pytest.mark.asyncio
    async def test_invalid_transition_raises_value_error(self):
        """Skipping states (draft -> submitted) raises ValueError on both backends."""
        job_id = await _create_ranked_job("parity-invalid-001")
        app_id = await create_application(ApplicationCreate(job_id=job_id, profile_id=1))

        with pytest.raises(ValueError, match="Invalid application transition"):
            await update_application_status(app_id, "submitted")

    @pytest.mark.asyncio
    async def test_application_idempotent_upsert(self):
        """Creating the same (job_id, profile_id) twice returns the same ID."""
        job_id = await _create_ranked_job("parity-idempotent-001")
        app = ApplicationCreate(job_id=job_id, profile_id=1)
        id_1 = await create_application(app)
        id_2 = await create_application(app)
        assert id_1 == id_2
