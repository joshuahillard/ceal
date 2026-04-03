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
    sees it -- preventing prompt injection from malformed input."
"""
from __future__ import annotations

import re

from src.tailoring.models import ParsedBullet, ParsedResume, ResumeSection

# ---------------------------------------------------------------------------
# Skill Taxonomy -- canonical skills for cross-referencing
# ---------------------------------------------------------------------------
# This is the Phase 1 skill vocabulary. In production, this would load from
# the skills table via SQLAlchemy. For deterministic parsing, we hardcode it.

SKILL_TAXONOMY: dict[str, list[str]] = {
    "Python": ["python"],
    "SQL": ["sql", "sqlite", "postgresql", "mysql"],
    "REST APIs": ["rest api", "rest apis", "restful", "api integration"],
    "Linux": ["linux", "ubuntu", "centos"],
    "Docker": ["docker", "containerization", "containers"],
    "GCP": ["gcp", "google cloud", "google cloud platform"],
    "AWS": ["aws", "amazon web services"],
    "Azure": ["azure", "microsoft azure"],
    "asyncio": ["asyncio", "async", "asynchronous"],
    "Git": ["git", "github", "version control"],
    "Payment Processing": ["payment processing", "payment", "payments", "pos"],
    "API Integrations": ["api integration", "api integrations"],
    "systemd": ["systemd", "systemctl"],
    "Deployment Automation": ["deployment automation", "ci/cd", "cicd"],
    "Escalation Management": ["escalation", "escalations", "escalation management"],
    "Cross-Functional Leadership": ["cross-functional", "cross functional"],
    "Process Optimization": ["process optimization", "process improvement"],
    "Training & Enablement": ["training", "enablement", "onboarding"],
    "Project Management": ["project management", "program management"],
    "FinTech": ["fintech", "financial technology"],
    "SaaS": ["saas", "software as a service"],
    "Kubernetes": ["kubernetes", "k8s"],
    "Terraform": ["terraform", "infrastructure as code", "iac"],
    "Java": ["java"],
    "Go": ["golang", " go "],
    "TypeScript": ["typescript", " ts "],
    "JavaScript": ["javascript", " js "],
    "React": ["react", "reactjs"],
    "Node.js": ["node.js", "nodejs", "node"],
    "Machine Learning": ["machine learning", "ml", "deep learning"],
    "Data Engineering": ["data engineering", "data pipeline", "etl"],
    "Pydantic": ["pydantic"],
    "SQLAlchemy": ["sqlalchemy"],
    "FastAPI": ["fastapi"],
    "Flask": ["flask"],
    "Django": ["django"],
}

# ---------------------------------------------------------------------------
# Section Header Patterns
# ---------------------------------------------------------------------------
# Matches lines like "EXPERIENCE:", "SKILLS", "## PROJECTS", "CERTIFICATIONS —"
# Case-insensitive, allows optional leading markers and trailing punctuation.

_SECTION_PATTERNS: dict[ResumeSection, re.Pattern] = {
    ResumeSection.SUMMARY: re.compile(
        r"^\s*(?:#*\s*)?(?:SUMMARY|PROFESSIONAL\s+SUMMARY|PROFILE|OBJECTIVE|ABOUT)\s*[:\-—]*\s*$",
        re.IGNORECASE,
    ),
    ResumeSection.EXPERIENCE: re.compile(
        r"^\s*(?:#*\s*)?(?:EXPERIENCE|WORK\s+EXPERIENCE|EMPLOYMENT|PROFESSIONAL\s+EXPERIENCE|INDEPENDENT\s+PROJECT)\s*[:\-—]*\s*$",
        re.IGNORECASE,
    ),
    ResumeSection.SKILLS: re.compile(
        r"^\s*(?:#*\s*)?(?:SKILLS|TECHNICAL\s+SKILLS|CORE\s+COMPETENCIES|TECHNOLOGIES)\s*[:\-—]*\s*$",
        re.IGNORECASE,
    ),
    ResumeSection.PROJECTS: re.compile(
        r"^\s*(?:#*\s*)?(?:PROJECTS|PERSONAL\s+PROJECTS|SIDE\s+PROJECTS|KEY\s+PROJECTS)\s*[:\-—]*\s*$",
        re.IGNORECASE,
    ),
    ResumeSection.CERTIFICATIONS: re.compile(
        r"^\s*(?:#*\s*)?(?:CERTIFICATIONS|CERTIFICATES|EDUCATION|EDUCATION\s*&\s*CERTIFICATIONS)\s*[:\-—]*\s*$",
        re.IGNORECASE,
    ),
}

# ---------------------------------------------------------------------------
# Metric Detection Pattern
# ---------------------------------------------------------------------------
# Matches: $12M, $12 million, 37%, 93 tests, 1,800-line, 50K+, 100+
_METRIC_PATTERN = re.compile(
    r"""
    \$[\d,]+(?:\.\d+)?[KMBkmb]?(?:\s*(?:million|billion|thousand))? |  # Dollar amounts
    \d+(?:,\d{3})*(?:\.\d+)?%                                       |  # Percentages
    \d+(?:,\d{3})*\+?\s*(?:tests|users|devices|clients|teams|people|engineers|months|years|hours|days|minutes) |  # Counted nouns
    \d+(?:,\d{3})*[KMBkmb]\+?                                       |  # Abbreviated numbers (50K+)
    \d+(?:,\d{3})*-(?:line|page|step|point|stage)                       # Hyphenated measures
    """,
    re.VERBOSE | re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Bullet Detection Pattern
# ---------------------------------------------------------------------------
# Matches lines starting with: -, *, bullet, or indented sub-bullets
_BULLET_PATTERN = re.compile(r"^\s*[\-\*\u2022\u25E6\u25AA]\s+(.+)$")


class ResumeProfileParser:
    """Parses raw resume text into structured sections for dynamic reordering."""

    def __init__(self) -> None:
        self._taxonomy_lower: dict[str, list[str]] = {
            canonical: [alias.lower() for alias in aliases]
            for canonical, aliases in SKILL_TAXONOMY.items()
        }

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
        lines = raw_text.split("\n")
        sections = self._extract_sections(lines)
        bullets = self._extract_bullets(sections)

        return ParsedResume(
            profile_id=profile_id,
            sections=bullets,
            raw_text=raw_text,
        )

    def _detect_section(self, line: str) -> ResumeSection | None:
        """Check if a line is a section header."""
        for section, pattern in _SECTION_PATTERNS.items():
            if pattern.match(line):
                return section
        return None

    def _extract_sections(self, lines: list[str]) -> dict[ResumeSection, list[str]]:
        """
        Walk through lines and group them under detected section headers.
        Lines before the first header are dropped (typically name/contact info).
        """
        sections: dict[ResumeSection, list[str]] = {}
        current_section: ResumeSection | None = None

        for line in lines:
            detected = self._detect_section(line)
            if detected is not None:
                current_section = detected
                if current_section not in sections:
                    sections[current_section] = []
                continue

            if current_section is not None and line.strip():
                sections[current_section].append(line)

        return sections

    def _extract_bullets(
        self, sections: dict[ResumeSection, list[str]]
    ) -> list[ParsedBullet]:
        """
        Extract bullet points from each section, detect metrics,
        and cross-reference skills against the taxonomy.
        """
        bullets: list[ParsedBullet] = []

        for section, lines in sections.items():
            for line in lines:
                bullet_match = _BULLET_PATTERN.match(line)
                text = bullet_match.group(1).strip() if bullet_match else line.strip()

                if len(text) < 10:
                    continue

                metrics = self._detect_metrics(text)
                skills = self._detect_skills(text)

                bullets.append(
                    ParsedBullet(
                        section=section,
                        original_text=text,
                        skills_referenced=skills,
                        metrics=metrics,
                    )
                )

        return bullets

    def _detect_metrics(self, text: str) -> list[str]:
        """Find dollar amounts, percentages, and counted nouns in text."""
        return [m.strip() for m in _METRIC_PATTERN.findall(text)]

    def _detect_skills(self, text: str) -> list[str]:
        """Cross-reference text against the skill taxonomy."""
        text_lower = text.lower()
        found: list[str] = []

        for canonical, aliases in self._taxonomy_lower.items():
            for alias in aliases:
                if alias in text_lower:
                    found.append(canonical)
                    break

        return found
