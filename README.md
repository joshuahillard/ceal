# Céal

[![CI](https://github.com/joshuahillard/ceal/actions/workflows/ci.yml/badge.svg)](https://github.com/joshuahillard/ceal/actions/workflows/ci.yml)

**An event-driven career signal engine that scrapes, normalizes, ranks, tailors, and tracks job applications using LLM-powered matching.**

Céal (pronounced "KAYL") is a full-lifecycle async pipeline that processes job listings from multiple sources, extracts structured data, scores each listing against your resume using Claude's API, tailors resume bullets, and manages applications through a web-based approval queue. The name blends Cape Verdean *céu* (sky) and Irish *Cael* (heavens) — two cultures, same sky.

## Architecture

```
┌──────────┐  asyncio.Queue  ┌────────────┐  asyncio.Queue  ┌──────────┐
│ SCRAPER  │ ─────────────▶  │ NORMALIZER │ ─────────────▶  │  RANKER  │
│(Producer)│  RawJobListing   │(Transform) │ JobListingCreate │(Consumer)│
└──────────┘                  └────────────┘                  └──────────┘
     ↓                              ↓                              ↓
aiohttp + semaphore         Pydantic + regex               Claude API + SQLite
LinkedIn guest API          salary/skill parsing           match scoring + tier
                                                                   ↓
                              ┌────────────┐               ┌──────────────┐
                              │ PRE-FILL   │ ◀──────────── │  TAILORING   │
                              │  ENGINE    │  resume fields │   ENGINE     │
                              └────────────┘               └──────────────┘
                                    ↓                       X-Y-Z bullets
                              ┌────────────┐               prompt v1.1
                              │  APPROVAL  │
                              │   QUEUE    │
                              └────────────┘
                              human review → submit
```

Each stage runs as an independent `asyncio.Task`, communicating only through bounded queues. No shared state, no direct function calls — the same producer-consumer pattern used by Kafka consumers at Stripe, Datadog's intake pipeline, and Google Cloud Pub/Sub.

## Key Design Decisions

- **Async I/O with backpressure** — Semaphore-controlled concurrency respects rate limits while maximizing throughput. Queue `maxsize` prevents unbounded memory growth.
- **Pydantic at every boundary** — Schema validation between each pipeline stage means corrupt data never reaches the database. Zero invalid records in production.
- **Idempotent upserts** — `ON CONFLICT` ensures the scraper can run repeatedly without duplicates. Run it 10 times, get the same result.
- **WAL mode for concurrent access** — Write-Ahead Logging lets the ranker read while the scraper writes, avoiding lock contention.
- **Structured logging** — Every pipeline event is queryable with `structlog`. Filter by job_id, source, or stage.
- **Tier-aware ranking** — Companies are auto-classified into tiers (Tier 1: Apply Now, Tier 2: Build Credential, Tier 3: Campaign) based on a configurable lookup table.
- **State-machine transitions** — Both the CRM job lifecycle (8 states) and the auto-apply pipeline (5 states) enforce valid transitions at the database layer. Invalid transitions raise `ValueError` with clear messages.
- **Confidence scoring** — The pre-fill engine assigns per-field confidence scores so reviewers know which fields to verify.

## Tech Stack

| Library | Purpose |
|---------|---------|
| `aiohttp` | Async HTTP client with connection pooling |
| `pydantic` v2 | Data validation and schema contracts |
| `SQLAlchemy` 2.0 (async) | Database layer with async session management |
| `aiosqlite` | Non-blocking SQLite driver |
| `beautifulsoup4` | HTML parsing for job listings |
| `httpx` | HTTP client for LLM API calls |
| `structlog` | Structured JSON logging |
| `tenacity` | Retry logic with exponential backoff |
| `python-docx` | .docx resume export |
| `fastapi` | Web UI framework with async route handlers |
| `jinja2` | Server-side HTML templating |
| `pytest` + `pytest-asyncio` | 202 unit and integration tests |

## Project Structure

```
ceal/
├── src/
│   ├── main.py                  # Pipeline orchestrator + CLI
│   ├── demo.py                  # Demo mode — single-job tailoring without DB
│   ├── batch.py                 # Batch tailoring of all ranked jobs
│   ├── fetcher.py               # URL-to-text job description fetcher
│   ├── export.py                # .docx export of tailored resume bullets
│   ├── models/
│   │   ├── database.py          # Async SQLAlchemy engine, sessions, CRUD
│   │   ├── entities.py          # Pydantic models (validation layer)
│   │   └── schema.sql           # SQLite schema with triggers + indexes
│   ├── scrapers/
│   │   ├── base.py              # Abstract scraper with rate limiting + retry
│   │   └── linkedin.py          # LinkedIn guest API scraper
│   ├── normalizer/
│   │   └── pipeline.py          # HTML cleanup, salary parsing, skill extraction
│   ├── ranker/
│   │   └── llm_ranker.py        # Claude API scoring + response parsing
│   ├── tailoring/
│   │   ├── resume_parser.py     # Resume text → ParsedResume with sections
│   │   ├── skill_extractor.py   # Job ↔ resume skill gap analysis
│   │   ├── engine.py            # Claude API bullet rewriting (X-Y-Z format)
│   │   ├── models.py            # Phase 2 Pydantic models
│   │   ├── persistence.py       # Phase 2 CRUD layer (save/retrieve results)
│   │   └── db_models.py         # Phase 2 SQLAlchemy ORM table definitions
│   ├── apply/
│   │   └── prefill.py           # Pre-fill engine: resume → ATS form fields
│   ├── web/
│   │   ├── app.py               # FastAPI app factory with lifespan
│   │   ├── static/
│   │   │   └── style.css        # Shared styles (Kanban, cards, badges)
│   │   ├── routes/
│   │   │   ├── dashboard.py     # GET / — pipeline stats + CRM overview
│   │   │   ├── jobs.py          # GET /jobs — ranked listings with filters
│   │   │   ├── applications.py  # CRM Kanban board + status transitions
│   │   │   ├── apply.py         # Auto-apply approval queue + pre-fill
│   │   │   └── demo.py          # GET/POST /demo — skill gap + tailoring
│   │   └── templates/
│   │       ├── base.html             # Shared layout + nav
│   │       ├── dashboard.html        # Pipeline stats dashboard
│   │       ├── jobs.html             # Job listings table with pre-fill
│   │       ├── applications.html     # CRM Kanban board
│   │       ├── approval_queue.html   # Auto-apply queue with filters
│   │       ├── application_review.html # Field-by-field review page
│   │       ├── reminders.html        # Stale application follow-ups
│   │       └── demo.html             # Demo mode form + results
│   └── utils/
├── tests/
│   ├── unit/                    # 198 unit tests
│   │   ├── test_database.py     # Schema, upserts, tiers, ranking, profiles
│   │   ├── test_scrapers.py     # Parsing, pagination, rate limits, errors
│   │   ├── test_normalizer.py   # Salary, HTML, skills, batch processing
│   │   ├── test_ranker.py       # LLM response parsing, API mocking
│   │   ├── test_tailoring_models.py # Pydantic model validation
│   │   ├── test_demo.py         # Demo mode pipeline tests
│   │   ├── test_resume_parser.py # Resume parsing and section detection
│   │   ├── test_skill_extractor.py # Skill gap analysis tests
│   │   ├── test_persistence.py  # Tailoring CRUD round-trip tests
│   │   ├── test_batch.py        # Batch tailoring mode tests
│   │   ├── test_fetcher.py      # URL fetcher and HTML stripping tests
│   │   ├── test_export.py       # .docx export tests
│   │   ├── test_web.py          # Dashboard, jobs, demo route tests
│   │   ├── test_crm.py          # CRM state machine + Kanban route tests
│   │   └── test_autoapply.py    # Pre-fill, approval queue, model tests
│   ├── integration/             # 4 integration tests
│   │   └── test_pipeline.py     # Full scrape → normalize → DB flow
│   └── mocks/                   # Realistic HTML fixtures
├── data/
│   ├── resume.txt               # Candidate resume (plain text)
│   └── sample_job.txt           # Sample job description for testing
├── config/
├── .github/workflows/
│   └── ci.yml                   # 6-job CI matrix (lint, unit/integration 3.11+3.12, coverage)
└── pyproject.toml               # Ruff, pytest, coverage config
```

## Web UI

Céal includes a 5-page web application built with FastAPI and Jinja2:

```bash
# Launch the web server
python -m src.main --web --port 8000

# Then visit http://localhost:8000
```

| Page | URL | Description |
|------|-----|-------------|
| **Dashboard** | `/` | Pipeline stats, tier distribution, CRM overview, auto-apply counts |
| **Jobs** | `/jobs` | Ranked listings with score/tier/limit filters + Pre-Fill button |
| **Applications** | `/applications` | CRM Kanban board with drag-free status transitions |
| **Auto-Apply** | `/apply` | Approval queue: draft → ready → approved → submitted |
| **Demo** | `/demo` | Single-job skill gap analysis + LLM bullet tailoring |

## Usage

```bash
# Full pipeline: scrape → normalize → rank
python -m src.main --query "Technical Solutions Engineer" --location "Boston, MA"

# Scrape and normalize only (no LLM ranking)
python -m src.main --query "TPM" --location "Remote" --no-rank

# Re-rank existing unranked jobs (useful after improving the prompt)
python -m src.main --rank-only

# Show top 10 matches
python -m src.main --rank-only --top 10

# Launch web UI
python -m src.main --web --port 8000

# Demo mode (offline skill gap analysis)
python -m src.main --demo --resume data/resume.txt --job data/sample_job.txt

# Demo mode with LLM tailoring
echo "LLM_API_KEY=your_key_here" > .env
python -m src.main --demo --resume data/resume.txt --job data/sample_job.txt

# Fetch job from URL
python -m src.main --demo --resume data/resume.txt --job-url https://example.com/job

# Batch tailor top 20 ranked jobs
python -m src.main --batch --resume data/resume.txt

# Export tailored results to .docx
python -m src.main --export 42
```

## Database Schema

Nine tables across two phases with referential integrity, audit columns, and trigger-based `updated_at` timestamps:

**Phase 1 (schema.sql):**
- **`job_listings`** — Core listing data with deduplication key (`external_id` + `source`), 8-state lifecycle
- **`skills`** — Vocabulary of 40+ skills with categories and relevance weights
- **`job_skills`** — Many-to-many join tracking required vs. nice-to-have
- **`resume_profiles`** — Multiple resume variants for A/B testing match strategies
- **`resume_skills`** — Your skills mapped to proficiency levels with evidence
- **`company_tiers`** — Configurable tier lookup (Tier 1/2/3 role strategy)
- **`scrape_log`** — Operational metrics per scrape run (success rate, duration, errors)

**Phase 2 (Alembic-managed ORM):**
- Tailoring requests, tailored bullets, and skill gaps

**Phase 4 (schema.sql):**
- **`applications`** — Auto-apply drafts with 5-state lifecycle, confidence scoring, CRM sync
- **`application_fields`** — Pre-filled ATS form fields with per-field confidence and source tracking

## Running Tests

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Full suite (202 tests)
pytest tests/ -v

# Unit tests only
pytest tests/unit/ -v

# Integration tests only
pytest tests/integration/ -v

# With coverage report
pytest tests/ --cov=src --cov-report=term-missing
```

CI runs a 6-job matrix: lint, unit tests (Python 3.11 + 3.12), integration tests (3.11 + 3.12), and coverage (≥80% gate).

## Roadmap

- **Phase 1**: Scrape → Normalize → Rank pipeline — **complete**
- **Phase 2**: Resume tailoring — **complete**. Demo mode, batch processing, URL fetching, persistence layer, .docx export, skill gap detection, LLM-powered X-Y-Z bullet generation, prompt v1.1 with anti-keyword-stuffing.
- **Phase 3**: Application tracking CRM — **complete**. Kanban board, state-machine status transitions, stale application reminders, tier-colored cards.
- **Phase 4**: Auto-apply with approval queue — **complete**. Pre-fill engine with confidence scoring, 5-state approval lifecycle, field-by-field review, CRM sync on approval.

## License

MIT
