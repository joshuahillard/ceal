"""
Céal: Pipeline Integration Test

Tests the full three-stage pipeline with mocked external dependencies
(LinkedIn HTTP + Claude API). Verifies that data flows correctly
through queues from scraper → normalizer → database.

Interview point: "The integration test runs the full pipeline with
mocked externals. It proves that the asyncio.Queue wiring works,
that the sentinel shutdown propagates correctly, and that data
arrives in the database with the right shape. This catches wiring
bugs that unit tests miss."
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
import pytest_asyncio
from aioresponses import aioresponses

# Override DB before imports
os.environ["DATABASE_URL"] = "sqlite+aiosqlite://"

from src.main import run_pipeline
from src.models.database import (
    engine,
    get_unranked_jobs,
    init_db,
)

MOCK_DIR = Path(__file__).parent.parent / "mocks"
SEARCH_PATTERN = re.compile(
    r"^https://www\.linkedin\.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
)
DETAIL_PATTERN = re.compile(
    r"^https://www\.linkedin\.com/jobs-guest/jobs/api/jobPosting/\d+"
)


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    await init_db()
    yield
    await engine.dispose()


@pytest.fixture
def search_html() -> str:
    return (MOCK_DIR / "linkedin_search_page.html").read_text()


@pytest.fixture
def detail_html() -> str:
    return (MOCK_DIR / "linkedin_job_detail.html").read_text()


class TestFullPipeline:
    @pytest.mark.asyncio
    async def test_scrape_and_normalize_no_rank(
        self, search_html, detail_html
    ):
        """
        Full pipeline minus ranking (no API key).
        Should scrape → normalize → insert into DB.
        """
        with aioresponses() as mock_aio:
            mock_aio.get(SEARCH_PATTERN, body=search_html, status=200)
            mock_aio.get(SEARCH_PATTERN, body="", status=200)
            mock_aio.get(DETAIL_PATTERN, body=detail_html, status=200, repeat=True)

            stats = await run_pipeline(
                query="Technical Solutions Engineer",
                location="Boston, MA",
                max_results=25,
                rank=False,  # Skip ranking
            )

        # Verify jobs made it to the database
        unranked = await get_unranked_jobs()
        assert len(unranked) == 3, f"Expected 3 jobs in DB, got {len(unranked)}"

        # Verify job data
        titles = {j["title"] for j in unranked}
        assert "Technical Solutions Engineer" in titles

        # Verify companies
        companies = {j["company_name"] for j in unranked}
        assert "Stripe" in companies
        assert "Datadog" in companies

        # Verify pipeline stats
        assert stats.get("jobs_by_status", {}).get("scraped", 0) >= 3

    @pytest.mark.asyncio
    async def test_pipeline_with_empty_scrape(self):
        """
        Pipeline should complete cleanly even with zero results.
        """
        with aioresponses() as mock_aio:
            mock_aio.get(SEARCH_PATTERN, body="<html></html>", status=200)

            await run_pipeline(
                query="Nonexistent Role",
                location="Nowhere",
                max_results=10,
                rank=False,
            )

        unranked = await get_unranked_jobs()
        assert len(unranked) == 0

    @pytest.mark.asyncio
    async def test_pipeline_descriptions_are_cleaned(
        self, search_html, detail_html
    ):
        """
        Verify that HTML descriptions are cleaned before DB insertion.
        """
        with aioresponses() as mock_aio:
            mock_aio.get(SEARCH_PATTERN, body=search_html, status=200)
            mock_aio.get(SEARCH_PATTERN, body="", status=200)
            mock_aio.get(DETAIL_PATTERN, body=detail_html, status=200, repeat=True)

            await run_pipeline(
                query="TSE",
                location="Boston",
                max_results=25,
                rank=False,
            )

        jobs = await get_unranked_jobs()
        for job in jobs:
            if job.get("description_clean"):
                # Should not contain HTML tags
                assert "<" not in job["description_clean"]
                assert ">" not in job["description_clean"]

    @pytest.mark.asyncio
    async def test_company_tiers_auto_assigned(
        self, search_html, detail_html
    ):
        """
        Companies in the tier lookup should be auto-assigned.
        """
        with aioresponses() as mock_aio:
            mock_aio.get(SEARCH_PATTERN, body=search_html, status=200)
            mock_aio.get(SEARCH_PATTERN, body="", status=200)
            mock_aio.get(DETAIL_PATTERN, body=detail_html, status=200, repeat=True)

            await run_pipeline(
                query="TSE",
                location="Boston",
                max_results=25,
                rank=False,
            )

        from sqlalchemy import text

        from src.models.database import get_session

        async with get_session() as session:
            result = await session.execute(
                text("""
                    SELECT company_name, company_tier
                    FROM job_listings
                    WHERE company_tier IS NOT NULL
                """)
            )
            tiered = {row[0]: row[1] for row in result}

        # Stripe should be Tier 1, Datadog should be Tier 1
        assert tiered.get("Stripe") == 1
        assert tiered.get("Datadog") == 1
