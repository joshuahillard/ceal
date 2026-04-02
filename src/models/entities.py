"""
Céal: Pydantic Data Models (Validation Layer)

These models enforce data contracts at every pipeline boundary.
The scraper produces RawJobListing → normalizer validates into JobListingCreate
→ ranker enriches into RankedJobListing → database receives clean data.

Interview talking point:
    "Pydantic models act as schema enforcement at the application boundary,
    so corrupt or incomplete data is rejected before it touches the database.
    This is the same pattern FastAPI uses internally."
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

# ---------------------------------------------------------------------------
# Enums — constrained at the type level, not just string checks
# ---------------------------------------------------------------------------

class JobSource(str, Enum):
    """Where the listing was scraped from."""
    LINKEDIN = "linkedin"
    INDEED = "indeed"
    GOOGLE_JOBS = "google_jobs"
    MANUAL = "manual"


class RemoteType(str, Enum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    UNKNOWN = "unknown"


class JobStatus(str, Enum):
    """State machine for job application lifecycle."""
    SCRAPED = "scraped"
    RANKED = "ranked"
    APPLIED = "applied"
    RESPONDED = "responded"
    INTERVIEWING = "interviewing"
    OFFER = "offer"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class SkillCategory(str, Enum):
    LANGUAGE = "language"
    FRAMEWORK = "framework"
    INFRASTRUCTURE = "infrastructure"
    DATABASE = "database"
    CLOUD = "cloud"
    METHODOLOGY = "methodology"
    SOFT_SKILL = "soft_skill"
    DOMAIN = "domain"
    TOOL = "tool"


class Proficiency(str, Enum):
    EXPERT = "expert"
    PROFICIENT = "proficient"
    FAMILIAR = "familiar"
    LEARNING = "learning"


# ---------------------------------------------------------------------------
# Skill Models
# ---------------------------------------------------------------------------

class SkillBase(BaseModel):
    """Shared fields for skill records."""
    name: str = Field(..., min_length=1, max_length=100)
    category: SkillCategory
    weight: float = Field(default=0.5, ge=0.0, le=1.0)


class SkillCreate(SkillBase):
    """Used when inserting a new skill into the vocabulary table."""
    canonical_name: str | None = None


class Skill(SkillBase):
    """Full skill record from the database."""
    id: int
    canonical_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Job Listing Models — the core pipeline data
# ---------------------------------------------------------------------------

class RawJobListing(BaseModel):
    """
    What the scraper produces — minimal validation, raw data.
    This is deliberately loose because scrapers deal with messy HTML.
    """
    external_id: str
    source: JobSource
    title: str
    company_name: str
    url: str
    location: str | None = None
    remote_type: RemoteType = RemoteType.UNKNOWN
    salary_text: str | None = None  # Raw "$90K - $140K" before parsing
    description_raw: str | None = None

    @field_validator("url")
    @classmethod
    def url_must_be_http(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError(f"URL must start with http:// or https://, got: {v[:50]}")
        return v

    @field_validator("external_id")
    @classmethod
    def external_id_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("external_id cannot be empty or whitespace")
        return v.strip()


class JobListingCreate(BaseModel):
    """
    What the normalizer produces — clean, validated, ready for DB insert.
    This is the "contract" between the normalizer and the database.

    Interview point: "I separate raw ingestion models from DB-ready models
    so the normalizer is forced to explicitly handle every field transformation.
    Nothing slips through implicitly."
    """
    external_id: str
    source: JobSource
    title: str = Field(..., min_length=1, max_length=500)
    company_name: str = Field(..., min_length=1, max_length=300)
    url: str
    location: str | None = None
    remote_type: RemoteType = RemoteType.UNKNOWN
    salary_min: float | None = Field(default=None, ge=0)
    salary_max: float | None = Field(default=None, ge=0)
    salary_currency: str = "USD"
    description_raw: str | None = None
    description_clean: str | None = None
    posting_date: str | None = None
    expiry_date: str | None = None

    @model_validator(mode="after")
    def salary_range_valid(self) -> JobListingCreate:
        """Salary min must not exceed max."""
        if self.salary_min is not None and self.salary_max is not None:
            if self.salary_min > self.salary_max:
                raise ValueError(
                    f"salary_min ({self.salary_min}) cannot exceed "
                    f"salary_max ({self.salary_max})"
                )
        return self

    model_config = ConfigDict(from_attributes=True)


class JobListing(JobListingCreate):
    """
    Full job listing record from the database, including computed fields.
    """
    id: int
    company_tier: int | None = Field(default=None, ge=1, le=3)
    match_score: float | None = Field(default=None, ge=0.0, le=1.0)
    match_reasoning: str | None = None
    rank_model_version: str | None = None
    status: JobStatus = JobStatus.SCRAPED
    scraped_at: datetime
    ranked_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Job-Skill Relationship
# ---------------------------------------------------------------------------

class JobSkillCreate(BaseModel):
    """Link a skill to a job listing with context."""
    job_id: int
    skill_id: int
    is_required: bool = True
    source_context: str | None = None  # The sentence mentioning this skill


class JobSkill(JobSkillCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Resume Profile Models
# ---------------------------------------------------------------------------

class ResumeProfileCreate(BaseModel):
    """Create a resume profile for matching against jobs."""
    name: str = Field(..., min_length=1, max_length=100)
    version: str = "1.0"
    raw_text: str | None = None


class ResumeProfile(ResumeProfileCreate):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ResumeSkillCreate(BaseModel):
    """Map a skill to a resume profile with proficiency."""
    profile_id: int
    skill_id: int
    proficiency: Proficiency
    years_experience: float | None = Field(default=None, ge=0)
    evidence: str | None = None  # e.g., "Saved $12M identifying firmware defects"


class ResumeSkill(ResumeSkillCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Scrape Log — operational observability
# ---------------------------------------------------------------------------

class ScrapeLogCreate(BaseModel):
    """Metrics from a single scrape run."""
    source: JobSource
    query_term: str
    jobs_found: int = Field(default=0, ge=0)
    jobs_new: int = Field(default=0, ge=0)
    jobs_duplicate: int = Field(default=0, ge=0)
    errors: int = Field(default=0, ge=0)
    error_details: str | None = None  # JSON array
    duration_seconds: float | None = Field(default=None, ge=0)


class ScrapeLog(ScrapeLogCreate):
    id: int
    completed_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Ranked Job — what the ranker stage outputs
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Phase 4: Auto-Apply Enums + Models
# ---------------------------------------------------------------------------


class ApplicationStatus(str, Enum):
    """Status lifecycle for auto-apply applications."""
    DRAFT = "draft"
    READY = "ready"
    APPROVED = "approved"
    SUBMITTED = "submitted"
    WITHDRAWN = "withdrawn"


class FieldType(str, Enum):
    """Common ATS form field types."""
    TEXT = "text"
    TEXTAREA = "textarea"
    SELECT = "select"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    FILE = "file"
    DATE = "date"
    EMAIL = "email"
    PHONE = "phone"
    URL = "url"


class FieldSource(str, Enum):
    """Where the pre-filled value came from."""
    RESUME = "resume"
    PROFILE = "profile"
    TAILORED = "tailored"
    MANUAL = "manual"
    AI_GENERATED = "ai_generated"


class ApplicationFieldCreate(BaseModel):
    """A single pre-filled form field."""
    field_name: str = Field(..., min_length=1, max_length=200)
    field_type: FieldType = FieldType.TEXT
    field_value: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    source: FieldSource | None = None


class ApplicationCreate(BaseModel):
    """Create a new auto-apply application draft."""
    job_id: int
    profile_id: int = 1
    cover_letter: str | None = None
    confidence_score: float | None = Field(default=None, ge=0.0, le=1.0)
    fields: list[ApplicationFieldCreate] = Field(default_factory=list)
    notes: str | None = None


class Application(BaseModel):
    """Full application record from database."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    profile_id: int
    status: ApplicationStatus
    cover_letter: str | None = None
    confidence_score: float | None = None
    notes: str | None = None
    created_at: str
    updated_at: str
    submitted_at: str | None = None
    fields: list[ApplicationFieldCreate] = Field(default_factory=list)

    # Joined fields from job_listings (populated by queries)
    job_title: str | None = None
    company_name: str | None = None
    company_tier: int | None = None
    match_score: float | None = None
    url: str | None = None


# ---------------------------------------------------------------------------
# Ranked Job — what the ranker stage outputs
# ---------------------------------------------------------------------------

class RankedResult(BaseModel):
    """
    The LLM ranker's output for a single job.

    Interview point: "I modeled the ranker output as its own Pydantic schema
    so I can validate LLM responses — if the model returns a score outside
    0-1 or omits reasoning, the pipeline catches it immediately."
    """
    job_id: int
    match_score: float = Field(..., ge=0.0, le=1.0)
    match_reasoning: str = Field(..., min_length=10)
    skills_matched: list[str] = Field(default_factory=list)
    skills_missing: list[str] = Field(default_factory=list)
    rank_model_version: str
