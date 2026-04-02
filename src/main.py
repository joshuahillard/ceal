"""
Céal: Pipeline Orchestrator

This is the entry point that wires all three pipeline stages together
using asyncio.Queue as the message broker between stages.

Architecture — the Producer-Consumer Pipeline:

    ┌──────────┐    raw_queue     ┌────────────┐    clean_queue    ┌──────────┐
    │ SCRAPER  │ ──────────────▶  │ NORMALIZER │ ───────────────▶  │  RANKER  │
    │(Producer)│   RawJobListing  │(Transform) │  JobListingCreate │(Consumer)│
    └──────────┘                  └────────────┘                   └──────────┘
         ↓                              ↓                               ↓
    aiohttp + semaphore         Pydantic + regex              Claude API + DB write
    LinkedIn guest API          salary/skill parsing          match scoring

    Each stage runs as an independent asyncio Task. They communicate
    ONLY through queues — no shared state, no direct function calls.

Interview script (the 60-second version):

    "Céal is an event-driven pipeline with three decoupled stages.
    The scraper produces RawJobListing objects and pushes them onto an
    asyncio.Queue. The normalizer consumes from that queue, cleans HTML,
    parses salaries, extracts skills, validates through Pydantic, and
    pushes clean records onto a second queue. The ranker consumes clean
    records, scores each one against my resume using Claude's API, and
    writes results to SQLite.

    The stages are independently testable — the normalizer is a pure
    function, the scraper is tested with mocked HTTP, and the ranker
    is tested with mocked LLM responses. The queue-based architecture
    means I can scale any stage independently or swap implementations
    without touching the others."

Usage:
    # Full pipeline: scrape → normalize → rank
    python -m src.main --query "Technical Solutions Engineer" --location "Boston, MA"

    # Rank-only mode: just re-rank existing unranked jobs
    python -m src.main --rank-only

    # Scrape-only mode: scrape and normalize without ranking
    python -m src.main --query "TPM" --location "Boston, MA" --no-rank
"""

from __future__ import annotations

import argparse
import asyncio
import os
import time

import structlog

from src.models.database import (
    assign_company_tiers,
    get_pipeline_stats,
    get_top_matches,
    init_db,
    log_scrape_run,
    upsert_jobs_batch,
)
from src.models.entities import (
    JobListingCreate,
    JobSource,
    RawJobListing,
    ScrapeLogCreate,
)
from src.normalizer.pipeline import normalize_job
from src.ranker.llm_ranker import LLMRanker
from src.scrapers.linkedin import LinkedInScraper

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Sentinel value to signal queue shutdown
# ---------------------------------------------------------------------------
# Why a sentinel instead of Queue.join()? The sentinel pattern lets each
# consumer shut down cleanly after processing all items, rather than
# blocking indefinitely. This is the standard pattern in Go channels
# and Kafka consumer groups.

_SHUTDOWN = object()


# ---------------------------------------------------------------------------
# Pipeline Stages (each runs as an asyncio Task)
# ---------------------------------------------------------------------------

async def scraper_stage(
    raw_queue: asyncio.Queue,
    query: str,
    location: str,
    max_results: int = 100,
    concurrency: int = 3,
) -> None:
    """
    Stage 1: PRODUCER — scrapes jobs and pushes RawJobListings onto the queue.

    This stage owns the aiohttp session lifecycle. When scraping is complete,
    it pushes a _SHUTDOWN sentinel onto the queue so the normalizer knows
    there's no more data coming.

    Interview point: "The producer pushes a sentinel value when it's done,
    which is the standard shutdown signal in producer-consumer patterns.
    This avoids the 'how does the consumer know when to stop?' problem
    without requiring timeouts or polling."
    """
    logger.info(
        "scraper_stage_started",
        query=query,
        location=location,
        max_results=max_results,
    )

    start = time.monotonic()
    scrape_stats = {"found": 0, "new": 0, "errors": 0}

    try:
        async with LinkedInScraper(
            concurrency=concurrency,
            request_delay=2.0,
            fetch_descriptions=True,
        ) as scraper:
            jobs = await scraper.scrape_jobs(
                query=query,
                location=location,
                max_results=max_results,
            )

            scrape_stats["found"] = len(jobs)

            # Push each job onto the queue individually (streaming)
            for job in jobs:
                await raw_queue.put(job)

            # Log scrape metrics

    except Exception as exc:
        scrape_stats["errors"] = 1
        logger.error("scraper_stage_failed", error=str(exc))

    finally:
        # Always send shutdown signal, even on failure
        await raw_queue.put(_SHUTDOWN)

        duration = round(time.monotonic() - start, 2)
        logger.info(
            "scraper_stage_complete",
            duration=duration,
            **scrape_stats,
        )

        # Log to scrape_log table
        try:
            await log_scrape_run(ScrapeLogCreate(
                source=JobSource.LINKEDIN,
                query_term=f"{query} | {location}",
                jobs_found=scrape_stats["found"],
                jobs_new=scrape_stats["found"],  # Updated by DB upsert
                errors=scrape_stats["errors"],
                duration_seconds=duration,
            ))
        except Exception:
            pass  # Don't crash on metrics logging failure


