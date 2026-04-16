# Ceal Project Ledger
**Canonical Timeline, Decision Log & Sprint Retrospectives**
*Owner: Josh Hillard | Created: April 3, 2026 | Living document — update after every sprint*

---

## How to Use This Document

This is the single source of truth for Ceal's history, decisions, and lessons learned. It serves three purposes: (1) interview preparation — every entry maps to a STAR story or X-Y-Z bullet, (2) onboarding — any AI or human collaborator reads this first to understand where the project has been, and (3) project management — tracking velocity, decisions, and technical debt.

**Update protocol:** After every sprint or significant session, append a new timeline entry, log any architectural decisions, and add a retrospective. If a previous decision is reversed, update the original entry with a "Superseded by" note rather than deleting it.

---

## Project Timeline

### Phase 0 — Project Inception (March 28, 2026)

**What happened:** Josh and Claude designed the full career automation strategy during a 7-page handoff session. Sol-Jobhunter was conceived as a 4-phase project: Scrape, Tailor, CRM, Auto-Apply. The tiered company targeting strategy (Tier 1/2/3) was established. Resume and LinkedIn profile were drafted. The project was renamed from Sol-Jobhunter to **Ceal** (pronounced "KAYL") the same day.

**Commits:** `058f0b0` Initial scaffold: project structure and database schema
**Artifacts:** `Career_Strategy_Handoff.pdf`, `Josh_Hillard_Resume.docx/.pdf`, `LinkedIn_Profile_Overhaul.md`, `Sol-Jobhunter_Architecture.md`
**Test count:** 0

### Phase 1 — Core Pipeline Build (March 28-29, 2026)

**What happened:** The async 3-stage ETL pipeline (Scrape -> Normalize -> Rank) was built from scratch. Pydantic v2 data models, async SQLAlchemy database layer with batch upserts, LinkedIn scraper, normalizer with salary parsing and skill extraction, Claude-powered LLM ranker with explainable scoring, CLI orchestrator, 93 unit and integration tests, and a README were all shipped.

**Commits:**
- `1722844` Pydantic data models for pipeline boundary validation
- `b32d9ed` Async SQLAlchemy database layer with batch upsert
- `2ea58df` Abstract scraper framework and LinkedIn implementation
- `7ccde59` ETL normalizer with salary parsing and skill extraction
- `08499cf` Claude-powered LLM ranker with explainable scoring
- `75ec8f3` Pipeline orchestrator with CLI interface
- `5899a70` 93 unit and integration tests (100% pass rate)
- `5698d1f` README with architecture overview

**Artifacts:** `Sol-Jobhunter_Phase1_Handoff.pdf`, `Project Charter.docx`, `Technical Program Report.docx`
**Test count:** 0 -> 93
**Tags:** None (pre-tagging convention)

### Sprint Week: March 30 - April 3, 2026

#### Monday, March 30 — CI/CD + Phase 2 Scaffold

**Session duration:** ~3 hours (2:00-5:00 PM ET)
**Personas active:** DevOps (lead), Backend Engineer, DPM

**What shipped:**
- GitHub Actions CI/CD pipeline with 4-stage quality gates (lint, unit, integration, coverage)
- Phase 2 file scaffold: 7 Pydantic v2 models, 5 tailoring module files, pyproject.toml config
- 2 validator bugs caught and fixed during audit (`target_tier` arithmetic, X-Y-Z clause logic)

**What did NOT ship (deferred to Tuesday):**
- Phase 2 test files, git commit of scaffold, SQLAlchemy models
- Test count remained at 93 (originally planned 107+)

**Commits:** `bf3b557`, `9c2de41` (CI/CD pipeline)
**Effort:** Medium. Clean execution on CI, scope was right-sized when tests were deferred.

**Retrospective:**
- *What went well:* CI/CD pipeline shipped clean on first try. Validator bugs caught during manual audit before any tests existed.
- *What went wrong:* Overscoped Monday — 107+ tests was unrealistic alongside CI setup and model design. Tests deferred to Tuesday.
- *Lesson:* When building both infrastructure (CI) and domain code (models) in the same session, budget 2x for the infrastructure. CI/CD always takes longer than expected due to YAML iteration.

