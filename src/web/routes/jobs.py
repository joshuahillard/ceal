"""Job listings route with live refresh, safe filters, and resilient fallback."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx
import structlog
from fastapi import APIRouter, Request

from src.models.database import (
    assign_company_tiers,
    get_job_board_listings,
    get_jobs_by_ids,
    update_job_ranking,
    upsert_job,
)
from src.normalizer.pipeline import normalize_job
from src.ranker.llm_ranker import LLMRanker
from src.scrapers.linkedin import LinkedInScraper
from src.web.app import templates

router = APIRouter(prefix="/jobs", tags=["jobs"])
logger = structlog.get_logger(__name__)

DEFAULT_JOB_QUERY = "Technical Solutions Engineer"
DEFAULT_JOB_LOCATION = "Boston, MA"
DEFAULT_JOB_LIMIT = 25
LIVE_SOURCE_LABEL = "LinkedIn"
NO_LLM_KEY_WARNING = "Live refresh succeeded, but match scoring is unavailable because no LLM API key is configured."
INVALID_LLM_KEY_WARNING = (
    "Live refresh succeeded, but match scoring is unavailable because the configured LLM API key "
    "was rejected by Anthropic. Update the key and restart the app to re-enable scoring."
)
PARTIAL_RANK_WARNING = (
    "Live refresh succeeded, but some jobs could not be ranked. Unranked jobs are shown with pending scores."
)

_INVALID_LLM_API_KEY: str | None = None


@router.get("")
@router.get("/")
async def job_list(request: Request):
    """Render the live jobs page using the current search query and location."""
    filters = _parse_jobs_filters(request)
    jobs, refresh = await _load_jobs_page(**filters)

    return templates.TemplateResponse(
        request,
        "jobs.html",
        context={
            "jobs": jobs,
            "filters": filters,
            "refresh": refresh,
        },
    )


def _parse_jobs_filters(request: Request) -> dict[str, Any]:
    """Safely parse query params so empty form values never 422 the Jobs page."""
    params = request.query_params

    return {
        "query": _parse_text_param(params.get("query"), DEFAULT_JOB_QUERY),
        "location": _parse_text_param(params.get("location"), DEFAULT_JOB_LOCATION),
        "min_score": _parse_float_param(params.get("min_score"), default=0.3, min_value=0.0, max_value=1.0),
        "tier": _parse_int_param(params.get("tier"), default=None, min_value=1, max_value=3),
        "limit": _parse_int_param(params.get("limit"), default=DEFAULT_JOB_LIMIT, min_value=1, max_value=200),
    }


def _parse_text_param(raw_value: str | None, default: str) -> str:
    value = (raw_value or "").strip()
    return value or default


def _parse_int_param(
    raw_value: str | None,
    *,
    default: int | None,
    min_value: int,
    max_value: int,
) -> int | None:
    value = (raw_value or "").strip()
    if not value:
        return default

    try:
        parsed = int(value)
    except ValueError:
        return default

    return min(max(parsed, min_value), max_value)


def _parse_float_param(
    raw_value: str | None,
    *,
    default: float,
    min_value: float,
    max_value: float,
) -> float:
    value = (raw_value or "").strip()
    if not value:
        return default

    try:
        parsed = float(value)
    except ValueError:
        return default

    return min(max(parsed, min_value), max_value)


def _resolve_llm_api_key() -> tuple[str | None, str | None]:
    """Return the active Anthropic-compatible key, or a user-facing warning if scoring is disabled."""
    api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("LLM_API_KEY")
    if not api_key:
        return None, NO_LLM_KEY_WARNING

    if _INVALID_LLM_API_KEY and api_key == _INVALID_LLM_API_KEY:
        return None, INVALID_LLM_KEY_WARNING

    return api_key, None


def _is_unauthorized_llm_error(exc: Exception) -> bool:
    """Detect rejected Anthropic credentials so the Jobs page can fail open cleanly."""
    return isinstance(exc, httpx.HTTPStatusError) and exc.response is not None and exc.response.status_code in {401, 403}


async def _load_jobs_page(
    query: str,
    location: str,
    min_score: float,
    tier: int | None,
    limit: int,
) -> tuple[list[dict], dict[str, Any]]:
    """
    Refresh live jobs for the current search, then render only that current batch.

    If the live refresh fails, fall back to cached DB listings instead of raising.
    """
    refresh = await _refresh_live_jobs(query=query, location=location, limit=limit)

    if refresh["success"]:
        jobs = _filter_jobs(refresh["jobs"], min_score=min_score, tier=tier, limit=limit)
        refresh.pop("jobs", None)
        return jobs, refresh

    fallback_jobs = await get_job_board_listings(
        min_score=min_score,
        tier=tier,
        limit=limit,
        include_unranked=True,
    )
    refresh["fallback"] = True
    refresh.pop("jobs", None)
    return fallback_jobs, refresh


async def _refresh_live_jobs(query: str, location: str, limit: int) -> dict[str, Any]:
    """Run a best-effort live job search refresh for the Jobs page."""
    global _INVALID_LLM_API_KEY

    api_key, warning = _resolve_llm_api_key()
    llm_enabled = bool(api_key)
    job_ids: list[int] = []
    ranked_count = 0

    try:
        async with LinkedInScraper(
            concurrency=2,
            request_delay=1.5,
            fetch_descriptions=True,
        ) as scraper:
            raw_jobs = await scraper.scrape_jobs(
                query=query,
                location=location,
                max_results=limit,
            )

        normalized_jobs: list[dict[str, Any]] = []
        for raw_job in raw_jobs:
            try:
                clean_job, _skills = normalize_job(raw_job)
                job_id = await upsert_job(clean_job)
                job_ids.append(job_id)
                normalized_jobs.append(
                    {
                        "id": job_id,
                        "title": clean_job.title,
                        "company_name": clean_job.company_name,
                        "location": clean_job.location,
                        "remote_type": clean_job.remote_type.value,
                        "url": clean_job.url,
                        "description": clean_job.description_clean or clean_job.description_raw or "",
                    }
                )
            except Exception as exc:
                logger.warning(
                    "jobs_live_normalize_failed",
                    external_id=raw_job.external_id,
                    error=str(exc),
                )

        if normalized_jobs:
            await assign_company_tiers()

        if llm_enabled and normalized_jobs:
            resume_text = _load_resume_text()
            async with LLMRanker(api_key=api_key) as ranker:
                for job in normalized_jobs:
                    try:
                        result = await ranker.rank_job(
                            job_id=job["id"],
                            job_title=job["title"],
                            company_name=job["company_name"],
                            job_description=job["description"],
                            resume_text=resume_text,
                            location=job["location"],
                        )
                        await update_job_ranking(result)
                        ranked_count += 1
                    except Exception as exc:
                        if _is_unauthorized_llm_error(exc):
                            _INVALID_LLM_API_KEY = api_key
                            llm_enabled = False
                            warning = INVALID_LLM_KEY_WARNING
                            logger.warning(
                                "jobs_live_ranker_unauthorized",
                                query=query,
                                location=location,
                                status_code=exc.response.status_code,
                            )
                            break

                        logger.warning(
                            "jobs_live_rank_failed",
                            job_id=job["id"],
                            error=str(exc),
                        )

        jobs = await get_jobs_by_ids(job_ids)

        if warning is None and llm_enabled and ranked_count < len(normalized_jobs):
            warning = PARTIAL_RANK_WARNING

        logger.info(
            "jobs_live_refresh_complete",
            query=query,
            location=location,
            source=LIVE_SOURCE_LABEL,
            refreshed_count=len(jobs),
            ranked_count=ranked_count,
            llm_enabled=llm_enabled,
        )

        return {
            "attempted": True,
            "success": True,
            "fallback": False,
            "source_label": LIVE_SOURCE_LABEL,
            "query": query,
            "location": location,
            "llm_enabled": llm_enabled,
            "refreshed_count": len(jobs),
            "ranked_count": ranked_count,
            "warning": warning,
            "error": None,
            "jobs": jobs,
        }

    except Exception as exc:
        logger.warning(
            "jobs_live_refresh_failed",
            query=query,
            location=location,
            source=LIVE_SOURCE_LABEL,
            error=str(exc),
        )
        return {
            "attempted": True,
            "success": False,
            "fallback": False,
            "source_label": LIVE_SOURCE_LABEL,
            "query": query,
            "location": location,
            "llm_enabled": llm_enabled,
            "refreshed_count": 0,
            "ranked_count": 0,
            "warning": None,
            "error": str(exc),
            "jobs": [],
        }


def _load_resume_text() -> str:
    """Load the real resume text for live job ranking, with a safe fallback."""
    resume_path = Path("data") / "resume.txt"
    if resume_path.exists():
        return resume_path.read_text()

    from src.main import _get_default_resume_text

    return _get_default_resume_text()


def _filter_jobs(
    jobs: list[dict],
    *,
    min_score: float,
    tier: int | None,
    limit: int,
) -> list[dict]:
    """Apply UI filters to the current live batch without crashing on missing scores."""
    filtered: list[dict] = []

    for job in jobs:
        job_tier = job.get("company_tier")
        score = job.get("match_score")

        if tier is not None and job_tier != tier:
            continue
        if score is not None and score < min_score:
            continue

        filtered.append(job)

    filtered.sort(
        key=lambda job: (
            job.get("match_score") is None,
            -(job.get("match_score") or 0.0),
            job.get("company_tier") is None,
            job.get("company_tier") or 99,
            job.get("company_name") or "",
        )
    )
    return filtered[:limit]
