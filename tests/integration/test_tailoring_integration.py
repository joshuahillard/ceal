"""
Ceal Phase 2: Tailoring Integration Tests

End-to-end tests for the parser + extractor pipeline and the
4-stage async pipeline with the tailor stage.

Tests use frozen fixtures with known resume text and mocked LLM responses.

Persona: [QA Lead] -- integration coverage, pipeline wiring verification
"""
from __future__ import annotations

import asyncio
import datetime
import json
from unittest.mock import AsyncMock, patch

import pytest

from src.models.entities import (
    JobListing,
    JobSource,
    JobStatus,
    Proficiency,
    RemoteType,
    SkillCategory,
)
from src.tailoring.engine import TailoringEngine
from src.tailoring.models import (
    ParsedResume,
    ResumeSection,
    SkillGap,
    TailoringRequest,
    TailoringResult,
)
from src.tailoring.resume_parser import ResumeProfileParser
from src.tailoring.skill_extractor import SkillOverlapAnalyzer

# ---------------------------------------------------------------------------
# Frozen Fixtures
# ---------------------------------------------------------------------------

JOSH_RESUME_FIXTURE = """
Josh Hillard
Boston, MA

SUMMARY:
Technical leader with 6+ years in SaaS escalation management.

EXPERIENCE:
- Manager II, Technical Escalations at Toast, Inc.
  * Identified critical firmware defects saving Toast estimated $12 million
  * Reduced recurring issue volume by 37% via cross-functional collaboration
  * Created enablement materials and onboarding frameworks

SKILLS:
Python, SQL, REST APIs, Linux, Docker, GCP, asyncio, Git
Escalation Management, Cross-Functional Leadership, Payment Processing

PROJECTS:
- Moss Lane Trading Bot
  * Production autonomous trading system with 5 API integrations
  * Python, asyncio, systemd, SQL

CERTIFICATIONS:
- Google AI Essentials - Professional Certificate (2026)
""".strip()


def _make_job(description: str, tier: int = 1) -> JobListing:
    now = datetime.datetime.now(datetime.UTC)
    return JobListing(
        id=1,
        external_id="test-job-1",
        source=JobSource.LINKEDIN,
        title="Technical Solutions Engineer",
        company_name="Stripe",
        url="https://stripe.com/jobs/1",
        location="San Francisco, CA",
        remote_type=RemoteType.HYBRID,
        status=JobStatus.RANKED,
        company_tier=tier,
        description_clean=description,
        scraped_at=now,
        created_at=now,
        updated_at=now,
    )


STRIPE_JOB_DESC = """
Requirements:
- Strong Python programming skills
- Experience with REST APIs and SQL databases
- Docker and Kubernetes deployment experience
- Payment processing domain knowledge
- Cross-functional collaboration with engineering teams
- GCP or AWS cloud infrastructure experience
"""

NO_MATCH_JOB_DESC = """
Requirements:
- Rust programming and WASM expertise
- Embedded systems and FPGA design
- RTOS experience
"""

VALID_LLM_RESPONSE = json.dumps({
    "tailored_bullets": [
        {
            "original": "Identified critical firmware defects saving Toast estimated $12 million",
            "rewritten_text": (
                "Accomplished $12M in cost avoidance as measured by "
                "defect resolution rate, by doing systematic firmware "
                "root cause analysis across deployed POS infrastructure"
            ),
            "xyz_format": True,
            "relevance_score": 0.95,
        },
    ],
    "skill_gaps": [
        {
            "skill_name": "Python",
            "category": "language",
            "job_requires": True,
            "resume_has": True,
            "proficiency": "proficient",
        },
        {
            "skill_name": "Kubernetes",
            "category": "infrastructure",
            "job_requires": True,
            "resume_has": False,
            "proficiency": None,
        },
    ],
})


# ---------------------------------------------------------------------------
# End-to-End: parse() -> analyze() -> validated output
# ---------------------------------------------------------------------------

