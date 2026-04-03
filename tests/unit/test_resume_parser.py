"""
Ceal Phase 2: Resume Parser Tests

Tests the ResumeProfileParser against frozen resume fixtures.
Validates section detection, bullet extraction, metric detection,
and skill cross-referencing against the known skill taxonomy.

Persona: [QA Lead] -- deterministic parsing, Pydantic boundary enforcement
Constraint: No LLM calls, no external dependencies. Frozen fixtures only.
"""

import pytest
from pydantic import ValidationError

from src.tailoring.models import ParsedBullet, ParsedResume, ResumeSection
from src.tailoring.resume_parser import ResumeProfileParser

# ---------------------------------------------------------------------------
# Frozen Fixture: Josh Hillard Resume
# ---------------------------------------------------------------------------

JOSH_RESUME = """
Josh Hillard
Boston, MA | josh@example.com | (555) 123-4567

SUMMARY:
Experienced technical leader with 6+ years in SaaS escalation management,
cross-functional leadership, and process optimization at Toast, Inc.

EXPERIENCE:
- Manager II, Technical Escalations at Toast, Inc. (Oct 2023 - Oct 2025)
  * Directed team of senior technical consultants handling complex escalations
  * Identified critical firmware defects saving Toast estimated $12 million
  * Recognized by CEO Chris Comparato at company-wide kickoff event
  * Reduced recurring issue volume by 37% via cross-functional collaboration
  * Created enablement materials, onboarding frameworks, knowledge base articles

- Senior Restaurant Technical Consultant II at Toast (Jun 2022 - Sep 2023)
  * 63% successful post-sales adoption partnering with Success Managers
  * Created consultative playbooks and training frameworks
  * Primary Technical SME for on-site and cross-team initiatives

- Senior Customer Care Rep at Toast (Apr 2019 - Jun 2022)
  * Complex payment processing escalation management
  * Customer feedback analysis driving operational enhancements

PROJECTS:
- Moss Lane Trading Bot (March 2026 - Present)
  * Production autonomous trading system on cloud infrastructure
  * Full lifecycle: audit, root cause analysis, 1,800-line rewrite
  * 5 external API integrations, multi-layer risk management
  * Python, Linux admin, SSH/SCP, systemd, SQL, REST APIs

SKILLS:
Technical: Python, SQL, REST APIs, Linux, Docker, GCP, asyncio, Git
Leadership: Escalation Management, Cross-Functional Leadership
Domain: FinTech, POS Systems, SaaS, Payment Processing

CERTIFICATIONS:
- Google AI Essentials - Professional Certificate (2026)
- Google Project Management - Professional Certificate (In Progress)
""".strip()

# Minimal resume with only raw text, no parseable sections
MINIMAL_RESUME = "Josh Hillard - Technical Solutions Engineer with Python and SQL experience."

# Resume with no metrics
NO_METRICS_RESUME = """
EXPERIENCE:
- Managed a team of technical consultants
- Led cross-functional projects to improve product quality
- Created onboarding documentation for new hires

SKILLS:
Python, SQL, REST APIs
""".strip()

# Resume with unusual section headers
UNUSUAL_HEADERS_RESUME = """
PROFESSIONAL SUMMARY:
Experienced engineer with deep technical background.

WORK EXPERIENCE:
- Built distributed systems for real-time data processing
- Deployed microservices architecture serving millions of requests

TECHNICAL SKILLS:
Python, Go, Kubernetes, Terraform

EDUCATION & CERTIFICATIONS:
- MIT Computer Science (2018)
- AWS Solutions Architect (2020)
""".strip()


