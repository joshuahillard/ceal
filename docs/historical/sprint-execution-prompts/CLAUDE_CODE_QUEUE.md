# Céal — Claude Code Prompt Queue
## Objective: Demo Mode (end-to-end usable pipeline)
### Generated: April 1, 2026

---

## HOW TO USE THIS DOCUMENT

Each numbered section below is **one Claude Code prompt**. Copy the entire prompt text (inside the code block) and paste it into Claude Code.

**Before starting:** Open a terminal and `cd` into your `ceal/` git repo directory — the one that contains `src/`, `tests/`, `pyproject.toml`, and `README.md`. All prompts assume Claude Code's working directory is this folder.

**Run them in order.** Each prompt builds on the previous one. Do not skip ahead.

**After each prompt completes:** Verify the output before moving to the next one. Each prompt includes its own verification step.

---

## PROMPT 1 — Fix Failing Tests + Commit All Work

**What this does:** Fixes 14 test failures caused by `datetime.UTC` (Python 3.11+ only, but this project runs on 3.10), then commits all 31 modified and 4 untracked files that are currently sitting outside version control.

**Why first:** Nothing else matters if the test suite is red and work isn't committed.

```
WORKING DIRECTORY: This is the Céal project (ceal/ repo root).
IMPORTANT: Only modify files inside this directory. Do not create files outside of it.

TASK: Fix 14 failing tests and commit all uncommitted work.

ROOT CAUSE: `datetime.UTC` does not exist in Python 3.10. It was added in Python 3.11.
This project targets Python 3.10+ (check pyproject.toml to confirm).

EXACT FILES TO FIX (only these two files have the bug):
- tests/unit/test_skill_extractor.py — line 29 uses `datetime.datetime.now(datetime.UTC)`
- tests/integration/test_tailoring_integration.py — line 71 uses `datetime.datetime.now(datetime.UTC)`

FIX: In both files, replace `datetime.UTC` with `datetime.timezone.utc`
Do NOT add any new imports — `datetime.timezone` is already available from `import datetime`.

VERIFICATION STEPS (do all of these):
1. Run: PYTHONPATH=. python -m pytest tests/ -q --tb=short
2. Confirm: 0 failures. Expected passing count is approximately 183 (169 previously passing + 14 now fixed).
3. If any test still fails, read the traceback and fix it before proceeding.

AFTER TESTS PASS — commit everything:
1. Run `git status` to see all modified and untracked files.
2. Stage everything EXCEPT .coverage files, __pycache__/, .pytest_cache/, .ruff_cache/, and .venv/:
   - git add src/ tests/ alembic/ .github/ README.md requirements.txt pyproject.toml .gitignore .env.example alembic.ini docs/ push_to_github.sh
3. Commit with message: "Fix datetime.UTC compat for Python 3.10, commit Phase 2 implementation"
4. Run `git log --oneline -3` to confirm the commit landed.

Do NOT push to remote. Just commit locally.
```

---

## PROMPT 2 — Add Demo Mode CLI Command

**What this does:** Adds a `--demo` CLI flag that takes a job description file, runs it through the full Phase 2 pipeline (parse resume → extract skills → analyze gaps → generate tailored bullets), and prints readable output to stdout.

**Why:** This is the core deliverable — making Céal actually usable without live scraping.

