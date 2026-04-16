# Céal Strategy Documentation

*Canonical strategy artifacts that define how Céal reasons about trust, governance, delivery, and pipeline architecture.*

---

## Purpose

This directory holds the build-facing strategy documents for Céal. These docs are **load-bearing context** — they explain the *why* behind architectural invariants that appear as terse rules elsewhere (in `RULES.md`, `CLAUDE.md`, ADRs). When a rule's rationale is not obvious from code, the explanation is here.

All docs in this directory were verified against current `src/` on April 16, 2026. Strategy docs drift faster than code — treat any secondary claim (test counts, route counts, table names) as suspect until primary-source-verified.

---

## Index

### `foundations/` — System invariants and trust model

| Doc | One-liner |
|---|---|
| [ceal-system-trust-model.md](foundations/ceal-system-trust-model.md) | Deterministic vs. non-deterministic components; trusted/untrusted/context-locked inputs; authority boundaries |
| [trust-boundaries-in-ceal-pipelines.md](foundations/trust-boundaries-in-ceal-pipelines.md) | 10-boundary map of the pipeline — what crosses, trust level, validation, fail mode |
| [schema-validation-for-llm-output.md](foundations/schema-validation-for-llm-output.md) | Why LLM output is untrusted and how Pydantic v2 enforces contracts at every boundary |
| [transaction-identity-and-auditability.md](foundations/transaction-identity-and-auditability.md) | Canonical transaction types, deduplication keys, audit trail, known audit gaps |
| [golden-corpus-design.md](foundations/golden-corpus-design.md) | Fixture taxonomy, frozen LLM response strategy, test distribution, coverage gaps |

### `governance/` — Automation authority contracts

| Doc | One-liner |
|---|---|
| [human-in-the-loop-governance.md](governance/human-in-the-loop-governance.md) | What automation may do, may not do, and what requires Josh's explicit human authority |

### `program-management/` — Delivery discipline

| Doc | One-liner |
|---|---|
| [program-management-for-career-signal-infrastructure.md](program-management/program-management-for-career-signal-infrastructure.md) | Baseline validation, project phases, sequencing logic, 8-pillar sprint framework, Definition of Done |

### `design-docs/` — Architecture reviews

| Doc | One-liner |
|---|---|
| [ceal-career-signal-pipeline-hardening.md](design-docs/ceal-career-signal-pipeline-hardening.md) | Stage-by-stage hardening log (Phase 1 through Sprint 10) with decisions and rationale |
| [ceal-control-plane-review.md](design-docs/ceal-control-plane-review.md) | Control-plane boundaries, file responsibilities, invariants, deployed-vs-planned distinctions |

---

## Relationship to Other Docs

| Doc type | Purpose | Update cadence |
|---|---|---|
| `strategy/` (this directory) | The *why* — trust model, governance contract, delivery philosophy | Per-sprint, when architectural decisions evolve |
| `ai-onboarding/RULES.md` | Terse rules with incident history | Per-incident, per-sprint |
| `ai-onboarding/PROJECT_CONTEXT.md` | Full architecture reference for new AI sessions | Per-sprint, when file tree changes |
| `prompts/PROMPT_REGISTRY.md` | Active LLM prompt versions | Per-prompt change |
| `CEAL_PROJECT_LEDGER.md` | Timeline, decisions, retrospectives | Per-sprint |
| `CLAUDE.md` | Claude Code master prompt (Core Contract, Mode Packs) | When Core Contract or Mode Packs change |

---

## When to Update a Strategy Doc

1. **Trust model changes** → `foundations/ceal-system-trust-model.md`
2. **New pipeline stage or boundary** → `foundations/trust-boundaries-in-ceal-pipelines.md`
3. **New LLM integration** → `foundations/schema-validation-for-llm-output.md`
4. **New transaction type or audit gap identified** → `foundations/transaction-identity-and-auditability.md`
5. **Test fixture strategy evolves** → `foundations/golden-corpus-design.md`
6. **Governance contract changes** → `governance/human-in-the-loop-governance.md` (and notify Josh)
7. **Phase/sprint complete or process changes** → `program-management/program-management-for-career-signal-infrastructure.md`
8. **Major hardening decision** → append a new stage to `design-docs/ceal-career-signal-pipeline-hardening.md`
9. **Control-plane file inventory changes** → `design-docs/ceal-control-plane-review.md`

**Verification requirement:** Any strategy-doc update that cites code (file paths, symbols, test counts, DB tables) must be verified against current `src/` or `tests/` before commit. Strategy docs with stale code claims are worse than no docs.

---

*Maintained alongside `docs/ai-onboarding/` and `docs/prompts/`. Cross-reference: `CLAUDE.md` for the runtime Core Contract.*
