"""
Céal: Phase 4 Auto-Apply Tests

Tests the pre-fill engine, application database functions,
approval queue web routes, and Pydantic model validation.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.web.app import create_app

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    """Create a fresh FastAPI app for each test (skip lifespan/DB init)."""
    test_app = create_app()
    test_app.router.lifespan_context = None  # type: ignore[assignment]
    return test_app


@pytest_asyncio.fixture
async def client(app):
    """Async HTTP client wired to the test app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=True) as ac:
        yield ac


# ---------------------------------------------------------------------------
# Schema Tests
# ---------------------------------------------------------------------------

class TestPhase4Schema:
    @pytest.mark.asyncio
    async def test_applications_table_created(self):
        """Verify applications table exists after init_db."""
        import os

        from src.models.database import init_db

        # Use in-memory DB for schema test
        os.environ["DATABASE_URL"] = "sqlite+aiosqlite://"
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from sqlalchemy.pool import StaticPool

        test_engine = create_async_engine(
            "sqlite+aiosqlite://",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

        @asynccontextmanager
        async def mock_session():
            session = TestSession()
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

        with patch("src.models.database.get_session", mock_session), patch("src.models.database.engine", test_engine):
            await init_db()

            async with mock_session() as session:
                from sqlalchemy import text
                result = await session.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='applications'"))
                assert result.first() is not None

        await test_engine.dispose()

    @pytest.mark.asyncio
    async def test_application_fields_table_created(self):
        """Verify application_fields table exists after init_db."""
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from sqlalchemy.pool import StaticPool

        from src.models.database import init_db

        test_engine = create_async_engine(
            "sqlite+aiosqlite://",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

        @asynccontextmanager
        async def mock_session():
            session = TestSession()
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

        with patch("src.models.database.get_session", mock_session), patch("src.models.database.engine", test_engine):
            await init_db()

            async with mock_session() as session:
                result = await session.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='application_fields'"))
                assert result.first() is not None

        await test_engine.dispose()


# ---------------------------------------------------------------------------
# Pre-Fill Engine Tests
# ---------------------------------------------------------------------------

class TestPreFillEngine:
    def test_prefill_extracts_name_from_resume(self):
        """Verify full_name field extracted from resume."""
        from src.apply.prefill import PreFillEngine

        engine = PreFillEngine(resume_path="data/resume.txt")
        result = engine.prefill_application(job_id=1)
        name_fields = [f for f in result.fields if f.field_name == "full_name"]
        assert len(name_fields) == 1
        assert name_fields[0].field_value is not None
        assert len(name_fields[0].field_value) > 0

    def test_prefill_extracts_email_from_resume(self):
        """Verify email field extracted (or None if not in resume)."""
        from src.apply.prefill import PreFillEngine

        engine = PreFillEngine(resume_path="data/resume.txt")
        result = engine.prefill_application(job_id=1)
        email_fields = [f for f in result.fields if f.field_name == "email"]
        assert len(email_fields) == 1
        # Email may or may not be in resume — test that field exists

    def test_prefill_extracts_phone_from_resume(self):
        """Verify phone field extracted (or None if not in resume)."""
        from src.apply.prefill import PreFillEngine

        engine = PreFillEngine(resume_path="data/resume.txt")
        result = engine.prefill_application(job_id=1)
        phone_fields = [f for f in result.fields if f.field_name == "phone"]
        assert len(phone_fields) == 1

    def test_prefill_returns_application_create_model(self):
        """Verify return type is ApplicationCreate."""
        from src.apply.prefill import PreFillEngine
        from src.models.entities import ApplicationCreate

        engine = PreFillEngine(resume_path="data/resume.txt")
        result = engine.prefill_application(job_id=1)
        assert isinstance(result, ApplicationCreate)

    def test_prefill_confidence_score_between_0_and_1(self):
        """Verify overall confidence score is valid."""
        from src.apply.prefill import PreFillEngine

        engine = PreFillEngine(resume_path="data/resume.txt")
        result = engine.prefill_application(job_id=1)
        assert result.confidence_score is not None
        assert 0.0 <= result.confidence_score <= 1.0

    def test_prefill_populates_common_fields(self):
        """Verify at least 8 fields have values."""
        from src.apply.prefill import PreFillEngine

        engine = PreFillEngine(resume_path="data/resume.txt")
        result = engine.prefill_application(job_id=1)
        populated = [f for f in result.fields if f.field_value]
        assert len(populated) >= 8


# ---------------------------------------------------------------------------
# Database Function Tests (mocked session)
# ---------------------------------------------------------------------------

class TestAutoApplyDB:
    @staticmethod
    def _mock_session_ctx(mock_session):
        """Wrap a mock session so it works with `async with get_session()`."""

        @asynccontextmanager
        async def _ctx():
            yield mock_session

        return _ctx

    @pytest.mark.asyncio
    async def test_create_application_returns_id(self):
        """create_application returns the new app ID."""
        from src.models.database import create_application
        from src.models.entities import ApplicationCreate

        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 42

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        app_create = ApplicationCreate(job_id=1, profile_id=1)

        with patch("src.models.database.get_session", self._mock_session_ctx(mock_session)):
            app_id = await create_application(app_create)

        assert app_id == 42

    @pytest.mark.asyncio
    async def test_create_application_idempotent(self):
        """Creating same (job_id, profile_id) twice calls upsert (ON CONFLICT)."""
        from src.models.database import create_application
        from src.models.entities import ApplicationCreate

        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 42

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        app_create = ApplicationCreate(job_id=1, profile_id=1)

        with patch("src.models.database.get_session", self._mock_session_ctx(mock_session)):
            id1 = await create_application(app_create)
            id2 = await create_application(app_create)

        assert id1 == 42
        assert id2 == 42

    @pytest.mark.asyncio
    async def test_get_application_returns_fields(self):
        """get_application returns app dict with fields list."""
        from src.models.database import get_application

        app_mapping = {
            "id": 1, "job_id": 10, "profile_id": 1, "status": "draft",
            "cover_letter": None, "confidence_score": 0.75, "notes": "test",
            "created_at": "2026-04-02", "updated_at": "2026-04-02",
            "submitted_at": None, "job_title": "TSE", "company_name": "Stripe",
            "company_tier": 1, "match_score": 0.85, "url": "https://stripe.com",
        }
        mock_app_row = MagicMock()
        mock_app_row._mapping = app_mapping

        field_mapping = {"field_name": "full_name", "field_type": "text", "field_value": "Josh", "confidence": 0.95, "source": "resume"}
        mock_field_row = MagicMock()
        mock_field_row._mapping = field_mapping

        mock_app_result = MagicMock()
        mock_app_result.first.return_value = mock_app_row

        mock_fields_result = MagicMock()
        mock_fields_result.__iter__ = lambda self: iter([mock_field_row])

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=[mock_app_result, mock_fields_result])

        with patch("src.models.database.get_session", self._mock_session_ctx(mock_session)):
            result = await get_application(1)

        assert result is not None
        assert result["company_name"] == "Stripe"
        assert len(result["fields"]) == 1
        assert result["fields"][0]["field_name"] == "full_name"

    @pytest.mark.asyncio
    async def test_get_approval_queue_filters_by_status(self):
        """get_approval_queue returns only items matching status."""
        from src.models.database import get_approval_queue

        draft_row = MagicMock()
        draft_row._mapping = {
            "id": 1, "job_id": 10, "profile_id": 1, "status": "draft",
            "cover_letter": None, "confidence_score": 0.7, "notes": None,
            "created_at": "2026-04-02", "updated_at": "2026-04-02",
            "job_title": "TSE", "company_name": "Stripe", "company_tier": 1,
            "match_score": 0.85, "url": "https://stripe.com",
        }

        mock_result = MagicMock()
        mock_result.__iter__ = lambda self: iter([draft_row])

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("src.models.database.get_session", self._mock_session_ctx(mock_session)):
            results = await get_approval_queue(status="draft")

        assert len(results) == 1
        assert results[0]["status"] == "draft"

    @pytest.mark.asyncio
    async def test_update_application_status_valid(self):
        """Valid transition draft → ready succeeds."""
        from src.models.database import update_application_status

        mock_app_row = (1, "draft", 10)
        mock_select = MagicMock()
        mock_select.first.return_value = mock_app_row

        mock_update = MagicMock()

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=[mock_select, mock_update])

        with patch("src.models.database.get_session", self._mock_session_ctx(mock_session)):
            result = await update_application_status(1, "ready")

        assert result["previous_status"] == "draft"
        assert result["new_status"] == "ready"

    @pytest.mark.asyncio
    async def test_update_application_status_invalid(self):
        """Invalid transition draft → submitted raises ValueError."""
        from src.models.database import update_application_status

        mock_app_row = (1, "draft", 10)
        mock_select = MagicMock()
        mock_select.first.return_value = mock_app_row

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_select)

        with patch("src.models.database.get_session", self._mock_session_ctx(mock_session)), pytest.raises(ValueError, match="Invalid application transition"):
            await update_application_status(1, "submitted")

    @pytest.mark.asyncio
    async def test_update_application_status_approved_syncs_crm(self):
        """Approving an application calls update_job_status to sync CRM."""
        from src.models.database import update_application_status

        mock_app_row = (1, "ready", 10)  # ready → approved
        mock_select = MagicMock()
        mock_select.first.return_value = mock_app_row
        mock_update = MagicMock()

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=[mock_select, mock_update])

        with (
            patch("src.models.database.get_session", self._mock_session_ctx(mock_session)),
            patch("src.models.database.update_job_status", new_callable=AsyncMock) as mock_crm,
        ):
            await update_application_status(1, "approved")
            mock_crm.assert_called_once_with(10, "applied")