```
WORKING DIRECTORY: This is the Céal project (ceal/ repo root).
IMPORTANT: Only modify files inside this directory. Do not create files outside of it.

TASK: Add a `--demo` CLI subcommand to src/main.py that runs the Phase 2 tailoring pipeline on a single job description, without requiring live scraping or a database.

EXISTING CODE YOU MUST READ FIRST (read each file before writing any code):
- src/main.py — the existing CLI lives in `_async_main()` starting around line 668. It uses argparse.
- src/tailoring/resume_parser.py — `ResumeProfileParser` class with `.parse(profile_id: int, raw_text: str) -> ParsedResume`
- src/tailoring/skill_extractor.py — `SkillOverlapAnalyzer` class with `.analyze(job: JobListing, resume_skills: list[str]) -> list[SkillGap]`
- src/tailoring/engine.py — `TailoringEngine` class with `.__init__(api_key: str)` and `.generate_tailored_profile(request, resume_bullets, skill_gaps) -> TailoringResult`
- src/tailoring/models.py — `TailoringRequest`, `TailoringResult`, `TailoredBullet`, `SkillGap`, `ParsedResume`, `ParsedBullet`
- src/models/entities.py — `JobListing`, `JobListingCreate`, `JobSource`, `RemoteType`, `JobStatus` and other Pydantic models
- .env.example — shows `LLM_API_KEY` as the env var name for the Anthropic key

ARCHITECTURE REQUIREMENTS:
1. Create a NEW file: src/demo.py — this keeps demo logic separate from the pipeline orchestrator.
2. Do NOT modify the existing pipeline functions (run_pipeline, run_rank_only, etc.).
3. Add a `--demo` argument to the existing argparse in _async_main() that points to src/demo.py.

WHAT src/demo.py MUST DO:
1. Accept two inputs:
   - `resume_path` (str): Path to a plain text file containing the candidate's resume
   - `job_path` (str): Path to a plain text file containing a job description
2. Load both files from disk (plain text, not .docx — tell the user to paste resume text into a .txt file)
3. Parse the resume using `ResumeProfileParser().parse(profile_id=1, raw_text=resume_text)`
4. Build a minimal `JobListing` object from the job description text. Since this is demo mode (no DB), construct it manually:
   - Use `JobListing` from `src.models.entities` — BUT this model requires many fields (id, scraped_at, created_at, updated_at, etc.) that won't exist in demo mode.
   - SOLUTION: Create a `_build_demo_job(description: str) -> JobListing` helper that fills required fields with sensible defaults:
     - id=0, external_id="demo-001", source=JobSource.MANUAL, title="Demo Job", company_name="Demo Company"
     - url="https://example.com", status=JobStatus.SCRAPED, company_tier=1
     - description_raw=description, description_clean=description
     - scraped_at/created_at/updated_at = datetime.now(datetime.timezone.utc)
   - IMPORTANT: Read the `JobListing` model definition in src/models/entities.py to confirm every required field. Do not guess.
5. Run `SkillOverlapAnalyzer().analyze(job=demo_job, resume_skills=resume_skills)` where resume_skills comes from the parsed resume bullets
6. Check for `LLM_API_KEY` in environment (loaded via python-dotenv which is already in requirements.txt and already called in src/models/database.py). If no key found, print skill gap analysis only (no LLM call) and exit with a helpful message.
7. If API key exists, build a `TailoringRequest` and call `TailoringEngine(api_key=key).generate_tailored_profile(request, resume_bullets, skill_gaps)`
8. Print results to stdout in a readable format:
   - Section 1: "SKILL GAP ANALYSIS" — list each SkillGap with skill_name, category, resume_has (✓/✗), proficiency
   - Section 2: "TAILORED BULLETS" — for each TailoredBullet, show original → rewritten, relevance score, xyz_format flag
   - Section 3: "METADATA" — prompt version, job_id, profile_id, bullet count

CLI INTEGRATION in src/main.py:
- Add a mutually exclusive group or subcommand: `--demo` flag
- When `--demo` is passed, also require `--resume` (path to resume.txt) and `--job` (path to job.txt)
- Example usage: `python -m src.main --demo --resume data/resume.txt --job data/job_description.txt`
- Import and call the demo function from src/demo.py

ERROR HANDLING:
- If resume file doesn't exist: print clear error message, exit 1
- If job file doesn't exist: print clear error message, exit 1
- If LLM call fails (httpx error, JSON parse error): catch the exception, print what went wrong, still show the skill gap analysis that succeeded

DO NOT:
- Do not modify any existing test files
- Do not modify the existing pipeline functions in main.py
- Do not hardcode any API keys
- Do not use any libraries not already in requirements.txt

AFTER IMPLEMENTATION:
1. Create a sample job description file at data/sample_job.txt with this content (a real Stripe TSE posting style):
---
Technical Solutions Engineer - Stripe

About the role:
We're looking for a Technical Solutions Engineer to help our largest users build and scale their payments infrastructure. You'll work directly with engineering teams to debug complex API integrations, design solutions for payment flows, and serve as the technical voice of the customer.

Requirements:
- 3+ years of experience in a technical support, solutions engineering, or similar customer-facing technical role
- Strong debugging and troubleshooting skills, including reading logs and API traces
- Experience with REST APIs, webhooks, and payment processing systems
- Proficiency in at least one programming language (Python, Ruby, Java, or JavaScript)
- Familiarity with SQL databases and data analysis
- Excellent written and verbal communication skills

Nice to have:
- Experience with financial technology or payment processing
- Familiarity with cloud infrastructure (AWS, GCP, or Azure)
- Experience managing technical escalations
- Background in SaaS platforms
---

2. Run the demo in offline mode (no API key) to verify skill gap analysis works:
   PYTHONPATH=. python -m src.main --demo --resume data/resume.txt --job data/sample_job.txt
   (This will fail because data/resume.txt doesn't exist yet — that's expected. Just confirm the CLI args parse correctly and the error message is clear.)

3. Run: PYTHONPATH=. python -m pytest tests/ -q --tb=short
   Confirm no regressions — the same number of tests should pass as before.
```

