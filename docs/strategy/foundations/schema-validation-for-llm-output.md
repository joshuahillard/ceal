# Schema Validation for LLM Output

*Why LLM output must be structurally validated before use, and how Ceal enforces this.*

---

## Core Principle

LLM output is untrusted text until proven otherwise. Claude API responses may contain malformed JSON, out-of-range values, hallucinated fields, or structurally valid but semantically wrong content. Ceal uses Pydantic v2 at every module boundary to enforce structural contracts before any LLM output touches the database or reaches the user.

---

## LLM Integration Points in Ceal

### 1. Job Ranking (`src/ranker/llm_ranker.py`)

**Expected output:** JSON with a `score` field (float, 0.0–1.0) and optional `reasoning`.

**Validation steps:**
1. Strip markdown code fences (``` markers) from raw response
2. Parse as JSON — reject on `JSONDecodeError`
3. Extract `score` field — reject if missing or non-numeric
4. Validate bounds: `0.0 <= score <= 1.0` — reject if out of range
5. Validate boolean fields structurally (not string-comparison)

**Fail mode:** Unparseable or invalid response → job listing not ranked, error logged. Core function: fail-closed.

### 2. Resume Tailoring (`src/tailoring/engine.py`)

**Expected output:** JSON array of rewritten bullets in X-Y-Z format.

**Validation steps:**
1. Strip code fences from raw response
2. Parse as JSON array
3. Each bullet validated as `TailoredBullet` (Pydantic model)
4. Semantic Fidelity Guardrail v1.1 applied:
   - Reject bullets that introduce metrics not present in the original
   - Reject bullets that drift from the original semantic meaning
   - Reject bullets with hallucinated job titles, tools, or outcomes

**Fail mode:** Guardrail rejection → original bullet preserved, tailored version discarded. Per-bullet granularity: one bad bullet doesn't invalidate the batch.

### 3. Cover Letter Generation (`src/document/coverletter_engine.py`)

**Expected output:** Structured content sections for a cover letter.

**Validation steps:**
1. Parse Claude API response into `CoverLetterData` (Pydantic model)
2. Validate required sections present (greeting, body paragraphs, closing)
3. Validate company name and role match the source job listing

**Fail mode:** Invalid structure → generation fails, user notified. Core function: fail-closed.

### 4. Regime Classification (`src/ranker/regime_classifier.py`)

**Expected output:** Tier classification (1/2/3) with confidence and reasoning.

**Validation steps:**
1. Parse Vertex AI response into regime Pydantic models (`src/ranker/regime_models.py`)
2. Validate tier is one of the expected enum values
3. Validate confidence is numeric and bounded

**Fail mode:** Fail-open. Classification failure → `regime_confidence = None`, pipeline continues without enrichment.

---

## Common LLM Response Failure Modes

| Failure Mode | Example | Ceal Mitigation |
|-------------|---------|----------------|
| Markdown-wrapped JSON | ````json\n{...}\n```` | Strip code fences before parsing |
| Missing required field | `{"reasoning": "..."}` (no score) | Pydantic rejects missing fields |
| Out-of-range score | `{"score": 1.5}` | Bounds check: 0.0–1.0 |
| String boolean | `{"is_remote": "true"}` | Structural boolean validation |
| Hallucinated metric | "Increased revenue by 340%" (not in original) | Semantic Fidelity Guardrail v1.1 |
| Partial JSON | `{"score": 0.8, "reas` | JSONDecodeError caught |
| Extra fields | `{"score": 0.8, "made_up_field": ...}` | Pydantic ignores or rejects extras |
| Empty response | `""` | Detected before JSON parsing |

---

## Pydantic v2 Boundary Enforcement

Ceal enforces Pydantic v2 models at every module boundary, not just LLM output:

| Boundary | Model | Location |
|----------|-------|----------|
| Scraper → Queue | `RawJobListing` | `src/models/entities.py` |
| Queue → Normalizer | `JobListingCreate` | `src/models/entities.py` |
| Ranker output | Score validation | `src/ranker/llm_ranker.py` |
| Tailoring input | `TailoringRequest` | `src/tailoring/models.py` |
| Tailoring output | `TailoredBullet` | `src/tailoring/models.py` |
| Cover letter | `CoverLetterData` | `src/document/models.py` |
| Resume export | `ResumeData` | `src/document/models.py` |
| Export result | `ExportResult` | `src/document/models.py` |
| Regime classification | Regime Pydantic models | `src/ranker/regime_models.py` |

---

## Design Rule

> No raw dict payloads cross module boundaries. Every inter-module data transfer uses a Pydantic v2 model. This is not optional — it is the primary mechanism by which Ceal prevents corrupt data from propagating through the pipeline.

---

## Related Files

- `src/models/entities.py` — Core Pydantic models and enums
- `src/tailoring/models.py` — Tailoring-specific models
- `src/document/models.py` — Document generation models
- `src/ranker/regime_models.py` — Vertex AI regime models
- `src/ranker/llm_ranker.py` — Score parsing and validation
- `src/tailoring/engine.py` — Semantic Fidelity Guardrail v1.1
