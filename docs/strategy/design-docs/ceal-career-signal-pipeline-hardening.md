# Ceal Career Signal Pipeline Hardening

*How the pipeline evolved from a basic scraper to a hardened, multi-stage system with LLM validation, semantic guardrails, and governance controls.*

---

## Stage 1: Core Pipeline (Phase 1)

**Problem:** Job listings scattered across platforms. Manual search is slow. No way to systematically rank listings against Josh's skills and target roles.

**What shipped:**
- 3-stage async ETL pipeline: Scraper → Normalizer → Ranker
- LinkedIn guest API scraper with rate limiting (`src/scrapers/base.py`, `linkedin.py`)
- HTML → structured data normalizer with salary parsing and skill extraction (`src/normalizer/pipeline.py`)
- Claude API scoring (0.0–1.0) with JSON response validation (`src/ranker/llm_ranker.py`)
- asyncio.Queue for stage-to-stage coordination with backpressure
- SQLite database with 7 tables, ON CONFLICT deduplication
- CLI orchestrator with multiple modes (`src/main.py`)
- 93 unit and integration tests

**Hardening decisions:**
- Pydantic v2 at every boundary — no raw dicts crossing modules
- LLM output treated as untrusted — JSON parsed, score bounds enforced
- Idempotent writes — re-running the pipeline doesn't create duplicates
- Rate limiting — scraper respects source API constraints

---

## Stage 2: Resume Tailoring + Semantic Guardrail (Phase 2)

**Problem:** Raw resume bullets don't target specific job listings. LLM rewriting can hallucinate metrics and fabricate experience.

**What shipped:**
- Resume parser (`src/tailoring/resume_parser.py`) — text → structured sections with skills
- Skill gap analyzer (`src/tailoring/skill_extractor.py`) — job vs. resume overlap
- Claude API bullet rewriting in X-Y-Z format (`src/tailoring/engine.py`)
- Semantic Fidelity Guardrail v1.1 — rejects hallucinated metrics, semantic drift
- Persistence layer (`src/tailoring/persistence.py`) — save/retrieve results
- Demo mode — offline skill analysis without database
- Batch mode — tailor 20-50 jobs in sequence
- 4 additional database tables (parsed_bullets, tailoring_requests, tailored_bullets, skill_gaps)

**Hardening decisions:**
- Guardrail is fail-closed — hallucinated content is rejected, original preserved
- Per-bullet granularity — one bad bullet doesn't invalidate the batch
- Original text preserved alongside tailored version for comparison
- Enrichment (skill gaps) fails open; core (bullet rewriting) fails closed

---

## Stage 3: Web UI + CRM + Auto-Apply (Sprints 1, 8)

**Problem:** Pipeline produces results but has no user interface. No way to track application state or manage the job search workflow.

**What shipped:**
- FastAPI + Jinja2 web application (`src/web/app.py`) with 7 route modules
- Dashboard with pipeline stats (`src/web/routes/dashboard.py`)
- Jobs view with tier-based ranking display (`src/web/routes/jobs.py`)
- CRM state machine: PROSPECT → APPLIED → INTERVIEWING → OFFER → REJECTED/ARCHIVED
- Kanban board UI (`src/web/routes/applications.py`)
- Follow-up reminder scheduling
- ATS prefill engine (`src/apply/prefill.py`) — deterministic field mapping, no LLM
- Approval queue with human review (`src/web/routes/apply.py`)
- Confidence scoring per pre-filled field
- 2 additional database tables (applications, application_fields)

**Hardening decisions:**
- Auto-apply is human-gated — approval queue is a hard gate, no bypass path
- Prefill is deterministic — no LLM involvement, no randomness
- State machine enforced in code — invalid transitions rejected
- Server-side form validation — never trust client-side data
- Proper HTTP status codes on all routes

**Branch reset incident (April 2):**
`main` was reset to `codex/semantic-fidelity-guardrail` to fix schema issues, temporarily removing CRM and Auto-Apply. Sprint 8 reimplemented both on the recovered Sprint 6 baseline using the preserved reference copy. This forced a clean reimplementation rather than a merge, resulting in tighter code.

---

## Stage 4: Infrastructure Hardening (Sprint 6)

**Problem:** Pipeline runs only on local SQLite. No containerization, no production database, no deployment path.

