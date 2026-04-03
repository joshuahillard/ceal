"""
Céal: Web Route Tests

Tests the FastAPI web layer using httpx.AsyncClient with mocked
database functions to avoid requiring a real database connection.

Interview point: "I test the web layer independently from the database
by mocking the query functions. This lets me verify routing, template
rendering, and form processing without database setup overhead."
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.web.app import create_app


@pytest.fixture
def app():
    """Create a fresh FastAPI app for each test (skip lifespan/DB init)."""
    test_app = create_app()
    # Disable lifespan so init_db() is not called during tests
    test_app.router.lifespan_context = None  # type: ignore[assignment]
    return test_app


@pytest_asyncio.fixture
async def client(app):
    """Async HTTP client wired to the test app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=True) as ac:
        yield ac


# ---------------------------------------------------------------------------
# Dashboard Tests
# ---------------------------------------------------------------------------

class TestDashboard:
    @pytest.mark.asyncio
    async def test_dashboard_returns_200(self, client):
        """GET / returns 200 with dashboard content."""
        mock_stats = {
            "jobs_by_status": {"scraped": 10, "ranked": 5},
            "jobs_by_tier": {"tier_1": 3, "tier_2": 2},
            "avg_match_score": 0.72,
            "total_ranked": 5,
            "latest_scrape": None,
        }
        mock_regime = {
            "tier_1_count": 3, "tier_2_count": 1, "tier_3_count": 1,
            "unclassified_count": 0, "total_classified": 5,
        }
        with (
            patch("src.web.routes.dashboard.get_pipeline_stats", new_callable=AsyncMock, return_value=mock_stats),
            patch(
                "src.web.routes.dashboard.get_application_summary",
                new_callable=AsyncMock,
                return_value={"ranked": 3, "applied": 2},
            ),
            patch("src.web.routes.dashboard.get_stale_applications", new_callable=AsyncMock, return_value=[{"id": 1}]),
            patch(
                "src.web.routes.dashboard.get_application_stats",
                new_callable=AsyncMock,
                return_value={"draft": 1, "ready": 1},
            ),
            patch(
                "src.web.routes.dashboard._get_regime_stats_safe",
                new_callable=AsyncMock,
                return_value=mock_regime,
            ),
        ):
            response = await client.get("/")
        assert response.status_code == 200
        assert "Pipeline Dashboard" in response.text
        assert "72%" in response.text
        assert "Application Pipeline" in response.text
        assert "Auto-Apply Pipeline" in response.text
        assert "Follow-Up Reminders" in response.text
        assert "Regime Classification" in response.text

    @pytest.mark.asyncio
    async def test_dashboard_empty_state(self, client):
        """Dashboard renders cleanly with no data."""
        mock_stats = {
            "jobs_by_status": {},
            "jobs_by_tier": {},
            "avg_match_score": None,
            "total_ranked": 0,
            "latest_scrape": None,
        }
        mock_regime_empty = {
            "tier_1_count": 0, "tier_2_count": 0, "tier_3_count": 0,
            "unclassified_count": 0, "total_classified": 0,
        }
        with (
            patch("src.web.routes.dashboard.get_pipeline_stats", new_callable=AsyncMock, return_value=mock_stats),
            patch("src.web.routes.dashboard.get_application_summary", new_callable=AsyncMock, return_value={}),
            patch("src.web.routes.dashboard.get_stale_applications", new_callable=AsyncMock, return_value=[]),
            patch("src.web.routes.dashboard.get_application_stats", new_callable=AsyncMock, return_value={}),
            patch(
                "src.web.routes.dashboard._get_regime_stats_safe",
                new_callable=AsyncMock,
                return_value=mock_regime_empty,
            ),
        ):
            response = await client.get("/")
        assert response.status_code == 200
        assert "No jobs in pipeline yet" in response.text
        assert "No applications tracked yet" in response.text
        assert "No auto-apply drafts yet" in response.text
        assert "No classifications yet" in response.text


# ---------------------------------------------------------------------------
# Jobs Tests
# ---------------------------------------------------------------------------

