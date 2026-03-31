"""
Ceal Phase 2: Tailoring Subpackage

Exports the strict data contracts and engine components for pipeline integration.

Phase 2 scope: Automating the translation of experience into bespoke,
role-specific value propositions. Reduces manual application prep from
45 minutes to under 2 minutes per listing.
"""
from .engine import TailoringEngine
from .models import (
    ParsedBullet,
    ParsedResume,
    ResumeSection,
    SkillGap,
    TailoredBullet,
    TailoringRequest,
    TailoringResult,
)
from .resume_parser import ResumeProfileParser
from .skill_extractor import SkillOverlapAnalyzer

__all__ = [
    "ResumeSection",
    "ParsedBullet",
    "ParsedResume",
    "SkillGap",
    "TailoringRequest",
    "TailoredBullet",
    "TailoringResult",
    "ResumeProfileParser",
    "SkillOverlapAnalyzer",
    "TailoringEngine",
]