---

## PROMPT 3 — Create Josh's Resume Text File

**What this does:** Creates a plain text version of Josh's resume that the demo mode can parse. This is the "fuel" for the pipeline.

**Why:** The ResumeProfileParser needs raw text input. Without this, demo mode has nothing to parse.

```
WORKING DIRECTORY: This is the Céal project (ceal/ repo root).
IMPORTANT: Only modify files inside this directory. Do not create files outside of it.

TASK: Create data/resume.txt containing Josh Hillard's resume in plain text format.

IMPORTANT: The ResumeProfileParser in src/tailoring/resume_parser.py detects sections using regex patterns. Read that file first (specifically the _SECTION_PATTERNS dict around line 75) to understand exactly what section headers it recognizes. The resume text MUST use headers that match those patterns, or the parser will fail to extract sections.

The parser recognizes these section header patterns (case-insensitive):
- SUMMARY / PROFESSIONAL SUMMARY / PROFILE / OBJECTIVE / ABOUT
- EXPERIENCE / WORK EXPERIENCE / EMPLOYMENT / PROFESSIONAL EXPERIENCE / INDEPENDENT PROJECT
- SKILLS / TECHNICAL SKILLS / CORE COMPETENCIES / TECHNOLOGIES
- PROJECTS / PERSONAL PROJECTS / SIDE PROJECTS / KEY PROJECTS
- CERTIFICATIONS / CERTIFICATES / EDUCATION / EDUCATION & CERTIFICATIONS

Bullets must start with: -, *, or bullet character (•, ◦, ▪) followed by a space.

The parser also cross-references skills against SKILL_TAXONOMY (line 30 in resume_parser.py). Use canonical skill names from that taxonomy where possible so the skill extractor picks them up.

CREATE data/resume.txt with this content:

PROFESSIONAL SUMMARY
Experienced technical leader with 10+ years in tech, including 6+ years at Toast (NYSE: TOST) managing technical escalation teams and driving cross-functional solutions. Builder of production autonomous systems and AI-powered data pipelines. Demonstrated ability to save $12 million by identifying critical firmware defects. Currently building cloud-native Python applications with async architectures, AI/LLM integrations, and CI/CD automation.

EXPERIENCE
Toast, Inc. — Manager II, Technical Escalations (Oct 2023 – Oct 2025)
- Directed and mentored team of senior technical consultants handling complex POS system escalations
- Saved Toast estimated $12 million by identifying critical firmware defects on handheld POS devices
- Recognized by CEO Chris Comparato at company-wide kickoff event for defect identification impact
- Featured in Toast marketing materials as subject matter expert
- Reduced recurring issue volume by 37% via cross-functional collaboration with Product and Engineering teams
- Created enablement materials, onboarding frameworks, and knowledge base articles for technical teams
- Managed escalation workflows across Engineering, Product, and Customer Success organizations

Toast, Inc. — Senior Restaurant Technical Consultant II (Jun 2022 – Sep 2023)
- Achieved 63% successful post-sales adoption rate partnering with Customer Success Managers
- Created consultative playbooks and training frameworks for technical onboarding
- Served as primary Technical SME for on-site implementations and cross-team technical initiatives
- Delivered API integration guidance for restaurant technology ecosystem partners

Toast, Inc. — Senior Customer Care Representative, Payment Escalations (Apr 2019 – Jun 2022)
- Managed complex payment processing escalation workflows for enterprise restaurant clients
- Drove customer feedback analysis leading to operational enhancements across support organization
- Built foundation for technical leadership through deep domain expertise in FinTech payment systems

PROJECTS
Sol-Fortress / Moss Lane — Autonomous Trading System (March 2026 – Present)
- Built production autonomous trading system deployed on cloud infrastructure (Vultr VPS, Ubuntu Linux)
- Executed full lifecycle: audit, root cause analysis, 1,800-line rewrite, automated deployment with rollback
- Integrated 5 external REST APIs with multi-layer risk management framework and SQLite database
- Orchestrated AI-driven development using Claude and Gemini for systematic code generation
- Demonstrated: Python, Linux administration, SSH/SCP, systemd services, SQL, REST APIs, deployment automation

Céal — AI-Powered Career Signal Engine (March 2026 – Present)
- Designed event-driven async pipeline processing 500+ job listings in 8 seconds (95% reduction from sync baseline)
- Enforced Pydantic v2 data contracts at every pipeline boundary achieving 0% corrupt database records
- Built Claude API integration for deterministic LLM scoring with prompt versioning for A/B testing
- Implemented GitHub Actions CI/CD with 4-stage quality gates (lint, unit test, integration test, coverage)
- Stack: Python, asyncio, SQLAlchemy 2.0, aiosqlite, Pydantic v2, httpx, structlog, pytest (183+ tests)

SKILLS
- Leadership: Escalation Management, Cross-Functional Leadership, Process Optimization, Project Management, Training & Enablement
- Technical: Python, SQL, REST APIs, API Integrations, Git, Payment Processing, Pydantic, SQLAlchemy, asyncio
- Infrastructure: Linux, Docker, systemd, Deployment Automation, GCP, SSH/SCP
- Domain: FinTech, SaaS, Data Engineering, Machine Learning

CERTIFICATIONS
- Google AI Essentials — Professional Certificate (2026)
- Google Project Management — Professional Certificate (In Progress, 3/7 courses)

VERIFICATION:
1. Read data/resume.txt back and confirm it exists and is non-empty.
2. Run a quick Python test to verify the parser can parse it:
   PYTHONPATH=. python -c "
from src.tailoring.resume_parser import ResumeProfileParser
with open('data/resume.txt') as f:
    text = f.read()
parser = ResumeProfileParser()
result = parser.parse(profile_id=1, raw_text=text)
print(f'Sections found: {len(set(b.section for b in result.sections))}')
print(f'Bullets parsed: {len(result.sections)}')
print(f'Skills detected: {sorted(set(s for b in result.sections for s in b.skills_referenced))}')
for b in result.sections[:3]:
    print(f'  [{b.section.value}] {b.original_text[:80]}...')
"
3. Confirm: At least 3 sections detected, at least 10 bullets parsed, at least 5 skills detected.
4. If the parser returns 0 sections or 0 bullets, the section headers don't match the regex patterns. Read _SECTION_PATTERNS in resume_parser.py and adjust the headers.
```

