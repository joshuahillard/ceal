"""
Ceal Resume PDF Generator — Brother Kit Rules design system.

Generates a single-page US Letter resume using ReportLab canvas API
with the exact color palette, typography, and spacing from Josh's
approved TPM prompt.

Interview talking point:
    "The PDF generator uses ReportLab canvas API for pixel-level control
    over the design system — fonts are committed to the repo for
    deterministic Docker builds with no runtime downloads."
"""
from __future__ import annotations

import io

import structlog
from reportlab.pdfgen import canvas as canvas_mod

from src.document.design_system import (
    ARCHIVO_BOLD,
    ARCHIVO_SEMIBOLD,
    INK,
    INTER_REGULAR,
    KIT_BLUE,
    NAVY,
    PAGE_HEIGHT,
    PAGE_WIDTH,
    RESUME_BODY_SIZE,
    RESUME_CONTACT_SIZE,
    RESUME_CONTENT_WIDTH,
    RESUME_HEADER_RULE_WIDTH,
    RESUME_JOB_TITLE_SIZE,
    RESUME_MARGIN_BOTTOM,
    RESUME_MARGIN_LEFT,
    RESUME_MARGIN_TOP,
    RESUME_NAME_SIZE,
    RESUME_SECTION_GAP,
    RESUME_SECTION_HEADER_SIZE,
    RESUME_SKILL_LABEL_SIZE,
    RESUME_TITLE_SIZE,
    SLATE,
)
from src.document.font_manager import register_fonts
from src.document.models import ExportResult, ResumeData
from src.document.rich_text import draw_bullet_rich, draw_rich_wrapped

logger = structlog.get_logger(__name__)

# Register fonts at import time (idempotent)
register_fonts()


def generate_resume_pdf(
    data: ResumeData,
    output_path: str | None = None,
) -> ExportResult:
    """
    Generate a single-page resume PDF.

    Args:
        data: Complete resume data contract.
        output_path: Optional file path to write PDF. Always returns bytes.

    Returns:
        ExportResult with file_bytes, overflow detection, and final_y.
    """
    try:
        buf = io.BytesIO()
        c = canvas_mod.Canvas(buf, pagesize=(PAGE_WIDTH, PAGE_HEIGHT))

        y = _draw_resume(c, data)

        c.save()
        pdf_bytes = buf.getvalue()

        overflow = y < RESUME_MARGIN_BOTTOM

        if output_path:
            with open(output_path, "wb") as f:
                f.write(pdf_bytes)

        if overflow:
            logger.warning("resume_overflow", final_y=y, margin=RESUME_MARGIN_BOTTOM)

        return ExportResult(
            success=True,
            file_path=output_path,
            file_bytes=pdf_bytes,
            final_y=y,
            overflow=overflow,
        )

    except Exception as exc:
        logger.exception("resume_pdf_error")
        return ExportResult(success=False, error=str(exc))


def _draw_resume(c, data: ResumeData) -> float:
    """Draw all resume sections. Returns final y position."""
    x_left = RESUME_MARGIN_LEFT
    x_center = PAGE_WIDTH / 2
    y = PAGE_HEIGHT - RESUME_MARGIN_TOP

    # -- Header --
    # Name (centered)
    c.setFont(ARCHIVO_BOLD, RESUME_NAME_SIZE)
    c.setFillColor(NAVY)
    c.drawCentredString(x_center, y, data.name)
    y -= RESUME_NAME_SIZE + 2

    # Title line (centered, Kit Blue)
    c.setFont(ARCHIVO_SEMIBOLD, RESUME_TITLE_SIZE)
    c.setFillColor(KIT_BLUE)
    c.drawCentredString(x_center, y, data.title_line)
    y -= RESUME_TITLE_SIZE + 2

    # Contact (centered, Slate)
    c.setFont(INTER_REGULAR, RESUME_CONTACT_SIZE)
    c.setFillColor(SLATE)
    c.drawCentredString(x_center, y, data.contact)
    y -= RESUME_CONTACT_SIZE + 1

    # Links (centered, Kit Blue)
    c.setFont(INTER_REGULAR, RESUME_CONTACT_SIZE)
    c.setFillColor(KIT_BLUE)
    c.drawCentredString(x_center, y, data.links)
    y -= RESUME_CONTACT_SIZE + RESUME_SECTION_GAP

    # -- Professional Profile --
    y = _draw_section_header(c, "PROFESSIONAL PROFILE", x_left, y)
    y = draw_rich_wrapped(
        c, data.profile, x_left, y, RESUME_CONTENT_WIDTH,
        justified=True,
    )
    y -= RESUME_SECTION_GAP

    # -- Ordered sections (experience / projects) --
    for section_key in data.section_order:
        if section_key == "experience" and data.experience:
            y = _draw_section_header(c, "PROFESSIONAL EXPERIENCE", x_left, y)
            for job in data.experience:
                y = _draw_job_block(c, job, x_left, y)
            y -= RESUME_SECTION_GAP * 0.5

        elif section_key == "projects" and data.projects:
            y = _draw_section_header(c, "INDEPENDENT PROJECTS", x_left, y)
            for proj in data.projects:
                y = _draw_project_block(c, proj, x_left, y)
            y -= RESUME_SECTION_GAP * 0.5

    # -- Skills --
    if data.skills:
        y = _draw_section_header(c, "TECHNICAL SKILLS", x_left, y)
        for skill in data.skills:
            y = _draw_skill_row(c, skill.label, skill.items, x_left, y)
        y -= RESUME_SECTION_GAP * 0.5

    # -- Certifications --
    if data.certifications:
        y = _draw_section_header(c, "CERTIFICATIONS", x_left, y)
        for cert in data.certifications:
            y = draw_bullet_rich(c, cert, x_left, y, RESUME_CONTENT_WIDTH)
            y -= 1
        y -= RESUME_SECTION_GAP * 0.5

    # -- Education --
    if data.education:
        y = _draw_section_header(c, "EDUCATION", x_left, y)
        for edu in data.education:
            y = draw_bullet_rich(c, edu, x_left, y, RESUME_CONTENT_WIDTH)
            y -= 1

    return y


