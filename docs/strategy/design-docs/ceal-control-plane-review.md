# Ceal Control Plane Review

*Build-facing review of control-plane boundaries, file responsibilities, invariants, and deployed vs. planned distinctions.*

---

## Purpose

This document maps every control-plane boundary in Ceal — where data crosses trust levels, which files own which responsibilities, and what invariants must hold. It exists to prevent the most common failure mode in growing systems: ambiguity about what is deployed, what is built but not deployed, and what is planned but not built.

---

## File Inventory

### Pipeline Core (`src/`)

| File | Responsibility | Status |
|------|---------------|--------|
| `main.py` | CLI orchestrator (pipeline, rank-only, demo, batch, export, web) | Deployed |
| `batch.py` | Batch tailoring mode (20-50 jobs) | Deployed |
| `demo.py` | Offline demo mode (no DB) | Deployed |
| `export.py` | .docx resume export | Deployed |
| `fetcher.py` | Secure URL-to-text fetcher | Deployed |

### Scrapers (`src/scrapers/`)

| File | Responsibility | Status |
|------|---------------|--------|
| `base.py` | Abstract rate-limited scraper interface | Deployed |
| `linkedin.py` | LinkedIn guest API implementation | Deployed |

### Normalizer (`src/normalizer/`)

| File | Responsibility | Status |
|------|---------------|--------|
| `pipeline.py` | HTML → clean text, salary parsing, skill extraction | Deployed |

### Ranker (`src/ranker/`)

| File | Responsibility | Status |
|------|---------------|--------|
| `llm_ranker.py` | Claude API scoring (0.0–1.0) with JSON validation | Deployed |
| `regime_classifier.py` | Vertex AI tier classification (optional, fail-open) | Deployed |
| `regime_models.py` | Regime classification Pydantic models | Deployed |

### Models (`src/models/`)

| File | Responsibility | Status |
|------|---------------|--------|
| `entities.py` | Pydantic v2 models + enums (all pipeline boundaries) | Deployed |
| `database.py` | Async SQLAlchemy engine, sessions, all CRUD operations | Deployed |
| `compat.py` | Polymorphic backend detection (is_sqlite/is_postgres) | Deployed |
| `schema.sql` | SQLite DDL (13 tables, triggers, indexes) | Deployed |
| `schema_postgres.sql` | PostgreSQL DDL (13 tables, matching constraints) | Deployed |

### Tailoring (`src/tailoring/`)

| File | Responsibility | Status |
|------|---------------|--------|
| `engine.py` | Claude API bullet rewriting + Semantic Fidelity Guardrail v1.1 | Deployed |
| `models.py` | TailoringRequest, TailoringResult, TailoredBullet | Deployed |
| `resume_parser.py` | Resume text → ParsedResume (sections + skills) | Deployed |
| `skill_extractor.py` | Skill gap analysis (job vs. resume overlap) | Deployed |
| `persistence.py` | Save/retrieve tailoring results from DB | Deployed |
| `db_models.py` | SQLAlchemy ORM for tailoring tables | Deployed |

### Document Generation (`src/document/`)

| File | Responsibility | Status |
|------|---------------|--------|
| `coverletter_engine.py` | Claude API cover letter content generation | Deployed |
| `coverletter_pdf.py` | ReportLab cover letter PDF rendering | Deployed |
| `resume_pdf.py` | ReportLab resume PDF rendering | Deployed |
| `design_system.py` | Brother Kit Rules design tokens (colors, fonts, spacing) | Deployed |
| `font_manager.py` | TTF font loading (Archivo, Inter, JetBrains Mono) | Deployed |
| `rich_text.py` | Bold metric parsing for PDFs | Deployed |
| `models.py` | ResumeData, CoverLetterData, ExportResult | Deployed |

### Auto-Apply (`src/apply/`)

| File | Responsibility | Status |
|------|---------------|--------|
| `prefill.py` | Deterministic ATS prefill engine (no LLM) | Deployed |

### Web (`src/web/`)

| File | Responsibility | Status |
|------|---------------|--------|
| `app.py` | FastAPI factory (7 route modules) | Deployed |
| `routes/dashboard.py` | GET / — pipeline stats dashboard | Deployed |
| `routes/jobs.py` | GET /jobs — ranked listings with tier display | Deployed |
| `routes/applications.py` | GET /applications — CRM Kanban + reminders | Deployed |
| `routes/apply.py` | GET/POST /apply — approval queue + form prefill review | Deployed |
| `routes/demo.py` | GET/POST /demo — interactive tailoring demo | Deployed |
| `routes/export.py` | GET/POST /export — PDF resume + cover letter download | Deployed |
| `routes/health.py` | GET /health — database health probe | Deployed |

