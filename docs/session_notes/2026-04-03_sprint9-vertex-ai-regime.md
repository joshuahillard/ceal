# Ceal Session Notes — Thursday 2026-04-03

**Session type:** Sprint 9 — Vertex AI Regime Classification
**AI platform:** Claude Code (Opus 4.6)
**Branch:** main

## Objective
Add an optional, fail-open Vertex AI classifier that recommends which existing tier strategy (1, 2, or 3) best fits a job listing. Persist classification results with model/version metadata for prompt A/B analysis. Does NOT replace Claude for ranking or tailoring.

## Tasks Completed
| # | Task | Files | Status |
|---|------|-------|--------|
| 1 | Regime classification Pydantic models | src/ranker/regime_models.py | Created |
| 2 | Schema columns (both SQLite + PostgreSQL) | src/models/schema.sql, schema_postgres.sql | Modified |
| 3 | Vertex AI classifier module (fail-open) | src/ranker/regime_classifier.py | Created |
| 4 | Database helpers (missing/save/stats) | src/models/database.py | Modified |
| 5 | CLI --classify-regimes flag | src/main.py | Modified |
| 6 | Dashboard regime summary card | src/web/routes/dashboard.py, dashboard.html | Modified |
| 7 | Unit tests (mocked Vertex AI) | tests/unit/test_regime_classifier.py | Created |
| 8 | Integration tests (real SQLite) | tests/integration/test_regime_classification_roundtrip.py | Created |
| 9 | Config vars + dependency | .env.example, requirements.txt | Modified |

## Files Changed
- **Created:** src/ranker/regime_models.py, src/ranker/regime_classifier.py, tests/unit/test_regime_classifier.py, tests/integration/test_regime_classification_roundtrip.py
- **Modified:** src/models/schema.sql, src/models/schema_postgres.sql, src/models/database.py, src/main.py, src/web/routes/dashboard.py, src/web/templates/dashboard.html, .env.example, requirements.txt, tests/unit/test_web.py

## Test Results
| Metric | Value |
|--------|-------|
| Total tests | 246 |
| Passed | 246 |
| Failed | 0 |
| Lint errors | 0 |

## Architecture Decisions

1. **Fail-open by design:** If VERTEX_PROJECT_ID is unset, SDK is missing, or API errors, classify_regime() returns None. The pipeline proceeds unchanged.
2. **Separate columns from company_tier:** Regime classification uses 5 new nullable columns (recommended_tier, regime_confidence, regime_reasoning, regime_model_version, regime_classified_at). company_tier remains untouched — it's company-lookup metadata.
3. **Session-scoped DB helpers:** get_jobs_missing_regime() and save_regime_classification() accept an AsyncSession parameter so they work within the caller's transaction. get_regime_stats() follows the same pattern.
4. **Dashboard fail-safe:** _get_regime_stats_safe() wraps the DB call in try/except so the dashboard renders even if the regime tables/columns don't exist on an older DB.
5. **Model version tracking:** Format "vertex-ai/{model_name}/{date}" enables prompt A/B analysis by filtering classifications by model version.

## What Stayed Intentionally Claude-Based
- **LLM ranking:** src/ranker/llm_ranker.py — Claude scores job-resume fit (match_score)
- **Resume tailoring:** src/tailoring/engine.py — Claude rewrites bullets in X-Y-Z format
- **Tailoring persistence:** src/tailoring/persistence.py — unchanged

## Environment/Config Assumptions
- VERTEX_PROJECT_ID: Required to enable classification (blank = disabled)
- VERTEX_LOCATION: Defaults to us-east1
- VERTEX_MODEL: Defaults to gemini-2.0-flash
- google-cloud-aiplatform>=1.60.0 in requirements.txt
- Application Default Credentials for GCP auth (gcloud auth application-default login)

## What's NOT in This Session
- No production deployment to Cloud Run
- No Alembic migration (schema changes require fresh DB or manual ALTER TABLE)
- No live Vertex AI API calls in tests (all mocked)
- No replacement of Claude for any existing functionality
- No new tier taxonomy — classifier outputs tiers 1, 2, 3 only

## Career Translation (X-Y-Z Bullet)
> Accomplished optional Vertex AI regime classification with fail-open architecture as measured by 246 passing tests and zero regression to the existing Claude-based pipeline, by doing strict Pydantic validation, dual-backend SQL (SQLite + PostgreSQL), and explicit version tracking for prompt A/B analysis.
