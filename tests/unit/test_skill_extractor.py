"""
Céal Phase 2: Skill Overlap Analyzer Stub Tests

Validates that the SkillOverlapAnalyzer stub raises NotImplementedError
until Wednesday's implementation session.

Persona: [QA Lead] — stub coverage, interface contract verification
"""

import datetime

import pytest

from src.models.entities import JobListing, JobSource, JobStatus, RemoteType
from src.tailoring.skill_extractor import SkillOverlapAnalyzer


def _make_test_job() -> JobListing:
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
        scraped_at=now,
        created_at=now,
        updated_at=now,
    )


class TestSkillOverlapAnalyzer:
    """Validates analyzer stub behavior and interface contract."""

    def test_analyzer_raises_not_implemented(self):
        """
        The analyzer stub must raise NotImplementedError.
        Gate for Wed 4/1 implementation session.
        """
        analyzer = SkillOverlapAnalyzer()
        job = _make_test_job()
        with pytest.raises(NotImplementedError):
            analyzer.analyze(job=job, resume_skills=["Python", "SQL"])

    def test_analyzer_accepts_correct_signature(self):
        """
        Verify the analyzer interface accepts a JobListing and
        list of skill names. Confirms interface stability.
        """
        analyzer = SkillOverlapAnalyzer()
        job = _make_test_job()
        with pytest.raises(NotImplementedError):
            analyzer.analyze(
                job=job,
                resume_skills=["Python", "REST APIs", "Payment Processing"],
            )

    def test_analyzer_instantiation(self):
        """Analyzer can be instantiated with no arguments."""
        analyzer = SkillOverlapAnalyzer()
        assert analyzer is not None
