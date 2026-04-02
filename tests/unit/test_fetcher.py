"""
Ceal Phase 2: URL Fetcher Tests

Tests URL validation, HTML stripping, and error handling.
All HTTP requests are mocked — no live network calls.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.fetcher import fetch_job_description


class TestFetchJobDescription:
    """Tests for the URL-to-text fetcher."""

    @pytest.mark.asyncio
    async def test_fetch_rejects_file_scheme(self):
        """ValueError on file:// URLs."""
        with pytest.raises(ValueError, match="Only http and https"):
            await fetch_job_description("file:///etc/passwd")

    @pytest.mark.asyncio
    async def test_fetch_rejects_ftp_scheme(self):
        """ValueError on ftp:// URLs."""
        with pytest.raises(ValueError, match="Only http and https"):
            await fetch_job_description("ftp://example.com/job.txt")

    @pytest.mark.asyncio
    async def test_fetch_strips_html(self):
        """Mock httpx to return HTML, verify clean text output."""
        html = """
        <html>
        <head><style>body { color: red; }</style></head>
        <body>
            <nav>Menu</nav>
            <h1>Software Engineer</h1>
            <p>We need a <strong>Python</strong> developer with REST API experience.</p>
            <script>alert('hi')</script>
            <footer>Copyright 2026</footer>
        </body>
        </html>
        """
        mock_response = httpx.Response(
            status_code=200,
            text=html,
            request=httpx.Request("GET", "https://example.com/job"),
        )

        with patch("src.fetcher.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await fetch_job_description("https://example.com/job")

        assert "Software Engineer" in result
        assert "Python" in result
        assert "REST API" in result
        # Script, style, nav, footer should be stripped
        assert "alert" not in result
        assert "color: red" not in result
        assert "Menu" not in result
        assert "Copyright" not in result

    @pytest.mark.asyncio
    async def test_fetch_timeout(self):
        """Mock httpx to timeout, verify graceful error."""
        with patch("src.fetcher.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(httpx.TimeoutException):
                await fetch_job_description("https://example.com/slow-job")
