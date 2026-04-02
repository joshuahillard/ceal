"""
Ceal Phase 2: Demo Mode Unit Tests

Validates the demo pipeline components: job construction, resume parsing,
skill gap analysis, and error handling for missing files.
"""
from __future__ import annotations

import datetime
import os
import tempfile

import pytest

from src.demo import _build_demo_job, run_demo
from src.models.entities import JobListing, JobSource, JobStatus
from src.tailoring.models import SkillGap
from src.tailoring.resume_parser import ResumeProfileParser
from src.tailoring.skill_extractor import SkillOverlapAnalyzer


class TestBuildDemoJob:
    """Tests for the _build_demo_job helper."""

    def test_build_demo_job_returns_valid_job_listing(self):
        """Build a demo JobListing from a description string."""
        desc = "We need a Python developer with REST API experience."
        job = _build_demo_job(desc)
        assert isinstance(job, JobListing)
        assert job.description_clean == desc
        assert job.description_raw == desc
        assert job.source == JobSource.MANUAL
        assert job.id == 0
        assert job.external_id == "demo-001"
        assert job.status == JobStatus.SCRAPED

    def test_build_demo_job_with_empty_description(self):
        """Empty description still returns a valid JobListing."""
        job = _build_demo_job("")
        assert isinstance(job, JobListing)
        assert job.description_clean == ""

    def test_build_demo_job_has_timestamps(self):
        """Demo job has valid datetime fields."""
        job = _build_demo_job("test")
        assert isinstance(job.scraped_at, datetime.datetime)
        assert isinstance(job.created_at, datetime.datetime)
        assert isinstance(job.updated_at, datetime.datetime)


class TestDemoResumeParsing:
    """Tests that the demo pipeline correctly parses resume files."""

    def test_demo_parses_resume_file(self):
        """Parser extracts sections from a well-formatted resume."""
        resume_text = """PROFESSIONAL SUMMARY
Experienced engineer with 10+ years building production Python applications.

EXPERIENCE
Acme Corp — Senior Engineer (2020 – 2024)
- Built REST API services handling 10,000 requests per second using Python and asyncio
- Reduced deployment time by 40% through CI/CD pipeline automation with GitHub Actions
- Managed team of 5 engineers across 3 cross-functional projects

SKILLS
- Technical: Python, SQL, REST APIs, Docker, Git
- Leadership: Project Management, Cross-Functional Leadership
"""
        parser = ResumeProfileParser()
        result = parser.parse(profile_id=1, raw_text=resume_text)
        sections_found = set(b.section.value for b in result.sections)
        assert "EXPERIENCE" in sections_found
        assert "SKILLS" in sections_found
        assert len(result.sections) >= 3


class TestDemoSkillGapAnalysis:
    """Tests skill gap analysis in demo context."""

    def test_demo_skill_gap_analysis_offline(self):
        """Skill gap analysis detects overlaps and gaps correctly."""
        job = _build_demo_job(
            "Requirements: Experience with Python, SQL, and REST APIs. "
            "Familiarity with cloud infrastructure (AWS, GCP)."
        )
        resume_skills = ["Python", "SQL", "Docker"]
        analyzer = SkillOverlapAnalyzer()
        gaps = analyzer.analyze(job=job, resume_skills=resume_skills)

        assert isinstance(gaps, list)
        assert all(isinstance(g, SkillGap) for g in gaps)

        # Python and SQL should be detected as overlaps
        has_skills = {g.skill_name for g in gaps if g.resume_has}
        missing_skills = {g.skill_name for g in gaps if not g.resume_has}
        assert "Python" in has_skills
        assert "SQL" in has_skills
        # AWS should be a gap (not in resume_skills)
        assert "AWS" in missing_skills


class TestDemoErrorHandling:
    """Tests error handling for missing files."""

    def test_demo_handles_missing_resume_file(self):
        """Demo exits with error for nonexistent resume path."""
        with pytest.raises(SystemExit):
            import asyncio
            asyncio.run(run_demo(
                resume_path="/nonexistent/resume.txt",
                job_path="/nonexistent/job.txt",
            ))

    def test_demo_handles_missing_job_file(self):
        """Demo exits with error for nonexistent job path."""
        # Create a real resume file but fake job path
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8",
        ) as f:
            f.write("EXPERIENCE\n- Did some work at a company for 3 years\n")
            resume_path = f.name

        try:
            with pytest.raises(SystemExit):
                import asyncio
                asyncio.run(run_demo(
                    resume_path=resume_path,
                    job_path="/nonexistent/job.txt",
                ))
        finally:
            os.unlink(resume_path)
