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
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        context={
            "stats": stats,
            "app_summary": app_summary,
            "stale_count": len(stale),
            "apply_stats": apply_stats,
        },
    )
