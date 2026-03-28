"""
Céal: LLM-based Job Ranker (Consumer Stage)

Scores job listings against Josh's resume using Claude as the
evaluation engine. Each job gets a match_score (0.0-1.0) and
a natural-language reasoning explaining why.

Architecture:
  - The ranker reads unranked jobs from the database
  - For each job, it constructs a prompt with the job description
    and the resume profile
  - Claude evaluates the fit and returns structured JSON
  - The result is validated through Pydantic (RankedResult)
    before being written back to the database

Interview point: "I used an LLM for ranking instead of TF-IDF or
keyword counting because job-resume matching is fundamentally a
semantic problem. 'Payment processing experience' on my resume
should match 'FinTech background required' in a listing, and
only an LLM understands that relationship. The LLM output is
validated through a Pydantic schema so malformed responses are
caught before they corrupt the database."

Why Claude specifically? The Anthropic API returns structured,
instruction-following responses that parse cleanly into JSON.
The architecture supports swapping in any LLM — the ranker
takes an API key and model name from environment config.
"""

from __future__ import annotations

import json
import os
from typing import Optional

import httpx
import structlog

from src.models.entities import RankedResult

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "claude-sonnet-4-20250514"
DEFAULT_MAX_TOKENS = 1024
RANKER_VERSION = "v1.0-ceal"


# ---------------------------------------------------------------------------
# Ranking Prompt
# ---------------------------------------------------------------------------
# This prompt is the core intellectual property of the ranker. It's
# designed to produce consistent, structured JSON output that maps
# directly to our RankedResult Pydantic model.

RANKING_PROMPT_TEMPLATE = """You are evaluating how well a job listing matches a candidate's resume.

## Candidate Resume
{resume_text}

## Job Listing
**Title:** {job_title}
**Company:** {company_name}
**Location:** {location}
**Description:**
{job_description}

## Extracted Skills from Listing
Required: {required_skills}
Nice-to-have: {nice_to_have_skills}

## Instructions
Score this job on a scale of 0.0 to 1.0 based on how well the candidate's experience matches the requirements. Consider:

1. **Direct skill matches** — Does the candidate have the required technical skills?
2. **Domain relevance** — Does the candidate's industry experience (FinTech, POS, payments) align?
3. **Seniority fit** — Is the role's level appropriate for the candidate's experience?
4. **Growth trajectory** — Does the candidate's career progression support this role?

Respond with ONLY valid JSON in this exact format:
{{
  "match_score": <float 0.0-1.0>,
  "match_reasoning": "<2-3 sentence explanation of the score>",
  "skills_matched": ["<skill1>", "<skill2>"],
  "skills_missing": ["<skill1>", "<skill2>"]
}}"""


# ---------------------------------------------------------------------------
# LLM Ranker
# ---------------------------------------------------------------------------

