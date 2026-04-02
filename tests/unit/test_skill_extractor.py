"""
Ceal Phase 2: Skill Overlap Analyzer Tests

Validates that the SkillOverlapAnalyzer correctly identifies skill
gaps and overlaps between a job listing and candidate's resume.

Persona: [QA Lead] — gap analysis accuracy, contract verification
"""

import datetime

import pytest

from src.models.entities import JobListing, JobSource, JobStatus, RemoteType
from src.tailoring.models import SkillGap
from src.tailoring.skill_extractor import SkillOverlapAnalyzer


def _make_test_job(description: str | None = None) -> JobListing:
    """Creates a minimal valid JobListing for testing."""
    now = datetime.datetime.now(datetime.timezone.utc)
    desc = description or (
        "Requirements: Experience with Python, REST APIs, and SQL. "
        "Familiarity with cloud infrastructure (AWS, GCP). "
        "Strong debugging and troubleshooting skills."
    )
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
        description_raw=desc,
        description_clean=desc,
        scraped_at=now,
        created_at=now,
        updated_at=now,
    )


class TestSkillOverlapAnalyzer:
    """Validates analyzer behavior and interface contract."""

    def test_analyzer_returns_skill_gaps(self):
        """Analyzer returns a list of SkillGap models."""
        analyzer = SkillOverlapAnalyzer()
        job = _make_test_job()
        gaps = analyzer.analyze(job=job, resume_skills=["Python", "SQL"])
        assert isinstance(gaps, list)
        assert all(isinstance(g, SkillGap) for g in gaps)
        assert len(gaps) > 0

    def test_analyzer_detects_overlaps(self):
        """Skills present in both job and resume are flagged as resume_has=True."""
        analyzer = SkillOverlapAnalyzer()
        job = _make_test_job()
        gaps = analyzer.analyze(
            job=job,
            resume_skills=["Python", "REST APIs", "SQL"],
        )
        python_gap = next((g for g in gaps if g.skill_name == "Python"), None)
        assert python_gap is not None
        assert python_gap.resume_has is True

    def test_analyzer_detects_missing_skills(self):
        """Skills in job but not resume are flagged as resume_has=False."""
        analyzer = SkillOverlapAnalyzer()
        job = _make_test_job()
        gaps = analyzer.analyze(job=job, resume_skills=[])
        assert all(g.resume_has is False for g in gaps)

    def test_analyzer_instantiation(self):
        """Analyzer can be instantiated with no arguments."""
        analyzer = SkillOverlapAnalyzer()
        assert analyzer is not None
