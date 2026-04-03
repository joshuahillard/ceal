"""Dashboard route — pipeline overview."""
from __future__ import annotations

from fastapi import APIRouter, Request

from src.models.database import (
    get_application_stats,
    get_application_summary,
    get_pipeline_stats,
    get_stale_applications,
)
from src.web.app import templates

router = APIRouter()


@router.get("/")
async def dashboard(request: Request):
    """Render pipeline statistics dashboard with CRM overview."""
    stats = await get_pipeline_stats()
    app_summary = await get_application_summary()
    stale = await get_stale_applications(days=7)
    apply_stats = await get_application_stats()
    regime_stats = await _get_regime_stats_safe()
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        context={
            "stats": stats,
            "app_summary": app_summary,
            "stale_count": len(stale),
            "apply_stats": apply_stats,
            "regime_stats": regime_stats,
        },
    )


async def _get_regime_stats_safe() -> dict:
    """Fetch regime stats with fail-safe for dashboard rendering."""
    try:
        from src.models.database import get_regime_stats, get_session
        async with get_session() as session:
            return await get_regime_stats(session)
    except Exception:
        return {
            "tier_1_count": 0,
            "tier_2_count": 0,
            "tier_3_count": 0,
            "unclassified_count": 0,
            "total_classified": 0,
        }
