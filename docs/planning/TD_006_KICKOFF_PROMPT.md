# TD-006 Kickoff Prompt — PostgreSQL Schema Loader Multi-Command Fix

> **Paste this entire document as the first message in a fresh chat.** The new Claude instance has zero prior conversation history; this prompt is authoritative. Verify every claim by reading the files listed before writing any code.

---

## Context — read these first

You are working on the **Ceal** project. The Career-pipeline track is ACTIVE, scoped to the Tech Debt Program. **TD-006** is the current in-flight item — the sequence was corrected on 2026-05-04 to put it ahead of TD-001 because TD-001's tests would have inherited TD-006's CI failure. Fixing TD-006 turns the long-standing red `db-tests-postgres` CI job green and unblocks every subsequent TD from shipping with green CI.

- **Project root:** `C:\Users\joshb\Documents\Claude\Projects\Ceal\ceal`
- **GitHub:** https://github.com/joshuahillard/ceal
- **Owner:** Josh Hillard (Boston, MA)
- **Phase at prompt creation:** Tech Debt Program activated 2026-05-04; this is its first execution session.

**Read these in order before any code:**

1. `CLAUDE.md` (repo root) — Core Contract, Mode Packs, Task Format. **Mode Pack `db` applies directly to this work.**
2. `docs/ai-onboarding/PROJECT_CONTEXT.md` — full project context (post-Sprint 11 + Maven OS Week-One).
3. `docs/ai-onboarding/RULES.md` — anti-hallucination engineering rules. Rule #1 (read before edit) and rule #5 (keep diffs minimal) are load-bearing here.
4. `docs/CEAL_PROJECT_LEDGER.md` — recent timeline (the two 2026-05-04 entries) and Tech Debt Register.
5. `docs/planning/TECH_DEBT_PROGRAM.md` — **most important framework doc.** The 10-step per-TD framework, the five mechanisms (A–E), Cross-TD Dependencies table, and the Lessons section recording the 2026-05-04 sequence reversal that made this ticket the first executed item.
6. `docs/planning/td_006_postgres_schema_loader.md` — **this ticket.** Tasks 0–10, walk-the-merge projection, acceptance criteria. **Source of truth for tasks; this prompt is the cold-start wrapper.**
7. `docs/planning/sprint_review_20260504.md` — sprint review providing the program's context.
8. `src/models/database.py` (especially `init_db()` at lines ~140–172 and `_split_sql_statements()` at lines ~264–323) — the code being fixed.
9. `src/models/schema_postgres.sql` — the schema file whose multi-command blocks trigger the failure.
10. `.github/workflows/ci.yml` (`db-tests-postgres` job at lines ~178–213) — the CI gate that must turn green.

---

## What's been done thus far

### Through 2026-04-30 — main project state

- Phase 1 + Sprints 1–11 + Maven OS Week-One Miniature complete.
- Test count: 355 local SQLite suite (verified 2026-04-30).
- PostgreSQL CI red since at least 2026-04-08 — this is TD-006.

### 2026-05-04 — Tech Debt Program activation and same-day correction

- **Sprint review** for window 2026-04-27 → 2026-05-04 captured at `docs/planning/sprint_review_20260504.md`. Identified parallel-track drift and the TD-001 30-day RED threshold crossing.
- **Maven OS Week-Two** retroactively marked as a single-session ticket; **Week-Three** authored then immediately DEFERRED via STATUS header until TD-006 and TD-001 close.
- **Tech Debt Program activated** at `docs/planning/TECH_DEBT_PROGRAM.md` (commit `f79099c`).
- **Same-day sequence correction** (commit `fce7090`): operator caught a CI dependency miss within hours. Original sequence (TD-001 first) reversed to **TD-006 → TD-001 → TD-003 → TD-002 → TD-005**. Five new pre-execution mechanisms (A–E) inscribed in the framework so the same shape of oversight cannot recur.
- **TD-006 ticket** scoped at `docs/planning/td_006_postgres_schema_loader.md` with mechanism D (Task 0 CI audit) and mechanism E (walk-the-merge projection) populated as of 2026-05-04. **This session is the first to exercise those mechanisms end-to-end on a real TD.**

