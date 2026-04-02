"""
Céal: CRM Tests — Application Tracking + Kanban Board

Tests the state machine transitions, CRM database functions,
and web routes for application tracking.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.models.database import VALID_TRANSITIONS
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
# VALID_TRANSITIONS Tests
# ---------------------------------------------------------------------------

class TestValidTransitions:
    def test_scraped_can_transition_to_ranked(self):
        assert "ranked" in VALID_TRANSITIONS["scraped"]

    def test_scraped_cannot_skip_to_offer(self):
        assert "offer" not in VALID_TRANSITIONS["scraped"]

    def test_archived_is_terminal(self):
        assert VALID_TRANSITIONS["archived"] == set()

    def test_all_statuses_have_transition_entry(self):
        expected = {"scraped", "ranked", "applied", "responded", "interviewing", "offer", "rejected", "archived"}
        assert set(VALID_TRANSITIONS.keys()) == expected


# ---------------------------------------------------------------------------
# Database Function Tests (mocked session)
# ---------------------------------------------------------------------------

class TestUpdateJobStatus:
    @staticmethod
    def _mock_session_ctx(mock_session):
        """Wrap a mock session so it works with `async with get_session()`."""
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def _ctx():
            yield mock_session

        return _ctx

    @pytest.mark.asyncio
    async def test_valid_transition_updates_status(self):
        """Transition scraped → ranked succeeds."""
        from src.models.database import update_job_status

        mock_job_row = (1, "scraped", "TSE", "Stripe")
        mock_select_result = MagicMock()
        mock_select_result.first.return_value = mock_job_row
        mock_update_result = MagicMock()

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=[mock_select_result, mock_update_result])

        with patch("src.models.database.get_session", self._mock_session_ctx(mock_session)):
            result = await update_job_status(1, "ranked")

        assert result["previous_status"] == "scraped"
        assert result["new_status"] == "ranked"

    @pytest.mark.asyncio
    async def test_invalid_transition_raises_valueerror(self):
        """Transition scraped → offer is rejected."""
        from src.models.database import update_job_status

        mock_job_row = (1, "scraped", "TSE", "Stripe")
        mock_result = MagicMock()
        mock_result.first.return_value = mock_job_row

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("src.models.database.get_session", self._mock_session_ctx(mock_session)), pytest.raises(ValueError, match="Invalid transition"):
            await update_job_status(1, "offer")

    @pytest.mark.asyncio
    async def test_nonexistent_job_raises_valueerror(self):
        """Non-existent job raises ValueError."""
        from src.models.database import update_job_status

        mock_result = MagicMock()
        mock_result.first.return_value = None

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("src.models.database.get_session", self._mock_session_ctx(mock_session)), pytest.raises(ValueError, match="not found"):
            await update_job_status(999, "ranked")


# ---------------------------------------------------------------------------
# Web Route Tests
# ---------------------------------------------------------------------------

class TestKanbanRoute:
    @pytest.mark.asyncio
    async def test_kanban_board_returns_200(self, client):
        """GET /applications returns 200 with Kanban board."""
        mock_summary = {"scraped": 10, "ranked": 5, "applied": 2}
        mock_jobs = [
            {
                "id": 1,
                "title": "TSE",
                "company_name": "Stripe",
                "company_tier": 1,
                "match_score": 0.85,
                "match_reasoning": "Strong fit",
                "url": "https://stripe.com",
                "location": "Boston",
                "remote_type": "hybrid",
                "salary_min": None,
                "salary_max": None,
                "status": "ranked",
                "updated_at": "2026-04-01T12:00:00Z",
            },
        ]
        with (
            patch("src.web.routes.applications.get_application_summary", new_callable=AsyncMock, return_value=mock_summary),
            patch("src.web.routes.applications.get_jobs_by_status", new_callable=AsyncMock, return_value=mock_jobs),
            patch("src.web.routes.applications.get_stale_applications", new_callable=AsyncMock, return_value=[]),
        ):
            response = await client.get("/applications")
        assert response.status_code == 200
        assert "Application Tracker" in response.text
        assert "Stripe" in response.text

    @pytest.mark.asyncio
    async def test_status_update_redirects_on_success(self, client):
        """POST /applications/{id}/status redirects on valid transition."""
        mock_summary = {"ranked": 5}
        with (
            patch("src.web.routes.applications.update_job_status", new_callable=AsyncMock, return_value={"job_id": 1, "previous_status": "ranked", "new_status": "applied"}),
            patch("src.web.routes.applications.get_application_summary", new_callable=AsyncMock, return_value=mock_summary),
            patch("src.web.routes.applications.get_jobs_by_status", new_callable=AsyncMock, return_value=[]),
            patch("src.web.routes.applications.get_stale_applications", new_callable=AsyncMock, return_value=[]),
        ):
            response = await client.post(
                "/applications/1/status",
                data={"new_status": "applied"},
            )
        # follow_redirects=True means we end up at /applications with 200
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_status_update_shows_error_on_invalid(self, client):
        """POST /applications/{id}/status shows error for invalid transition."""
        mock_summary = {"ranked": 5}
        with (
            patch("src.web.routes.applications.update_job_status", new_callable=AsyncMock, side_effect=ValueError("Invalid transition: scraped → offer")),
            patch("src.web.routes.applications.get_application_summary", new_callable=AsyncMock, return_value=mock_summary),
            patch("src.web.routes.applications.get_jobs_by_status", new_callable=AsyncMock, return_value=[]),
            patch("src.web.routes.applications.get_stale_applications", new_callable=AsyncMock, return_value=[]),
        ):
            response = await client.post(
                "/applications/1/status",
                data={"new_status": "offer"},
            )
        assert response.status_code == 200
        assert "Invalid transition" in response.text

    @pytest.mark.asyncio
    async def test_reminders_returns_200(self, client):
        """GET /applications/reminders returns 200."""
        with patch("src.web.routes.applications.get_stale_applications", new_callable=AsyncMock, return_value=[]):
            response = await client.get("/applications/reminders")
        assert response.status_code == 200
        assert "Follow-Up Reminders" in response.text
        assert "on top of things" in response.text


# ---------------------------------------------------------------------------
# Stale Applications Tests
# ---------------------------------------------------------------------------

class TestStaleApplications:
    @pytest.mark.asyncio
    async def test_stale_only_returns_active_statuses(self):
        """get_stale_applications only returns applied/responded/interviewing."""
        from contextlib import asynccontextmanager

        from src.models.database import get_stale_applications

        mock_rows = [
            AsyncMock(
                _mapping={
                    "id": 1, "title": "TSE", "company_name": "Stripe",
                    "company_tier": 1, "match_score": 0.8, "status": "applied",
                    "updated_at": "2026-03-20", "days_stale": 13,
                },
            ),
        ]
        mock_result = AsyncMock()
        mock_result.__iter__ = lambda self: iter(mock_rows)

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        @asynccontextmanager
        async def _ctx():
            yield mock_session

        with patch("src.models.database.get_session", _ctx):
            results = await get_stale_applications(days=7)

        assert len(results) == 1
        assert results[0]["status"] == "applied"
