"""Job listings route with tier/score filtering."""
from __future__ import annotations

from fastapi import APIRouter, Query, Request

from src.models.database import get_top_matches
from src.web.app import templates

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/")
async def job_list(
    request: Request,
    min_score: float = Query(0.3, ge=0.0, le=1.0, description="Minimum match score"),
    tier: str | None = Query(None, description="Filter by company tier"),
    limit: int = Query(50, ge=1, le=200, description="Max results"),
):
    """Render filtered job listings."""
    # HTML select sends tier="" for "All" — treat empty string as None
    tier_int = int(tier) if tier and tier.strip() else None
    jobs = await get_top_matches(min_score=min_score, tier=tier_int, limit=limit)
    return templates.TemplateResponse(
        "jobs.html",
        {
            "request": request,
            "jobs": jobs,
            "filters": {
                "min_score": min_score,
                "tier": tier_int,
                "limit": limit,
            },
        },
    )
