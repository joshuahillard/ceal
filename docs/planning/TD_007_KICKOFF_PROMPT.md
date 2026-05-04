# TD-007 Kickoff Prompt — PostgreSQL Datetime ISO Strings Rejected by asyncpg

Paste this entire document as the first message in a fresh chat. The new Claude instance has zero prior conversation history; this prompt is authoritative. Verify every claim by reading the files listed before writing any code.

---

## Context — read these first

You are working on the Ceal project. The Career-pipeline track is ACTIVE, scoped to the Tech Debt Program. **TD-007 is the current in-flight item.** It was authored 2026-05-04 during TD-006's closure as one of three masked bugs that surfaced once TD-006's schema-loader fix removed the foundational mask. TD-007 is now the highest-impact remaining gate on full PostgreSQL CI parity (~16 tests across 4 files).

**Project root:** `C:\Users\joshb\Documents\Claude\Projects\Ceal\ceal`
**GitHub:** `https://github.com/joshuahillard/ceal`
**Owner:** Josh Hillard (Boston, MA)
**Phase at prompt creation:** Tech Debt Program post-TD-006 closure (2026-05-04). Sequence: TD-006 ✅ → **TD-007 (this ticket)** → TD-008 → TD-009 → TD-001 → TD-003 → TD-002 → TD-005.

Read these in order before any code:

- `CLAUDE.md` (repo root) — Core Contract, Mode Packs, Task Format. Mode Pack `db` applies directly to this work.
- `docs/ai-onboarding/PROJECT_CONTEXT.md` — full project context (post-Sprint 11 + Maven OS Week-One + TD-006 closure).
- `docs/ai-onboarding/RULES.md` — anti-hallucination engineering rules. Rule #1 (read before edit), rule #5 (keep diffs minimal), rule #9 (never fabricate symbols) are load-bearing here.
- `docs/CEAL_PROJECT_LEDGER.md` — recent timeline (the 2026-05-04 entries through TD-006 closure) and the Tech Debt Register (TD-007 is queued).
- `docs/planning/TECH_DEBT_PROGRAM.md` — most important framework doc. The 10-step per-TD framework, the **six mechanisms (A–F — Mechanism F is new and load-bearing for this ticket)**, Cross-TD Dependencies table (now naming TD-007/008/009 with their relations), and the Lessons section recording the *masked-bugs cascade* discovery from 2026-05-04.
- `docs/planning/td_007_postgres_datetime_strings.md` — this ticket. Source of truth for tasks; this prompt is the cold-start wrapper.
- `docs/session_notes/2026-05-04_td_006_postgres_schema_loader.md` — the TD-006 closure notes. Includes the "Masked-bugs cascade" section that named TD-007 and the discovery context.
- `docs/smoke_logs/td_006_20260504.md` — TD-006 pre-fix-vs-post-fix smoke. Has sample stack traces of the TD-007 failure mode.
- `src/models/database.py` — likely site of the bug. Upsert paths, `update_*_status` flows, and any function that writes timestamps. Grep for `to_char`, `isoformat`, `strftime`, `NOW()` in raw SQL.
- `src/models/entities.py` — Pydantic v2 boundary models. Look for `Field(default_factory=...)` on datetime fields, custom serializers, and `model_dump(mode='json')` patterns that may emit ISO strings before they hit the DB layer.
- `src/models/schema_postgres.sql` — the columns that asyncpg is rejecting strings for. Identify which columns are `TIMESTAMP`/`TIMESTAMPTZ`/`DATE` (typed) vs `TEXT` (string-storage). Pre-existing convention: some columns are TEXT-stored (e.g., `created_at` in `application_fields` is `TEXT NOT NULL DEFAULT to_char(NOW() AT TIME ZONE 'UTC', ...)`) — those are NOT the failure surface.
- `tests/integration/test_persistence_roundtrip.py`, `test_db_parity.py`, `test_crm_autoapply_roundtrip.py`, `test_regime_classification_roundtrip.py` — the four files carrying `pytest.mark.postgres_skip_td("TD-007: ...")` (the regime file has `TD-007 + TD-009`).
- `tests/integration/conftest.py` — registers the `postgres_skip_td` marker. Removing markers as TD-007 closes is part of acceptance.
- `.github/workflows/ci.yml` — `db-tests-postgres` job (lines ~178–213). The success signal.

## What's been done thus far

### TD-006 closure (2026-05-04, commit `03fe3eb`)

- Schema loader fix: `init_db()` PostgreSQL branch uses `exec_driver_sql()`. SQLite branch unchanged.
- Splitter fix: `_split_sql_statements()` now guards `in_trigger = True` with `not in_dollar_quote`.
- Conftest CASCADE fix: `drop_all_tables()` adds `CASCADE` for Postgres (was a masked bug inseparable from TD-006 verification).
- Smoke tests added: `tests/integration/test_init_db_multi_command_ddl.py` (3 PG-only tests), `tests/unit/test_split_sql_statements.py` (4 unit tests).
- Test count: 355 → 359 SQLite (+4 splitter unit tests).
- CI: 8/8 jobs green on `03fe3eb`. `db-tests-postgres` ✅ for the first time since 2026-04-08.