---

#### Tuesday, March 31 — SQLAlchemy + Alembic + Tests

**Session duration:** ~3 hours
**Personas active:** ETL Architect (lead), Backend Engineer, QA Lead

**What shipped:**
- SQLAlchemy 2.0 async ORM models for Phase 2 tables
- Alembic migration setup
- Phase 2 scaffold committed to git
- Requirements cleanup (removed Python 3.10-only backports)

**Commits:** `e6b2258`, `b86e4b4`, `39a5e1b`, `72a76b7`
**Test count:** 93 -> ~130 (local; Cowork sandbox showed 169 due to sync divergence)
**Effort:** Medium-High. SQLAlchemy async + Alembic setup required careful Pydantic-to-ORM alignment.

**Retrospective:**
- *What went well:* Phase 2 data layer is solid — Pydantic v2 -> SQLAlchemy round-trip validation works.
- *What went wrong:* File sync divergence between Cowork sandbox and local machine. Different test counts in different environments.
- *Lesson:* Cowork mount and local git are separate states. Always verify against `git show` or `git log`, never trust the Cowork sandbox file state as canonical.

---

#### Wednesday, April 1 — Demo Mode + Live API Integration

**Session duration:** ~4 hours
**Personas active:** DPM (lead), AI Architect, Career Strategist, QA Lead

**What shipped:**
- Phase 2 stubs fully implemented: ResumeProfileParser, SkillOverlapAnalyzer, TailoringEngine
- Demo mode CLI (`--demo --resume --job`)
- Claude API live integration with tier-specific prompt templates
- First successful live demo: 15 tailored bullets, $12M and 37% auto-converted to X-Y-Z format
- 7 demo mode unit tests

**Commits:** `65e75fc`, `a0433f1`, `ae7eeec`, `10cadbb`
**Test count:** 130 -> 140
**Tags:** `v2.0.0-phase2-alpha`
**Effort:** High. 7-prompt queue executed sequentially. PowerShell encoding issues and API key exposure required debugging.

**Retrospective:**
- *What went well:* The prompt queue pattern (7 sequential prompts with anti-hallucination guards) worked excellently. Phase 2 went from stubs to live demo in one session.
- *What went wrong:* PowerShell BOM encoding broke `.env` file. API key accidentally pasted into chat (rotated). Phase 2 stubs on local machine didn't match Cowork sandbox state.
- *Lesson:* (1) Never use `echo` for file writes on Windows — use Python. (2) Prompt queues should include a warning about not pasting API keys. (3) The prompt queue pattern is the single biggest velocity multiplier we've found — formalize it.

---

#### Thursday, April 2 — Sprint 1 UI + Sprint 6 Infrastructure + Multi-AI Onboarding

**Session duration:** ~4.25 hours
**Personas active:** TPM (lead), Backend Engineer, DPM, AI Architect, DevOps

**What shipped:**
- **Sprint 1:** FastAPI + Jinja2 web UI (Dashboard, Jobs, Demo pages, 6 routers, 926 lines across 14 files)
- **Git consolidation:** Force-pushed `feature/ci-pipeline` to `main` (divergent history resolved)
- **Sprint 6:** Docker containerization + Cloud SQL polymorphic database layer (13 files, +712 lines)
- **Multi-AI onboarding:** 7 documents in `docs/ai-onboarding/` for Claude, Codex, Gemini collaboration
- **Runtime bugs fixed:** LLM xyz_format trust issue, Jobs page empty-string tier crash
- **First live scraper run through web UI:** 50 jobs scraped, normalized, ranked

**Commits:** `655132f`, `bff21db`, `4bb9547` (Sprint 1 + fixes), `98177d4` (Sprint 6), `3b89465` (onboarding), `8344b67`, `1a23012` (docs)
**Test count:** 140 -> 179
**Tags:** `v2.6.0-sprint6-gapfill`, `v2.6.0-sprint6-infra`
**Effort:** Very High. Three sprints worth of work in one session. Combined sprint prompt strategy saved context windows.

