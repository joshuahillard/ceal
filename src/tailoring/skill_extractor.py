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

from typing import List

from src.models.entities import JobListing
from src.tailoring.models import SkillGap


class SkillOverlapAnalyzer:
    """Calculates overlaps and flags critical gaps for LLM context."""

    def __init__(self) -> None:
        pass

    def analyze(self, job: JobListing, resume_skills: List[str]) -> List[SkillGap]:
        """
        Calculates gap analysis enforcing SkillGap Pydantic boundaries.

        Args:
            job: A fully validated JobListing from Phase 1 pipeline.
            resume_skills: List of skill names from the candidate's profile.

        Returns:
            List of SkillGap models — one per skill in the job listing,
            with resume_has and proficiency mapped where applicable.
        """
        # TODO: Implement overlap and gap flag logic
        # Implementation plan (Wed 4/1):
        #   1. Extract required skills from job.description_clean
        #   2. Cross-reference against resume_skills (fuzzy + exact match)
        #   3. Map proficiency levels from resume_profiles_skills table
        #   4. Return SkillGap list with conservative gap flagging
        raise NotImplementedError("Stub implementation — scheduled for Wed 4/1")
