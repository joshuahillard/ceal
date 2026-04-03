"""
Ceal Phase 2: Tailoring Engine Unit Tests

Tests the TailoringEngine with frozen LLM responses (no live API calls).
Validates tier-specific prompts, code fence stripping, score bounds,
and prompt version logging.

Persona: [QA Lead] -- frozen fixtures, Pydantic boundary enforcement
Constraint: All tests use pre-recorded responses. No live API calls.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from src.models.entities import Proficiency, SkillCategory
from src.tailoring.engine import (
    CURRENT_PROMPT_VERSION,
    TailoringEngine,
    _build_user_prompt,
    strip_code_fences,
)
from src.tailoring.models import (
    SkillGap,
    TailoredBullet,
    TailoringRequest,
    TailoringResult,
)

# ---------------------------------------------------------------------------
# Frozen LLM Response Fixtures
# ---------------------------------------------------------------------------

VALID_LLM_RESPONSE = json.dumps({
    "tailored_bullets": [
        {
            "original": "Saved Toast estimated $12 million identifying critical firmware defects",
            "rewritten_text": (
                "Accomplished $12M in annual cost savings as measured by "
                "defect resolution metrics, by doing systematic firmware "
                "root cause analysis across 50K+ deployed POS terminals"
            ),
            "xyz_format": True,
            "relevance_score": 0.95,
        },
        {
            "original": "Reduced recurring issue volume by 37%",
            "rewritten_text": (
                "Reduced recurring escalation volume by 37% through "
                "cross-functional process optimization"
            ),
            "xyz_format": False,
            "relevance_score": 0.82,
        },
    ],
    "skill_gaps": [
        {
            "skill_name": "Python",
            "category": "language",
            "job_requires": True,
            "resume_has": True,
            "proficiency": "proficient",
        },
        {
            "skill_name": "Kubernetes",
            "category": "infrastructure",
            "job_requires": True,
            "resume_has": False,
            "proficiency": None,
        },
    ],
})

TIER3_LLM_RESPONSE = json.dumps({
    "tailored_bullets": [
        {
            "original": "Directed team of senior consultants",
            "rewritten_text": (
                "Accomplished cross-org technical leadership as measured by "
                "37% reduction in recurring escalation volume, by doing "
                "data-driven process optimization across 5 engineering teams"
            ),
            "xyz_format": True,
            "relevance_score": 0.91,
        },
    ],
    "skill_gaps": [
        {
            "skill_name": "Python",
            "category": "language",
            "job_requires": True,
            "resume_has": True,
            "proficiency": "proficient",
        },
    ],
})

CODE_FENCED_RESPONSE = f"```json\n{VALID_LLM_RESPONSE}\n```"

MALFORMED_RESPONSE = "This is not JSON at all, just plain text."


# ---------------------------------------------------------------------------
# Test: strip_code_fences
# ---------------------------------------------------------------------------

class TestStripCodeFences:
    """Validates the resilient parsing fallback for LLM output."""

    def test_strips_json_fence(self):
        result = strip_code_fences("```json\n{\"key\": \"value\"}\n```")
        assert result == '{"key": "value"}'

    def test_strips_plain_fence(self):
        result = strip_code_fences("```\n{\"key\": \"value\"}\n```")
        assert result == '{"key": "value"}'

    def test_no_fences_unchanged(self):
        original = '{"key": "value"}'
        assert strip_code_fences(original) == original

    def test_handles_whitespace(self):
        result = strip_code_fences("  ```json\n{}\n```  ")
        assert result == "{}"

    def test_nested_backticks_preserved(self):
        """Only strips outermost fences."""
        result = strip_code_fences('```json\n{"code": "use ```backticks```"}\n```')
        assert "backticks" in result


# ---------------------------------------------------------------------------
# Test: _build_user_prompt
# ---------------------------------------------------------------------------

class TestBuildUserPrompt:
    """Validates tier-specific prompt construction."""

    def _make_request(self, tier: int) -> TailoringRequest:
        return TailoringRequest(
            job_id=1, profile_id=1, target_tier=tier,
            emphasis_areas=["payment systems"],
        )

    def test_tier1_prompt_contains_direct_experience(self):
        prompt = _build_user_prompt(
            self._make_request(1), ["Saved $12M"], [],
        )
        assert "DIRECT experience" in prompt or "QUANTIFIED IMPACT" in prompt

    def test_tier2_prompt_contains_growth_trajectory(self):
        prompt = _build_user_prompt(
            self._make_request(2), ["Led team"], [],
        )
        assert "GROWTH TRAJECTORY" in prompt or "stretch" in prompt

    def test_tier3_prompt_contains_xyz_format(self):
        prompt = _build_user_prompt(
            self._make_request(3), ["Led team"], [],
        )
        assert "X-Y-Z" in prompt
        assert "Google" in prompt or "L5" in prompt

    def test_emphasis_areas_included(self):
        prompt = _build_user_prompt(
            self._make_request(1), ["bullet"], [],
        )
        assert "payment systems" in prompt

    def test_skill_gaps_included(self):
        gaps = [
            SkillGap(
                skill_name="Python", category=SkillCategory.LANGUAGE,
                job_requires=True, resume_has=True, proficiency=Proficiency.PROFICIENT,
            ),
            SkillGap(
                skill_name="Kubernetes", category=SkillCategory.INFRASTRUCTURE,
                job_requires=True, resume_has=False,
            ),
        ]
        prompt = _build_user_prompt(
            self._make_request(1), ["bullet"], gaps,
        )
        assert "Python" in prompt
        assert "Kubernetes" in prompt

    def test_empty_bullets_handled(self):
        prompt = _build_user_prompt(
            self._make_request(1), [], [],
        )
        assert "Job ID: 1" in prompt


# ---------------------------------------------------------------------------
# Test: TailoringEngine
# ---------------------------------------------------------------------------

class TestTailoringEngine:
    """Validates engine behavior with frozen LLM responses."""

    def _make_request(self, tier: int = 1) -> TailoringRequest:
        return TailoringRequest(
            job_id=42, profile_id=1, target_tier=tier,
        )

    def _mock_api_response(self, response_text: str):
        """Create a mock that returns the given text from Claude API."""
        from unittest.mock import MagicMock

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "content": [{"text": response_text}],
        }
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        return mock_client

    @pytest.mark.asyncio
    async def test_engine_generates_tailored_bullets(self):
        """Happy path: valid LLM response -> TailoringResult."""
        engine = TailoringEngine(api_key="test-key")

        with patch("src.tailoring.engine.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = self._mock_api_response(VALID_LLM_RESPONSE)

            result = await engine.generate_tailored_profile(
                request=self._make_request(),
                resume_bullets=["Saved Toast $12M", "Reduced issues by 37%"],
            )

        assert isinstance(result, TailoringResult)
        assert len(result.tailored_bullets) == 2
        assert result.tailored_bullets[0].relevance_score == 0.95
        assert result.tailoring_version == CURRENT_PROMPT_VERSION

    @pytest.mark.asyncio
    async def test_engine_tier_specific_prompts(self):
        """Tier 3 request generates Google culture markers."""
        engine = TailoringEngine(api_key="test-key")

        with patch("src.tailoring.engine.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = self._mock_api_response(TIER3_LLM_RESPONSE)

            result = await engine.generate_tailored_profile(
                request=self._make_request(tier=3),
                resume_bullets=["Directed team of consultants"],
            )

        assert isinstance(result, TailoringResult)
        assert len(result.tailored_bullets) == 1
        # Tier 3 bullet should have X-Y-Z format
        bullet = result.tailored_bullets[0]
        assert bullet.xyz_format is True
        assert "measured by" in bullet.rewritten_text.lower()
        assert "by doing" in bullet.rewritten_text.lower()

    @pytest.mark.asyncio
    async def test_engine_handles_malformed_llm_code_fences(self):
        """Code-fenced response is stripped and parsed correctly."""
        engine = TailoringEngine(api_key="test-key")

        with patch("src.tailoring.engine.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = self._mock_api_response(CODE_FENCED_RESPONSE)

            result = await engine.generate_tailored_profile(
                request=self._make_request(),
                resume_bullets=["Saved $12M"],
            )

        assert isinstance(result, TailoringResult)
        assert len(result.tailored_bullets) == 2

    @pytest.mark.asyncio
    async def test_engine_malformed_json_raises(self):
        """Completely malformed response raises JSONDecodeError."""
        engine = TailoringEngine(api_key="test-key")

        with patch("src.tailoring.engine.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = self._mock_api_response(MALFORMED_RESPONSE)

            with pytest.raises(Exception):
                await engine.generate_tailored_profile(
                    request=self._make_request(),
                    resume_bullets=["Saved $12M"],
                )

    @pytest.mark.asyncio
    async def test_engine_score_validation(self):
        """Scores outside 0.0-1.0 are rejected by Pydantic."""
        bad_response = json.dumps({
            "tailored_bullets": [{
                "original": "Test",
                "rewritten_text": "Test rewrite",
                "xyz_format": False,
                "relevance_score": 1.5,  # Invalid!
            }],
            "skill_gaps": [],
        })
        engine = TailoringEngine(api_key="test-key")

        with patch("src.tailoring.engine.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = self._mock_api_response(bad_response)

            with pytest.raises(Exception):
                await engine.generate_tailored_profile(
                    request=self._make_request(),
                    resume_bullets=["Test"],
                )

    @pytest.mark.asyncio
    async def test_engine_logs_ranker_version(self):
        """Prompt version is tracked in TailoringResult."""
        engine = TailoringEngine(api_key="test-key", prompt_version="v2.0-beta")

        with patch("src.tailoring.engine.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = self._mock_api_response(VALID_LLM_RESPONSE)

            result = await engine.generate_tailored_profile(
                request=self._make_request(),
                resume_bullets=["Saved $12M"],
            )

        assert result.tailoring_version == "v2.0-beta"

    @pytest.mark.asyncio
    async def test_engine_empty_response_handled(self):
        """Empty bullet list from LLM produces valid TailoringResult."""
        empty_response = json.dumps({
            "tailored_bullets": [],
            "skill_gaps": [],
        })
        engine = TailoringEngine(api_key="test-key")

        with patch("src.tailoring.engine.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = self._mock_api_response(empty_response)

            result = await engine.generate_tailored_profile(
                request=self._make_request(),
            )

        assert isinstance(result, TailoringResult)
        assert result.tailored_bullets == []

    @pytest.mark.asyncio
    async def test_engine_preserves_request(self):
        """The original request is preserved in the result."""
        engine = TailoringEngine(api_key="test-key")
        request = self._make_request(tier=2)

        with patch("src.tailoring.engine.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = self._mock_api_response(VALID_LLM_RESPONSE)

            result = await engine.generate_tailored_profile(
                request=request, resume_bullets=["Test"],
            )

        assert result.request.job_id == 42
        assert result.request.target_tier == 2
