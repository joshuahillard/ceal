# Céal Phase 2B — Claude Code Implementation Prompt
## Generated: April 1, 2026
## Objective: Persist tailoring results, add batch mode, add URL fetching, export to .docx

---

## HOW TO USE

1. Open Claude Code in your terminal
2. `cd C:\Users\joshb\Documents\GitHub\ceal`
3. Paste the entire prompt below (everything between the `---START---` and `---END---` markers)

---START---

You are working on the Céal project — an AI-powered career signal engine. This is a Python async pipeline that scrapes job listings, normalizes them, ranks them with Claude API, and tailors resume bullets.

## ABSOLUTE RULES — READ BEFORE DOING ANYTHING

### Security
1. NEVER hardcode API keys, secrets, or credentials in any source file.
2. ALL secrets are loaded from `.env` via `python-dotenv` (already configured in `src/models/database.py` line 46: `load_dotenv()`).
3. The `.env` file is already in `.gitignore` (line 2). NEVER remove it from `.gitignore`.
4. NEVER print, log, or expose API key values — not in error messages, not in debug output, not in test fixtures.
5. When fetching URLs (for the `--job-url` feature), NEVER send the API key as a query parameter, header, or in any HTTP request to external sites. The API key is ONLY used for calls to `https://api.anthropic.com/v1/messages`.
6. Before committing, run: `git diff --cached | findstr -i "sk-ant api.key secret password token"` — if anything matches, unstage that file and fix it.

### No Hallucination
7. BEFORE modifying any file, READ IT FIRST using your file reading tools. Do not assume file contents.
8. ONLY import modules that exist in `requirements.txt` or the Python standard library. The full dependency list is in `requirements.txt` at the project root. Read it before adding imports.
9. ONLY reference functions, classes, and methods that actually exist. If you need to call a function, grep for its definition first.
10. Do not invent database tables. The Phase 1 tables are defined in `src/models/schema.sql`. The Phase 2 tables are defined in `src/tailoring/db_models.py`. Read both files before writing any database code.
11. Do not assume the state of any file based on memory. The canonical source of truth is the file on disk RIGHT NOW.

### Python 3.10+ Compatibility
12. Use `datetime.timezone.utc` — NEVER `datetime.UTC` (added in Python 3.11, but this project runs on 3.10+ environments including CI).
13. NOTE: `src/tailoring/db_models.py` line 87 currently has `datetime.UTC` in the `_utcnow()` function. You MUST fix this as your first action.

### Linting (ruff)
14a. The ruff config is in `pyproject.toml`. BEFORE running any code, read it and verify:
    - `target-version` is `"py310"` (NOT `"py311"`). If it says `py311`, change it to `py310`.
    - The `ignore` list includes `"UP017"`. If it does not, add it with comment: `# datetime-utc-alias — datetime.UTC requires 3.11+, use timezone.utc for 3.10 compat`
14b. After every implementation step, run BOTH:
    - `$env:PYTHONPATH="."; python -m ruff check src/ tests/` — fix all lint errors before proceeding
    - `$env:PYTHONPATH="."; python -m pytest tests/ -q --tb=short` — confirm 0 test failures
14c. Common lint issues to fix proactively:
    - F401 (unused imports): Remove any import you don't use.
    - I001 (unsorted imports): Let ruff auto-fix with `python -m ruff check --fix src/ tests/`
    - F841 (unused variables): Remove assigned-but-unused variables.

### Architecture
15. ALL new source files go under `src/`. ALL new test files go under `tests/unit/` or `tests/integration/`.
16. EVERY function that produces data crossing a module boundary MUST validate through Pydantic models defined in `src/tailoring/models.py` or `src/models/entities.py`. Read those files to see the existing model hierarchy.
17. The existing async database session pattern is in `src/models/database.py` — use `get_session()` context manager for ALL database operations. Do not create new engines or session factories.
18. New CLI flags go in the existing argparse block in `src/main.py` function `_async_main()` (starts at line 668). Read the current arguments before adding new ones.

