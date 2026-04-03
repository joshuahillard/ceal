"""Unit tests for the cover letter content engine (Claude API integration)."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.document.coverletter_engine import (
    COVER_LETTER_PROMPT_VERSION,
    _parse_response,
    _strip_code_fences,
    generate_cover_letter_content,
)


class TestCodeFenceStripping:
    def test_strips_json_fences(self):
        raw = '```json\n{"paragraphs": ["a"]}\n```'
        assert _strip_code_fences(raw) == '{"paragraphs": ["a"]}'

    def test_strips_plain_fences(self):
        raw = '```\n{"key": "val"}\n```'
        assert _strip_code_fences(raw) == '{"key": "val"}'

    def test_no_fences_unchanged(self):
        raw = '{"paragraphs": ["a"]}'
        assert _strip_code_fences(raw) == raw


class TestParseResponse:
    def test_valid_response_parsing(self):
        """Valid JSON with 5 paragraphs returns dict."""
        raw = json.dumps({"paragraphs": [f"Paragraph {i}" for i in range(5)]})
        result = _parse_response(raw)
        assert result is not None
        assert len(result["paragraphs"]) == 5

    def test_code_fence_stripping(self):
        """Response wrapped in ```json ... ``` still parses."""
        raw = '```json\n' + json.dumps({"paragraphs": ["a", "b", "c"]}) + '\n```'
        result = _parse_response(raw)
        assert result is not None
        assert len(result["paragraphs"]) == 3

    def test_fail_graceful_bad_json(self):
        """Garbage response returns None."""
        result = _parse_response("This is not JSON at all")
        assert result is None

    def test_paragraph_count_validation_too_few(self):
        """Response with 2 paragraphs is rejected."""
        raw = json.dumps({"paragraphs": ["a", "b"]})
        result = _parse_response(raw)
        assert result is None

    def test_paragraph_count_validation_too_many(self):
        """Response with 7 paragraphs is rejected."""
        raw = json.dumps({"paragraphs": [f"P{i}" for i in range(7)]})
        result = _parse_response(raw)
        assert result is None

    def test_empty_paragraph_rejected(self):
        """Response with empty paragraph string is rejected."""
        raw = json.dumps({"paragraphs": ["Good", "", "Also good"]})
        result = _parse_response(raw)
        assert result is None

    def test_missing_paragraphs_key(self):
        """Response without 'paragraphs' key returns None."""
        raw = json.dumps({"content": ["a", "b", "c"]})
        result = _parse_response(raw)
        assert result is None


class TestGenerateCoverLetterContent:
    @pytest.mark.asyncio
    async def test_fail_graceful_missing_api_key(self):
        """No ANTHROPIC_API_KEY or LLM_API_KEY returns None."""
        with patch.dict("os.environ", {}, clear=True):
            # Clear both possible key names
            import os
            os.environ.pop("ANTHROPIC_API_KEY", None)
            os.environ.pop("LLM_API_KEY", None)
            result = await generate_cover_letter_content(
                "TSE", "Stripe", "Job description here"
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_fail_graceful_api_error(self):
        """Mocked API raises returns None."""
        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}),
            patch("src.document.coverletter_engine.httpx.AsyncClient") as mock_client_cls,
        ):
            mock_client = AsyncMock()
            mock_client.post.side_effect = Exception("API error")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await generate_cover_letter_content(
                "TSE", "Stripe", "Job description"
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_valid_api_response(self):
        """Mocked successful API response returns parsed content."""
        paragraphs = [f"Paragraph {i} content" for i in range(5)]
        api_response = {
            "content": [{"text": json.dumps({"paragraphs": paragraphs})}],
        }

        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}),
            patch("src.document.coverletter_engine.httpx.AsyncClient") as mock_client_cls,
        ):
            mock_response = MagicMock()
            mock_response.json.return_value = api_response
            mock_response.raise_for_status = MagicMock()

            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await generate_cover_letter_content(
                "TSE", "Stripe", "Job description"
            )

        assert result is not None
        assert len(result["paragraphs"]) == 5

    def test_prompt_version_tracked(self):
        """COVER_LETTER_PROMPT_VERSION exists and is a string."""
        assert isinstance(COVER_LETTER_PROMPT_VERSION, str)
        assert COVER_LETTER_PROMPT_VERSION.startswith("v")
