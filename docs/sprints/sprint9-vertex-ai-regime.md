# Céal Sprint 9 — Vertex AI Regime Classification (Tier Strategy A/B Scaffolding)

## CONTEXT

You are working on the Céal project — an AI-powered career signal engine.
The project root is the `ceal/` directory containing `src/`, `tests/`, `pyproject.toml`, `requirements.txt`.

**Read these onboarding docs before starting:**
- `docs/ai-onboarding/PROJECT_CONTEXT.md` — Architecture, file inventory, current state
- `docs/ai-onboarding/PERSONAS.md` — Stakeholder personas and constraints
- `docs/ai-onboarding/RULES.md` — Engineering rules and incident history
- `docs/ai-onboarding/DEBRIEF_TEMPLATE.md` — Session note format

**Branch state**: You are on `main`. Recent commits:
- `d054f4e` feat: Sprint 8 — CRM + Auto-Apply reimplementation (reference-locked)
- `3b89465` docs: add multi-AI onboarding package for Claude, Codex, and Gemini
- `98177d4` feat: Docker + polymorphic Cloud SQL support (Sprint 6)

**Current validation baseline**:
- `pytest tests/ -q` → 220 passed
- `ruff check src/ tests/` → clean

**This sprint's scope**: Add an **optional**, fail-open Vertex AI classifier that recommends which existing Céal strategy tier (1, 2, or 3) best fits a job listing. Persist classification results with model/version metadata for prompt A/B analysis. This is about **classification + instrumentation**, not replacing the existing Claude ranker or tailoring engine.

**There is no preserved reference implementation for this sprint.** The authoritative sources are:
1. Current `main` codebase
2. Onboarding docs in `docs/ai-onboarding/`
3. Existing tier strategy semantics already in code
4. Official Google Vertex AI documentation (verify SDK/API details before coding)

**Stakeholders active for this sprint:**
- AI Architect (lead)
- ETL Architect
- QA Lead
- DPM

---

## CRITICAL RULES (Anti-Hallucination)

### From RULES.md (apply to ALL sprints):
1. **READ before WRITE**: Before modifying ANY file, read it first. Never assume file contents.
2. **No File Duplication**: Do NOT create files that duplicate existing functionality.
3. **Python 3.10+ Target**: No `datetime.UTC`, no `StrEnum`, no `match`, no `X | Y` without `from __future__ import annotations`.
4. **Import Paths**: All imports use `src.` prefix. Project uses `pythonpath = ["."]`.
5. **Async Everywhere**: `AsyncSession`, `async def` for DB and routes, `@pytest.mark.asyncio`.
6. **No Dialect-Specific SQL in Shared Paths**: Use `src.models.compat.is_sqlite()` branching.
7. **No Secrets in Code**: `.env` + `python-dotenv` only.
8. **Ruff**: `py310`, `line-length = 120`. Ignored: `UP017`, `UP042`, `E501`, `SIM102`, `SIM105`, `SIM108`, `B017`, `B904`.
9. **Test Isolation**: `StaticPool` in-memory SQLite, `asyncio_mode = "strict"`.
10. **Dual-Backend Testing**: Raw SQL functions need real SQLite integration tests, not just mocks (Jobs Tab Bug — 3x recurrence).

### Sprint 9-Specific Rules:
11. **Do NOT invent a new taxonomy.** The ONLY allowed classification outputs are the existing Céal tiers `1`, `2`, and `3`.
12. **Do NOT overwrite `company_tier`.** Company tier is company-lookup metadata from `company_tiers` table. Regime classification is stored in SEPARATE columns.
13. **Fail-open required.** If Vertex AI credentials/config are missing or the classifier errors, the existing pipeline MUST still work with zero degradation.
14. **Do NOT replace Claude.** Claude still performs semantic ranking (`llm_ranker.py`) and tailoring (`engine.py`). Vertex AI adds a Google-native classifier for strategy experimentation only.
15. **Do NOT fabricate GCP SDK names, client APIs, or auth patterns.** If any Google SDK detail is uncertain, STOP and verify from official docs before coding.
16. **No live Vertex AI calls in tests.** Use mocks/fakes only for the API layer. Real SQLite for persistence.
17. **Prefer new module-local models** over modifying `src/models/entities.py` unless absolutely necessary.

