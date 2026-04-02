"""
Ceal Phase 2: Skill Overlap Analyzer

Analyzes the job requirements against the candidate profile to generate
SkillGaps. This is the bridge between Phase 1's ranked listings and
Phase 2's tailored output — it tells the LLM what to emphasize and
what gaps to address.

Persona: Senior Data Engineer / ETL Architect
Constraint: Output must flow through SkillGap Pydantic boundary.
Fallback: If skill matching is ambiguous, default to job_requires=True
          and resume_has=False to surface the gap conservatively.

Interview talking point:
    "The skill gap analyzer feeds structured context to the LLM so it
    doesn't hallucinate qualifications — it can only emphasize skills
    the candidate actually has, and must flag gaps transparently."
"""
from __future__ import annotations

from src.models.entities import JobListing, Proficiency, SkillCategory
from src.tailoring.models import SkillGap

# ---------------------------------------------------------------------------
# Skill category mappings for common job description terms
# ---------------------------------------------------------------------------

_SKILL_CATEGORIES: dict[str, tuple[str, SkillCategory]] = {
    "python": ("Python", SkillCategory.LANGUAGE),
    "javascript": ("JavaScript", SkillCategory.LANGUAGE),
    "java": ("Java", SkillCategory.LANGUAGE),
    "ruby": ("Ruby", SkillCategory.LANGUAGE),
    "sql": ("SQL", SkillCategory.DATABASE),
    "rest apis": ("REST APIs", SkillCategory.TOOL),
    "webhooks": ("Webhooks", SkillCategory.TOOL),
    "debugging": ("Debugging", SkillCategory.METHODOLOGY),
    "troubleshooting": ("Troubleshooting", SkillCategory.METHODOLOGY),
    "payment processing": ("Payment Processing", SkillCategory.DOMAIN),
    "financial technology": ("FinTech", SkillCategory.DOMAIN),
    "fintech": ("FinTech", SkillCategory.DOMAIN),
    "cloud infrastructure": ("Cloud Infrastructure", SkillCategory.INFRASTRUCTURE),
    "aws": ("AWS", SkillCategory.CLOUD),
    "gcp": ("GCP", SkillCategory.CLOUD),
    "azure": ("Azure", SkillCategory.CLOUD),
    "communication": ("Communication", SkillCategory.SOFT_SKILL),
    "data analysis": ("Data Analysis", SkillCategory.METHODOLOGY),
    "saas": ("SaaS", SkillCategory.DOMAIN),
    "docker": ("Docker", SkillCategory.INFRASTRUCTURE),
    "linux": ("Linux", SkillCategory.INFRASTRUCTURE),
    "git": ("Git", SkillCategory.TOOL),
    "technical escalations": ("Technical Escalations", SkillCategory.SOFT_SKILL),
    "project management": ("Project Management", SkillCategory.METHODOLOGY),
    "api integrations": ("API Integrations", SkillCategory.TOOL),
}


class SkillOverlapAnalyzer:
    """Calculates overlaps and flags critical gaps for LLM context."""

    def __init__(self) -> None:
        pass

    def analyze(self, job: JobListing, resume_skills: list[str]) -> list[SkillGap]:
        """
        Calculates gap analysis enforcing SkillGap Pydantic boundaries.

        Args:
            job: A fully validated JobListing from Phase 1 pipeline.
            resume_skills: List of skill names from the candidate's profile.

        Returns:
            List of SkillGap models — one per skill in the job listing,
            with resume_has and proficiency mapped where applicable.
        """
        job_skills = self._extract_job_skills(
            job.description_clean or job.description_raw or ""
        )
        resume_lower = {s.lower().strip() for s in resume_skills}

        gaps: list[SkillGap] = []
        seen: set[str] = set()

        for skill_name, category in job_skills:
            key = skill_name.lower()
            if key in seen:
                continue
            seen.add(key)

            has_skill = any(
                key in r or r in key for r in resume_lower
            )

            gaps.append(SkillGap(
                skill_name=skill_name,
                category=category,
                job_requires=True,
                resume_has=has_skill,
                proficiency=Proficiency.PROFICIENT if has_skill else None,
            ))

        return gaps

    def _extract_job_skills(
        self, description: str,
    ) -> list[tuple[str, SkillCategory]]:
        """Extract skill phrases from job description text."""
        found: list[tuple[str, SkillCategory]] = []
        desc_lower = description.lower()
        seen: set[str] = set()

        for keyword, (display_name, category) in _SKILL_CATEGORIES.items():
            if keyword in desc_lower and display_name.lower() not in seen:
                seen.add(display_name.lower())
                found.append((display_name, category))

        return found
