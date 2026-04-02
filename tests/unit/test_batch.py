"""
Ceal Phase 2: Batch Tailoring Tests

Tests batch processing logic with mocked database and API calls.
"""
from __future__ import annotations

import os
import tempfile
from unittest.mock import AsyncMock, patch

import pytest

from src.batch import run_batch_tailoring

# Ensure test uses in-memory DB
os.environ["DATABASE_URL"] = "sqlite+aiosqlite://"


def _make_job_dict(job_id: int = 1, **overrides) -> dict:
    """Create a mock job dict matching get_top_matches() output."""
    base = {
        "id": job_id,
        "title": f"TSE at Company{job_id}",
        "company_name": f"Company{job_id}",
        "company_tier": 1,
        "match_score": 0.85,
        "match_reasoning": "Strong match",
        "url": f"https://example.com/{job_id}",
        "location": "Remote",
        "remote_type": "remote",
        "salary_min": None,
        "salary_max": None,
        "status": "ranked",
        "description_clean": "Needs Python, SQL, REST APIs experience.",
        "description_raw": "Needs Python, SQL, REST APIs experience.",
    }
    base.update(overrides)
    return base


@pytest.fixture
def resume_file():
    """Create a temp resume file for testing."""
    content = """EXPERIENCE
Acme Corp — Engineer (2020-2024)
- Built REST API services using Python and asyncio for production workloads
- Managed SQL databases and payment processing integrations

SKILLS
- Technical: Python, SQL, REST APIs
"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8",
    ) as f:
        f.write(content)
        path = f.name
    yield path
    os.unlink(path)


class TestBatchTailoring:
    """Tests for batch tailoring mode."""

    @pytest.mark.asyncio
    async def test_batch_skips_already_tailored(self, resume_file):
        """Jobs with existing results are skipped."""
        mock_result = AsyncMock()  # non-None means already tailored

        with (
            patch("src.batch.get_top_matches", new_callable=AsyncMock) as mock_top,
            patch("src.batch.get_tailoring_results", new_callable=AsyncMock) as mock_get,
            patch.dict(os.environ, {"LLM_API_KEY": "test-key"}),
        ):
            mock_top.return_value = [_make_job_dict(1)]
            mock_get.return_value = mock_result  # already exists

            stats = await run_batch_tailoring(resume_file, limit=5)

        assert stats["skipped"] == 1
        assert stats["tailored"] == 0

    @pytest.mark.asyncio
    async def test_batch_respects_limit(self, resume_file):
        """Only N jobs are fetched from the database."""
        with (
            patch("src.batch.get_top_matches", new_callable=AsyncMock) as mock_top,
            patch.dict(os.environ, {"LLM_API_KEY": "test-key"}),
        ):
            mock_top.return_value = []

            stats = await run_batch_tailoring(resume_file, limit=10, min_score=0.7)

        mock_top.assert_called_once_with(min_score=0.7, limit=10)
        assert stats["total"] == 0

    @pytest.mark.asyncio
    async def test_batch_handles_api_failure_gracefully(self, resume_file):
        """One LLM failure doesn't crash the entire batch."""
        with (
            patch("src.batch.get_top_matches", new_callable=AsyncMock) as mock_top,
            patch("src.batch.get_tailoring_results", new_callable=AsyncMock) as mock_get,
            patch("src.tailoring.engine.TailoringEngine.generate_tailored_profile", new_callable=AsyncMock) as mock_gen,
            patch.dict(os.environ, {"LLM_API_KEY": "test-key"}),
        ):
            mock_top.return_value = [_make_job_dict(1), _make_job_dict(2)]
            mock_get.return_value = None  # not yet tailored
            mock_gen.side_effect = Exception("API rate limit")

            stats = await run_batch_tailoring(resume_file, limit=5)

        assert stats["errors"] == 2
        assert stats["tailored"] == 0
        assert stats["total"] == 2

    @pytest.mark.asyncio
    async def test_batch_no_api_key(self, resume_file):
        """Batch fails gracefully without API key."""
        with (
            patch("src.batch.load_dotenv"),
            patch("src.batch.os.getenv", return_value=None),
        ):
            stats = await run_batch_tailoring(resume_file)

        assert "error" in stats
