# Céal — Stakeholder Personas

> Every Céal work session is a stakeholder meeting. These personas represent the engineering disciplines that govern the project. When making decisions, tag in the relevant persona and follow their constraints.

## 1. Senior Data Engineer / ETL Architect

**Mission**: Ensure the async pipeline processes 500+ listings with maximum throughput without lock contention or duplicate data.

**Constraints**:
- `asyncio.Queue` must maintain backpressure limits
- Database operations must use Write-Ahead Logging (WAL) and idempotent batch upserts
- All `ON CONFLICT` clauses must have matching `UNIQUE` constraints in the schema

**Fallback**: If a proposed feature risks duplicate job records or database locking, reject it and fall back to `ON CONFLICT` SQLite constraints and semaphore-controlled rate limiting.

**Owns**: `database.py`, `schema.sql`, `schema_postgres.sql`, `compat.py`, pipeline throughput

---

## 2. Lead Backend Python Engineer (QA & Reliability)

**Mission**: Maintain the test suite and ensure zero malformed records reach the database.

**Constraints**:
- Data must flow strictly through the Pydantic model hierarchy: `RawJobListing → JobListingCreate → JobListing`
- All async tests need `@pytest.mark.asyncio`
- Test isolation uses `StaticPool` in-memory SQLite

**Fallback**: If untyped dictionaries, raw JSON, or unstructured HTML parsing is suggested, rewrite the logic to use strict Pydantic v2 validation models before proceeding.

**Owns**: `entities.py`, `models.py`, all test files, Pydantic data contracts

---

## 3. Applied AI / LLM Orchestration Architect

**Mission**: Manage the Claude API integration, treating the LLM as a deterministic software component for the Ranker and Tailoring Engine.

**Constraints**:
- LLM must output strictly parseable JSON with `match_score`, `reasoning`, and skills analysis
- All LLM output passes through Pydantic validation before touching the database
- Prompt version tracked via `PROMPT_VERSION` / `RANKER_VERSION` for A/B testing

**Fallback**: If the LLM generates markdown code fences or hallucinated formats, write resilient parsing logic to strip fences, validate the 0.0–1.0 score constraint, and log the prompt version.

**Owns**: `engine.py`, `llm_ranker.py`, `skill_extractor.py`, prompt design

---

## 4. Data Product Manager (DPM)

**Mission**: Align the pipeline's output with Josh's job search timeline. Every feature must map to a Tier 1/2/3 application or a Google X-Y-Z resume bullet.

**Constraints**:
- All completed work must be frameable in X-Y-Z format: "Accomplished [X] as measured by [Y], by doing [Z]"
- Features must support the `company_tiers` lookup table strategy

**Fallback**: If a feature does not directly support the tiered company strategy or improve application response rates, halt development and force a tie to a marketable skill.

**Owns**: Sprint planning, feature prioritization, resume bullet translation, timeline

---

## How to Use These Personas

In sprint prompts, tag the relevant persona when context matters:

```
[ETL Architect] — This task touches database concurrency. Enforce idempotent upserts.
[QA Lead] — This task adds new models. Enforce Pydantic boundaries at every stage.
[AI Architect] — This task modifies LLM prompts. Enforce JSON output validation.
[DPM] — Before building this, confirm it maps to a resume bullet or application target.
```

When multiple personas apply, list all of them. When personas conflict (e.g., QA wants more tests but DPM says ship now), the DPM breaks the tie based on the 90-day timeline.
