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
    "I treat the LLM as a deterministic software component -- its output
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
    SkillGap,
    TailoredBullet,
    TailoringRequest,
    TailoringResult,
)

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Prompt Version Tracking
# ---------------------------------------------------------------------------
CURRENT_PROMPT_VERSION = "v1.0"

# ---------------------------------------------------------------------------
# Tier-Specific Prompt Templates
# ---------------------------------------------------------------------------

_TIER_PROMPTS: dict[int, str] = {
    1: (
        "TIER 1 - APPLY NOW: This is a high-match role. Emphasize DIRECT experience "
        "and QUANTIFIED IMPACT. Lead with dollar amounts, percentages, and team sizes. "
        "Use action verbs: Directed, Saved, Reduced, Identified. "
        "Every bullet must demonstrate immediate value to the hiring manager."
    ),
    2: (
        "TIER 2 - CREDENTIAL BUILDING: This is a stretch role. Highlight the "
        "candidate's GROWTH TRAJECTORY and transferable skills. Frame current "
        "experience as a stepping stone. Emphasize cloud migration pathway, "
        "cross-functional collaboration, and self-directed learning. "
        "Show ambition without overselling."
    ),
    3: (
        "TIER 3 - CAMPAIGN TARGET: This is a Google/FAANG-tier role. Use strict "
        "X-Y-Z format: 'Accomplished [X] as measured by [Y], by doing [Z]'. "
        "Include Google culture markers: data-driven decisions, scale thinking, "
        "user impact. Frame all experience through the lens of L5 competency "
        "signals: technical leadership, ambiguity navigation, cross-org impact."
    ),
}

_SYSTEM_PROMPT = """\
You are a resume tailoring engine. You rewrite resume bullets to be maximally \
relevant for a specific job listing. You output ONLY valid JSON, no markdown, \
no explanation.

Output format:
{
  "tailored_bullets": [
    {
      "original": "<original bullet text>",
      "rewritten_text": "<rewritten bullet>",
      "xyz_format": <true if X-Y-Z format>,
      "relevance_score": <0.0 to 1.0>
    }
  ],
  "skill_gaps": [
    {
      "skill_name": "<skill>",
      "category": "<language|framework|infrastructure|database|cloud|methodology|soft_skill|domain|tool>",
      "job_requires": true,
      "resume_has": <true|false>,
      "proficiency": "<expert|proficient|familiar|learning|null>"
    }
  ]
}

Rules:
- relevance_score MUST be between 0.0 and 1.0
- xyz_format=true ONLY if the bullet contains both "measured by" AND "by doing"
- Output valid JSON only. No markdown fences, no comments, no trailing commas.
"""


def _build_user_prompt(
    request: TailoringRequest,
    resume_bullets: list[str],
    skill_gaps: list[SkillGap],
) -> str:
    """Build the user message with job context, tier strategy, and resume bullets."""
    tier_instruction = _TIER_PROMPTS.get(request.target_tier, _TIER_PROMPTS[1])

    emphasis = ""
    if request.emphasis_areas:
        emphasis = f"\nEmphasis areas: {', '.join(request.emphasis_areas)}"

    skill_gap_text = ""
    if skill_gaps:
        has_skills = [g.skill_name for g in skill_gaps if g.resume_has]
        missing_skills = [g.skill_name for g in skill_gaps if not g.resume_has]
        skill_gap_text = (
            f"\n\nSkill Analysis:"
            f"\n  Candidate has: {', '.join(has_skills) if has_skills else 'None detected'}"
            f"\n  Gaps to address: {', '.join(missing_skills) if missing_skills else 'None'}"
        )

    bullets_text = "\n".join(f"- {b}" for b in resume_bullets)

    return (
        f"Job ID: {request.job_id} | Profile ID: {request.profile_id}\n"
        f"Target Tier: {request.target_tier}\n"
        f"\n{tier_instruction}{emphasis}{skill_gap_text}\n"
        f"\nResume bullets to tailor:\n{bullets_text}\n"
        f"\nRewrite each bullet for maximum relevance. Output JSON only."
    )


def strip_code_fences(text: str) -> str:
    """
    Strip markdown code fences from LLM output.

    The LLM sometimes wraps JSON in ```json ... ``` despite instructions.
    This fallback ensures we can still parse the response.
    """
    text = text.strip()
    if text.startswith("```"):
        # Remove opening fence (```json or ```)
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        # Remove closing fence
        text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


class TailoringEngine:
    """Generates role-specific emphasis profiles using skill-gap analysis."""

    def __init__(self, api_key: str, prompt_version: str = CURRENT_PROMPT_VERSION) -> None:
        self.api_key = api_key
        self.prompt_version = prompt_version

    async def generate_tailored_profile(
        self,
        request: TailoringRequest,
        resume_bullets: list[str] | None = None,
        skill_gaps: list[SkillGap] | None = None,
    ) -> TailoringResult:
        """
        Executes LLM request and validates output through TailoringResult.

        Args:
            request: Validated TailoringRequest with job_id, profile_id,
                     target_tier, and emphasis_areas.
            resume_bullets: List of bullet strings to tailor.
            skill_gaps: Pre-computed skill gap analysis.

        Returns:
            TailoringResult with tailored bullets, skill gaps, and
            version tracking for prompt A/B testing.

        Raises:
            ValidationError: If LLM output fails Pydantic contract.
        """
        resume_bullets = resume_bullets or []
        skill_gaps = skill_gaps or []

        user_prompt = _build_user_prompt(request, resume_bullets, skill_gaps)

        logger.info(
            "tailoring_engine_call",
            job_id=request.job_id,
            tier=request.target_tier,
            prompt_version=self.prompt_version,
            bullet_count=len(resume_bullets),
        )

        raw_response = await self._call_claude_api(user_prompt)
        parsed = self._parse_llm_response(raw_response)

        # Build validated TailoringResult
        tailored_bullets = [
            TailoredBullet(**bullet) for bullet in parsed.get("tailored_bullets", [])
        ]
        response_gaps = [
            SkillGap(**gap) for gap in parsed.get("skill_gaps", [])
        ]

        result = TailoringResult(
            request=request,
            tailored_bullets=tailored_bullets,
            skill_gaps=response_gaps if response_gaps else skill_gaps,
            tailoring_version=self.prompt_version,
        )

        logger.info(
            "tailoring_engine_success",
            job_id=request.job_id,
            bullets_generated=len(result.tailored_bullets),
            ranker_version=self.prompt_version,
        )

        return result

    async def _call_claude_api(self, user_prompt: str) -> str:
        """
        Call Claude API via httpx with JSON response format.
        Returns raw response text.
        """
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
                    "system": _SYSTEM_PROMPT,
                    "messages": [
                        {"role": "user", "content": user_prompt},
                    ],
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["content"][0]["text"]

    def _parse_llm_response(self, raw: str) -> dict:
        """
        Parse LLM response with code fence stripping fallback.
        Returns parsed JSON dict.
        """
        cleaned = strip_code_fences(raw)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(
                "llm_response_parse_failed",
                error=str(e),
                raw_preview=cleaned[:200],
            )
            raise