### Testing
19. Every new module gets a corresponding test file. Test files mirror the source structure: `src/demo.py` → `tests/unit/test_demo.py`.
20. Tests NEVER make live API calls. Mock `httpx` for any test involving Claude API.
21. Tests NEVER depend on external network access or files outside the repo.
22. Use `datetime.timezone.utc` in all test files — never `datetime.UTC`.
23. After EVERY implementation step, run BOTH lint and tests (see rule 14b).

### Git
23. Commit after each completed feature (not after each file). Use descriptive messages.
24. Do NOT push to remote. Josh will push manually.
25. Do NOT modify `.github/workflows/ci.yml` unless explicitly required.

## PROJECT FILE MAP — Read these files to understand the codebase

Core pipeline:
- `src/main.py` — CLI entry point, pipeline orchestrator, argparse (668+), `run_pipeline()`, `run_rank_only()`, `tailor_stage()`
- `src/models/database.py` — Async SQLAlchemy engine, session management, all CRUD operations including `upsert_job()`, `get_top_matches()`, `create_resume_profile()`, `link_resume_skill()`
- `src/models/entities.py` — Pydantic v2 models: `RawJobListing`, `JobListingCreate`, `JobListing`, `Skill`, `SkillCategory`, `Proficiency`, `JobSource`, `RemoteType`, `JobStatus`
- `src/models/schema.sql` — Phase 1 DDL: `job_listings`, `skills`, `job_skills`, `resume_profiles`, `resume_skills`, `company_tiers`, `scrape_log`

Phase 2 tailoring:
- `src/tailoring/models.py` — Pydantic v2: `ParsedBullet`, `ParsedResume`, `SkillGap`, `TailoringRequest`, `TailoredBullet`, `TailoringResult`, `ResumeSection`
- `src/tailoring/resume_parser.py` — `ResumeProfileParser` class, `SKILL_TAXONOMY` dict, section header regex patterns
- `src/tailoring/skill_extractor.py` — `SkillOverlapAnalyzer` class, `_SKILL_CATEGORIES` mapping, `_DEFAULT_PROFICIENCY` mapping
- `src/tailoring/engine.py` — `TailoringEngine` class, Claude API via httpx, `strip_code_fences()`, tier-specific prompts, `_SYSTEM_PROMPT`
- `src/tailoring/db_models.py` — SQLAlchemy 2.0 ORM: `ParsedBulletTable`, `TailoringRequestTable`, `TailoredBulletTable`, `SkillGapTable`, `Base`, `_utcnow()`
- `src/demo.py` — Demo mode orchestrator (created April 1 2026)

Database migrations:
- `alembic/env.py` — Async migration runner, Phase 1 stub table exclusion
- `alembic/versions/e3f5bea2636a_add_phase2_tailoring_tables.py` — Phase 2 migration
- `alembic.ini` — Alembic config pointing to `sqlite+aiosqlite:///data/ceal.db`

Data files:
- `data/resume.txt` — Josh's resume in parser-compatible plain text format
- `data/sample_job.txt` — Sample Stripe TSE job description