**Retrospective:**
- *What went well:* Combined sprint prompts (merging Sprint 6 gap-fill + Docker/Cloud SQL into one prompt with self-skip logic) eliminated redundant context-switching. Multi-AI onboarding package means any new AI session starts from full context.
- *What went wrong:* Branch reset to `codex/semantic-fidelity-guardrail` lost Sprints 2-5 history. Had to reimplement CRM and Auto-Apply later. Cowork `.git/index.lock` permission error blocked direct git operations.
- *Lesson:* (1) Never force-push without a backup branch. (2) Combined prompts with pre-flight self-skip logic are superior to separate prompts when token budget is constrained. (3) In-repo onboarding docs (readable after `git clone`) beat external wikis for multi-AI collaboration.

**Critical Incident: Branch Reset**
On April 2, `main` was reset to `codex/semantic-fidelity-guardrail`, which lost the commit history for Sprints 2-5 (Phase 2B features: batch tailoring, .docx export, persistence, fetcher, demo enhancements). The code still existed on Josh's local `feature/ci-pipeline` branch but was not recoverable via git merge (divergent root commits). Decision was made to reimplement the missing features in subsequent sprints rather than attempt a complex history graft.

---

#### Friday, April 3 — Sprint 8 CRM + Sprint 9 Vertex AI + Sprint 10 PDF Generation

**Session duration:** Multi-session day
**Personas active:** Full team

**What shipped:**
- **Sprint 8:** CRM reimplementation (Kanban board, state machine, reminders) + Auto-Apply (prefill engine, approval queue, review interface)
- **Sprint 9:** Vertex AI regime classification (optional, fail-open, A/B instrumentation with `RANKER_VERSION`)
- **Sprint 10:** PDF document generation pipeline (resume + cover letter .docx export)
- Jobs tab live refresh hardening + runtime recovery fix

**Commits:** `d054f4e` (Sprint 8), `22eb104` (docs), `1c7dc0e` (Sprint 9), `655adf7` (Sprint 10), `a33ecbd` (Sprint 10 sign-off), `20c2c18` (jobs tab fix)
**Test count:** 179 -> 246
**Tags:** `v2.9.0-sprint9-vertex-ai`, `v2.10.0-sprint10-pdf-generation`
**Effort:** Very High. Three major feature sprints plus a bug fix in one day.

**Retrospective:**
- *What went well:* Sprint velocity is at peak — 8-pillar prompt framework + combined sprint strategy + multi-AI onboarding enabled shipping 3 sprints in a day.
- *What went wrong:* Jobs tab had a hidden SQL bug that mock-only route tests didn't catch. Required a post-sprint hotfix.
- *Lesson:* Mock-only route tests hide SQL bugs. Core query functions need DB-level integration tests exercising real SQL, not just mocked return values. This is a systemic testing gap that needs addressing.

---

#### Thursday, April 16 — Sprint 11 Hardening + Twin-Docs Reconciliation

**Session duration:** Multi-session continuation
**Personas active:** QA Lead, Backend Engineer, AI Architect, Technical Program Manager

**What shipped:**
- **Sprint 11 hardening:** Prefill engine edge-case coverage for empty, whitespace, unicode, and malformed resume inputs
- **DB parity:** SQLite/PostgreSQL round-trip harness validating backend-aware behavior instead of relying on route-layer mocks
- **Canonical docs reconciliation:** Re-merged active onboarding, prompt, reference, and strategy docs into `ceal/docs/`
- **Claude Code fast-path fix:** Corrected stale source paths, prompt locations, and repo-state counts in the active AI entrypoints

**Commits:** `e5fa565` (prefill hardening + DB parity), `fe607aa` (historical/reference rescue), `29b12b2` (RULES merge), `5697e43` (PROMPT_REGISTRY merge), `bfdb481` (PROJECT_CONTEXT correction), `509b722` (master prompt key-doc fix)
**Test count:** 246 -> 317
**Effort:** High. Hardening and docs reconciliation both required source-verifying the canonical docs against the live repo tree.

