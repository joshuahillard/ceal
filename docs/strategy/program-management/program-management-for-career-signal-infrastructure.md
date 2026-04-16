# Program Management for Career Signal Infrastructure

*Delivery discipline, sequencing logic, and definition of done for Ceal.*

---

## Baseline Validation

Before planning new work, confirm what actually exists:

**Deployed and verified (as of April 3, 2026):**
- 3-stage async ETL pipeline (Scraper → Normalizer → Ranker) — operational
- Resume tailoring engine with Semantic Fidelity Guardrail v1.1 — operational
- Demo mode (offline skill analysis, no DB required) — operational
- Batch tailoring mode (20-50 jobs, min_score filter) — operational
- FastAPI web UI with 7 routes (dashboard, jobs, demo, applications, apply, export, health) — operational
- CRM state machine (PROSPECT → APPLIED → INTERVIEWING → OFFER) — operational
- Auto-apply prefill engine with approval queue — operational
- PDF generation (resume + cover letter via ReportLab) — operational
- Vertex AI regime classification (optional, fail-open) — operational
- Docker multi-stage build — operational
- GitHub Actions CI (6-job pipeline, 295+ tests) — operational
- PostgreSQL schema parity (13 tables, both SQLite and PostgreSQL DDL) — operational

**Not yet deployed:**
- GCP Cloud Run production deployment — Docker image built, not yet running in Cloud Run
- Cloud SQL production database — schema ready, not provisioned
- A/B experiment analysis for Vertex AI scoring — instrumented, not analyzed

---

## Project Phases

### Phase 1 — Core Pipeline (March 28-29, 2026)
Scrape → Normalize → Rank. 93 tests. CLI orchestrator. LinkedIn guest API scraper.

### Phase 2 — Resume Tailoring (April 1-3, 2026)
Resume parser, skill gap analyzer, Claude API bullet rewriting (X-Y-Z format), demo mode, batch mode, persistence layer, URL fetcher.

### Sprint 1 — Web UI (April 2-3, 2026)
FastAPI + Jinja2 web application. Dashboard, jobs page, demo interface. 7 route modules + health check.

### Sprint 6 — Infrastructure (April 2, 2026)
Docker multi-stage build. Cloud SQL polymorphic database layer. PostgreSQL schema parity (13 tables). Environment-based backend switching.

### Sprint 8 — CRM + Auto-Apply (April 3, 2026)
CRM state machine with Kanban UI. Follow-up reminder scheduling. ATS prefill engine (deterministic). Approval queue + human review interface.

### Sprint 9 — Vertex AI Regime Classification (April 3, 2026)
Optional Vertex AI integration (fail-open). Tier classification (1/2/3). A/B instrumentation with RANKER_VERSION.

### Sprint 10 — PDF Document Generation (April 3, 2026)
Resume PDF (ReportLab, Brother Kit Rules design system). Cover letter PDF (Claude API content + ReportLab rendering). TTF font loading. Rich text parsing. Streaming HTTP download.

---

## Sequencing Logic

Ceal's sprint sequence follows dependency order:

1. **Core pipeline first** — nothing works without scrape → normalize → rank
2. **Tailoring after pipeline** — requires ranked listings to tailor against
3. **Web UI after core features** — UI surfaces existing functionality, doesn't create it
4. **Infrastructure after features** — Docker/PostgreSQL wraps working code, not speculative code
5. **CRM after web** — application tracking requires a UI to manage state
6. **Auto-apply after CRM** — prefill engine needs application records to populate
7. **PDF after tailoring** — documents require tailored content to render
8. **Vertex AI after scoring** — enrichment layer on top of existing ranking

---

## 8-Pillar Sprint Framework

Each sprint follows a structured format:

1. **Context** — Current state snapshot (what's deployed, what's the baseline)
2. **Critical Rules** — From RULES.md, plus sprint-specific additions
3. **Preflight Checks** — Verify repo state before starting (`pwd`, `git remote -v`, test baseline)
4. **File Inventory** — Which files to create, modify, or inspect
5. **Task Definitions** — Persona-tagged tasks with acceptance criteria
6. **Verification** — Targeted test commands to run after each task
7. **Completion Checklist** — All tests pass, no regressions, files updated
8. **Session Close** — Summary, test count, technical debt, NotebookLM sync suggestion

---

## Definition of Done

No sprint item is complete until it satisfies:

| Gate | Requirement | Evidence |
|------|------------|---------|
| Logic | Feature works as specified | Targeted test passes |
| Regression | No existing tests broken | Full test suite green |
| Schema | Both DDL files updated if schema changed | `schema.sql` and `schema_postgres.sql` in sync |
| Validation | Pydantic models at boundaries | No raw dict payloads crossing modules |
| CI | GitHub Actions pipeline passes | All 6 jobs green |
| Coverage | 80%+ code coverage maintained | Coverage report in CI |
| Documentation | PROJECT_CONTEXT.md updated if architecture changed | Diff shows context updates |

---

## Common PM Failure Modes (Ceal-specific)

1. **Modifying schema.sql without updating schema_postgres.sql.** Polymorphic database means dual-file updates are mandatory.
2. **Shipping LLM integration without validation.** Every Claude API call must validate the response structurally before use.
3. **Adding web routes without test coverage.** Routes must be tested with `httpx.AsyncClient`, not manual browser checks.
4. **Confusing "built" with "deployed."** Code in the repo is not the same as code running in production. Label clearly.
5. **Skipping the approval queue.** Auto-apply must always gate on human review. No shortcuts.
6. **Drifting from tier strategy.** Every feature should connect to Tier 1/2/3 interview value.

---

## Sprint Velocity Reference

| Sprint | Duration | Tests Added | Key Deliverable |
|--------|----------|------------|----------------|
| Phase 1 | 2 days | 93 | Core ETL pipeline |
| Phase 2 | 3 days | +60 | Resume tailoring engine |
| Sprint 1 | 1 day | +20 | Web UI (6 routes) |
| Sprint 6 | 1 day | +15 | Docker + Cloud SQL |
| Sprint 8 | 1 day | +30 | CRM + Auto-Apply |
| Sprint 9 | 0.5 day | +10 | Vertex AI classification |
| Sprint 10 | 0.5 day | +25 | PDF generation |
| **Total** | **7 days** | **295+** | **Full pipeline + web + docs + PDF** |

---

## Related Files

- `docs/CEAL_PROJECT_LEDGER.md` — Canonical timeline, decisions, retrospectives
- `docs/ai-onboarding/PROJECT_CONTEXT.md` — Full architecture reference
- `docs/prompts/RUNTIME_PROMPTS.md` — Core Contract + Mode Packs
- `CLAUDE.md` — Claude Code custom instructions
- `.github/workflows/ci.yml` — 6-stage CI pipeline
