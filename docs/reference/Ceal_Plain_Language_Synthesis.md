# Ceal Project: Plain-Language Synthesis

**What this document is:** A complete guide to understanding the Ceal project and its code, written for someone who doesn't code. Every technical term is explained. Every code pattern is broken down into what it actually does and why.

**Last updated:** April 2, 2026

---

## Research Overview

- **What was reviewed:** The entire Ceal codebase (Python pipeline code, 202 tests), architecture documentation, team persona instructions, Asana project board (15 tasks across 4 phases), career strategy documents, and sprint execution plans
- **Purpose:** Make the project understandable to any stakeholder -- regardless of coding background -- so they could confidently read the code, understand decisions, and evaluate progress
- **Author context:** Josh Hillard built this from zero coding experience, applying systems thinking from 6 years of technical leadership at Toast (FinTech). Ceal is both a functional tool and a portfolio piece demonstrating production-grade engineering skills

---

## Part 1: What Is This Project?

### The One-Sentence Version

Ceal is a robot that searches job boards 24/7, reads every listing, scores how well each one matches Josh's resume using AI, and ranks the best opportunities -- all automatically, without manually browsing job sites.

### The Full Picture

| Term | What It Means |
|------|--------------|
| **Ceal** | The project's name (pronounced "KAYL"). It blends Cape Verdean *ceu* (sky) and Irish *Cael* (heavens) -- two cultures, same sky. A personal nod to heritage and aspiration. |
| **Pipeline** | A system where data flows through multiple stages in order, like an assembly line. Each stage does one specific job and passes its output to the next stage. |
| **Scraping** | Automatically reading information from websites. Instead of a person browsing LinkedIn and copying job listings, the bot reads the same pages and extracts the data. |
| **LLM (Large Language Model)** | An AI system like Claude that can read and understand text. Ceal uses Claude to read job descriptions and judge how well they match Josh's resume -- something a keyword search can't do. |
| **Paper trading (from Moss Lane)** | A concept Josh applied here too: test the system with real data but no real consequences before relying on it. |

### The Goal

**Automate the job search pipeline end-to-end.** From finding listings, to scoring fit, to (eventually) auto-filling applications -- reducing what normally takes 45 minutes per listing down to under 2 minutes. But equally important: the project itself *is* the resume. Every architectural decision, every library choice, and every line of code is designed to demonstrate skills that hiring managers at Stripe, Datadog, Google, and Coinbase look for.

### The Four Phases

| Phase | What It Does | Status |
|-------|-------------|--------|
| **Phase 1: Scraping & Matching** | Find job listings, clean them up, score them with AI | Complete |
| **Phase 2: Resume Tailoring** | Auto-generate role-specific resume emphasis for each listing | Complete — demo mode, batch tailoring, .docx export, prompt v1.1 |
| **Sprint 1: Web UI** | Browser-based dashboard, job listings, and demo mode | Complete — FastAPI + Jinja2, 5 pages |
| **Phase 3: Application CRM** | Track every application, Kanban board, follow-up reminders | Complete — state-machine transitions, stale reminders |
| **Phase 4: Auto-Apply** | Pre-fill applications automatically, with human approval before submit | Complete — pre-fill engine, approval queue, confidence scoring, 202 tests |

---

## Part 2: How the Pipeline Works (The Big Picture)

The system runs as a three-stage pipeline. Think of it like a factory assembly line:

```
SCRAPE --> NORMALIZE --> RANK
  |            |            |
  v            v            v
Find jobs    Clean up    Score with
on LinkedIn  the data    AI (Claude)
             & extract
             skills        |
                           v
                     Save to Database
```

### Stage 1: SCRAPE (Finding Job Listings)

The bot searches LinkedIn's public job listings using search terms like "Technical Solutions Engineer" and "Boston, MA." It reads multiple pages of results, pulling out the key details from each listing: title, company, location, salary, and full description.

**Key detail:** The scraper uses LinkedIn's *public guest API* -- the same data anyone sees without logging in. No hacking, no login credentials, no terms-of-service violations.

