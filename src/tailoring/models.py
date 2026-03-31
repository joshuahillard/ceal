"""
Ceal Phase 2: Resume Tailoring Data Models

Enforces strict boundaries between the normalizer, ranker, and tailoring engine.
All models utilize Pydantic v2 validators to enforce business rules and X-Y-Z formatting.

DPM Scope Lock: Every model maps directly to the Phase 2 deliverable —
automating the translation of experience into bespoke, role-specific
value propositions. TailoringRequest.target_tier enforces campaign
strategy alignment (Tier 1 Apply Now / Tier 2 Credential / Tier 3 Campaign).

Interview talking point:
    "I enforced strict Pydantic v2 data contracts on all LLM-generated
    resume content — including a model_validator that programmatically
    rejects any bullet claiming X-Y-Z format if it lacks the required
    structural clauses. Zero malformed records reach the application CRM."
"""
from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

# Re-using entities from Phase 1 to maintain normalized data structures
from src.models.entities import Proficiency, SkillCategory


# ---------------------------------------------------------------------------
# Resume Section Enum
# ---------------------------------------------------------------------------

class ResumeSection(str, Enum):
    """Sections of a parsed resume document."""
    SUMMARY = "SUMMARY"
    EXPERIENCE = "EXPERIENCE"
    SKILLS = "SKILLS"
    PROJECTS = "PROJECTS"
    CERTIFICATIONS = "CERTIFICATIONS"


# ---------------------------------------------------------------------------
# Resume Parsing Models
# ---------------------------------------------------------------------------

class ParsedBullet(BaseModel):
    """Represents a single atomic bullet point from a resume."""
    section: ResumeSection
    original_text: str = Field(..., min_length=10)
    skills_referenced: List[str] = Field(default_factory=list)
    metrics: List[str] = Field(default_factory=list)

    @field_validator("original_text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Parsed bullet text cannot be empty.")
        return v.strip()


class ParsedResume(BaseModel):
    """The structured hierarchy of the parsed master resume."""
    profile_id: int
    sections: List[ParsedBullet] = Field(default_factory=list)
    raw_text: str

    @model_validator(mode="after")
    def ensure_data_integrity(self) -> "ParsedResume":
        if not self.sections and not self.raw_text:
            raise ValueError(
                "ParsedResume must contain extracted sections or raw text fallback."
            )
        return self


# ---------------------------------------------------------------------------
# Skill Gap Analysis Models
# ---------------------------------------------------------------------------

class SkillGap(BaseModel):
    """Identifies overlaps and missing requirements for a specific listing."""
    skill_name: str
    category: SkillCategory
    job_requires: bool = True
    resume_has: bool = False
    proficiency: Optional[Proficiency] = None

    @model_validator(mode="after")
    def validate_proficiency_logic(self) -> "SkillGap":
        if self.resume_has and not self.proficiency:
            raise ValueError(
                "If resume_has is True, candidate proficiency must be mapped."
            )
        return self


# ---------------------------------------------------------------------------
# Tailoring Request — strict payload to LLM engine
# ---------------------------------------------------------------------------

class TailoringRequest(BaseModel):
    """The strict payload sent to the LLM tailoring engine."""
    job_id: int
    profile_id: int
    target_tier: int = Field(..., ge=1, le=3)
    emphasis_areas: List[str] = Field(default_factory=list)

    @field_validator("target_tier")
    @classmethod
    def validate_strategy_tier(cls, v: int) -> int:
        # Belt-and-suspenders: Field(ge=1, le=3) handles range,
        # this validator enforces business-rule semantics.
        if v not in [1, 2, 3]:
            raise ValueError(
                "Tier must align with strategy: "
                "1 (Apply Now), 2 (Credential), or 3 (Campaign)."
            )
        return v


# ---------------------------------------------------------------------------
# Tailored Output Models
# ---------------------------------------------------------------------------

class TailoredBullet(BaseModel):
    """A rewritten resume bullet formatted for the specific job listing."""
    original: str
    rewritten_text: str
    xyz_format: bool = False
    relevance_score: float = Field(..., ge=0.0, le=1.0)

    @model_validator(mode="after")
    def enforce_xyz_compliance(self) -> "TailoredBullet":
        """
        Strict validation for Google X-Y-Z formatting logic.

        Format: "Accomplished [X] as measured by [Y], by doing [Z]"

        Zero-defect rule: if xyz_format is True, BOTH structural clauses
        must be present. A bullet missing either clause is malformed.
        """
        if self.xyz_format:
            text = self.rewritten_text.lower()
            has_measured_by = "measured by" in text
            has_by_doing = "by doing" in text
            if not has_measured_by or not has_by_doing:
                missing = []
                if not has_measured_by:
                    missing.append('"as measured by [Y]"')
                if not has_by_doing:
                    missing.append('"by doing [Z]"')
                raise ValueError(
                    f"xyz_format marked True but missing X-Y-Z structural "
                    f"clause(s): {', '.join(missing)}"
                )
        return self


class TailoringResult(BaseModel):
    """The final output contract from the tailoring stage."""
    request: TailoringRequest
    tailored_bullets: List[TailoredBullet]
    skill_gaps: List[SkillGap]
    tailoring_version: str

    @field_validator("tailoring_version")
    @classmethod
    def validate_versioning(cls, v: str) -> str:
        if not v.startswith("v"):
            raise ValueError(
                "tailoring_version must track prompt iterations (e.g., v1.0)."
            )
        return v