### Files That Must NOT Be Modified (Protected — per RULES.md):
| File | Why |
|------|-----|
| `src/tailoring/engine.py` | Semantic fidelity guardrail v1.1 — rejects hallucinated metrics |
| `src/tailoring/models.py` | Pydantic contracts used by engine, persistence, and export |
| `src/tailoring/db_models.py` | SQLAlchemy ORM models for Phase 2 tables |
| `src/tailoring/persistence.py` | Save/retrieve tailoring results |
| `src/models/compat.py` | Backend detection used by database.py, init_db, CI |
| `src/models/entities.py` | Pydantic models used by every pipeline stage (modify ONLY if blocked — explain why) |
| `src/apply/prefill.py` | Deterministic ATS prefill engine |

### Files That Require Explicit Permission (granted for this sprint):
| File | Permitted Change |
|------|-----------------|
| `src/models/schema.sql` | Add nullable regime classification columns to `job_listings` |
| `src/models/schema_postgres.sql` | Add matching nullable regime classification columns |
| `src/models/database.py` | Add regime classification DB helpers (read/write/stats) |
| `src/main.py` | Add opt-in `--classify-regimes` CLI path |
| `src/web/app.py` | No changes expected — but permitted if needed for health/stats |
| `src/web/routes/dashboard.py` | Add small regime summary card context |
| `src/web/templates/dashboard.html` | Add small regime summary card UI |
| `.env.example` | Add documented Vertex AI config vars |
| `requirements.txt` | Add pinned `google-cloud-aiplatform` dependency |
| `.github/workflows/ci.yml` | No changes expected this sprint |

---

## PRE-FLIGHT CHECK

Run these commands IN ORDER before starting any work:

```bash
# 1. Verify working directory
pwd
# Must be inside the ceal/ project root

# 2. Verify branch
git branch --show-current
# Must be: main

# 3. Recent commits
git log --oneline -5
# Expect to see Sprint 8 CRM + Auto-Apply commit (d054f4e)

# 4. Uncommitted changes
git status
# If modified files exist, read diffs and decide:
#   - Legitimate additions → commit with descriptive message
#   - Unexpected → STOP and report
# If clean, proceed.

# 5. Run all tests
pytest tests/ -q
# Must be: 220 passed. Fix failures before proceeding.

# 6. Verify lint
ruff check src/ tests/
# Must be: clean. Fix errors before proceeding.

# 7. Verify key files this sprint depends on
ls src/ranker/llm_ranker.py
ls src/tailoring/models.py
ls src/tailoring/engine.py
ls src/models/database.py
ls src/models/schema.sql
ls src/models/schema_postgres.sql
ls src/main.py
ls src/web/routes/dashboard.py
ls .env.example
ls requirements.txt

# 8. Verify files this sprint will CREATE don't already exist
ls src/ranker/regime_models.py 2>&1     # Should NOT exist
ls src/ranker/regime_classifier.py 2>&1  # Should NOT exist
ls tests/unit/test_regime_classifier.py 2>&1  # Should NOT exist
ls tests/integration/test_regime_classification_roundtrip.py 2>&1  # Should NOT exist
```

---

## EXISTING STRATEGY SEMANTICS (USE THESE — DO NOT INVENT NEW ONES)

The classifier target is the EXISTING tier model already in the codebase:

| Tier | Strategy | Source |
|------|----------|--------|
| 1 | Apply Now (Stripe, Square, Plaid, Coinbase, Datadog) | `PROJECT_CONTEXT.md`, `company_tiers` table |
| 2 | Build Credential (Google, AWS, MongoDB, Cloudflare) | `PROJECT_CONTEXT.md`, `company_tiers` table |
| 3 | Campaign (Google L5 TPM III, Customer Engineer II) | `PROJECT_CONTEXT.md`, `company_tiers` table |

The classifier's job: given a job listing, recommend which existing tier strategy should apply.

Also read for semantic context:
- `src/tailoring/models.py` → `TailoringRequest.target_tier` field
- `src/tailoring/engine.py` → `tier_strategy` mapping
- `src/ranker/llm_ranker.py` → `RANKER_VERSION` tracking pattern

---

## OUT OF SCOPE

- Replacing Claude with Vertex AI for ranking
- Replacing Claude with Vertex AI for tailoring
- Browser automation or ATS submission
- CRM / Auto-Apply feature expansion
- New prompt taxonomies beyond tiers 1/2/3
- Production Cloud Run deployment beyond env/config documentation
- Unreviewed prompt-routing logic that silently changes current behavior
- Changes to any protected file listed above

---

## FILE INVENTORY

