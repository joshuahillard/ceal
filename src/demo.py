"""
Ceal Phase 2: Demo Mode

Runs the tailoring pipeline on a single job description without
requiring live scraping or a database connection. Useful for
quick testing and demonstration of the Phase 2 pipeline.

Usage:
    python -m src.main --demo --resume data/resume.txt --job data/sample_job.txt
"""
from __future__ import annotations

import datetime
import os
import sys

from dotenv import load_dotenv

from src.models.entities import JobListing, JobSource, JobStatus, RemoteType
from src.tailoring.models import SkillGap, TailoredBullet, TailoringRequest, TailoringResult
from src.tailoring.resume_parser import ResumeProfileParser
from src.tailoring.skill_extractor import SkillOverlapAnalyzer


def _build_demo_job(description: str) -> JobListing:
    """Build a minimal JobListing from raw description text for demo mode."""
    now = datetime.datetime.now(datetime.timezone.utc)
    return JobListing(
        id=0,
        external_id="demo-001",
        source=JobSource.MANUAL,
        title="Demo Job",
        company_name="Demo Company",
        url="https://example.com",
        location=None,
        remote_type=RemoteType.UNKNOWN,
        status=JobStatus.SCRAPED,
        company_tier=1,
        description_raw=description,
        description_clean=description,
        scraped_at=now,
        created_at=now,
        updated_at=now,
    )


def _print_skill_gaps(gaps: list[SkillGap]) -> None:
    """Print skill gap analysis in a readable table."""
    print("\n" + "=" * 60)
    print("  SKILL GAP ANALYSIS")
    print("=" * 60)
    print(f"  {'Skill':<30} {'Category':<15} {'Resume'}",)
    print("  " + "-" * 56)
    for gap in gaps:
        icon = "Y" if gap.resume_has else "N"
        prof = f" ({gap.proficiency.value})" if gap.proficiency else ""
        print(f"  {gap.skill_name:<30} {gap.category.value:<15} {icon}{prof}")
    print()


def _print_tailored_bullets(bullets: list[TailoredBullet]) -> None:
    """Print tailored bullets with before/after comparison."""
    print("=" * 60)
    print("  TAILORED BULLETS")
    print("=" * 60)
    for i, b in enumerate(bullets, 1):
        print(f"\n  Bullet {i}:")
        print(f"    Original:  {b.original[:100]}{'...' if len(b.original) > 100 else ''}")
        print(f"    Rewritten: {b.rewritten_text[:100]}{'...' if len(b.rewritten_text) > 100 else ''}")
        print(f"    Relevance: {b.relevance_score:.2f}  |  X-Y-Z: {'Yes' if b.xyz_format else 'No'}")
    print()


def _print_metadata(
    prompt_version: str, job_id: int, profile_id: int, bullet_count: int,
) -> None:
    """Print metadata summary."""
    print("=" * 60)
    print("  METADATA")
    print("=" * 60)
    print(f"  Prompt Version: {prompt_version}")
    print(f"  Job ID:         {job_id}")
    print(f"  Profile ID:     {profile_id}")
    print(f"  Bullet Count:   {bullet_count}")
    print("=" * 60)
    print()


async def run_demo(
    resume_path: str,
    job_path: str,
    *,
    save: bool = False,
) -> None:
    """Run the Phase 2 demo pipeline on a single resume + job pair."""
    # Validate files exist
    if not os.path.isfile(resume_path):
        print(f"Error: Resume file not found: {resume_path}", file=sys.stderr)
        sys.exit(1)
    if not os.path.isfile(job_path):
        print(f"Error: Job file not found: {job_path}", file=sys.stderr)
        sys.exit(1)

    # Load files
    with open(resume_path, encoding="utf-8") as f:
        resume_text = f.read()
    with open(job_path, encoding="utf-8") as f:
        job_text = f.read()

    print("\n  Ceal Demo Mode")
    print("  " + "-" * 40)

    # Step 1: Parse resume
    parser = ResumeProfileParser()
    parsed = parser.parse(profile_id=1, raw_text=resume_text)
    resume_skills = sorted(set(
        skill
        for bullet in parsed.sections
        for skill in bullet.skills_referenced
    ))
    print(f"  Resume parsed: {len(parsed.sections)} bullets, {len(resume_skills)} skills detected")

    # Step 2: Build demo job
    demo_job = _build_demo_job(job_text)
    print(f"  Job loaded: {len(job_text)} chars")

    # Step 3: Skill gap analysis
    analyzer = SkillOverlapAnalyzer()
    skill_gaps = analyzer.analyze(job=demo_job, resume_skills=resume_skills)
    _print_skill_gaps(skill_gaps)

    # Step 4: LLM tailoring (if API key available)
    load_dotenv()
    api_key = os.getenv("LLM_API_KEY")

    if not api_key:
        print("  No LLM_API_KEY found. Showing skill gap analysis only.")
        print("  Set LLM_API_KEY in .env to enable bullet tailoring.\n")
        return

    print("  LLM_API_KEY found. Running bullet tailoring...")

    try:
        from src.tailoring.engine import TailoringEngine

        request = TailoringRequest(
            job_id=0,
            profile_id=1,
            target_tier=1,
            emphasis_areas=[g.skill_name for g in skill_gaps if g.resume_has],
        )

        engine = TailoringEngine(api_key=api_key)
        result = await engine.generate_tailored_profile(
            request=request,
            resume_bullets=parsed.sections,
            skill_gaps=skill_gaps,
        )

        _print_tailored_bullets(result.tailored_bullets)
        _print_metadata(
            prompt_version=result.tailoring_version,
            job_id=request.job_id,
            profile_id=request.profile_id,
            bullet_count=len(result.tailored_bullets),
        )

        # Save to database if requested
        if save:
            await _maybe_save_result(result)

    except Exception as exc:
        print(f"\n  LLM tailoring failed: {exc}", file=sys.stderr)
        print("  Skill gap analysis (above) still valid.\n")


async def _maybe_save_result(result: TailoringResult) -> None:
    """Save tailoring result to DB if data/ceal.db exists."""
    from pathlib import Path

    db_path = Path("data/ceal.db")
    if not db_path.exists():
        print("  No database found (data/ceal.db). Skipping save.")
        return

    try:
        from src.tailoring.persistence import save_tailoring_result
        request_id = await save_tailoring_result(result)
        print(f"  Result saved to database (request_id={request_id})")
    except Exception as exc:
        print(f"  Failed to save result: {exc}", file=sys.stderr)