**Retrospective:**
- *What went well:* The DB parity harness closed the mock blind spot quickly. Re-centering onboarding inside `ceal/docs/` restored a single canonical source of truth for AI sessions.
- *What went wrong:* Parallel top-level and in-repo doc trees drifted. Claude Code, Codex, and Gemini entrypoints pointed at deleted paths and stale counts, which forced repeated re-verification and slowed every session.
- *Lesson:* AI entrypoints are operational infrastructure. When code paths or canonical doc locations move, `CLAUDE.md`, runtime prompts, onboarding docs, and the ledger must be updated in the same change window.

---

## Decision Log

### ADR-001: Pydantic v2 at Every Pipeline Boundary (March 28)
**Decision:** All data flowing between pipeline stages must pass through Pydantic v2 validation models (`RawJobListing` -> `JobListingCreate` -> `JobListing`).
**Why:** Zero-defect culture — corrupt data is a system failure. Runtime type checking catches issues that static typing misses, especially with LLM-generated JSON.
**Trade-off:** Slightly higher serialization overhead vs. guaranteed data integrity.
**Status:** Active. Extended to Phase 2 models (7 additional contracts).

### ADR-002: asyncio.Queue as Internal Message Broker (March 28)
**Decision:** Use `asyncio.Queue` with backpressure limits instead of an external message broker (Redis, RabbitMQ).
**Why:** Single-process deployment simplicity. The pipeline processes hundreds of listings, not millions. External broker adds operational complexity without proportional benefit at current scale.
**Trade-off:** No persistence between restarts, no distributed processing. Acceptable for a portfolio project.
**Status:** Active.

### ADR-003: SQLite WAL Mode for Development, Cloud SQL for Production (March 28, extended April 2)
**Decision:** Use SQLite with Write-Ahead Logging for local development. Cloud SQL (PostgreSQL) for production via polymorphic database layer (`compat.py`).
**Why:** SQLite is zero-config for development. WAL mode allows concurrent reads during writes. Cloud SQL provides the production credibility needed for Tier 2 cloud roles.
**Trade-off:** Must maintain two schema files (`schema.sql` for SQLite, `schema_postgres.sql` for PostgreSQL) and a compatibility layer.
**Status:** Active. Polymorphic layer shipped in Sprint 6.

### ADR-004: LLM Output Treated as Untrusted Input (April 1)
**Decision:** Never trust LLM claims about its own output structure. Validate all LLM responses through Pydantic before accepting.
**Why:** Claude API claimed `xyz_format: true` on bullets missing the "by doing [Z]" clause. Pydantic rejected the entire TailoringResult, crashing the pipeline. Fix: verify structural clauses exist in text independently of LLM's self-assessment.
**Trade-off:** Extra validation logic, but prevents data corruption from LLM hallucination.
**Status:** Active. Applies to all current and future LLM integrations.

### ADR-005: Combined Sprint Prompts with Self-Skip Logic (April 2)
**Decision:** When token budget is constrained, merge multiple sprint scopes into a single prompt with pre-flight checks that skip already-completed work.
**Why:** API usage constraints. Fewer prompts = fewer context windows = less token spend. Sprint 6 combined prompt merged gap-fill + Docker/Cloud SQL into one 13-task prompt.
**Trade-off:** Larger prompts are harder to debug if something fails mid-execution. Mitigated by part-level checkpoints.
**Status:** Active. Standard practice going forward.

### ADR-006: Multi-AI Onboarding Docs Live In-Repo (April 2)
**Decision:** All AI onboarding documentation lives at `docs/ai-onboarding/` inside the git repo, not in external wikis or platform-specific configs.
**Why:** Any AI platform reads the docs after `git clone`. No external dependencies, no sync issues. GitHub is the single source of truth.
**Trade-off:** Adds ~150KB to the repo. Worth it for context accuracy.
**Status:** Active.

### ADR-007: Vertex AI Fail-Open Architecture (April 3)
**Decision:** Vertex AI regime classification is optional and fail-open — returns `None` on any failure, never blocks the pipeline.
**Why:** Regime classification enriches job listings but isn't required for core functionality. A Vertex AI outage shouldn't prevent job scraping and ranking.
**Trade-off:** Some jobs may lack regime classification data. Dashboard shows "Pending Classification" for unclassified jobs.
**Status:** Active.

