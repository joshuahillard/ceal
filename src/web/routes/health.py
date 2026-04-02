"""Health check endpoint for Docker and Cloud Run."""

import importlib.metadata
import logging

from fastapi import APIRouter

from src.models.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """
    Health check endpoint.

    Returns service status, version, and database connectivity.
    Used by:
    - Docker HEALTHCHECK directive
    - GCP Cloud Run HTTP health checks
    - Load balancers and monitoring systems

    Interview point: "Health endpoints are the foundation of
    observable systems — they enable zero-downtime deployments
    and automated rollback on Cloud Run."
    """
    status = {"status": "ok", "service": "ceal", "version": _get_version()}

    # Check database connectivity
    try:
        async with get_session() as session:
            result = await session.execute(__import__("sqlalchemy").text("SELECT 1"))
            result.scalar()
        status["database"] = "connected"
    except Exception as e:
        logger.warning("health_check_db_failed", extra={"error": str(e)})
        status["database"] = "disconnected"
        status["status"] = "degraded"

    return status


def _get_version() -> str:
    """Get version from package metadata or fallback."""
    try:
        return importlib.metadata.version("ceal")
    except importlib.metadata.PackageNotFoundError:
        return "dev"
