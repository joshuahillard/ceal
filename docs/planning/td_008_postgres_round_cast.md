# TD-008 — PostgreSQL `round(double precision, integer)` Function Missing

> **STATUS — 2026-05-04: QUEUED. Authored during TD-006 closure as a masked-bug finding.**
> Pre-existing bug surfaced when TD-006's init_db fix removed the schema-loader mask. PostgreSQL's `round()` does not accept `(double precision, integer)` — it requires `CAST(x AS numeric)`. This is documented in `CLAUDE.md` Mode Pack `db`: "PostgreSQL gotchas: ROUND() requires CAST(x AS numeric)" — but the constraint was not enforced anywhere, and SQLite's `round()` accepts the same call shape silently.
> **Resume condition:** TD-006 [RESOLVED]; framework's pre-execution mechanisms A–E re-run on TD-008's first session.
> Do NOT execute this ticket until those conditions are met.

---

> **Severity:** Medium (blocks 4 pipeline tests on Postgres; smaller surface than TD-007 but trivially diagnosable)
> **Opened:** 2026-05-04 (during TD-006 execution)
> **Branch:** `fix/td-008-postgres-round-cast`
> **Pre-flight tag:** `pre-td-008`
> **Framework reference:** `docs/planning/TECH_DEBT_PROGRAM.md`
> **Discovery context:** `docs/session_notes/2026-05-04_td_006_postgres_schema_loader.md` § "Masked-bugs cascade"

---

## Problem statement

Pipeline statistics queries call `round(<double precision column>, <integer>)`. PostgreSQL's `round()` function only accepts `numeric` for the two-argument form; `double precision` is rejected:

```
asyncpg.exceptions.UndefinedFunctionError:
function round(double precision, integer) does not exist
HINT: No function matches the given name and argument types. You might
      need to add explicit type casts.
```

The fix is a SQL change: `round(x, 2)` → `round(CAST(x AS numeric), 2)`. SQLite accepts both forms identically, so the cast is portable.

CLAUDE.md `MODE: db` calls this gotcha out explicitly, but no automated check enforces it. A grep-based CI lint or a backend-parity unit test on every aggregate query would catch this class going forward — consider as a Lessons addition once the fix lands.

## Affected tests (file-level postgres_skip_td gate landed in TD-006)

- `tests/integration/test_pipeline.py` (4/4 failures all trace to this)

The file carries `pytestmark = [pytest.mark.postgres_skip_td("TD-008: ...")]`. Removing the marker is part of this ticket's acceptance.

## In scope

- Identify every `round(...)` call against `double precision` columns in `src/models/database.py` and any other module that issues raw SQL.
- Apply `CAST(... AS numeric)` to the first argument.
- Verify both backends accept the new form.
- Remove the `postgres_skip_td("TD-008: ...")` marker from `test_pipeline.py`.

## Out of scope

- TD-007 and TD-009 — separate tickets.
- Other PostgreSQL function-signature mismatches (none currently known; surface as findings if discovered).
- Schema column type changes.

## Files to read first

- `src/models/database.py` — most likely site for aggregate stats SQL (`get_pipeline_stats`, `get_regime_stats`)
- `tests/integration/test_pipeline.py` — failure surface
- `docs/session_notes/2026-05-04_td_006_postgres_schema_loader.md` — discovery
- `docs/planning/TECH_DEBT_PROGRAM.md` — framework gates

## Tasks (skeletal)

1. Task 0 — CI state audit
2. Reproduce locally
3. `grep -rn "round(" src/` and audit each call site
4. Fix every identified call with `CAST(... AS numeric)`
5. Run regression gate on both backends
6. Remove `postgres_skip_td("TD-008: ...")` marker
7. Ledger + Cross-TD update
8. Session note + commit + merge + verify

## Acceptance criteria

- `postgres_skip_td("TD-008: ...")` marker removed from `test_pipeline.py`
- All four pipeline tests pass on Postgres
- SQLite suite unchanged
- Walk-the-merge projection: `db-tests-postgres` improves by 4 passes

## Walk-the-merge projection

To be filled at session start.

## Rollback procedure

Standard: `pre-td-008` tag preserved.