### Stage 2: NORMALIZE (Cleaning the Data)

Raw job listings are messy. They contain HTML formatting codes, inconsistent salary formats ("$90K-$140K" vs "$90,000 to $140,000"), and descriptions buried in formatting junk. The normalizer:

1. **Strips HTML** -- removes all the formatting codes, leaving clean text
2. **Parses salaries** -- converts "$90K-$140K" into two clean numbers: min = 90,000, max = 140,000
3. **Extracts skills** -- identifies which technical skills each job requires (Python, SQL, Docker, etc.)
4. **Validates everything** -- runs every field through strict rules before saving. If anything is malformed, it's rejected (not silently saved with bad data)

### Stage 3: RANK (AI-Powered Scoring)

This is where Ceal gets smart. For each cleaned job listing, the bot sends the job description plus Josh's resume to Claude (Anthropic's AI) and asks: "How well does this person match this job?"

Claude returns:
- **A score from 0.0 to 1.0** (0% match to 100% match)
- **A written explanation** of why it scored that way ("Strong FinTech overlap, but missing Kubernetes experience")
- **Skills matched** -- what the candidate has that the job wants
- **Skills missing** -- what gaps exist

**Why AI instead of keyword matching?** Because "payment processing experience" on a resume should match "FinTech background required" in a listing. A keyword search would miss that connection entirely. An AI understands the *meaning*, not just the words.

---

## Part 3: The Tiered Company Strategy

Not all companies are treated equally. Ceal has a built-in strategy system that automatically classifies companies into three tiers:

| Tier | Strategy | Examples | What It Means |
|------|----------|----------|---------------|
| **Tier 1: Apply Now** | Roles where Josh's experience is a direct fit | Stripe, Coinbase, Datadog, Toast, Plaid, Square | Apply immediately -- skills align today |
| **Tier 2: Build Credential** | Roles that need one more qualification | MongoDB, Cloudflare | Apply while building the missing credential (e.g., a cloud certification) |
| **Tier 3: Campaign** | Aspirational roles requiring a longer strategy | Google, Amazon, Microsoft | 3-6 month campaign: build portfolio, network, prepare for rigorous interviews |

This classification is stored in the database and happens automatically when a job is processed. When Josh looks at his results, Tier 1 jobs float to the top because they're the ones he should act on today.

---

## Part 4: Key Code Explained

This section takes real code from the project and explains each piece so you could read it confidently.

### 4.1 The Pipeline Orchestrator

**What it is:** The conductor of the orchestra. It creates the stages, connects them, and starts the music.

```python
async def run_pipeline(query, location, max_results=100, resume_text=None, rank=True):
    await init_db()

    raw_queue = asyncio.Queue(maxsize=100)
    clean_queue = asyncio.Queue(maxsize=100)

    scraper_task = asyncio.create_task(scraper_stage(raw_queue, query, location))
    normalizer_task = asyncio.create_task(normalizer_stage(raw_queue, clean_queue))
    ranker_task = asyncio.create_task(ranker_stage(clean_queue, resume_text))

    await asyncio.gather(scraper_task, normalizer_task, ranker_task)
```

**Line-by-line:**

| Code | What It Does |
|------|-------------|
| `async def run_pipeline(...)` | **Defines the main function** that runs the whole system. `async` means it can handle multiple tasks at once. |
| `await init_db()` | **Prepares the database** -- creates tables if they don't exist yet. |
| `raw_queue = asyncio.Queue(maxsize=100)` | **Creates a conveyor belt** between stages. `maxsize=100` means it can hold 100 items at most -- if it's full, the scraper pauses until the normalizer catches up. This prevents the system from using unlimited memory. |
| `asyncio.create_task(scraper_stage(...))` | **Starts the scraper running** in the background, like starting the first machine on the assembly line. |
| `asyncio.create_task(normalizer_stage(...))` | **Starts the normalizer** -- it immediately begins waiting for items from the scraper. |
| `asyncio.create_task(ranker_stage(...))` | **Starts the ranker** -- it waits for the normalizer to finish cleaning data. |
| `await asyncio.gather(...)` | **Waits for all three stages** to complete before the function returns. |

