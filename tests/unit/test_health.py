"""Tests for the health check endpoint."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.web.app import create_app


@pytest.mark.asyncio
async def test_health_returns_200():
    """Health endpoint returns 200 with expected fields."""
    app = create_app()
    with patch("src.web.routes.health.get_session") as mock_session:
        mock_ctx = AsyncMock()
        mock_result = AsyncMock()
        mock_result.scalar.return_value = 1
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_result)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        # get_session is a context manager
        mock_session.return_value = mock_ctx

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "ceal"
    assert "version" in data
    assert "database" in data


@pytest.mark.asyncio
async def test_health_degraded_on_db_failure():
    """Health endpoint returns degraded when DB is unreachable."""
    app = create_app()
    with patch("src.web.routes.health.get_session") as mock_session:
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(side_effect=Exception("DB down"))
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session.return_value = mock_ctx

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["database"] == "disconnected"
