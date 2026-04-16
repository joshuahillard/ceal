# Céal — Project Context

> **Read this first.** This document gives any AI assistant the full context needed to work on Céal without hallucinating, duplicating files, or breaking existing functionality.

## What Is Céal?

Céal (pronounced "KAYL") is an AI-powered career signal engine built by Josh Hillard. It processes job listings through a 3-stage async ETL pipeline (Scraper → Normalizer → Ranker), then uses Claude API to tailor resume bullets to each listing using the Google X-Y-Z format.

**It is also a portfolio piece.** Every architectural decision, test, and deployment choice is designed to be defensible in a technical interview for roles at Stripe, Datadog, Google, and similar companies.

## Owner

- **Name**: Josh Hillard
- **Location**: Boston, MA
- **Background**: 6+ years at Toast (Manager II, Technical Escalations). Saved Toast an estimated $12M identifying firmware defects. Recognized by CEO at company-wide event.
- **Current status**: Career transition (since Oct 2025). Building Céal + Moss Lane (autonomous trading system) as portfolio projects.
- **Learning style**: Learns fast with clear instructions. Needs paste-ready commands. Explain the "why" behind decisions. Connect every feature to its resume/interview value.

## Repository

- **GitHub**: `https://github.com/joshuahillard/ceal`
- **Branch**: `main`
- **Language**: Python 3.10+
- **Framework**: FastAPI (async), SQLAlchemy (async), Pydantic v2
- **Database**: Polymorphic — SQLite (dev/test) + PostgreSQL (production via Cloud SQL)
- **Deployment**: Docker + GCP Cloud Run
- **Tests**: pytest with `asyncio_mode = "strict"`, 317 passing (verified 2026-04-16 via pytest)
- **Lint**: ruff (`py310`, line-length 120)
- **CI**: GitHub Actions (lint → unit → integration → coverage → docker-build → db-tests-postgres)

## Current Architecture (post-Sprint 11)