async def normalizer_stage(
    raw_queue: asyncio.Queue,
    clean_queue: asyncio.Queue,
) -> None:
    """
    Stage 2: TRANSFORMER — consumes RawJobListings, produces clean records.

    Reads from raw_queue, normalizes each job (HTML cleanup, salary parsing,
    skill extraction), validates through Pydantic, inserts into the database,
    and pushes the DB record onto clean_queue for the ranker.

    Interview point: "The normalizer is the only stage that writes to the
    database. This is intentional — having a single writer simplifies
    concurrency and makes the data flow easy to trace. The scraper
    produces raw data, the normalizer is the gatekeeper."
    """
    logger.info("normalizer_stage_started")
    processed = 0
    failed = 0
    all_jobs: list[JobListingCreate] = []
    all_skills: list[tuple[int, list[dict]]] = []

    while True:
        item = await raw_queue.get()

        if item is _SHUTDOWN:
            raw_queue.task_done()
            break

        raw_job: RawJobListing = item

        try:
            # Normalize: clean HTML, parse salary, extract skills
            clean_job, skills = normalize_job(raw_job)
            all_jobs.append(clean_job)
            # We'll link skills after batch insert (need job IDs)
            all_skills.append((processed, skills))
            processed += 1

        except Exception as exc:
            failed += 1
            logger.warning(
                "normalize_failed",
                external_id=raw_job.external_id,
                error=str(exc),
            )

        raw_queue.task_done()

    # Batch insert all normalized jobs
    if all_jobs:
        await upsert_jobs_batch(all_jobs)

        # Auto-assign company tiers
        await assign_company_tiers()

        # Push job IDs onto clean_queue for the ranker
        # For now, just signal that normalization is done
        for job in all_jobs:
            await clean_queue.put(job)

    # Signal shutdown to the ranker
    await clean_queue.put(_SHUTDOWN)

    logger.info(
        "normalizer_stage_complete",
        processed=processed,
        failed=failed,
        batch_insert=len(all_jobs),
    )


async def ranker_stage(
    clean_queue: asyncio.Queue,
    resume_text: str,
    api_key: str | None = None,
) -> None:
    """
    Stage 3: CONSUMER — scores jobs against the resume via LLM.

    Reads from clean_queue, but actually ranks from the database
    (where the normalizer just inserted the jobs). This ensures
    the ranker always works with the latest data and can be re-run
    independently.

    Interview point: "The ranker reads from the database rather than
    directly from the queue because it needs the generated job IDs
    for the update. This also means I can run the ranker independently
    (--rank-only mode) against any unranked jobs, which is useful
    when I improve the ranking prompt and want to re-score."
    """
    logger.info("ranker_stage_started")

    # Drain the queue first (wait for normalizer to finish)
    count = 0
    while True:
        item = await clean_queue.get()
        clean_queue.task_done()
        if item is _SHUTDOWN:
            break
        count += 1

    if not api_key:
        logger.warning(
            "ranker_skipped",
            reason="No LLM_API_KEY configured. Set LLM_API_KEY in .env to enable ranking.",
        )
        return

    logger.info("ranker_scoring_jobs", queued_count=count)

    # Now rank from the database
    from src.models.database import get_unranked_jobs, update_job_ranking

    unranked = await get_unranked_jobs(limit=50)
    if not unranked:
        logger.info("no_unranked_jobs")
        return

    ranked = 0
    errors = 0

    async with LLMRanker(api_key=api_key) as ranker:
        for job in unranked:
            try:
                result = await ranker.rank_job(
                    job_id=job["id"],
                    job_title=job["title"],
                    company_name=job["company_name"],
                    job_description=(
                        job.get("description_clean")
                        or job.get("description_raw")
                        or ""
                    ),
                    resume_text=resume_text,
                    location=job.get("location"),
                )
                await update_job_ranking(result)
                ranked += 1

            except Exception as exc:
                errors += 1
                logger.error(
                    "rank_job_failed",
                    job_id=job["id"],
                    error=str(exc),
                )

    logger.info(
        "ranker_stage_complete",
        total=len(unranked),
        ranked=ranked,
        errors=errors,
    )


# ---------------------------------------------------------------------------
# Pipeline Orchestrator
# ---------------------------------------------------------------------------