**What shipped:**
- Docker multi-stage build (Python 3.11-slim, < 3 min build time)
- Polymorphic database layer (`src/models/compat.py`) — same code runs SQLite and PostgreSQL
- PostgreSQL schema parity — 13 tables with matching constraints in both DDL files
- Cloud SQL integration via environment-based backend switching
- Health endpoint (`src/web/routes/health.py`) — database probe, always 200 when healthy
- docker-compose.yml with PostgreSQL 16 + web service

**Hardening decisions:**
- Dual schema files are mandatory — schema.sql and schema_postgres.sql must stay in sync
- PostgreSQL-specific gotchas documented: ROUND() requires CAST(x AS numeric), CREATE TRIGGER syntax differences
- Environment variables for backend switching — no code changes for dev vs. prod
- Health endpoint probes real database connectivity, not just process liveness

---

## Stage 5: LLM Enrichment Layer (Sprint 9)

**Problem:** All job rankings use the same scoring model. No way to distinguish tier strategy (Apply Now vs. Build Credential vs. Campaign) at the ranking level.

**What shipped:**
- Vertex AI regime classifier (`src/ranker/regime_classifier.py`) — optional tier classification
- Regime Pydantic models (`src/ranker/regime_models.py`)
- A/B instrumentation with `RANKER_VERSION` env var
- Database columns for classification metadata (regime_confidence, regime_reasoning, regime_model_version, regime_classified_at)

**Hardening decisions:**
- Fail-open design — Vertex AI failure returns None, pipeline continues without tier data
- Classification is enrichment, not core — never blocks the ranking pipeline
- Structured Vertex AI prompting with validated response parsing
- A/B scaffolding in place but experiment analysis deferred

---

## Stage 6: Document Generation (Sprint 10)

**Problem:** Tailored bullets and job data exist in the database but cannot be exported as professional documents.

**What shipped:**
- Resume PDF generation (`src/document/resume_pdf.py`) via ReportLab
- Cover letter PDF generation (`src/document/coverletter_pdf.py`) via ReportLab
- Claude API cover letter content engine (`src/document/coverletter_engine.py`)
- Brother Kit Rules design system (`src/document/design_system.py`) — colors, fonts, spacing
- TTF font loading from `data/fonts/` (Archivo, Inter, JetBrains Mono)
- Rich text parsing for bold metrics (`src/document/rich_text.py`)
- Streaming HTTP download (no temp files)
- Export route (`src/web/routes/export.py`)

**Hardening decisions:**
- ReportLab over HTML-to-PDF — pixel-level control, no browser dependency
- Committed font assets — deterministic rendering across local, Docker, and Cloud Run
- Streaming response — no temp files on server
- Cover letter content validated via Pydantic before rendering

---

## Hardening Themes Across All Stages

### 1. LLM Output Is Never Trusted
Every Claude API and Vertex AI response is validated structurally before use. JSON is parsed, fields are type-checked, bounds are enforced, and hallucinated content is rejected by the Semantic Fidelity Guardrail.

### 2. Pydantic v2 Is the Contract Layer
No raw dicts cross module boundaries. Every inter-module data transfer uses a Pydantic model. This is the primary mechanism preventing corrupt data propagation.

### 3. Fail-Open for Enrichment, Fail-Closed for Core
Vertex AI classification and skill gap analysis are nice-to-have — failures degrade gracefully. LLM scoring, Pydantic validation, and the Semantic Fidelity Guardrail are core — failures stop the pipeline.

### 4. Human Authority at Career-Critical Boundaries
The approval queue, confidence scoring, and manual review screen ensure no application is submitted without explicit human approval.

### 5. Idempotent Everything
ON CONFLICT upserts, deterministic prefill, reproducible PDF rendering. Re-running any operation produces the same result without side effects.

---

## Related Files

- `docs/ai-onboarding/PROJECT_CONTEXT.md` — Architecture overview with full file tree
- `docs/CEAL_PROJECT_LEDGER.md` — Timeline, decisions, retrospectives
- `CLAUDE.md` — Claude Code custom instructions with mode packs
- `.github/workflows/ci.yml` — 6-stage CI pipeline
- `src/models/schema.sql` — SQLite DDL (13 tables)
- `src/models/schema_postgres.sql` — PostgreSQL DDL (13 tables)
