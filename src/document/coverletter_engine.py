"""
Ceal Cover Letter Content Engine — Claude API integration.

Generates 5-paragraph cover letter content using the same patterns
as the tailoring engine: httpx client, structured JSON prompting,
code fence stripping, fail-graceful.

Interview talking point:
    "The cover letter engine follows the same deterministic LLM pattern
    as the tailoring engine — structured JSON prompting with Pydantic
    validation and fail-graceful error handling."
"""
from __future__ import annotations

import json
import os
import re

import httpx
import structlog

logger = structlog.get_logger(__name__)

COVER_LETTER_PROMPT_VERSION = "v1.0"

_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?", re.MULTILINE)
_CODE_FENCE_END_RE = re.compile(r"\n?```\s*$")


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences from LLM response."""
    text = text.strip()
    text = _CODE_FENCE_RE.sub("", text)
    text = _CODE_FENCE_END_RE.sub("", text)
    return text.strip()


_SYSTEM_PROMPT = """You are a professional cover letter writer. Generate exactly 5 paragraphs \
for a cover letter following this arc:

1. HOOK: Company mission resonance + personal connection + why this role
2. TOAST CREDIBILITY: Quantified achievements ($12M save, 37% reduction, executive visibility, \
cross-functional governance)
3. BRIDGE (BUILDER): Technical projects (Ceal career signal engine, Moss Lane real estate platform), \
technical fluency, sprint management
4. DUAL PERSPECTIVE: Leadership + technical depth, rare combination for the role
5. CLOSE: Location/availability + call to action for conversation

Use **bold** markup for key metrics (e.g., **$12M**, **37%**).
Return ONLY a JSON object with this exact structure:
{"paragraphs": ["paragraph 1 text", "paragraph 2 text", "paragraph 3 text", \
"paragraph 4 text", "paragraph 5 text"]}

No markdown fences. No explanation. Just the JSON object."""

_PROFILE_CONTEXT = """Candidate Profile:
- Joshua Hillard, Technical Leader based in Boston, MA
- 10+ years in tech spanning payment processing, SaaS platforms, and cloud engineering
- At Toast: Saved $12M by identifying firmware defects in payment terminals, led 37% reduction \
in escalation resolution time, managed cross-functional programs across engineering and operations
- Independent projects: Ceal (AI-powered career signal engine using Claude API, ReportLab, FastAPI), \
Moss Lane (real estate listing platform with GCP deployment)
- Skills: Python, SQL, GCP, Docker, FastAPI, Pydantic, Claude API integration, CI/CD
- Leadership style: Combines technical depth with program management experience"""


async def generate_cover_letter_content(
    job_title: str,
    company_name: str,
    job_description: str,
    resume_profile: str = "",
    special_instructions: str = "",
) -> dict | None:
    """
    Generate cover letter content via Claude API.

    Args:
        job_title: Target role title.
        company_name: Target company name.
        job_description: Full job description text.
        resume_profile: Optional profile summary override.
        special_instructions: Optional role-specific customization.

    Returns:
        Dict with 'paragraphs' list on success, None on any failure.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("LLM_API_KEY")
    if not api_key:
        logger.warning("cover_letter_no_api_key")
        return None

    model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
    profile = resume_profile or _PROFILE_CONTEXT

    user_prompt = f"""Generate a cover letter for this role:

Company: {company_name}
Role: {job_title}

Job Description:
{job_description[:3000]}

{profile}

{f"Special Instructions: {special_instructions}" if special_instructions else ""}"""

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": 2048,
                    "system": _SYSTEM_PROMPT,
                    "messages": [
                        {"role": "user", "content": user_prompt},
                    ],
                },
            )
            response.raise_for_status()
            data = response.json()
            raw_text = data["content"][0]["text"]

    except Exception:
        logger.exception("cover_letter_api_error")
        return None

    return _parse_response(raw_text)


def _parse_response(raw_text: str) -> dict | None:
    """Parse and validate Claude's JSON response."""
    try:
        cleaned = _strip_code_fences(raw_text)
        result = json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        logger.warning("cover_letter_bad_json", raw=raw_text[:200])
        return None

    paragraphs = result.get("paragraphs")
    if not isinstance(paragraphs, list):
        logger.warning("cover_letter_missing_paragraphs")
        return None

    if len(paragraphs) < 3 or len(paragraphs) > 6:
        logger.warning("cover_letter_paragraph_count", count=len(paragraphs))
        return None

    if any(not isinstance(p, str) or not p.strip() for p in paragraphs):
        logger.warning("cover_letter_empty_paragraph")
        return None

    return {"paragraphs": paragraphs}
