"""
Ceal Phase 2: Batch Tailoring Mode

Processes all ranked jobs in the database through the tailoring engine.
Rate-limits API calls and skips jobs that already have results.
"""
from __future__ import annotations

import asyncio
import datetime
import os

import structlog
from dotenv import load_dotenv

from src.models.database import get_top_matches
from src.models.entities import JobListing, JobSource, JobStatus, RemoteType
from src.tailoring.models import TailoringRequest
from src.tailoring.persistence import get_tailoring_results, save_tailoring_result
from src.tailoring.resume_parser import ResumeProfileParser
from src.tailoring.skill_extractor import SkillOverlapAnalyzer

logger = structlog.get_logger(__name__)


def _dict_to_job_listing(d: dict) -> JobListing:
    """Convert a get_top_matches() dict into a JobListing for the analyzer."""
    now = datetime.datetime.now(datetime.timezone.utc)
    return JobListing(
        id=d["id"],
        external_id=f"batch-{d['id']}",
        source=JobSource.MANUAL,
        title=d.get("title", "Unknown"),
        company_name=d.get("company_name", "Unknown"),
        url=d.get("url", "https://example.com"),
        location=d.get("location"),
        remote_type=RemoteType(d["remote_type"]) if d.get("remote_type") else RemoteType.UNKNOWN,
        status=JobStatus(d["status"]) if d.get("status") else JobStatus.RANKED,
        company_tier=d.get("company_tier"),
        description_raw=d.get("description_raw", ""),
        description_clean=d.get("description_clean", ""),
        scraped_at=now,
        created_at=now,
        updated_at=now,
    )


async def run_batch_tailoring(
    resume_path: str,
    limit: int = 20,
    min_score: float = 0.5,
) -> dict:
    """
    Process ranked jobs through the tailoring pipeline.

    Args:
        resume_path: Path to the resume text file.
        limit: Max number of jobs to process.
        min_score: Minimum match score to include.

    Returns:
        Stats dict: total, tailored, errors, skipped.
    """
    load_dotenv()
    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        logger.error("batch_no_api_key")
        return {"error": "No LLM_API_KEY found. Set it in .env."}

    # Parse resume
    with open(resume_path, encoding="utf-8") as f:
        resume_text = f.read()

    parser = ResumeProfileParser()
    parsed = parser.parse(profile_id=1, raw_text=resume_text)
    resume_skills = sorted(set(
        skill
        for bullet in parsed.sections
        for skill in bullet.skills_referenced
    ))

    # Get ranked jobs from DB
    jobs = await get_top_matches(min_score=min_score, limit=limit)

    stats = {"total": len(jobs), "tailored": 0, "errors": 0, "skipped": 0}
    semaphore = asyncio.Semaphore(3)

    analyzer = SkillOverlapAnalyzer()

    from src.tailoring.engine import TailoringEngine
    engine = TailoringEngine(api_key=api_key)

    for job_dict in jobs:
        job_id = job_dict["id"]

        # Skip already-tailored jobs
        existing = await get_tailoring_results(job_id=job_id, profile_id=1)
        if existing is not None:
            stats["skipped"] += 1
            logger.info("batch_skip_existing", job_id=job_id)
            continue

        async with semaphore:
            try:
                job = _dict_to_job_listing(job_dict)
                skill_gaps = analyzer.analyze(job=job, resume_skills=resume_skills)

                request = TailoringRequest(
                    job_id=job_id,
                    profile_id=1,
                    target_tier=job_dict.get("company_tier") or 2,
                    emphasis_areas=[g.skill_name for g in skill_gaps if g.resume_has],
                )

                result = await engine.generate_tailored_profile(
                    request=request,
                    resume_bullets=parsed.sections,
                    skill_gaps=skill_gaps,
                )

                await save_tailoring_result(result)
                stats["tailored"] += 1
                logger.info(
                    "batch_tailored",
                    job_id=job_id,
                    title=job_dict.get("title"),
                    bullets=len(result.tailored_bullets),
                )

            except Exception as exc:
                stats["errors"] += 1
                logger.error(
                    "batch_tailor_failed",
                    job_id=job_id,
                    error=str(exc),
                )

    logger.info("batch_complete", **stats)
    return stats
