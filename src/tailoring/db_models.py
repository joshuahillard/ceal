"""
Céal Phase 2: SQLAlchemy 2.0 Async ORM Models

Persistence layer for the resume tailoring pipeline. Each table maps 1:1
to a Pydantic v2 contract in src/tailoring/models.py:

    ParsedBullet     ↔  parsed_bullets
    SkillGap         ↔  skill_gaps
    TailoringRequest ↔  tailoring_requests
    TailoredBullet   ↔  tailored_bullets

TailoringResult is a read-time assembly (not a table) — it composes
from tailoring_requests + tailored_bullets + skill_gaps at query time.

Architecture notes (interview-defensible):

    "I separated the validation layer (Pydantic) from the persistence
    layer (SQLAlchemy) so each can evolve independently. The Pydantic
    models enforce business rules at pipeline boundaries; the ORM models
    handle storage, relationships, and query optimization. Round-trip
    conversion uses Pydantic's from_attributes=True — zero manual mapping."

Personas tagged in:
    [ETL Architect] — table design, FK relationships, unique constraints
    [Backend Engineer] — type safety, ON CONFLICT patterns, test surface
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)


# ---------------------------------------------------------------------------
# Declarative Base — Phase 2 ORM root
# ---------------------------------------------------------------------------
# Phase 1 tables (job_listings, skills, etc.) remain in schema.sql.
# This Base governs Phase 2 tailoring tables only. Alembic's target_metadata
# points here so migrations are scoped to what the ORM knows about.

class Base(DeclarativeBase):
    """Phase 2 declarative base for Alembic migration management."""
    pass


# ---------------------------------------------------------------------------
# Phase 1 Table Stubs — FK resolution only, NOT managed by Alembic
# ---------------------------------------------------------------------------
# These minimal ORM classes exist SOLELY so SQLAlchemy can resolve
# foreign key references from Phase 2 tables to Phase 1 tables.
# The actual DDL for these tables lives in src/models/schema.sql.
# Alembic's env.py uses include_object to exclude them from migrations.

class _JobListingStub(Base):
    """FK stub for Phase 1 job_listings table. Do not modify."""
    __tablename__ = "job_listings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)


class _ResumeProfileStub(Base):
    """FK stub for Phase 1 resume_profiles table. Do not modify."""
    __tablename__ = "resume_profiles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)


# Phase 1 stub table names — excluded from Alembic migration generation
PHASE1_STUB_TABLES = {"job_listings", "resume_profiles"}


def _utcnow() -> datetime:
    """Timezone-aware UTC timestamp for default column values."""
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# ParsedBulletTable — atomic resume bullets extracted by parser
# ---------------------------------------------------------------------------
# Pydantic peer: ParsedBullet (src/tailoring/models.py)
# Relationship: Many bullets → one resume_profile (Phase 1 table)

class ParsedBulletTable(Base):
    """
    Stores individual bullet points decomposed from a master resume.

    Each bullet is an atomic unit the tailoring engine can selectively
    rewrite, reorder, or suppress per job listing. The section column
    enables section-aware reassembly.

    ON CONFLICT strategy: profile_id + original_text hash ensures
    re-parsing the same resume doesn't create duplicates.
    """
    __tablename__ = "parsed_bullets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("resume_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    section: Mapped[str] = mapped_column(
        String(20),
        CheckConstraint(
            "section IN ('SUMMARY', 'EXPERIENCE', 'SKILLS', 'PROJECTS', 'CERTIFICATIONS')",
            name="ck_parsed_bullets_section",
        ),
        nullable=False,
    )
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    skills_referenced: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None,
        comment="JSON array of skill names — denormalized for LLM context injection",
    )
    metrics: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None,
        comment="JSON array of quantitative metrics extracted from bullet",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )

    # Idempotency: same profile + same text = same bullet
    __table_args__ = (
        UniqueConstraint("profile_id", "original_text", name="uq_parsed_bullet_identity"),
    )

    def __repr__(self) -> str:
        return (
            f"<ParsedBullet(id={self.id}, profile={self.profile_id}, "
            f"section={self.section}, text={self.original_text[:40]}...)>"
        )


# ---------------------------------------------------------------------------
# TailoringRequestTable — strict payload tracking for LLM calls
# ---------------------------------------------------------------------------
# Pydantic peer: TailoringRequest (src/tailoring/models.py)
# Relationships: → job_listings (Phase 1), → resume_profiles (Phase 1)

class TailoringRequestTable(Base):
    """
    Tracks every tailoring request sent to the LLM engine.

    This is the audit trail: which job, which profile, which tier,
    and what emphasis areas were used. Enables prompt A/B testing by
    correlating request parameters with downstream interview response rates.

    ON CONFLICT strategy: job_id + profile_id is unique — re-tailoring
    the same resume for the same job overwrites the previous request.
    """
    __tablename__ = "tailoring_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("job_listings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    profile_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("resume_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_tier: Mapped[int] = mapped_column(
        Integer,
        CheckConstraint("target_tier BETWEEN 1 AND 3", name="ck_tailoring_tier"),
        nullable=False,
    )
    emphasis_areas: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None,
        comment="JSON array of emphasis keywords for LLM prompt context",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )

    # Relationships — loaded lazily by default, eager when needed
    tailored_bullets: Mapped[list["TailoredBulletTable"]] = relationship(
        back_populates="request",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    skill_gaps: Mapped[list["SkillGapTable"]] = relationship(
        back_populates="request",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # Idempotency: one active tailoring per job+profile pair
    __table_args__ = (
        UniqueConstraint("job_id", "profile_id", name="uq_tailoring_request_identity"),
    )

    def __repr__(self) -> str:
        return (
            f"<TailoringRequest(id={self.id}, job={self.job_id}, "
            f"profile={self.profile_id}, tier={self.target_tier})>"
        )


# ---------------------------------------------------------------------------
# TailoredBulletTable — rewritten bullets with X-Y-Z scores
# ---------------------------------------------------------------------------
# Pydantic peer: TailoredBullet (src/tailoring/models.py)
# Relationship: Many tailored bullets → one tailoring_request

class TailoredBulletTable(Base):
    """
    Stores LLM-rewritten resume bullets targeted for a specific job.

    Each bullet carries a relevance_score (0.0–1.0) and an xyz_format
    flag. The Pydantic layer enforces that xyz_format=True requires
    both 'measured by' and 'by doing' clauses — this table persists
    the validated result.

    Interview talking point:
        "Every rewritten bullet is scored and tagged for X-Y-Z compliance
        before it reaches the database. The ORM stores the validated
        output; the Pydantic model is the gatekeeper."
    """
    __tablename__ = "tailored_bullets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tailoring_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    original: Mapped[str] = mapped_column(Text, nullable=False)
    rewritten_text: Mapped[str] = mapped_column(Text, nullable=False)
    xyz_format: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    relevance_score: Mapped[float] = mapped_column(
        Float,
        CheckConstraint(
            "relevance_score BETWEEN 0.0 AND 1.0",
            name="ck_tailored_bullet_score",
        ),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )

    # Back-reference to parent request
    request: Mapped["TailoringRequestTable"] = relationship(
        back_populates="tailored_bullets",
    )

    def __repr__(self) -> str:
        return (
            f"<TailoredBullet(id={self.id}, request={self.request_id}, "
            f"score={self.relevance_score}, xyz={self.xyz_format})>"
        )


# ---------------------------------------------------------------------------
# SkillGapTable — per-job overlap/miss analysis
# ---------------------------------------------------------------------------
# Pydantic peer: SkillGap (src/tailoring/models.py)
# Relationship: Many gaps → one tailoring_request

class SkillGapTable(Base):
    """
    Stores the skill overlap analysis between a job listing and
    the candidate's resume profile.

    Each row is one skill: does the job require it? Does the resume
    have it? At what proficiency? This feeds the LLM's context window
    so it knows what to emphasize and what gaps to acknowledge.

    ON CONFLICT strategy: request_id + skill_name is unique —
    re-analyzing the same request updates rather than duplicates.
    """
    __tablename__ = "skill_gaps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tailoring_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    skill_name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(
        String(20),
        CheckConstraint(
            "category IN ('language', 'framework', 'infrastructure', 'database', "
            "'cloud', 'methodology', 'soft_skill', 'domain', 'tool')",
            name="ck_skill_gap_category",
        ),
        nullable=False,
    )
    job_requires: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    resume_has: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    proficiency: Mapped[str | None] = mapped_column(
        String(20),
        CheckConstraint(
            "proficiency IS NULL OR proficiency IN ('expert', 'proficient', 'familiar', 'learning')",
            name="ck_skill_gap_proficiency",
        ),
        nullable=True,
        default=None,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
    )

    # Back-reference to parent request
    request: Mapped["TailoringRequestTable"] = relationship(
        back_populates="skill_gaps",
    )

    # Idempotency: one gap record per skill per request
    __table_args__ = (
        UniqueConstraint("request_id", "skill_name", name="uq_skill_gap_identity"),
    )

    def __repr__(self) -> str:
        return (
            f"<SkillGap(id={self.id}, request={self.request_id}, "
            f"skill={self.skill_name}, has={self.resume_has})>"
        )
