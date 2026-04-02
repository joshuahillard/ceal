"""
Ceal Phase 2: Resume Parser Tests

Validates that the ResumeProfileParser correctly parses raw resume text
into structured ParsedResume with sections, bullets, skills, and metrics.

Persona: [QA Lead] — parsing accuracy, contract verification
"""

import pytest

from src.tailoring.models import ParsedResume, ResumeSection
from src.tailoring.resume_parser import ResumeProfileParser


SAMPLE_RESUME = """
PROFESSIONAL SUMMARY
Experienced technical leader with 10+ years in tech, including 6+ years managing escalation teams.

EXPERIENCE
Toast, Inc. — Manager II, Technical Escalations (Oct 2023 – Oct 2025)
- Saved Toast estimated $12 million by identifying critical firmware defects on handheld POS devices
- Reduced recurring issue volume by 37% via cross-functional collaboration with Product and Engineering teams
- Created enablement materials, onboarding frameworks, and knowledge base articles for technical teams

SKILLS
- Technical: Python, SQL, REST APIs, Git, Payment Processing
- Leadership: Escalation Management, Cross-Functional Leadership

PROJECTS
Ceal — AI-Powered Career Signal Engine (March 2026 – Present)
- Designed event-driven async pipeline processing 500+ job listings in 8 seconds
- Built Claude API integration for deterministic LLM scoring with prompt versioning

CERTIFICATIONS
- Google AI Essentials — Professional Certificate (2026)
""".strip()


class TestResumeProfileParser:
    """Validates parser behavior and interface contract."""

    def test_parser_returns_parsed_resume(self):
        """Parser returns a valid ParsedResume with sections extracted."""
        parser = ResumeProfileParser()
        result = parser.parse(profile_id=1, raw_text=SAMPLE_RESUME)
        assert isinstance(result, ParsedResume)
        assert result.profile_id == 1
        assert len(result.sections) > 0

    def test_parser_detects_sections(self):
        """Parser detects multiple section types from the resume."""
        parser = ResumeProfileParser()
        result = parser.parse(profile_id=1, raw_text=SAMPLE_RESUME)
        sections_found = set(b.section for b in result.sections)
        assert ResumeSection.EXPERIENCE in sections_found
        assert ResumeSection.SKILLS in sections_found

    def test_parser_extracts_metrics(self):
        """Parser detects dollar amounts and percentages in bullets."""
        parser = ResumeProfileParser()
        result = parser.parse(profile_id=1, raw_text=SAMPLE_RESUME)
        all_metrics = [m for b in result.sections for m in b.metrics]
        assert any("$12" in m for m in all_metrics)
        assert any("37%" in m for m in all_metrics)

    def test_parser_instantiation(self):
        """Parser can be instantiated with no arguments."""
        parser = ResumeProfileParser()
        assert parser is not None

    def test_parser_preserves_raw_text(self):
        """ParsedResume includes raw_text fallback."""
        parser = ResumeProfileParser()
        result = parser.parse(profile_id=42, raw_text=SAMPLE_RESUME)
        assert result.raw_text == SAMPLE_RESUME