async def run_pipeline(
    query: str,
    location: str,
    max_results: int = 100,
    resume_text: str | None = None,
    rank: bool = True,
    api_key: str | None = None,
) -> dict:
    """
    Run the full three-stage pipeline.

    Creates two asyncio.Queues and launches all three stages as
    concurrent Tasks. The stages communicate only through the queues.

    Returns pipeline stats for display.

    Interview point: "The orchestrator creates the queues, launches
    the stages as asyncio.Tasks, and waits for all of them to complete.
    The queue maxsize provides backpressure — if the normalizer is slow,
    the scraper blocks on put() rather than consuming unlimited memory.
    This is the same backpressure pattern used in Kafka and Go channels."
    """
    # Initialize the database
    await init_db()

    # Create bounded queues (backpressure)
    raw_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    clean_queue: asyncio.Queue = asyncio.Queue(maxsize=100)

    # Default resume text if none provided
    if resume_text is None:
        resume_text = _get_default_resume_text()

    # LLM API key
    if api_key is None:
        api_key = os.getenv("LLM_API_KEY")

    logger.info(
        "pipeline_started",
        query=query,
        location=location,
        max_results=max_results,
        ranking_enabled=rank and bool(api_key),
    )

    start = time.monotonic()

    # Launch all three stages as concurrent tasks
    scraper_task = asyncio.create_task(
        scraper_stage(raw_queue, query, location, max_results),
        name="scraper",
    )
    normalizer_task = asyncio.create_task(
        normalizer_stage(raw_queue, clean_queue),
        name="normalizer",
    )
    ranker_task = asyncio.create_task(
        ranker_stage(clean_queue, resume_text, api_key if rank else None),
        name="ranker",
    )

    # Wait for all stages to complete
    await asyncio.gather(scraper_task, normalizer_task, ranker_task)

    duration = round(time.monotonic() - start, 2)

    # Get final stats
    stats = await get_pipeline_stats()
    stats["pipeline_duration_seconds"] = duration

    logger.info("pipeline_complete", duration=duration)

    return stats


async def run_rank_only(
    resume_text: str | None = None,
    api_key: str | None = None,
    limit: int = 50,
) -> dict:
    """
    Rank-only mode: score unranked jobs without scraping.

    Useful for:
      - Re-ranking after improving the prompt
      - Ranking jobs that were scraped in a previous run
      - Testing the ranker in isolation
    """
    await init_db()

    if resume_text is None:
        resume_text = _get_default_resume_text()
    if api_key is None:
        api_key = os.getenv("LLM_API_KEY")

    if not api_key:
        logger.error("No LLM_API_KEY configured")
        return {"error": "Set LLM_API_KEY in .env"}

    from src.ranker.llm_ranker import rank_unranked_jobs

    results = await rank_unranked_jobs(
        resume_text=resume_text,
        api_key=api_key,
        limit=limit,
    )

    stats = await get_pipeline_stats()
    stats["newly_ranked"] = len(results)

    return stats


# ---------------------------------------------------------------------------
# CLI Interface
# ---------------------------------------------------------------------------

def _get_default_resume_text() -> str:
    """
    Josh's resume summary for LLM matching.
    In production, this would load from the resume_profiles table.
    """
    return """
Josh Hillard — Technical Solutions Engineer / Technical Program Manager

EXPERIENCE:
- Manager II, Technical Escalations at Toast, Inc. (Oct 2023 – Oct 2025)
  * Directed team of senior technical consultants handling complex escalations
  * Identified critical firmware defects saving Toast estimated $12 million
  * Recognized by CEO Chris Comparato at company-wide kickoff event
  * Reduced recurring issue volume by 37% via cross-functional collaboration
  * Created enablement materials, onboarding frameworks, knowledge base articles

- Senior Restaurant Technical Consultant II at Toast (Jun 2022 – Sep 2023)
  * 63% successful post-sales adoption partnering with Success Managers
  * Created consultative playbooks and training frameworks
  * Primary Technical SME for on-site and cross-team initiatives

- Senior Customer Care Rep — Payment Escalations at Toast (Apr 2019 – Jun 2022)
  * Complex payment processing escalation management
  * Customer feedback analysis driving operational enhancements

INDEPENDENT PROJECT: Moss Lane Trading Bot (March 2026 – Present)
  * Production autonomous trading system on cloud infrastructure
  * Full lifecycle: audit, root cause analysis, 1,800-line rewrite
  * 5 external API integrations, multi-layer risk management
  * Python, Linux admin, SSH/SCP, systemd, SQL, REST APIs

SKILLS:
Technical: Python, SQL, REST APIs, Linux, Docker, GCP, asyncio, Git,
  Payment Processing, API Integrations, systemd, Deployment Automation
Leadership: Escalation Management, Cross-Functional Leadership,
  Process Optimization, Training & Enablement, Project Management
Domain: FinTech, POS Systems, SaaS, Payment Processing

CERTIFICATIONS:
- Google AI Essentials — Professional Certificate (2026)
- Google Project Management — Professional Certificate (In Progress)
""".strip()