class TestJobs:
    @pytest.mark.asyncio
    async def test_jobs_returns_200(self, client):
        """GET /jobs returns 200 with job table."""
        mock_jobs = [
            {
                "id": 1,
                "title": "TSE",
                "company_name": "Stripe",
                "company_tier": 1,
                "match_score": 0.85,
                "match_reasoning": "Strong fit",
                "url": "https://stripe.com/jobs/1",
                "location": "Boston, MA",
                "remote_type": "hybrid",
                "salary_min": None,
                "salary_max": None,
                "status": "ranked",
            },
        ]
        refresh_meta = {
            "attempted": True,
            "success": True,
            "fallback": False,
            "source_label": "LinkedIn",
            "query": "Technical Solutions Engineer",
            "location": "Boston, MA",
            "llm_enabled": True,
            "refreshed_count": 1,
            "ranked_count": 1,
            "warning": None,
            "error": None,
        }
        with patch(
            "src.web.routes.jobs._load_jobs_page",
            new_callable=AsyncMock,
            return_value=(mock_jobs, refresh_meta),
        ):
            response = await client.get("/jobs")
        assert response.status_code == 200
        assert "Stripe" in response.text
        assert "85%" in response.text
        assert "Pre-Fill" in response.text
        assert "Live Refresh" in response.text

    @pytest.mark.asyncio
    async def test_jobs_empty(self, client):
        """GET /jobs with no matches shows empty state."""
        refresh_meta = {
            "attempted": True,
            "success": True,
            "fallback": False,
            "source_label": "LinkedIn",
            "query": "Technical Solutions Engineer",
            "location": "Boston, MA",
            "llm_enabled": True,
            "refreshed_count": 0,
            "ranked_count": 0,
            "warning": None,
            "error": None,
        }
        with patch(
            "src.web.routes.jobs._load_jobs_page",
            new_callable=AsyncMock,
            return_value=([], refresh_meta),
        ):
            response = await client.get("/jobs")
        assert response.status_code == 200
        assert "No jobs match" in response.text

    @pytest.mark.asyncio
    async def test_jobs_filter_params(self, client):
        """GET /jobs passes filter parameters correctly."""
        refresh_meta = {
            "attempted": True,
            "success": True,
            "fallback": False,
            "source_label": "LinkedIn",
            "query": "Platform Engineer",
            "location": "Remote",
            "llm_enabled": True,
            "refreshed_count": 0,
            "ranked_count": 0,
            "warning": None,
            "error": None,
        }
        with patch(
            "src.web.routes.jobs._load_jobs_page",
            new_callable=AsyncMock,
            return_value=([], refresh_meta),
        ) as mock:
            response = await client.get("/jobs?min_score=0.7&tier=1&limit=10")
        assert response.status_code == 200
        mock.assert_called_once_with(
            query="Technical Solutions Engineer",
            location="Boston, MA",
            min_score=0.7,
            tier=1,
            limit=10,
        )

    @pytest.mark.asyncio
    async def test_jobs_empty_tier_query_does_not_422(self, client):
        """Empty tier query params from the filter form should fall back to All."""
        refresh_meta = {
            "attempted": True,
            "success": True,
            "fallback": False,
            "source_label": "LinkedIn",
            "query": "Technical Solutions Engineer",
            "location": "Boston, MA",
            "llm_enabled": True,
            "refreshed_count": 0,
            "ranked_count": 0,
            "warning": None,
            "error": None,
        }
        with patch(
            "src.web.routes.jobs._load_jobs_page",
            new_callable=AsyncMock,
            return_value=([], refresh_meta),
        ) as mock:
            response = await client.get("/jobs?tier=")

        assert response.status_code == 200
        mock.assert_called_once_with(
            query="Technical Solutions Engineer",
            location="Boston, MA",
            min_score=0.3,
            tier=None,
            limit=25,
        )

    @pytest.mark.asyncio
    async def test_jobs_route_accepts_no_trailing_slash_without_redirect(self, app):
        """The nav link should load /jobs directly without an extra redirect hop."""
        refresh_meta = {
            "attempted": True,
            "success": True,
            "fallback": False,
            "source_label": "LinkedIn",
            "query": "Technical Solutions Engineer",
            "location": "Boston, MA",
            "llm_enabled": True,
            "refreshed_count": 0,
            "ranked_count": 0,
            "warning": None,
            "error": None,
        }
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as raw_client:
            with patch(
                "src.web.routes.jobs._load_jobs_page",
                new_callable=AsyncMock,
                return_value=([], refresh_meta),
            ) as mock:
                response = await raw_client.get("/jobs")

        assert response.status_code == 200
        mock.assert_called_once_with(
            query="Technical Solutions Engineer",
            location="Boston, MA",
            min_score=0.3,
            tier=None,
            limit=25,
        )

    @pytest.mark.asyncio
    async def test_jobs_refresh_disables_rejected_llm_key_after_first_401(self):
        """A rejected Anthropic key should produce one graceful failure, then skip future ranking."""
        from src.models.entities import JobListingCreate, JobSource, RemoteType
        from src.web.routes import jobs as jobs_route

        raw_job = SimpleNamespace(external_id="job-1")
        clean_job = JobListingCreate(
            external_id="job-1",
            source=JobSource.LINKEDIN,
            title="Technical Solutions Engineer",
            company_name="Stripe",
            url="https://stripe.com/jobs/1",
            location="Boston, MA",
            remote_type=RemoteType.HYBRID,
            description_raw="Solve customer issues with Python and APIs.",
            description_clean="Solve customer issues with Python and APIs.",
        )
        request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        response = httpx.Response(401, request=request)
        auth_error = httpx.HTTPStatusError("Unauthorized", request=request, response=response)

        with (
            patch.dict("os.environ", {"LLM_API_KEY": "bad-key"}, clear=True),
            patch.object(jobs_route, "_INVALID_LLM_API_KEY", None),
            patch("src.web.routes.jobs.LinkedInScraper") as mock_scraper_cls,
            patch("src.web.routes.jobs.normalize_job", return_value=(clean_job, [])),
            patch("src.web.routes.jobs.upsert_job", new_callable=AsyncMock, return_value=11),
            patch("src.web.routes.jobs.assign_company_tiers", new_callable=AsyncMock, return_value=0),
            patch("src.web.routes.jobs.get_jobs_by_ids", new_callable=AsyncMock, return_value=[{"id": 11}]),
            patch("src.web.routes.jobs._load_resume_text", return_value="Resume text"),
            patch("src.web.routes.jobs.LLMRanker") as mock_ranker_cls,
        ):
            mock_scraper = AsyncMock()
            mock_scraper.scrape_jobs.return_value = [raw_job]
            mock_scraper_cls.return_value.__aenter__ = AsyncMock(return_value=mock_scraper)
            mock_scraper_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            mock_ranker = AsyncMock()
            mock_ranker.rank_job.side_effect = auth_error
            mock_ranker_cls.return_value.__aenter__ = AsyncMock(return_value=mock_ranker)
            mock_ranker_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            first = await jobs_route._refresh_live_jobs("Technical Solutions Engineer", "Boston, MA", 1)
            second = await jobs_route._refresh_live_jobs("Technical Solutions Engineer", "Boston, MA", 1)

        assert first["success"] is True
        assert first["ranked_count"] == 0
        assert "rejected by Anthropic" in first["warning"]
        assert second["success"] is True
        assert second["ranked_count"] == 0
        assert "rejected by Anthropic" in second["warning"]
        assert mock_ranker.rank_job.await_count == 1

    @pytest.mark.asyncio
    async def test_jobs_query_and_location_are_preserved(self, client):
        """Jobs page should drive live refresh from the current search inputs."""
        refresh_meta = {
            "attempted": True,
            "success": True,
            "fallback": False,
            "source_label": "LinkedIn",
            "query": "TPM",
            "location": "New York, NY",
            "llm_enabled": True,
            "refreshed_count": 0,
            "ranked_count": 0,
            "warning": None,
            "error": None,
        }
        with patch(
            "src.web.routes.jobs._load_jobs_page",
            new_callable=AsyncMock,
            return_value=([], refresh_meta),
        ) as mock:
            response = await client.get("/jobs?query=TPM&location=New%20York,%20NY&min_score=0.5")

        assert response.status_code == 200
        mock.assert_called_once_with(
            query="TPM",
            location="New York, NY",
            min_score=0.5,
            tier=None,
            limit=25,
        )
        assert 'value="TPM"' in response.text
        assert 'value="New York, NY"' in response.text