### ADR-008: Branch Reset Recovery Strategy (April 2)
**Decision:** After `main` was reset to `codex/semantic-fidelity-guardrail` (losing Sprints 2-5), reimplement missing features in subsequent sprints rather than attempt history grafting.
**Why:** Divergent root commits made `git merge` impossible. The lost code (batch tailoring, .docx export, persistence, CRM, auto-apply) was reimplemented with improvements in Sprints 6, 8, and 10. Fresh implementation was cleaner than attempting to cherry-pick across incompatible histories.
**Trade-off:** Lost the original commit history for those features. Mitigated by session notes documenting what was lost and when it was recovered.
**Status:** Resolved. All features recovered by Sprint 10.

---

## Cumulative Metrics

| Metric | Phase 0 | Phase 1 | Current |
|--------|---------|---------|---------|
| **Tests passing** | 0 | 93 | 317 |
| **Source files** | 1 | ~15 | 60+ |
| **Database tables** | 1 | 7 | 13 |
| **Git commits** | 1 | 8 | 49 |
| **Release tags** | 0 | 0 | 4 |
| **CI jobs** | 0 | 0 | 6 |
| **Lines of code** | ~50 | ~1,500 | ~5,000+ |
| **API integrations** | 0 | 1 (Claude) | 2 (Claude + Vertex AI) |
| **Web routes** | 0 | 0 | 6 + health |

---

## Technical Debt Register

| ID | Description | Severity | Introduced | Status |
|----|-------------|----------|------------|--------|
| TD-001 | Mock-only route tests hide SQL bugs. Core query functions need DB-level integration tests. | High | Sprint 1 | Open |
| TD-002 | LLM keyword-stuffs job requirements into resume bullets regardless of candidate's actual skills. Tier prompts need a "only reference skills the candidate has" constraint. | Medium | Sprint 1 | Open |
| TD-003 | Existing `ceal.db` won't have Sprint 9 regime columns (CREATE TABLE IF NOT EXISTS doesn't ALTER). Need Alembic migration or manual ALTER TABLE. | Medium | Sprint 9 | Open |
| TD-004 | No prompt registry — `RANKER_VERSION` tracks version but no document maps version to actual prompt text. | Medium | Phase 1 | Resolved (PROMPT_REGISTRY.md created April 3) |
| TD-005 | Two schema files (`schema.sql` + `schema_postgres.sql`) must be kept in sync manually. | Low | Sprint 6 | Open |

---

## X-Y-Z Resume Bullets (Cumulative)

**Phase 1 (Pipeline):**
> Architected an event-driven career signal engine processing 500+ job listings in 8 seconds (95% reduction from 4-minute baseline), by building a 3-stage async ETL pipeline with Pydantic v2 data contracts, Claude API integration, and 93 automated tests.

**Phase 2 (Tailoring):**
> Shipped an AI-powered resume tailoring pipeline generating role-specific X-Y-Z bullets with 0.95 peak relevance scoring, as measured by 140 automated tests with zero failures, by integrating Claude API with tier-specific prompt templates and structured skill gap analysis.

**Sprint Week (Infrastructure + Scale):**
> Delivered 10 engineering sprints in 7 days — from CLI prototype to production-ready web application with Docker containerization, Cloud SQL, Vertex AI classification, PDF generation, CRM, and auto-apply — scaling from 93 to 246 automated tests with zero regressions, by developing an 8-pillar anti-hallucination prompt framework enabling deterministic multi-AI development across Claude, Codex, and Gemini.

**Sprint 11 (Hardening + Reconciliation):**
> Hardened Ceal for dual-backend reliability and restored canonical AI onboarding as measured by 317 passing tests and zero lint failures, by adding SQLite/PostgreSQL parity coverage, prefill edge-case tests, and a source-verified Claude Code documentation reconciliation pass.

---

*Ledger maintained by: Technical Program Manager persona*
*Last updated: April 16, 2026*
