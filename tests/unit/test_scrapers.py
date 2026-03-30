"""
Céal: Scraper Tests

Tests the scraper framework and LinkedIn implementation using mocked
HTTP responses. No live network calls — deterministic and fast.

Interview point: "I mock external dependencies with aioresponses so
tests are deterministic, fast, and don't depend on LinkedIn being up.
This is the same pattern used in CI/CD pipelines at companies like
Stripe and Datadog — you can't have flaky tests blocking deploys
because a third-party endpoint is slow."

Test categories:
  1. Base scraper mechanics (semaphore, retries, error handling)
  2. LinkedIn search result parsing (HTML → RawJobListing)
  3. LinkedIn job detail extraction (description enrichment)
  4. Full scrape flow with pagination
  5. Edge cases (empty results, rate limiting, blocked)
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from aioresponses import aioresponses

from src.models.entities import JobSource, RemoteType
from src.scrapers.base import (
    BlockedError,
    RateLimitError,
    ScrapeMetrics,
)
from src.scrapers.linkedin import (
    LinkedInScraper,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MOCK_DIR = Path(__file__).parent.parent / "mocks"

# Pattern to match the LinkedIn search URL with any query params
SEARCH_PATTERN = re.compile(r"^https://www\.linkedin\.com/jobs-guest/jobs/api/seeMoreJobPostings/search")
DETAIL_PATTERN = re.compile(r"^https://www\.linkedin\.com/jobs-guest/jobs/api/jobPosting/\d+")


@pytest.fixture
def search_html() -> str:
    """Load the mock LinkedIn search results page."""
    return (MOCK_DIR / "linkedin_search_page.html").read_text()


@pytest.fixture
def detail_html() -> str:
    """Load the mock LinkedIn job detail page."""
    return (MOCK_DIR / "linkedin_job_detail.html").read_text()


@pytest.fixture
def mock_aio():
    """Create an aioresponses mock context."""
    with aioresponses() as m:
        yield m


# ---------------------------------------------------------------------------
# ScrapeMetrics Tests
# ---------------------------------------------------------------------------

class TestScrapeMetrics:
    def test_initial_state(self):
        m = ScrapeMetrics()
        assert m.requests_made == 0
        assert m.success_rate == 0.0

    def test_success_rate_calculation(self):
        m = ScrapeMetrics()
        m.requests_made = 10
        m.requests_succeeded = 8
        m.requests_failed = 2
        assert m.success_rate == 0.8

    def test_to_dict(self):
        m = ScrapeMetrics()
        d = m.to_dict()
        assert "requests_made" in d
        assert "duration_seconds" in d
        assert "success_rate" in d


# ---------------------------------------------------------------------------
# LinkedIn HTML Parsing Tests (no network calls)
# ---------------------------------------------------------------------------

class TestLinkedInParsing:
    """Test the HTML parsing logic in isolation — no HTTP involved."""

    def test_parse_search_results(self, search_html):
        """Should parse 3 job cards from the mock HTML."""
        scraper = LinkedInScraper.__new__(LinkedInScraper)
        scraper._metrics = ScrapeMetrics()
        jobs = scraper._parse_search_results(search_html)

        assert len(jobs) == 3

    def test_parse_stripe_listing(self, search_html):
        """First card should be the Stripe TSE role."""
        scraper = LinkedInScraper.__new__(LinkedInScraper)
        scraper._metrics = ScrapeMetrics()
        jobs = scraper._parse_search_results(search_html)

        stripe_job = jobs[0]
        assert stripe_job.external_id == "3847291001"
        assert stripe_job.source == JobSource.LINKEDIN
        assert stripe_job.title == "Technical Solutions Engineer"
        assert stripe_job.company_name == "Stripe"
        assert "linkedin.com" in stripe_job.url
        assert stripe_job.salary_text == "$120K - $160K"

    def test_parse_datadog_listing(self, search_html):
        """Second card should be the Datadog TPM role."""
        scraper = LinkedInScraper.__new__(LinkedInScraper)
        scraper._metrics = ScrapeMetrics()
        jobs = scraper._parse_search_results(search_html)

        dd_job = jobs[1]
        assert dd_job.external_id == "3847291002"
        assert dd_job.company_name == "Datadog"
        assert dd_job.title == "Senior Technical Program Manager"

    def test_remote_type_detection(self, search_html):
        """Should detect hybrid and remote from location text."""
        scraper = LinkedInScraper.__new__(LinkedInScraper)
        scraper._metrics = ScrapeMetrics()
        jobs = scraper._parse_search_results(search_html)

        # Stripe: "Boston, MA (Hybrid)" → HYBRID
        assert jobs[0].remote_type == RemoteType.HYBRID
        # Datadog: "New York, NY (Remote)" → REMOTE
        assert jobs[1].remote_type == RemoteType.REMOTE
        # Coinbase: "San Francisco, CA" → UNKNOWN
        assert jobs[2].remote_type == RemoteType.UNKNOWN

    def test_url_tracking_params_stripped(self, search_html):
        """URLs should have tracking parameters removed."""
        scraper = LinkedInScraper.__new__(LinkedInScraper)
        scraper._metrics = ScrapeMetrics()
        jobs = scraper._parse_search_results(search_html)

        # The Stripe URL in the mock has ?position=1&pageNum=0
        assert "?" not in jobs[0].url
        assert "position" not in jobs[0].url

    def test_parse_listing_returns_none_for_garbage(self):
        """parse_listing should return None for non-job HTML."""
        scraper = LinkedInScraper.__new__(LinkedInScraper)
        scraper._metrics = ScrapeMetrics()

        result = scraper.parse_listing("<div>not a job card</div>")
        assert result is None

    def test_parse_listing_returns_none_for_missing_urn(self):
        """Cards without data-entity-urn should be skipped."""
        scraper = LinkedInScraper.__new__(LinkedInScraper)
        scraper._metrics = ScrapeMetrics()

        html = '<li><div class="base-card"><h3>No URN</h3></div></li>'
        result = scraper.parse_listing(html)
        assert result is None

    def test_extract_description(self, detail_html):
        """Should extract description text from job detail HTML."""
        scraper = LinkedInScraper.__new__(LinkedInScraper)

        desc = scraper._extract_description(detail_html)
        assert desc is not None
        assert "Technical Solutions Engineer" in desc
        assert "Python" in desc
        assert "REST APIs" in desc

    def test_all_parsed_jobs_are_valid_pydantic_models(self, search_html):
        """Every parsed job should be a valid RawJobListing (Pydantic enforced)."""
        scraper = LinkedInScraper.__new__(LinkedInScraper)
        scraper._metrics = ScrapeMetrics()
        jobs = scraper._parse_search_results(search_html)

        for job in jobs:
            # If these fail, Pydantic validation is broken
            assert job.external_id
            assert job.source == JobSource.LINKEDIN
            assert job.title
            assert job.company_name
            assert job.url.startswith("https://")


# ---------------------------------------------------------------------------
# Full Scrape Flow Tests (with mocked HTTP)
# ---------------------------------------------------------------------------

class TestLinkedInScrapeFlow:
    """Test the full scrape_jobs flow with mocked HTTP responses."""

    @pytest.mark.asyncio
    async def test_scrape_single_page(self, mock_aio, search_html):
        """Should fetch one page and parse 3 jobs."""
        # Mock the search endpoint (pattern matches URL with any query params)
        mock_aio.get(SEARCH_PATTERN, body=search_html, status=200)
        # Mock a second page that returns empty (signals end)
        mock_aio.get(SEARCH_PATTERN, body="", status=200)

        async with LinkedInScraper(
            concurrency=2,
            request_delay=0.01,  # Fast for tests
            fetch_descriptions=False,  # Skip detail fetching
        ) as scraper:
            jobs = await scraper.scrape_jobs(
                query="Technical Solutions Engineer",
                location="Boston, MA",
                max_results=25,
            )

        assert len(jobs) == 3
        assert scraper.metrics.jobs_found == 3
        assert scraper.metrics.jobs_parsed == 3

    @pytest.mark.asyncio
    async def test_scrape_with_descriptions(
        self, mock_aio, search_html, detail_html
    ):
        """Should enrich jobs with full descriptions."""
        # Mock search
        mock_aio.get(SEARCH_PATTERN, body=search_html, status=200)
        mock_aio.get(SEARCH_PATTERN, body="", status=200)

        # Mock detail pages (pattern matches any job ID)
        mock_aio.get(DETAIL_PATTERN, body=detail_html, status=200, repeat=True)

        async with LinkedInScraper(
            concurrency=2,
            request_delay=0.01,
            fetch_descriptions=True,
        ) as scraper:
            jobs = await scraper.scrape_jobs(
                query="Technical Solutions Engineer",
                location="Boston, MA",
                max_results=25,
            )

        assert len(jobs) == 3
        # All jobs should have descriptions now
        for job in jobs:
            assert job.description_raw is not None
            assert "Python" in job.description_raw

    @pytest.mark.asyncio
    async def test_scrape_respects_max_results(self, mock_aio, search_html):
        """Should stop after max_results even if more pages exist."""
        # Return results on every page (infinite)
        mock_aio.get(SEARCH_PATTERN, body=search_html, status=200, repeat=True)

        async with LinkedInScraper(
            concurrency=2,
            request_delay=0.01,
            fetch_descriptions=False,
        ) as scraper:
            jobs = await scraper.scrape_jobs(
                query="Test",
                location="Boston",
                max_results=3,
            )

        # Should be capped at 3 even though each page has 3 results
        assert len(jobs) <= 3

    @pytest.mark.asyncio
    async def test_scrape_handles_rate_limit(self, mock_aio):
        """Should stop gracefully on 429 and return what it has."""
        mock_aio.get(
            SEARCH_PATTERN,
            status=429,
            headers={"Retry-After": "60"},
        )

        async with LinkedInScraper(
            concurrency=1,
            request_delay=0.01,
            fetch_descriptions=False,
        ) as scraper:
            jobs = await scraper.scrape_jobs(
                query="Test",
                location="Boston",
                max_results=25,
            )

        assert len(jobs) == 0  # No data before rate limit
        assert scraper.metrics.requests_failed >= 1

    @pytest.mark.asyncio
    async def test_scrape_handles_block(self, mock_aio):
        """Should stop gracefully on 403 (bot detection)."""
        mock_aio.get(SEARCH_PATTERN, status=403)

        async with LinkedInScraper(
            concurrency=1,
            request_delay=0.01,
            fetch_descriptions=False,
        ) as scraper:
            jobs = await scraper.scrape_jobs(
                query="Test",
                location="Boston",
                max_results=25,
            )

        assert len(jobs) == 0

    @pytest.mark.asyncio
    async def test_description_fetch_failure_is_graceful(
        self, mock_aio, search_html
    ):
        """If description fetch fails, job should still have card-level data."""
        mock_aio.get(SEARCH_PATTERN, body=search_html, status=200)
        mock_aio.get(SEARCH_PATTERN, body="", status=200)

        # Detail pages all return 500 (tenacity retries, then gives up)
        mock_aio.get(DETAIL_PATTERN, status=500, repeat=True)

        async with LinkedInScraper(
            concurrency=2,
            request_delay=0.01,
            fetch_descriptions=True,
            max_retries=1,
        ) as scraper:
            jobs = await scraper.scrape_jobs(
                query="Test",
                location="Boston",
                max_results=25,
            )

        # Jobs should still exist, just without descriptions
        assert len(jobs) == 3
        for job in jobs:
            assert job.title  # Card-level data preserved
            assert job.company_name

    @pytest.mark.asyncio
    async def test_empty_first_page_returns_empty(self, mock_aio):
        """An empty first page should return an empty list."""
        mock_aio.get(SEARCH_PATTERN, body="<html></html>", status=200)

        async with LinkedInScraper(
            concurrency=1,
            request_delay=0.01,
            fetch_descriptions=False,
        ) as scraper:
            jobs = await scraper.scrape_jobs(
                query="Nonexistent Role",
                location="Nowhere",
                max_results=25,
            )

        assert len(jobs) == 0


# ---------------------------------------------------------------------------
# Base Scraper Mechanics Tests
# ---------------------------------------------------------------------------

class TestBaseScraper:
    """Test the base scraper's HTTP mechanics."""

    @pytest.mark.asyncio
    async def test_fetch_success(self, mock_aio):
        """fetch() should return response text on 200."""
        mock_aio.get("https://example.com/test", body="hello", status=200)

        async with LinkedInScraper(
            concurrency=1, request_delay=0.01
        ) as scraper:
            result = await scraper.fetch("https://example.com/test")

        assert result == "hello"
        assert scraper.metrics.requests_succeeded == 1

    @pytest.mark.asyncio
    async def test_fetch_rate_limit_raises(self, mock_aio):
        """fetch() should raise RateLimitError on 429."""
        mock_aio.get(
            "https://example.com/test",
            status=429,
            headers={"Retry-After": "30"},
        )

        async with LinkedInScraper(
            concurrency=1, request_delay=0.01
        ) as scraper:
            with pytest.raises(RateLimitError) as exc_info:
                await scraper.fetch("https://example.com/test")

            assert exc_info.value.retry_after == 30

    @pytest.mark.asyncio
    async def test_fetch_blocked_raises(self, mock_aio):
        """fetch() should raise BlockedError on 403."""
        mock_aio.get("https://example.com/test", status=403)

        async with LinkedInScraper(
            concurrency=1, request_delay=0.01
        ) as scraper:
            with pytest.raises(BlockedError):
                await scraper.fetch("https://example.com/test")

    @pytest.mark.asyncio
    async def test_fetch_404_returns_empty(self, mock_aio):
        """fetch() should return empty string on 404 (not an error)."""
        mock_aio.get("https://example.com/test", status=404)

        async with LinkedInScraper(
            concurrency=1, request_delay=0.01
        ) as scraper:
            result = await scraper.fetch("https://example.com/test")

        assert result == ""

    @pytest.mark.asyncio
    async def test_fetch_many_concurrent(self, mock_aio):
        """fetch_many should fetch multiple URLs concurrently."""
        for i in range(5):
            mock_aio.get(
                f"https://example.com/{i}",
                body=f"response_{i}",
                status=200,
            )

        async with LinkedInScraper(
            concurrency=3, request_delay=0.01
        ) as scraper:
            results = await scraper.fetch_many(
                [f"https://example.com/{i}" for i in range(5)]
            )

        assert len(results) == 5
        assert scraper.metrics.requests_succeeded == 5

    @pytest.mark.asyncio
    async def test_fetch_many_partial_failure(self, mock_aio):
        """fetch_many should return empty string for failed URLs."""
        mock_aio.get("https://example.com/ok", body="good", status=200)
        mock_aio.get("https://example.com/bad", status=403)

        async with LinkedInScraper(
            concurrency=2, request_delay=0.01
        ) as scraper:
            results = await scraper.fetch_many([
                "https://example.com/ok",
                "https://example.com/bad",
            ])

        result_dict = dict(results)
        assert result_dict["https://example.com/ok"] == "good"
        assert result_dict["https://example.com/bad"] == ""

    @pytest.mark.asyncio
    async def test_context_manager_required(self):
        """Using fetch without context manager should raise."""
        scraper = LinkedInScraper(concurrency=1)
        from src.scrapers.base import ScraperError

        with pytest.raises(ScraperError, match="Session not initialized"):
            await scraper.fetch("https://example.com")

    @pytest.mark.asyncio
    async def test_metrics_tracked_across_requests(self, mock_aio):
        """Metrics should accumulate across multiple requests."""
        mock_aio.get("https://example.com/1", body="ok", status=200)
        mock_aio.get("https://example.com/2", body="ok", status=200)
        mock_aio.get("https://example.com/3", status=404)

        async with LinkedInScraper(
            concurrency=2, request_delay=0.01
        ) as scraper:
            await scraper.fetch("https://example.com/1")
            await scraper.fetch("https://example.com/2")
            await scraper.fetch("https://example.com/3")

        assert scraper.metrics.requests_made == 3
        assert scraper.metrics.requests_succeeded == 2
        assert scraper.metrics.requests_failed == 1
