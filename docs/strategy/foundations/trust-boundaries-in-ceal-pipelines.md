# Trust Boundaries in Ceal Pipelines

*Where information crosses from lower-confidence to higher-authority zones, and what must happen at each crossing.*

---

## Principle

Every pipeline stage in Ceal receives input from a source with a different trust level. At each boundary, the system must validate-and-continue, reject-and-stop, or degrade-gracefully depending on whether the component is core or enrichment. No boundary may be crossed silently without structural validation.

---

## Boundary 1: Content Ingestion (Scraper → Queue)

**What crosses:** Raw HTML from LinkedIn guest API responses.

**Trust level:** Untrusted. External HTML may contain unexpected structure, missing fields, injection payloads, or rate-limit responses.

**Validation:** Scraper (`src/scrapers/linkedin.py`) parses HTML into `RawJobListing` objects. Rate limiting enforced at the base scraper level (`src/scrapers/base.py`). Malformed pages produce parse errors, not corrupt data.

**Fail mode:** Scraper errors are logged and skipped. No partial listings enter the queue.

---

## Boundary 2: Queue → Normalizer

**What crosses:** `RawJobListing` objects via `asyncio.Queue`.

**Trust level:** Semi-trusted. Structure is known (came from our scraper), but content is external (job descriptions written by employers).

**Validation:** Normalizer (`src/normalizer/pipeline.py`) produces `JobListingCreate` — a Pydantic v2 model that enforces required fields, salary range parsing, and skill extraction. Invalid listings are rejected at model construction.

**Fail mode:** Pydantic `ValidationError` → listing dropped, error logged.

---

## Boundary 3: Normalizer → Ranker (LLM Boundary)

**What crosses:** Validated `JobListingCreate` data sent to Claude API as a scoring prompt.

**Trust level of input:** Trusted (Pydantic-validated listing).
**Trust level of output:** Untrusted. Claude API returns JSON with a fit score, but the response may contain malformed JSON, out-of-range scores, or hallucinated fields.

**Validation:** `src/ranker/llm_ranker.py` strips code fences, parses JSON, validates score is float in [0.0, 1.0], validates boolean fields structurally. Failed parsing → listing not ranked (fail-closed for core scoring).

**Fail mode:** Unparseable or invalid LLM response → job skipped, error logged.

---

## Boundary 4: Ranker → Database Write

**What crosses:** Validated fit score + listing metadata written to `job_listings` table.

**Trust level:** Trusted (post-validation). Score has been bounds-checked, listing has been deduplicated by `external_id + source`.

**Validation:** `ON CONFLICT (external_id, source)` ensures idempotent upserts. No duplicate records. WAL mode (SQLite) or standard transactions (PostgreSQL).

**Fail mode:** Constraint violation → transaction rolled back, error logged.

---

## Boundary 5: Resume Parsing (Text → Structured Data)

**What crosses:** `data/resume.txt` parsed into `ParsedResume` with sections and skill lists.

**Trust level:** Trusted input (human-authored resume), but parsing must be deterministic.

**Validation:** `src/tailoring/resume_parser.py` extracts sections by header matching, identifies skills by vocabulary lookup. Output is a Pydantic model (`ParsedResume`).

**Fail mode:** Unparseable sections → empty section list, not crash.

---

## Boundary 6: Tailoring Engine (LLM Boundary)

**What crosses:** Resume bullets + job listing sent to Claude API for X-Y-Z rewriting.

**Trust level of output:** Untrusted. Claude may hallucinate metrics, fabricate experience, or drift from the original bullet's meaning.

**Validation:** Semantic Fidelity Guardrail v1.1 (`src/tailoring/engine.py`) rejects tailored bullets that:
- Introduce metrics not present in the original
- Drift from the original bullet's semantic meaning
- Hallucinate job titles, tools, or outcomes

**Fail mode:** Guardrail rejection → original bullet preserved, tailored version discarded.

---

## Boundary 7: Cover Letter Generation (LLM Boundary)

**What crosses:** Job listing + resume context sent to Claude API for cover letter content.

**Trust level of output:** Untrusted. Generated text must be structurally validated.

**Validation:** `src/document/coverletter_engine.py` returns `CoverLetterData` (Pydantic model). The Moss Lane address (actual address) must not be fabricated. Company name and role must match the source listing.

**Fail mode:** Invalid structure → cover letter generation fails, user notified.

---

## Boundary 8: Auto-Apply Prefill (No LLM)

**What crosses:** Validated application data from database → ATS form field mapping.

**Trust level:** Trusted. This boundary is entirely deterministic — no LLM involvement.

**Validation:** `src/apply/prefill.py` maps database fields to ATS form fields using a static mapping table. Confidence scoring indicates how well each field was matched.

**Fail mode:** Unmapped fields flagged with low confidence → human reviews before submission.

---

## Boundary 9: Approval Queue → Submission

**What crosses:** Pre-filled application awaiting human approval.

**Trust level:** Requires human authority. Automation queues; humans approve.

**Validation:** Approval queue (`src/web/routes/apply.py`) presents the pre-filled form for human review. No application is submitted without explicit approval.

**Fail mode:** Unapproved applications remain in queue indefinitely.

---

## Boundary 10: Vertex AI Classification (Enrichment)

**What crosses:** Job listing metadata sent to Vertex AI for tier classification.

**Trust level of output:** Untrusted, and non-critical (enrichment).

**Validation:** `src/ranker/regime_classifier.py` validates response structure. Classification metadata stored in `job_listings` regime columns.

**Fail mode:** Fail-open. Classification failure → `regime_confidence = None`, pipeline continues without tier data.

---

## Summary Table

| Boundary | Input Trust | Output Trust | Fail Mode | Validation |
|----------|------------|-------------|-----------|------------|
| Scraper → Queue | Untrusted | Semi-trusted | Skip listing | HTML parsing |
| Queue → Normalizer | Semi-trusted | Trusted | Drop listing | Pydantic v2 |
| Normalizer → Ranker | Trusted → Untrusted | Post-validation | Skip ranking | JSON parse + bounds |
| Ranker → DB | Trusted | Trusted | Rollback | ON CONFLICT |
| Resume parsing | Trusted | Trusted | Empty sections | Section detection |
| Tailoring (LLM) | Trusted → Untrusted | Post-guardrail | Keep original | Semantic Fidelity v1.1 |
| Cover letter (LLM) | Trusted → Untrusted | Post-validation | Fail generation | Pydantic model |
| Auto-apply prefill | Trusted | Trusted | Flag low confidence | Static mapping |
| Approval queue | Trusted | Human-gated | Hold in queue | Manual review |
| Vertex AI | Trusted → Untrusted | Enrichment | Fail-open (None) | Response validation |