```
ceal/
├── src/
│   ├── main.py                  # CLI entry point
│   ├── batch.py                 # Batch tailoring mode
│   ├── demo.py                  # Offline demo mode
│   ├── export.py                # .docx resume export
│   ├── fetcher.py               # Secure URL fetcher
│   ├── apply/
│   │   └── prefill.py           # Deterministic ATS prefill engine
│   ├── models/
│   │   ├── compat.py            # Backend detection (is_sqlite/is_postgres)
│   │   ├── database.py          # All DB operations, engine factory
│   │   ├── entities.py          # Pydantic models + enums
│   │   ├── schema.sql           # SQLite DDL (13 tables)
│   │   └── schema_postgres.sql  # PostgreSQL DDL (13 tables)
│   ├── normalizer/
│   │   └── pipeline.py          # HTML → clean text normalizer
│   ├── document/
│   │   ├── __init__.py           # Package exports
│   │   ├── coverletter_engine.py # Claude API cover letter content
│   │   ├── coverletter_pdf.py    # ReportLab cover letter PDF
│   │   ├── design_system.py      # Brother Kit Rules design tokens
│   │   ├── font_manager.py       # TTF font loading
│   │   ├── models.py             # ResumeData, CoverLetterData, ExportResult
│   │   ├── resume_pdf.py         # ReportLab resume PDF
│   │   └── rich_text.py          # **bold** metric parsing for PDFs
│   ├── ranker/
│   │   ├── llm_ranker.py         # Claude API scoring (0.0–1.0)
│   │   ├── regime_classifier.py  # Vertex AI tier classification (optional, fail-open)
│   │   └── regime_models.py      # Regime classification Pydantic models
│   ├── scrapers/
│   │   ├── base.py              # Abstract scraper interface
│   │   └── linkedin.py          # LinkedIn scraper implementation
│   ├── tailoring/
│   │   ├── db_models.py         # SQLAlchemy ORM (Phase 2 tables)
│   │   ├── engine.py            # Tailoring engine + v1.1 guardrail
│   │   ├── models.py            # Pydantic models (tailoring)
│   │   ├── persistence.py       # Save/retrieve tailoring results
│   │   ├── resume_parser.py     # Resume → ParsedBullet extraction
│   │   └── skill_extractor.py   # Skill overlap analysis
│   └── web/
│       ├── app.py               # FastAPI factory (6 routers)
│       ├── routes/
│       │   ├── dashboard.py     # GET / — pipeline stats
│       │   ├── jobs.py          # GET /jobs — ranked listings
│       │   ├── demo.py          # GET/POST /demo — tailoring demo
│       │   ├── applications.py  # GET /applications — CRM Kanban + reminders
│       │   ├── apply.py         # GET/POST /apply — approval queue + review
│       │   ├── export.py        # GET/POST /export — PDF resume + cover letter
│       │   └── health.py        # GET /health — DB probe
│       ├── static/style.css
│       └── templates/           # Jinja2 HTML templates
├── tests/
│   ├── unit/                    # 17 test files, mock-based
│   └── integration/             # 4 round-trip / pipeline integration files
├── data/
│   ├── fonts/                   # TTF fonts (Archivo, Inter, JetBrains Mono)
│   ├── resume.txt               # Josh's resume (parser-compatible)
│   └── sample_job.txt           # Test job listing
├── deploy/
│   └── cloudrun.sh              # GCP Cloud Run deployment
├── docs/
│   ├── ai-onboarding/           # ← YOU ARE HERE (PROJECT_CONTEXT, RULES)
│   ├── historical/              # Archived PDFs/DOCX (Master Handoff, Project Charter, Phase 1 Handoff)
│   ├── prompts/                 # PROMPT_REGISTRY, RUNTIME_PROMPTS, MASTER_PROMPT_ARCHITECTURE
│   ├── reference/               # COWORK_PROJECT_INSTRUCTIONS, Plain_Language_Synthesis, SETUP_INSTRUCTIONS
│   ├── session_notes/           # Sprint session logs
│   └── strategy/                # Trust model, governance, program mgmt, design docs (see strategy/README.md)
├── alembic/                     # Database migrations
├── Dockerfile                   # Multi-stage build
├── docker-compose.yml           # PostgreSQL 16 + web
├── .github/workflows/ci.yml     # 6-job CI pipeline
├── pyproject.toml               # Tool config (ruff, pytest, coverage)
├── requirements.txt             # Pinned dependencies
└── .env.example                 # Environment variable docs
```

## What's Shipped vs. What's Missing

| Component | Status | Notes |
|-----------|--------|-------|
| Phase 1 (Scrape → Normalize → Rank) | ✅ Shipped | Core ETL pipeline |
| Phase 2 (Resume Tailoring Engine) | ✅ Shipped | Claude API + X-Y-Z format |
| Phase 2B (Demo, Batch, Export) | ✅ Shipped | Offline demo, .docx export |
| Semantic Fidelity Guardrail v1.1 | ✅ Shipped | Rejects hallucinated metrics/drift |
| Sprint 1 (Web UI) | ✅ Shipped | Dashboard, Jobs, Demo routes |
| Sprint 6 (Docker + Cloud SQL) | ✅ Shipped | Polymorphic DB, health endpoint |
| Sprint 2 (CRM) | ✅ Shipped | Applications route, Kanban board, job state machine, stale reminders |
| Sprint 3 (Auto-Apply) | ✅ Shipped | Prefill engine, approval queue, review screen, confidence scoring |
| Sprint 8 | ✅ Shipped | Reimplemented CRM + Auto-Apply on the recovered Sprint 6 baseline |
| Sprint 9 (Vertex AI) | ✅ Shipped | Optional fail-open regime classifier, tier strategy A/B scaffolding |
| Sprint 10 (PDF Gen) | ✅ Shipped | ReportLab resume + cover letter PDFs, Claude cover letter engine, export routes |
| Sprint 11 (Hardening + Docs) | ✅ Shipped | Prefill edge-case hardening, backend-aware DB parity harness (+71 tests), twin-docs reconciliation into canonical `docs/` tree |

