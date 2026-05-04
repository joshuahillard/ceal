# Ceal Technical Debt Program

> **Activated:** 2026-05-04
> **Trigger:** TD-001 (HIGH, 32 days open) crossed the 30-day RED threshold on activation day.
> **Operating principle:** No HIGH-severity tech debt item passes 30 days open uncontested. A "register entry" without an active branch is just an alibi for inaction.
> **Resume condition for parallel tracks:** TD-001 and TD-006 [RESOLVED] in the register, main CI green, next sprint review confirms no regression.
>
> **2026-05-04 framework correction:** The original sequence shipped TD-001 first. Within hours of the kickoff commit a CI dependency surfaced — TD-001's integration tests run in the same `db-tests-postgres` job that TD-006 has been breaking since 2026-04-08, so TD-001 could not have shipped green CI without TD-006 closing first. Sequence reversed below to **TD-006 → TD-001 → TD-003 → TD-002 → TD-005**. Five new pre-execution mechanisms (A–E) added to the framework to prevent the same shape of oversight. The miss is documented in "Lessons" so it serves as a precedent, not just a correction.

---

## Why this exists

The 2026-05-04 sprint review (`docs/planning/sprint_review_20260504.md`) named two structural pace failures:

1. Career-pipeline track dormant 18 days after Sprint 11 with no Sprint 12 plan.
2. TD-001 just crossed 30 days open — first time a HIGH-severity item had aged past the threshold without resolution.

Running parallel tracks (Maven OS + Career-pipeline) without a TD program produced exactly this drift. This document activates the Career-pipeline track for tech debt only, with operational rigor that prevents items from silently aging past their severity threshold.

## Track decisions logged here

- **Career-pipeline track:** ACTIVE 2026-05-04 — scope = the tech debt program below, nothing else. New features blocked.
- **Maven OS track:** DEFERRED 2026-05-04 until TD-001 and TD-006 close. See `docs/planning/MAVEN_OS_WEEK_THREE_PROMPT.md` STATUS header for resume condition.

## Pre-execution audits (the five mechanisms)

Five mechanisms added 2026-05-04 to prevent sequencing oversights. Each closes a different failure mode that produced the original-sequence miss. Defense in depth — one gate failing should not lose the catch.

### Program-level (one-time, before kickoff)

**A. Pre-program CI audit.** Before authoring any sequence, capture current CI state via `gh run list --limit 5` and `gh run view <id> --json jobs`. For every red job: name the root-cause TD, the test files it runs, and the source files it depends on. The sequence is then *derived* from the dependency graph, not asserted from register description prose.

**B. Cross-TD dependency graph.** Per-TD declaration (table below) of which CI jobs run that TD's tests/code, which currently-red jobs block it from shipping green, which TDs must close first. Maintained as the program runs — when a TD closes, update the graph in the same commit.

**C. Operator review on program design itself.** Before the kickoff commit, present the sequence + dependency graph to the operator and explicitly ask: *"Have I missed any cross-TD dependencies?"* From now on this is a required gate, not a courtesy. The 2026-05-04 reversal happened retroactively because this gate did not exist when the original program was inscribed.

### Per-TD (every TD ticket)

**D. Task 0 = CI state audit.** First step of every TD ticket, before scope confirmation. Capture `gh run list --limit 5` and identify every currently-red job. For each red job, name the TD it maps to. Then explicitly answer: *"Does this TD's test additions or code changes run in any currently-red job?"* If yes, that's a blocking dependency that must be resolved or explicitly carved out before the TD ships.

**E. Walk-the-merge projection.** Part of Task 4 (plan + scope pause). For each TD ticket, write a literal projection of what `git status` and `gh run list --limit 5` will show *the moment after that TD merges*. If the answer is "still red on `<job>`," the TD is not ready to ship — either the dependency has to land first, or the gate has to be explicitly carved out with operator sign-off recorded in the ticket.

## Sequence (corrected 2026-05-04, expanded 2026-05-04 post-TD-006)