class LLMRanker:
    """
    Ranks job listings against a resume profile using an LLM.

    Usage:
        ranker = LLMRanker(api_key="sk-...")
        result = await ranker.rank_job(
            job_id=42,
            job_title="Technical Solutions Engineer",
            company_name="Stripe",
            job_description="As a TSE at Stripe...",
            required_skills=["Python", "SQL"],
            nice_to_have_skills=["Docker"],
            resume_text="Josh Hillard — 6+ years at Toast...",
        )
        # result is a validated RankedResult

    Interview point: "The ranker is stateless — it takes all inputs
    as parameters and returns a Pydantic-validated result. This means
    it's trivially testable with mock responses and can be parallelized
    without shared state."
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ):
        self.api_key = api_key or os.getenv("LLM_API_KEY", "")
        self.model = model
        self.max_tokens = max_tokens
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "LLMRanker":
        self._client = httpx.AsyncClient(
            timeout=60.0,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
        )
        return self

    async def __aexit__(self, *args) -> None:
        if self._client:
            await self._client.aclose()

    async def rank_job(
        self,
        job_id: int,
        job_title: str,
        company_name: str,
        job_description: str,
        resume_text: str,
        location: Optional[str] = None,
        required_skills: Optional[list[str]] = None,
        nice_to_have_skills: Optional[list[str]] = None,
    ) -> RankedResult:
        """
        Score a single job listing against the resume.

        Returns a validated RankedResult. Raises on API failure
        or unparseable response (the pipeline handles the error).
        """
        prompt = RANKING_PROMPT_TEMPLATE.format(
            resume_text=resume_text,
            job_title=job_title,
            company_name=company_name,
            location=location or "Not specified",
            job_description=job_description[:4000],  # Truncate long descriptions
            required_skills=", ".join(required_skills or []) or "Not specified",
            nice_to_have_skills=", ".join(nice_to_have_skills or []) or "Not specified",
        )

        raw_response = await self._call_llm(prompt)
        result = self._parse_response(raw_response, job_id)

        logger.info(
            "job_ranked",
            job_id=job_id,
            score=result.match_score,
            skills_matched=len(result.skills_matched),
            skills_missing=len(result.skills_missing),
        )

        return result

    async def _call_llm(self, prompt: str) -> str:
        """
        Call the Anthropic Messages API.

        Interview point: "I call the API directly with httpx rather
        than using the anthropic SDK because it keeps the dependency
        tree small and gives me full control over retry logic and
        timeout handling. The SDK is a convenience wrapper — for a
        single-endpoint integration, raw HTTP is simpler."
        """
        if not self._client:
            raise RuntimeError("Ranker not initialized. Use 'async with' context manager.")

        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [
                {"role": "user", "content": prompt}
            ],
        }

        response = await self._client.post(
            "https://api.anthropic.com/v1/messages",
            json=payload,
        )
        response.raise_for_status()

        data = response.json()
        # Extract text from Anthropic's response format
        content_blocks = data.get("content", [])
        if not content_blocks:
            raise ValueError("Empty response from LLM API")

        return content_blocks[0].get("text", "")

    def _parse_response(self, raw: str, job_id: int) -> RankedResult:
        """
        Parse LLM response JSON into a validated RankedResult.

        Handles common LLM quirks:
          - Markdown code fences around JSON
          - Extra whitespace or newlines
          - Missing optional fields

        Interview point: "I validate LLM output through the same
        Pydantic schema used everywhere else. If the model returns
        a score of 1.5 or omits the reasoning, Pydantic catches it
        before it hits the database. You can't trust LLM output to
        be well-formed — you have to validate it."
        """
        # Strip markdown code fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            # Remove ```json\n...\n```
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"LLM returned invalid JSON for job {job_id}: {e}\n"
                f"Raw response: {raw[:500]}"
            )

        # Build RankedResult with Pydantic validation
        return RankedResult(
            job_id=job_id,
            match_score=parsed.get("match_score", 0.0),
            match_reasoning=parsed.get("match_reasoning", "No reasoning provided"),
            skills_matched=parsed.get("skills_matched", []),
            skills_missing=parsed.get("skills_missing", []),
            rank_model_version=f"{RANKER_VERSION}-{self.model}",
        )


# ---------------------------------------------------------------------------
# Convenience: rank from database records
# ---------------------------------------------------------------------------

async def rank_unranked_jobs(
    resume_text: str,
    api_key: Optional[str] = None,
    limit: int = 20,
) -> list[RankedResult]:
    """
    High-level function: fetch unranked jobs from DB, score them, update DB.

    This is what the pipeline orchestrator calls. It handles:
      1. Fetching unranked jobs from the database
      2. Ranking each one via the LLM
      3. Writing results back to the database
      4. Returning results for logging/display

    Interview point: "The ranker processes jobs in serial to respect
    API rate limits. In a production system with higher throughput needs,
    I'd use asyncio.Semaphore to control concurrent API calls — the same
    pattern the scraper uses for HTTP requests."
    """
    from src.models.database import get_unranked_jobs, update_job_ranking

    unranked = await get_unranked_jobs(limit=limit)
    if not unranked:
        logger.info("no_unranked_jobs")
        return []

    results: list[RankedResult] = []

    async with LLMRanker(api_key=api_key) as ranker:
        for job in unranked:
            try:
                result = await ranker.rank_job(
                    job_id=job["id"],
                    job_title=job["title"],
                    company_name=job["company_name"],
                    job_description=job.get("description_clean") or job.get("description_raw") or "",
                    resume_text=resume_text,
                    location=job.get("location"),
                )
                await update_job_ranking(result)
                results.append(result)

            except Exception as exc:
                logger.error(
                    "ranking_failed",
                    job_id=job["id"],
                    error=str(exc),
                )

    logger.info(
        "ranking_complete",
        total=len(unranked),
        ranked=len(results),
        failed=len(unranked) - len(results),
    )

    return results