# ---------------------------------------------------------------------------
# Web Route Tests
# ---------------------------------------------------------------------------

class TestApplyRoutes:
    @pytest.mark.asyncio
    async def test_approval_queue_returns_200(self, client):
        """GET /apply returns 200."""
        with (
            patch("src.web.routes.apply.get_approval_queue", new_callable=AsyncMock, return_value=[]),
            patch("src.web.routes.apply.get_application_stats", new_callable=AsyncMock, return_value={}),
        ):
            response = await client.get("/apply")
        assert response.status_code == 200
        assert "Auto-Apply Queue" in response.text

    @pytest.mark.asyncio
    async def test_prefill_redirects_to_review(self, client):
        """POST /apply/prefill/{id} creates app and redirects."""
        from src.models.entities import ApplicationCreate

        mock_app = ApplicationCreate(job_id=1, profile_id=1)

        with (
            patch("src.web.routes.apply.PreFillEngine") as mock_engine_cls,
            patch("src.web.routes.apply.create_application", new_callable=AsyncMock, return_value=42),
            patch("src.web.routes.apply.get_application", new_callable=AsyncMock, return_value={
                "id": 42, "job_id": 1, "profile_id": 1, "status": "draft",
                "cover_letter": None, "confidence_score": 0.7, "notes": "test",
                "created_at": "2026-04-02", "updated_at": "2026-04-02",
                "submitted_at": None, "job_title": "TSE", "company_name": "Stripe",
                "company_tier": 1, "match_score": 0.85, "url": "https://stripe.com",
                "fields": [],
            }),
        ):
            mock_engine = MagicMock()
            mock_engine.prefill_application.return_value = mock_app
            mock_engine_cls.return_value = mock_engine

            response = await client.post("/apply/prefill/1")

        # follow_redirects=True, so we end at the review page
        assert response.status_code == 200
        assert "Application Review" in response.text

    @pytest.mark.asyncio
    async def test_review_application_returns_200(self, client):
        """GET /apply/{id} returns 200 with review page."""
        mock_app = {
            "id": 1, "job_id": 10, "profile_id": 1, "status": "draft",
            "cover_letter": None, "confidence_score": 0.75, "notes": "test",
            "created_at": "2026-04-02", "updated_at": "2026-04-02",
            "submitted_at": None, "job_title": "TSE", "company_name": "Stripe",
            "company_tier": 1, "match_score": 0.85, "url": "https://stripe.com",
            "fields": [
                {"field_name": "full_name", "field_type": "text", "field_value": "Josh", "confidence": 0.95, "source": "resume"},
            ],
        }
        with patch("src.web.routes.apply.get_application", new_callable=AsyncMock, return_value=mock_app):
            response = await client.get("/apply/1")
        assert response.status_code == 200
        assert "Application Review" in response.text
        assert "Stripe" in response.text
        assert "Full Name" in response.text

    @pytest.mark.asyncio
    async def test_status_update_redirects(self, client):
        """POST /apply/{id}/status redirects on success."""
        with (
            patch("src.web.routes.apply.update_application_status", new_callable=AsyncMock, return_value={"app_id": 1, "previous_status": "draft", "new_status": "ready"}),
            patch("src.web.routes.apply.get_approval_queue", new_callable=AsyncMock, return_value=[]),
            patch("src.web.routes.apply.get_application_stats", new_callable=AsyncMock, return_value={}),
        ):
            response = await client.post("/apply/1/status", data={"new_status": "ready"})
        assert response.status_code == 200  # follow_redirects lands on /apply

    @pytest.mark.asyncio
    async def test_invalid_status_shows_error(self, client):
        """POST /apply/{id}/status with invalid transition shows error."""
        mock_app = {
            "id": 1, "job_id": 10, "profile_id": 1, "status": "draft",
            "cover_letter": None, "confidence_score": 0.75, "notes": None,
            "created_at": "2026-04-02", "updated_at": "2026-04-02",
            "submitted_at": None, "job_title": "TSE", "company_name": "Stripe",
            "company_tier": 1, "match_score": 0.85, "url": "https://stripe.com",
            "fields": [],
        }
        with (
            patch("src.web.routes.apply.update_application_status", new_callable=AsyncMock, side_effect=ValueError("Invalid application transition")),
            patch("src.web.routes.apply.get_application", new_callable=AsyncMock, return_value=mock_app),
        ):
            response = await client.post("/apply/1/status", data={"new_status": "submitted"})
        assert response.status_code == 200
        assert "Invalid application transition" in response.text


