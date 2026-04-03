"""
Ceal Cover Letter PDF Generator — Brother Kit Rules design system.

Generates a single-page US Letter cover letter using ReportLab canvas
with justified paragraphs and the exact Brother Kit design system.
"""
from __future__ import annotations

import io

import structlog
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas as canvas_mod

from src.document.design_system import (
    ARCHIVO_BOLD,
    ARCHIVO_SEMIBOLD,
    CL_BODY_SIZE,
    CL_CONTACT_SIZE,
    CL_CONTENT_WIDTH,
    CL_DATE_SIZE,
    CL_DIVIDER_WIDTH,
    CL_LINE_SPACING,
    CL_LINK_SIZE,
    CL_MARGIN_BOTTOM,
    CL_MARGIN_LEFT,
    CL_NAME_SIZE,
    CL_PARAGRAPH_GAP,
    CL_SALUTATION_SIZE,
    CL_SIGNATURE_SIZE,
    INK,
    INTER_MEDIUM,
    INTER_REGULAR,
    KIT_BLUE,
    NAVY,
    PAGE_HEIGHT,
    PAGE_WIDTH,
    SLATE,
)
from src.document.font_manager import register_fonts
from src.document.models import CoverLetterData, ExportResult

logger = structlog.get_logger(__name__)

register_fonts()


def generate_cover_letter_pdf(
    data: CoverLetterData,
    output_path: str | None = None,
) -> ExportResult:
    """
    Generate a single-page cover letter PDF.

    Args:
        data: Complete cover letter data contract.
        output_path: Optional file path to write PDF. Always returns bytes.

    Returns:
        ExportResult with file_bytes, overflow detection, and final_y.
    """
    try:
        buf = io.BytesIO()
        c = canvas_mod.Canvas(buf, pagesize=(PAGE_WIDTH, PAGE_HEIGHT))

        y = _draw_cover_letter(c, data)

        c.save()
        pdf_bytes = buf.getvalue()

        overflow = y < CL_MARGIN_BOTTOM

        if output_path:
            with open(output_path, "wb") as f:
                f.write(pdf_bytes)

        if overflow:
            logger.warning("coverletter_overflow", final_y=y, margin=CL_MARGIN_BOTTOM)

        return ExportResult(
            success=True,
            file_path=output_path,
            file_bytes=pdf_bytes,
            final_y=y,
            overflow=overflow,
        )

    except Exception as exc:
        logger.exception("coverletter_pdf_error")
        return ExportResult(success=False, error=str(exc))


def _draw_cover_letter(c, data: CoverLetterData) -> float:
    """Draw all cover letter sections. Returns final y position."""
    x_left = CL_MARGIN_LEFT
    y = PAGE_HEIGHT - CL_MARGIN_LEFT  # top margin from spec

    # -- Name (left-aligned, Archivo-Bold 18pt, Navy) --
    c.setFont(ARCHIVO_BOLD, CL_NAME_SIZE)
    c.setFillColor(NAVY)
    c.drawString(x_left, y, data.name)
    y -= CL_NAME_SIZE + 3

    # -- Contact (left-aligned, Inter 8.5pt, Slate) --
    c.setFont(INTER_REGULAR, CL_CONTACT_SIZE)
    c.setFillColor(SLATE)
    c.drawString(x_left, y, data.contact)
    y -= CL_CONTACT_SIZE + 6

    # -- Kit Blue divider --
    c.setStrokeColor(KIT_BLUE)
    c.setLineWidth(CL_DIVIDER_WIDTH)
    c.line(x_left, y, x_left + CL_CONTENT_WIDTH, y)
    y -= 12

    # -- Date (Inter 9pt, Slate) --
    c.setFont(INTER_REGULAR, CL_DATE_SIZE)
    c.setFillColor(SLATE)
    c.drawString(x_left, y, data.date)
    y -= CL_DATE_SIZE + 4

    # -- Company + Role (Inter 9pt, Ink) --
    c.setFont(INTER_REGULAR, CL_DATE_SIZE)
    c.setFillColor(INK)
    c.drawString(x_left, y, f"{data.company} — {data.role}")
    y -= CL_DATE_SIZE + 10

    # -- Salutation (Inter-Medium 9.5pt, Navy) --
    c.setFont(INTER_MEDIUM, CL_SALUTATION_SIZE)
    c.setFillColor(NAVY)
    c.drawString(x_left, y, data.salutation)
    y -= CL_SALUTATION_SIZE + 8

    # -- Body paragraphs (Inter 9.2pt, Ink, justified, 1.45x line spacing) --
    for para in data.paragraphs:
        y = _draw_justified_paragraph(c, para, x_left, y)
        y -= CL_PARAGRAPH_GAP

    # -- Closing (Inter 9.2pt, Ink) --
    c.setFont(INTER_REGULAR, CL_BODY_SIZE)
    c.setFillColor(INK)
    c.drawString(x_left, y, data.closing)
    y -= CL_BODY_SIZE + 8

    # -- Signature (Archivo-SemiBold 10pt, Navy) --
    c.setFont(ARCHIVO_SEMIBOLD, CL_SIGNATURE_SIZE)
    c.setFillColor(NAVY)
    c.drawString(x_left, y, data.signature_name)
    y -= CL_SIGNATURE_SIZE + 6

    # -- Links (Inter 8.5pt, Kit Blue) --
    c.setFont(INTER_REGULAR, CL_LINK_SIZE)
    c.setFillColor(KIT_BLUE)
    c.drawString(x_left, y, data.links)
    y -= CL_LINK_SIZE

    return y


def _draw_justified_paragraph(c, text: str, x: float, y: float) -> float:
    """Draw a justified paragraph with word wrapping."""
    words = text.split()
    if not words:
        return y

    font = INTER_REGULAR
    size = CL_BODY_SIZE
    line_height = size * CL_LINE_SPACING
    space_width = pdfmetrics.stringWidth(" ", font, size)

    c.setFont(font, size)
    c.setFillColor(INK)

    lines: list[list[str]] = []
    current_line: list[str] = []
    current_width = 0.0

    for word in words:
        w = pdfmetrics.stringWidth(word, font, size)
        needed = w if not current_line else w + space_width

        if current_line and current_width + needed > CL_CONTENT_WIDTH:
            lines.append(current_line)
            current_line = [word]
            current_width = w
        else:
            current_line.append(word)
            current_width += needed

    if current_line:
        lines.append(current_line)

    for i, line in enumerate(lines):
        is_last = (i == len(lines) - 1)
        total_text = sum(pdfmetrics.stringWidth(w, font, size) for w in line)
        gap_count = len(line) - 1

        if not is_last and gap_count > 0:
            gap = (CL_CONTENT_WIDTH - total_text) / gap_count
            gap = min(gap, space_width * 4)
        else:
            gap = space_width

        cx = x
        for word in line:
            c.drawString(cx, y, word)
            cx += pdfmetrics.stringWidth(word, font, size) + gap

        y -= line_height

    return y
