"""PDF export routes — resume and cover letter generation."""
from __future__ import annotations

import io
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from src.document.coverletter_engine import generate_cover_letter_content
from src.document.coverletter_pdf import generate_cover_letter_pdf
from src.document.models import CoverLetterData, ResumeData
from src.document.resume_pdf import generate_resume_pdf
from src.models.database import get_session
from src.web.app import templates

router = APIRouter(prefix="/export", tags=["export"])


# ---------------------------------------------------------------------------
# Base resume template — Josh's standard resume data
# ---------------------------------------------------------------------------

def _get_base_resume_data() -> ResumeData:
    """Return Josh's standard resume as the base template."""
    return ResumeData(
        name="JOSHUA HILLARD",
        title_line="Technical Leader | Program Management & Cloud Engineering",
        contact="Boston, MA | (781) 308-0407 | joshua.hillard4@gmail.com",
        links="linkedin.com/in/joshua-hillard | github.com/joshuahillard",
        profile=(
            "Technical leader with 10+ years in tech spanning payment processing, "
            "SaaS platforms, and cloud engineering. At Toast, saved **$12M** by identifying "
            "firmware defects in payment terminals and led a **37%** reduction in escalation "
            "resolution time through cross-functional program governance. Combines deep "
            "technical fluency (Python, SQL, GCP, Docker) with executive-level program "
            "management to drive measurable business outcomes."
        ),
        experience=[],
        projects=[],
        skills=[],
        certifications=[],
        education=[],
        section_order=["experience", "projects"],
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/{job_id}")
async def export_page(request: Request, job_id: int):
    """Render export page with job details and generate buttons."""
    from sqlalchemy import text as sql_text

    async with get_session() as session:
        result = await session.execute(
            sql_text(
                "SELECT id, title, company_name, company_tier, match_score, "
                "description_clean, description_raw, url "
                "FROM job_listings WHERE id = :job_id"
            ),
            {"job_id": job_id},
        )
        job = result.first()

    if not job:
        return templates.TemplateResponse(
            request,
            "export.html",
            context={"job": None, "error": f"Job {job_id} not found."},
        )

    return templates.TemplateResponse(
        request,
        "export.html",
        context={"job": dict(job._mapping), "error": None},
    )


@router.post("/{job_id}/resume")
async def generate_resume(job_id: int):
    """Generate tailored resume PDF and return as download."""
    from sqlalchemy import text as sql_text

    async with get_session() as session:
        result = await session.execute(
            sql_text(
                "SELECT id, title, company_name FROM job_listings WHERE id = :job_id"
            ),
            {"job_id": job_id},
        )
        job = result.first()

    if not job:
        return StreamingResponse(
            io.BytesIO(b"Job not found"),
            status_code=404,
            media_type="text/plain",
        )

    job_dict = dict(job._mapping)
    data = _get_base_resume_data()
    export = generate_resume_pdf(data)

    if not export.success:
        return StreamingResponse(
            io.BytesIO(f"PDF generation failed: {export.error}".encode()),
            status_code=500,
            media_type="text/plain",
        )

    company = job_dict["company_name"].replace(" ", "_")
    title = job_dict["title"].replace(" ", "_")
    filename = f"{company}_{title}_Resume.pdf"

    return StreamingResponse(
        io.BytesIO(export.file_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{job_id}/cover-letter")
async def generate_cover_letter(job_id: int):
    """Generate cover letter PDF via Claude API and return as download."""
    from sqlalchemy import text as sql_text

    async with get_session() as session:
        result = await session.execute(
            sql_text(
                "SELECT id, title, company_name, description_clean, description_raw "
                "FROM job_listings WHERE id = :job_id"
            ),
            {"job_id": job_id},
        )
        job = result.first()

    if not job:
        return StreamingResponse(
            io.BytesIO(b"Job not found"),
            status_code=404,
            media_type="text/plain",
        )

    job_dict = dict(job._mapping)
    description = job_dict.get("description_clean") or job_dict.get("description_raw") or ""

    content = await generate_cover_letter_content(
        job_title=job_dict["title"],
        company_name=job_dict["company_name"],
        job_description=description,
    )

    if content is None:
        return StreamingResponse(
            io.BytesIO(b"Cover letter content generation failed. Check ANTHROPIC_API_KEY."),
            status_code=500,
            media_type="text/plain",
        )

    now = datetime.now(timezone.utc)
    cl_data = CoverLetterData(
        name="Joshua Hillard",
        contact="Boston, MA | (781) 308-0407 | joshua.hillard4@gmail.com",
        date=now.strftime("%B %d, %Y"),
        company=job_dict["company_name"],
        role=job_dict["title"],
        paragraphs=content["paragraphs"],
        signature_name="Joshua Hillard",
        links="linkedin.com/in/joshua-hillard | github.com/joshuahillard",
    )

    export = generate_cover_letter_pdf(cl_data)

    if not export.success:
        return StreamingResponse(
            io.BytesIO(f"PDF generation failed: {export.error}".encode()),
            status_code=500,
            media_type="text/plain",
        )

    company = job_dict["company_name"].replace(" ", "_")
    title = job_dict["title"].replace(" ", "_")
    filename = f"{company}_{title}_CoverLetter.pdf"

    return StreamingResponse(
        io.BytesIO(export.file_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
