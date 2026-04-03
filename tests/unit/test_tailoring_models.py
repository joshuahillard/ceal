"""
Céal Phase 2: Tailoring Model Validation Tests

Tests the Pydantic v2 data contracts that guard the tailoring pipeline.
Written BEFORE implementation logic (TDD discipline).

Every test constructs data through the model hierarchy — no raw dicts
bypass validation. This mirrors the zero-defect rule: if the model
accepts it, the pipeline trusts it.

Personas:
    [Backend Engineer] — Pydantic boundary enforcement
    [QA Lead] — edge cases, rejection paths, enum coverage

Interview talking point:
    "I wrote validation tests before the implementation existed.
    The Pydantic models are the spec — if the test passes, the
    contract is enforceable. TDD at the data layer."
"""

import pytest
from pydantic import ValidationError

from src.models.entities import Proficiency, SkillCategory
from src.tailoring.models import (
    ParsedBullet,
    ParsedResume,
    ResumeSection,
    SkillGap,
    TailoredBullet,
    TailoringRequest,
    TailoringResult,
)

# ---------------------------------------------------------------------------
# ParsedBullet Tests
# ---------------------------------------------------------------------------

class TestParsedBullet:
    """Validates the atomic resume bullet extraction contract."""

    def test_valid_bullet_happy_path(self):
        """A well-formed bullet with all fields passes validation."""
        bullet = ParsedBullet(
            section=ResumeSection.EXPERIENCE,
            original_text="Saved Toast estimated $12 million identifying critical firmware defects",
            skills_referenced=["firmware debugging", "root cause analysis"],
            metrics=["$12M"],
        )
        assert bullet.section == ResumeSection.EXPERIENCE
        assert bullet.original_text.startswith("Saved Toast")
        assert len(bullet.skills_referenced) == 2
        assert bullet.metrics == ["$12M"]

    def test_empty_text_rejected(self):
        """
        original_text has min_length=10. Empty or whitespace-only text
        must be rejected — the parser should never produce empty bullets.
        """
        with pytest.raises(ValidationError) as exc_info:
            ParsedBullet(
                section=ResumeSection.SKILLS,
                original_text="",
            )
        errors = exc_info.value.errors()
        assert any("min_length" in str(e) or "at least" in str(e).lower() for e in errors)

    def test_whitespace_only_text_rejected(self):
        """Whitespace-only text is stripped and then fails min_length."""
        with pytest.raises(ValidationError):
            ParsedBullet(
                section=ResumeSection.SKILLS,
                original_text="         ",
            )

    def test_short_text_rejected(self):
        """Text under 10 chars is rejected (enforces meaningful content)."""
        with pytest.raises(ValidationError):
            ParsedBullet(
                section=ResumeSection.EXPERIENCE,
                original_text="Short",
            )

    def test_defaults_for_optional_fields(self):
        """skills_referenced and metrics default to empty lists."""
        bullet = ParsedBullet(
            section=ResumeSection.PROJECTS,
            original_text="Built a production trading system on cloud infrastructure",
        )
        assert bullet.skills_referenced == []
        assert bullet.metrics == []

    def test_all_resume_sections_accepted(self):
        """Every ResumeSection enum value is valid for ParsedBullet.section."""
        for section in ResumeSection:
            bullet = ParsedBullet(
                section=section,
                original_text=f"Valid bullet for {section.value} section of the resume",
            )
            assert bullet.section == section


# ---------------------------------------------------------------------------
# ParsedResume Tests
# ---------------------------------------------------------------------------

class TestParsedResume:
    """Validates the structured resume hierarchy contract."""

    def test_valid_resume_with_sections(self):
        """A resume with extracted sections passes validation."""
        resume = ParsedResume(
            profile_id=1,
            sections=[
                ParsedBullet(
                    section=ResumeSection.EXPERIENCE,
                    original_text="Saved Toast estimated $12 million identifying critical firmware defects",
                ),
            ],
            raw_text="Full resume text...",
        )
        assert resume.profile_id == 1
        assert len(resume.sections) == 1

    def test_resume_with_raw_text_only(self):
        """
        If section extraction fails, raw_text fallback is preserved.
        The model_validator allows this — the pipeline never drops content.
        """
        resume = ParsedResume(
            profile_id=1,
            sections=[],
            raw_text="Fallback raw resume text that couldn't be parsed into sections",
        )
        assert resume.sections == []
        assert resume.raw_text.startswith("Fallback")

    def test_empty_resume_rejected(self):
        """
        A resume with no sections AND no raw_text is invalid.
        The model_validator enforces at least one source of content.
        """
        with pytest.raises(ValidationError) as exc_info:
            ParsedResume(
                profile_id=1,
                sections=[],
                raw_text="",
            )
        assert "must contain" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# SkillGap Tests