| Order | TD | Severity | Days open at activation | Rationale |
|---|---|---|---|---|
| 1 | **TD-006** | HIGH | 18 | Schema loader bug breaking PostgreSQL CI since 2026-04-08. Blocks every other TD from shipping green CI because `db-tests-postgres` runs all of `tests/integration/`. **First — unblocks CI signal that gates every later commit.** |
| 2 | **TD-007** | HIGH | 0 (opened during TD-006) | Datetime ISO strings rejected by asyncpg for typed columns. Pre-existing bug masked by TD-006. Affects ~16 integration tests across 4 files. Blocks `db-tests-postgres` full-green. |
| 3 | **TD-008** | Medium | 0 (opened during TD-006) | `round()` requires `CAST(x AS numeric)` on Postgres. Pre-existing bug masked by TD-006. Affects 4 pipeline tests. |
| 4 | **TD-009** | Medium | 0 (opened during TD-006) | SERIAL sequence not advanced after explicit-id fixture INSERTs. Test-fixture-only. Affects regime fixture; audit may surface more. |
| 5 | TD-001 | HIGH | 32 (⚠ RED) | Mock-only route tests; original program-#1. Ships green only after TD-006/007/008/009 unblock `db-tests-postgres`. |
| 6 | TD-003 | Medium | 31 | DB migration for Sprint 9 regime columns; depends on TD-006/007/009 backend parity to run on PostgreSQL. |
| 7 | TD-002 | Medium | 32 | Prompt fix; independent of CI infra. Runs after HIGH items close. |
| 8 | TD-005 | Low | 32 | Process gap (schema file drift); cheap, last. |

**Ordering rule (corrected, reaffirmed 2026-05-04 post-TD-006):** CI-blocking dependency first, then severity, then non-blocking dependency, then age. The original "severity first, then dependency, then age" rule under-weighted CI-blocking dependencies. The TD-007/008/009 insertion preserves that rule — they are CI-blocking on `db-tests-postgres` for every later ticket.

**Masked-bugs handling:** TD-007/008/009 were authored *during* TD-006's execution as findings, not in advance. They follow the same authoring discipline as any other TD in this program (per-TD ticket file, mechanisms D + E re-run at session start, walk-the-merge projection). The discovery pattern is recorded in § "Lessons" so the framework treats this kind of cascade as expected, not exceptional.

## Cross-TD Dependencies

| TD | CI jobs that run its tests/code | Currently-red jobs that block green-CI ship | TDs that must close first |
|---|---|---|---|
| TD-006 | `db-tests-postgres`, `unit-tests`, `integration-tests`, `coverage` | (target of fix — turns `db-tests-postgres` green for the schema-loader-specific failure) | None |
| TD-007 | `db-tests-postgres`, `integration-tests` | `db-tests-postgres` (datetime-string rejection across ~16 tests) | **TD-006** (mask removal) |
| TD-008 | `db-tests-postgres`, `integration-tests` | `db-tests-postgres` (round-cast across 4 pipeline tests) | **TD-006** (mask removal) |
| TD-009 | `db-tests-postgres`, `integration-tests` | `db-tests-postgres` (SERIAL fixture across regime tests + audit-pending more) | **TD-006** (mask removal) |
| TD-001 | `unit-tests`, `integration-tests`, `db-tests-postgres`, `coverage` | `db-tests-postgres` (new integration tests inherit any unresolved masked bug) | **TD-006, TD-007, TD-008, TD-009** |
| TD-003 | `db-tests-postgres`, `integration-tests`, `unit-tests` | `db-tests-postgres` (migration must run on PostgreSQL) | **TD-006, TD-007, TD-009** |
| TD-002 | `unit-tests`, `coverage` | None | None |
| TD-005 | (CI workflow file itself; possibly a new lint job) | None | None |

If a TD's "blocking jobs" column is non-empty, the TDs in "must close first" come before it in the sequence.

**Note on TD-006 closure (2026-05-04):** `db-tests-postgres` does *not* go fully green at TD-006 closure because TD-007/008/009 still gate ~22 tests via `postgres_skip_td` markers. TD-006's own success criterion — the schema loader's `cannot insert multiple commands` failure stops occurring — is met. Full PostgreSQL test parity arrives when TD-007/008/009 close.