class TestResumeProfileParser:
    """Validates parser behavior against frozen resume fixtures."""

    def setup_method(self):
        self.parser = ResumeProfileParser()

    # ------------------------------------------------------------------
    # test_parse_valid_resume -- full resume -> ParsedResume
    # ------------------------------------------------------------------

    def test_parse_valid_resume(self):
        """Full Josh resume -> ParsedResume with sections and raw_text."""
        result = self.parser.parse(profile_id=1, raw_text=JOSH_RESUME)

        assert isinstance(result, ParsedResume)
        assert result.profile_id == 1
        assert result.raw_text == JOSH_RESUME
        assert len(result.sections) > 0

    def test_parse_returns_pydantic_model(self):
        """Output conforms to ParsedResume Pydantic contract."""
        result = self.parser.parse(profile_id=42, raw_text=JOSH_RESUME)
        assert isinstance(result, ParsedResume)
        dumped = result.model_dump()
        assert "profile_id" in dumped
        assert "sections" in dumped
        assert "raw_text" in dumped

    # ------------------------------------------------------------------
    # test_parse_section_detection -- correct section classification
    # ------------------------------------------------------------------

    def test_parse_section_detection(self):
        """Detects SUMMARY, EXPERIENCE, SKILLS, PROJECTS, CERTIFICATIONS."""
        result = self.parser.parse(profile_id=1, raw_text=JOSH_RESUME)
        detected_sections = {b.section for b in result.sections}

        assert ResumeSection.SUMMARY in detected_sections
        assert ResumeSection.EXPERIENCE in detected_sections
        assert ResumeSection.SKILLS in detected_sections
        assert ResumeSection.PROJECTS in detected_sections
        assert ResumeSection.CERTIFICATIONS in detected_sections

    def test_experience_bullets_extracted(self):
        """EXPERIENCE section contains multiple bullet points."""
        result = self.parser.parse(profile_id=1, raw_text=JOSH_RESUME)
        experience_bullets = [
            b for b in result.sections if b.section == ResumeSection.EXPERIENCE
        ]
        assert len(experience_bullets) >= 5

    def test_unusual_section_headers(self):
        """Handles PROFESSIONAL SUMMARY, WORK EXPERIENCE, TECHNICAL SKILLS."""
        result = self.parser.parse(profile_id=1, raw_text=UNUSUAL_HEADERS_RESUME)
        detected = {b.section for b in result.sections}

        assert ResumeSection.SUMMARY in detected
        assert ResumeSection.EXPERIENCE in detected
        assert ResumeSection.SKILLS in detected
        assert ResumeSection.CERTIFICATIONS in detected

    # ------------------------------------------------------------------
    # test_parse_metric_extraction -- '$12M', '37%', '93 tests' detected
    # ------------------------------------------------------------------

    def test_parse_metric_extraction_dollar(self):
        """Detects '$12 million' in resume bullets."""
        result = self.parser.parse(profile_id=1, raw_text=JOSH_RESUME)
        all_metrics = []
        for b in result.sections:
            all_metrics.extend(b.metrics)

        metric_text = " ".join(all_metrics).lower()
        assert "$12" in metric_text or "12 million" in metric_text

    def test_parse_metric_extraction_percentage(self):
        """Detects '37%' in resume bullets."""
        result = self.parser.parse(profile_id=1, raw_text=JOSH_RESUME)
        all_metrics = []
        for b in result.sections:
            all_metrics.extend(b.metrics)

        assert any("37%" in m for m in all_metrics)

    def test_parse_metric_extraction_percentage_63(self):
        """Detects '63%' in resume bullets."""
        result = self.parser.parse(profile_id=1, raw_text=JOSH_RESUME)
        all_metrics = []
        for b in result.sections:
            all_metrics.extend(b.metrics)

        assert any("63%" in m for m in all_metrics)

    def test_no_metrics_resume(self):
        """Resume with no metrics produces bullets with empty metrics lists."""
        result = self.parser.parse(profile_id=1, raw_text=NO_METRICS_RESUME)
        for b in result.sections:
            assert b.metrics == []

    def test_hyphenated_measure_detection(self):
        """Detects '1,800-line' in Moss Lane project bullet."""
        result = self.parser.parse(profile_id=1, raw_text=JOSH_RESUME)
        all_metrics = []
        for b in result.sections:
            all_metrics.extend(b.metrics)

        assert any("1,800-line" in m for m in all_metrics)

    # ------------------------------------------------------------------
    # Skill cross-referencing
    # ------------------------------------------------------------------

    def test_skill_detection_in_experience(self):
        """Detects skill references in experience bullets."""
        result = self.parser.parse(profile_id=1, raw_text=JOSH_RESUME)
        all_skills = set()
        for b in result.sections:
            all_skills.update(b.skills_referenced)

        assert "Python" in all_skills
        assert "SQL" in all_skills
        assert "REST APIs" in all_skills or "API Integrations" in all_skills

    def test_skill_detection_in_skills_section(self):
        """Skills section bullets reference taxonomy entries."""
        result = self.parser.parse(profile_id=1, raw_text=JOSH_RESUME)
        skills_bullets = [
            b for b in result.sections if b.section == ResumeSection.SKILLS
        ]
        all_skills = set()
        for b in skills_bullets:
            all_skills.update(b.skills_referenced)

        assert "Python" in all_skills
        assert "Docker" in all_skills
        assert "GCP" in all_skills

    # ------------------------------------------------------------------
    # test_parse_empty_input -- graceful handling
    # ------------------------------------------------------------------

    def test_parse_empty_input(self):
        """Empty string raises ValidationError (no sections, no raw_text)."""
        with pytest.raises(ValidationError):
            self.parser.parse(profile_id=1, raw_text="")

    def test_parse_minimal_text(self):
        """Text with no section headers still returns ParsedResume with raw_text fallback."""
        result = self.parser.parse(profile_id=1, raw_text=MINIMAL_RESUME)
        assert isinstance(result, ParsedResume)
        assert result.raw_text == MINIMAL_RESUME
        # May have no sections, but raw_text preserves the content
        assert result.raw_text != ""

    def test_all_bullets_are_parsed_bullet_instances(self):
        """Every extracted bullet is a valid ParsedBullet Pydantic model."""
        result = self.parser.parse(profile_id=1, raw_text=JOSH_RESUME)
        for bullet in result.sections:
            assert isinstance(bullet, ParsedBullet)
            assert len(bullet.original_text) >= 10
            assert isinstance(bullet.section, ResumeSection)

    def test_parser_instantiation(self):
        """Parser can be instantiated with no arguments."""
        parser = ResumeProfileParser()
        assert parser is not None

    def test_profile_id_preserved(self):
        """profile_id passed to parse() is preserved in output."""
        result = self.parser.parse(profile_id=99, raw_text=JOSH_RESUME)
        assert result.profile_id == 99

    def test_certifications_section_detected(self):
        """CERTIFICATIONS section is detected and bullets extracted."""
        result = self.parser.parse(profile_id=1, raw_text=JOSH_RESUME)
        cert_bullets = [
            b for b in result.sections if b.section == ResumeSection.CERTIFICATIONS
        ]
        assert len(cert_bullets) >= 1

    def test_projects_section_detected(self):
        """PROJECTS section bullets include Moss Lane content."""
        result = self.parser.parse(profile_id=1, raw_text=JOSH_RESUME)
        project_bullets = [
            b for b in result.sections if b.section == ResumeSection.PROJECTS
        ]
        assert len(project_bullets) >= 1
        project_text = " ".join(b.original_text for b in project_bullets)
        assert "trading" in project_text.lower() or "api" in project_text.lower()
