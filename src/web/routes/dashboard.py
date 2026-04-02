"""Dashboard route — pipeline overview."""
from __future__ import annotations

from fastapi import APIRouter, Request

from src.models.database import get_pipeline_stats
from src.web.app import templates

router = APIRouter()


@router.get("/")
async def dashboard(request: Request):
    """Render pipeline statistics dashboard."""
    stats = await get_pipeline_stats()
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "stats": stats,
        },
    )
