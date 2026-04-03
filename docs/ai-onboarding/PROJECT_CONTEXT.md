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
- **Tests**: pytest with `asyncio_mode = "strict"`, 179+ passing
- **Lint**: ruff (`py310`, line-length 120)
- **CI**: GitHub Actions (lint → unit → integration → coverage → docker-build → db-tests-postgres)

## Current Architecture (post-Sprint 6)

```
ceal/
├── src/
│   ├── main.py                  # CLI entry point
│   ├── batch.py                 # Batch tailoring mode
│   ├── demo.py                  # Offline demo mode
│   ├── export.py                # .docx resume export
│   ├── fetcher.py               # Secure URL fetcher
│   ├── models/
│   │   ├── compat.py            # Backend detection (is_sqlite/is_postgres)
│   │   ├── database.py          # All DB operations, engine factory
│   │   ├── entities.py          # Pydantic models + enums
│   │   ├── schema.sql           # SQLite DDL (11 tables)
│   │   └── schema_postgres.sql  # PostgreSQL DDL (11 tables)
│   ├── normalizer/
│   │   └── pipeline.py          # HTML → clean text normalizer
│   ├── ranker/
│   │   └── llm_ranker.py        # Claude API scoring (0.0–1.0)
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
│       ├── app.py               # FastAPI factory (4 routers)
│       ├── routes/
│       │   ├── dashboard.py     # GET / — pipeline stats
│       │   ├── jobs.py          # GET /jobs — ranked listings
│       │   ├── demo.py          # GET/POST /demo — tailoring demo
│       │   └── health.py        # GET /health — DB probe
│       ├── static/style.css
│       └── templates/           # Jinja2 HTML templates
├── tests/
│   ├── unit/                    # 15 test files, mock-based
│   └── integration/             # Pipeline + persistence round-trip
├── data/
│   ├── resume.txt               # Josh's resume (parser-compatible)
│   └── sample_job.txt           # Test job listing
├── deploy/
│   └── cloudrun.sh              # GCP Cloud Run deployment
├── docs/
│   ├── ai-onboarding/           # ← YOU ARE HERE
│   └── session_notes/           # Sprint session logs
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
| **Sprint 2 (CRM)** | ❌ **MISSING** | Applications, Kanban, state machine, stale reminders |
| **Sprint 3 (Auto-Apply)** | ❌ **MISSING** | Prefill engine, approval queue, confidence scoring |
| Sprint 8 (future) | 📋 Planned | Reimplement CRM + Auto-Apply |
| Vertex AI integration | 📋 Planned | Regime classification for prompt A/B testing |

**Why are Sprints 2-3 missing?** On April 2, 2026, `main` was reset to the `codex/semantic-fidelity-guardrail` branch to fix schema issues. This lost the CRM and Auto-Apply implementations. Sprint 6 reimplemented Docker + Cloud SQL on the new baseline. The old reference code with CRM/Auto-Apply is preserved at `C:\Users\joshb\Documents\GitHub\ceal\` on Josh's machine.

## Database Schema (11 tables)

**Phase 1 (7 tables)**: `job_listings`, `skills`, `job_skills`, `resume_profiles`, `resume_skills`, `scrape_log`, `company_tiers`

**Phase 2 (4 tables)**: `parsed_bullets`, `tailoring_requests`, `tailored_bullets`, `skill_gaps`

Both `schema.sql` (SQLite) and `schema_postgres.sql` (PostgreSQL) contain all 11 tables with matching constraints.

## Target Roles (Why This Exists)

| Tier | Roles | Companies | Pay Range |
|------|-------|-----------|-----------|
| 1 (Apply Now) | Technical Solutions Engineer, Solutions Consultant | Stripe, Square, Plaid, Coinbase, Datadog | $90–140K |
| 2 (One More Credential) | Cloud Solutions Architect, DevOps Engineer | Google, AWS, MongoDB, Cloudflare | $100–170K |
| 3 (Campaign) | Google L5 TPM III, Customer Engineer II | Google, Amazon, Microsoft | $120–170K+ |
