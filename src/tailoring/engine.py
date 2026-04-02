"""
Ceal Phase 2: Tailoring Engine

Orchestrates Claude API to rewrite resume bullets using the X-Y-Z format.
The LLM is treated as a deterministic software component, not a chatbot.
All output passes through TailoringResult Pydantic validation before
reaching the application tracking CRM.

Persona: Applied AI / LLM Orchestration Architect
Constraint: LLM must output strictly parseable JSON with match_score,
            reasoning, and skills analysis. Prompt version tracked via
            tailoring_version for A/B testing.
Fallback: If LLM generates markdown code fences or malformed JSON,
          resilient parsing strips fences and validates through Pydantic
          before any data enters the database.

Interview talking point:
    "I treat the LLM as a deterministic software component — its output
    passes through the same Pydantic validation layer as every other
    pipeline stage. If the model hallucinates formatting, the validator
    catches it before it pollutes the application CRM."
"""
from __future__ import annotations

import json
import re

import httpx
import structlog

from src.tailoring.models import (
    ParsedBullet,
    SkillGap,
    TailoredBullet,
    TailoringRequest,
    TailoringResult,
)

logger = structlog.get_logger(__name__)

PROMPT_VERSION = "v1.0"


def strip_code_fences(text: str) -> str:
    """Remove markdown code fences from LLM response."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


class TailoringEngine:
    """Generates role-specific emphasis profiles using skill-gap analysis."""

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    async def generate_tailored_profile(
        self,
        request: TailoringRequest,
        resume_bullets: list[ParsedBullet],
        skill_gaps: list[SkillGap],
    ) -> TailoringResult:
        """
        Executes LLM request and validates output through TailoringResult.

        Args:
            request: Validated TailoringRequest with job_id, profile_id,
                     target_tier, and emphasis_areas.
            resume_bullets: Parsed resume bullets to rewrite.
            skill_gaps: Skill gap analysis for context.

        Returns:
            TailoringResult with tailored bullets, skill gaps, and
            version tracking for prompt A/B testing.

        Raises:
            ValidationError: If LLM output fails Pydantic contract.
        """
        prompt = self._build_prompt(request, resume_bullets, skill_gaps)
        raw_response = await self._call_claude_api(prompt)
        tailored_bullets = self._parse_llm_response(raw_response, resume_bullets)

        return TailoringResult(
            request=request,
            tailored_bullets=tailored_bullets,
            skill_gaps=skill_gaps,
            tailoring_version=PROMPT_VERSION,
        )

    def _build_prompt(
        self,
        request: TailoringRequest,
        bullets: list[ParsedBullet],
        gaps: list[SkillGap],
    ) -> str:
        """Build structured prompt for Claude API."""
        tier_strategy = {
            1: "Apply Now — lead with quantified impact, mirror job keywords exactly",
            2: "Build Credential — emphasize transferable skills and growth trajectory",
            3: "Campaign — highlight domain expertise and strategic thinking",
        }

        skill_context = "\n".join(
            f"  - {g.skill_name}: {'HAVE' if g.resume_has else 'GAP'} ({g.category.value})"
            for g in gaps
        )

        bullet_list = "\n".join(
            f"  {i+1}. [{b.section.value}] {b.original_text}"
            for i, b in enumerate(bullets[:15])  # Limit to 15 bullets
        )

        return f"""You are a resume tailoring engine. Rewrite the following resume bullets
to better match the target job listing. Use the X-Y-Z format where appropriate:
"Accomplished [X] as measured by [Y], by doing [Z]"

STRATEGY: Tier {request.target_tier} — {tier_strategy.get(request.target_tier, '')}

SKILL GAP ANALYSIS:
{skill_context}

EMPHASIS AREAS: {', '.join(request.emphasis_areas) if request.emphasis_areas else 'None specified'}

RESUME BULLETS TO REWRITE:
{bullet_list}

Respond with ONLY a JSON array. Each element must have:
- "original": the original bullet text (exact match)
- "rewritten_text": the improved bullet
- "xyz_format": true ONLY if the rewrite contains both "measured by" AND "by doing"
- "relevance_score": 0.0-1.0 how relevant this bullet is to the target role

Return ONLY the JSON array, no markdown fences, no explanation."""

    async def _call_claude_api(self, prompt: str) -> str:
        """Call Claude API via httpx and return raw text response."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 4096,
                    "messages": [
                        {"role": "user", "content": prompt},
                    ],
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["content"][0]["text"]

    def _parse_llm_response(
        self,
        raw: str,
        original_bullets: list[ParsedBullet],
    ) -> list[TailoredBullet]:
        """Parse LLM JSON response into validated TailoredBullet list."""
        cleaned = strip_code_fences(raw)
        items = json.loads(cleaned)

        results: list[TailoredBullet] = []
        for item in items:
            results.append(TailoredBullet(
                original=item["original"],
                rewritten_text=item["rewritten_text"],
                xyz_format=item.get("xyz_format", False),
                relevance_score=max(0.0, min(1.0, float(item.get("relevance_score", 0.5)))),
            ))

        return results