# ---------------------------------------------------------------------------
# Model Tests
# ---------------------------------------------------------------------------

class TestAutoApplyModels:
    def test_application_status_enum_values(self):
        """Verify all 5 application status values."""
        from src.models.entities import ApplicationStatus

        assert set(ApplicationStatus) == {
            ApplicationStatus.DRAFT,
            ApplicationStatus.READY,
            ApplicationStatus.APPROVED,
            ApplicationStatus.SUBMITTED,
            ApplicationStatus.WITHDRAWN,
        }

    def test_application_create_validation(self):
        """Confidence must be 0.0-1.0."""
        from pydantic import ValidationError

        from src.models.entities import ApplicationCreate

        with pytest.raises(ValidationError):
            ApplicationCreate(job_id=1, confidence_score=1.5)

        # Valid
        app = ApplicationCreate(job_id=1, confidence_score=0.85)
        assert app.confidence_score == 0.85

    def test_field_type_enum_values(self):
        """Verify all 10 field type values."""
        from src.models.entities import FieldType

        assert len(FieldType) == 10
        assert FieldType.TEXT.value == "text"
        assert FieldType.TEXTAREA.value == "textarea"
        assert FieldType.EMAIL.value == "email"
        assert FieldType.PHONE.value == "phone"
        assert FieldType.URL.value == "url"
        assert FieldType.SELECT.value == "select"
        assert FieldType.CHECKBOX.value == "checkbox"
        assert FieldType.RADIO.value == "radio"
        assert FieldType.FILE.value == "file"
        assert FieldType.DATE.value == "date"
