# Ceal Master Prompt Architecture
**Human-facing reference: how the prompt system works and why**
*Owner: Josh Hillard | Created: April 3, 2026 | Version: 1.1*

---

## What This Document Is (And Isn't)

This is the **design document** for Ceal's prompt system. It explains the architecture, the rationale, and how to maintain it. It is NOT pasted into AI sessions — the runtime prompts live in `RUNTIME_PROMPTS.md`. If you're looking for the copy-paste text, go there.

---

## Problem (v1.0 Failures)

The original prompt approach had three failure modes:

**Fragmented context.** Project state was spread across 5+ overlapping documents (Cowork instructions, sprint prompts, persona doc, onboarding docs, session notes). Each new session had to reconcile slightly different versions of the same information.

**Sequential posting waste.** Each message re-established context that should already be loaded. Sprint prompts ranged from 12KB to 43KB. Most of that was background the model already knew.

**ML reteaching.** LLM integration constraints (validate output, version prompts, strip code fences) weren't front-loaded. Every session rediscovered the same failure modes.

**v1.0 improvement** cut from ~19K-44K to ~1,900 tokens per task but still had problems: the "stable" header contained volatile state (test counts, tags), the owner bio was irrelevant to coding tasks, persona bindings cost tokens without operational payoff, line-number references in task templates went stale immediately, and the doc mixed human guidance with runtime prompt text.

---

## Architecture: Three Runtime Pieces + Optional Snapshot

```
CORE CONTRACT (stable, ~250-350 tokens)
  Architecture facts and hard rules only.
  Changes: when the stack changes or a new rule is adopted.
  Does NOT contain: repo state, counts, owner bio, career strategy.

TASK CARD (per task, ~150-250 tokens)
  Goal, scope, out-of-scope, inspect-first symbols, acceptance, verify.
  Uses path::symbol references (durable across refactors).
  Verification is targeted to the task, not full-suite.

MODE PACK (optional, ~60-120 tokens)
  Domain-specific rules. Activated by task type, not persona narrative.
  Available: MODE: db, MODE: ml, MODE: web, MODE: product, MODE: infra
```

**Optional: SNAPSHOT block** (~50-100 tokens)
Attach only when the task depends on current branch, tag, failing tests, or other volatile state. Most tasks don't need it.

**Token budget:**
- Typical coding task: Core (~300) + Task Card (~200) = **~500 tokens**
- Task with domain rules: Core (~300) + Task Card (~200) + Mode (~80) = **~580 tokens**
- Task needing state: Core (~300) + Task Card (~200) + Mode (~80) + Snapshot (~80) = **~660 tokens**
- Multi-message continuation: **~100-150 tokens** (commit hash + delta description)

Compared to v1.0 (~1,900) and the original approach (~19K-44K), this is a 3-4x and 30-70x reduction respectively.

---

## Design Decisions

### Why path::symbol instead of line numbers
Line numbers shift with every commit. `src/models/database.py::get_top_matches` survives refactors and is greppable. The model can find the symbol itself — you just need to point it to the right file.

### Why targeted verification instead of full suite
`python -m pytest tests/ -v` on a 246-test suite takes time and bandwidth. For a change to one route handler, `python -m pytest tests/unit/test_web.py -v -k "test_jobs"` is faster and more informative. Full suite runs before merge or for broad changes (schema, pipeline, shared utilities).

### Why Mode Packs instead of Persona Bindings
The Persona Library (see `PORTABLE_PERSONA_LIBRARY.md`) is valuable as a human-facing thinking framework — it helps Josh internalize how different engineering roles approach problems, and it's interview prep material. But at runtime, a model doesn't need "Mental Model" and "Mission" paragraphs. It needs domain rules: "version prompt changes," "idempotent writes," "strip code fences." Mode Packs deliver those rules in 60-120 tokens instead of 200.

### Why the owner bio is removed from Core
Claude Code doesn't need career context to implement a database migration. Owner bio, career targets, and interview strategy belong in product/portfolio mode (`MODE: product`), activated only when the task is resume bullets, application strategy, or narrative framing.

### Why Constraint 5 (Tier 1/2/3 mapping) moved to MODE: product
"Every feature maps to a Tier 1/2/3 role and an X-Y-Z resume bullet" is a product strategy rule, not a coding rule. It belongs in the product mode pack, not the core contract that applies to every task.

---

## Maintenance Protocol

### After every sprint:
1. Update the SNAPSHOT template values in `RUNTIME_PROMPTS.md` (tag, test count, known issues)
2. Append to `CEAL_PROJECT_LEDGER.md` (timeline entry, retrospective, any new ADRs)
3. If a new hard rule was adopted, add it to the Core Contract
4. If a Mode Pack needs a new rule, add it

### After stack changes:
1. Update the Core Contract's stack line
2. Update relevant Mode Packs

### After adding a new LLM integration:
1. Add to Prompt Registry (`docs/prompts/PROMPT_REGISTRY.md`)
2. Verify MODE: ml covers the new integration's failure modes

---

## Document Map

| Document | Type | Purpose |
|----------|------|---------|
| `MASTER_PROMPT_ARCHITECTURE.md` | Human reference | This doc — explains the system |
| `RUNTIME_PROMPTS.md` | Copy-paste runtime | Core Contract, Task Card template, Mode Packs, Snapshot |
| `CLAUDE_CODE_MASTER_PROMPT.md` | Claude Code config | Full instructions file for Claude Code sessions |
| `PORTABLE_PERSONA_LIBRARY.md` | Human reference | Thinking frameworks for interview prep and mental models |
| `CEAL_PROJECT_LEDGER.md` | Living record | Timeline, decisions, retrospectives |
| `PROMPT_REGISTRY.md` | Repo artifact | LLM prompt version tracking |

---

*Architecture designed by: Josh Hillard + Claude*
*v1.0: April 3, 2026 | v1.1: April 3, 2026 (lean revision based on critical review)*
