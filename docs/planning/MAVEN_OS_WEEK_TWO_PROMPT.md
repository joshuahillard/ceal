# Maven OS Week-Two Kickoff — Concrete Tracker Adapter + Pipeline Hardening

> **Paste this entire document as the first message in a fresh chat.** The new Claude instance has zero prior conversation history; this prompt is authoritative. Verify every claim by reading the files listed before writing any code.

---

## Context — read these first

You are working on the **Ceal** project (Phase 2 complete + Sprints 1–11 shipped, plus the Maven OS Week-One Miniature). Ceal is an AI-powered career signal engine that scrapes job listings, ranks them with Claude, tailors resume bullets in Google X-Y-Z format, and generates PDF resumes/cover letters. The Maven OS pilot is a separate-but-adjacent governance pipeline for agentic handoffs (handoff document → linter → tracker action) that ships under `pilots/` and `tools/`.

- **Project root:** `C:\Users\joshb\Documents\Claude\Projects\Ceal\ceal`
- **GitHub:** https://github.com/joshuahillard/ceal
- **Owner:** Josh Hillard (Boston, MA)
- **Phase at prompt creation:** Maven OS Week-One Miniature complete (April 22–24). Sprint 11 was the prior main-line sprint (April 16). Repo state has the linter + Protocol-only `tracker_adapter` shipped, with `pilots/acme-corp/` as the first pilot scaffold.

**Read these in order before any code:**

1. `CLAUDE.md` (repo root) — Core Contract, Mode Packs, Task Format. Mode Packs `ml` and `db` apply to this work.
2. `docs/ai-onboarding/PROJECT_CONTEXT.md` — full project context, current architecture (post-Sprint 11)
3. `docs/ai-onboarding/RULES.md` — anti-hallucination engineering rules
4. `docs/CEAL_PROJECT_LEDGER.md` § Technical Debt Register and Sprint History — last entry is Sprint 11 (April 16, 2026)
5. `docs/planning/SELF_REVIEW.md` — Maven OS Week-One self-review with the 10-finding list. **This is the most important doc for this session — it identifies the P1 blocker that this prompt closes.**
6. `tools/handoff_lint.py` — the linter that produced 332 passing tests in Week One (read for context, do NOT modify in this session)
7. `tools/tracker_adapter/__init__.py` — the Protocol-only contract. Read it; do NOT modify it.
8. `pilots/acme-corp/pilot_profile.yaml` — declares `active_tracker: linear` (currently unresolvable)
9. `.github/workflows/handoff-lint.yml` — the CI gate that runs the linter (read for context)

---

## What's been done thus far

### Through Sprint 11 (March 28 → April 16) — base Ceal pipeline

- **Phase 1 — Core Pipeline:** 3-stage async ETL (Scrape → Normalize → Rank) with Pydantic v2 contracts at every boundary, async SQLAlchemy 2.0, Claude API ranker with explainable scoring, 93 tests on landing.
- **Phase 2 — Resume Tailoring:** Claude API + tier-specific prompt templates, X-Y-Z bullet generation, Semantic Fidelity Guardrail v1.1 (rejects hallucinated metrics).
- **Sprints 1–6:** FastAPI + Jinja2 web UI (6 routers + health), Docker containerization, polymorphic SQLite/PostgreSQL DB layer (`compat.py`).
- **Sprints 8–10:** CRM Kanban + state machine, Auto-Apply prefill engine + approval queue, Vertex AI regime classification (fail-open), ReportLab resume + cover letter PDFs, Claude cover letter engine.
- **Sprint 11:** Prefill edge-case hardening (empty/whitespace/unicode/malformed inputs), SQLite-first DB parity harness, twin-docs reconciliation into `docs/`.
- **Test count:** 317 passing local SQLite suite (verified 2026-04-16). PostgreSQL CI is red on schema-loader multi-statement init (TD-006).

### Maven OS Week-One Miniature (April 22–24) — agentic pipeline scaffold

The Maven OS work is a separate track from the main Ceal sprints. It builds a governance pipeline for agentic handoffs: a structured handoff document is linted for completeness/scope-drift/banned-terms, then routed via a tracker adapter to a work-tracking system (Linear/ClickUp/Notion/Jira).

