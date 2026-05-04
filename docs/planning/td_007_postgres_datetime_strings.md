# TD-007 — PostgreSQL Datetime ISO Strings Rejected by asyncpg

> **STATUS — 2026-05-04: QUEUED. Authored during TD-006 closure as a masked-bug finding.**
> Pre-existing bug surfaced when TD-006's init_db fix removed the schema-loader mask. Tests that pass on SQLite (which silently coerces ISO strings) fail on PostgreSQL+asyncpg with `DataError: invalid input for query argument $N: '2026-...' (expected a datetime.date or datetime.datetime instance, got 'str')`.
> **Resume condition:** TD-006 [RESOLVED]; framework's pre-execution mechanisms A–E re-run on TD-007's first session.
> Do NOT execute this ticket until those conditions are met.

---

> **Severity:** HIGH (blocks `db-tests-postgres` green-CI; 16+ test failures across 4 integration files)
> **Opened:** 2026-05-04 (during TD-006 execution)
> **Branch:** `fix/td-007-postgres-datetime-strings` (to be created after TD-006 closes)
> **Pre-flight tag:** `pre-td-007`
> **Framework reference:** `docs/planning/TECH_DEBT_PROGRAM.md`
> **Discovery context:** `docs/session_notes/2026-05-04_td_006_postgres_schema_loader.md` § "Masked-bugs cascade"

---

## Problem statement

Application code emits ISO-8601 datetime strings (e.g., `"2026-05-04T18:49:43Z"`) and passes them as parameters to PostgreSQL queries with typed `TIMESTAMP` / `DATE` columns. SQLite silently coerces these strings; PostgreSQL+asyncpg rejects them at the driver layer:

```
asyncpg.exceptions.DataError: invalid input for query argument $4:
'2026-05-04T18:49:43Z' (expected a datetime.date or datetime.datetime instance, got 'str')
```

Pre-fix this was masked because TD-006 prevented `init_db()` from succeeding — no test against PostgreSQL ever reached the application code. Post-TD-006, every code path emitting ISO strings to typed columns fails on Postgres.

## Affected tests (file-level postgres_skip_td gates landed in TD-006)

- `tests/integration/test_persistence_roundtrip.py` (3 failures)
- `tests/integration/test_db_parity.py` (4 failures, includes other patterns)
- `tests/integration/test_crm_autoapply_roundtrip.py` (6 failures)
- `tests/integration/test_regime_classification_roundtrip.py` (intersects with TD-009)

Each file carries a `pytestmark = [pytest.mark.postgres_skip_td("TD-007: ...")]`. Removing those markers is part of this ticket's acceptance.

## In scope

- Identify the source paths emitting ISO strings into typed datetime columns (likely in `src/models/database.py` upserts, `src/models/entities.py` serializers, or both).
- Convert to passing `datetime` objects directly OR cast the SQL parameter type explicitly so asyncpg accepts the string (`CAST(:dt AS TIMESTAMP)`).
- Verify both backends accept the converted form.
- Remove the `postgres_skip_td("TD-007: ...")` markers from the affected test files.

## Out of scope

- Schema column type changes.
- TD-008 (round-cast) and TD-009 (SERIAL fixtures) — separate tickets.
- Test rewrites unless the markers can't be removed without one (note as finding if so).

## Files to read first

- `src/models/database.py` — query functions and upsert paths
- `src/models/entities.py` — Pydantic serializers and `to_*` helpers
- `tests/integration/test_persistence_roundtrip.py`, `test_db_parity.py`, `test_crm_autoapply_roundtrip.py` — failure surfaces
- `docs/session_notes/2026-05-04_td_006_postgres_schema_loader.md` — discovery + sample stack traces
- `docs/planning/TECH_DEBT_PROGRAM.md` — framework gates

## Tasks (skeletal — fill in at session start)

1. Task 0 — CI state audit (mechanism D)
2. Reproduce locally against docker-compose Postgres
3. Identify root-cause emission sites (grep `to_char\|isoformat\|strftime`)
4. Pause for fix-path decision (datetime objects vs SQL CAST)
5. Implement fix
6. Smoke test: a previously-failing assertion now passes against Postgres
7. Regression gate: SQLite + Postgres + ruff
8. Remove `postgres_skip_td("TD-007: ...")` markers from affected files
9. Update ledger + Cross-TD Dependencies + framework lessons if applicable
10. Session note + commit + merge + verify

## Acceptance criteria

- All `postgres_skip_td` markers referencing TD-007 removed
- Affected integration tests pass on Postgres
- SQLite suite unchanged (no regression)
- Walk-the-merge projection met: `db-tests-postgres` job preserves green it had at TD-006 closure (or improves it if TD-008/009 are resolved by then)

## Walk-the-merge projection

To be filled at session start, before any code.

## Rollback procedure

Standard: `pre-td-007` tag preserved; `git reset --hard pre-td-007` on feature branch pre-merge, with operator approval post-merge.