**Branch reset recovery note:** On April 2, 2026, `main` was reset to the `codex/semantic-fidelity-guardrail` branch to fix schema issues. That temporarily removed CRM and Auto-Apply from `main`. Sprint 6 reimplemented Docker + Cloud SQL on the recovered baseline, and Sprint 8 reimplemented CRM + Auto-Apply using the preserved reference copy at `C:\Users\joshb\Documents\GitHub\ceal\`.

## Database Schema (13 tables)

**Phase 1 (7 tables)**: `job_listings`, `skills`, `job_skills`, `resume_profiles`, `resume_skills`, `scrape_log`, `company_tiers`

**Phase 2 (4 tables)**: `parsed_bullets`, `tailoring_requests`, `tailored_bullets`, `skill_gaps`

**Phase 4 / CRM + Auto-Apply (2 tables)**: `applications`, `application_fields`

Both `schema.sql` (SQLite) and `schema_postgres.sql` (PostgreSQL) contain all 13 tables with matching constraints.

**Sprint 9 additions**: `job_listings` gained regime columns (`regime_confidence`, `regime_reasoning`, `regime_model_version`, `regime_classified_at`) for Vertex AI tier classification metadata.

> See also: `docs/CEAL_PROJECT_LEDGER.md` for the full project timeline, and `docs/prompts/MASTER_PROMPT_ARCHITECTURE.md` for prompt system design rationale.

## Sprint History

| Sprint | What Shipped | Tests After |
|--------|--------------|-------------|
| Phase 0 | Project inception, architecture design | 0 |
| Phase 1 | 3-stage async ETL (Scraper → Normalizer → Ranker), Pydantic models, Claude API ranker | 93 |
| Phase 2 / 2B | Resume Tailoring Engine (X-Y-Z format), Demo/Batch/.docx Export | rolled into S1 |
| Sprint 1 | FastAPI + Jinja2 web UI (Dashboard, Jobs, Demo) | 140 |
| Sprint 6 | Docker + Cloud SQL polymorphic DB layer, /health | 179 |
| Sprint 8 | CRM (Kanban + state machine) + Auto-Apply (prefill, approval queue) | 202 |
| Sprint 9 | Vertex AI regime classification (fail-open, A/B instrumented) | 220 |
| Sprint 10 | PDF generation (ReportLab resume + cover letter), Claude cover letter engine | 246 |
| Sprint 11 | Prefill edge-case hardening + DB parity harness + twin-docs reconciliation | 317 |

*Counts match `pytest --collect-only` on the landing commit of each sprint.*

## Prompt Architecture (v1.1)

| Document | Location |
|----------|----------|
| Claude Code master prompt | `CLAUDE.md` (repo root) |
| Runtime prompts (Core Contract, Task Cards, Mode Packs) | `docs/prompts/RUNTIME_PROMPTS.md` |
| Prompt architecture design rationale | `docs/prompts/MASTER_PROMPT_ARCHITECTURE.md` |
| Prompt version registry | `docs/prompts/PROMPT_REGISTRY.md` |
| Project ledger (ADRs, retrospectives) | `docs/CEAL_PROJECT_LEDGER.md` |
| Engineering rules | `docs/ai-onboarding/RULES.md` |

## Target Roles (Why This Exists)

| Tier | Roles | Companies | Pay Range |
|------|-------|-----------|-----------|
| 1 (Apply Now) | Technical Solutions Engineer, Solutions Consultant | Stripe, Square, Plaid, Coinbase, Datadog | $90–140K |
| 2 (One More Credential) | Cloud Solutions Architect, DevOps Engineer | Google, AWS, MongoDB, Cloudflare | $100–170K |
| 3 (Campaign) | Google L5 TPM III, Customer Engineer II | Google, Amazon, Microsoft | $120–170K+ |