### Files to Create (new)
| # | File | Lines (approx) | Purpose |
|---|------|----------------|---------|
| 1 | `src/ranker/regime_models.py` | ~60 | Pydantic models for regime classification (RegimeClassification, RegimeStats) |
| 2 | `src/ranker/regime_classifier.py` | ~120 | Vertex AI classifier module — prompt, API call, response parsing, fail-open |
| 3 | `tests/unit/test_regime_classifier.py` | ~150 | Mock-based tests for classifier parsing, validation, fail-open behavior |
| 4 | `tests/integration/test_regime_classification_roundtrip.py` | ~120 | Real SQLite tests for schema columns, save/read, stats query |

### Files to Modify (existing)
| # | File | Changes |
|---|------|---------|
| 5 | `src/models/schema.sql` | Add 5 nullable regime columns to `job_listings` table |
| 6 | `src/models/schema_postgres.sql` | Add matching 5 nullable regime columns |
| 7 | `src/models/database.py` | Add 3 async helpers: `get_jobs_missing_regime()`, `save_regime_classification()`, `get_regime_stats()` |
| 8 | `src/main.py` | Add `--classify-regimes` CLI flag and orchestration function |
| 9 | `src/web/routes/dashboard.py` | Add regime stats to dashboard context |
| 10 | `src/web/templates/dashboard.html` | Add Regime Classification summary card |
| 11 | `.env.example` | Add `VERTEX_PROJECT_ID`, `VERTEX_LOCATION`, `VERTEX_MODEL` |
| 12 | `requirements.txt` | Add pinned `google-cloud-aiplatform` |

---

## TASK 0: Read All Files That Will Be Modified

Before writing ANY code, read these files IN FULL:

```
src/models/schema.sql
src/models/schema_postgres.sql
src/models/database.py
src/main.py
src/web/routes/dashboard.py
src/web/templates/dashboard.html
.env.example
requirements.txt
```

Also read for reference (do NOT modify):
```
docs/ai-onboarding/PROJECT_CONTEXT.md
docs/ai-onboarding/PERSONAS.md
docs/ai-onboarding/RULES.md
src/ranker/llm_ranker.py
src/tailoring/models.py
src/tailoring/engine.py
src/models/entities.py
src/models/compat.py
tests/unit/test_ranker.py
tests/unit/test_database.py
tests/integration/test_persistence_roundtrip.py
```

---

## TASK 1: Add Regime Classification Models

**Read first**: `src/ranker/llm_ranker.py`, `src/tailoring/models.py`, `src/models/entities.py`

**Persona**: [AI Architect] — This task defines the LLM output contract. Enforce strict Pydantic validation.

Create `src/ranker/regime_models.py` with:

```python
# Scaffold — adapt to match existing codebase style after reading files above
from __future__ import annotations
from pydantic import BaseModel, Field, field_validator

class RegimeClassification(BaseModel):
    """Vertex AI regime classification result for a single job listing."""
    job_id: int
    recommended_tier: int = Field(..., ge=1, le=3)
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str = Field(..., min_length=1)
    model_version: str = Field(..., min_length=1)

    @field_validator("recommended_tier")
    @classmethod
    def tier_must_be_valid(cls, v: int) -> int:
        if v not in (1, 2, 3):
            raise ValueError(f"Tier must be 1, 2, or 3, got {v}")
        return v

class RegimeStats(BaseModel):
    """Summary counts for dashboard display."""
    tier_1_count: int = 0
    tier_2_count: int = 0
    tier_3_count: int = 0
    unclassified_count: int = 0
    total_classified: int = 0
```

**Verification**:
```bash
python -c "from src.ranker.regime_models import RegimeClassification, RegimeStats; print('Models OK')"
ruff check src/ranker/regime_models.py
```

---

## TASK 2: Add Persistence Columns to Schema

**Read first**: `src/models/schema.sql`, `src/models/schema_postgres.sql`

**Persona**: [ETL Architect] — This task modifies the schema. Columns must be nullable for backward compatibility. Do NOT touch `company_tier`.

Add these nullable columns to the `job_listings` table in BOTH schema files:

```sql
-- Add after existing columns, before closing paren or final constraint
recommended_tier        INTEGER,
regime_confidence       REAL,
regime_reasoning        TEXT,
regime_model_version    TEXT,
regime_classified_at    TEXT
```

**Rules**:
- `company_tier` remains UNCHANGED — it is company-lookup metadata
- All 5 columns must be nullable (no `NOT NULL`) for backward compat
- `regime_classified_at` is `TEXT` in SQLite (ISO format), `TIMESTAMP` in PostgreSQL
- Add an index on `recommended_tier` in both schemas: `CREATE INDEX IF NOT EXISTS idx_job_listings_recommended_tier ON job_listings(recommended_tier);`

