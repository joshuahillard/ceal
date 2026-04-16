# Ceal Prompt Registry
**Version tracking for all LLM prompts used in the system**
*Owner: AI Architect persona | Created: April 3, 2026 | Last updated: April 16, 2026*

---

## Purpose

Every LLM prompt in Ceal is source code — it must be versioned, tracked, and auditable. This registry maps prompt versions to their actual text, parameters, and performance notes. Version strings (`RANKER_VERSION`, `PROMPT_VERSION`, etc.) are logged alongside every LLM output, enabling A/B testing and drift detection.

---

## Active Prompts — Summary

| Prompt ID | Component | Version Constant | Value | Model | Introduced |
|-----------|-----------|------------------|-------|-------|------------|
| `RANKER_V1` | `src/ranker/llm_ranker.py` | `RANKER_VERSION` | `"v1.0-ceal"` | Claude (httpx) | Phase 1 (Mar 29, 2026) |
| `TAILORING_V1.1` | `src/tailoring/engine.py` | `PROMPT_VERSION` | `"v1.1"` | Claude (httpx) | Sprint 1 / Phase 2 (Apr 1, 2026); bumped Sprint 2 |
| `REGIME_V1` | `src/ranker/regime_classifier.py` | (inline) | `"vertex-regime-v1"` | Vertex AI | Sprint 9 (Apr 3, 2026) |
| `COVERLETTER_V1` | `src/document/coverletter_engine.py` | `COVER_LETTER_PROMPT_VERSION` | `"v1.0"` | Claude (httpx) | Sprint 10 (Apr 3, 2026) |

---

## Per-Prompt Details

### RANKER_V1

| Field | Value |
|-------|-------|
| **Location** | `src/ranker/llm_ranker.py::RANKING_PROMPT_TEMPLATE` (line 58) |
| **Version constant** | `RANKER_VERSION = "v1.0-ceal"` (line 48) |
| **Persisted as** | `rank_model_version` column (format: `f"{RANKER_VERSION}-{self.model}"`, line 257) |
| **Model** | Claude (Anthropic API via httpx) |
| **Input** | Resume text + job title + company name + job description (truncated to 4,000 chars) |
| **Output schema** | JSON: `match_score` (0.0-1.0), `reasoning` (str), `skills_matched` (list), `skills_missing` (list) |
| **Validation** | Score bounds check, JSON parse with code fence stripping, field presence verification |
| **Introduced** | Phase 1 (March 29, 2026) |
| **Notes** | Initial ranking prompt. Tends to keyword-stuff requirements into bullets (TD-002). |

### TAILORING_V1.1

| Field | Value |
|-------|-------|
| **Location** | `src/tailoring/engine.py::_build_prompt` (line 210) |
| **Version constant** | `PROMPT_VERSION = "v1.1"` (line 41) |
| **Persisted as** | `tailoring_version` field (line 207) |
| **Model** | Claude (Anthropic API via httpx) |
| **Input** | Parsed resume sections + job requirements + skill overlap analysis |
| **Output schema** | JSON: array of `TailoredBullet` objects with `text`, `relevance_score`, `xyz_format` |
| **Validation** | Score bounds, `xyz_format` boolean verified structurally against text (never trusting LLM self-report, ADR-004), Pydantic model validation |
| **Introduced** | Sprint 1 / Phase 2 (April 1, 2026); bumped to v1.1 in Sprint 2 with Semantic Fidelity Guardrail additions |
| **Notes** | `xyz_format` boolean is verified by checking text for "by doing/by [verb]" clause — never trusting the LLM's self-report (Rule 11, ADR-004). Guardrail v1.1 rejects hallucinated metrics. |

### REGIME_V1

| Field | Value |
|-------|-------|
| **Location** | `src/ranker/regime_classifier.py::REGIME_PROMPT_TEMPLATE` (line 43) |
| **Version identifier** | `"vertex-regime-v1"` (inline) |
| **Model** | Vertex AI (Google-native classifier) |
| **Input** | Job listing metadata (title, company, description excerpt) |
| **Output schema** | Regime label (classification category) or `None` on failure |
| **Validation** | Fail-open: returns `None` on any error (ADR-007, Rule 15). Never blocks the pipeline. |
| **Introduced** | Sprint 9 (April 3, 2026) |
| **Notes** | Optional enrichment. A/B instrumented for comparing regime-aware vs. regime-unaware rankings. Experiment analysis deferred (TD: A/B analysis pending). |

### COVERLETTER_V1

| Field | Value |
|-------|-------|
| **Location** | `src/document/coverletter_engine.py::_SYSTEM_PROMPT` (line 38) + inline `user_prompt` (line 95) |
| **Version constant** | `COVER_LETTER_PROMPT_VERSION = "v1.0"` (line 24) |
| **Model** | Claude (Anthropic API via httpx) |
| **Input** | Job listing + parsed resume + tailored bullets (role context) |
| **Output schema** | 5-paragraph cover letter with structural arc (Pydantic-validated before PDF rendering) |
| **Validation** | Pydantic model validation before rendering. No LLM self-reported booleans trusted. |
| **Introduced** | Sprint 10 (April 3, 2026) |
| **Notes** | Uses same httpx + structured JSON prompting pattern as tailoring engine. Content is validated via Pydantic before ReportLab rendering (Rule 19: PDF generation isolation). |

---

## Retired Prompts

| Prompt ID | Component | Retired | Reason |
|-----------|-----------|---------|--------|
| *(none yet)* | | | |

---

## Prompt Engineering Rules

1. Every prompt change bumps the version constant and updates this registry (Rule 16).
2. Version strings are logged alongside every LLM output for traceability and A/B analysis.
3. Prompt text is treated as source code — review before deploying.
4. New prompts must define: Location, version constant, input schema, output schema, validation logic, failure mode.
5. LLM self-reported booleans are never trusted (Rule 11, ADR-004).
6. Code fences must be stripped before JSON parsing.
7. Enrichment prompts fail open; core prompts fail closed (Rule 15, ADR-007).

---

## Adding a New Prompt

1. Write the prompt with a version string (e.g., `PROMPT_VERSION = "v1.0"`) in the source file.
2. Add an entry to the summary table and a per-prompt detail section here.
3. Fill in all fields: Location (with line number), version constant, persisted column, model, input, output schema, validation, introduced sprint, notes.
4. Ensure output passes through Pydantic validation before use.
5. Add frozen fixture tests (never live API calls in unit tests).
6. Log the version alongside output in the persistence layer.
7. Update MODE: ml in `docs/prompts/RUNTIME_PROMPTS.md` if new failure modes emerge.
8. If the prompt change is architecturally significant, log an ADR in `docs/CEAL_PROJECT_LEDGER.md`.

---

## Verification Notes

All Locations, version constants, and values in this registry were verified against the current `src/` tree on April 16, 2026. When updating a prompt:
- Update the source file first.
- Run the relevant test suite to confirm the persistence layer logs the new version.
- Update this registry's corresponding row and detail section.
- Line numbers may drift — treat them as hints, not contracts.

---

*Registry maintained by: AI Architect persona*
*Cross-reference: Rule 16 in `docs/ai-onboarding/RULES.md`, MODE: ml in `docs/prompts/RUNTIME_PROMPTS.md`, ADR-004 and ADR-007 in `docs/CEAL_PROJECT_LEDGER.md`*