## Per-TD framework (10 steps, in order)

| Step | What | Artifact |
|---|---|---|
| 1 | Pre-flight: **CI state audit (mechanism D)** + tag | Audit table written into the ticket; `git tag pre-td-NNN` on main |
| 2 | Feature branch | `fix/td-NNN-<slug>` — never touch main directly |
| 3 | Baseline capture | Test count + lint result + git SHA recorded in the per-TD ticket |
| 4 | Plan + scope pause + **walk-the-merge projection (mechanism E)** | `docs/planning/td_NNN_<slug>.md` with files-to-touch, acceptance, smoke procedure, rollback procedure, post-merge CI projection. **Operator greenlight required before code.** |
| 5 | Execute | Code + tests on the feature branch |
| 6 | Smoke test | Both: full suite green AND a positive check that the fix addresses root cause. Smoke output captured to `docs/smoke_logs/td_NNN_<YYYYMMDD>.md` |
| 7 | SELF_REVIEW / ledger update | Mark TD-NNN [RESOLVED YYYY-MM-DD <commit>] in `docs/CEAL_PROJECT_LEDGER.md` Tech Debt Register. **Update the Cross-TD Dependencies table.** Decision Log entry if pattern changed. |
| 8 | Session note | `docs/session_notes/YYYY-MM-DD_td_NNN_<slug>.md` — required, not optional |
| 9 | Commit (no push without operator approval) | Body includes a Limitations sub-section AND a "Walk-the-merge actual" line confirming what CI now looks like |
| 10 | Merge + verify | Merge to main, delete branch, verify CI matches the projection from step 4. If reality diverges from projection, hard-reset to pre-flight tag (operator approval) and revise the projection. |

## Smoke test definition

