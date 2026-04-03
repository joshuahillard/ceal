"""Integration tests for PDF export — file I/O and route roundtrips."""
from __future__ import annotations

import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.document.coverletter_pdf import generate_cover_letter_pdf
from src.document.models import CoverLetterData, ResumeData
from src.document.resume_pdf import generate_resume_pdf
from src.web.app import create_app


def _base_resume() -> ResumeData:
    return ResumeData(
        name="TEST USER",
        title_line="Test Title",
        contact="test@test.com",
        links="test.com",
        profile="Profile text for integration test with enough content.",
    )


def _base_cover_letter() -> CoverLetterData:
    return CoverLetterData(
        name="Test User",
        contact="test@test.com",
        date="April 3, 2026",
        company="TestCo",
        role="Engineer",
        paragraphs=["Para one.", "Para two.", "Para three."],
        signature_name="Test User",
        links="test.com",
    )


class TestFileRoundtrip:
    def test_resume_pdf_file_roundtrip(self):
        """Generate PDF -> write to temp file -> read back -> valid PDF header."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            result = generate_resume_pdf(_base_resume(), output_path=tmp_path)
            assert result.success
            assert os.path.exists(tmp_path)

            with open(tmp_path, "rb") as f:
                content = f.read()
            assert content[:5] == b"%PDF-"
            assert len(content) > 100
        finally:
            os.unlink(tmp_path)

    def test_coverletter_pdf_file_roundtrip(self):
        """Generate PDF -> write to temp file -> read back -> valid PDF header."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            result = generate_cover_letter_pdf(_base_cover_letter(), output_path=tmp_path)
            assert result.success
            assert os.path.exists(tmp_path)

            with open(tmp_path, "rb") as f:
                content = f.read()
            assert content[:5] == b"%PDF-"
            assert len(content) > 100
        finally:
            os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# Route Integration Tests
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    test_app = create_app()
    test_app.router.lifespan_context = None  # type: ignore[assignment]
    return test_app


@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=True) as ac:
        yield ac


def _make_mock_row(mapping: dict):
    """Create a mock SQLAlchemy row with _mapping attribute."""
    row = MagicMock()
    row._mapping = mapping
    return row


def _mock_session_with_row(row):
    """Create a mock async context manager for get_session that returns a session with a query result."""
    from contextlib import asynccontextmanager

    mock_result = MagicMock()
    mock_result.first.return_value = row

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    @asynccontextmanager
    async def fake_get_session():
        yield mock_session

    return fake_get_session


class TestExportRoutes:
    @pytest.mark.asyncio
    async def test_export_page_job_not_found(self, client):
        """GET /export/999 with non-existent job shows error."""
        ctx = _mock_session_with_row(None)

        with patch("src.web.routes.export.get_session", ctx):
            response = await client.get("/export/999")
        assert response.status_code == 200
        assert "not found" in response.text

    @pytest.mark.asyncio
    async def test_export_resume_returns_pdf(self, client):
        """POST /export/1/resume returns PDF content type."""
        mock_job = _make_mock_row({
            "id": 1,
            "title": "TSE",
            "company_name": "Stripe",
        })
        ctx = _mock_session_with_row(mock_job)

        with patch("src.web.routes.export.get_session", ctx):
            response = await client.post("/export/1/resume")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert response.content[:5] == b"%PDF-"

    @pytest.mark.asyncio
    async def test_export_cover_letter_returns_pdf(self, client):
        """POST /export/1/cover-letter with mocked Claude returns PDF."""
        mock_job = _make_mock_row({
            "id": 1,
            "title": "TSE",
            "company_name": "Stripe",
            "description_clean": "Looking for a TSE",
            "description_raw": None,
        })
        ctx = _mock_session_with_row(mock_job)
        mock_content = {"paragraphs": [f"Paragraph {i}" for i in range(5)]}

        with (
            patch("src.web.routes.export.get_session", ctx),
            patch(
                "src.web.routes.export.generate_cover_letter_content",
                new_callable=AsyncMock,
                return_value=mock_content,
            ),
        ):
            response = await client.post("/export/1/cover-letter")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert response.content[:5] == b"%PDF-"

    @pytest.mark.asyncio
    async def test_export_cover_letter_api_failure(self, client):
        """POST /export/1/cover-letter with API failure returns error."""
        mock_job = _make_mock_row({
            "id": 1,
            "title": "TSE",
            "company_name": "Stripe",
            "description_clean": "Looking for a TSE",
            "description_raw": None,
        })
        ctx = _mock_session_with_row(mock_job)

        with (
            patch("src.web.routes.export.get_session", ctx),
            patch(
                "src.web.routes.export.generate_cover_letter_content",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            response = await client.post("/export/1/cover-letter")

        assert response.status_code == 500
        assert b"failed" in response.content
