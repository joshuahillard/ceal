# Céal Session Notes — Tuesday April 1, 2026

**Session type:** Deep work block — Phase 2 completion + demo mode launch
**Personas active:** Data Product Manager (lead), Applied AI Architect, Career Strategist, QA Lead

---

## Executive Summary

Phase 2 (Resume Tailoring) went from partially-scaffolded stubs to a fully functional, live demo in one session. Céal can now parse a real resume, analyze skill gaps against any job description, call Claude's API, and generate tailored X-Y-Z format bullets — all from a single CLI command. First live demo ran successfully against a Stripe Technical Solutions Engineer job posting.

---

## Session Timeline

### Block 1: Sprint Assessment (Cowork)

**Objective:** DPM audit of what shipped Mon–Tue and where to take the week.

**Key findings from codebase audit:**
- Git showed 15 commits, latest on `feature/ci-pipeline` branch
- Phase 2 scaffold committed (Pydantic models, SQLAlchemy ORM, Alembic migration)
- Test suite: 169 passing in Cowork sandbox, 130 on Josh's local machine (state divergence due to file sync timing)
- All three Phase 2 implementation files (`resume_parser.py`, `skill_extractor.py`, `engine.py`) were stubs raising `NotImplementedError`
- 14 test failures from `datetime.UTC` (Python 3.11+ only; project supports 3.10)

**DPM recommendation:** Stop building new pipeline stages. Close the loop on making Phase 1 + Phase 2 actually runnable. Ship demo mode.

### Block 2: Claude Code Prompt Queue (Cowork → Claude Code)

**Objective:** Build a 7-prompt queue for Claude Code to implement demo mode.

**Process:**
1. Audited every file path, class name, function signature, and line number needed for the prompts
2. Built 7 sequential prompts with anti-hallucination guards (each prompt tells Claude Code to read source files before writing code)
3. Ran verification agent — 15/15 references confirmed accurate against actual codebase
4. Saved as `CLAUDE_CODE_QUEUE.md` in Céal project folder

### Block 3: Prompt Queue Execution (Claude Code on Josh's machine)

