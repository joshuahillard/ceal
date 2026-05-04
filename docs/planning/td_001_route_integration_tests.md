# TD-001 — Route Integration Tests (Real DB, No Mocks)

> **STATUS — 2026-05-04 (updated): DEFERRED until TD-006/007/008/009 close.**
> Same-day sequence correction moved TD-006 ahead of TD-001 in the program (see `docs/planning/TECH_DEBT_PROGRAM.md` § "Sequence" and § "Lessons"). TD-006 closed 2026-05-04, but its execution surfaced a masked-bugs cascade — three pre-existing PostgreSQL-incompatible patterns (TD-007 datetime strings, TD-008 round-cast, TD-009 SERIAL fixtures) that had been hidden behind TD-006's setup error. TD-001 will add new integration tests in `tests/integration/`, which run in `db-tests-postgres` and can inherit any unresolved masked bug. TD-001 therefore now waits on the full chain.
> **Resume condition:** TD-006/007/008/009 all [RESOLVED] in the Tech Debt Register, AND `db-tests-postgres` CI green on a fresh push to main *with all `pytest.mark.postgres_skip_td` markers removed*. Until those markers are gone, "green CI" includes 22+ skipped tests that TD-001's new tests should be running through.
> Do NOT execute this ticket until those conditions are met. The Task 1 mock-coverage inventory and other in-scope items remain valid; only the timing changes. When resumed, re-run Task 0 (CI state audit, mechanism D), Task 4's walk-the-merge projection (mechanism E), AND grep `tests/` for any remaining `postgres_skip_td` markers (mechanism F) before code.

---

> **Severity:** HIGH
> **Opened:** 2026-04-02 (Sprint 1)
> **Days open at ticket creation:** 32 (RED threshold crossed 2026-05-04)
> **Activated:** 2026-05-04 as TD program item #1 — *re-sequenced same day to item #2 behind TD-006*
> **Branch:** `fix/td-001-route-integration-tests` (to be created in step 2 of the framework, after TD-006 closes)
> **Pre-flight tag:** `pre-td-001` (to be created in step 1 of the framework, after TD-006 closes)
> **Framework reference:** `docs/planning/TECH_DEBT_PROGRAM.md`

---

## Problem statement (from `docs/CEAL_PROJECT_LEDGER.md` Tech Debt Register)

> Mock-only route tests hide SQL bugs. Core query functions need DB-level integration tests.

The Jobs-tab bug class recurred three times because route tests mocked the query functions returning canned data, so the actual SQL never executed in the route's request path. Sprint 6 gap-fill closed *some* of the gap by adding `TestCRMQuerySQL` and `TestAutoApplyQuerySQL` at the database layer (query function called directly with a real session). But route tests in `tests/unit/test_web.py` continue to patch the query functions at the route boundary, so a SQL error in the actual route request path would not be caught by the route test suite.

This ticket closes the route-layer gap.

## In scope

- Add integration tests that exercise route handlers end-to-end against a real in-memory SQLite database, with `init_db()` and seeded data.
- Cover at minimum the routes named in the Sprint 6 / Sprint 8 stakeholder review as the bug-prone surface area: jobs list, dashboard, applications, reminders, approval queue, application review.
- Use `httpx.AsyncClient` against the FastAPI app (existing pattern in `tests/unit/test_web.py` if present — extend, do not duplicate).

## Out of scope

- Modifying any route logic. **This TD is additive testing only.**
- Modifying any query function. The DB layer is already covered by Sprint 6's `TestCRMQuerySQL` and `TestAutoApplyQuerySQL` classes.
- PostgreSQL coverage. TD-006 covers that backend; do not entangle.
- New routes, new schema columns, or new query functions.
- Removing existing mock-based tests. Leave them in place; new integration tests are additive.

## Files to read first (before scope decision)

- `tests/unit/test_web.py` — current route tests; identify every mock site
- `src/web/app.py` — registered routers, app construction
- `src/web/routes/dashboard.py`, `src/web/routes/applications.py`, `src/web/routes/apply.py`, plus any other route module under `src/web/routes/` — route handlers under test
- `src/models/database.py` — query functions currently mocked at the route layer
- `tests/integration/test_persistence_roundtrip.py`, `tests/integration/test_crm_autoapply_roundtrip.py` — integration test patterns to follow
- `tests/conftest.py` (if present) — fixtures available
- `docs/planning/TECH_DEBT_PROGRAM.md` — the framework gates this ticket reports against

## Tasks

### Task 1 — Inventory the mock-coverage gap (no code yet)

For every route module in `src/web/routes/`, list:

- The route path(s) registered
- The query function(s) the handler calls
- Whether `tests/unit/test_web.py` (or any other test file) mocks those calls — and where (file:line)
- Whether any integration test exists that exercises the full route path with a real session

Output: a markdown table written into the session note (created in Task 7) under a "Route Coverage Inventory" heading. This drives the rest of the work.

### Task 2 — Pause for scope decision

