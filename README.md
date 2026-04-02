# Céal

[![CI](https://github.com/joshuahillard/ceal/actions/workflows/ci.yml/badge.svg)](https://github.com/joshuahillard/ceal/actions/workflows/ci.yml)

**An event-driven career signal engine that scrapes, normalizes, and ranks job listings against your resume using LLM-powered matching.**

Céal (pronounced "KAYL") is a three-stage async pipeline that processes job listings from multiple sources, extracts structured data, and scores each listing against your resume profile using Claude's API. The name blends Cape Verdean *céu* (sky) and Irish *Cael* (heavens) — two cultures, same sky.

## Architecture

```
┌──────────┐    asyncio.Queue    ┌────────────┐    asyncio.Queue    ┌──────────┐
│ SCRAPER  │ ─────────────────▶  │ NORMALIZER │ ─────────────────▶  │  RANKER  │
│(Producer)│   RawJobListing     │(Transform) │  JobListingCreate   │(Consumer)│
└──────────┘                     └────────────┘                     └──────────┘
     ↓                                ↓                                  ↓
aiohttp + semaphore           Pydantic + regex                  Claude API + SQLite
LinkedIn guest API            salary/skill parsing              match scoring + tier
```

Each stage runs as an independent `asyncio.Task`, communicating only through bounded queues. No shared state, no direct function calls — the same producer-consumer pattern used by Kafka consumers at Stripe, Datadog's intake pipeline, and Google Cloud Pub/Sub.

## Key Design Decisions

- **Async I/O with backpressure** — Semaphore-controlled concurrency respects rate limits while maximizing throughput. Queue `maxsize` prevents unbounded memory growth.
- **Pydantic at every boundary** — Schema validation between each pipeline stage means corrupt data never reaches the database. Zero invalid records in production.
- **Idempotent upserts** — `ON CONFLICT` ensures the scraper can run repeatedly without duplicates. Run it 10 times, get the same result.
- **WAL mode for concurrent access** — Write-Ahead Logging lets the ranker read while the scraper writes, avoiding lock contention.
- **Structured logging** — Every pipeline event is queryable with `structlog`. Filter by job_id, source, or stage.
- **Tier-aware ranking** — Companies are auto-classified into tiers (Tier 1: Apply Now, Tier 2: Build Credential, Tier 3: Campaign) based on a configurable lookup table.

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
| `pytest` + `pytest-asyncio` | 158 unit and integration tests |

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
│   │   ├── schema.sql           # SQLite schema with triggers + indexes
│   │   └── seed_skills.sql      # Skill vocabulary (40+ skills, weighted)
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
│   └── utils/
├── tests/
│   ├── unit/                    # 154 unit tests
│   │   ├── test_database.py     # Schema, upserts, tiers, ranking, profiles
│   │   ├── test_scrapers.py     # Parsing, pagination, rate limits, errors
│   │   ├── test_normalizer.py   # Salary, HTML, skills, batch processing
│   │   ├── test_ranker.py       # LLM response parsing, API mocking
│   │   ├── test_demo.py         # Demo mode pipeline tests
│   │   ├── test_resume_parser.py # Resume parsing and section detection
│   │   ├── test_skill_extractor.py # Skill gap analysis tests
│   │   ├── test_persistence.py  # Tailoring CRUD round-trip tests
│   │   ├── test_batch.py        # Batch tailoring mode tests
│   │   ├── test_fetcher.py      # URL fetcher and HTML stripping tests
│   │   └── test_export.py       # .docx export tests
│   ├── integration/             # 4 integration tests
│   │   └── test_pipeline.py     # Full scrape → normalize → DB flow
│   └── mocks/                   # Realistic HTML fixtures
├── data/
│   ├── resume.txt               # Candidate resume (plain text)
│   └── sample_job.txt           # Sample job description for testing
└── config/
```

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
```

## Demo Mode

Run the tailoring pipeline on a single job description without live scraping:

```bash
# Offline mode (skill gap analysis only, no API key needed)
PYTHONPATH=. python -m src.main --demo --resume data/resume.txt --job data/sample_job.txt

# Full mode with LLM-powered bullet tailoring
echo "LLM_API_KEY=your_key_here" > .env
PYTHONPATH=. python -m src.main --demo --resume data/resume.txt --job data/sample_job.txt

# Fetch job description from a URL instead of a local file
PYTHONPATH=. python -m src.main --demo --resume data/resume.txt --job-url https://example.com/job

# Save tailoring results to the database
PYTHONPATH=. python -m src.main --demo --resume data/resume.txt --job data/sample_job.txt --save
```

## Batch Mode

Process all ranked jobs through the tailoring pipeline at once:

```bash
# Tailor top 20 ranked jobs (default)
PYTHONPATH=. python -m src.main --batch --resume data/resume.txt

# Tailor top 50 jobs with minimum 70% match score
PYTHONPATH=. python -m src.main --batch --resume data/resume.txt --limit 50 --min-score 0.7
```

## Export

Export tailored results to a Word document:

```bash
# Export tailored results for job_id=42
PYTHONPATH=. python -m src.main --export 42

# Export to a custom directory
PYTHONPATH=. python -m src.main --export 42 --export-dir reports/
```

## Database Schema

Seven normalized tables with referential integrity, audit columns, and a trigger-based `updated_at` timestamp:

- **`job_listings`** — Core listing data with deduplication key (`external_id` + `source`)
- **`skills`** — Vocabulary of 40+ skills with categories and relevance weights
- **`job_skills`** — Many-to-many join tracking required vs. nice-to-have
- **`resume_profiles`** — Multiple resume variants for A/B testing match strategies
- **`resume_skills`** — Your skills mapped to proficiency levels with evidence
- **`company_tiers`** — Configurable tier lookup (Tier 1/2/3 role strategy)
- **`scrape_log`** — Operational metrics per scrape run (success rate, duration, errors)

## Running Tests

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. pytest tests/ -v
```

## Roadmap

- **Phase 2**: Resume tailoring — **complete**. Demo mode, batch processing, URL fetching, persistence layer, .docx export, skill gap detection, LLM-powered X-Y-Z bullet generation.
- **Phase 3**: Application tracking CRM — dashboard, response rates, follow-up reminders
- **Phase 4**: Auto-apply with approval queue — pre-fill applications, human reviews before submit

## License

MIT