# ---------------------------------------------------------------------------

class TestSkillGap:
    """Validates the skill overlap analysis contract."""

    def test_valid_skill_gap_resume_has(self):
        """A skill the candidate has requires a proficiency level."""
        gap = SkillGap(
            skill_name="Python",
            category=SkillCategory.LANGUAGE,
            job_requires=True,
            resume_has=True,
            proficiency=Proficiency.PROFICIENT,
        )
        assert gap.resume_has is True
        assert gap.proficiency == Proficiency.PROFICIENT

    def test_valid_skill_gap_resume_missing(self):
        """A skill the candidate lacks doesn't need proficiency."""
        gap = SkillGap(
            skill_name="Kubernetes",
            category=SkillCategory.INFRASTRUCTURE,
            job_requires=True,
            resume_has=False,
            proficiency=None,
        )
        assert gap.resume_has is False
        assert gap.proficiency is None

    def test_resume_has_without_proficiency_rejected(self):
        """
        If resume_has is True, proficiency MUST be set.
        The model_validator enforces this business rule —
        you can't claim to have a skill without stating your level.
        """
        with pytest.raises(ValidationError) as exc_info:
            SkillGap(
                skill_name="Go",
                category=SkillCategory.LANGUAGE,
                job_requires=True,
                resume_has=True,
                proficiency=None,  # Missing!
            )
        assert "proficiency" in str(exc_info.value).lower()

    def test_all_categories_accepted(self):
        """Every SkillCategory enum value is valid."""
        for cat in SkillCategory:
            gap = SkillGap(
                skill_name=f"Skill in {cat.value}",
                category=cat,
                job_requires=True,
                resume_has=False,
            )
            assert gap.category == cat

    def test_round_trip_serialization(self):
        """Pydantic → dict → Pydantic preserves all fields."""
        original = SkillGap(
            skill_name="SQLAlchemy",
            category=SkillCategory.FRAMEWORK,
            job_requires=True,
            resume_has=True,
            proficiency=Proficiency.PROFICIENT,
        )
        data = original.model_dump()
        reconstructed = SkillGap(**data)
        assert original == reconstructed


# ---------------------------------------------------------------------------
# TailoringRequest Tests
# ---------------------------------------------------------------------------

class TestTailoringRequest:
    """Validates the LLM tailoring payload contract."""

    def test_valid_tier_1_request(self):
        """A Tier 1 (Apply Now) request passes validation."""
        req = TailoringRequest(
            job_id=42,
            profile_id=1,
            target_tier=1,
            emphasis_areas=["payment systems", "technical escalation"],
        )
        assert req.target_tier == 1
        assert req.job_id == 42

    def test_tier_bounds_lower(self):
        """target_tier below 1 is rejected."""
        with pytest.raises(ValidationError):
            TailoringRequest(
                job_id=1, profile_id=1, target_tier=0,
            )

    def test_tier_bounds_upper(self):
        """target_tier above 3 is rejected."""
        with pytest.raises(ValidationError):
            TailoringRequest(
                job_id=1, profile_id=1, target_tier=4,
            )

    def test_all_tiers_accepted(self):
        """Tiers 1, 2, and 3 all pass validation."""
        for tier in [1, 2, 3]:
            req = TailoringRequest(
                job_id=1, profile_id=1, target_tier=tier,
            )
            assert req.target_tier == tier

    def test_emphasis_areas_defaults_empty(self):
        """emphasis_areas defaults to empty list when omitted."""
        req = TailoringRequest(
            job_id=1, profile_id=1, target_tier=2,
        )
        assert req.emphasis_areas == []


# ---------------------------------------------------------------------------
# TailoredBullet Tests
# ---------------------------------------------------------------------------