**Shipped:**

- `pilots/acme-corp/` — first pilot directory: 15-section `handoff_spec.md` template with HTML-comment anchors, `pilot_profile.yaml` modular gate flags, `golden_corpus.jsonl` (20 cases, 35% adversarial), append-only `ledger.jsonl` (file exists, writer not built).
- `tools/handoff_lint.py` — CLI linter with 4 exit codes (PASS/BLOCK/ESCALATE/HARNESS_FAULT), 25% delta rule for scope-change detection (structural leaf-path symmetric difference), baseline resolution from PR base branch (resolved 2026-04-24).
- `tools/tracker_adapter/` — **Protocol-only**. Control-Surface Boundary preserved (no SDK leakage past the protocol) but **the boundary encloses empty space**.
- `tests/unit/test_handoff_lint.py` — 15 tests, all green; full Ceal suite 332 passing.
- `.github/workflows/handoff-lint.yml` — GHA workflow gating PRs that touch `pilots/**`.

**Not yet built / known gaps (from `docs/planning/SELF_REVIEW.md`):**

- Tracker adapter has no concrete implementations (P1) — `active_tracker: linear` in pilot_profile is unresolvable.
- Banned-term enforcement (IaC, Cloud Run, em dashes) is not wired into the linter (P2).
- 25% delta threshold is a hardcoded magic number (P2).
- `ALLOWED_SEVERITY`, `REQUIRED_SECTIONS`, and the 15-anchor list are hardcoded frozensets (P2).
- Golden corpus is 100% placeholder strings (P2).
- PyYAML pinned without an ADR (P2).
- Workflow not verified end-to-end via `act` (P2).
- `pilot_profile.yaml` has no Pydantic validator (P3).
- `ledger.jsonl` writer path not built (file is 0 bytes).

### Last session's determinations (April 30 evening)

- Read all relevant orientation, planning, and ledger docs across both Ceal and the LLM Model project.
- Confirmed Maven OS Week-One ships a linter without an action layer — **the linter is a gate that never actually gates**.
- Identified SELF_REVIEW finding #2 (Protocol-only tracker_adapter) as the highest-leverage move and the right kickoff for Week Two.

---

## What needs to change in the pipeline

The Maven OS pilot pipeline conceptually does **handoff document → linter (validation) → tracker (action)**. Today the validation layer ships with an empty action layer. Below is the gap list, ordered by priority. **This session focuses on P1.** P2 and P3 items are explicitly out of scope unless the user requests they be combined.

### P1 — blocking: action layer empty

- **Concrete tracker adapter for Linear.** `tools/tracker_adapter/linear.py` does not exist. `pilot_profile.yaml` declares `active_tracker: linear`. Any caller that imports a concrete adapter ImportErrors. **This session's primary deliverable.**

### P2 — pipeline depth (mechanical, low-risk; deferred to a follow-up prompt)

- **Banned-term enforcement.** One regex per term (IaC, Cloud Run, em dashes), BLOCK on match.
- **Move 25% delta threshold to per-pilot YAML** under `governance.scope_change_threshold_pct` so pilots can tune it with IM sign-off.
- **Schema-driven enums.** `ALLOWED_SEVERITY`, `REQUIRED_SECTIONS`, anchor list — read from a versioned schema file, not hardcoded.
- **PyYAML ADR.** One-line decision record under `docs/reference/` for the new top-level dependency.

### P3 — foundational (larger; deferred)

- **Replace placeholder corpus with real inputs** from pilot ticket history.
- **Pydantic validator for `pilot_profile.yaml`.**
- **End-to-end workflow verification** via `act` or a real GHA dry-run.
- **Build the `ledger.jsonl` writer** — append-only, schema-stamped, idempotent on re-runs.

### Carry-over from main Ceal (out of Maven OS scope but worth knowing)

