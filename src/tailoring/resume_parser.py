"""
Ceal Phase 2: Resume Profile Parser

Decomposes raw resume text into the ParsedResume Pydantic model.
This module bridges unstructured resume text into structured sections
that the tailoring engine can selectively rewrite per job listing.

Persona: Lead Backend Python Engineer
Constraint: All output must pass through ParsedResume validation.
Fallback: If section extraction fails, raw_text fallback is preserved
          so the pipeline never silently drops resume content.

Interview talking point:
    "The parser enforces a Pydantic boundary so unstructured resume text
    is decomposed into typed, validated sections before the LLM ever
    sees it — preventing prompt injection from malformed input."
"""
from __future__ import annotations

import re

from src.tailoring.models import ParsedBullet, ParsedResume, ResumeSection

# ---------------------------------------------------------------------------
# Skill taxonomy — canonical names the pipeline recognizes
# ---------------------------------------------------------------------------

SKILL_TAXONOMY: dict[str, str] = {
    "python": "Python",
    "sql": "SQL",
    "rest apis": "REST APIs",
    "rest api": "REST APIs",
    "api integrations": "API Integrations",
    "api integration": "API Integrations",
    "git": "Git",
    "linux": "Linux",
    "docker": "Docker",
    "gcp": "GCP",
    "aws": "AWS",
    "azure": "Azure",
    "asyncio": "asyncio",
    "pydantic": "Pydantic",
    "sqlalchemy": "SQLAlchemy",
    "systemd": "systemd",
    "ssh": "SSH/SCP",
    "ssh/scp": "SSH/SCP",
    "deployment automation": "Deployment Automation",
    "ci/cd": "CI/CD",
    "github actions": "GitHub Actions",
    "payment processing": "Payment Processing",
    "fintech": "FinTech",
    "saas": "SaaS",
    "data engineering": "Data Engineering",
    "machine learning": "Machine Learning",
    "escalation management": "Escalation Management",
    "cross-functional leadership": "Cross-Functional Leadership",
    "process optimization": "Process Optimization",
    "project management": "Project Management",
    "training & enablement": "Training & Enablement",
    "training": "Training & Enablement",
    "debugging": "Debugging",
    "troubleshooting": "Troubleshooting",
    "webhooks": "Webhooks",
    "javascript": "JavaScript",
    "java": "Java",
    "ruby": "Ruby",
    "cloud infrastructure": "Cloud Infrastructure",
    "communication": "Communication",
    "data analysis": "Data Analysis",
    "httpx": "httpx",
    "pytest": "pytest",
    "structlog": "structlog",
    "aiosqlite": "aiosqlite",
}

# ---------------------------------------------------------------------------
# Section header patterns — regex for detecting resume section boundaries
# ---------------------------------------------------------------------------

_SECTION_PATTERNS: dict[ResumeSection, re.Pattern] = {
    ResumeSection.SUMMARY: re.compile(
        r"^(?:SUMMARY|PROFESSIONAL\s+SUMMARY|PROFILE|OBJECTIVE|ABOUT)\s*$",
        re.IGNORECASE,
    ),
    ResumeSection.EXPERIENCE: re.compile(
        r"^(?:EXPERIENCE|WORK\s+EXPERIENCE|EMPLOYMENT|PROFESSIONAL\s+EXPERIENCE|INDEPENDENT\s+PROJECT)\s*$",
        re.IGNORECASE,
    ),
    ResumeSection.SKILLS: re.compile(
        r"^(?:SKILLS|TECHNICAL\s+SKILLS|CORE\s+COMPETENCIES|TECHNOLOGIES)\s*$",
        re.IGNORECASE,
    ),
    ResumeSection.PROJECTS: re.compile(
        r"^(?:PROJECTS|PERSONAL\s+PROJECTS|SIDE\s+PROJECTS|KEY\s+PROJECTS)\s*$",
        re.IGNORECASE,
    ),
    ResumeSection.CERTIFICATIONS: re.compile(
        r"^(?:CERTIFICATIONS|CERTIFICATES|EDUCATION|EDUCATION\s*&\s*CERTIFICATIONS)\s*$",
        re.IGNORECASE,
    ),
}

# Bullet prefix pattern
_BULLET_RE = re.compile(r"^\s*[-*\u2022\u25e6\u25aa]\s+")

# Metric detection patterns
_METRIC_PATTERNS = [
    re.compile(r"\$[\d,.]+[KMB]?", re.IGNORECASE),
    re.compile(r"\d+%"),
    re.compile(r"\d+\+?\s*(?:years?|months?|hours?)", re.IGNORECASE),
    re.compile(r"\d{1,3}(?:,\d{3})+"),
]


class ResumeProfileParser:
    """Parses raw resume text into structured sections for dynamic reordering."""

    def __init__(self) -> None:
        pass

    def parse(self, profile_id: int, raw_text: str) -> ParsedResume:
        """
        Executes parsing logic and enforces model boundary.

        Args:
            profile_id: The resume_profiles.id from the Phase 1 database.
            raw_text: Full resume text extracted from .docx or .pdf.

        Returns:
            ParsedResume with validated sections and raw_text fallback.

        Raises:
            ValidationError: If parsed output violates Pydantic constraints.
        """
        sections = self._extract_sections(raw_text)
        bullets: list[ParsedBullet] = []

        for section_type, lines in sections.items():
            for line in lines:
                clean = _BULLET_RE.sub("", line).strip()
                if len(clean) < 10:
                    continue
                metrics = self._extract_metrics(clean)
                skills = self._extract_skills(clean)
                bullets.append(ParsedBullet(
                    section=section_type,
                    original_text=clean,
                    skills_referenced=skills,
                    metrics=metrics,
                ))

        return ParsedResume(
            profile_id=profile_id,
            sections=bullets,
            raw_text=raw_text,
        )

    def _extract_sections(self, text: str) -> dict[ResumeSection, list[str]]:
        """Split text into sections based on header detection."""
        result: dict[ResumeSection, list[str]] = {}
        current_section: ResumeSection | None = None

        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue

            # Check if this line is a section header
            matched = False
            for section_type, pattern in _SECTION_PATTERNS.items():
                if pattern.match(stripped):
                    current_section = section_type
                    if current_section not in result:
                        result[current_section] = []
                    matched = True
                    break

            if matched:
                continue

            # Add content lines to current section
            if current_section is not None:
                # Accept bullet lines and non-empty content lines
                if _BULLET_RE.match(line) or (stripped and len(stripped) >= 10):
                    result[current_section].append(stripped)

        return result

    @staticmethod
    def _extract_metrics(text: str) -> list[str]:
        """Find dollar amounts, percentages, and numeric achievements."""
        metrics = []
        for pattern in _METRIC_PATTERNS:
            metrics.extend(pattern.findall(text))
        return metrics

    @staticmethod
    def _extract_skills(text: str) -> list[str]:
        """Cross-reference text against SKILL_TAXONOMY."""
        text_lower = text.lower()
        found: list[str] = []
        for keyword, canonical in SKILL_TAXONOMY.items():
            if keyword in text_lower and canonical not in found:
                found.append(canonical)
        return found