### Outstanding hygiene items (NOT blocking this ticket but worth knowing)

- `data/resume.txt` modified in working tree, uncommitted, unrelated to either track. Disposition deferred. Verify with operator if its state has changed by the time this session opens.
- No session note exists for the 2026-04-30 Maven OS work. Out of scope for this ticket; flag if you have time.

---

## What needs to change

`init_db()` in `src/models/database.py` iterates over schema statements and calls `await conn.execute(text(stmt))` for the PostgreSQL backend (line ~166). SQLAlchemy's `text()` execution path goes through asyncpg's *prepared statement* protocol, which rejects payloads containing multiple commands — even when those commands are inside a `$$ ... $$` dollar-quoted body. Result: `asyncpg.exceptions.PostgresSyntaxError: cannot insert multiple commands into a prepared statement` at every test setup against PostgreSQL.

The fix is at the **execution layer**, not the parsing layer. The splitter (`_split_sql_statements()`) correctly keeps dollar-quoted blocks together. The execution call must use a non-prepared protocol path. Three candidate fix paths laid out in the ticket's Task 3.

---

## Goal for this session

Close TD-006: turn `db-tests-postgres` from red to green via a minimal-diff fix to `init_db()` for the PostgreSQL branch only. SQLite path must remain literally unchanged at the line level. Ship with a positive smoke test, ledger update, Cross-TD Dependencies table update, TD-001 deferral header removal, session note, and CI matching the walk-the-merge projection in the ticket.

---

## Open decisions — confirm with the user before writing code

The TD-006 ticket's Task 3 has the full decision text for the fix path. Pause and present these five to the operator before any code:

1. **Fix path:** Path A (`exec_driver_sql()`), Path B (raw asyncpg via `driver_connection`), or Path C (per-statement protocol switching). **Recommended: Path A** — smallest diff, idiomatic SQLAlchemy 2.0. Confirm or override.
2. **Local PostgreSQL setup:** does Josh have a working local docker-compose Postgres or equivalent? If not, this session adds the minimum stub for Task 1 reproduction. Confirm.
3. **Smoke test location:** new file `tests/integration/test_init_db_multi_command_ddl.py`, or extend `tests/integration/test_db_parity.py`? **Recommended: new file** (clearer scope, easier to find). Confirm.
4. **TD-001 STATUS removal timing:** when TD-006 closes, does the TD-001 deferral header come off in the same commit, the next commit, or a separate small commit? **Recommended: same commit** (single round-trip per TD closure). Confirm.
5. **`data/resume.txt` working-tree state:** confirm it's still modified-but-deferred, or if its disposition has changed.

---

## Tasks (after open decisions are settled)

The ticket file (`docs/planning/td_006_postgres_schema_loader.md`) is the source of truth. Brief outline mapping ticket tasks to the framework's 10 steps:

| Framework step | Ticket task | Summary |
|---|---|---|
| 0 (mechanism D) | (already in ticket) | CI audit complete in ticket. Re-verify still-current at session start. |
| 1 | Pre-flight tag + Task 1 | `git tag pre-td-006`; reproduce locally |
| 2 | Branch | `git checkout -b fix/td-006-postgres-schema-loader` |
| 3 | Baseline | Test count + lint + git SHA recorded in session note |
| 4 (mechanism E) | Tasks 2 & 3 | Multi-command block inventory + fix-path decision pause |
| 5 | Task 4 | Implement chosen fix path |
| 6 | Tasks 5 & 6 | Positive smoke test + full regression gate (SQLite AND Postgres locally) |
| 7 | Task 7 | Ledger + Cross-TD Dependencies table update + TD-001 deferral removal |
| 8 | Task 8 | Session note |
| 9 | Task 9 | Commit (no push without approval) |
| 10 | Task 10 | Merge + verify against projection |

---

## Acceptance criteria

See `docs/planning/td_006_postgres_schema_loader.md` § "Acceptance criteria" for the full checklist. Every box must check before push approval is requested.

The single most important check: **`db-tests-postgres` goes from red to green on the merge commit.** If it doesn't, the fix didn't work; rollback per the ticket's procedure.

---

## What you should NOT do