After Task 1, present the inventory to the operator. Confirm:

- Which routes get integration tests in this TD
- Which (if any) are deferred to a follow-up TD
- Whether the inventory itself surfaces any route-layer issue worth a separate ticket

**Do not proceed to code without confirmation.**

### Task 3 — Write the failing-then-passing positive smoke

Pick the *single* route most associated with the Jobs-tab bug class (likely the jobs list page, which historically broke on tier-filtering SQL). Write an integration test that:

- (a) Currently passes against main (proving the gap — route works on the happy path the mocks already cover)
- (b) Would fail if a hypothetical SQL bug were reintroduced in the route's query path — i.e., this test would have caught at least one of the three Jobs-tab regressions

Capture the test execution to `docs/smoke_logs/td_001_<YYYYMMDD>.md` with: the test name, the SQL it exercises, the assertion it makes, and the rationale for "this would have caught the X bug."

This is the positive smoke for TD-001. Without it, the fix is just "more tests" — not a closed root cause.

### Task 4 — Add the rest of the integration tests

Per Task 2's confirmed scope. Use the pattern from Task 3. Each test:

- Spins up a real in-memory SQLite session via the existing fixture pattern
- Seeds minimal test data (job listings, applications, etc.) using real INSERT statements
- Invokes the route via `httpx.AsyncClient`
- Asserts on the rendered response (status, key strings, expected data presence/absence)

Do **not** patch any query function for routes that this ticket is adding integration coverage to. Tests for unrelated paths (e.g., authentication, where the underlying issue isn't SQL) may continue to mock as-is.

### Task 5 — Verify regression gate

- `pytest tests/ -q` — full suite green
- `ruff check src/ tests/` — clean
- Test count baseline + delta recorded in the session note
- Verify the original mock-based route tests in `tests/unit/test_web.py` still pass alongside the new integration tests (additive coverage)

### Task 6 — Update SELF_REVIEW + ledger

Mark TD-001 [RESOLVED YYYY-MM-DD <commit-sha>] in the Tech Debt Register at `docs/CEAL_PROJECT_LEDGER.md`. Add a one-line timeline entry under the most recent date heading. No Decision Log entry required unless Task 1's inventory surfaced a pattern change.

### Task 7 — Session note

Create `docs/session_notes/YYYY-MM-DD_td_001_route_integration_tests.md` using `docs/ai-onboarding/DEBRIEF_TEMPLATE.md`. Include:

- Objective + scope confirmed in Task 2
- Route Coverage Inventory table (Task 1's output)
- Files changed (test files only — no src/ changes)
- Test count delta
- Smoke log path
- X-Y-Z career bullet
- Limitations: which routes were NOT covered (if any), why, and the follow-up TD ID if one was opened

### Task 8 — Commit (no push without operator approval)

Single commit on the feature branch. Body includes a **Limitations** sub-section listing:

- Routes intentionally out of scope (with TD link if a follow-up was opened)
- The SQLite-only nature of this coverage (TD-006 covers PostgreSQL parity for the same routes)
- Any test that currently uses mock fallback because the route path requires external services not yet stubbable

## Acceptance criteria

- [ ] `pre-td-001` tag exists on main pre-execution
- [ ] All work on `fix/td-001-route-integration-tests` branch
- [ ] Inventory table exists (Task 1) and operator confirmed scope (Task 2) before any code
- [ ] At least one positive smoke test (failing-then-passing pattern) captured to `docs/smoke_logs/td_001_<YYYYMMDD>.md`
- [ ] Integration tests exist for every route confirmed in Task 2's scope
- [ ] Tests use real `init_db()` + seeded data — NO mock for the query functions under test
- [ ] Full suite green with delta recorded vs baseline
- [ ] TD-001 marked [RESOLVED <date> <commit>] in Tech Debt Register
- [ ] Session note exists
- [ ] Branch merged to main; CI green
- [ ] `pre-td-001` tag still resolves post-merge (rollback path verified by inspection)

## Rollback procedure

**Pre-merge:** `git reset --hard pre-td-001` on the feature branch. No operator approval needed — feature branch is private to the work.

**Post-merge with CI red:** Pause. Capture the failure. `git reset --hard pre-td-001` on main only after operator approval. Force-push main only if operator explicitly authorizes — and never without that authorization.

**Post-merge with CI green but a regression surfaces later:** `git revert <merge-commit>` on a new branch; open a PR for the revert. Investigate root cause before re-attempting.

## Notes

- This TD is additive (new tests). Risk is low. The rigor here builds the pattern for TD-006, which is *not* additive and will need every gate.
- Keep diffs minimal. Per `CLAUDE.md` rule #5: "Keep diffs minimal and local to the task." Do not refactor existing tests in this commit.
- If Task 1 surfaces routes that have been removed or renamed since the register entry, log it but do not retroactively rewrite the register. Surface as a finding for the next sprint review.
- Per `CLAUDE.md` rule #1: read each file before editing it. The inventory in Task 1 is the literal application of that rule to the route surface.
