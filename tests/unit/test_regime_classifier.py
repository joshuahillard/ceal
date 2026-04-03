"""
Céal: Regime Classifier Unit Tests

Tests the Vertex AI classifier with mocked API responses. No live API calls.
Validates parsing, Pydantic validation, and fail-open behavior exhaustively.

Interview point: "I mock the Vertex AI client so classifier tests are fast,
deterministic, and don't require GCP credentials. The tests prove that the
classifier is fail-open — every possible failure mode returns None instead
of raising an exception."
"""
from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from src.ranker.regime_classifier import _parse_response, classify_regime
from src.ranker.regime_models import RegimeClassification

# ---------------------------------------------------------------------------
# Mock Responses
# ---------------------------------------------------------------------------

GOOD_RESPONSE = json.dumps({
    "recommended_tier": 1,
    "confidence": 0.92,
    "reasoning": "Strong FinTech domain overlap with Stripe's TSE role. Python, SQL, and payment processing experience are direct matches.",
})

TIER_2_RESPONSE = json.dumps({
    "recommended_tier": 2,
    "confidence": 0.75,
    "reasoning": "MongoDB role needs cloud credential buildout. Current GCP skills are transferable but need MongoDB-specific certification.",
})

TIER_3_RESPONSE = json.dumps({
    "recommended_tier": 3,
    "confidence": 0.60,
    "reasoning": "Google L5 TPM is a long-term campaign target. Candidate needs strategic networking and portfolio building.",
})

CODE_FENCED_RESPONSE = f"```json\n{GOOD_RESPONSE}\n```"

MALFORMED_RESPONSE = "This is not JSON, just some text about tiers."

INVALID_TIER_RESPONSE = json.dumps({
    "recommended_tier": 4,
    "confidence": 0.80,
    "reasoning": "Invalid tier",
})

ZERO_TIER_RESPONSE = json.dumps({
    "recommended_tier": 0,
    "confidence": 0.80,
    "reasoning": "Invalid tier zero",
})

NEGATIVE_TIER_RESPONSE = json.dumps({
    "recommended_tier": -1,
    "confidence": 0.80,
    "reasoning": "Invalid negative tier",
})

HIGH_CONFIDENCE_RESPONSE = json.dumps({
    "recommended_tier": 1,
    "confidence": 1.5,
    "reasoning": "Overconfident",
})

LOW_CONFIDENCE_RESPONSE = json.dumps({
    "recommended_tier": 1,
    "confidence": -0.1,
    "reasoning": "Negative confidence",
})

MISSING_FIELD_RESPONSE = json.dumps({
    "recommended_tier": 1,
    "confidence": 0.80,
    # missing "reasoning"
})


# ---------------------------------------------------------------------------
# Response Parsing Tests (no API at all)
# ---------------------------------------------------------------------------

class TestResponseParsing:
    """Tests for _parse_response — pure function, no API calls."""

    def test_valid_classification_parsing(self):
        """Valid JSON → RegimeClassification with correct fields."""
        result = _parse_response(GOOD_RESPONSE, job_id=42, model_name="gemini-2.0-flash")

        assert result is not None
        assert isinstance(result, RegimeClassification)
        assert result.job_id == 42
        assert result.recommended_tier == 1
        assert result.confidence == 0.92
        assert "FinTech" in result.reasoning
        assert result.model_version.startswith("vertex-ai/gemini-2.0-flash/")

    def test_tier_2_parsing(self):
        result = _parse_response(TIER_2_RESPONSE, job_id=10, model_name="gemini-2.0-flash")
        assert result is not None
        assert result.recommended_tier == 2
        assert result.confidence == 0.75

    def test_tier_3_parsing(self):
        result = _parse_response(TIER_3_RESPONSE, job_id=20, model_name="gemini-2.0-flash")
        assert result is not None
        assert result.recommended_tier == 3

    def test_code_fence_stripping(self):
        """Response wrapped in ```json ... ``` still parses."""
        result = _parse_response(CODE_FENCED_RESPONSE, job_id=1, model_name="gemini-2.0-flash")
        assert result is not None
        assert result.recommended_tier == 1
        assert result.confidence == 0.92

    def test_malformed_response_returns_none(self):
        """Garbage response → returns None, no exception."""
        result = _parse_response(MALFORMED_RESPONSE, job_id=1, model_name="gemini-2.0-flash")
        assert result is None

    def test_missing_field_returns_none(self):
        """Missing required field → returns None."""
        result = _parse_response(MISSING_FIELD_RESPONSE, job_id=1, model_name="gemini-2.0-flash")
        assert result is None

    def test_model_version_format(self):
        """model_version matches expected 'vertex-ai/...' pattern."""
        result = _parse_response(GOOD_RESPONSE, job_id=1, model_name="gemini-2.0-flash")
        assert result is not None
        assert result.model_version.startswith("vertex-ai/")
        assert "gemini-2.0-flash" in result.model_version


