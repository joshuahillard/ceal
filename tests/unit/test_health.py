"""
Céal: Health Endpoint Tests

Tests the /health endpoint returns correct status and handles DB failures.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.web.app import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        """Health endpoint should return 200 even when DB is down."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "version" in data
        assert "database" in data

    def test_health_degraded_on_db_failure(self, client):
        """When DB is unreachable, status should be 'degraded'."""
        with patch("src.web.routes.health.get_session") as mock_session:
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(side_effect=ConnectionError("DB down"))
            mock_session.return_value = mock_ctx
            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "degraded"
