"""Unit tests for the resume PDF generator."""
from __future__ import annotations

import os
import tempfile

from src.document.models import ResumeData, ResumeJobEntry, ResumeProjectEntry, ResumeSkillCategory
from src.document.resume_pdf import generate_resume_pdf


def _minimal_data() -> ResumeData:
    return ResumeData(
        name="TEST USER",
        title_line="Test Title",
        contact="Test Contact",
        links="test.com",
        profile="Test profile text with enough content to render.",
        experience=[],
        projects=[],
        skills=[],
        certifications=[],
        education=[],
    )


def _full_data() -> ResumeData:
    return ResumeData(
        name="JOSHUA HILLARD",
        title_line="Technical Leader | Program Management & Cloud Engineering",
        contact="Boston, MA | (781) 308-0407 | joshua.hillard4@gmail.com",
        links="linkedin.com/in/joshua-hillard | github.com/joshuahillard",
        profile=(
            "Technical leader with 10+ years in tech spanning payment processing, "
            "SaaS platforms, and cloud engineering. Saved **$12M** by identifying "
            "firmware defects and led a **37%** reduction in escalation time."
        ),
        experience=[
            ResumeJobEntry(
                title="Manager II, Technical Escalations",
                company="Toast, Inc.",
                location="Boston, MA",
                dates="Oct 2023 - Oct 2025",
                bullets=[
                    "Directed team of senior technical consultants handling **200+** complex escalations monthly",
                    "Identified critical firmware defects saving estimated **$12M** in potential losses",
                    "Led **37%** reduction in escalation resolution time through process optimization",
                ],
            ),
        ],
        projects=[
            ResumeProjectEntry(
                name="Ceal — Career Signal Engine",
                tech="Python, FastAPI, Claude API, ReportLab",
                dates="2025 - Present",
                bullets=[
                    "Built AI-powered career signal engine with resume tailoring pipeline",
                    "Integrated Claude API for LLM-based job matching and content generation",
                ],
            ),
        ],
        skills=[
            ResumeSkillCategory(label="Languages", items="Python, SQL, JavaScript, Bash"),
            ResumeSkillCategory(label="Cloud & Infra", items="GCP, Docker, Cloud Run, Cloud SQL"),
        ],
        certifications=["Google Cloud Associate Cloud Engineer (2024)"],
        education=["B.S. Information Technology, University of Massachusetts"],
        section_order=["experience", "projects"],
    )


class TestResumeGeneration:
    def test_minimal_resume_generates(self):
        """Minimal ResumeData produces valid PDF bytes."""
        result = generate_resume_pdf(_minimal_data())
        assert result.success
        assert result.file_bytes is not None
        assert len(result.file_bytes) > 0

    def test_full_resume_generates(self):
        """Complete ResumeData with all sections produces valid PDF bytes."""
        result = generate_resume_pdf(_full_data())
        assert result.success
        assert result.file_bytes is not None
        assert len(result.file_bytes) > 1000

    def test_resume_single_page(self):
        """Full Josh resume data fits on a single page."""
        result = generate_resume_pdf(_full_data())
        assert result.success
        assert not result.overflow

    def test_resume_overflow_detected(self):
        """Extremely long content triggers overflow detection."""
        data = _full_data()
        # Add tons of extra bullets to force overflow
        long_bullets = [f"Bullet item number {i} with enough text to take up space on the page" for i in range(50)]
        data.experience[0].bullets = long_bullets
        result = generate_resume_pdf(data)
        assert result.success
        assert result.overflow

    def test_resume_pdf_starts_with_magic(self):
        """Output bytes start with %PDF- magic bytes."""
        result = generate_resume_pdf(_minimal_data())
        assert result.file_bytes[:5] == b"%PDF-"

    def test_resume_file_output(self):
        """output_path provided writes file to disk."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            result = generate_resume_pdf(_minimal_data(), output_path=tmp_path)
            assert result.success
            assert result.file_path == tmp_path
            assert os.path.exists(tmp_path)
            with open(tmp_path, "rb") as f:
                assert f.read(5) == b"%PDF-"
        finally:
            os.unlink(tmp_path)

    def test_resume_section_order(self):
        """section_order=["projects", "experience"] puts projects first."""
        data = _full_data()
        data.section_order = ["projects", "experience"]
        result = generate_resume_pdf(data)
        assert result.success
        assert result.file_bytes is not None
