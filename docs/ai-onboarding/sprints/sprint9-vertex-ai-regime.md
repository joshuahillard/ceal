# Ceal Sprint 9 - Vertex AI Regime Classification (Tier Strategy A/B Scaffolding)

## CONTEXT

You are working on the Ceal project in the `ceal/` repo.

Current `main` now includes:
- Phase 1 pipeline: scrape -> normalize -> rank
- Phase 2 tailoring engine, persistence, demo mode, batch mode, export
- Sprint 1 web UI
- Sprint 6 Docker + polymorphic SQLite/PostgreSQL support
- Sprint 8 CRM + Auto-Apply reimplementation

Current validation baseline:
- `pytest tests/ -q` -> 220 passed
- `ruff check src/ tests/` -> clean

The next planned feature, documented in:
- `docs/ai-onboarding/PROJECT_CONTEXT.md`
- `docs/ai-onboarding/GEMINI_SYSTEM_PROMPT.md`

is:
- **Vertex AI integration for regime classification / prompt A/B testing**

There is **no preserved reference implementation** for this sprint.

That means the authoritative sources for this sprint are:
1. current `main`
2. onboarding docs in `docs/ai-onboarding/`
3. the existing tier strategy semantics already present in code
4. official Google Vertex AI documentation, if SDK/API details are uncertain

If any Google SDK name, auth flow, request shape, or model invocation detail is uncertain, STOP and verify it from official Google docs before coding. Do NOT guess.

## GOAL

Add an **optional** Vertex AI classifier that recommends which existing Ceal strategy tier best fits a job listing:
- Tier 1: Apply Now
- Tier 2: Build Credential
- Tier 3: Campaign

This recommendation must be persisted with model/version metadata so Ceal can use it for prompt A/B analysis later.

This sprint is about **classification + instrumentation**, not replacing the existing Claude ranker or tailoring engine.

## CRITICAL ANTI-HALLUCINATION RULES

1. READ before WRITE. Read every file before modifying it.
2. Do NOT invent a new taxonomy. The only allowed classification outputs are the existing Ceal tiers `1`, `2`, and `3`.
3. Do NOT overwrite `company_tier`. Company tier is company-lookup metadata. Prompt regime must be stored separately.
4. Vertex AI integration must be fail-open. If credentials/config are missing or the classifier errors, the existing pipeline still works.
5. Do NOT replace Claude ranking or tailoring in this sprint.
6. Do NOT invent GCP package names, client APIs, or auth patterns. Verify against official Google docs if needed.
7. No live Vertex AI calls in tests. Use mocks/fakes only.
8. Every new raw-SQL function needs real SQLite integration coverage.
9. All new SQL must work on both SQLite and PostgreSQL.
10. No secrets in code. Use `.env` + documented env vars only.
11. Prefer adding new module-local models over modifying `src/models/entities.py` unless absolutely necessary.
12. Keep the initial rollout narrow: classification, persistence, stats, and opt-in orchestration only.

## EXISTING STRATEGY SEMANTICS (USE THESE, DO NOT INVENT NEW ONES)

Use the current repo's existing tier model as the classifier target:
- `docs/ai-onboarding/PROJECT_CONTEXT.md` -> target role tiers
- `src/tailoring/models.py` -> `TailoringRequest.target_tier`
- `src/tailoring/engine.py` -> `tier_strategy`

The classifier's job is to recommend which **existing** tier strategy should be used for a listing or experiment cohort.

## OUT OF SCOPE

- Replacing Claude with Vertex AI for ranking
- Replacing Claude with Vertex AI for tailoring
- Browser automation or ATS submission
- CRM / Auto-Apply feature expansion
- New prompt taxonomies beyond tiers 1/2/3
- Production Cloud Run deployment work beyond env/config documentation
- Unreviewed prompt-routing logic that silently changes current behavior

## FILES TO READ FIRST

Read these current files in full before changing anything:

```text
docs/ai-onboarding/PROJECT_CONTEXT.md
docs/ai-onboarding/PERSONAS.md
docs/ai-onboarding/RULES.md
docs/session_notes/2026-04-03_sprint8-crm-autoapply.md
src/ranker/llm_ranker.py
src/tailoring/models.py
src/tailoring/engine.py
src/models/database.py
src/models/schema.sql
src/models/schema_postgres.sql
src/main.py
src/web/routes/dashboard.py
src/web/templates/dashboard.html
.env.example
requirements.txt
tests/unit/test_ranker.py
tests/unit/test_database.py
tests/integration/test_persistence_roundtrip.py
```

## EXPECTED SPRINT SHAPE

This sprint should produce a minimal, interview-defensible architecture:

1. **A dedicated regime-classification module**
   Suggested path:
   - `src/ranker/regime_models.py`
   - `src/ranker/regime_classifier.py`

2. **Separate persistence for classifier output on each job**
   Minimum persisted data:
   - recommended tier (`1` / `2` / `3`)
   - classifier confidence (`0.0-1.0`)
   - classifier reasoning
   - classifier model/version
   - classified timestamp

3. **Database helpers**
   Minimum helper set:
   - fetch jobs missing regime classification
   - save one classification
   - summarize regime counts for dashboards / analysis

4. **Opt-in orchestration**
   The existing pipeline must not silently change behavior.
   Add an explicit CLI path or flag such as:
   - `--classify-regimes`
   - or `--with-regimes`

5. **Tests**
   - mocked unit tests for Vertex response parsing / failure handling
   - real SQLite integration test for persistence and stats

## RECOMMENDED IMPLEMENTATION PLAN

### Task 0 - Pre-flight

Run:

```bash
git branch --show-current
git status
git log --oneline -5
pytest tests/ -q
ruff check src/ tests/
```

If baseline is not green, stop and fix baseline first.

### Task 1 - Add Regime Models

Create a new ranker-local model file instead of extending global entities unless blocked.

Suggested model:
- `RegimeClassification`
  - `job_id: int`
  - `recommended_tier: int` (must validate to 1, 2, or 3)
  - `confidence: float` (0.0-1.0)
  - `reasoning: str`
  - `model_version: str`

The validation rules must mirror the current repo's strict Pydantic style.

### Task 2 - Add Persistence Fields

Add nullable regime-classification fields to `job_listings` in both:
- `src/models/schema.sql`
- `src/models/schema_postgres.sql`

Suggested columns:
- `recommended_tier`
- `regime_confidence`
- `regime_reasoning`
- `regime_model_version`
- `regime_classified_at`

Rules:
- keep `company_tier` unchanged
- keep fields nullable for backward compatibility
- add an index only if clearly justified by query shape

### Task 3 - Add Vertex AI Classifier Module

Create a classifier module that:
- accepts job title, company name, location, and description
- returns a validated `RegimeClassification`
- classifies only into tier `1`, `2`, or `3`
- records model/version metadata

Auth / SDK rules:
- prefer the official current Google Vertex AI client path
- if package/API details are uncertain, verify from official docs before editing `requirements.txt`
- use Application Default Credentials or documented env-driven config
- never hardcode service-account material

### Task 4 - Add Database Helpers

Add helpers in `src/models/database.py` for:
- reading jobs missing regime classification
- saving classification output
- retrieving regime summary stats

These helpers must be portable across SQLite and PostgreSQL.

### Task 5 - Add Opt-In Orchestration

Integrate the classifier through an explicit path in `src/main.py`.

Allowed patterns:
- classify existing jobs in a dedicated mode
- or run classification during pipeline execution only when a flag is set

Do NOT make Vertex classification mandatory for the default path.

### Task 6 - Optional Minimal UI Exposure

If the data is already available cleanly, add a **small** dashboard summary card for regime counts.

Do not build a large new UI surface in this sprint.

### Task 7 - Tests

Minimum test additions:
- `tests/unit/test_regime_classifier.py`
  - response parsing
  - invalid tier rejection
  - confidence bounds
  - fail-open behavior when config/client fails
- `tests/integration/test_regime_classification_roundtrip.py`
  - schema columns exist
  - save/read classification
  - stats query works
  - jobs without classification are discoverable

### Task 8 - Config / Docs

Update `.env.example` with only documented, non-secret config such as:
- `VERTEX_PROJECT_ID`
- `VERTEX_LOCATION`
- `VERTEX_MODEL`

If a dependency is added, pin it and justify it in the session note.

### Task 9 - Full Verification

Run:

```bash
pytest tests/ -q
ruff check src/ tests/
pytest tests/ --co -q
```

Acceptance criteria:
- full suite remains green
- lint remains clean
- classifier is optional, not mandatory
- no current Claude functionality regressed

### Task 10 - Session Note

Create:
- `docs/session_notes/YYYY-MM-DD_sprint9-vertex-ai-regime.md`

Document:
- what Vertex AI touchpoints were added
- what stayed intentionally Claude-based
- exact env/config assumptions
- exact tests added

## DESIGN GUARDRAILS

This sprint should be easy to defend in an interview:
- "Claude still performs semantic ranking and tailoring"
- "Vertex AI adds a Google-native classifier for prompt-strategy experimentation"
- "The rollout is incremental, observable, and fail-open"
- "Prompt A/B analysis is enabled through explicit version tracking, not hidden behavior changes"

If the implementation starts drifting into "replace Claude with Vertex" or "invent a new regime taxonomy," stop and reset to the scope above.