**Key concept -- Queues as conveyor belts:** The three stages don't call each other directly. They communicate through queues (conveyor belts). The scraper puts raw jobs on Belt 1. The normalizer picks them off Belt 1, cleans them, and puts them on Belt 2. The ranker picks them off Belt 2 and scores them. If any stage is slow, the queue applies "backpressure" -- the upstream stage pauses until there's room. This is the same pattern used by major tech companies like Stripe and Google in their data processing systems.

### 4.2 Data Validation Models (Pydantic)

**What they are:** Strict rules that define what valid data looks like. Think of them as bouncers at a club -- if your data doesn't meet the dress code, it doesn't get in.

```python
class RawJobListing(BaseModel):
    external_id: str
    source: JobSource
    title: str
    company_name: str
    url: str
    location: str | None = None
    salary_text: str | None = None
    description_raw: str | None = None

class JobListingCreate(BaseModel):
    external_id: str
    source: JobSource
    title: str = Field(..., min_length=1, max_length=500)
    company_name: str = Field(..., min_length=1, max_length=300)
    salary_min: float | None = Field(default=None, ge=0)
    salary_max: float | None = Field(default=None, ge=0)
```

**What's happening:**

| Concept | What It Means |
|---------|---------------|
| `RawJobListing` | **What the scraper produces.** Loose rules -- because raw data from websites is messy and you can't control its format. |
| `JobListingCreate` | **What the normalizer produces.** Strict rules -- the data has been cleaned and must now meet quality standards before entering the database. |
| `str` | A text field (a word, sentence, or paragraph). |
| `str \| None = None` | "This can be text OR empty. If not provided, default to empty." The `\|` means "or." |
| `Field(..., min_length=1)` | "This field is required, and it must be at least 1 character." The `...` means "required." |
| `Field(default=None, ge=0)` | "This is optional, but if provided, it must be zero or greater." `ge` = "greater than or equal to." |

**Why two separate models?** The scraper deals with the real world (messy HTML, missing fields). The normalizer is the gatekeeper -- it transforms messy data into clean data and validates every field. By using two separate models, the system forces the normalizer to explicitly handle every transformation. Nothing slips through accidentally.

### 4.3 The AI Ranker

**What it is:** The brain of the operation. It reads job descriptions and Josh's resume, then judges the fit.

```python
class LLMRanker:
    async def rank_job(self, job_id, job_title, company_name, job_description, resume_text):
        prompt = RANKING_PROMPT_TEMPLATE.format(
            resume_text=resume_text,
            job_title=job_title,
            company_name=company_name,
            job_description=job_description[:4000],
        )
        raw_response = await self._call_llm(prompt)
        result = self._parse_response(raw_response, job_id)
        return result
```

| Code | What It Does |
|------|-------------|
| `RANKING_PROMPT_TEMPLATE.format(...)` | **Builds a question for the AI.** It fills in a template with the specific job details and resume. Like a form letter where you fill in the blanks. |
| `job_description[:4000]` | **Trims the description to 4,000 characters.** AI models have a maximum input size, and most job descriptions have repetitive legal text at the end. The important stuff is at the top. |
| `await self._call_llm(prompt)` | **Sends the question to Claude** and waits for the answer. |
| `self._parse_response(raw_response, job_id)` | **Validates the AI's answer.** Claude returns text -- this function checks that the score is actually between 0 and 1, that reasoning was provided, and that the response is properly formatted. If the AI returns garbage, this catches it. |

**Why validate AI output?** AI models occasionally return unexpected formats -- a score of 1.5 instead of 1.0, or text instead of JSON. The parser catches these errors before they corrupt the database. This is called "defensive programming" -- don't trust any input, even from your own AI.

### 4.4 The Shutdown Signal Pattern

**What it is:** A clever way for stages to tell each other "I'm done."