class TestParserExtractorIntegration:
    """Tests raw resume text -> parse() -> analyze() -> validated output."""

    def test_end_to_end_parse_and_analyze(self):
        """Full pipeline: raw text -> ParsedResume -> SkillGaps."""
        parser = ResumeProfileParser()
        analyzer = SkillOverlapAnalyzer()

        # Step 1: Parse resume
        parsed = parser.parse(profile_id=1, raw_text=JOSH_RESUME_FIXTURE)
        assert isinstance(parsed, ParsedResume)
        assert len(parsed.sections) > 0

        # Step 2: Extract skills from parsed bullets
        resume_skills = list({
            skill for b in parsed.sections for skill in b.skills_referenced
        })
        assert len(resume_skills) > 0

        # Step 3: Analyze gaps
        job = _make_job(STRIPE_JOB_DESC)
        gaps = analyzer.analyze(job=job, resume_skills=resume_skills)

        assert len(gaps) > 0
        matching = [g for g in gaps if g.resume_has]
        missing = [g for g in gaps if not g.resume_has]
        assert len(matching) > 0
        assert len(missing) > 0

    def test_integration_with_josh_resume_fixture(self):
        """Test with Josh's actual resume content (frozen fixture)."""
        parser = ResumeProfileParser()
        parsed = parser.parse(profile_id=1, raw_text=JOSH_RESUME_FIXTURE)

        # Verify all expected sections are found
        sections = {b.section for b in parsed.sections}
        assert ResumeSection.EXPERIENCE in sections
        assert ResumeSection.SKILLS in sections

        # Verify metrics extracted
        all_metrics = [m for b in parsed.sections for m in b.metrics]
        metric_text = " ".join(all_metrics)
        assert "$12" in metric_text or "12 million" in metric_text
        assert "37%" in metric_text

    def test_resume_with_no_metrics(self):
        """Resume with no metrics still produces valid ParsedResume."""
        no_metrics = """
EXPERIENCE:
- Managed a team of technical consultants
- Led cross-functional projects for product quality

SKILLS:
Python, SQL, REST APIs
""".strip()
        parser = ResumeProfileParser()
        parsed = parser.parse(profile_id=1, raw_text=no_metrics)
        assert isinstance(parsed, ParsedResume)
        for b in parsed.sections:
            assert b.metrics == []

    def test_resume_with_unusual_section_headers(self):
        """Resume with PROFESSIONAL SUMMARY, WORK EXPERIENCE still parsed."""
        unusual = """
PROFESSIONAL SUMMARY:
Experienced engineer with deep technical background.

WORK EXPERIENCE:
- Built distributed systems for data processing
- Deployed microservices architecture

TECHNICAL SKILLS:
Python, Go, Kubernetes
""".strip()
        parser = ResumeProfileParser()
        parsed = parser.parse(profile_id=1, raw_text=unusual)
        sections = {b.section for b in parsed.sections}
        assert ResumeSection.SUMMARY in sections
        assert ResumeSection.EXPERIENCE in sections

    def test_job_with_skills_not_in_resume(self):
        """Job requiring skills not in resume produces gaps."""
        parser = ResumeProfileParser()
        analyzer = SkillOverlapAnalyzer()

        parsed = parser.parse(profile_id=1, raw_text=JOSH_RESUME_FIXTURE)
        resume_skills = list({
            skill for b in parsed.sections for skill in b.skills_referenced
        })

        job = _make_job(NO_MATCH_JOB_DESC)
        gaps = analyzer.analyze(job=job, resume_skills=resume_skills)

        # Should have few or no matches since the job is Rust/FPGA
        matching = [g for g in gaps if g.resume_has]
        assert len(matching) == 0 or len(matching) <= 1


# ---------------------------------------------------------------------------
# TailoringEngine Integration (with mocked API)
# ---------------------------------------------------------------------------

class TestTailoringEngineIntegration:
    """Tests full tailoring flow with frozen LLM responses."""

    def _mock_api(self, response_text: str):
        from unittest.mock import MagicMock

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "content": [{"text": response_text}],
        }
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        return mock_client

    @pytest.mark.asyncio
    async def test_full_tailoring_flow(self):
        """parse -> analyze -> tailor -> validated TailoringResult."""
        parser = ResumeProfileParser()
        analyzer = SkillOverlapAnalyzer()
        engine = TailoringEngine(api_key="test-key")

        # Parse
        parsed = parser.parse(profile_id=1, raw_text=JOSH_RESUME_FIXTURE)
        resume_bullets = [b.original_text for b in parsed.sections]
        resume_skills = list({
            skill for b in parsed.sections for skill in b.skills_referenced
        })

        # Analyze
        job = _make_job(STRIPE_JOB_DESC)
        gaps = analyzer.analyze(job=job, resume_skills=resume_skills)

        # Tailor
        request = TailoringRequest(
            job_id=1, profile_id=1, target_tier=1,
            emphasis_areas=[g.skill_name for g in gaps if g.resume_has],
        )

        with patch("src.tailoring.engine.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = self._mock_api(VALID_LLM_RESPONSE)

            result = await engine.generate_tailored_profile(
                request=request,
                resume_bullets=resume_bullets,
                skill_gaps=gaps,
            )

        assert isinstance(result, TailoringResult)
        assert len(result.tailored_bullets) == 1
        assert result.tailored_bullets[0].xyz_format is True
        assert result.tailoring_version.startswith("v")

    @pytest.mark.asyncio
    async def test_graceful_degradation_on_api_failure(self):
        """LLM API failure raises but doesn't hang."""
        engine = TailoringEngine(api_key="test-key")

        with patch("src.tailoring.engine.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post.side_effect = Exception("API timeout")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            with pytest.raises(Exception, match="API timeout"):
                await engine.generate_tailored_profile(
                    request=TailoringRequest(
                        job_id=1, profile_id=1, target_tier=1,
                    ),
                )


# ---------------------------------------------------------------------------
# Pipeline Queue Backpressure Tests
# ---------------------------------------------------------------------------

class TestPipelineBackpressure:
    """Tests queue-based backpressure behavior."""

    @pytest.mark.asyncio
    async def test_bounded_queue_maxsize(self):
        """Queues with maxsize enforce backpressure."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=2)
        await queue.put("item1")
        await queue.put("item2")
        assert queue.full()

    @pytest.mark.asyncio
    async def test_sentinel_shutdown_propagation(self):
        """Shutdown sentinel propagates through queue chain."""
        from src.main import _SHUTDOWN

        q = asyncio.Queue()
        await q.put("data")
        await q.put(_SHUTDOWN)

        item1 = await q.get()
        assert item1 == "data"
        item2 = await q.get()
        assert item2 is _SHUTDOWN