**Verification**:
```bash
# Verify both schema files parse without syntax errors
python -c "
import sqlite3
conn = sqlite3.connect(':memory:')
with open('src/models/schema.sql') as f:
    conn.executescript(f.read())
print('SQLite schema OK')
conn.close()
"
# Spot-check the new columns exist
python -c "
import sqlite3
conn = sqlite3.connect(':memory:')
with open('src/models/schema.sql') as f:
    conn.executescript(f.read())
cursor = conn.execute('PRAGMA table_info(job_listings)')
cols = [row[1] for row in cursor.fetchall()]
for c in ['recommended_tier', 'regime_confidence', 'regime_reasoning', 'regime_model_version', 'regime_classified_at']:
    assert c in cols, f'Missing column: {c}'
print('All regime columns present')
conn.close()
"
```

---

## TASK 3: Add Vertex AI Classifier Module

**Read first**: `src/ranker/llm_ranker.py` (for style and version tracking pattern), `.env.example`

**Persona**: [AI Architect] — This task builds the Vertex AI integration. Enforce fail-open behavior, deterministic output parsing, and model version tracking.

Create `src/ranker/regime_classifier.py`:

**Requirements**:
- Accept job title, company name, location, and description
- Return a validated `RegimeClassification` from `regime_models.py`
- Classify ONLY into tier 1, 2, or 3 using the existing tier definitions
- Record `model_version` with format `"vertex-ai/{model_name}/{version}"`
- Use `google-cloud-aiplatform` SDK with Application Default Credentials
- Config from env vars: `VERTEX_PROJECT_ID`, `VERTEX_LOCATION`, `VERTEX_MODEL`
- **Fail-open**: If ANY of these conditions are true, return `None` (not an error):
  - `VERTEX_PROJECT_ID` not set
  - `google-cloud-aiplatform` not installed
  - API call fails
  - Response cannot be parsed into valid tier 1/2/3
- Strip markdown code fences from LLM response before JSON parsing (match the pattern in `engine.py`)
- Log warnings on failure but never raise exceptions that block the pipeline

**SDK verification**: Before writing import statements, confirm the correct import path from official Google docs. The expected pattern is:
```python
from vertexai.generative_models import GenerativeModel
```
If this path does not exist in the current SDK version, STOP and report.

**Verification**:
```bash
python -c "from src.ranker.regime_classifier import classify_regime; print('Classifier module OK')"
ruff check src/ranker/regime_classifier.py
```

---

## TASK 4: Add Database Helpers

**Read first**: `src/models/database.py`, `src/models/compat.py`

**Persona**: [ETL Architect] — This task adds raw SQL. ALL queries must work on both SQLite and PostgreSQL. Use `is_sqlite()` branching if dialect-specific SQL is needed.

Add these async helpers to `src/models/database.py`:

1. **`get_jobs_missing_regime(session) -> list[dict]`**
   - SELECT job_id, title, company, location, description FROM job_listings WHERE recommended_tier IS NULL AND match_score IS NOT NULL
   - Only classify jobs that have already been ranked (match_score exists)

2. **`save_regime_classification(session, classification: dict) -> None`**
   - UPDATE job_listings SET recommended_tier=?, regime_confidence=?, regime_reasoning=?, regime_model_version=?, regime_classified_at=? WHERE id=?
   - Idempotent — safe to re-run on already-classified jobs (overwrites previous classification)
   - Use portable timestamp: `datetime.now(datetime.timezone.utc).isoformat()` for SQLite, `func.now()` branch for PostgreSQL if needed

3. **`get_regime_stats(session) -> dict`**
   - COUNT grouped by recommended_tier (1, 2, 3, NULL)
   - Return dict with keys: `tier_1_count`, `tier_2_count`, `tier_3_count`, `unclassified_count`, `total_classified`

**Verification**:
```bash
python -c "from src.models.database import get_jobs_missing_regime, save_regime_classification, get_regime_stats; print('DB helpers OK')"
ruff check src/models/database.py
```

---

## TASK 5: Add Opt-In CLI Orchestration

**Read first**: `src/main.py`

**Persona**: [DPM] — This feature must be explicitly opt-in. The default pipeline path MUST NOT change. Users run `--classify-regimes` only when they want Vertex AI classification.

Add to `src/main.py`:

1. New CLI argument: `--classify-regimes` (store_true, default False)
2. New async function: `classify_regimes(session)`
   - Call `get_jobs_missing_regime()` to get unclassified ranked jobs
   - For each job, call `classify_regime()` from `regime_classifier.py`
   - If classifier returns `None` (fail-open), skip that job with a log warning
   - If classifier returns a valid `RegimeClassification`, call `save_regime_classification()`
   - Print summary: "Classified X/Y jobs" at the end
3. Wire into the existing CLI so `--classify-regimes` runs the classification pass AFTER the normal pipeline

**Critical**: The default `python -m src.main` path (scrape → normalize → rank) must work identically to today with NO Vertex AI calls.

**Verification**:
```bash
python -m src.main --help 2>&1 | grep "classify-regimes"
# Should show the new flag in help output
```

---

## TASK 6: Add Dashboard Regime Summary Card

**Read first**: `src/web/routes/dashboard.py`, `src/web/templates/dashboard.html`

**Persona**: [DPM] — Small UI addition only. Do NOT build a large new surface. One summary card showing regime classification counts.

1. In `dashboard.py`: call `get_regime_stats()` and add result to template context as `regime_stats`
2. In `dashboard.html`: add a "Regime Classification" card showing:
   - Tier 1 (Apply Now): {count}
   - Tier 2 (Credential): {count}
   - Tier 3 (Campaign): {count}
   - Unclassified: {count}
   - Show "No classifications yet — run with --classify-regimes" if total_classified == 0

**Verification**:
```bash
pytest tests/unit/test_web.py -v -k dashboard
```

---

## TASK 7: Add Unit Tests (Mocked Vertex AI)

**Read first**: `tests/unit/test_ranker.py` (for style)

**Persona**: [QA Lead] — No live API calls. Mock the Vertex AI client. Test parsing, validation, and fail-open exhaustively.

Create `tests/unit/test_regime_classifier.py`:

| Test | What it covers |
|------|---------------|
| `test_valid_classification_parsing` | Valid JSON → RegimeClassification with correct fields |
| `test_tier_validation_rejects_invalid` | Tier 0, 4, -1 all rejected by Pydantic |
| `test_confidence_bounds` | confidence < 0.0 or > 1.0 rejected |
| `test_code_fence_stripping` | Response wrapped in ```json ... ``` still parses |
| `test_fail_open_missing_config` | No VERTEX_PROJECT_ID → returns None, no exception |
| `test_fail_open_api_error` | Mocked API raises → returns None, no exception |
| `test_fail_open_unparseable_response` | Garbage response → returns None, no exception |
| `test_model_version_format` | model_version matches expected "vertex-ai/..." pattern |

**Verification**:
```bash
pytest tests/unit/test_regime_classifier.py -v
```

---

## TASK 8: Add Integration Tests (Real SQLite)

**Read first**: `tests/integration/test_persistence_roundtrip.py`, `tests/integration/test_crm_autoapply_roundtrip.py` (for pattern)

**Persona**: [QA Lead] + [ETL Architect] — Real SQL against in-memory SQLite. This is the DUAL-BACKEND TESTING rule.

Create `tests/integration/test_regime_classification_roundtrip.py`:

| Test | What it covers |
|------|---------------|
| `test_regime_columns_exist` | Schema creates all 5 regime columns on job_listings |
| `test_save_and_read_classification` | save_regime_classification → SELECT confirms data persisted |
| `test_get_jobs_missing_regime` | Only unclassified ranked jobs returned |
| `test_get_regime_stats` | Correct counts per tier after inserting test data |
| `test_reclassification_overwrites` | Running classification twice on same job overwrites cleanly |
| `test_regime_columns_nullable` | Insert a job with no regime data → no constraint error |

**Verification**:
```bash
pytest tests/integration/test_regime_classification_roundtrip.py -v
```

---

## TASK 9: Update Config

**Read first**: `.env.example`, `requirements.txt`

**Persona**: [ETL Architect]

1. Add to `.env.example`:
```bash
# Vertex AI (optional — regime classification)
VERTEX_PROJECT_ID=
VERTEX_LOCATION=us-east1
VERTEX_MODEL=gemini-2.0-flash
```

2. Add to `requirements.txt`:
```
google-cloud-aiplatform>=1.60.0
```

**Verification**:
```bash
grep "VERTEX_PROJECT_ID" .env.example
grep "google-cloud-aiplatform" requirements.txt
```

---

## TASK 10: Full Verification

**Persona**: [QA Lead] — Full suite, zero regressions.