class TestTailoredBullet:
    """Validates the LLM-rewritten bullet contract."""

    def test_valid_xyz_bullet(self):
        """A properly formatted X-Y-Z bullet passes validation."""
        bullet = TailoredBullet(
            original="Saved Toast $12M by finding firmware bugs",
            rewritten_text=(
                "Accomplished $12M in cost avoidance as measured by "
                "defect resolution rate, by doing systematic firmware "
                "root cause analysis across 50K+ deployed POS devices"
            ),
            xyz_format=True,
            relevance_score=0.95,
        )
        assert bullet.xyz_format is True
        assert bullet.relevance_score == 0.95

    def test_score_lower_bound(self):
        """relevance_score at 0.0 is valid."""
        bullet = TailoredBullet(
            original="Some experience",
            rewritten_text="Not very relevant to this role but included for completeness",
            xyz_format=False,
            relevance_score=0.0,
        )
        assert bullet.relevance_score == 0.0

    def test_score_upper_bound(self):
        """relevance_score at 1.0 is valid."""
        bullet = TailoredBullet(
            original="Core experience",
            rewritten_text="Directly applicable experience measured by outcomes, by doing the exact role requirements",
            xyz_format=False,
            relevance_score=1.0,
        )
        assert bullet.relevance_score == 1.0

    def test_score_below_zero_rejected(self):
        """relevance_score below 0.0 is rejected."""
        with pytest.raises(ValidationError):
            TailoredBullet(
                original="Test",
                rewritten_text="Test rewrite",
                xyz_format=False,
                relevance_score=-0.1,
            )

    def test_score_above_one_rejected(self):
        """relevance_score above 1.0 is rejected."""
        with pytest.raises(ValidationError):
            TailoredBullet(
                original="Test",
                rewritten_text="Test rewrite",
                xyz_format=False,
                relevance_score=1.01,
            )

    def test_xyz_flag_true_missing_measured_by_rejected(self):
        """
        If xyz_format=True, the text MUST contain 'measured by'.
        This is the zero-defect rule: no malformed X-Y-Z bullets
        reach the application CRM.
        """
        with pytest.raises(ValidationError) as exc_info:
            TailoredBullet(
                original="Test",
                rewritten_text="Did something great by doing some work",
                xyz_format=True,
                relevance_score=0.8,
            )
        assert "measured by" in str(exc_info.value).lower()

    def test_xyz_flag_true_missing_by_doing_rejected(self):
        """If xyz_format=True, the text MUST contain 'by doing'."""
        with pytest.raises(ValidationError) as exc_info:
            TailoredBullet(
                original="Test",
                rewritten_text="Accomplished X as measured by Y but no doing clause",
                xyz_format=True,
                relevance_score=0.8,
            )
        assert "by doing" in str(exc_info.value).lower()

    def test_xyz_flag_false_skips_clause_check(self):
        """
        When xyz_format=False, the structural clause check is skipped.
        Non-X-Y-Z bullets are valid without the clauses.
        """
        bullet = TailoredBullet(
            original="Led team of 5",
            rewritten_text="Directed cross-functional team of senior consultants",
            xyz_format=False,
            relevance_score=0.7,
        )
        assert bullet.xyz_format is False


# ---------------------------------------------------------------------------
# TailoringResult Tests
# ---------------------------------------------------------------------------

class TestTailoringResult:
    """Validates the composite output contract from the tailoring stage."""

    def _make_valid_result(self, version: str = "v1.0") -> TailoringResult:
        """Helper to build a valid TailoringResult."""
        return TailoringResult(
            request=TailoringRequest(
                job_id=1, profile_id=1, target_tier=1,
            ),
            tailored_bullets=[
                TailoredBullet(
                    original="Saved $12M",
                    rewritten_text=(
                        "Accomplished $12M in cost savings as measured by "
                        "annual defect reduction, by doing firmware root cause analysis"
                    ),
                    xyz_format=True,
                    relevance_score=0.95,
                ),
            ],
            skill_gaps=[
                SkillGap(
                    skill_name="Python",
                    category=SkillCategory.LANGUAGE,
                    job_requires=True,
                    resume_has=True,
                    proficiency=Proficiency.PROFICIENT,
                ),
            ],
            tailoring_version=version,
        )

    def test_valid_result_assembly(self):
        """A complete TailoringResult with all components passes."""
        result = self._make_valid_result()
        assert len(result.tailored_bullets) == 1
        assert len(result.skill_gaps) == 1
        assert result.tailoring_version == "v1.0"

    def test_version_must_start_with_v(self):
        """
        tailoring_version must start with 'v' for prompt iteration tracking.
        This enables A/B testing of prompt versions against response rates.
        """
        with pytest.raises(ValidationError) as exc_info:
            self._make_valid_result(version="1.0")
        assert "tailoring_version" in str(exc_info.value).lower()

    def test_version_valid_formats(self):
        """Various version formats starting with 'v' are accepted."""
        for version in ["v1.0", "v2.0-beta", "v0.1", "v10.3.1"]:
            result = self._make_valid_result(version=version)
            assert result.tailoring_version == version

    def test_empty_bullets_allowed(self):
        """
        An empty tailored_bullets list is valid — the LLM might determine
        no bullets are worth tailoring for a low-match listing.
        """
        result = TailoringResult(
            request=TailoringRequest(
                job_id=1, profile_id=1, target_tier=3,
            ),
            tailored_bullets=[],
            skill_gaps=[],
            tailoring_version="v1.0",
        )
        assert result.tailored_bullets == []
        assert result.skill_gaps == []
