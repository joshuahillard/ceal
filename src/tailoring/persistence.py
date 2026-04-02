"""
Ceal Phase 2: Tailoring Persistence Layer

CRUD operations for Phase 2 tailoring data, following the same
session pattern as src/models/database.py. All data flows through
Pydantic models for validation before hitting the database.

Uses raw SQL via text() for consistency with the Phase 1 layer.
"""
from __future__ import annotations

import datetime
import json

import structlog
from sqlalchemy import text

from src.models.database import get_session
from src.models.entities import Proficiency, SkillCategory
from src.tailoring.models import (
    SkillGap,
    TailoredBullet,
    TailoringRequest,
    TailoringResult,
)

logger = structlog.get_logger(__name__)


async def save_tailoring_result(result: TailoringResult) -> int:
    """
    Save a complete TailoringResult to the database.

    Inserts into tailoring_requests, then inserts each TailoredBullet
    and SkillGap with the request_id FK. Uses ON CONFLICT for
    idempotency on the (job_id, profile_id) unique constraint.

    Returns the request_id.
    """
    async with get_session() as session:
        # Upsert the tailoring request
        req = result.request
        emphasis_json = json.dumps(req.emphasis_areas) if req.emphasis_areas else None

        row = await session.execute(
            text("""
                INSERT INTO tailoring_requests (job_id, profile_id, target_tier, emphasis_areas, created_at)
                VALUES (:job_id, :profile_id, :target_tier, :emphasis_areas, :created_at)
                ON CONFLICT(job_id, profile_id) DO UPDATE SET
                    target_tier = excluded.target_tier,
                    emphasis_areas = excluded.emphasis_areas
            """),
            {
                "job_id": req.job_id,
                "profile_id": req.profile_id,
                "target_tier": req.target_tier,
                "emphasis_areas": emphasis_json,
                "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            },
        )

        # Get the request_id (new or existing)
        id_row = await session.execute(
            text("""
                SELECT id FROM tailoring_requests
                WHERE job_id = :job_id AND profile_id = :profile_id
            """),
            {"job_id": req.job_id, "profile_id": req.profile_id},
        )
        request_id = id_row.scalar_one()

        # Clear existing child rows before re-inserting (idempotent replace)
        await session.execute(
            text("DELETE FROM tailored_bullets WHERE request_id = :rid"),
            {"rid": request_id},
        )
        await session.execute(
            text("DELETE FROM skill_gaps WHERE request_id = :rid"),
            {"rid": request_id},
        )

        # Insert tailored bullets
        for bullet in result.tailored_bullets:
            await session.execute(
                text("""
                    INSERT INTO tailored_bullets
                        (request_id, original, rewritten_text, xyz_format, relevance_score, created_at)
                    VALUES (:rid, :original, :rewritten_text, :xyz_format, :relevance_score, :created_at)
                """),
                {
                    "rid": request_id,
                    "original": bullet.original,
                    "rewritten_text": bullet.rewritten_text,
                    "xyz_format": bullet.xyz_format,
                    "relevance_score": bullet.relevance_score,
                    "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                },
            )

        # Insert skill gaps
        for gap in result.skill_gaps:
            await session.execute(
                text("""
                    INSERT INTO skill_gaps
                        (request_id, skill_name, category, job_requires, resume_has, proficiency, created_at)
                    VALUES (:rid, :skill_name, :category, :job_requires, :resume_has, :proficiency, :created_at)
                    ON CONFLICT(request_id, skill_name) DO UPDATE SET
                        category = excluded.category,
                        job_requires = excluded.job_requires,
                        resume_has = excluded.resume_has,
                        proficiency = excluded.proficiency
                """),
                {
                    "rid": request_id,
                    "skill_name": gap.skill_name,
                    "category": gap.category.value,
                    "job_requires": gap.job_requires,
                    "resume_has": gap.resume_has,
                    "proficiency": gap.proficiency.value if gap.proficiency else None,
                    "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                },
            )

    logger.info(
        "tailoring_result_saved",
        request_id=request_id,
        job_id=req.job_id,
        bullets=len(result.tailored_bullets),
        gaps=len(result.skill_gaps),
    )
    return request_id


async def get_tailoring_results(
    job_id: int, profile_id: int = 1,
) -> TailoringResult | None:
    """
    Retrieve a saved tailoring result, reconstructing the Pydantic
    TailoringResult from the ORM tables. Returns None if not found.
    """
    async with get_session() as session:
        # Find the request
        req_row = await session.execute(
            text("""
                SELECT id, job_id, profile_id, target_tier, emphasis_areas
                FROM tailoring_requests
                WHERE job_id = :job_id AND profile_id = :profile_id
            """),
            {"job_id": job_id, "profile_id": profile_id},
        )
        req = req_row.first()
        if req is None:
            return None

        req_map = dict(req._mapping)
        request_id = req_map["id"]

        emphasis = []
        if req_map["emphasis_areas"]:
            emphasis = json.loads(req_map["emphasis_areas"])

        request = TailoringRequest(
            job_id=req_map["job_id"],
            profile_id=req_map["profile_id"],
            target_tier=req_map["target_tier"],
            emphasis_areas=emphasis,
        )

        # Load tailored bullets
        bullet_rows = await session.execute(
            text("""
                SELECT original, rewritten_text, xyz_format, relevance_score
                FROM tailored_bullets
                WHERE request_id = :rid
                ORDER BY id
            """),
            {"rid": request_id},
        )
        bullets = [
            TailoredBullet(
                original=r._mapping["original"],
                rewritten_text=r._mapping["rewritten_text"],
                xyz_format=bool(r._mapping["xyz_format"]),
                relevance_score=r._mapping["relevance_score"],
            )
            for r in bullet_rows
        ]

        # Load skill gaps
        gap_rows = await session.execute(
            text("""
                SELECT skill_name, category, job_requires, resume_has, proficiency
                FROM skill_gaps
                WHERE request_id = :rid
                ORDER BY id
            """),
            {"rid": request_id},
        )
        gaps = [
            SkillGap(
                skill_name=r._mapping["skill_name"],
                category=SkillCategory(r._mapping["category"]),
                job_requires=bool(r._mapping["job_requires"]),
                resume_has=bool(r._mapping["resume_has"]),
                proficiency=Proficiency(r._mapping["proficiency"]) if r._mapping["proficiency"] else None,
            )
            for r in gap_rows
        ]

    return TailoringResult(
        request=request,
        tailored_bullets=bullets,
        skill_gaps=gaps,
        tailoring_version="v1.0",
    )


async def list_tailored_jobs(limit: int = 20) -> list[dict]:
    """
    List jobs that have been tailored, joining tailoring_requests
    with job_listings to show job title, company, tier, and bullet count.
    """
    async with get_session() as session:
        result = await session.execute(
            text("""
                SELECT
                    tr.id AS request_id,
                    tr.job_id,
                    tr.profile_id,
                    tr.target_tier,
                    jl.title,
                    jl.company_name,
                    jl.company_tier,
                    (SELECT COUNT(*) FROM tailored_bullets tb WHERE tb.request_id = tr.id) AS bullet_count
                FROM tailoring_requests tr
                LEFT JOIN job_listings jl ON jl.id = tr.job_id
                ORDER BY tr.created_at DESC
                LIMIT :limit
            """),
            {"limit": limit},
        )
        return [dict(row._mapping) for row in result]