```python
_SHUTDOWN = object()

async def scraper_stage(raw_queue, query, location):
    try:
        # ... scrape jobs and put them on the queue ...
        for job in jobs:
            await raw_queue.put(job)
    finally:
        await raw_queue.put(_SHUTDOWN)
```

| Code | What It Does |
|------|-------------|
| `_SHUTDOWN = object()` | **Creates a unique marker** -- like a special flag. It's not a job listing; it's a signal that means "no more data is coming." |
| `finally:` | **"No matter what happens -- even if there was an error -- run this code."** This guarantees the shutdown signal is always sent, so the next stage doesn't wait forever. |
| `raw_queue.put(_SHUTDOWN)` | **Puts the flag on the conveyor belt.** When the normalizer picks this up, it knows the scraper is finished and there's nothing left to process. |

**Why not just check if the queue is empty?** Because "empty" could mean "the scraper is still working but hasn't produced anything yet." The sentinel (flag) pattern explicitly distinguishes between "no data yet" and "no data ever." This is a standard pattern in production systems.

---

## Part 5: The Database (Where Everything Is Stored)

### The 7-Table Design

All data is stored in a SQLite database -- a single file that acts like a spreadsheet with superpowers.

| Table | What It Stores | Why It Exists |
|-------|---------------|---------------|
| **job_listings** | Every job found: title, company, salary, description, match score, status | The core data -- this is what the whole pipeline produces |
| **skills** | A vocabulary of 40+ skills (Python, SQL, Docker, etc.) with importance weights | Enables structured matching: "does this job need Python?" not just keyword searching |
| **job_skills** | Which skills each job requires, and whether they're required vs. nice-to-have | Links jobs to skills -- answers "show me all jobs needing Python AND Docker" |
| **resume_profiles** | Josh's resume(s), potentially in multiple versions | Allows A/B testing different resume strategies against the same job pool |
| **resume_skills** | Josh's skills with proficiency levels and evidence | Maps "Python: proficient, 1 year, built autonomous trading bot" for matching |
| **company_tiers** | The Tier 1/2/3 classification rules | Auto-classifies "Stripe" as Tier 1 (apply now), "Google" as Tier 3 (campaign) |
| **scrape_log** | Metrics from every scraping run: how many found, how long it took, any errors | Operational visibility -- like a dashboard for the pipeline's health |

### Key Database Design Decisions

| Decision | What It Means | Why It Matters |
|----------|---------------|----------------|
| **Deduplication key** | `external_id + source` together must be unique | LinkedIn job #12345 and Indeed job #12345 are different listings. Without this rule, you'd get phantom duplicates |
| **WAL mode** | Write-Ahead Logging allows reading and writing at the same time | The scraper can write new jobs while the ranker reads existing ones -- no waiting |
| **Status state machine** | Jobs move through statuses: scraped -> ranked -> applied -> responded -> offer/rejected | Tracks every listing through the full lifecycle, from discovery to outcome |
| **Audit timestamps** | Every record tracks when it was created and last updated | Built-in history -- "when did we last see this listing?" is always answerable |

---

## Part 6: The Skill Weighting System

Not all skills are equal for Josh's job search. The database contains 40+ skills, each with a **weight** from 0.0 to 1.0 that reflects how important it is for his target roles:

| Category | Example Skills | Typical Weight | Why |
|----------|---------------|----------------|-----|
| **Languages** | Python (1.0), SQL (0.9), Bash (0.7) | High | These appear in virtually every target job listing |
| **Domain** | Payment Processing (0.9), FinTech (0.9), SaaS (0.8) | High | Josh's 6 years at Toast make these a direct match |
| **Soft Skills** | Technical Escalation Mgmt (1.0), Cross-Functional Leadership (0.9) | Very High | These differentiate Josh from pure-coder applicants |
| **Infrastructure** | Docker (0.9), Linux (0.9), CI/CD (0.8) | High | Shows production-readiness, not just scripting |
| **Cloud** | GCP (0.9), AWS (0.8) | High | Cloud experience is near-universal in target roles |
| **Frameworks** | asyncio (0.9), FastAPI (0.8) | High | Demonstrates modern Python proficiency |

