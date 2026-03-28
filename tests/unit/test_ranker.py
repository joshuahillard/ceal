"""
Céal: Ranker Tests

Tests the LLM ranker with mocked API responses. No real API calls.

Interview point: "I mock the Anthropic API so ranker tests are fast,
deterministic, and don't cost money. The mock returns the exact JSON
structure Claude would return, and the tests verify that Pydantic
validation catches malformed responses."
"""

from __future__ import annotations

import json

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from src.models.entities import RankedResult
from src.ranker.llm_ranker import LLMRanker, RANKER_VERSION


# ---------------------------------------------------------------------------
# Mock LLM Responses
# ---------------------------------------------------------------------------

GOOD_RESPONSE = json.dumps({
    "match_score": 0.87,
    "match_reasoning": "Strong fit: 6+ years technical escalation management at Toast maps directly to TSE requirements. Python and SQL skills match. Payment processing domain experience is a key differentiator.",
    "skills_matched": ["Python", "SQL", "Payment Processing", "Technical Escalation Management", "REST APIs"],
    "skills_missing": ["Go", "Kubernetes"],
})

LOW_SCORE_RESPONSE = json.dumps({
    "match_score": 0.25,
    "match_reasoning": "Weak fit: Role requires 5+ years of Rust and systems programming. Candidate's Python experience is relevant but insufficient for this low-level infrastructure role.",
    "skills_matched": ["Linux", "Git"],
    "skills_missing": ["Rust", "C++", "Kernel Development"],
})

RESPONSE_WITH_CODE_FENCE = f"```json\n{GOOD_RESPONSE}\n```"

MALFORMED_RESPONSE = "This is not JSON at all, just rambling text."

INVALID_SCORE_RESPONSE = json.dumps({
    "match_score": 1.5,
    "match_reasoning": "Perfect match",
    "skills_matched": [],
    "skills_missing": [],
})


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _mock_httpx_response(text: str, status: int = 200):
    """Create a mock httpx response matching Anthropic's API format."""
    resp = MagicMock()
    resp.status_code = status
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "content": [{"type": "text", "text": text}],
        "model": "claude-sonnet-4-20250514",
        "usage": {"input_tokens": 500, "output_tokens": 200},
    }
    return resp


# ---------------------------------------------------------------------------
# Response Parsing Tests (no HTTP at all)
# ---------------------------------------------------------------------------

class TestResponseParsing:
    def test_parse_good_response(self):
        ranker = LLMRanker.__new__(LLMRanker)
        ranker.model = "test-model"
        result = ranker._parse_response(GOOD_RESPONSE, job_id=42)

        assert isinstance(result, RankedResult)
        assert result.job_id == 42
        assert result.match_score == 0.87
        assert "Strong fit" in result.match_reasoning
        assert "Python" in result.skills_matched
        assert "Go" in result.skills_missing
        assert RANKER_VERSION in result.rank_model_version

    def test_parse_code_fenced_response(self):
        """LLMs sometimes wrap JSON in ```json blocks."""
        ranker = LLMRanker.__new__(LLMRanker)
        ranker.model = "test-model"
        result = ranker._parse_response(RESPONSE_WITH_CODE_FENCE, job_id=1)

        assert result.match_score == 0.87

    def test_parse_malformed_response_raises(self):
        """Non-JSON responses should raise ValueError."""
        ranker = LLMRanker.__new__(LLMRanker)
        ranker.model = "test-model"

        with pytest.raises(ValueError, match="invalid JSON"):
            ranker._parse_response(MALFORMED_RESPONSE, job_id=1)

    def test_parse_invalid_score_raises(self):
        """Score > 1.0 should fail Pydantic validation."""
        ranker = LLMRanker.__new__(LLMRanker)
        ranker.model = "test-model"

        with pytest.raises(Exception):  # Pydantic ValidationError
            ranker._parse_response(INVALID_SCORE_RESPONSE, job_id=1)

    def test_parse_low_score(self):
        ranker = LLMRanker.__new__(LLMRanker)
        ranker.model = "test-model"
        result = ranker._parse_response(LOW_SCORE_RESPONSE, job_id=5)

        assert result.match_score == 0.25
        assert "Weak fit" in result.match_reasoning


# ---------------------------------------------------------------------------
# Mocked API Call Tests
# ---------------------------------------------------------------------------

class TestLLMRankerWithMockedAPI:
    @pytest.mark.asyncio
    async def test_rank_job_returns_valid_result(self):
        """Full rank_job flow with mocked HTTP."""
        mock_resp = _mock_httpx_response(GOOD_RESPONSE)

        async with LLMRanker(api_key="test-key") as ranker:
            ranker._client.post = AsyncMock(return_value=mock_resp)

            result = await ranker.rank_job(
                job_id=42,
                job_title="Technical Solutions Engineer",
                company_name="Stripe",
                job_description="We need a TSE with Python and SQL...",
                resume_text="Josh Hillard — 6 years at Toast...",
                location="Boston, MA",
                required_skills=["Python", "SQL"],
                nice_to_have_skills=["Docker"],
            )

        assert isinstance(result, RankedResult)
        assert result.job_id == 42
        assert result.match_score == 0.87

    @pytest.mark.asyncio
    async def test_rank_job_sends_correct_payload(self):
        """Verify the API payload includes the right model and prompt."""
        mock_resp = _mock_httpx_response(GOOD_RESPONSE)

        async with LLMRanker(api_key="test-key", model="claude-sonnet-4-20250514") as ranker:
            ranker._client.post = AsyncMock(return_value=mock_resp)

            await ranker.rank_job(
                job_id=1,
                job_title="TPM",
                company_name="Google",
                job_description="Program management role...",
                resume_text="Josh Hillard resume...",
            )

            # Verify the API was called
            ranker._client.post.assert_called_once()
            call_kwargs = ranker._client.post.call_args
            payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")

            assert payload["model"] == "claude-sonnet-4-20250514"
            assert len(payload["messages"]) == 1
            assert "Josh Hillard" in payload["messages"][0]["content"]

    @pytest.mark.asyncio
    async def test_context_manager_required(self):
        """Using rank_job without context manager should raise."""
        ranker = LLMRanker(api_key="test-key")

        with pytest.raises(RuntimeError, match="not initialized"):
            await ranker.rank_job(
                job_id=1,
                job_title="Test",
                company_name="Test",
                job_description="Test",
                resume_text="Test",
            )

    @pytest.mark.asyncio
    async def test_rank_model_version_tracked(self):
        """Result should include the ranker version + model name."""
        mock_resp = _mock_httpx_response(GOOD_RESPONSE)

        async with LLMRanker(api_key="test-key", model="claude-sonnet-4-20250514") as ranker:
            ranker._client.post = AsyncMock(return_value=mock_resp)

            result = await ranker.rank_job(
                job_id=1,
                job_title="TSE",
                company_name="Stripe",
                job_description="...",
                resume_text="...",
            )

        assert "v1.0" in result.rank_model_version
        assert "claude" in result.rank_model_version
