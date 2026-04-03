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

PROMPT_VERSION = "v1.1"

_METRIC_TOKEN_RE = re.compile(
    r"""
    \$?\d[\d,]*(?:\.\d+)?(?:\s*(?:million|billion|thousand)|[kmb])?%?\+?
    """,
    re.IGNORECASE | re.VERBOSE,
)
_WORD_RE = re.compile(r"[a-z0-9][a-z0-9/+-]*", re.IGNORECASE)
_STOP_WORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "by",
    "for",
    "from",
    "in",
    "into",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
    "using",
    "use",
    "used",
    "via",
    "through",
    "accomplished",
    "measured",
    "doing",
    "did",
    "this",
    "that",
}


def strip_code_fences(text: str) -> str:
    """Remove markdown code fences from LLM response."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def _normalize_metric_token(token: str) -> str:
    """Normalize numeric claims so '$12 million' and '$12M' compare equally."""
    cleaned = token.lower().replace(",", "").replace("+", "").strip()
    kind = "number"
    scale = "raw"

    if cleaned.startswith("$"):
        kind = "money"
        cleaned = cleaned[1:]
    if cleaned.endswith("%"):
        kind = "percent"
        cleaned = cleaned[:-1]

    scale_map = {
        "thousand": "k",
        "k": "k",
        "million": "m",
        "m": "m",
        "billion": "b",
        "b": "b",
    }
    for suffix, normalized in scale_map.items():
        if cleaned.endswith(suffix):
            scale = normalized
            cleaned = cleaned[: -len(suffix)]
            break

    numeric = re.sub(r"[^0-9.]", "", cleaned)
    return f"{kind}:{numeric}:{scale}"


def _extract_metric_tokens(text: str) -> set[str]:
    """Extract normalized numeric claims from free text."""
    return {
        _normalize_metric_token(match.group(0))
        for match in _METRIC_TOKEN_RE.finditer(text)
    }


def _normalize_anchor(token: str) -> str:
    """Normalize semantic anchor words for drift detection."""
    cleaned = token.lower().strip(".,:;()[]{}\"'")
    if len(cleaned) <= 3:
        return ""
    if cleaned.endswith("ies") and len(cleaned) > 4:
        cleaned = f"{cleaned[:-3]}y"
    elif cleaned.endswith("s") and len(cleaned) > 4:
        cleaned = cleaned[:-1]
    return cleaned


def _extract_anchor_tokens(text: str) -> set[str]:
    """Capture content words that should survive a faithful rewrite."""
    anchors: set[str] = set()
    for match in _WORD_RE.finditer(text.lower()):
        anchor = _normalize_anchor(match.group(0))
        if anchor and anchor not in _STOP_WORDS and not anchor.isdigit():
            anchors.add(anchor)
    return anchors


def _semantic_fidelity_issues(original_bullet: ParsedBullet, rewritten_text: str) -> list[str]:
    """Return falsification findings for one rewritten bullet."""
    issues: list[str] = []

    original_metrics = _extract_metric_tokens(original_bullet.original_text)
    rewritten_metrics = _extract_metric_tokens(rewritten_text)
    introduced_metrics = rewritten_metrics - original_metrics
    if introduced_metrics:
        issues.append(
            "introduced unseen numeric claim(s): "
            + ", ".join(sorted(introduced_metrics))
        )

    original_anchors = _extract_anchor_tokens(original_bullet.original_text)
    rewritten_anchors = _extract_anchor_tokens(rewritten_text)
    if original_anchors and not (original_anchors & rewritten_anchors):
        issues.append("semantic drift: rewrite dropped all source anchors")

    return issues


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
- Do NOT invent metrics, team sizes, dollar amounts, or technologies not present in the original bullet
- Preserve at least one concrete anchor from the original bullet (skill, metric, domain noun, or system)

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
        original_lookup = {bullet.original_text: bullet for bullet in original_bullets}

        results: list[TailoredBullet] = []
        for item in items:
            original_text = item["original"]
            source_bullet = original_lookup.get(original_text)
            if source_bullet is None:
                raise ValueError(
                    "Tailoring response referenced a bullet that was not in the request: "
                    f"{original_text!r}"
                )

            rewritten_text = item["rewritten_text"]
            semantic_issues = _semantic_fidelity_issues(source_bullet, rewritten_text)
            if semantic_issues:
                raise ValueError(
                    "Semantic fidelity check failed for bullet "
                    f"{original_text!r}: {'; '.join(semantic_issues)}"
                )

            text = rewritten_text.lower()
            # Don't trust the LLM's xyz_format claim — verify against actual text.
            # The model sometimes marks True when "by doing [Z]" is missing.
            xyz_claimed = item.get("xyz_format", False)
            xyz_verified = xyz_claimed and "measured by" in text and "by doing" in text

            results.append(TailoredBullet(
                original=original_text,
                rewritten_text=rewritten_text,
                xyz_format=xyz_verified,
                relevance_score=max(0.0, min(1.0, float(item.get("relevance_score", 0.5)))),
            ))

        return results
