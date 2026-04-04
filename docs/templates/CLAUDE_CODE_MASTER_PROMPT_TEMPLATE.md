# Claude Code Master Prompt — [Project Name]
**Paste as Claude Code custom instructions or CLAUDE.md**
*Version: 1.0 | [Date]*

---

## Core Contract

You are working on [Project Name], [1-sentence description].
Core flow: [primary flow]. Extended modules: [secondary features].

Stack: [comma-separated tech stack]

Rules:
1. Read each file before editing it. Search before assuming symbols exist.
2. [Data contract rule]
3. [External input rule]
4. [DB rule]
5. Keep diffs minimal and local to the task.
6. [Environment/OS rule]
7. Run targeted verification and report what actually passed.
8. Ask one brief question only if ambiguity creates material risk.
9. Do not fabricate file paths, function names, or test results.
10. [Project-specific safety rule — e.g., dual schema sync, protected files]

Key paths:
- [Domain]: path/to/files
- [Domain]: path/to/files
- [Tests]: path/to/tests

Full project context: [path to detailed context doc]

## Mode Packs (activate per task)

**MODE: db** — [1-line summary of DB rules]
**MODE: ml** — [1-line summary of ML rules]
**MODE: web** — [1-line summary of web rules]
**MODE: product** — [1-line summary of product rules]
**MODE: infra** — [1-line summary of infra rules]

Full mode pack text: [path to RUNTIME_PROMPTS.md]

## Task Format

Tasks follow this structure:
```
TASK: [title]
Goal: [what and why]
Scope: [in bounds]  |  Out of scope: [leave alone]
Inspect first: path::symbol (max 3-5)
Acceptance: [testable outcomes]
Verify: [targeted checks]
```

## Session Close Protocol

At session end, produce:
1. Summary: what changed, files touched, verification results
2. Updated test count if tests were added
3. Any new technical debt identified
4. [Project-specific close action — e.g., sync to external tool]

## Key Documents

| Doc | Location |
|-----|----------|
| Project Context | [path] |
| Project Ledger | [path] |
| Runtime Prompts | [path] |
| Prompt Architecture | [path] |
| [Other key doc] | [path] |