### Masked-bugs cascade — TD-007/008/009 authored same-session

When TD-006 was reproduced locally, three more pre-existing PostgreSQL-incompatible patterns surfaced. They were authored as their own tickets and gated in tests via `pytest.mark.postgres_skip_td(reason)` (registered in `tests/integration/conftest.py`).

- **TD-007 (this ticket)** — datetime ISO strings rejected by asyncpg on typed columns. ~16 tests across 4 files.
- TD-008 — `round(double precision, integer)` not supported on Postgres. 4 pipeline tests.
- TD-009 — SERIAL sequence not advanced after explicit-id fixture INSERTs. Regime fixture; audit pending.

### Framework additions (live as of TD-006 closure)

- **Mechanism F — Post-foundational-fix unmasking pass.** Per-TD ticket must, after a foundational fix, re-run the affected job locally and audit every newly-surfaced failure. Each new failure gets categorized as (i) caused by this TD's change → fix in scope, or (ii) pre-existing/masked → carve out via marker + new TD ticket.
- **`pytest.mark.postgres_skip_td(reason)` marker convention.** Greppable: `grep -rn postgres_skip_td tests/` enumerates outstanding masked-bug debt. Marker is removed when its TD closes.
- **Same-session ticket authoring rule.** Follow-up tickets (if any) are authored in the same commit as the foundational fix while context is sharpest.

## What needs to change

Application code emits ISO-8601 datetime strings (e.g., `"2026-05-04T18:49:43Z"`) and passes them as parameters to PostgreSQL queries with typed `TIMESTAMP` / `TIMESTAMPTZ` / `DATE` columns. SQLite silently coerces strings; PostgreSQL+asyncpg rejects at the driver layer:

```
asyncpg.exceptions.DataError: invalid input for query argument $4:
'2026-05-04T18:49:43Z' (expected a datetime.date or datetime.datetime instance, got 'str')
```

Pre-TD-006 this was masked because `init_db()` never reached application code. Post-TD-006 every code path emitting ISO strings to typed columns fails on Postgres.

The fix is at the **boundary between application code and the DB layer.** Three candidate paths (Task 3 will pause to choose):

- **Path A — Pass datetime objects.** Audit every site emitting `to_char(...)` / `isoformat()` / `.strftime(...)` for DB insertion. Replace with `datetime` objects. Most idiomatic. Largest surface to audit.
- **Path B — SQL CAST in parameter bindings.** Wrap each problematic parameter as `CAST(:param AS TIMESTAMP)` so asyncpg accepts the string. Smaller per-site diff. Uglier SQL.
- **Path C — Custom SQLAlchemy TypeDecorator.** Centralized at the type level — every model field of type `DateTime` accepts string input and converts on bind. Smallest diff at call sites; bigger architectural change.

**Important nuance:** some columns *are* TEXT-typed by design (e.g., `application_fields.created_at` is `TEXT NOT NULL DEFAULT to_char(NOW() ...)`). The schema explicitly stores those as strings. Do NOT touch their write paths — they're correct as-is. Identify the typed-vs-text distinction in `schema_postgres.sql` before deciding scope.

## Goal for this session

