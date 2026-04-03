"""
Ceal Document Models — Pydantic data contracts for PDF generation.

These models define the exact data shape consumed by the resume and
cover letter PDF generators. They are independent of the tailoring
engine models (which they may be populated from, but never import).
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class ResumeJobEntry(BaseModel):
    """A single job experience block."""
    title: str
    company: str
    location: str
    dates: str
    bullets: list[str] = Field(default_factory=list)


class ResumeProjectEntry(BaseModel):
    """A single project block."""
    name: str
    tech: str
    dates: str
    bullets: list[str] = Field(default_factory=list)


class ResumeSkillCategory(BaseModel):
    """A labeled skill group."""
    label: str
    items: str


class ResumeData(BaseModel):
    """Complete data contract for resume PDF generation."""
    name: str
    title_line: str
    contact: str
    links: str
    profile: str
    experience: list[ResumeJobEntry] = Field(default_factory=list)
    projects: list[ResumeProjectEntry] = Field(default_factory=list)
    skills: list[ResumeSkillCategory] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    section_order: list[str] = Field(default=["experience", "projects"])


class CoverLetterData(BaseModel):
    """Complete data contract for cover letter PDF generation."""
    name: str
    contact: str
    date: str
    company: str
    role: str
    salutation: str = "Dear Hiring Team,"
    paragraphs: list[str] = Field(..., min_length=3, max_length=6)
    closing: str = "Sincerely,"
    signature_name: str
    links: str


class ExportResult(BaseModel):
    """Result of a PDF generation operation."""
    success: bool
    file_path: str | None = None
    file_bytes: bytes | None = None
    final_y: float = 0.0
    overflow: bool = False
    error: str | None = None
