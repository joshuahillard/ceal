# Golden Corpus Design

*How Ceal's test fixtures establish deterministic baseline coverage for a pipeline that depends on non-deterministic LLM output.*

---

## Core Problem

Ceal's pipeline depends on Claude API and Vertex AI for scoring, tailoring, and classification. These are non-deterministic: the same input may produce different output across calls. Testing a pipeline that includes LLM calls requires either mocking the LLM boundary or accepting non-deterministic test results.

Ceal chooses mocking with frozen fixtures — deterministic canned responses that exercise every validation path without live API dependency.

---

## Fixture Categories

### 1. Scraper Fixtures (`tests/mocks/`)

**Purpose:** Realistic HTML that exercises the LinkedIn scraper's parsing logic.

**Current fixtures:**
- `linkedin_search_page.html` — Multi-result search page with pagination markers, sponsored listings, and edge-case formatting
- `linkedin_job_detail.html` — Full job posting with salary range, skills, description sections, and metadata

**Design rule:** Fixtures reflect real LinkedIn HTML structure. When LinkedIn changes their markup, fixtures are updated to match — not invented.

### 2. Job Listing Test Data (`data/`)

**Purpose:** Known-good inputs for normalizer and ranker testing.

- `sample_job.txt` — Representative job description for demo mode and unit tests
- `resume.txt` — Josh's actual resume in parser-compatible format (trusted input for tailoring tests)

### 3. Frozen LLM Response Fixtures

**Purpose:** Deterministic substitutes for Claude API responses used in unit tests.

**Coverage areas:**
- Valid JSON with score in [0.0, 1.0] → happy path
- Malformed JSON → parser error handling
- Out-of-range score (> 1.0, < 0.0, negative) → bounds rejection
- Missing required fields → Pydantic validation error
- Code-fence-wrapped JSON → fence stripping logic
- Empty response → pre-parse detection
- String booleans → structural validation
- Hallucinated metrics in tailored bullets → Semantic Fidelity Guardrail rejection

### 4. Database Fixtures

**Purpose:** Schema and CRUD testing with known data states.

**Approach:** Tests use fresh SQLite databases (`:memory:` or temp files) with schema loaded from `src/models/schema.sql`. No shared test database state — each test starts clean.

**Coverage areas:**
- Schema creation (all 13 tables)
- Idempotent upserts (ON CONFLICT behavior)
- Tier classification storage and retrieval
- Application state machine transitions
- Tailoring request/result round-trips

### 5. Integration Fixtures

**Purpose:** End-to-end pipeline tests using mock data through all stages.

**Current integration tests:**
- `test_pipeline.py` — Full scrape → normalize → rank flow with mocked HTTP
- `test_persistence_roundtrip.py` — Save → retrieve tailoring results
- `test_crm_autoapply_roundtrip.py` — CRM + auto-apply integration flow
- `test_pdf_export_roundtrip.py` — Resume + cover letter PDF generation
- `test_regime_classification_roundtrip.py` — Vertex AI classification
- `test_db_parity.py` — SQLite vs. PostgreSQL schema and behavior parity

---

## Test Distribution

| Category | File Count | Assertion Count | Purpose |
|----------|-----------|----------------|---------|
| Unit tests | 18 files | ~290 assertions | Mock-based, isolated component testing |
| Integration tests | 6 files | ~27 assertions | Round-trip and cross-component testing |
| CI matrix | 2 Python versions | 3.11 + 3.12 | Version compatibility |
| PostgreSQL tests | 1 CI job | Against Postgres 16-alpine | Production DB parity |

**Total:** 295+ tests, 80%+ coverage gate enforced in CI.

---

## Fixture Design Principles

1. **Use real data patterns first.** LinkedIn HTML fixtures reflect actual markup. Resume text is Josh's real resume. Job descriptions are realistic.

2. **Freeze LLM responses, don't generate them.** Every LLM test uses a hardcoded response string, not a live API call. This makes tests deterministic and fast.

3. **Test the validation, not the LLM.** The LLM's actual quality is not testable via fixtures. What IS testable: does the pipeline correctly validate, reject, or accept the LLM's output?

4. **One fixture per failure mode.** Each validation path (bounds check, JSON parse, guardrail rejection) has at least one dedicated fixture that triggers it.

5. **Database tests use real schemas.** No simplified test schemas. Tests load `schema.sql` and run against the full 13-table DDL.

6. **Parity tests catch schema drift.** `test_db_parity.py` ensures SQLite and PostgreSQL schemas produce identical behavior.

---

## Coverage Gaps (Known)

- **No adversarial prompt injection fixtures.** Tests don't exercise prompt injection via job descriptions.
- **No multi-page scraper pagination tests.** Current fixtures are single-page.
- **No Vertex AI response failure fixtures.** Fail-open behavior is tested, but not all failure shapes.
- **No concurrent pipeline stress tests.** asyncio.Queue backpressure is designed but not load-tested.

---

## Related Files

- `tests/unit/` — 18 unit test files
- `tests/integration/` — 6 integration test files
- `tests/mocks/` — HTML fixtures for scraper tests
- `data/sample_job.txt` — Test job description
- `data/resume.txt` — Parser-compatible resume
- `.github/workflows/ci.yml` — 6-stage CI pipeline with coverage gate