- **TD-001 (HIGH):** Mock-only route tests hide SQL bugs. Core query functions need DB-level integration tests.
- **TD-002 (Medium):** LLM keyword-stuffs job requirements into resume bullets.
- **TD-006 (HIGH):** PostgreSQL DB Tests CI fails on multi-statement schema loader through asyncpg prepared statements.

---

## Goal for this session

Implement the **Linear concrete tracker adapter** at `tools/tracker_adapter/linear.py`, with full unit-test coverage and a smoke-test path through the pilot harness. After this session:

- `active_tracker: linear` in `pilots/acme-corp/pilot_profile.yaml` resolves at runtime
- The Control-Surface Boundary encloses real implementation
- SELF_REVIEW finding #2 closes
- The Maven OS pipeline is end-to-end functional for the Linear path (handoff → lint → tracker action)

---

## Open decisions — confirm with the user before writing code

1. **HTTP client.** Linear's official SDK is Node-only; Python integrations use the GraphQL API directly. Recommend `httpx` (already a Ceal dep, async-native, plays well with the rest of the stack). Confirm or push back.
2. **Authentication.** Linear API supports personal API tokens or OAuth. Recommend personal API token in `LINEAR_API_KEY` env var, read at adapter construction. Confirm.
3. **Mocking strategy for unit tests.** Mock at the HTTP layer (`respx` or `httpx.MockTransport`), not at the adapter method layer, so the GraphQL contract gets exercised. Confirm.
4. **Live smoke-test scope.** Should this session include a live Linear smoke run against a real workspace, or is unit-test green sufficient? Live runs require `LINEAR_API_KEY` set + a throwaway issue. Recommend deferring live smoke to a follow-up session and shipping unit-tested adapter only.
5. **Out-of-scope confirmation.** P2 items (banned-term, magic-number, hardcoded enums, PyYAML ADR) are intentionally deferred. Confirm — or fold one in if it's a small marginal cost.

---

## Tasks (after open decisions are settled)

1. **Verify context.** Run `pwd` (must end in `Ceal\ceal`), `git remote -v` (must point at `joshuahillard/ceal`), `git log --oneline -5`, `git status`. If wrong, stop and ask.
2. **Capture baseline tests.** `PYTHONPATH=. pytest tests/ -q` and record the count + exit code. (Anti-regression baseline for end of session.)
3. **Read** `tools/tracker_adapter/__init__.py` in full and capture the Protocol method signatures.
4. **Read** `pilots/acme-corp/pilot_profile.yaml` and any `handoff_spec.md` present to understand the expected input shape.
5. **Sketch the Linear GraphQL queries** needed to satisfy the Protocol:
   - Create issue
   - Update issue (state, assignee, labels)
   - Get issue by external/identifier
   - List issues by team / project
