# TD-006 — PostgreSQL Schema Loader: Multi-Command SQL Through asyncpg

> **Severity:** HIGH
> **Opened:** 2026-04-16 (Sprint 11)
> **Days open at ticket creation:** 18
> **Activated:** 2026-05-04 as TD program item #1 (post sequence correction)
> **Branch:** `fix/td-006-postgres-schema-loader` (to be created in step 2)
> **Pre-flight tag:** `pre-td-006` (to be created in step 1)
> **Framework reference:** `docs/planning/TECH_DEBT_PROGRAM.md`
> **Kickoff prompt for fresh chat:** `docs/planning/TD_006_KICKOFF_PROMPT.md`

---

## Problem statement (from `docs/CEAL_PROJECT_LEDGER.md` Tech Debt Register)

> PostgreSQL DB Tests CI fails because the schema loader sends multi-command SQL blocks (including `DO $$ ... $$` / trigger setup) through asyncpg prepared statements.

The current `init_db()` flow at `src/models/database.py:140`:

1. Reads `schema_postgres.sql`
2. Splits into "statements" via `_split_sql_statements()` (lines ~264–323) — correctly keeps dollar-quoted blocks and trigger blocks together
3. Iterates and calls `await conn.execute(text(stmt))` (line ~166) for each block

The failure is at step 3: `asyncpg.exceptions.PostgresSyntaxError: cannot insert multiple commands into a prepared statement`. SQLAlchemy's `text()` execution path goes through asyncpg's *prepared statement* protocol, which rejects any payload containing multiple commands. The dollar-quoted blocks in `schema_postgres.sql` (function bodies, trigger function definitions) contain semicolons inside the body that asyncpg's prepare-path interprets as command separators — even though they are syntactically inside a `$$ ... $$` quote.

This breaks every test in `tests/integration/` against PostgreSQL because they all error at setup (`init_db()` fails before any test body runs). Confirmed reproduction in CI run `25333277478` on 2026-05-04.

The fix is at the **execution layer**, not the parsing layer.

## In scope

- Modify `init_db()` (or a helper it calls) so that PostgreSQL schema loading does not go through asyncpg's prepared statement path for multi-command blocks.
- Verify the fix against both backends — SQLite path must remain unchanged in behavior.
- Add a positive test asserting that a multi-command DDL block (e.g., `DO $$...$$` plus a `CREATE TRIGGER` on the same `init_db()` invocation) loads cleanly against PostgreSQL.

## Out of scope

- Modifying `schema_postgres.sql` itself to avoid multi-command blocks. (Workaround, not fix.)
- Changing the SQLite schema loader behavior. SQLite path is currently working.
- Rewriting `_split_sql_statements()`. The splitter's current behavior is correct.
- Migrating to Alembic for schema management (TD-003 territory).
- Any change to `schema.sql` unless dual-write is structurally required.
- Bundling TD-001 work into this commit.

## Files to read first (before scope decision)

- `src/models/database.py` — `init_db()` (lines ~140–172) and `_split_sql_statements()` (lines ~264–323)
- `src/models/schema_postgres.sql` — identify all multi-command blocks (DO $$, CREATE OR REPLACE FUNCTION ... $$, trigger function definitions)
- `src/models/schema.sql` — SQLite schema, for comparison
- `src/models/compat.py` — `is_sqlite()` branching
- `tests/integration/test_db_parity.py` — existing PostgreSQL parity tests (currently erroring at setup)
- `.github/workflows/ci.yml` — `db-tests-postgres` job definition (lines ~178–213)
- `docs/planning/TECH_DEBT_PROGRAM.md` — framework gates this ticket reports against
- (Reference) SQLAlchemy 2.0 async docs on `Connection.exec_driver_sql()`; asyncpg docs on simple vs prepared protocol

## Task 0 — CI state audit (mechanism D, performed in this ticket)

Captured 2026-05-04 ~17:43 UTC via `gh run list --limit 5` and `gh run view 25333277478 --json jobs`:

| Job | Latest status | Notes |
|---|---|---|
| Lint (ruff) | ✅ green | |
| Unit Tests (Python 3.11) | ✅ green | |
| Unit Tests (Python 3.12) | ✅ green | |
| Docker Build | ✅ green | |
| Integration Tests (Python 3.11) | ✅ green | SQLite |
| Integration Tests (Python 3.12) | ✅ green | SQLite |
| Coverage Check | ✅ green | |
| **DB Tests (PostgreSQL)** | ❌ **red** | Root cause: TD-006 (this ticket). Setup error: `asyncpg.exceptions.PostgresSyntaxError: cannot insert multiple commands into a prepared statement`. All ~28 integration tests show ERROR at setup; ~5 PDF tests (no DB) PASS. |

**Question (mechanism D):** Does this TD's test additions or code changes run in any currently-red job?
**Answer:** Yes — TD-006 *targets* the currently-red job. Closing this TD turns `db-tests-postgres` green. There are no other red jobs to consider.

**Unidentified red signals:** None. The only red job traces to this ticket.

**Re-verify at session start.** If the audit table above is more than 3 days old when this ticket starts, re-run `gh run list --limit 5` to confirm state has not changed. If `db-tests-postgres` has somehow gone green, that is itself a finding — investigate before code.

## Tasks

### Task 1 — Reproduce locally (no code changes yet)

Stand up PostgreSQL via docker-compose (or equivalent) and invoke `init_db()` against it directly (e.g., `python -c "import asyncio; from src.models.database import init_db; asyncio.run(init_db())"` with `DATABASE_URL` pointing at the local Postgres). Capture:

- The exact stack trace
- Which "statement" emitted by `_split_sql_statements()` triggers the error (add a debug print inside the iteration loop temporarily; revert before commit)

Confirm the stack trace matches the CI failure. If it doesn't, the local repro is wrong — fix the local environment before proceeding.

### Task 2 — Identify the multi-command blocks in `schema_postgres.sql`

List every block that produces a multi-command payload after `_split_sql_statements()`. Most likely candidates:

- `DO $$ DECLARE ... BEGIN ... END $$;` blocks
- `CREATE OR REPLACE FUNCTION ... AS $$ ... $$ LANGUAGE plpgsql;`
- The `applications.updated_at` trigger function (referenced in `docs/sprints/sprint8-crm-autoapply.md`)

Output: numbered list of line ranges in `schema_postgres.sql` mapped to the resulting "statement" string the splitter emits. This becomes part of the session note's audit trail.

### Task 3 — Pause for fix-path decision

Three candidate fix paths. Present to operator and confirm before code:

- **Path A — `exec_driver_sql()`:** SQLAlchemy 2.0's `connection.exec_driver_sql(sql)` bypasses prepared statements and sends the raw string to the driver's simple query protocol. Drop-in replacement at the iteration call site for the PostgreSQL branch. Smallest diff.
- **Path B — Raw asyncpg `connection.execute()`:** Drop to the asyncpg layer via `engine.raw_connection()` or `Connection.driver_connection` and call `await asyncpg_conn.execute(sql)`. Simple query protocol, multi-command safe. More code.
- **Path C — Per-statement protocol switching:** Detect multi-command blocks (e.g., contains `$$`) inside the loader and switch protocol just for those blocks; use prepare for single-statement DDL. Most surgical, most code, most edge-case risk.

**Recommended: Path A.** Smallest diff, idiomatic SQLAlchemy 2.0, isolates the change to the PostgreSQL branch in `init_db()`. Operator confirms before code.

### Task 4 — Implement chosen fix path

For Path A: change line 166 of `src/models/database.py` from `await conn.execute(text(stmt))` to `await conn.exec_driver_sql(stmt)`. Keep the SQLite branch (line 160) literally unchanged. Add a brief comment explaining why the PostgreSQL branch uses `exec_driver_sql` (multi-command DDL safety; reference TD-006).