### Infrastructure

| File | Responsibility | Status |
|------|---------------|--------|
| `Dockerfile` | Multi-stage Python 3.11-slim build | Built |
| `docker-compose.yml` | PostgreSQL 16 + web service | Built |
| `.github/workflows/ci.yml` | 6-job CI pipeline | Deployed (GitHub Actions) |
| `deploy/cloudrun.sh` | GCP Cloud Run deployment | Built, not deployed |
| `pyproject.toml` | ruff, pytest, coverage config | Deployed |
| `requirements.txt` | 53 pinned dependencies | Deployed |
| `.env.example` | Environment variable documentation | Deployed |

---

## Critical Invariants

### Invariant 1: Pydantic at Every Boundary
No raw dict payloads cross module boundaries. Every data transfer between modules uses a Pydantic v2 model. Violations introduce silent corruption.

### Invariant 2: LLM Output Is Untrusted
Claude API and Vertex AI responses are parsed, validated, and bounds-checked before use. No LLM output reaches the database or user without structural validation.

### Invariant 3: Dual Schema Parity
`schema.sql` (SQLite) and `schema_postgres.sql` (PostgreSQL) must contain the same 13 tables with matching constraints. Any change to one must be reflected in the other.

### Invariant 4: Idempotent Writes
All database writes use ON CONFLICT clauses. Re-running any pipeline operation does not create duplicate records.

### Invariant 5: Human-Gated Applications
No application submission bypasses the approval queue. The prefill engine queues; humans approve.

### Invariant 6: Semantic Fidelity
The Semantic Fidelity Guardrail v1.1 rejects hallucinated metrics in tailored bullets. This guardrail is fail-closed and may not be bypassed.

### Invariant 7: Fail-Open Enrichment, Fail-Closed Core
Vertex AI classification and skill gap analysis fail open (return None, pipeline continues). LLM scoring, Pydantic validation, and the Semantic Fidelity Guardrail fail closed (errors stop the pipeline).

---

## Database Schema (13 Tables)

**Phase 1 (7 tables):** `job_listings`, `skills`, `job_skills`, `resume_profiles`, `resume_skills`, `scrape_log`, `company_tiers`

**Phase 2 (4 tables):** `parsed_bullets`, `tailoring_requests`, `tailored_bullets`, `skill_gaps`

**Phase 4 / CRM + Auto-Apply (2 tables):** `applications`, `application_fields`

**Sprint 9 additions:** `job_listings` gained regime columns (`regime_confidence`, `regime_reasoning`, `regime_model_version`, `regime_classified_at`).

---

## CI Pipeline (6 Jobs)

1. **Lint** (ruff check) — fail-fast
2. **Unit Tests** (Python 3.11/3.12) — depends on lint
3. **Integration Tests** — depends on unit tests
4. **Coverage Check** (80%+ gate) — depends on unit tests
5. **Docker Build** — depends on lint
6. **PostgreSQL Tests** (Postgres 16-alpine) — depends on unit tests

---

## Verified Gaps

| Gap | Description | Severity | Notes |
|-----|-------------|----------|-------|
| No prompt versioning in DB | LLM prompt changes silently affect scores | Medium | Prompt version not stored alongside results |
| No LLM response archival | Raw Claude responses discarded after validation | Low | Limits post-hoc analysis |
| Cover letters ephemeral | Generated on-demand, not persisted | Low | Regeneration produces different content |
| Cloud Run not deployed | Docker image built, Cloud Run not provisioned | Medium | Deployment script exists but untested |
| A/B analysis deferred | RANKER_VERSION instrumented but not analyzed | Low | Data collection active, analysis pending |

---

## Related Files

- `docs/ai-onboarding/PROJECT_CONTEXT.md` — Full architecture with file tree
- `docs/CEAL_PROJECT_LEDGER.md` — Timeline, decisions, retrospectives
- `CLAUDE.md` — Claude Code master prompt
- `Foundations/Ceal System Trust Model.md` — Trust model
- `Governance/Human-in-the-Loop Governance.md` — Governance contract