- Do NOT modify `_split_sql_statements()`. The splitter is correct; the bug is at execution.
- Do NOT modify `schema_postgres.sql` to avoid multi-command blocks. That's a workaround, not a fix.
- Do NOT modify the SQLite branch of `init_db()` (line ~160). It currently works; do not regress it. Diff the function before and after — the SQLite line should be byte-identical.
- Do NOT migrate to Alembic. That's TD-003.
- Do NOT bundle TD-001 or any other TD's work into this commit. Single-TD commit.
- Do NOT pin a new top-level dependency without an ADR under `docs/reference/`.
- Do NOT push until operator gives explicit `PUSH` approval — and only after the merge-and-verify step in the ticket completes successfully.
- Do NOT silently include `data/resume.txt` in the commit. Disposition is deferred per operator decision; if it's still in the working tree at session start, leave it alone or confirm intent.
- Do NOT trust this prompt blindly. Verify every claim by reading the referenced file (CLAUDE.md rule #1). The ticket's Task 0 CI audit data was current as of 2026-05-04; if more than ~3 days have passed, re-run `gh run list --limit 5` to confirm the audit is still accurate.

---

## How to start

1. **Verify context:** `pwd` (must end in `Ceal\ceal`), `git remote -v` (must point at `joshuahillard/ceal`), `git log --oneline -5`, `git status`. If anything surprises you, stop and ask.
2. **Re-run CI audit** (`gh run list --limit 5`) to confirm state still matches the ticket's Task 0 audit. If `db-tests-postgres` has gone green in the interim, that's a finding — investigate before any code.
3. **Read the docs** listed under "Context" in order.
4. **Pause and present the open-decisions list (1–5) to the operator.** Wait for confirmation on each before writing code.
5. **After greenlight:** pre-flight tag → reproduce locally → branch → baseline → walk-the-merge projection re-confirmed → fix path implemented → smoke test → regression gate → ledger + Cross-TD Dependencies update + TD-001 deferral removal → session note → commit → merge + verify.

---

## Reference: file inventory for this work

| Path | Role |
|------|------|
| `CLAUDE.md` | Master prompt — read first |
| `docs/ai-onboarding/PROJECT_CONTEXT.md` | Full project context |
| `docs/ai-onboarding/RULES.md` | Anti-hallucination rules |
| `docs/ai-onboarding/DEBRIEF_TEMPLATE.md` | Session note template |
| `docs/CEAL_PROJECT_LEDGER.md` | Tech Debt Register, timeline, Decision Log — will be updated |
| `docs/planning/TECH_DEBT_PROGRAM.md` | Framework + Cross-TD Dependencies table — will be updated post-fix |
| `docs/planning/td_006_postgres_schema_loader.md` | **This session's ticket** — source of truth for tasks |
| `docs/planning/td_001_route_integration_tests.md` | Will have its DEFERRED STATUS removed once TD-006 closes (Task 7) |
| `docs/planning/sprint_review_20260504.md` | Sprint review — read for context |
| `src/models/database.py` | **Will be modified** — `init_db()` line ~166 only |
| `src/models/schema_postgres.sql` | Read; do not modify |
| `src/models/schema.sql` | Read; do not modify |
| `src/models/compat.py` | Read for `is_sqlite()` semantics; do not modify |
| `tests/integration/test_db_parity.py` | Read for test pattern |
| `tests/integration/test_init_db_multi_command_ddl.py` | **You may create this** — new positive smoke test (per open-decision #3) |
| `docs/smoke_logs/td_006_<YYYYMMDD>.md` | **You will create this** — pre-fix-vs-post-fix capture |
| `docs/session_notes/<YYYY-MM-DD>_td_006_postgres_schema_loader.md` | **You will create this** |
| `.github/workflows/ci.yml` | Read for `db-tests-postgres` definition; out of scope to modify |
| `docker-compose.yml` (or `docker-compose.test.yml` if present) | Read for local Postgres setup; possibly add minimal stub per open-decision #2 |

---

*Authored 2026-05-04 as the kickoff prompt for the TD-006 session. Ticket at `docs/planning/td_006_postgres_schema_loader.md`. Framework at `docs/planning/TECH_DEBT_PROGRAM.md`.*