```bash
# Run full test suite
pytest tests/ -v

# Verify lint
ruff check src/ tests/

# Count tests (should be > 220)
pytest tests/ --co -q 2>&1 | tail -3

# Verify classifier is optional (default pipeline still works)
python -c "
import asyncio
from src.models.database import get_engine, init_db
async def check():
    engine = await get_engine()
    await init_db(engine)
    print('Default init_db works without Vertex AI config')
asyncio.run(check())
"
```

**Acceptance criteria**:
- [ ] Full suite green (220+ existing tests pass, new tests pass)
- [ ] Lint clean
- [ ] Classifier is optional — default pipeline unaffected
- [ ] No Claude functionality regressed
- [ ] No protected files modified

---

## TASK 11: Create Session Note

**Persona**: [DPM]

Create: `docs/session_notes/YYYY-MM-DD_sprint9-vertex-ai-regime.md`

Use the format from `docs/ai-onboarding/DEBRIEF_TEMPLATE.md`. Document:
- What Vertex AI touchpoints were added
- What stayed intentionally Claude-based
- Exact env/config assumptions
- Exact tests added
- Career Translation (X-Y-Z bullet)

---

## COMMIT

```bash
git add src/ranker/regime_models.py \
        src/ranker/regime_classifier.py \
        src/models/schema.sql \
        src/models/schema_postgres.sql \
        src/models/database.py \
        src/main.py \
        src/web/routes/dashboard.py \
        src/web/templates/dashboard.html \
        .env.example \
        requirements.txt \
        tests/unit/test_regime_classifier.py \
        tests/integration/test_regime_classification_roundtrip.py \
        docs/session_notes/

git status

git commit -m "feat: Sprint 9 — Vertex AI regime classification (optional, fail-open)

Add Google Vertex AI classifier for tier strategy A/B testing.
- RegimeClassification Pydantic model (tier 1/2/3 only)
- Fail-open classifier module (returns None on any failure)
- 5 nullable regime columns on job_listings (both schemas)
- 3 DB helpers: missing/save/stats (portable SQLite + PostgreSQL)
- Opt-in CLI: --classify-regimes flag
- Dashboard regime summary card
- Unit tests (mocked API) + integration tests (real SQLite)
- Claude ranker and tailoring engine UNCHANGED

Co-authored-by: Josh Hillard <joshua.hillard4@gmail.com>"

git tag -a v2.9.0-sprint9-vertex-ai -m "Sprint 9: Vertex AI regime classification"
git push origin main --tags
```

---

## COMPLETION CHECKLIST

- [ ] `src/ranker/regime_models.py` — created with Pydantic validation
- [ ] `src/ranker/regime_classifier.py` — created with fail-open behavior
- [ ] `src/models/schema.sql` — 5 nullable regime columns added
- [ ] `src/models/schema_postgres.sql` — matching 5 nullable regime columns added
- [ ] `src/models/database.py` — 3 regime helpers added (portable SQL)
- [ ] `src/main.py` — `--classify-regimes` opt-in flag wired
- [ ] `src/web/routes/dashboard.py` — regime stats added to context
- [ ] `src/web/templates/dashboard.html` — regime summary card added
- [ ] `.env.example` — Vertex AI config vars documented
- [ ] `requirements.txt` — `google-cloud-aiplatform` pinned
- [ ] `tests/unit/test_regime_classifier.py` — 8+ mock-based tests
- [ ] `tests/integration/test_regime_classification_roundtrip.py` — 6+ real SQLite tests
- [ ] `docs/session_notes/` — session note created
- [ ] `pytest tests/ -v` — ALL pass (220+ existing + new)
- [ ] `ruff check src/ tests/` — 0 errors
- [ ] Default pipeline (`python -m src.main`) works WITHOUT Vertex AI config
- [ ] No protected files modified
- [ ] Committed and tagged `v2.9.0-sprint9-vertex-ai`
- [ ] Pushed to `origin/main`

---

## DESIGN GUARDRAILS (Interview Defense)

This sprint should be easy to defend in an interview:
- "Claude still performs semantic ranking and resume tailoring"
- "Vertex AI adds a Google-native classifier for prompt-strategy experimentation"
- "The rollout is incremental, observable, and fail-open"
- "Prompt A/B analysis is enabled through explicit version tracking, not hidden behavior changes"
- "The classifier is entirely optional — controlled by a CLI flag with zero impact on the default path"

If the implementation starts drifting into "replace Claude with Vertex" or "invent a new regime taxonomy," STOP and reset to the scope above.