**Why this matters:** When the AI ranks a job, the weights influence the scoring. A job requiring "Payment Processing" (weight 1.0) scores higher than one requiring "Azure" (weight 0.5), because the former is a stronger match for Josh's experience.

---

## Part 7: External Services Map

| Service | What It Does | Analogy | Cost |
|---------|-------------|---------|------|
| **LinkedIn (Guest API)** | Source of job listings | A job board that the bot reads automatically | Free (public data) |
| **Claude (Anthropic API)** | Reads job descriptions and scores them against the resume | A very fast, very smart career advisor who reads every listing | Pay-per-use (small cost) |
| **SQLite** | Stores all data in a single file | A spreadsheet that can answer complex questions instantly | Free (built into Python) |
| **GitHub Actions** | Automatically runs all 202 tests every time code changes | A quality inspector who checks every update before it goes live | Free (open source projects) |

---

## Part 8: The Test Suite

The project has **202 automated tests** that verify the system works correctly. Here's what they cover:

| Test Area | # Tests | What They Check |
|-----------|---------|----------------|
| **Database** | ~40 | Schema creation, data insertion, deduplication, tier assignment, ranking updates, resume profiles |
| **Scrapers** | ~20 | HTML parsing, pagination, rate limiting, error handling, blocked request detection |
| **Normalizer** | ~15 | Salary parsing ("$90K" -> 90000), HTML cleanup, skill extraction, batch processing |
| **Ranker** | ~10 | AI response parsing, markdown code fence handling, score validation, API error handling |
| **Tailoring** | ~40 | Resume parsing, skill extraction, model validation, persistence, demo mode, batch, export |
| **Web Routes** | 9 | Dashboard rendering, job listing filters, demo form POST, LLM mock integration |
| **CRM** | 11 | State machine validation, Kanban board routes, stale application detection |
| **Auto-Apply** | 19 | Pre-fill engine, approval queue routes, application DB functions, model validation |
| **Fetcher** | 4 | URL validation, HTML stripping, timeout handling |
| **Integration** | 4 | Full pipeline flow: scrape -> normalize -> save to database |

**Why testing matters so much:** In interviews, "Do you write tests?" is the single most common technical filter. Having 202 passing tests with CI/CD (automated testing on every code change across Python 3.11 and 3.12) demonstrates that Josh builds production-grade software, not just scripts that work on his laptop.

---

## Part 9: Current Status (as of April 2, 2026)

### Where Things Stand

| Metric | Value |
|--------|-------|
| **Current Phase** | All 4 phases complete |
| **Phase 1** | Complete -- scraping, normalizing, and ranking all work end-to-end |
| **Phase 2** | Complete -- demo mode CLI, batch tailoring, .docx export, URL fetcher, persistence layer, prompt v1.1 |
| **Phase 3** | Complete -- CRM Kanban board, state-machine status transitions, stale reminders |
| **Phase 4** | Complete -- auto-apply pre-fill engine, approval queue, confidence scoring, CRM sync |
| **Web UI** | 5 pages -- Dashboard, Jobs, Applications (Kanban), Auto-Apply (approval queue), Demo |
| **Total Tests** | 202 passing (198 unit + 4 integration) |
| **Codebase** | 30+ source files, 20+ web files, full test coverage |
| **CI/CD** | GitHub Actions — 6 jobs (lint, unit 3.11/3.12, integration 3.11/3.12, coverage ≥80%) all green |
| **Live Data** | 50 real job listings scraped, normalized, and LLM-ranked from LinkedIn |

### What's Working