If `text` is no longer used in the PostgreSQL branch but is still used elsewhere in the file, leave the import alone. Verify with grep before removing any import.

### Task 5 — Add positive smoke test

Create `tests/integration/test_init_db_multi_command_ddl.py` (recommended scope per the kickoff prompt's open-decisions). Assert: after `init_db()` runs against PostgreSQL, the database state reflects the dollar-quoted blocks (e.g., the trigger function exists in `pg_proc`, the trigger is registered in `pg_trigger`).

Pre-fix run captures the failure (ERROR at setup). Post-fix run captures the pass. Both go to `docs/smoke_logs/td_006_<YYYYMMDD>.md` with annotations. This is the **positive smoke** for TD-006.

### Task 6 — Verify regression gate

- `pytest tests/ -q` against SQLite → full suite green (no regression)
- Local `pytest tests/integration/ -q` against PostgreSQL via docker-compose → full suite green
- `ruff check src/ tests/` clean
- Test count delta recorded (355 → 355 + N where N includes the new smoke test)

### Task 7 — Update ledger + Cross-TD Dependencies table

In a single commit:

- `docs/CEAL_PROJECT_LEDGER.md` Tech Debt Register: mark TD-006 [RESOLVED YYYY-MM-DD &lt;commit-sha&gt;]; append timeline entry
- `docs/planning/TECH_DEBT_PROGRAM.md` Cross-TD Dependencies table: TD-001 and TD-003 no longer have `db-tests-postgres` as a blocking job
- `docs/planning/TECH_DEBT_PROGRAM.md` Per-TD ticket index: TD-001 status updated to "queued — operator to confirm scope on Task 2"; TD-006 status updated to "[RESOLVED YYYY-MM-DD]"
- `docs/planning/td_001_route_integration_tests.md` STATUS header: remove the DEFERRED block (resume condition met). Per Task 7's "single-commit-per-TD-closure" recommendation, do this in the same commit.

If a new pattern emerges (e.g., "PostgreSQL DDL execution uses simple query protocol"), add an ADR under `docs/reference/`. Otherwise no Decision Log entry needed.

### Task 8 — Session note

Create `docs/session_notes/YYYY-MM-DD_td_006_postgres_schema_loader.md` per `docs/ai-onboarding/DEBRIEF_TEMPLATE.md`. Sections:

- Objective + scope confirmed in Task 3
- Multi-command block inventory (Task 2 output)
- Fix path chosen and why
- Files changed
- Smoke log path
- Test count delta
- X-Y-Z career bullet
- Limitations: what wasn't covered, what's at risk if Path A's underlying assumption (asyncpg simple-query protocol handles all schema constructs) turns out to be false in some corner of `schema_postgres.sql`

### Task 9 — Commit (no push without operator approval)

Single commit on `fix/td-006-postgres-schema-loader`. Body includes:

- **Limitations** sub-section
- **Walk-the-merge actual** line confirming what `gh run list --limit 1` shows after the commit pushes (filled in post-push, before merge)

### Task 10 — Merge + verify against projection

Merge `fix/td-006-postgres-schema-loader` to main. Run `gh run list --limit 1` and `gh run view <new-run-id> --json jobs --jq '.jobs[] | {name, conclusion}'` after CI completes. Verify against the walk-the-merge projection below:

- `db-tests-postgres` job: ❌ red → ✅ green ✓
- All other 7 jobs: still ✅ green ✓

If reality diverges from projection, hard-reset main to `pre-td-006` (operator approval required) and re-derive the fix path.

## Walk-the-merge projection (mechanism E, performed in this ticket)

**Projected CI state immediately after TD-006 merges to main:**

| Job | Pre-merge | Projected post-merge |
|---|---|---|
| Lint (ruff) | ✅ | ✅ |
| Unit Tests (Python 3.11) | ✅ | ✅ |
| Unit Tests (Python 3.12) | ✅ | ✅ |
| Docker Build | ✅ | ✅ |
| Integration Tests (Python 3.11) | ✅ | ✅ |
| Integration Tests (Python 3.12) | ✅ | ✅ |
| Coverage Check | ✅ | ✅ (single test addition does not threaten 80% floor) |
| **DB Tests (PostgreSQL)** | ❌ | ✅ (this is the fix's success signal) |

**Test count projection:** 355 baseline → 356+ (one new smoke test minimum).

**`git status` projected:** clean. No uncommitted artifacts; smoke log committed alongside source change. `data/resume.txt` deferred state preserved (do not include in this commit).

**Failure mode to watch:** if `db-tests-postgres` stays red post-merge, the fix didn't address the actual root cause. Hard-reset to `pre-td-006`, re-investigate. Possible alternative root causes if Path A doesn't work:

- A schema construct that's broken in *both* prepare and simple-query modes (would indicate a bug in `_split_sql_statements()` after all)
- A postgres version mismatch between local and CI (CI uses `postgres:16-alpine` per `ci.yml:186`)
- A connection-pool / DDL-in-transaction issue that exec_driver_sql doesn't solve

If any of these surface, log as a sub-finding, do not bundle a second fix into the same commit, and refine the ticket.

## Acceptance criteria

- [ ] `pre-td-006` tag exists on main pre-execution
- [ ] All work on `fix/td-006-postgres-schema-loader` branch
- [ ] Reproduction of failure captured in Task 1 before any fix
- [ ] Multi-command block inventory exists (Task 2)
- [ ] Fix-path decision logged (Task 3) with operator confirmation
- [ ] Fix landed (Task 4) — minimal diff, isolates PostgreSQL branch, SQLite branch literally unchanged
- [ ] Positive smoke test exists (`tests/integration/test_init_db_multi_command_ddl.py` or equivalent) and pre-fix-vs-post-fix captured in `docs/smoke_logs/td_006_<date>.md`
- [ ] Full suite green on SQLite (no regression)
- [ ] Full suite green on PostgreSQL locally (the actual fix)
- [ ] TD-006 marked [RESOLVED] in register; Cross-TD Dependencies table updated; TD-001 STATUS deferral removed
- [ ] Session note exists
- [ ] Branch merged to main; CI matches walk-the-merge projection (`db-tests-postgres` ✅ green)
- [ ] `pre-td-006` tag still resolves post-merge (rollback path verified by inspection)

## Rollback procedure

**Pre-merge:** `git reset --hard pre-td-006` on the feature branch. No operator approval needed — branch is private to the work.

**Post-merge with CI red beyond projection:** Pause. Capture the failure log. `git reset --hard pre-td-006` on main only after operator approval. Force-push main only with explicit authorization.

**Post-merge with CI green but smoke regresses later:** `git revert <merge-commit>` on a new branch; PR the revert. Investigate root cause before re-attempting.

## Notes

- This is the first TD to exercise mechanisms D (Task 0 CI audit) and E (walk-the-merge projection) end-to-end. If either mechanism feels awkward in execution, flag in the session note for framework refinement.
- TD-006 is more delicate than TD-001 would have been because it touches `init_db()` — a startup path used by every test fixture and by `python -m src.main`. The risk model: if the fix breaks SQLite, every subsequent commit becomes harder. The SQLite path must remain literally unchanged at the line level.
- Do NOT attempt to "improve" `_split_sql_statements()` in this commit. The splitter's current behavior is correct; the bug is at the execution layer, not the parsing layer. Per `CLAUDE.md` rule #5: keep diffs minimal and local to the task.
- If the docker-compose Postgres setup doesn't already exist in the repo, add the minimum stub needed for local reproduction (Task 1) and call it out in the session note's Limitations.
- TD-001's STATUS header resume condition is met the moment TD-006 closes. The ticket's Task 7 includes removing that header so the deferral does not survive past the closure of its blocker.
