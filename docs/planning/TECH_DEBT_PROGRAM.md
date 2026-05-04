# Ceal Technical Debt Program

> **Activated:** 2026-05-04
> **Trigger:** TD-001 (HIGH, 32 days open) crossed the 30-day RED threshold on activation day.
> **Operating principle:** No HIGH-severity tech debt item passes 30 days open uncontested. A "register entry" without an active branch is just an alibi for inaction.
> **Resume condition for parallel tracks:** TD-001 and TD-006 [RESOLVED] in the register, main CI green, next sprint review confirms no regression.

---

## Why this exists

The 2026-05-04 sprint review (`docs/planning/sprint_review_20260504.md`) named two structural pace failures:

1. Career-pipeline track dormant 18 days after Sprint 11 with no Sprint 12 plan.
2. TD-001 just crossed 30 days open — first time a HIGH-severity item has aged past the threshold without resolution.

Running parallel tracks (Maven OS + Career-pipeline) without a TD program produced exactly this drift. This document activates the Career-pipeline track for tech debt only, with operational rigor that prevents items from silently aging past their severity threshold.

## Track decisions logged here

- **Career-pipeline track:** ACTIVE 2026-05-04 — scope = the tech debt program below, nothing else. New features blocked.
- **Maven OS track:** DEFERRED 2026-05-04 until TD-001 and TD-006 close. See `docs/planning/MAVEN_OS_WEEK_THREE_PROMPT.md` STATUS header for resume condition.

## Sequence

| Order | TD | Severity | Days open at activation | Rationale |
|---|---|---|---|---|
| 1 | TD-001 | HIGH | 32 | Highest aging risk; fixes the test infrastructure that gates every later fix |
| 2 | TD-006 | HIGH | 18 | Schema loader bug; needs TD-001 test infrastructure to verify SQLite no-regress |
| 3 | TD-003 | Medium | 31 | DB migration; depends on TD-006 backend parity |
| 4 | TD-002 | Medium | 32 | Prompt fix; independent, runs after infra debt closes |
| 5 | TD-005 | Low | 32 | Process gap; cheap, last |

Ordering rule: severity first, then dependency, then age. The override on age (TD-001 first despite tying TD-002 and TD-005 at 32 days) is because TD-001 is HIGH and unblocks the rigor for every later fix.

## Per-TD framework (10 steps, in order)

| Step | What | Artifact |
|---|---|---|
| 1 | Pre-flight tag | `git tag pre-td-NNN` on main, before any branch work |
| 2 | Feature branch | `fix/td-NNN-<slug>` — never touch main directly |
| 3 | Baseline capture | Test count + lint result + git SHA recorded in the per-TD ticket |
| 4 | Plan + scope pause | `docs/planning/td_NNN_<slug>.md` with files-to-touch, acceptance, smoke procedure, rollback procedure. **Operator greenlight required before code.** |
| 5 | Execute | Code + tests on the feature branch |
| 6 | Smoke test | Both: full suite green AND a positive check that the fix addresses root cause. Smoke output captured to `docs/smoke_logs/td_NNN_<YYYYMMDD>.md` |
| 7 | SELF_REVIEW / ledger update | Mark TD-NNN [RESOLVED YYYY-MM-DD <commit>] in `docs/CEAL_PROJECT_LEDGER.md` Tech Debt Register. Decision Log entry if pattern changed. |
| 8 | Session note | `docs/session_notes/YYYY-MM-DD_td_NNN_<slug>.md` — required, not optional |
| 9 | Commit (no push without operator approval) | Body includes a Limitations sub-section |
| 10 | Merge + verify | Merge to main, delete branch, verify CI green. If CI red post-merge, hard-reset to pre-flight tag (operator approval required). |

## Smoke test definition

Smoke is **not** "all tests pass." All tests passing is the regression gate (step 6's first half). Smoke is the **positive** check that the fix actually addresses the root cause. Per TD:

| TD | Positive smoke |
|---|---|
| TD-001 | A new integration test that fails against current main and passes against the fix (i.e., the test would have caught the Jobs-tab bug class) |
| TD-006 | PostgreSQL CI workflow goes from red to green; local docker-compose Postgres run also green; SQLite suite unchanged |
| TD-003 | Migration runs against an existing pre-migration `ceal.db` copy; schema matches the target; queries that depend on the new columns succeed on both backends |
| TD-002 | Frozen LLM fixtures previously flagged by `SemanticValidator` now pass without flagging; golden corpus diff shows no quality regression |
| TD-005 | Schema diff check runs in CI; intentional SQLite-only divergence fails fast; matched schemas pass |

If smoke can't be defined for a TD, the ticket is not ready for execution — surface as a finding and refine the ticket before opening the branch.

## Rollback playbook

Every TD has a pre-flight tag (step 1). Rollback paths in priority order:

1. **Pre-merge (working branch only):** `git reset --hard pre-td-NNN` on the feature branch; force-push the branch (NEVER force-push main).
2. **Post-merge, CI red:** Hard-reset main to `pre-td-NNN` after operator approval. Coordinate with operator before pushing the reset. NEVER force-push main without explicit authorization.
3. **Post-merge, CI green but smoke regresses later:** `git revert <merge-commit>` on a new branch; PR the revert.

Pre-flight tags persist; do not delete them until the TD has been closed AND the next TD has shipped without regression.

## Cadence rules

- **No HIGH-severity TD passes 30 days open** without an active branch, a scoped ticket, or a logged operator decision to defer with rationale.
- **No idle days >3 within an active TD session.** If a TD is in flight, every 3 calendar days produces either a commit or a logged status note in the per-TD ticket.
- **Sprint review every 7 days** as long as the program is active. Pace metrics include TD age, days-since-last-commit, and rollback events.

## What this program does NOT cover

- **New features.** Maven OS Week-Three is deferred precisely so this program does not compete for attention.
- **Tech debt items not in the register.** If a new TD surfaces during a fix, log it (`TD-NNN`) and continue current work; do not expand the active branch's scope.
- **Refactor-for-refactor's-sake.** Every fix points at a specific register entry. If a refactor isn't named in the ticket, it doesn't ship in the ticket's commit.

## Done condition for the program

The program closes when all five TD items in the sequence are [RESOLVED] in the register, AND the next sprint review confirms no regression. At that point Maven OS Week-Three resumes from its deferred state.

## Per-TD ticket index

| TD | Ticket | Status |
|---|---|---|
| TD-001 | `docs/planning/td_001_route_integration_tests.md` | Scoped, awaiting operator confirmation on Task 1 inventory |
| TD-006 | (not yet authored — open after TD-001 closes) | — |
| TD-003 | (not yet authored — open after TD-006 closes) | — |
| TD-002 | (not yet authored) | — |
| TD-005 | (not yet authored) | — |

---

*Activated 2026-05-04. Owner: Josh Hillard. First TD ticket: `td_001_route_integration_tests.md`.*