1. **The full Phase 1 pipeline runs end-to-end.** Scrape LinkedIn -> clean data -> score with Claude -> save ranked results to database. First live run: 50 jobs in 283 seconds.
2. **Phase 2 resume tailoring** is fully functional. Parse resume -> analyze skill gaps -> generate X-Y-Z bullets via Claude API -> save to DB -> export to .docx.
3. **Phase 3 CRM** tracks every application through an 8-state lifecycle with a Kanban board and stale reminders.
4. **Phase 4 auto-apply** pre-fills ATS form fields from resume data with confidence scoring, human approval queue, and CRM sync on approval.
5. **Browser-based web UI** at `localhost:8000` with five pages: Dashboard, Jobs, Applications (Kanban), Auto-Apply (approval queue), Demo.
6. **202 tests all passing.** CI pipeline verifies this automatically on every push across Python 3.11 and 3.12.
7. **Automatic tier classification.** Companies auto-classified into Tier 1/2/3. First run: 3 Tier 1, 5 Tier 3.

### The Roadmap

| Phase | Target Date | Key Deliverable | Status |
|-------|-------------|-----------------|--------|
| **Phase 1** (Scraping & Matching) | March 2026 | 3-stage async pipeline | Complete |
| **Phase 2** (Resume Tailoring) | April 2026 | Demo mode, batch, export, persistence, prompt v1.1 | Complete |
| **Phase 3** (Application CRM) | April 2026 | Kanban board, state-machine transitions, stale reminders | Complete |
| **Phase 4** (Auto-Apply) | April 2026 | Pre-fill engine, approval queue, confidence scoring | Complete |

---

## Part 10: Key Terms -- Glossary

