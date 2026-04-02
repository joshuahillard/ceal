"""Auto-apply approval queue routes."""
from __future__ import annotations

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import RedirectResponse

from src.apply.prefill import PreFillEngine
from src.models.database import (
    create_application,
    get_application,
    get_application_stats,
    get_approval_queue,
    update_application_status,
)
from src.web.app import templates

router = APIRouter(prefix="/apply", tags=["apply"])


@router.get("/")
async def approval_queue(request: Request, status: str = Query("draft")):
    """Render the approval queue showing applications awaiting review."""
    queue = await get_approval_queue(status=status)
    stats = await get_application_stats()
    return templates.TemplateResponse(
        "approval_queue.html",
        {
            "request": request,
            "queue": queue,
            "stats": stats,
            "current_filter": status,
        },
    )


@router.post("/prefill/{job_id}")
async def prefill_job(request: Request, job_id: int):
    """Pre-fill an application for a specific job and redirect to review."""
    engine = PreFillEngine()
    app_create = engine.prefill_application(job_id=job_id)
    app_id = await create_application(app_create)
    return RedirectResponse(url=f"/apply/{app_id}", status_code=303)


@router.get("/{app_id}")
async def review_application(request: Request, app_id: int):
    """Render the application review page with pre-filled fields."""
    application = await get_application(app_id)
    if not application:
        return RedirectResponse(url="/apply", status_code=303)
    return templates.TemplateResponse(
        "application_review.html",
        {
            "request": request,
            "application": application,
        },
    )


@router.post("/{app_id}/status")
async def update_status(request: Request, app_id: int, new_status: str = Form(...)):
    """Transition an application status (approve, submit, withdraw, etc.)."""
    try:
        await update_application_status(app_id, new_status)
        return RedirectResponse(url="/apply", status_code=303)
    except ValueError as e:
        application = await get_application(app_id)
        return templates.TemplateResponse(
            "application_review.html",
            {
                "request": request,
                "application": application,
                "error": str(e),
            },
        )
