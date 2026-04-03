"""
Ceal Phase 2: Skill Overlap Analyzer

Analyzes the job requirements against the candidate profile to generate
SkillGaps. This is the bridge between Phase 1's ranked listings and
Phase 2's tailored output -- it tells the LLM what to emphasize and
what gaps to address.

Persona: Senior Data Engineer / ETL Architect
Constraint: Output must flow through SkillGap Pydantic boundary.
Fallback: If skill matching is ambiguous, default to job_requires=True
          and resume_has=False to surface the gap conservatively.

Interview talking point:
    "The skill gap analyzer feeds structured context to the LLM so it
    doesn't hallucinate qualifications -- it can only emphasize skills
    the candidate actually has, and must flag gaps transparently."
"""
from __future__ import annotations

from src.models.entities import JobListing, Proficiency, SkillCategory
from src.tailoring.models import SkillGap
from src.tailoring.resume_parser import SKILL_TAXONOMY

# ---------------------------------------------------------------------------
# Skill-to-Category Mapping
# ---------------------------------------------------------------------------
# Maps canonical skill names to their SkillCategory for structured output.

_SKILL_CATEGORIES: dict[str, SkillCategory] = {
    "Python": SkillCategory.LANGUAGE,
    "Java": SkillCategory.LANGUAGE,
    "Go": SkillCategory.LANGUAGE,
    "TypeScript": SkillCategory.LANGUAGE,
    "JavaScript": SkillCategory.LANGUAGE,
    "SQL": SkillCategory.DATABASE,
    "SQLAlchemy": SkillCategory.FRAMEWORK,
    "Pydantic": SkillCategory.FRAMEWORK,
    "FastAPI": SkillCategory.FRAMEWORK,
    "Flask": SkillCategory.FRAMEWORK,
    "Django": SkillCategory.FRAMEWORK,
    "React": SkillCategory.FRAMEWORK,
    "Node.js": SkillCategory.FRAMEWORK,
    "REST APIs": SkillCategory.TOOL,
    "API Integrations": SkillCategory.TOOL,
    "Git": SkillCategory.TOOL,
    "systemd": SkillCategory.TOOL,
    "Linux": SkillCategory.INFRASTRUCTURE,
    "Docker": SkillCategory.INFRASTRUCTURE,
    "Kubernetes": SkillCategory.INFRASTRUCTURE,
    "Terraform": SkillCategory.INFRASTRUCTURE,
    "Deployment Automation": SkillCategory.INFRASTRUCTURE,
    "GCP": SkillCategory.CLOUD,
    "AWS": SkillCategory.CLOUD,
    "Azure": SkillCategory.CLOUD,
    "asyncio": SkillCategory.LANGUAGE,
    "Payment Processing": SkillCategory.DOMAIN,
    "FinTech": SkillCategory.DOMAIN,
    "SaaS": SkillCategory.DOMAIN,
    "Data Engineering": SkillCategory.DOMAIN,
    "Machine Learning": SkillCategory.DOMAIN,
    "Escalation Management": SkillCategory.SOFT_SKILL,
    "Cross-Functional Leadership": SkillCategory.SOFT_SKILL,
    "Process Optimization": SkillCategory.METHODOLOGY,
    "Training & Enablement": SkillCategory.SOFT_SKILL,
    "Project Management": SkillCategory.METHODOLOGY,
}

# Default proficiency mapping for skills the candidate has.
# In production this would come from resume_profiles_skills table.
_DEFAULT_PROFICIENCY: dict[str, Proficiency] = {
    "Python": Proficiency.PROFICIENT,
    "SQL": Proficiency.PROFICIENT,
    "REST APIs": Proficiency.PROFICIENT,
    "Linux": Proficiency.PROFICIENT,
    "Git": Proficiency.PROFICIENT,
    "asyncio": Proficiency.PROFICIENT,
    "Payment Processing": Proficiency.EXPERT,
    "Escalation Management": Proficiency.EXPERT,
    "Cross-Functional Leadership": Proficiency.EXPERT,
    "Process Optimization": Proficiency.PROFICIENT,
    "Training & Enablement": Proficiency.EXPERT,
    "Project Management": Proficiency.PROFICIENT,
    "FinTech": Proficiency.PROFICIENT,
    "SaaS": Proficiency.PROFICIENT,
    "API Integrations": Proficiency.PROFICIENT,
    "systemd": Proficiency.FAMILIAR,
    "Deployment Automation": Proficiency.FAMILIAR,
    "Docker": Proficiency.FAMILIAR,
    "GCP": Proficiency.FAMILIAR,
    "Pydantic": Proficiency.PROFICIENT,
    "SQLAlchemy": Proficiency.PROFICIENT,
}


class SkillOverlapAnalyzer:
    """Calculates overlaps and flags critical gaps for LLM context."""

    def __init__(self) -> None:
        self._taxonomy_lower: dict[str, list[str]] = {
            canonical: [alias.lower() for alias in aliases]
            for canonical, aliases in SKILL_TAXONOMY.items()
        }

    def analyze(self, job: JobListing, resume_skills: list[str]) -> list[SkillGap]:
        """
        Calculates gap analysis enforcing SkillGap Pydantic boundaries.

        Args:
            job: A fully validated JobListing from Phase 1 pipeline.
            resume_skills: List of skill names from the candidate's profile.

        Returns:
            List of SkillGap models -- one per skill detected in the job listing,
            with resume_has and proficiency mapped where applicable.
        """
        job_text = (job.description_clean or job.description_raw or "").lower()
        job_skills = self._extract_skills_from_text(job_text)
        resume_skills_lower = {s.lower() for s in resume_skills}

        gaps: list[SkillGap] = []
        seen: set[str] = set()

        for canonical_name in job_skills:
            if canonical_name in seen:
                continue
            seen.add(canonical_name)

            has_skill = canonical_name.lower() in resume_skills_lower or any(
                rs in canonical_name.lower() or canonical_name.lower() in rs
                for rs in resume_skills_lower
            )
            category = _SKILL_CATEGORIES.get(canonical_name, SkillCategory.TOOL)
            proficiency = _DEFAULT_PROFICIENCY.get(canonical_name) if has_skill else None

            gaps.append(
                SkillGap(
                    skill_name=canonical_name,
                    category=category,
                    job_requires=True,
                    resume_has=has_skill,
                    proficiency=proficiency,
                )
            )

        return gaps

    def _extract_skills_from_text(self, text: str) -> list[str]:
        """Find all canonical skills mentioned in text using the taxonomy."""
        found: list[str] = []
        for canonical, aliases in self._taxonomy_lower.items():
            for alias in aliases:
                if alias in text:
                    found.append(canonical)
                    break
        return found
