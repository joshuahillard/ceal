# TD-009 — PostgreSQL SERIAL Sequence Not Advanced After Explicit-id Test Fixtures

> **STATUS — 2026-05-04: QUEUED. Authored during TD-006 closure as a masked-bug finding.**
> Pre-existing bug surfaced when TD-006's init_db fix removed the schema-loader mask. Test fixtures seed rows with explicit `id=1, 2, 3` for deterministic test data. SQLite's AUTOINCREMENT picks `MAX(id)+1` on subsequent inserts; PostgreSQL's SERIAL is backed by a sequence that does NOT advance on explicit-id INSERT, so the next auto-INSERT collides with the seeded row.
> **Resume condition:** TD-006 [RESOLVED]; framework's pre-execution mechanisms A–E re-run on TD-009's first session.
> Do NOT execute this ticket until those conditions are met.

---

> **Severity:** Medium (test-fixture-only issue; production code unaffected — but blocks ~5 tests on Postgres)
> **Opened:** 2026-05-04 (during TD-006 execution)
> **Branch:** `fix/td-009-postgres-serial-fixtures`
> **Pre-flight tag:** `pre-td-009`
> **Framework reference:** `docs/planning/TECH_DEBT_PROGRAM.md`
> **Discovery context:** `docs/session_notes/2026-05-04_td_006_postgres_schema_loader.md` § "Masked-bugs cascade"

---

## Problem statement

Test fixtures (notably the regime-classification fixture and similar patterns elsewhere) seed test data with explicit `id` values:

```python
INSERT INTO job_listings (id, external_id, ...) VALUES (1, 'regime-001', ...) ON CONFLICT DO NOTHING;
INSERT INTO job_listings (id, external_id, ...) VALUES (2, 'regime-002', ...) ON CONFLICT DO NOTHING;
INSERT INTO job_listings (id, external_id, ...) VALUES (3, 'regime-003', ...) ON CONFLICT DO NOTHING;
```

After the fixture runs:
- **SQLite:** AUTOINCREMENT picks `MAX(id)+1 = 4` on the next INSERT — works.
- **PostgreSQL:** the SERIAL sequence still points at `1` (explicit INSERT does not advance the sequence). The next auto-INSERT generates `id=1` and collides:

```
asyncpg.exceptions.UniqueViolationError:
duplicate key value violates unique constraint "job_listings_pkey"
DETAIL: Key (id)=(1) already exists.
```

The fix is fixture-only. Three options:
1. Bump the sequence after explicit INSERTs: `SELECT setval(pg_get_serial_sequence('job_listings', 'id'), MAX(id)) FROM job_listings;`
2. Drop explicit-id INSERTs and use returned ids (refactor fixtures).
3. Use a portable seed helper that adapts per backend.

Option 1 is the smallest diff. Option 2 is most idiomatic but rewrites fixture logic. Operator decides at TD-009 session start.

## Affected tests (file-level postgres_skip_td gate landed in TD-006)

- `tests/integration/test_regime_classification_roundtrip.py` (intersects with TD-007)

The file carries `pytestmark = [pytest.mark.postgres_skip_td("TD-007 + TD-009: ...")]`. Marker can only be removed when BOTH TD-007 and TD-009 are resolved (whichever ships second drops the marker).

A grep audit across `tests/integration/` may surface other fixtures with the same pattern; included in scope as part of Task 0.

## In scope

- Audit every `tests/integration/` fixture for explicit-id INSERT patterns.
- Apply chosen fix (bump sequence, or refactor) to each affected fixture.
- Verify on both backends.
- Coordinate with TD-007 on shared marker removal.

## Out of scope

- Changes to production code (SERIAL semantics are correct in production; only test fixtures are affected).
- TD-007 and TD-008 — separate tickets, though scheduling-coordinated for marker removal.

## Files to read first

- `tests/integration/test_regime_classification_roundtrip.py` — the canonical failure case
- All other `tests/integration/test_*.py` — audit for the same pattern
- `src/models/schema_postgres.sql` — confirm SERIAL columns
- `docs/session_notes/2026-05-04_td_006_postgres_schema_loader.md` — discovery context
- `docs/planning/TECH_DEBT_PROGRAM.md` — framework

## Tasks (skeletal)

1. Task 0 — CI state audit
2. Reproduce locally
3. Grep-based audit of all integration fixtures for explicit-id INSERT patterns
4. Pause for fix-path decision (bump sequence vs refactor)
5. Apply fix to every identified fixture
6. Regression gate
7. Coordinate with TD-007 to remove the shared `postgres_skip_td` marker on regime test
8. Ledger + Cross-TD update
9. Session note + commit + merge + verify

## Acceptance criteria

- All identified explicit-id fixtures fixed
- All affected tests pass on Postgres
- SQLite suite unchanged
- `postgres_skip_td` markers referencing TD-009 removed (final marker may need TD-007's resolution to drop fully)

## Walk-the-merge projection

To be filled at session start.

## Rollback procedure

Standard: `pre-td-009` tag preserved.