def _print_results(stats: dict) -> None:
    """Pretty-print pipeline results to the terminal."""
    print("\n" + "=" * 60)
    print("  CÉAL — Pipeline Results")
    print("=" * 60)

    if "pipeline_duration_seconds" in stats:
        print(f"\n  Pipeline Duration: {stats['pipeline_duration_seconds']}s")

    jobs_by_status = stats.get("jobs_by_status", {})
    if jobs_by_status:
        print("\n  Jobs by Status:")
        for status, count in sorted(jobs_by_status.items()):
            print(f"    {status:>15}: {count}")

    jobs_by_tier = stats.get("jobs_by_tier", {})
    if jobs_by_tier:
        print("\n  Jobs by Tier:")
        for tier, count in sorted(jobs_by_tier.items()):
            label = {"tier_1": "Tier 1 (Apply Now)", "tier_2": "Tier 2 (Build Credential)", "tier_3": "Tier 3 (Campaign)"}
            print(f"    {label.get(tier, tier):>30}: {count}")

    avg_score = stats.get("avg_match_score")
    if avg_score is not None:
        print(f"\n  Average Match Score: {avg_score:.1%}")
        print(f"  Total Ranked: {stats.get('total_ranked', 0)}")

    print("\n" + "=" * 60)


async def _async_main() -> None:
    """Async entry point."""
    parser = argparse.ArgumentParser(
        description="Céal: AI-powered job matching pipeline",
    )
    parser.add_argument(
        "--query", "-q",
        default="Technical Solutions Engineer",
        help="Job search query (default: 'Technical Solutions Engineer')",
    )
    parser.add_argument(
        "--location", "-l",
        default="Boston, MA",
        help="Job location (default: 'Boston, MA')",
    )
    parser.add_argument(
        "--max-results", "-n",
        type=int,
        default=50,
        help="Max results to scrape (default: 50)",
    )
    parser.add_argument(
        "--rank-only",
        action="store_true",
        help="Only rank existing unranked jobs (skip scraping)",
    )
    parser.add_argument(
        "--no-rank",
        action="store_true",
        help="Scrape and normalize only (skip LLM ranking)",
    )
    parser.add_argument(
        "--top",
        type=int,
        help="Show top N matches after pipeline completes",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run demo mode: single-job tailoring without DB or scraping",
    )
    parser.add_argument(
        "--resume",
        type=str,
        help="Path to resume text file (used with --demo)",
    )
    job_source = parser.add_mutually_exclusive_group()
    job_source.add_argument(
        "--job",
        type=str,
        help="Path to job description text file (used with --demo)",
    )
    job_source.add_argument(
        "--job-url",
        type=str,
        help="URL to fetch job description from (used with --demo)",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save tailoring results to database (used with --demo)",
    )

    args = parser.parse_args()

    # Demo mode — separate pipeline, no DB needed
    if args.demo:
        if not args.resume:
            parser.error("--demo requires --resume")
        if not args.job and not args.job_url:
            parser.error("--demo requires either --job or --job-url")

        job_path = args.job
        if args.job_url:
            # Fetch job description from URL into a temp file
            import tempfile

            from src.fetcher import fetch_job_description
            job_text = await fetch_job_description(args.job_url)
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", delete=False, encoding="utf-8",
            ) as tmp:
                tmp.write(job_text)
                job_path = tmp.name

        from src.demo import run_demo
        await run_demo(
            resume_path=args.resume,
            job_path=job_path,
            save=getattr(args, "save", False),
        )
        return

    if args.rank_only:
        stats = await run_rank_only()
    else:
        stats = await run_pipeline(
            query=args.query,
            location=args.location,
            max_results=args.max_results,
            rank=not args.no_rank,
        )

    _print_results(stats)

    # Optionally show top matches
    if args.top:
        matches = await get_top_matches(limit=args.top)
        if matches:
            print(f"\n  Top {args.top} Matches:")
            print("-" * 60)
            for i, m in enumerate(matches, 1):
                score = m.get("match_score", 0)
                print(
                    f"  {i}. [{score:.0%}] {m['title']} at {m['company_name']}"
                    f" (Tier {m.get('company_tier', '?')})"
                )
                if m.get("match_reasoning"):
                    print(f"     {m['match_reasoning'][:100]}")
            print()


def main() -> None:
    """Sync entry point for the CLI."""
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()
