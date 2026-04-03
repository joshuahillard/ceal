"""
Ceal Phase 2: Tailoring Engine Guardrail Tests

Validates that the tailoring engine rejects structurally valid but
semantically unsafe rewrites before they reach persistence or export.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.entities import Proficiency, SkillCategory
from src.tailoring.engine import PROMPT_VERSION, TailoringEngine, strip_code_fences
from src.tailoring.models import (
    ParsedBullet,
    ResumeSection,
    SkillGap,
    TailoringRequest,
    TailoringResult,
)


def _make_bullets() -> list[ParsedBullet]:
    return [
        ParsedBullet(
            section=ResumeSection.EXPERIENCE,
            original_text="Saved Toast estimated $12 million by identifying critical firmware defects on handheld POS devices",
            skills_referenced=["Payment Processing"],
            metrics=["$12 million"],
        ),
        ParsedBullet(
            section=ResumeSection.EXPERIENCE,
            original_text="Created onboarding frameworks and technical enablement materials for escalation teams",
            skills_referenced=["Training & Enablement"],
            metrics=[],
        ),
    ]


def _make_skill_gaps() -> list[SkillGap]:
    return [
        SkillGap(
            skill_name="Payment Processing",
            category=SkillCategory.DOMAIN,
            job_requires=True,
            resume_has=True,
            proficiency=Proficiency.EXPERT,
        ),
    ]


def _make_request() -> TailoringRequest:
    return TailoringRequest(
        job_id=1,
        profile_id=1,
        target_tier=1,
        emphasis_areas=["Payment Processing"],
    )


def _mock_client(response_text: str) -> AsyncMock:
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"content": [{"text": response_text}]}

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


class TestStripCodeFences:
    def test_strips_json_fence(self):
        assert strip_code_fences("```json\n{}\n```") == "{}"


class TestTailoringEngineGuardrails:
    @pytest.mark.asyncio
    async def test_accepts_faithful_rewrite(self):
        response = json.dumps(
            [
                {
                    "original": _make_bullets()[0].original_text,
                    "rewritten_text": (
                        "Saved $12M in payment-platform losses as measured by defect trend reduction, "
                        "by doing firmware root cause analysis on handheld POS devices"
                    ),
                    "xyz_format": True,
                    "relevance_score": 0.94,
                },
            ]
        )
        engine = TailoringEngine(api_key="test-key")

        with patch("src.tailoring.engine.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = _mock_client(response)
            result = await engine.generate_tailored_profile(
                request=_make_request(),
                resume_bullets=[_make_bullets()[0]],
                skill_gaps=_make_skill_gaps(),
            )

        assert isinstance(result, TailoringResult)
        assert result.tailoring_version == PROMPT_VERSION
        assert result.tailored_bullets[0].xyz_format is True

    @pytest.mark.asyncio
    async def test_rejects_invented_metric(self):
        response = json.dumps(
            [
                {
                    "original": _make_bullets()[0].original_text,
                    "rewritten_text": (
                        "Saved $15M annually as measured by platform incident reduction, "
                        "by doing firmware root cause analysis on handheld POS devices"
                    ),
                    "xyz_format": True,
                    "relevance_score": 0.95,
                },
            ]
        )
        engine = TailoringEngine(api_key="test-key")

        with patch("src.tailoring.engine.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = _mock_client(response)
            with pytest.raises(ValueError, match="introduced unseen numeric claim"):
                await engine.generate_tailored_profile(
                    request=_make_request(),
                    resume_bullets=[_make_bullets()[0]],
                    skill_gaps=_make_skill_gaps(),
                )

    @pytest.mark.asyncio
    async def test_rejects_semantic_drift_without_source_anchor(self):
        response = json.dumps(
            [
                {
                    "original": _make_bullets()[1].original_text,
                    "rewritten_text": "Built greenfield cloud infrastructure for a global platform migration",
                    "xyz_format": False,
                    "relevance_score": 0.71,
                },
            ]
        )
        engine = TailoringEngine(api_key="test-key")

        with patch("src.tailoring.engine.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = _mock_client(response)
            with pytest.raises(ValueError, match="semantic drift"):
                await engine.generate_tailored_profile(
                    request=_make_request(),
                    resume_bullets=[_make_bullets()[1]],
                    skill_gaps=_make_skill_gaps(),
                )

    @pytest.mark.asyncio
    async def test_rejects_unknown_original_bullet_reference(self):
        response = json.dumps(
            [
                {
                    "original": "Managed a team of 15 engineers across three continents",
                    "rewritten_text": "Managed a team of 15 engineers across three continents",
                    "xyz_format": False,
                    "relevance_score": 0.8,
                },
            ]
        )
        engine = TailoringEngine(api_key="test-key")

        with patch("src.tailoring.engine.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = _mock_client(response)
            with pytest.raises(ValueError, match="was not in the request"):
                await engine.generate_tailored_profile(
                    request=_make_request(),
                    resume_bullets=_make_bullets(),
                    skill_gaps=_make_skill_gaps(),
                )