| Term | Definition |
|------|-----------|
| **API (Application Programming Interface)** | A way for two programs to talk to each other. When Ceal asks LinkedIn for job listings, it's using LinkedIn's API -- like ordering from a menu at a restaurant instead of going into the kitchen. |
| **async / await** | Python's way of doing multiple things at once. `await` means "start this task, and while we're waiting for the answer, do something else." Like texting someone and doing dishes while you wait for their reply. |
| **Backpressure** | A safety mechanism that prevents the system from being overwhelmed. If the scraper finds jobs faster than the normalizer can clean them, the queue fills up and the scraper automatically pauses. Like a conveyor belt that stops when the bin at the end is full. |
| **CI/CD (Continuous Integration / Continuous Deployment)** | A system that automatically tests code every time a change is made. If tests fail, the change is blocked. It's like having a quality inspector check every widget before it leaves the factory. |
| **Claude** | Anthropic's AI model. Ceal uses it to read job descriptions and score them against Josh's resume. It understands meaning, not just keywords -- so "FinTech experience" matches "payment processing background." |
| **Concurrency** | Doing multiple things at the same time. The scraper can fetch several job pages simultaneously instead of one at a time. Like having 3 cooks in a kitchen instead of 1. |
| **Database (SQLite)** | A file that stores structured data. Every job listing, every score, every skill -- organized in tables that can be searched instantly. SQLite runs in a single file with no server needed. |
| **Deduplication** | Preventing the same job from being saved twice. If the bot scrapes LinkedIn on Monday and again on Tuesday, jobs from Monday aren't duplicated -- they're recognized and skipped. |
| **.env File** | A text file that stores secrets (API keys, passwords) separately from the code. This way, the code can be shared publicly on GitHub without exposing private credentials. |
| **ETL (Extract, Transform, Load)** | A standard data engineering pattern. Extract raw data (scrape), Transform it (normalize), Load it (save to database). This is the pattern behind every major data pipeline at every major tech company. |
| **Event-Driven Architecture** | A design where system components communicate through messages (events) rather than direct calls. Each stage works independently and only reacts when it receives data. Like a relay race -- each runner only starts when they receive the baton. |
| **Guest API** | A public endpoint that doesn't require login or authentication. LinkedIn's guest job search shows the same data anyone sees when browsing without logging in. |
| **HTML** | The formatting language of web pages. Raw job listings contain HTML codes like `<strong>Requirements:</strong>`. The normalizer strips these codes to get clean text. |
| **httpx** | A Python library for making web requests (like fetching a web page). Ceal uses it to communicate with the Claude API. |
| **Idempotent** | An operation that produces the same result no matter how many times you run it. Running the scraper 10 times on the same jobs produces the same database -- no duplicates, no corruption. Like pressing an elevator button 10 times -- it still only goes to one floor. |
| **JSON** | A standard format for structured data. `{"name": "Stripe", "tier": 1}` -- readable by both humans and computers. Claude returns its scores in JSON format. |
| **LLM (Large Language Model)** | An AI system trained on text that can understand and generate language. Claude is an LLM made by Anthropic. |
| **Match Score** | A number from 0.0 to 1.0 indicating how well a job matches Josh's resume. 0.0 = no fit. 1.0 = perfect fit. Computed by the AI ranker stage. |
| **Normalizer** | The middle stage of the pipeline. Takes messy, raw data from the scraper and produces clean, validated, structured data for the ranker. Like a translator who converts rough notes into a polished document. |
| **Pydantic** | A Python library that enforces data rules. "This field must be a number between 0 and 1." If data doesn't follow the rules, it's rejected immediately. Used by major frameworks like FastAPI. |
| **Queue** | A data structure that holds items in order (first in, first out). In Ceal, queues connect pipeline stages -- the scraper puts jobs in, the normalizer takes them out. Like a conveyor belt. |
| **Rate Limiting** | Controlling how fast the bot sends requests to avoid overwhelming (or getting blocked by) external services. The scraper waits 2 seconds between requests and never sends more than 3 at once. |
| **Resume Tailoring** | Automatically adjusting which parts of a resume to emphasize based on what a specific job listing requires. Phase 2 of Ceal. |
| **Scraper** | The first stage of the pipeline. Automatically reads job listings from websites (like LinkedIn) and extracts the key information. Like a research assistant who reads every page and takes notes. |
| **Semaphore** | A concurrency control mechanism. "Only 3 requests at a time." Like a bouncer at a club who only lets 3 people in at once. |
| **Sentinel** | A special marker value that signals "no more data." When the scraper finishes, it puts a sentinel on the queue so the normalizer knows to stop waiting. Like a "last call" announcement at a bar. |
| **SQLAlchemy** | A Python library for working with databases. Provides a clean interface for reading and writing data without writing raw SQL queries every time. |
| **structlog** | A logging library that writes structured, searchable log entries. Instead of "Error happened," it writes `{"event": "ranking_failed", "job_id": 42, "error": "timeout"}` -- queryable and debuggable. |
| **Test Suite** | The collection of automated tests that verify the system works correctly. Ceal has 202 tests. Running them takes seconds and catches bugs before they reach production. |
| **Tier (Company Tier)** | Ceal's classification system for target companies. Tier 1 = apply now (Stripe, Coinbase). Tier 2 = need one more credential (MongoDB). Tier 3 = long campaign (Google, Amazon). |
| **Upsert** | "Insert if new, update if it already exists." The database operation that makes scraping idempotent -- scrape the same job twice, and it updates the existing record instead of creating a duplicate. |
| **Validation** | Checking that data meets quality rules before saving it. "Is the salary a positive number? Is the URL actually a URL? Is the score between 0 and 1?" Prevents garbage data from corrupting the system. |
| **WAL (Write-Ahead Logging)** | A database mode that allows reading and writing at the same time. The scraper can save new jobs while the ranker reads existing ones -- no waiting. |

---

## Part 11: Key Decisions and Why They Were Made

