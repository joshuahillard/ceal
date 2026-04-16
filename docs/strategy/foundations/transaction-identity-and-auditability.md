# Transaction Identity and Auditability

*How to identify, track, and reconstruct meaningful transactions across Ceal's pipeline.*

---

## Why Identity Matters

Ceal processes job listings through a multi-stage pipeline where each stage produces artifacts that downstream stages depend on. Without clear transaction identity, common problems emerge:
- A tailored bullet cannot be traced back to the job listing and resume version that produced it
- Application state changes cannot be reconstructed in sequence
- LLM scoring results cannot be attributed to the prompt version and model that generated them
- Duplicate records accumulate when deduplication keys are ambiguous

---

## Canonical Transaction Types

### 1. Job Listing Transaction

**Identity key:** `external_id + source`

**Lifecycle:** Scraped → Normalized → Ranked → (optionally) Tailored → (optionally) Applied

**Database anchor:** `job_listings` table with `ON CONFLICT (external_id, source)` ensuring idempotent upserts.

**Audit trail:** `scrape_log` records per-run metrics (listings found, new vs. updated, errors). Each listing carries `scraped_at` and `ranked_at` timestamps.

### 2. Tailoring Transaction

**Identity key:** `job_id + profile_id + tier + emphasis`

**Lifecycle:** Request created → Resume parsed → Skills compared → Bullets rewritten → Results persisted

**Database anchor:** `tailoring_requests` table links to `tailored_bullets` (one-to-many). Each bullet carries its relevance score and X-Y-Z format flag.

**Audit trail:** `tailoring_requests.created_at` records when the tailoring was performed. The `tailored_bullets.original_text` preserves the pre-tailoring bullet for comparison.

### 3. Application Transaction

**Identity key:** `application_id` (linked to `job_listing_id`)

**Lifecycle:** PROSPECT → APPLIED → INTERVIEWING → OFFER (or REJECTED / ARCHIVED)

**Database anchor:** `applications` table with state machine enforcement. `application_fields` stores pre-filled form data.

**Audit trail:** State transitions carry timestamps. The approval queue records when a human reviewed and approved (or rejected) the pre-filled application.

### 4. Document Generation Transaction

**Identity key:** `job_id + document_type (resume | cover_letter)`

**Lifecycle:** Data gathered → LLM content generated (cover letter) → PDF rendered → HTTP download

**Database anchor:** No persistent storage — PDFs are generated on-demand and streamed via HTTP response (no temp files).

**Audit trail:** Export route logs which job listing triggered the generation. Cover letter content is produced fresh each time (not cached).

---

## Deduplication Strategy

| Entity | Dedup Key | Mechanism |
|--------|-----------|-----------|
| Job listings | `external_id + source` | `ON CONFLICT` upsert |
| Skills | `name` (normalized) | `ON CONFLICT` upsert |
| Job-skill associations | `job_id + skill_id` | `ON CONFLICT` ignore |
| Resume profiles | `name + version` | Unique constraint |
| Tailoring requests | `job_id + profile_id` | Application-level check |
| Applications | `job_listing_id` | One application per listing |

---

## Reconstruction Requirements

Given any artifact in the system, you should be able to trace back to its origin:

**From a tailored bullet** → the tailoring request → the job listing → the original scrape run
**From an application** → the job listing → the fit score → the ranking prompt version
**From a cover letter PDF** → the job listing title + company → the Claude API generation call
**From a fit score** → the LLM ranker prompt → the normalized listing data → the raw scraped HTML

---

## Current Audit Strengths

- **Idempotent writes:** ON CONFLICT prevents duplicate records across all tables
- **Timestamp tracking:** `scraped_at`, `ranked_at`, `created_at` on key entities
- **State machine enforcement:** Application transitions are explicit, not implicit
- **Scrape logging:** `scrape_log` table records per-run metrics
- **Original preservation:** `tailored_bullets.original_text` keeps the pre-LLM version

## Current Audit Gaps

- **No prompt versioning in DB:** The Claude API prompt used for scoring is not recorded alongside the score. Prompt changes silently produce incomparable scores.
- **No LLM response archival:** Raw Claude API responses are validated and discarded. The original response text is not stored for post-hoc analysis.
- **Cover letter ephemeral:** Cover letters are generated on-demand and not persisted. Regenerating produces different content each time.
- **No A/B attribution:** `RANKER_VERSION` env var enables A/B instrumentation for Vertex AI, but baseline vs. experiment results are not yet partitioned in analysis queries.

---

## Related Files

- `src/models/database.py` — All CRUD operations with idempotent upserts
- `src/models/entities.py` — Pydantic models defining transaction structure
- `src/models/schema.sql` — SQLite DDL with deduplication constraints
- `src/models/schema_postgres.sql` — PostgreSQL DDL (matching constraints)
- `src/tailoring/persistence.py` — Tailoring result save/retrieve
- `src/web/routes/applications.py` — Application state machine