# ---------------------------------------------------------------------------
# Demo Tests
# ---------------------------------------------------------------------------

class TestDemo:
    @pytest.mark.asyncio
    async def test_demo_form_returns_200(self, client):
        """GET /demo returns 200 with form."""
        response = await client.get("/demo")
        assert response.status_code == 200
        assert "Demo Mode" in response.text
        assert "Run Tailoring" in response.text

    @pytest.mark.asyncio
    async def test_demo_post_with_description(self, client):
        """POST /demo with resume + job description returns skill gaps."""
        resume = """
EXPERIENCE:
- Manager II, Technical Escalations at Toast, Inc. (Oct 2023 - Oct 2025)
  * Directed team of senior technical consultants handling complex escalations
  * Identified critical firmware defects saving estimated $12 million
SKILLS:
Technical: Python, SQL, REST APIs, Linux
"""
        job_desc = """
We are looking for a Technical Solutions Engineer with experience in:
- Python programming
- SQL databases
- REST API design
- Troubleshooting complex technical issues
"""
        response = await client.post(
            "/demo",
            data={
                "resume_text": resume,
                "job_description": job_desc,
                "job_url": "",
                "target_tier": "1",
            },
        )
        assert response.status_code == 200
        assert "Skill Gap Analysis" in response.text

    @pytest.mark.asyncio
    async def test_demo_post_missing_description(self, client):
        """POST /demo without job description shows error."""
        response = await client.post(
            "/demo",
            data={
                "resume_text": "Some resume text here that is long enough",
                "job_description": "",
                "job_url": "",
                "target_tier": "1",
            },
        )
        assert response.status_code == 200
        assert "Please provide a job description or URL" in response.text

    @pytest.mark.asyncio
    async def test_demo_post_with_llm_mock(self, client):
        """POST /demo with mocked LLM engine returns tailored bullets."""
        from src.tailoring.models import TailoredBullet, TailoringRequest, TailoringResult

        mock_result = TailoringResult(
            request=TailoringRequest(job_id=0, profile_id=1, target_tier=1, emphasis_areas=[]),
            tailored_bullets=[
                TailoredBullet(
                    original="Directed team of senior consultants",
                    rewritten_text="Accomplished team leadership as measured by 37% issue reduction, by doing cross-functional coordination",
                    xyz_format=True,
                    relevance_score=0.9,
                ),
            ],
            skill_gaps=[],
            tailoring_version="v1.0",
        )

        resume = """
EXPERIENCE:
- Manager II, Technical Escalations at Toast, Inc. (Oct 2023 - Oct 2025)
  * Directed team of senior technical consultants handling complex escalations
  * Identified critical firmware defects saving estimated $12 million
SKILLS:
Technical: Python, SQL, REST APIs, Linux
"""
        job_desc = "Looking for a TSE with Python, SQL, REST APIs, troubleshooting."

        with (
            patch.dict("os.environ", {"LLM_API_KEY": "test-key-123"}),
            patch(
                "src.tailoring.engine.TailoringEngine",
            ) as mock_engine_cls,
        ):
            mock_engine = AsyncMock()
            mock_engine.generate_tailored_profile.return_value = mock_result
            mock_engine_cls.return_value = mock_engine

            response = await client.post(
                "/demo",
                data={
                    "resume_text": resume,
                    "job_description": job_desc,
                    "job_url": "",
                    "target_tier": "1",
                },
            )

        assert response.status_code == 200
        assert "Tailored Bullets" in response.text
        assert "90% relevant" in response.text
