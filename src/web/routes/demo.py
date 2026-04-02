"""Demo mode route — resume tailoring without database or scraping."""
from __future__ import annotations

import datetime
import os
from pathlib import Path

from fastapi import APIRouter, Form, Request

from src.models.entities import JobListing, JobSource, JobStatus, RemoteType
from src.tailoring.models import TailoringRequest
from src.tailoring.resume_parser import ResumeProfileParser
from src.tailoring.skill_extractor import SkillOverlapAnalyzer
from src.web.app import templates

router = APIRouter(prefix="/demo", tags=["demo"])

_RESUME_PATH = Path("data/resume.txt")


def _build_demo_job(description: str) -> JobListing:
    """Build a minimal JobListing from raw description text for demo mode."""
    now = datetime.datetime.now(datetime.timezone.utc)
    return JobListing(
        id=0,
        external_id="web-demo-001",
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


@router.get("/")
async def demo_form(request: Request):
    """Render the demo form, pre-populated with resume if available."""
    resume_text = ""
    if _RESUME_PATH.is_file():
        resume_text = _RESUME_PATH.read_text(encoding="utf-8")

    return templates.TemplateResponse(
        "demo.html",
        {
            "request": request,
            "resume_text": resume_text,
            "results": None,
        },
    )


@router.post("/")
async def demo_run(
    request: Request,
    resume_text: str = Form(...),
    job_description: str = Form(""),
    job_url: str = Form(""),
    target_tier: int = Form(1),
):
    """Process the demo form and render results."""
    errors: list[str] = []
    skill_gaps = []
    tailored_bullets = []
    has_api_key = False

    # Get job description from URL or textarea
    description = job_description.strip()
    if not description and job_url.strip():
        try:
            from src.fetcher import fetch_job_description
            description = await fetch_job_description(job_url.strip())
        except Exception as exc:
            errors.append(f"Failed to fetch URL: {exc}")

    if not description and not errors:
        errors.append("Please provide a job description or URL.")

    if not resume_text.strip():
        errors.append("Resume text is required.")

    if not errors and description:
        # Step 1: Parse resume
        parser = ResumeProfileParser()
        parsed = parser.parse(profile_id=1, raw_text=resume_text)
        resume_skills = sorted(set(
            skill
            for bullet in parsed.sections
            for skill in bullet.skills_referenced
        ))

        # Step 2: Build demo job and run skill gap analysis
        demo_job = _build_demo_job(description)
        analyzer = SkillOverlapAnalyzer()
        skill_gaps = analyzer.analyze(job=demo_job, resume_skills=resume_skills)

        # Step 3: LLM tailoring (if API key available)
        api_key = os.getenv("LLM_API_KEY")
        if api_key:
            has_api_key = True
            try:
                from src.tailoring.engine import TailoringEngine

                tailoring_request = TailoringRequest(
                    job_id=0,
                    profile_id=1,
                    target_tier=target_tier,
                    emphasis_areas=[g.skill_name for g in skill_gaps if g.resume_has],
                )
                engine = TailoringEngine(api_key=api_key)
                result = await engine.generate_tailored_profile(
                    request=tailoring_request,
                    resume_bullets=parsed.sections,
                    skill_gaps=skill_gaps,
                )
                tailored_bullets = result.tailored_bullets
            except Exception as exc:
                errors.append(f"LLM tailoring failed: {exc}")

    return templates.TemplateResponse(
        "demo.html",
        {
            "request": request,
            "resume_text": resume_text,
            "results": {
                "skill_gaps": skill_gaps,
                "tailored_bullets": tailored_bullets,
                "has_api_key": has_api_key,
                "errors": errors,
                "job_description": description,
                "job_url": job_url,
                "target_tier": target_tier,
            },
        },
    )