---

## PROMPT 4 — End-to-End Demo Test (Offline, No API Key)

**What this does:** Runs the demo pipeline without an API key to verify the full chain works up to the skill gap analysis step.

```
WORKING DIRECTORY: This is the Céal project (ceal/ repo root).
IMPORTANT: Only modify files inside this directory. Do not create files outside of it.

TASK: Run an end-to-end test of demo mode and fix any issues.

STEP 1 — Run demo mode without API key:
PYTHONPATH=. python -m src.main --demo --resume data/resume.txt --job data/sample_job.txt

Expected behavior:
- Resume parsed successfully (should print bullet count and skill count)
- Job description loaded and converted to a demo JobListing object
- Skill gap analysis completed (should print a table of skills with ✓/✗)
- Message printed: "No LLM_API_KEY found. Showing skill gap analysis only."
- No crash, no traceback

STEP 2 — If there are ANY errors:
- Read the full traceback carefully
- Identify the exact file and line number
- Fix the issue
- Re-run and confirm it works

STEP 3 — Common issues to watch for:
- Import errors: Make sure src/demo.py imports use the `src.` prefix (e.g., `from src.tailoring.resume_parser import ResumeProfileParser`)
- JobListing construction: If you get a ValidationError, read src/models/entities.py to see which field is missing or has the wrong type. The `JobListing` model inherits from `JobListingCreate` and adds fields like `id`, `scraped_at`, `created_at`, `updated_at`, `status`.
- datetime fields: Use `datetime.datetime.now(datetime.timezone.utc)` — NOT `datetime.UTC` (Python 3.10 compat)

STEP 4 — After demo runs successfully, run the full test suite to confirm no regressions:
PYTHONPATH=. python -m pytest tests/ -q --tb=short

STEP 5 — If everything works, commit:
git add src/demo.py data/resume.txt data/sample_job.txt
git commit -m "Add demo mode CLI with offline skill gap analysis"

Do NOT push to remote.
```

