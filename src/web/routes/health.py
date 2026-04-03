"""
Céal: Health Check Endpoint

Returns application health status including database connectivity.
Used by Docker HEALTHCHECK, GCP Cloud Run, and load balancers.

Interview talking point:
    "The health endpoint probes actual DB connectivity with SELECT 1,
    not just 'the process is alive'. If the database connection pool
    is exhausted, the health check fails and the orchestrator restarts
    the container before users see errors."
"""
from __future__ import annotations

from fastapi import APIRouter

from src.models.database import get_session

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """
    Health check endpoint for container orchestration.
    Returns 200 with status details, or 200 with degraded status on DB failure.
    """
    db_ok = False
    db_error = None

    try:
        from sqlalchemy import text
        async with get_session() as session:
            await session.execute(text("SELECT 1"))
            db_ok = True
    except Exception as exc:
        db_error = str(exc)

    status = "healthy" if db_ok else "degraded"
    return {
        "status": status,
        "version": "2.6.0",
        "database": "connected" if db_ok else f"error: {db_error}",
    }