Close TD-007: turn the 16+ datetime-string-rejection tests from `postgres_skip_td("TD-007: ...")` to passing on the merge commit. Remove TD-007 references from all `postgres_skip_td` reasons (the regime file's marker stays, with reason narrowed to TD-009 only). Ship with smoke log, ledger update, Cross-TD Dependencies table update, session note, and CI matching the walk-the-merge projection in the ticket.

## Open decisions — confirm with the user before writing code

The TD-007 ticket's Task 3 has the full decision text. Pause and present these to the operator before any code:

1. **Fix path:** Path A (datetime objects), Path B (SQL CAST), or Path C (TypeDecorator). Recommended in the ticket: TBD pending Task 1's audit. Hold the recommendation until you've grepped the actual emission sites — the volume of call sites determines whether A is feasible vs whether C is justified.
2. **Local Postgres setup:** the dev machine had a native Postgres on `localhost:5432` that won the connection race during TD-006 (cause unknown). Workaround: `docker run --rm -d --name ceal-td007-repro -p 5433:5432 -e POSTGRES_DB=ceal -e POSTGRES_USER=ceal -e POSTGRES_PASSWORD=ceal_dev_only postgres:16-alpine`. Confirm the same workaround applies — or operator stops the native instance.
3. **Marker removal granularity.** Four files carry the TD-007 marker; one (`test_regime_classification_roundtrip.py`) has a combined TD-007+TD-009 reason. When TD-007 closes:
   - Remove markers entirely from the three TD-007-only files (`test_persistence_roundtrip.py`, `test_db_parity.py`, `test_crm_autoapply_roundtrip.py`).
   - Narrow the regime file's marker reason to TD-009 only.
   Confirm this granularity is correct, or whether some tests in the TD-007 files are TD-009-blocked too (audit may surface this).
4. **Scope boundary on TD-008/TD-009.** If during the audit you find a code path that's broken by *both* TD-007 (datetime) and TD-008 (round-cast) at the same call site, fix only the TD-007 part — leave TD-008 to its own ticket. If a single fix would close all three at once (unlikely but possible), pause and surface to operator before expanding scope.
5. **Mechanism F unmasking pass.** Once your fix lands and you remove the markers, re-run `pytest tests/integration/ -q` against Postgres locally. Audit any *newly* surfaced failure. If anything appears that wasn't in TD-007/008/009's known list, treat it as a fresh masked-bug discovery (author TD-010, gate with marker, document). The framework expects this; it's not a regression.

## Tasks (after open decisions are settled)

The ticket file (`docs/planning/td_007_postgres_datetime_strings.md`) is the source of truth. Brief outline mapping ticket tasks to the framework's 10 steps:

| Framework step | Ticket task | Summary |
|---|---|---|
| 0 (mechanism D) | Task 0 | CI audit: `gh run list --limit 5`. Confirm `db-tests-postgres` is currently green (after TD-006). Re-affirm `postgres_skip_td("TD-007: ...")` markers are still the gate. |
| 1 | Task 1 (pre-flight) | `git tag pre-td-007` on main; reproduce locally. |
| 2 | Task 2 | `git checkout -b fix/td-007-postgres-datetime-strings`. |
| 3 | Task 3 (baseline) | Test count + lint + git SHA recorded in session note. Note: SQLite count after TD-006 is 359; Postgres `tests/integration/` is 9 passed, 29 skipped. |
| 4 (mechanism E) | Task 4 (audit + decision pause) | Grep audit of every datetime emission site in `src/`. Build a table mapping each site to its column type and current emission form. Pause for fix-path decision (Path A/B/C). |
| 5 | Task 5 | Implement chosen fix path. |
| 6 (mechanism F) | Task 6 (unmasking) | Re-run Postgres suite locally with TD-007 markers removed (file by file). Catalogue every newly-surfaced failure. |
| 6 cont. | Task 7 (smoke) | Positive smoke: a previously-failing assertion now passes against Postgres. Capture pre-fix-vs-post-fix in `docs/smoke_logs/td_007_<YYYYMMDD>.md`. |
| 6 cont. | Task 8 (regression gate) | SQLite full suite + Postgres full suite + ruff. Test count delta recorded. |
| 7 | Task 9 (ledger) | `docs/CEAL_PROJECT_LEDGER.md` Tech Debt Register: TD-007 [RESOLVED YYYY-MM-DD]; append timeline entry. `docs/planning/TECH_DEBT_PROGRAM.md` Cross-TD Dependencies table: drop TD-007's row, update TD-001/TD-003 "must close first" to drop TD-007. Per-TD ticket index updates. |
| 8 | Task 10 (session note) | `docs/session_notes/<YYYY-MM-DD>_td_007_postgres_datetime_strings.md` — required. Limitations section calls out anything Mechanism F surfaced that was deferred. |
| 9 | Task 11 (commit) | Single commit on `fix/td-007-postgres-datetime-strings`. Body includes Limitations + walk-the-merge projection + walk-the-merge actual placeholder. |
| 10 | Task 12 (merge + verify) | Merge to main, delete branch, verify CI green and that the test count for `db-tests-postgres` improved by ≥16. |

## Acceptance criteria

See `docs/planning/td_007_postgres_datetime_strings.md` § "Acceptance criteria" for the full checklist. The decisive ones:

- All `postgres_skip_td` markers referencing TD-007 removed (or narrowed to non-TD-007 reasons where appropriate).
- The 16+ previously-failing tests on Postgres now pass.
- SQLite suite test count and pass/fail unchanged (no regression).
- `db-tests-postgres` CI job remains ✅ green (with the unmasked tests now actually running and passing).
- `pre-td-007` tag still resolves post-merge (rollback path).

## What you should NOT do

- Do NOT modify `_split_sql_statements()` or `init_db()` PostgreSQL execution path — those are TD-006 territory. The exec_driver_sql + splitter guard are correct as-shipped.
- Do NOT modify `schema_postgres.sql` to widen typed columns to TEXT. That's a workaround, not a fix.
- Do NOT modify SQLite test fixtures or app code paths in ways that change SQLite behavior. SQLite must keep working byte-identically.
- Do NOT bundle TD-008 (round-cast) or TD-009 (SERIAL fixtures) work into TD-007's commit. Single-TD commit, even if you discover a same-line fix.
- Do NOT pin a new top-level dependency without an ADR under `docs/reference/`.
- Do NOT push until operator gives explicit PUSH approval — and only after the merge-and-verify step in the ticket completes successfully.
- Do NOT silently include `data/resume.txt` in the commit. Disposition is deferred per operator decision.
- Do NOT trust this prompt blindly. Verify every claim by reading the referenced file (`CLAUDE.md` rule #1). The TD-006 closure data was current as of 2026-05-04; if more than ~3 days have passed, re-run `gh run list --limit 5` to confirm CI state has not changed.
- Do NOT skip Mechanism F. After your fix lands and markers are removed, the unmasking pass is mandatory. The framework's most expensive lesson lives there.

## How to start

1. Verify context: `pwd` (must end in `Ceal\ceal`), `git remote -v` (must point at `joshuahillard/ceal`), `git log --oneline -5`, `git status`. The most recent commit on main should be `03fe3eb` (TD-006 closure). If anything surprises you, stop and ask.
2. Re-run CI audit (`gh run list --limit 5`). Expected: most recent run on main is green (TD-006 closure verified). If `db-tests-postgres` has regressed, that's a finding — investigate before any code.
3. Read the docs listed under "Context" in order. Pay close attention to the Mechanism F definition in `TECH_DEBT_PROGRAM.md` — it's new since the framework's first version and you'll execute it in Task 6.
4. Pause and present the open-decisions list (1–5) to the operator. Decision 1 (fix path) needs Task 1's audit before a recommendation; the others can be confirmed up front.
5. After greenlight: pre-flight tag → branch → baseline → audit (Task 1) → fix-path decision pause → implement → unmasking pass (Mechanism F) → smoke → regression gate → ledger + Cross-TD update → session note → commit → merge + verify.

## Reference: file inventory for this work

| Path | Role |
|---|---|
| `CLAUDE.md` | Master prompt — read first |
| `docs/ai-onboarding/PROJECT_CONTEXT.md` | Full project context |
| `docs/ai-onboarding/RULES.md` | Anti-hallucination rules |
| `docs/ai-onboarding/DEBRIEF_TEMPLATE.md` | Session note template |
| `docs/CEAL_PROJECT_LEDGER.md` | Tech Debt Register, timeline, Decision Log — will be updated |
| `docs/planning/TECH_DEBT_PROGRAM.md` | Framework + Cross-TD Dependencies + Mechanism F + Lessons — will be updated post-fix |
| `docs/planning/td_007_postgres_datetime_strings.md` | This session's ticket — source of truth for tasks |
| `docs/planning/td_006_postgres_schema_loader.md` | Reference — how the prior TD shipped + closed |
| `docs/planning/td_001_route_integration_tests.md` | Will have its DEFERRED STATUS narrowed once TD-007 closes (TD-008/009 still gating) |
| `docs/session_notes/2026-05-04_td_006_postgres_schema_loader.md` | Discovery context for TD-007's existence |
| `docs/smoke_logs/td_006_20260504.md` | Sample stack traces of TD-007's failure mode |
| `src/models/database.py` | Likely modified — datetime emission sites |
| `src/models/entities.py` | Likely modified — Pydantic serializers |
| `src/models/schema_postgres.sql` | Read; do not modify (column type identification) |
| `src/models/schema.sql` | Read; do not modify (SQLite parity check) |
| `src/models/compat.py` | Read for `is_sqlite()` semantics; do not modify |
| `tests/integration/conftest.py` | Read — `postgres_skip_td` marker registration. Modify only if you need a narrower marker behavior. |
| `tests/integration/test_persistence_roundtrip.py` | Marker removal (TD-007 only) |
| `tests/integration/test_db_parity.py` | Marker removal (TD-007 only — db_parity marker stays) |
| `tests/integration/test_crm_autoapply_roundtrip.py` | Marker removal (TD-007 only) |
| `tests/integration/test_regime_classification_roundtrip.py` | Marker reason narrowed (TD-007 dropped, TD-009 stays) |
| `tests/integration/test_init_db_multi_command_ddl.py` | Read — TD-006 smoke pattern; reuse pattern for TD-007's positive smoke if needed |
| `docs/smoke_logs/td_007_<YYYYMMDD>.md` | You will create this |
| `docs/session_notes/<YYYY-MM-DD>_td_007_postgres_datetime_strings.md` | You will create this |
| `.github/workflows/ci.yml` | Read for `db-tests-postgres` definition; out of scope to modify |
| `docker-compose.yml` | Read for local Postgres setup; use `docker run -p 5433:5432` if native PG conflict on host |