Config:
- `.env` — LLM_API_KEY (gitignored, loaded by python-dotenv)
- `.env.example` — Template showing all env vars
- `.gitignore` — Excludes .env, data/*.db, __pycache__, .venv, .coverage
- `requirements.txt` — All pinned dependencies (read before adding imports)

Tests:
- `tests/unit/test_demo.py` — Demo mode tests
- `tests/unit/test_tailoring_models.py` — Pydantic model validation tests
- `tests/unit/test_resume_parser.py` — Parser tests
- `tests/unit/test_skill_extractor.py` — Skill analyzer tests
- `tests/unit/test_tailoring_engine.py` — Engine tests (mocked API)
- `tests/unit/test_database.py`, `test_normalizer.py`, `test_ranker.py`, `test_scrapers.py` — Phase 1 tests
- `tests/integration/test_pipeline.py` — Phase 1 integration tests

## TASKS — Execute in order

### TASK 0: Fix ruff config + datetime.UTC bugs + lint errors (MANDATORY FIRST)

**Step 1 — Fix ruff config:**
Read `pyproject.toml`. Under `[tool.ruff]`, verify `target-version = "py310"`. If it says `"py311"`, change it.
Under `[tool.ruff.lint]` → `ignore`, verify `"UP017"` is in the list. If not, add it.

**Step 2 — Fix datetime.UTC:**
Read `src/tailoring/db_models.py`. Line 87 has:
```python
def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)
```
Change `datetime.UTC` to `datetime.timezone.utc`.

**Step 3 — Fix existing lint errors:**
Run: `$env:PYTHONPATH="."; python -m ruff check src/ tests/`
Fix ALL errors. Common ones from previous CI run:
- `src/demo.py`: unused `asyncio` import (F401) — remove it
- `tests/unit/test_demo.py`: unused variable `now` (F841) — remove it
- `tests/unit/test_resume_parser.py`: unused `pytest` import (F401) + unsorted imports (I001) — remove unused, sort imports
- `tests/unit/test_skill_extractor.py`: unused `pytest` import (F401) — remove it
You can auto-fix import sorting with: `python -m ruff check --fix src/ tests/`
Then manually fix any remaining F401/F841 errors.

**Step 4 — Verify:**
Run: `$env:PYTHONPATH="."; python -m ruff check src/ tests/` — expect 0 errors
Run: `$env:PYTHONPATH="."; python -m pytest tests/ -q --tb=short` — expect 0 failures

Commit: `"Fix ruff config for Python 3.10 target, fix datetime.UTC and lint errors"`

### TASK 1: Save tailoring results to database

The SQLAlchemy ORM models already exist in `src/tailoring/db_models.py`:
- `TailoringRequestTable` (table: `tailoring_requests`)
- `TailoredBulletTable` (table: `tailored_bullets`)
- `SkillGapTable` (table: `skill_gaps`)
- `ParsedBulletTable` (table: `parsed_bullets`)

The Alembic migration already exists: `alembic/versions/e3f5bea2636a_add_phase2_tailoring_tables.py`

**What to build:**

Create `src/tailoring/persistence.py` — CRUD functions for Phase 2 data, following the same pattern as `src/models/database.py`:

1. READ `src/models/database.py` to understand the session pattern (`get_session()`, `text()` queries, logging pattern).
2. READ `src/tailoring/db_models.py` to understand the exact table schemas and column names.
3. Implement these functions:
   - `async def save_tailoring_result(result: TailoringResult) -> int` — Saves a complete TailoringResult to the database. Insert into `tailoring_requests`, then insert each `TailoredBullet` and `SkillGap` with the request_id FK. Use ON CONFLICT for idempotency (the unique constraints are defined in db_models.py). Returns the request_id.
   - `async def get_tailoring_results(job_id: int, profile_id: int = 1) -> TailoringResult | None` — Retrieves a saved tailoring result, reconstructing the Pydantic `TailoringResult` from the ORM tables. Returns None if not found.
   - `async def list_tailored_jobs(limit: int = 20) -> list[dict]` — Lists jobs that have been tailored, joining `tailoring_requests` with `job_listings` to show job title, company, tier, and bullet count.
4. Import `get_session` from `src.models.database` — do NOT create a new engine.
5. Import Pydantic models from `src.tailoring.models` — validate all data through them.
6. Handle the `skills_referenced` and `metrics` fields in `ParsedBulletTable` as JSON strings (they're `Text` columns storing JSON arrays — serialize with `json.dumps`, deserialize with `json.loads`).

**Update `src/demo.py`:**
After generating tailoring results in demo mode, offer to save them:
- After printing results, add a `--save` flag. If `--save` is passed AND a database exists (`data/ceal.db`), call `save_tailoring_result()`.
- If no database exists, skip silently with a log message — demo mode should never require a database.

**Tests:** Create `tests/unit/test_persistence.py` with:
- `test_save_and_retrieve_tailoring_result` — round-trip save + get
- `test_save_is_idempotent` — saving the same result twice doesn't create duplicates
- `test_list_tailored_jobs_empty` — returns empty list when no results
- Use in-memory SQLite (`sqlite+aiosqlite://`) for tests — same pattern as `test_database.py`

Run tests. Confirm 0 failures. Commit: `"Add tailoring persistence layer with idempotent save/retrieve"`

### TASK 2: Add --job-url flag for URL fetching

**Security requirements for this feature:**
- ONLY fetch from HTTP/HTTPS URLs. Reject `file://`, `ftp://`, and any other scheme.
- NEVER send the LLM_API_KEY in any request to fetched URLs.
- Set a User-Agent header: `Ceal/2.0 (Career Signal Engine)`
- Set a timeout of 15 seconds on all fetches.
- Strip HTML tags from fetched content to extract plain text job descriptions.
- If the URL is unreachable, print a clear error and exit 1. Do not retry.

**What to build:**

Create `src/fetcher.py` — a simple URL-to-text utility:

1. READ `requirements.txt` — `httpx` and `beautifulsoup4` are already available.
2. Implement `async def fetch_job_description(url: str) -> str`:
   - Validate URL scheme is http or https. Raise ValueError otherwise.
   - Use `httpx.AsyncClient` with 15s timeout and User-Agent header.
   - Parse HTML response with BeautifulSoup, extract text.
   - Strip excessive whitespace.
   - Return clean text string.
3. This module must NOT import anything from `.env` or use any API keys.

**CLI integration in `src/main.py`:**
- Add `--job-url` argument to the demo argument group.
- `--job-url` and `--job` are mutually exclusive — user provides one or the other.
- When `--job-url` is used, call `fetch_job_description()` to get the text, then proceed with the same demo pipeline.
- Example: `python -m src.main --demo --resume data/resume.txt --job-url "https://example.com/job-posting"`

**Tests:** Create `tests/unit/test_fetcher.py`:
- `test_fetch_rejects_file_scheme` — ValueError on `file:///etc/passwd`
- `test_fetch_rejects_ftp_scheme` — ValueError on `ftp://example.com`
- `test_fetch_strips_html` — mock httpx to return HTML, verify clean text output
- `test_fetch_timeout` — mock httpx to timeout, verify graceful error
- Do NOT make real HTTP requests in tests. Mock httpx.

Run tests. Confirm 0 failures. Commit: `"Add --job-url flag with secure URL fetching"`

### TASK 3: Batch mode — tailor all ranked jobs

**What to build:**

Add `--batch` flag to demo mode that processes all ranked jobs in the database through the tailoring engine.

1. READ `src/models/database.py` function `get_top_matches()` (line 449) — this returns ranked jobs from the DB.
2. READ `src/main.py` function `tailor_stage()` (line 342) — this is the existing pipeline tailor stage. Understand its pattern but do NOT modify it.
3. Create `src/batch.py`:
   - `async def run_batch_tailoring(resume_path: str, limit: int = 20, min_score: float = 0.5) -> dict`:
     - Load resume from `resume_path` using `ResumeProfileParser`
     - Call `get_top_matches(min_score=min_score, limit=limit)` to get ranked jobs
     - For each job, run the same pipeline as demo mode: parse resume → skill gap → tailoring engine
     - Save each result using `save_tailoring_result()` from Task 1
     - Return stats: `{"total": int, "tailored": int, "errors": int, "skipped": int}`
   - Rate-limit API calls with `asyncio.Semaphore(3)` to avoid throttling
   - Skip jobs that already have tailoring results (check with `get_tailoring_results()`)
   - Log progress with structlog
4. API key loaded from `os.getenv("LLM_API_KEY")` — same pattern as `src/main.py` line 491.

**CLI integration:**
- Add `--batch` flag in argparse (mutually exclusive with `--demo`)
- `--batch` accepts optional `--limit` (default 20) and `--min-score` (default 0.5)
- Requires `--resume` path
- Example: `python -m src.main --batch --resume data/resume.txt --limit 10 --min-score 0.7`

**Tests:** Create `tests/unit/test_batch.py`:
- `test_batch_skips_already_tailored` — mock DB to return a job that already has results
- `test_batch_respects_limit` — verify only N jobs are processed
- `test_batch_handles_api_failure_gracefully` — one LLM failure doesn't crash the batch
- Mock database and httpx — no live calls.

Run tests. Confirm 0 failures. Commit: `"Add batch tailoring mode for ranked jobs"`

### TASK 4: Export tailored bullets to .docx

**What to build:**

1. READ `requirements.txt` — check if `python-docx` is available. If NOT, add it:
   - Run: `pip install python-docx --break-system-packages`
   - Add `python-docx` to `requirements.txt` (with pinned version from pip show)
2. Create `src/export.py`:
   - `def export_tailored_resume(result: TailoringResult, parsed_resume: ParsedResume, output_path: str) -> str`:
     - Create a .docx file with:
       - Title: "Tailored Resume — [job context if available]"
       - Section for each resume section (SUMMARY, EXPERIENCE, SKILLS, etc.)
       - For each bullet: show the rewritten text (not the original)
       - Bold any bullet with `xyz_format=True`
       - Add a "Skill Gap Analysis" section at the bottom showing the gap table
     - Return the output file path
   - `def export_skill_gap_table(skill_gaps: list[SkillGap], output_path: str) -> str`:
     - Standalone export of just the skill gap analysis as a .docx table
     - Columns: Skill, Category, Resume Has (Y/N), Proficiency
     - Return the output file path
3. Import only from `src.tailoring.models` for data types.

**CLI integration:**
- Add `--export` flag that takes an output path (e.g., `--export output/tailored_stripe.docx`)
- Works with both `--demo` and `--batch` modes
- If used with `--demo`, exports the single result
- If used with `--batch`, exports one .docx per job into the specified directory
- Example: `python -m src.main --demo --resume data/resume.txt --job data/sample_job.txt --export output/stripe_tse.docx`

**Tests:** Create `tests/unit/test_export.py`:
- `test_export_creates_docx_file` — verify file exists and is valid .docx
- `test_export_contains_rewritten_bullets` — read back .docx, verify bullet text
- `test_export_bolds_xyz_bullets` — verify X-Y-Z bullets have bold formatting
- `test_export_skill_gap_table` — verify table has correct columns and data
- Use tmp_path fixture for output files.

Run tests. Confirm 0 failures. Commit: `"Add .docx export for tailored resume and skill gap analysis"`

### TASK 5: Update README + push prep

1. READ `README.md` current state.
2. Update the "Usage" section with all new CLI flags:
   - `--demo --resume --job` (existing)
   - `--demo --resume --job-url` (new)
   - `--demo --resume --job --save` (new)
   - `--demo --resume --job --export` (new)
   - `--batch --resume` (new)
3. Update "Project Structure" tree with new files (`persistence.py`, `fetcher.py`, `batch.py`, `export.py`)
4. Update test count (run tests to get exact number)
5. Update "Tech Stack" table if python-docx was added
6. Update "Roadmap" — Phase 2 items should reflect what's now complete vs planned

Run tests one final time. Confirm 0 failures.

Commit: `"Update README with batch mode, URL fetching, and export docs"`

Do NOT push. Do NOT tag a new release — Josh will decide on versioning.

### TASK 6: Final verification

Run this exact sequence and report the output:

```
$env:PYTHONPATH="."; python -m pytest tests/ -v --tb=short 2>&1 | Select-Object -Last 30
$env:PYTHONPATH="."; python -m pytest tests/ -q --tb=short 2>&1 | Select-Object -Last 5
git log --oneline -10
git status
git diff --cached | Select-String -Pattern "sk-ant|api.key|secret|password|token" -CaseSensitive
```

Expected:
- All tests pass, 0 failures
- 5-6 new commits since v2.0.0-phase2-alpha
- Clean working tree (nothing unstaged)
- No secrets in any committed code

---END---