6. **Implement `tools/tracker_adapter/linear.py`:**
   - Single class `LinearAdapter` implementing the Protocol
   - HTTP client import lives **only in this file** (Control-Surface Boundary preserved)
   - Constructor accepts `api_key` (env-var read at instantiation) + `team_id` from pilot_profile
   - All methods are async (consistent with rest of Ceal)
   - Errors raise the Protocol-declared adapter error type. **Never leak the API token in error messages or logs.**
   - Idempotency: `create_issue` uses an external/source identifier to detect duplicates (consistent with Ceal's ON CONFLICT pattern, ADR-001).
7. **Write unit tests at `tests/unit/test_tracker_adapter_linear.py`:**
   - Mock at HTTP layer using `respx` or `httpx.MockTransport`
   - Cover: create-success, create-duplicate-detected, update-success, get-by-id-found, get-by-id-not-found, auth-fail (401), rate-limited (429), server-error (500), parsing-failure (malformed GraphQL response)
   - **Positive assertion** that the API token never appears in any logged or raised text
8. **Wire the adapter into the pilot harness** so `active_tracker: linear` resolves:
   - Grep for `active_tracker` first to find the resolver call site
   - Add a small registry mapping (`{"linear": LinearAdapter, ...}`) at the right boundary
   - Confirm an unknown `active_tracker` value raises a useful error
9. **Update `docs/planning/SELF_REVIEW.md`:**
   - Mark finding #2 RESOLVED with date and evidence (test path, assertion count delta)
   - Add a one-line note pointing to whichever P2/P3 items the user wants next
10. **Pre-commit critical review.** What's the riskiest line? What did the tests not cover? What would surprise an auditor in three months? Surface as a Limitations sub-section in the commit message body.
11. **Commit (no push).** Wait for explicit `PUSH` approval before pushing.

---

## Acceptance criteria

- [ ] `tools/tracker_adapter/linear.py` exists and implements the Protocol fully
- [ ] `tests/unit/test_tracker_adapter_linear.py` exists; full Ceal suite passes with the new tests added
- [ ] No HTTP/SDK imports anywhere outside `tools/tracker_adapter/linear.py`
- [ ] No Linear API token leaks in any logged or raised text — verified by a positive assertion in tests
- [ ] `active_tracker: linear` in `pilots/acme-corp/pilot_profile.yaml` resolves at runtime (smoke test from the pilot harness or a CLI smoke if direct invocation is supported)
- [ ] `docs/planning/SELF_REVIEW.md` updated with finding #2 closed
- [ ] No regression in existing test count (record before/after)
- [ ] Commit message follows the project convention (check `git log --oneline -10` for style); body includes a Limitations sub-section
- [ ] No push to GitHub without explicit `PUSH` approval

---

## What you should NOT do

- Do NOT modify `tools/tracker_adapter/__init__.py`. Week One verified the Protocol surface. If a method is genuinely missing from the Protocol, surface as a finding before adding it.
- Do NOT touch `tools/handoff_lint.py`'s existing logic. The 25% delta rule, exit codes, anchor list, and structural diff are out of scope.
- Do NOT bundle P2 work (banned-term enforcement, YAML threshold migration, hardcoded enums) into this commit unless the user explicitly approves.
- Do NOT pin a new top-level dependency without a one-line ADR under `docs/reference/`.
- Do NOT push or share the `LINEAR_API_KEY` value anywhere. If a live smoke runs, the token comes from env and never gets logged.
- Do NOT create accounts, modify org settings, or call destructive Linear endpoints (delete issue, archive project) — read/create/update only.
- Do NOT modify `schema.sql` without also updating `schema_postgres.sql` (Ceal CLAUDE.md rule #10).
- Do NOT trust this prompt blindly. Verify every state claim by reading the referenced file (Ceal CLAUDE.md rule #1: Read each file before editing it).

---

## How to start

1. Verify context and capture baseline tests (Tasks 1–2 above)
2. Read the docs listed under "Context" in the order given
3. Sketch the GraphQL query shapes for the Protocol's methods (Task 5)
4. **Pause and present the open-decisions list (HTTP client, auth, mocking, live smoke, scope) to the user.** Wait for confirmation before writing code.
5. After greenlight: implement adapter → tests → resolver wiring → SELF_REVIEW update → pre-commit review → commit (no push)

---

## Reference: file inventory for this work

| Path | Role |
|------|------|
| `CLAUDE.md` | Master prompt (root) — read first |
| `docs/ai-onboarding/PROJECT_CONTEXT.md` | Full project context |
| `docs/ai-onboarding/RULES.md` | Anti-hallucination rules |
| `docs/CEAL_PROJECT_LEDGER.md` | Project timeline, ADRs, tech debt register |
| `docs/planning/SELF_REVIEW.md` | Maven OS Week-One self-review (THIS prompt closes finding #2) |
| `tools/handoff_lint.py` | Linter — read for context, do NOT modify |
| `tools/tracker_adapter/__init__.py` | Protocol — read but do NOT modify |
| `tools/tracker_adapter/linear.py` | **You will create this** |
| `tests/unit/test_tracker_adapter_linear.py` | **You will create this** |
| `pilots/acme-corp/pilot_profile.yaml` | Declares `active_tracker: linear` |
| `.github/workflows/handoff-lint.yml` | CI gate — out of scope |

---

*Authored 2026-04-30 evening as the kickoff prompt for the next session. Maven OS Week-One self-review is at `docs/planning/SELF_REVIEW.md`. Ceal master prompt at repo root `CLAUDE.md`.*
