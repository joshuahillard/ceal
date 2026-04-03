"""Unit tests for the cover letter PDF generator."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.document.coverletter_pdf import generate_cover_letter_pdf
from src.document.models import CoverLetterData


def _minimal_data() -> CoverLetterData:
    return CoverLetterData(
        name="Test User",
        contact="Boston, MA | test@test.com",
        date="April 3, 2026",
        company="Test Corp",
        role="Test Role",
        paragraphs=[
            "First paragraph with some content.",
            "Second paragraph with more content.",
            "Third paragraph closing thoughts.",
        ],
        signature_name="Test User",
        links="linkedin.com/test",
    )


def _five_paragraph_data() -> CoverLetterData:
    return CoverLetterData(
        name="Joshua Hillard",
        contact="Boston, MA | (781) 308-0407 | joshua.hillard4@gmail.com",
        date="April 3, 2026",
        company="WHOOP",
        role="Technical Program Manager",
        salutation="Dear WHOOP Engineering Team,",
        paragraphs=[
            "Your mission to unlock human performance resonates deeply with my approach to technical leadership. "
            "Having spent a decade building systems that translate complex signals into actionable outcomes, "
            "I see a natural alignment between my work and the Technical Program Manager role at WHOOP.",
            "At Toast, I saved **$12M** by identifying critical firmware defects in payment terminals and led "
            "a **37%** reduction in escalation resolution time through cross-functional program governance. "
            "These results came from the same data-driven, systems-thinking approach that WHOOP applies to "
            "human performance optimization.",
            "My independent projects demonstrate the builder mindset I would bring to WHOOP. Ceal, my "
            "AI-powered career signal engine, uses Claude API integration, FastAPI, and ReportLab to "
            "automate the entire job application pipeline. Moss Lane, a real estate platform, showcases "
            "my GCP deployment and sprint management capabilities.",
            "What makes my background distinctive is the combination of deep technical fluency with "
            "executive-level program management. I can architect a system in the morning and present "
            "the business case to leadership in the afternoon.",
            "Based in Boston and immediately available, I would welcome the opportunity to discuss how "
            "my technical leadership experience can accelerate WHOOP's engineering programs.",
        ],
        signature_name="Joshua Hillard",
        links="linkedin.com/in/joshua-hillard | github.com/joshuahillard",
    )


class TestCoverLetterGeneration:
    def test_minimal_cover_letter_generates(self):
        """Minimal CoverLetterData produces valid PDF bytes."""
        result = generate_cover_letter_pdf(_minimal_data())
        assert result.success
        assert result.file_bytes is not None
        assert len(result.file_bytes) > 0

    def test_cover_letter_single_page(self):
        """5-paragraph WHOOP letter fits on single page."""
        result = generate_cover_letter_pdf(_five_paragraph_data())
        assert result.success
        assert not result.overflow

    def test_cover_letter_overflow_detected(self):
        """10 very long paragraphs trigger overflow detection."""
        data = _minimal_data()
        long_para = "This is a very long paragraph. " * 40
        data.paragraphs = [long_para] * 6
        result = generate_cover_letter_pdf(data)
        assert result.success
        assert result.overflow

    def test_cover_letter_pdf_starts_with_magic(self):
        """Output bytes start with %PDF- magic bytes."""
        result = generate_cover_letter_pdf(_minimal_data())
        assert result.file_bytes[:5] == b"%PDF-"

    def test_cover_letter_paragraph_count_validation(self):
        """Pydantic rejects < 3 or > 6 paragraphs."""
        with pytest.raises(ValidationError):
            CoverLetterData(
                name="Test",
                contact="test",
                date="test",
                company="test",
                role="test",
                paragraphs=["One.", "Two."],
                signature_name="Test",
                links="test",
            )

        with pytest.raises(ValidationError):
            CoverLetterData(
                name="Test",
                contact="test",
                date="test",
                company="test",
                role="test",
                paragraphs=["P"] * 7,
                signature_name="Test",
                links="test",
            )
