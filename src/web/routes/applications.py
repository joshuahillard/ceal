"""Application tracking CRM routes — Kanban board + status transitions."""
from __future__ import annotations

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import RedirectResponse

from src.models.database import (
    get_application_summary,
    get_jobs_by_status,
    get_stale_applications,
    update_job_status,
)
from src.web.app import templates

router = APIRouter(prefix="/applications", tags=["applications"])


@router.get("/")
async def kanban_board(request: Request):
    """Render the Kanban board with jobs grouped by status."""
    summary = await get_application_summary()

    # Fetch jobs for each active column
    columns = {}
    for status in ["scraped", "ranked", "applied", "responded", "interviewing", "offer", "rejected", "archived"]:
        if summary.get(status, 0) > 0:
            columns[status] = await get_jobs_by_status(status, limit=50)
        else:
            columns[status] = []

    stale = await get_stale_applications(days=7)

    return templates.TemplateResponse(
        "applications.html",
        {
            "request": request,
            "summary": summary,
            "columns": columns,
            "stale_jobs": stale,
            "stale_count": len(stale),
        },
    )


@router.post("/{job_id}/status")
async def update_status(
    request: Request,
    job_id: int,
    new_status: str = Form(...),
):
    """Transition a job to a new status."""
    try:
        await update_job_status(job_id, new_status)
        return RedirectResponse(url="/applications", status_code=303)
    except ValueError as e:
        summary = await get_application_summary()
        columns = {}
        for status in ["scraped", "ranked", "applied", "responded", "interviewing", "offer", "rejected", "archived"]:
            columns[status] = await get_jobs_by_status(status, limit=50) if summary.get(status, 0) > 0 else []
        stale = await get_stale_applications(days=7)

        return templates.TemplateResponse(
            "applications.html",
            {
                "request": request,
                "summary": summary,
                "columns": columns,
                "stale_jobs": stale,
                "stale_count": len(stale),
                "error": str(e),
            },
        )


@router.get("/reminders")
async def reminders(
    request: Request,
    days: int = Query(7, ge=1, le=30, description="Days before flagging as stale"),
):
    """Show stale applications needing follow-up."""
    stale = await get_stale_applications(days=days)
    return templates.TemplateResponse(
        "reminders.html",
        {
            "request": request,
            "stale_jobs": stale,
            "days_threshold": days,
        },
    )