| Decision | What Was Chosen | Why | What Was Rejected |
|----------|----------------|-----|-------------------|
| **Language** | Python | Most in-demand for target roles, huge ecosystem, Josh is learning from scratch | Rust (too complex), JavaScript (less suited for data pipelines) |
| **Database** | SQLite | Single file, no server needed, good enough for one user's job search | PostgreSQL (overkill), will migrate to Cloud SQL in Phase 3 |
| **AI for ranking** | Claude (Anthropic API) | Semantic understanding (not just keywords), structured JSON output, reliable | TF-IDF (can't understand meaning), GPT (less consistent structured output) |
| **HTTP client** | httpx | Modern, async-capable, lightweight | anthropic SDK (unnecessary dependency), aiohttp (used for scraping already) |
| **Pipeline pattern** | asyncio.Queue (producer-consumer) | Decoupled stages, backpressure, testable independently | Celery (needs Redis, overkill for Phase 1), direct function calls (couples stages) |
| **Testing** | pytest + pytest-asyncio | Industry standard, async support, 202 tests passing | unittest (less ergonomic), no tests (disqualifying in interviews) |
| **CI/CD** | GitHub Actions | Free for open source, standard in industry, automatic on every push | Jenkins (requires server), none (not production-grade) |
| **Job source** | LinkedIn guest API | Public, no auth needed, sufficient data volume | Official LinkedIn API (requires business agreement), Indeed (less structured) |
| **Logging** | structlog (JSON) | Every event is queryable, filterable by job ID or stage | print() statements (not searchable), standard logging (not structured) |

---

## Part 12: How to Read the Code (Quick Start)

If you want to open the project and orient yourself, here are the landmarks:

1. **`src/main.py`** -- The conductor. Creates the pipeline, connects the stages, runs everything. Start here to understand the flow.

2. **`src/models/entities.py`** -- The data contracts. Every data type in the system is defined here with validation rules. Read this to understand what data flows through the pipeline.

3. **`src/models/database.py`** -- The storage layer. All database operations (save, read, update, search) are here.

4. **`src/scrapers/linkedin.py`** -- Stage 1. Reads LinkedIn job pages and extracts listing data.

5. **`src/normalizer/pipeline.py`** -- Stage 2. Cleans HTML, parses salaries, extracts skills.

6. **`src/ranker/llm_ranker.py`** -- Stage 3. Sends jobs to Claude and parses the AI's scoring response.

7. **`src/web/app.py`** -- The web application factory. Creates the FastAPI app, registers 5 route modules, serves the browser-based UI.

8. **`src/web/routes/`** -- Five route modules: dashboard (pipeline stats), jobs (ranked listings), applications (CRM Kanban), apply (auto-apply approval queue), demo (interactive tailoring).

9. **`src/apply/prefill.py`** -- The pre-fill engine. Extracts resume fields (name, email, phone, etc.) and maps them to common ATS form fields with confidence scores.

10. **`tests/`** -- The test suite. 202 tests organized by what they test (unit/integration) and which module they cover.

### Reading Tip: Follow the Data

The easiest way to understand the system is to follow one job listing through the pipeline:

1. **Scraper** finds it on LinkedIn -> creates a `RawJobListing`
2. **Queue 1** carries it to the normalizer
3. **Normalizer** cleans it -> creates a `JobListingCreate`, saves to database
4. **Queue 2** carries it to the ranker
5. **Ranker** sends it to Claude -> receives a `RankedResult`, updates the database
6. **Result:** A fully scored, classified job listing ready for Josh to review

---

## Part 13: The Dual Purpose

Ceal serves two goals simultaneously:

### Goal 1: Functional Tool
Automate the job search. Find listings faster, score them smarter, apply more efficiently. Reduce 45 minutes of manual work per listing to under 2 minutes.

### Goal 2: Portfolio Piece
Every architectural decision is interview-ready. The code is written to demonstrate skills that hiring managers at Tier 1 companies (Stripe, Datadog, Coinbase) look for:

| What the Code Shows | Interview Translation |
|---------------------|----------------------|
| asyncio.Queue pipeline | "I designed an event-driven architecture with backpressure control" |
| Pydantic validation at every boundary | "I enforce data contracts so corrupt data never reaches the database" |
| 93 automated tests | "I write comprehensive tests and run them in CI on every push" |
| Claude API integration | "I built a deterministic LLM integration with validated outputs" |
| SQLite with WAL mode | "I configured concurrent read/write access for the pipeline" |
| structlog JSON logging | "Every event is structured and queryable for debugging" |

The project isn't just *about* engineering -- it *is* engineering. The code itself is the proof of competence.

---

*This synthesis was generated from a complete review of the Ceal codebase, documentation, Asana project board, architecture documents, and career strategy materials. For the live code, see the `/ceal/src/` directory. For detailed architecture, see `Sol-Jobhunter_Architecture.md`.*