def _draw_section_header(c, title: str, x: float, y: float) -> float:
    """
    Draw a section header with Kit Blue rule above.

    Returns y position for content below the header.

    Note: These specific offsets were debugged through 4 iterations
    in the POC. Do NOT change the math.
    """
    # Kit Blue rule at current y
    c.setStrokeColor(KIT_BLUE)
    c.setLineWidth(RESUME_HEADER_RULE_WIDTH)
    c.line(x, y, x + RESUME_CONTENT_WIDTH, y)

    # Header text baseline
    text_y = y - RESUME_SECTION_HEADER_SIZE * 1.1
    c.setFont(ARCHIVO_SEMIBOLD, RESUME_SECTION_HEADER_SIZE)
    c.setFillColor(NAVY)
    c.drawString(x, text_y, title)

    # Content starts below header
    return text_y - RESUME_SECTION_HEADER_SIZE * 0.9


def _draw_job_block(c, job, x: float, y: float) -> float:
    """Draw a job experience block."""
    # Line 1: Title, Company (Archivo-SemiBold, Ink)
    c.setFont(ARCHIVO_SEMIBOLD, RESUME_JOB_TITLE_SIZE)
    c.setFillColor(INK)
    c.drawString(x, y, f"{job.title}, {job.company}")
    y -= RESUME_JOB_TITLE_SIZE + 1

    # Line 2: Location | Dates (Inter, Slate)
    c.setFont(INTER_REGULAR, RESUME_BODY_SIZE)
    c.setFillColor(SLATE)
    c.drawString(x, y, f"{job.location} | {job.dates}")
    y -= RESUME_BODY_SIZE + 2

    # Bullets
    for bullet in job.bullets:
        y = draw_bullet_rich(c, bullet, x, y, RESUME_CONTENT_WIDTH)
        y -= 1

    y -= 3  # gap between job blocks
    return y


def _draw_project_block(c, proj, x: float, y: float) -> float:
    """Draw a project block."""
    # Line 1: Project name (Archivo-SemiBold, Ink)
    c.setFont(ARCHIVO_SEMIBOLD, RESUME_JOB_TITLE_SIZE)
    c.setFillColor(INK)
    c.drawString(x, y, proj.name)
    y -= RESUME_JOB_TITLE_SIZE + 1

    # Line 2: Tech | Dates (Inter, Slate)
    c.setFont(INTER_REGULAR, RESUME_BODY_SIZE)
    c.setFillColor(SLATE)
    c.drawString(x, y, f"{proj.tech} | {proj.dates}")
    y -= RESUME_BODY_SIZE + 2

    # Bullets
    for bullet in proj.bullets:
        y = draw_bullet_rich(c, bullet, x, y, RESUME_CONTENT_WIDTH)
        y -= 1

    y -= 3
    return y


def _draw_skill_row(
    c, label: str, items: str, x: float, y: float,
) -> float:
    """Draw a skill category as bullet + bold label + items with wrapping."""
    text = f"**{label}:** {items}"
    y = draw_bullet_rich(
        c, text, x, y, RESUME_CONTENT_WIDTH,
        base_size=RESUME_SKILL_LABEL_SIZE,
    )
    y -= 1
    return y
