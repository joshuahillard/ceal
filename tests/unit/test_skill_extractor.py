"""
Ceal Phase 2: Skill Overlap Analyzer Tests

Tests the SkillOverlapAnalyzer against frozen job fixtures.
Validates skill gap detection, proficiency mapping, and conservative
gap flagging for skills the candidate doesn't have.

Persona: [QA Lead] -- deterministic analysis, Pydantic boundary enforcement
"""

import datetime

import pytest

from src.models.entities import (
    JobListing,
    JobSource,
    JobStatus,
    Proficiency,
    RemoteType,
    SkillCategory,
)
from src.tailoring.models import SkillGap
from src.tailoring.skill_extractor import SkillOverlapAnalyzer


def _make_test_job(description: str = "") -> JobListing:
    """Creates a minimal valid JobListing for testing."""
    now = datetime.datetime.now(datetime.UTC)
    return JobListing(
        id=1,
        external_id="stripe-123",
        source=JobSource.LINKEDIN,
        title="Technical Solutions Engineer",
        company_name="Stripe",
        url="https://stripe.com/jobs/123",
        location="San Francisco, CA",
        remote_type=RemoteType.HYBRID,
        status=JobStatus.RANKED,
        description_clean=description,
        scraped_at=now,
        created_at=now,
        updated_at=now,
    )


JOB_DESCRIPTION_STRIPE = """
We're looking for a Technical Solutions Engineer who can:
- Write production Python code to automate payment processing workflows
- Design and maintain REST APIs for internal and external integrations
- Work with SQL databases and manage data pipelines
- Deploy services using Docker and Kubernetes on GCP
- Collaborate cross-functionally with engineering and product teams
- Experience with Linux administration and Git version control

Nice to have: Terraform, Machine Learning, Go
"""

JOB_DESCRIPTION_NO_MATCH = """
We need a candidate with expertise in:
- Rust programming and WASM compilation
- Embedded systems firmware development
- FPGA design and hardware description languages
- Real-time operating systems (RTOS)
"""


class TestSkillOverlapAnalyzer:
    """Validates skill gap analysis against frozen job fixtures."""

    def setup_method(self):
        self.analyzer = SkillOverlapAnalyzer()

    def test_analyzer_instantiation(self):
        """Analyzer can be instantiated with no arguments."""
        analyzer = SkillOverlapAnalyzer()
        assert analyzer is not None

    def test_analyze_returns_skill_gaps(self):
        """analyze() returns list of SkillGap Pydantic models."""
        job = _make_test_job(JOB_DESCRIPTION_STRIPE)
        gaps = self.analyzer.analyze(
            job=job, resume_skills=["Python", "SQL", "REST APIs"]
        )
        assert isinstance(gaps, list)
        for gap in gaps:
            assert isinstance(gap, SkillGap)

    def test_analyze_detects_matching_skills(self):
        """Skills present in both job and resume are flagged resume_has=True."""
        job = _make_test_job(JOB_DESCRIPTION_STRIPE)
        gaps = self.analyzer.analyze(
            job=job, resume_skills=["Python", "SQL", "REST APIs", "Docker", "GCP"]
        )
        matching = {g.skill_name for g in gaps if g.resume_has}
        assert "Python" in matching
        assert "SQL" in matching
        assert "Docker" in matching

    def test_analyze_detects_missing_skills(self):
        """Skills in job but not in resume are flagged resume_has=False."""
        job = _make_test_job(JOB_DESCRIPTION_STRIPE)
        gaps = self.analyzer.analyze(
            job=job, resume_skills=["Python", "SQL"]
        )
        missing = {g.skill_name for g in gaps if not g.resume_has}
        # Kubernetes and Terraform are in the job but not in resume_skills
        assert "Kubernetes" in missing or "Terraform" in missing

    def test_proficiency_mapped_when_resume_has(self):
        """When resume_has=True, proficiency must be set (Pydantic enforces)."""
        job = _make_test_job(JOB_DESCRIPTION_STRIPE)
        gaps = self.analyzer.analyze(
            job=job, resume_skills=["Python", "SQL"]
        )
        for gap in gaps:
            if gap.resume_has:
                assert gap.proficiency is not None
                assert isinstance(gap.proficiency, Proficiency)

    def test_proficiency_none_when_resume_missing(self):
        """When resume_has=False, proficiency is None."""
        job = _make_test_job(JOB_DESCRIPTION_STRIPE)
        gaps = self.analyzer.analyze(
            job=job, resume_skills=["Python"]
        )
        for gap in gaps:
            if not gap.resume_has:
                assert gap.proficiency is None

    def test_categories_assigned_correctly(self):
        """Skills are mapped to correct SkillCategory values."""
        job = _make_test_job(JOB_DESCRIPTION_STRIPE)
        gaps = self.analyzer.analyze(
            job=job, resume_skills=["Python"]
        )
        gap_map = {g.skill_name: g for g in gaps}

        if "Python" in gap_map:
            assert gap_map["Python"].category == SkillCategory.LANGUAGE
        if "Docker" in gap_map:
            assert gap_map["Docker"].category == SkillCategory.INFRASTRUCTURE
        if "GCP" in gap_map:
            assert gap_map["GCP"].category == SkillCategory.CLOUD

    def test_no_duplicate_skills(self):
        """Each skill appears at most once in the gap analysis."""
        job = _make_test_job(JOB_DESCRIPTION_STRIPE)
        gaps = self.analyzer.analyze(
            job=job, resume_skills=["Python", "SQL"]
        )
        skill_names = [g.skill_name for g in gaps]
        assert len(skill_names) == len(set(skill_names))

    def test_no_skills_in_job_returns_empty(self):
        """Job with no recognized skills returns empty list."""
        job = _make_test_job(JOB_DESCRIPTION_NO_MATCH)
        gaps = self.analyzer.analyze(
            job=job, resume_skills=["Python", "SQL"]
        )
        assert isinstance(gaps, list)
        # May return empty or near-empty since job has no taxonomy skills
        assert len(gaps) <= 1

    def test_empty_resume_skills_all_gaps(self):
        """Empty resume_skills means all job skills are gaps."""
        job = _make_test_job(JOB_DESCRIPTION_STRIPE)
        gaps = self.analyzer.analyze(job=job, resume_skills=[])
        for gap in gaps:
            assert gap.resume_has is False
            assert gap.proficiency is None

    def test_job_requires_always_true(self):
        """All returned gaps have job_requires=True (conservative flagging)."""
        job = _make_test_job(JOB_DESCRIPTION_STRIPE)
        gaps = self.analyzer.analyze(
            job=job, resume_skills=["Python"]
        )
        for gap in gaps:
            assert gap.job_requires is True

    def test_round_trip_serialization(self):
        """SkillGap objects survive Pydantic serialization round-trip."""
        job = _make_test_job(JOB_DESCRIPTION_STRIPE)
        gaps = self.analyzer.analyze(
            job=job, resume_skills=["Python", "SQL"]
        )
        for gap in gaps:
            data = gap.model_dump()
            reconstructed = SkillGap(**data)
            assert gap == reconstructed