Smoke is **not** "all tests pass." All tests passing is the regression gate (step 6's first half). Smoke is the **positive** check that the fix actually addresses the root cause. Per TD:

| TD | Positive smoke |
|---|---|
| TD-006 | `db-tests-postgres` CI workflow goes from red to green; local docker-compose Postgres run also green; SQLite suite unchanged; positive test asserting a multi-statement DDL block (e.g., `DO $$...$$` plus a CREATE TRIGGER) loads cleanly via `init_db()` against PostgreSQL |
| TD-001 | A new integration test that fails against current main and passes against the fix (i.e., the test would have caught the Jobs-tab bug class) |
| TD-003 | Migration runs against an existing pre-migration `ceal.db` copy; schema matches the target; queries that depend on the new columns succeed on both backends |
| TD-002 | Frozen LLM fixtures previously flagged by `SemanticValidator` now pass without flagging; golden corpus diff shows no quality regression |
| TD-005 | Schema diff check runs in CI; intentional SQLite-only divergence fails fast; matched schemas pass |

If smoke can't be defined for a TD, the ticket is not ready for execution — surface as a finding and refine the ticket before opening the branch.

## Rollback playbook

Every TD has a pre-flight tag (step 1). Rollback paths in priority order:

1. **Pre-merge (working branch only):** `git reset --hard pre-td-NNN` on the feature branch; force-push the branch (NEVER force-push main).
2. **Post-merge, CI red beyond projection:** Hard-reset main to `pre-td-NNN` after operator approval. Coordinate with operator before pushing the reset. NEVER force-push main without explicit authorization.
3. **Post-merge, CI matches projection but smoke regresses later:** `git revert <merge-commit>` on a new branch; PR the revert.
4. **Sequencing miss surfaces mid-program:** if a TD is found to depend on another TD that was supposed to ship later, pause the active branch, update the Cross-TD Dependencies table, revise the sequence, and re-derive the per-TD ticket. The 2026-05-04 sequence reversal is the worked example.

Pre-flight tags persist; do not delete them until the TD has been closed AND the next TD has shipped without regression.

## Cadence rules

- **No HIGH-severity TD passes 30 days open** without an active branch, a scoped ticket, or a logged operator decision to defer with rationale.
- **No idle days >3 within an active TD session.** If a TD is in flight, every 3 calendar days produces either a commit or a logged status note in the per-TD ticket.
- **Sprint review every 7 days** as long as the program is active. Pace metrics include TD age, days-since-last-commit, rollback events, and any sequencing revisions.
- **CI health is a first-class signal.** A red main on any push prompts a CI audit before the next TD ticket opens. A red job that traces to a known TD does not block the program; an unidentified red job does.

## What this program does NOT cover

- **New features.** Maven OS Week-Three is deferred precisely so this program does not compete for attention.
- **Tech debt items not in the register.** If a new TD surfaces during a fix, log it (`TD-NNN`) and continue current work; do not expand the active branch's scope.
- **Refactor-for-refactor's-sake.** Every fix points at a specific register entry. If a refactor isn't named in the ticket, it doesn't ship in the ticket's commit.

## Done condition for the program

The program closes when all five TD items in the sequence are [RESOLVED] in the register, AND the next sprint review confirms no regression. At that point Maven OS Week-Three resumes from its deferred state.

## Lessons (precedent log)

### 2026-05-04 — Sequence-first oversight, caught by operator

**What happened.** Original program (commit `f79099c`) shipped with sequence TD-001 → TD-006 → TD-003 → TD-002 → TD-005. Within hours, the operator pointed at the failing `db-tests-postgres` CI job from the same push and asked whether it was a new failure. Investigation confirmed it was the long-standing TD-006. Cross-checking against TD-001's planned location (integration tests in `tests/integration/`) revealed that TD-001's tests would inherit TD-006's setup error on PostgreSQL CI — meaning TD-001 could not ship green CI without TD-006 closing first. The sequence was reversed.

**Root cause.** The program author (Claude) sequenced from the abstract register descriptions ("mock-only tests" vs "schema loader bug") and reasoned about them as different layers. The CI graph was already in context (the same session pulled CI runs for the sprint review hours earlier) but was never cross-referenced against the proposed sequence. The framework's strength was forcing rigor on per-TD execution; the gap was that the framework's own design was inscribed without the same rigor applied to it.

**What would have caught it.** Each of the five new mechanisms (A–E) would have caught it independently:
- **A** — Pre-program CI audit would have flagged `db-tests-postgres` red and traced it to TD-006 before any sequence was authored.
- **B** — Building the dependency graph would have surfaced TD-001's dependency on `db-tests-postgres` and hence on TD-006.
- **C** — Operator review on program design would have presented the sequence to the operator and made the dependency question explicit before commit. (This is essentially what happened, retroactively.)
- **D** — Per-TD Task 0 CI audit would have caught it at TD-001 ticket creation, before any branch.
- **E** — Walk-the-merge projection would have shown TD-001's post-merge state still has `db-tests-postgres` red.

**Why one mechanism isn't enough.** A and B catch at program-design time. D and E catch at ticket time. C is the operator-side gate. Defense in depth — one failed gate doesn't lose the catch.

**Takeaway.** "Verify before asserting" applies to program design as much as to per-TD execution. Mechanisms A–E close the gap that produced this miss. The lesson lives in the program permanently as a precedent for future programs of work.

### 2026-05-04 — Masked-bugs cascade caught during TD-006 execution

**What happened.** TD-006's named bug — `cannot insert multiple commands into a prepared statement` — was the first PostgreSQL error every test setup hit, so it short-circuited every later code path. Once the executor switch (`exec_driver_sql`) and the splitter guard landed and `init_db()` started succeeding against Postgres, the integration suite walked further into the application code and surfaced three *additional* pre-existing bugs that had been completely invisible:

1. **TD-007** — datetime ISO strings passed to typed PostgreSQL columns (~16 tests across 4 files).
2. **TD-008** — `round(double precision, integer)` not supported on PostgreSQL; needs `CAST(x AS numeric)` (4 pipeline tests). CLAUDE.md `MODE: db` even called this gotcha out, but no automated check enforced it.
3. **TD-009** — SERIAL sequence not advanced after explicit-id fixture INSERTs; subsequent auto-INSERTs collide (regime fixture; audit may surface more).

There was also an intermediate masked bug (`drop_all_tables` rejecting `DROP TABLE IF EXISTS` without `CASCADE` on Postgres FKs) that was inseparable from verifying TD-006 worked at all — that one was fixed inside TD-006's commit because it gates *any* test from completing setup. The other three are large enough to deserve their own tickets.

**Root cause of the masking.** A single foundational failure at the start of the test setup chain prevents all downstream code from ever executing on the failing backend. Every bug in the downstream chain is invisible until the foundational fix lands. This is structurally the same pattern as a dead-code-after-throw masking type errors — but at the integration-test level, where it can hide for weeks across many bug classes simultaneously.

**What would have caught it earlier.** The framework's mechanism A (pre-program CI audit) and mechanism D (per-TD CI audit) operate on *named* red jobs. They cannot see bugs that are still masked because no test of those bugs has ever run. The only mechanism that surfaces masked bugs is *executing the foundational fix* — which is what TD-006 just did.

**What the framework adds in response.**

- **Mechanism F — Post-foundational-fix unmasking pass.** When a TD removes a foundational mask (e.g., a fix that is the first error in a long error chain), the per-TD ticket *must* include a tasks step that re-runs the affected test job locally with the fix in place and audits every newly-surfaced failure. Each new failure gets categorized: (i) caused by this TD's change (rollback or fix in scope), or (ii) pre-existing and previously masked (carve out with a tracked marker + new TD ticket). The audit goes in the session note's "Masked-bugs cascade" section; new tickets get authored same-session.
- **Marker convention — `pytest.mark.postgres_skip_td(reason)`.** Tests gated on follow-up TDs use this marker (registered in `tests/integration/conftest.py`). Each marker carries a TD-NNN reference in `reason`. The marker is *temporary* — it is removed in the commit that closes the named TD. Greppable: `grep -rn "postgres_skip_td" tests/` enumerates outstanding masked-bug debt.
- **Author follow-up tickets in-session, don't commit them later.** The TD-NNN ticket files exist *as part of TD-006's commit*. The session that discovers a masked bug authors its ticket immediately. This locks in the discovery context (commit SHA, exact stack trace, exact test) at the moment of clearest understanding.

**Takeaway.** Foundational fixes routinely unmask cascades of bugs. The framework should expect this pattern, name it, and provide a clean carve-out so a single TD's commit doesn't grow unbounded. Mechanism F + the `postgres_skip_td` marker + same-session ticket authoring close the gap. Future foundational fixes (e.g., a similar pattern in a different test job) follow the same playbook.

## Per-TD ticket index

| TD | Ticket | Status |
|---|---|---|
| TD-006 | `docs/planning/td_006_postgres_schema_loader.md` | In-flight 2026-05-04 — schema loader fix shipped with masked-bug carve-outs (TD-007/008/009 markers); awaiting commit + push approval |
| TD-007 | `docs/planning/td_007_postgres_datetime_strings.md` | QUEUED — authored during TD-006 closure (masked-bugs cascade); resume when TD-006 closes |
| TD-008 | `docs/planning/td_008_postgres_round_cast.md` | QUEUED — authored during TD-006 closure (masked-bugs cascade); resume when TD-006 closes |
| TD-009 | `docs/planning/td_009_postgres_serial_fixtures.md` | QUEUED — authored during TD-006 closure (masked-bugs cascade); resume when TD-006 closes |
| TD-001 | `docs/planning/td_001_route_integration_tests.md` | DEFERRED until TD-006/007/008/009 close (per-ticket STATUS header — to be updated post-TD-006) |
| TD-003 | (not yet authored — open after TD-007/008/009 close) | — |
| TD-002 | (not yet authored) | — |
| TD-005 | (not yet authored) | — |

---

*Activated 2026-05-04. Framework corrected 2026-05-04. Sequence expanded 2026-05-04 post-TD-006 (masked-bugs cascade). Owner: Josh Hillard. Current in-flight ticket: `td_006_postgres_schema_loader.md`. Next in queue: TD-007 (datetime strings), TD-008 (round-cast), TD-009 (SERIAL fixtures) — order TBD at TD-006 closure based on impact and operator preference.*