---

## PROMPT 5 — Live Demo with Claude API

**What this does:** Runs the full demo with a real Claude API call to generate tailored X-Y-Z bullets.

**Prerequisites:** You need an Anthropic API key. Create a `.env` file in the ceal/ root (it's already in .gitignore).

```
WORKING DIRECTORY: This is the Céal project (ceal/ repo root).
IMPORTANT: Only modify files inside this directory. Do not create files outside of it.

TASK: Run demo mode with a live Claude API call and verify tailored bullet output.

PRE-CHECK: Confirm .env file exists with a real API key:
cat .env | grep LLM_API_KEY
If it says "your_anthropic_api_key_here" or doesn't exist, STOP and tell me to set up the .env file.

STEP 1 — Run demo with API key:
PYTHONPATH=. python -m src.main --demo --resume data/resume.txt --job data/sample_job.txt

Expected output:
- Skill gap analysis table (same as offline mode)
- TAILORED BULLETS section with rewritten resume bullets
- Each bullet shows: original text → rewritten text, relevance score (0.0-1.0), X-Y-Z format flag
- METADATA section with prompt version

STEP 2 — If the LLM call fails:
- Check the error message. Common issues:
  - "401 Unauthorized" → API key is wrong or expired
  - "429 Too Many Requests" → Rate limited, wait and retry
  - json.JSONDecodeError → The LLM returned markdown fences. The strip_code_fences() function in src/tailoring/engine.py should handle this, but if it doesn't, check the raw response.
- Read src/tailoring/engine.py method `_call_claude_api()` (around line 223) and `_parse_llm_response()` (around line 249) to understand the response handling.

STEP 3 — If bullets are generated, review quality:
- Are the rewritten bullets actually better than the originals?
- Do Tier 1 bullets lead with quantified impact?
- Do any bullets have relevance_score below 0.5? (These might indicate poor prompt targeting)

STEP 4 — Run the test suite one final time:
PYTHONPATH=. python -m pytest tests/ -q --tb=short

STEP 5 — Commit:
git add -A
git commit -m "Verify live demo mode with Claude API tailoring"

Do NOT push to remote.
```

---

## PROMPT 6 — Write Demo Mode Tests

**What this does:** Adds unit tests for the new demo module to maintain test coverage and prevent regressions.

```
WORKING DIRECTORY: This is the Céal project (ceal/ repo root).
IMPORTANT: Only modify files inside this directory. Do not create files outside of it.

TASK: Write unit tests for src/demo.py. Place them in tests/unit/test_demo.py.

READ FIRST:
- src/demo.py (the module you're testing)
- src/tailoring/resume_parser.py (ResumeProfileParser)
- src/tailoring/skill_extractor.py (SkillOverlapAnalyzer)
- tests/unit/test_resume_parser.py (for test patterns and fixture examples)
- src/models/entities.py (JobListing, JobSource, JobStatus, RemoteType)

TESTS TO WRITE:

1. test_build_demo_job_returns_valid_job_listing
   - Call the _build_demo_job helper with a sample description string
   - Assert it returns a JobListing instance (from src.models.entities)
   - Assert description_clean contains the input text
   - Assert source is JobSource.MANUAL

2. test_build_demo_job_with_empty_description
   - Pass an empty string
   - Verify it either raises ValueError or returns a JobListing with empty description (match actual behavior)

3. test_demo_parses_resume_file
   - Create a tmp file with known resume text (use the section headers from _SECTION_PATTERNS in resume_parser.py)
   - Verify ResumeProfileParser().parse() returns a ParsedResume with expected sections

4. test_demo_skill_gap_analysis_offline
   - Construct a demo JobListing with a description containing known skills from SKILL_TAXONOMY
   - Construct a resume_skills list with some matching and some missing skills
   - Call SkillOverlapAnalyzer().analyze()
   - Assert returned SkillGap list has entries with resume_has=True and resume_has=False

5. test_demo_handles_missing_resume_file
   - Call the demo function with a nonexistent resume path
   - Assert it raises FileNotFoundError or SystemExit (match actual behavior)

6. test_demo_handles_missing_job_file
   - Same as above but for the job file

CONSTRAINTS:
- Do NOT make any live API calls in tests. Mock httpx if needed.
- Use datetime.timezone.utc (NOT datetime.UTC) for any datetime construction
- Use PYTHONPATH=. prefix conventions — imports should be `from src.demo import ...`
- All test functions must be sync (not async) unless the function being tested is async, in which case use @pytest.mark.asyncio

VERIFICATION:
1. Run: PYTHONPATH=. python -m pytest tests/unit/test_demo.py -v --tb=short
2. Confirm: All new tests pass
3. Run: PYTHONPATH=. python -m pytest tests/ -q --tb=short
4. Confirm: No regressions — total test count should increase by ~6

Commit:
git add tests/unit/test_demo.py
git commit -m "Add unit tests for demo mode CLI"
```

---

## PROMPT 7 — Update README + Tag Release

**What this does:** Updates the README to document demo mode usage and tags the Phase 2 alpha release.

```
WORKING DIRECTORY: This is the Céal project (ceal/ repo root).
IMPORTANT: Only modify files inside this directory. Do not create files outside of it.

TASK: Update README.md to document demo mode and tag a release.

READ FIRST: README.md (current state)

UPDATES TO README.md:

1. In the "Tech Stack" table, update the pytest line to reflect the current test count. Run this to get the exact number:
   PYTHONPATH=. python -m pytest tests/ -q --tb=short 2>&1 | tail -1

2. In the "Usage" section, ADD a new subsection "Demo Mode" AFTER the existing CLI examples:

   ## Demo Mode

   Run the tailoring pipeline on a single job description without live scraping:

   ```bash
   # Offline mode (skill gap analysis only, no API key needed)
   PYTHONPATH=. python -m src.main --demo --resume data/resume.txt --job data/sample_job.txt

   # Full mode with LLM-powered bullet tailoring
   echo "LLM_API_KEY=your_key_here" > .env
   PYTHONPATH=. python -m src.main --demo --resume data/resume.txt --job data/sample_job.txt
   ```

3. In the "Project Structure" tree, add:
   - src/demo.py under src/ with comment "# Demo mode — single-job tailoring without DB"
   - data/resume.txt with comment "# Candidate resume (plain text)"
   - data/sample_job.txt with comment "# Sample job description for testing"

4. In the "Roadmap" section, update Phase 2 to:
   - **Phase 2**: Resume tailoring — **alpha complete**. Demo mode for single-job analysis, skill gap detection, LLM-powered X-Y-Z bullet generation.

5. Update test count references if they appear elsewhere.

DO NOT change the architecture diagram, the Key Design Decisions section, or the Database Schema section.

AFTER EDITS:
1. Run: PYTHONPATH=. python -m pytest tests/ -q --tb=short (confirm still green)
2. git add README.md
3. git commit -m "Update README with demo mode docs, Phase 2 alpha status"
4. git tag -a v2.0.0-phase2-alpha -m "Phase 2 alpha: demo mode with skill gap analysis and LLM tailoring"
5. git log --oneline -5 (confirm tag and commits look right)

Do NOT push to remote.
```

---

## AFTER THE QUEUE

Once all 7 prompts are done, you'll have:

- **Green test suite** with 0 failures
- **All work committed** (no more dangling changes)
- **Demo mode** you can actually run: `python -m src.main --demo --resume data/resume.txt --job data/sample_job.txt`
- **Your real resume loaded** and parseable by the pipeline
- **Sample job description** for quick testing
- **Unit tests** covering the new demo module
- **Tagged release** (v2.0.0-phase2-alpha)

**Next sprint candidates (for future prompt queues):**
- Add `--job-url` flag that fetches a job posting URL and extracts description automatically
- Save tailoring results to database (wire up the Phase 2 SQLAlchemy models that already exist in `src/tailoring/db_models.py`)
- Batch mode: process all ranked jobs in the DB through tailoring
- Export tailored bullets to .docx (resume file generation)
- Phase 3: Application tracking CRM
