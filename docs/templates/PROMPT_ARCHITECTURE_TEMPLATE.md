# [Project Name] Master Prompt Architecture
**Human-facing reference: how the prompt system works and why**
*Owner: [Name] | Created: [Date] | Version: 1.0*

---

## What This Document Is

This is the design document for the prompt system. It explains the architecture, rationale, and maintenance protocol. It is NOT pasted into AI sessions — the runtime prompts live in RUNTIME_PROMPTS.md.

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
  Domain-specific rules. Available: db, ml, web, product, infra.
```

**Optional: SNAPSHOT block** (~50-100 tokens)
Attach only when the task depends on current branch, tag, or failing tests.

**Token budget:**
- Typical task: Core (~300) + Task Card (~200) = ~500 tokens
- With mode: + ~80 = ~580 tokens
- With snapshot: + ~80 = ~660 tokens
- Continuation: ~100-150 tokens

---

## Design Decisions

### path::symbol over line numbers
Line numbers shift with every commit. `path/to/file.py::ClassName` survives refactors and is greppable.

### Targeted verification over full suite
For a change to one module, run the tests for that module. Full suite before merge or broad changes only.

### Mode Packs over Persona Bindings
Personas (see PERSONA_LIBRARY.md) are human-facing thinking frameworks. At runtime, models need domain rules, not narrative. Mode Packs deliver rules in 60-120 tokens.

### Owner bio removed from Core
The model doesn't need career context for coding tasks. Owner context lives in MODE: product, activated only for resume bullets and strategy work.

### Volatile state in Snapshot, not Core
Test counts, tags, and branch names go stale after every sprint. Core stays stable; Snapshot is attached per-task only when needed.

---

## Maintenance Protocol

### After every sprint:
1. Update SNAPSHOT template values in RUNTIME_PROMPTS.md
2. Append to PROJECT_LEDGER.md (timeline, retro, any new ADRs)
3. If a new hard rule was adopted, add to Core Contract
4. If a Mode Pack needs a new rule, add it

### After stack changes:
1. Update Core Contract's stack line
2. Update relevant Mode Packs

### After adding a new ML/AI integration:
1. Add to Prompt Registry
2. Verify MODE: ml covers the new integration's failure modes

---

## Document Map

| Document | Type | Purpose |
|----------|------|---------|
| PROMPT_ARCHITECTURE.md | Human reference | This doc — explains the system |
| RUNTIME_PROMPTS.md | Copy-paste runtime | Core, Task Card, Mode Packs, Snapshot |
| CLAUDE_CODE_MASTER_PROMPT.md | Tool config | Full instructions for Claude Code |
| PERSONA_LIBRARY.md | Human reference | Thinking frameworks and interview prep |
| PROJECT_LEDGER.md | Living record | Timeline, decisions, retrospectives |

---

*Last updated: [date]*