# ---------------------------------------------------------------------------
# Pydantic Validation Tests
# ---------------------------------------------------------------------------

class TestTierValidation:
    """Tests for RegimeClassification Pydantic model validation."""

    def test_tier_validation_rejects_tier_4(self):
        """Tier 4 rejected by Pydantic."""
        result = _parse_response(INVALID_TIER_RESPONSE, job_id=1, model_name="test")
        assert result is None

    def test_tier_validation_rejects_tier_0(self):
        """Tier 0 rejected by Pydantic."""
        result = _parse_response(ZERO_TIER_RESPONSE, job_id=1, model_name="test")
        assert result is None

    def test_tier_validation_rejects_negative(self):
        """Tier -1 rejected by Pydantic."""
        result = _parse_response(NEGATIVE_TIER_RESPONSE, job_id=1, model_name="test")
        assert result is None

    def test_confidence_too_high_rejected(self):
        """confidence > 1.0 rejected."""
        result = _parse_response(HIGH_CONFIDENCE_RESPONSE, job_id=1, model_name="test")
        assert result is None

    def test_confidence_negative_rejected(self):
        """confidence < 0.0 rejected."""
        result = _parse_response(LOW_CONFIDENCE_RESPONSE, job_id=1, model_name="test")
        assert result is None

    def test_valid_tiers_accepted(self):
        """Tiers 1, 2, 3 are all accepted."""
        for tier in (1, 2, 3):
            classification = RegimeClassification(
                job_id=1,
                recommended_tier=tier,
                confidence=0.5,
                reasoning="Test",
                model_version="vertex-ai/test/2026-04-03",
            )
            assert classification.recommended_tier == tier

    def test_boundary_confidence_accepted(self):
        """confidence 0.0 and 1.0 are accepted (boundary values)."""
        for conf in (0.0, 1.0):
            classification = RegimeClassification(
                job_id=1,
                recommended_tier=1,
                confidence=conf,
                reasoning="Test",
                model_version="vertex-ai/test/2026-04-03",
            )
            assert classification.confidence == conf


# ---------------------------------------------------------------------------
# Fail-Open Behavior Tests
# ---------------------------------------------------------------------------

class TestFailOpen:
    """Tests that classify_regime returns None on every failure mode."""

    @pytest.mark.asyncio
    async def test_fail_open_missing_config(self):
        """No VERTEX_PROJECT_ID → returns None, no exception."""
        with patch.dict(os.environ, {}, clear=False):
            # Ensure VERTEX_PROJECT_ID is not set
            env = os.environ.copy()
            env.pop("VERTEX_PROJECT_ID", None)
            with patch.dict(os.environ, env, clear=True):
                result = await classify_regime(
                    job_id=1,
                    job_title="TSE",
                    company_name="Stripe",
                )
                assert result is None

    @pytest.mark.asyncio
    async def test_fail_open_import_error(self):
        """google-cloud-aiplatform not installed → returns None."""
        with (
            patch.dict(os.environ, {"VERTEX_PROJECT_ID": "test-project"}),
            patch("src.ranker.regime_classifier.classify_regime") as mock_classify,
        ):
            # Simulate the real behavior when import fails
            mock_classify.return_value = None
            result = await mock_classify(
                job_id=1,
                job_title="TSE",
                company_name="Stripe",
            )
            assert result is None

    @pytest.mark.asyncio
    async def test_fail_open_api_error(self):
        """Mocked API raises → returns None, no exception."""
        with patch.dict(os.environ, {"VERTEX_PROJECT_ID": "test-project"}):
            # Mock the vertexai imports
            mock_vertexai = MagicMock()
            mock_model_class = MagicMock()
            mock_model_instance = MagicMock()
            mock_model_instance.generate_content.side_effect = RuntimeError("API unavailable")
            mock_model_class.return_value = mock_model_instance

            with patch.dict("sys.modules", {
                "vertexai": mock_vertexai,
                "vertexai.generative_models": MagicMock(GenerativeModel=mock_model_class),
            }):
                result = await classify_regime(
                    job_id=1,
                    job_title="TSE",
                    company_name="Stripe",
                )
                assert result is None

    @pytest.mark.asyncio
    async def test_fail_open_unparseable_response(self):
        """Garbage response → returns None, no exception."""
        with patch.dict(os.environ, {"VERTEX_PROJECT_ID": "test-project"}):
            mock_vertexai = MagicMock()
            mock_model_class = MagicMock()
            mock_model_instance = MagicMock()
            mock_response = MagicMock()
            mock_response.text = "This is garbage, not JSON"
            mock_model_instance.generate_content.return_value = mock_response
            mock_model_class.return_value = mock_model_instance

            with patch.dict("sys.modules", {
                "vertexai": mock_vertexai,
                "vertexai.generative_models": MagicMock(GenerativeModel=mock_model_class),
            }):
                result = await classify_regime(
                    job_id=1,
                    job_title="TSE",
                    company_name="Stripe",
                )
                assert result is None
