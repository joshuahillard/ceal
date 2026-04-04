# [Project Name] Runtime Prompts
**Copy-paste blocks for AI sessions. Everything here is model input.**
*Version: 1.0 | [Date]*

---

## CORE CONTRACT

Paste once at session start. Update only when the stack or rules change.

```
[PROJECT] CORE v1.0

Project: [1-2 sentence description of what the project does]
Core flow: [primary data/process flow]
Extended modules: [secondary features]

Stack: [language, framework, DB, infra — comma-separated, no descriptions]

Rules:
- Read each file before editing it. Search before assuming symbols exist.
- [Data contract rule — e.g., "Pydantic v2 at module boundaries"]
- [External input rule — e.g., "LLM output is untrusted. Validate before use."]
- [DB rule — e.g., "Writes are idempotent. No duplicate records."]
- Keep diffs minimal and local to the task.
- [Environment rule — e.g., "PowerShell 5 compatible" or "Linux only"]
- Run targeted verification and report what actually passed.
- Ask one brief question only if ambiguity creates material risk.

Key paths:
- [Domain A]: path/to/files
- [Domain B]: path/to/files
- [Tests]: path/to/tests
- [Config]: path/to/config
```

---

## TASK CARD TEMPLATE

One per unit of work. Fill in and paste after Core Contract.

```
TASK: [short title]

Goal: [what and why, 1-2 sentences]
Scope: [what's in bounds]
Out of scope: [what to leave alone]

Inspect first:
- path/to/file.py::SymbolName
- path/to/other.py::function_name

Acceptance:
- [testable outcome 1]
- [testable outcome 2]
- [testable outcome 3]

Verify:
- [targeted test or check command]

Deliver:
- implement changes
- summarize touched files
- report verification honestly
```

---

## MODE PACKS

Append after Task Card when the task enters a specific domain.

### MODE: db
```
MODE: db
- [Idempotency rule for your DB — e.g., upserts, transactions]
- [Schema sync rule — e.g., dual schema files, migrations]
- [Concurrency rule — e.g., WAL mode, connection pooling]
- [Migration tool — e.g., Alembic, Flyway, Prisma]
- [Testing rule — e.g., test with real DB, not just mocks]
```

### MODE: ml
```
MODE: ml
- Version any prompt/model change and log it.
- [Output parsing rule — e.g., strip code fences, parse JSON]
- [Validation rule — e.g., validate scores, verify boolean claims]
- [Edge case testing — e.g., empty output, malformed JSON, timeout, rate limit]
- [Failure mode — e.g., enrichment fails open, core fails closed]
- [Test rule — e.g., frozen fixtures, no live API calls in unit tests]
```

### MODE: web
```
MODE: web
- [HTTP rule — e.g., proper status codes, server-side validation]
- [Template rule — e.g., extend base, no inline styles]
- [Testing rule — e.g., test routes with real client]
- [Health check rule]
```

### MODE: product
```
MODE: product
- [Owner context — who, what roles they're targeting]
- [Value mapping rule — e.g., every feature maps to business outcome]
- [Communication rule — e.g., frame as X-Y-Z bullet]
- [Update rule — e.g., update project ledger after shipping]
```

### MODE: infra
```
MODE: infra
- [Build rule — e.g., Docker < 3 min, health checks]
- [CI rule — e.g., must pass before merge]
- [Config rule — e.g., externalized via env vars, no secrets]
- [Rollback rule — e.g., documented procedure required]
- [Env file rule — e.g., update .env.example]
```

---

## SNAPSHOT (optional)

Attach only when the task depends on volatile repo state.

```
SNAPSHOT:
- Branch: [branch] | Tag: [tag]
- Tests: [count] passing, [warnings]
- Known issues: [relevant blockers or failing tests]
- Recent context: [1-2 sentences if prior work matters]
```

---

## CONTINUATION (for multi-message tasks)

```
Continue from commit [hash].
[Part/step] done. Now: [next objective].
State: [1-2 sentences of what changed].
```

---

*See [PROJECT]_MASTER_PROMPT_ARCHITECTURE.md for design rationale.*