**Prompt 1 — Fix tests + commit** → Commit `65e75fc`
- Fixed `datetime.UTC` → `datetime.timezone.utc` (only 1 file needed fixing, not 2 as predicted — the integration test file didn't exist locally)
- 130 tests passing, 0 failures

**Prompt 2 — Demo mode CLI** → Part of commit `a0433f1`
- Created `src/demo.py` — demo mode orchestrator
- Added `--demo --resume --job` flags to existing argparse in `main.py`
- Created `data/sample_job.txt` (Stripe TSE posting style)
- **Critical discovery:** All three Phase 2 modules were stubs. Claude Code implemented them:
  - `resume_parser.py` — Section header regex detection, bullet extraction, metric detection ($12M, 37%), skill cross-referencing against 45-entry taxonomy
  - `skill_extractor.py` — Job description skill extraction, fuzzy matching, SkillGap generation with proficiency mapping
  - `engine.py` — Claude API integration via httpx, tier-specific prompt templates, X-Y-Z format enforcement, JSON response parsing with code fence stripping
- Updated 2 test files that expected `NotImplementedError` from stubs
- 133 tests passing

**Prompt 3 — Resume file** → Part of commit `a0433f1`
- Created `data/resume.txt` — Josh's full resume in parser-compatible plain text
- Verification: 5 sections detected, 36 bullets parsed, 31 skills detected

**Prompt 4 — End-to-end offline test** → Part of commit `a0433f1`
- Ran demo without API key — skill gap analysis worked cleanly
- Fixed Unicode encoding issue with checkmark characters on Windows console
- 20 skills analyzed: 8 matches (Python, SQL, REST APIs, Payment Processing, FinTech, GCP, SaaS, API Integrations), 12 gaps
- 133 tests passing, committed

**Prompt 5 — Live Claude API demo** → Verified (no code changes)
- Multiple `.env` file issues hit (PowerShell BOM encoding, missing `LLM_API_KEY=` prefix, exposed API key requiring rotation)
- Eventually resolved using Python for file writing and Notepad for key entry
- **FIRST LIVE DEMO RUN SUCCESSFUL**
- Results: 15 tailored bullets, 4 in X-Y-Z format, relevance scores 0.65–0.95
- $12M bullet auto-converted: "Accomplished $12 million cost savings as measured by defect remediation impact, by doing systematic debugging and root cause analysis of critical firmware defects on handheld POS devices"
- 37% bullet auto-converted: "Accomplished 37% reduction in recurring payment processing issues as measured by incident volume metrics, by doing cross-functional collaboration with Product and Engineering teams"
- 140 tests passing

**Prompt 6 — Demo mode tests** → Commit `ae7eeec`
- 7 new unit tests in `tests/unit/test_demo.py`
- 140 tests passing, 0 failures

**Prompt 7 — README + tag** → Commit `10cadbb` + tag `v2.0.0-phase2-alpha`
- Updated README with demo mode docs, test counts, project structure, Phase 2 status
- Tagged release: `v2.0.0-phase2-alpha`

---

## Deliverables Shipped

| Artifact | Type | Status |
|----------|------|--------|
| `src/demo.py` | New file | Demo mode orchestrator |
| `src/tailoring/resume_parser.py` | Implemented | Was stub → full parser with regex section detection, metric extraction |
| `src/tailoring/skill_extractor.py` | Implemented | Was stub → skill gap analyzer with taxonomy cross-reference |
| `src/tailoring/engine.py` | Implemented | Was stub → Claude API integration with tier prompts + code fence stripping |
| `data/resume.txt` | New file | Josh's resume in parser-compatible format |
| `data/sample_job.txt` | New file | Stripe TSE sample posting |
| `tests/unit/test_demo.py` | New file | 7 unit tests for demo module |
| `README.md` | Updated | Demo mode docs, Phase 2 status |
| `CLAUDE_CODE_QUEUE.md` | New file | 7-prompt implementation queue (reusable pattern) |
| `SESSION_NOTES_2026-04-01.md` | New file | This document |

---

## Test Suite Progression

| Checkpoint | Count | Notes |
|-----------|-------|-------|
| Start of session | 130 passing (local), 14 failing | `datetime.UTC` compat issue |
| After Prompt 1 | 130 passing, 0 failing | Bug fixed |
| After Prompt 2 | 133 passing | Stub tests updated |
| After Prompt 6 | 140 passing | Demo tests added |
| Final state | **140 passing, 0 failures** | Tagged v2.0.0-phase2-alpha |

---

## Git Log (4 new commits, 1 tag)

```
10cadbb Update README with demo mode docs, Phase 2 alpha status
ae7eeec Add unit tests for demo mode CLI
a0433f1 Add demo mode with resume parser, skill extractor, and tailoring engine
65e75fc Fix datetime.UTC compat for Python 3.10
```

Tag: `v2.0.0-phase2-alpha`
Branch: `feature/ci-pipeline` (4 commits ahead of origin, not pushed)

---

## Blockers Hit

1. **Cowork/local file sync divergence** — Cowork mount showed different file state than Josh's local machine. Prompt queue was designed to be resilient to this by reading actual files first.
2. **PowerShell encoding** — `echo` writes UTF-16 BOM, `python-dotenv` expects UTF-8. Resolved by using Python for file writes. `-Encoding utf8NoBOM` only works in PS7+; Josh runs PS5.
3. **API key exposure** — Key accidentally pasted into chat twice. Both rotated. Future prompt queues should include a warning about not pasting keys into chat.
4. **Phase 2 stubs** — All three implementation files were `NotImplementedError` stubs, not the implemented versions seen in Cowork sandbox. Claude Code handled this autonomously by implementing them.

---

## Lessons Learned

1. **Prompt queue pattern works.** 7 prompts executed sequentially by Claude Code with minimal human intervention. Anti-hallucination guards (read-before-write, explicit file paths, verification steps) caught issues early.
2. **Always include PowerShell-compatible commands.** The queue used bash syntax (`PYTHONPATH=.`), which failed in PS5. Future queues need `$env:PYTHONPATH="."` equivalents.
3. **File writes on Windows need Python, not shell.** PowerShell encoding pitfalls are avoidable by using `python -c "open(...).write(...)"` for any config file.
4. **State divergence between Cowork and local is real.** The Cowork sandbox may show different code than what's on Josh's machine. Prompts must be state-agnostic — read first, then act.

---

## Strategic Alignment

| Tier | How Today Maps |
|------|---------------|
| **Tier 1 — Apply Now** | Demo mode generates interview-ready bullets. The $12M and 37% X-Y-Z rewrites are directly usable on applications to Stripe, Datadog, Coinbase TSE roles. |
| **Tier 2 — Build Credential** | Full Claude API integration demonstrates production LLM orchestration. Prompt versioning (`RANKER_VERSION`) shows A/B testing awareness. |
| **Tier 3 — Campaign** | X-Y-Z bullet generation shows Google culture fluency. "I ran my own pipeline against this job posting and it produced the bullets on my resume" is the interview story. |

---

## X-Y-Z Resume Bullet (Session Summary)

> Shipped an AI-powered resume tailoring demo processing 36 resume bullets against live job descriptions with 0.95 peak relevance scoring, as measured by 140 automated tests with zero failures across a 4-commit sprint, by building a CLI-driven pipeline integrating Claude API with Pydantic v2 data contracts, tier-specific prompt templates, and structured skill gap analysis.

---

## Next Steps (Candidates for Next Session)

- Push to remote: `git push origin feature/ci-pipeline` + `git push origin v2.0.0-phase2-alpha`
- Add `--job-url` flag to fetch job postings from URL automatically
- Save tailoring results to database (Phase 2 SQLAlchemy models already exist in `db_models.py`)
- Batch mode: process all ranked jobs in DB through tailoring
- Export tailored bullets to .docx for direct resume use
- Phase 3 planning: Application tracking CRM

---

*Session notes prepared by: Data Product Manager persona*
*First live Céal demo: April 1, 2026*
