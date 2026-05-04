# Maven OS Week-Three Kickoff — Adapter Hardening, Live Smoke, Hygiene Catch-Up

> **STATUS — 2026-05-04: DEFERRED until TD-001 and TD-006 close.**
> Operator decision 2026-05-04 to focus on the Ceal Tech Debt Program (`docs/planning/TECH_DEBT_PROGRAM.md`) rather than run parallel tracks. Maven OS Week-Three's open decision #3 (Career-pipeline paused or active?) is hereby answered: **Career-pipeline ACTIVE for TD program; Maven OS DEFERRED.**
> **Resume condition:** TD-001 and TD-006 both [RESOLVED] in the Tech Debt Register, main CI green, AND the sprint review immediately following TD-006 closure confirms no regression.
> **Do NOT execute this prompt** until those conditions are met. Re-validate every state claim against the repo before resuming — items below were accurate as of 2026-05-04 but the resume window may be weeks out.
> **Reference docs at deferral time:** `docs/planning/TECH_DEBT_PROGRAM.md`, `docs/planning/td_001_route_integration_tests.md`, `docs/planning/sprint_review_20260504.md`.

---

> **Paste this entire document as the first message in a fresh chat.** The new Claude instance has zero prior conversation history; this prompt is authoritative. Verify every claim by reading the files listed before writing any code.

---

## Context — read these first

You are working on the **Ceal** project. Maven OS is the agentic-handoff governance pipeline that ships under `pilots/` and `tools/` inside this repo. The Week-Two ticket (Linear concrete tracker adapter) shipped on 2026-04-30 as a single-session burst. This Week-Three session closes the residual P1 findings that the Week-Two closeout opened, restores session-note discipline, and decides the Career-pipeline track's status.

- **Project root:** `C:\Users\joshb\Documents\Claude\Projects\Ceal\ceal`
- **GitHub:** https://github.com/joshuahillard/ceal
- **Owner:** Josh Hillard (Boston, MA)
- **Phase at prompt creation:** Maven OS Week-Two ticket complete (single-session, 2026-04-30). Sprint Review for window 2026-04-27 → 2026-05-04 captured at `docs/planning/sprint_review_20260504.md`. Career-pipeline track has been dormant since Sprint 11 (2026-04-16) — operator decision needed.

**Read these in order before any code:**

1. `CLAUDE.md` (repo root) — Core Contract, Mode Packs, Task Format. Mode Pack `ml` applies to the live-smoke work; Mode Pack `db` does not apply unless TD-006 is folded in.
2. `docs/ai-onboarding/PROJECT_CONTEXT.md` — full project context.
3. `docs/ai-onboarding/RULES.md` — anti-hallucination engineering rules.
4. `docs/CEAL_PROJECT_LEDGER.md` — Decision Log (ADR-001 through ADR-009) and Tech Debt Register (TD-001, TD-002, TD-006 are HIGH and untouched on the Career-pipeline side).
5. `docs/planning/sprint_review_20260504.md` — **Most important doc for this session.** Names the carry-forward queue this prompt closes.
6. `docs/planning/SELF_REVIEW.md` — current Maven OS self-review with findings #1–#15. **Findings #11, #13 are this session's primary targets.**
7. `docs/planning/MAVEN_OS_WEEK_TWO_PROMPT.md` — historical kickoff for the Week-Two ticket. Read the STATUS header for what shipped and what was deferred. Do NOT re-execute.
8. `tools/tracker_adapter/__init__.py` — the Protocol contract. Finding #11 may modify this; read it carefully.
9. `tools/tracker_adapter/linear.py` — the concrete adapter shipped 2026-04-30. Finding #13 validates this against a real Linear workspace; finding #14 (P2 stretch) hardens it.
10. `tools/tracker_adapter/registry.py` — the resolver wired in 2026-04-30. Read for context; do NOT modify unless a finding requires it.
11. `tests/unit/test_tracker_adapter_linear.py` and `tests/unit/test_tracker_adapter_registry.py` — current test coverage. Use as a pattern for any new tests.
12. `pilots/acme-corp/pilot_profile.yaml` — declares `active_tracker: linear` and the `tracker_config` block (placeholder `team_id`).
13. `.github/workflows/handoff-lint.yml` — current GHA gate (still hardcoded to acme-corp per finding #12).

---

## What's been done thus far

### Maven OS Week-One Miniature (April 22–24, committed retroactively 2026-04-30 in `09bf55c`)

- `pilots/acme-corp/` — first pilot: 15-section `handoff_spec.md` template, `pilot_profile.yaml`, 20-case `golden_corpus.jsonl` (35% adversarial), empty `ledger.jsonl` placeholder.
- `tools/handoff_lint.py` — CLI linter with 4 exit codes (PASS/BLOCK/ESCALATE/HARNESS_FAULT), 25% delta rule, baseline resolution from PR base branch.
- `tools/tracker_adapter/__init__.py` — **Protocol-only** at Week-One close. Sync method signatures.
- `tests/unit/test_handoff_lint.py` — 18 tests; full Ceal suite at 332 passing on 2026-04-30 morning.
- `.github/workflows/handoff-lint.yml` — GHA gate for `pilots/**` PRs (hardcoded to acme-corp).
- `docs/reference/ADR-009-pyyaml.md` — PyYAML pinned at 6.0.3 with full rationale.
- `docs/planning/SELF_REVIEW.md` — Week-One self-review with 10 findings; #1 closed in-week, #7 closed 2026-04-30, #2 closed 2026-04-30 by the Week-Two work.

### Maven OS Week-Two single-session ticket (2026-04-30)

- `tools/tracker_adapter/linear.py` — concrete `LinearAdapter` against Linear's GraphQL API via httpx. Five operations: FindIssueByTitlePrefix, GetIssue, ListStaleIssues, CreateIssue, UpdateIssue. **Sync** method signatures (matching the Protocol).
- `tools/tracker_adapter/registry.py` — resolves `active_tracker: linear` to `LinearAdapter` at runtime. Reads the `tracker_config` block from `pilot_profile.yaml`.
- `pilots/acme-corp/pilot_profile.yaml` — added `tracker_config` block with placeholder `team_id`.
- `tests/unit/test_tracker_adapter_linear.py` — 16 HTTP-mocked unit tests (respx). **Positive assertion that LINEAR_API_KEY never appears in any logged or raised text.**
- `tests/unit/test_tracker_adapter_registry.py` — 4 registry-resolution tests, including end-to-end smoke that reads the actual `pilot_profile.yaml`.
- `docs/planning/SELF_REVIEW.md` — finding #2 closed; **findings #11–#15 opened** during the closeout.
- Test suite 332 → 355 local, ruff clean, 0 regressions.
- All commits local (no push). Three commits: `09bf55c`, `6b05a8f`, `559b8f7`.

### Outstanding from `sprint_review_20260504.md`

- **No session note** was written for the 2026-04-30 Maven OS work. Last session note in repo is 2026-04-16. Convention violation; needs retroactive close.
- **Career-pipeline track has been dormant 18 days** with no Sprint 12 plan. Operator decision needed — pause formally or schedule.
- **`data/resume.txt`** is modified in the working tree at the time of this prompt (uncommitted, unrelated to either track). Disposition needed.
- **TD-006 (HIGH)** PostgreSQL CI red since 2026-04-16. Untouched. Maven OS scope decision: include in Week-Three or remain Career-pipeline scope.

---

## What needs to change in the pipeline

This session focuses on the residual P1 work from the Week-Two closeout, plus hygiene catch-up. P2 items are explicitly stretch goals — fold in only with explicit user approval.

### P1 — must-do this session

- **Finding #11 — Sync/async Protocol decision and implementation.** The `TrackerAdapter` Protocol declares sync method signatures; the rest of Ceal is async (asyncio + SQLAlchemy 2.0 async + httpx async). This blocks any async caller from wiring the Linear adapter cleanly. **Required output:** `docs/reference/ADR-010-tracker-adapter-async.md` recording the decision and rationale, plus the implementation that follows the decision (async-ify the Protocol + adapter, OR document explicit thread-executor wrapping pattern with example).
- **Finding #13 — Live Linear smoke against a throwaway workspace.** The five GraphQL operations in `tools/tracker_adapter/linear.py` are tested at the HTTP-mock layer only. A single live read+create+update+cleanup pass against a throwaway Linear workspace would catch any schema drift before this adapter sees production traffic. **Gate:** if no throwaway workspace + `LINEAR_API_KEY` is available, STOP and produce a one-page prep checklist for Josh; do not invent a smoke result.

### Hygiene catch-up — must close before next sprint

- **Retroactive session note** for 2026-04-30 Maven OS work at `docs/session_notes/2026-04-30_maven-os-linear-adapter.md`. Use `docs/ai-onboarding/DEBRIEF_TEMPLATE.md`. Document: scope shipped, deferred items, ADR-009 folded in, findings #11–#15 opened, X-Y-Z career bullet.
- **Career-pipeline track decision logged** in `docs/CEAL_PROJECT_LEDGER.md`. Either (a) "Paused 2026-05-04 pending Maven OS pilot completion" with a clear resume-trigger condition, or (b) a Sprint 12 plan covering TD-006 at minimum. Operator decision required — do not assume.
- **`data/resume.txt` disposition.** Modified in working tree at session start. Verify with Josh whether to commit, stash, or revert. Do not silently include in any other commit.

### P2 — stretch if time and explicit approval

- **Finding #14 — Linear adapter operational gaps.** Three sub-items, ordered by risk: (a) 429 rate-limit retry with exponential backoff (highest), (b) pagination on `list_stale` (Linear default ~50 nodes/page), (c) title-prefix idempotency hardening for the manual-edit case. (a) is ~30 min and tightens what just shipped; (b) and (c) larger.
- **Finding #12 — Workflow generalization.** `.github/workflows/handoff-lint.yml` runs the linter on `pilots/acme-corp/handoff_spec.md` only. Generalize via matrix or loop over `pilots/*/handoff_spec.md`. Mechanical; ~20 min.

### Out of scope (do not bundle)

- **Findings #6, #15** — Real golden corpus inputs and `ImplementationState` schema. Both gated on external artifacts (real ticket history; `Maven_OS_Enterprise_Malleability_Analysis.md` Part C). Defer.
- **Findings #3, #4, #5** — Banned-term enforcement, magic-number threshold to YAML, schema-driven enums. Defer to a P2 hardening session.
- **Findings #8, #10** — Workflow E2E via `act`, pilot_profile validator. Defer.
- **TD-006** — PostgreSQL CI red. Career-pipeline scope; defer unless operator explicitly folds it into Week-Three.

---

## Goal for this session

Close residual P1 findings #11 and #13, restore session-note hygiene, and resolve the Career-pipeline track and `data/resume.txt` working-tree state. After this session:

- `tools/tracker_adapter/__init__.py` is async-correct (or the sync-with-executor pattern is explicitly documented and implemented).
- `LinearAdapter` is either validated against a real Linear workspace, or has a published prep checklist for the next session to validate it.
- SELF_REVIEW findings #11 and #13 close (or #13 documents the prep gate cleanly).
- A session note exists for the 2026-04-30 work and for this session.
- The Career-pipeline track has a recorded decision in the ledger.
- The working tree has no unrelated uncommitted drift carrying into the next session.

---

## Open decisions — confirm with the user before writing code

Pause and present this list. Do not proceed until each is settled.

1. **Throwaway Linear workspace.** Does Josh have a throwaway/test Linear workspace with a working `LINEAR_API_KEY`? If yes, capture the team_id and proceed with finding #13. If no, scope #13 down to "produce prep checklist + defer."
2. **Sync vs async Protocol decision.** Two options: (a) async-ify `TrackerAdapter` Protocol — every method becomes `async def`, `LinearAdapter` migrates from sync httpx to async httpx; consistent with the rest of Ceal. (b) keep sync Protocol, document and implement a `run_in_executor` wrapper at the call site so async callers can use it without blocking. Recommended: (a) — Ceal is async-everywhere per CLAUDE.md and Cael never has a sync caller. Confirm or push back.
3. **Career-pipeline track decision.** Paused or active? If paused, what is the explicit resume-trigger? If active, who writes the Sprint 12 plan and when? Recommended: paused with trigger condition "Maven OS pilot has shipped first paying customer OR three concrete tracker adapters." Confirm or override.
4. **`data/resume.txt`** working-tree change. Commit, stash, or revert? Recommended: confirm intent before doing anything; this is unrelated to either track.
5. **P2 stretch.** Strict P1-only, or fold in finding #14(a) (429 retry, ~30 min)? If green-lit on (a), include in this session's commit. (b) and (c) and finding #12 stay deferred regardless.
6. **TD-006.** Out of Maven OS scope by default. Override to include?

---

## Tasks (after open decisions are settled)

1. **Verify context.** `pwd` (must end in `Ceal\ceal`), `git remote -v` (must point at `joshuahillard/ceal`), `git log --oneline -10`, `git status`. If wrong or surprising, stop and ask.
2. **Capture baseline tests.** `PYTHONPATH=. pytest tests/ -q` and record the count + exit code. Anti-regression gate. Expected: 355 passing on 2026-04-30 baseline (verify before claiming).
3. **Resolve `data/resume.txt`** per decision #4. Either commit it on its own (with intent message), stash it, or revert. Working tree must be clean before any other change.
4. **Write retroactive session note** for 2026-04-30 at `docs/session_notes/2026-04-30_maven-os-linear-adapter.md`. Use `docs/ai-onboarding/DEBRIEF_TEMPLATE.md`. Sections: objective, files changed, test results, architecture decisions, what was intentionally not in scope, X-Y-Z career bullet. Backdate the title only — the note is being written 2026-05-04+ for accountability and the file should say so.
5. **Implement Finding #11 per decision #2.**
   - **If async-ify (recommended):** Modify `tools/tracker_adapter/__init__.py` to make every Protocol method `async def`. Migrate `tools/tracker_adapter/linear.py` from sync httpx to async httpx (already a dep). Update `tools/tracker_adapter/registry.py` if any sync assumption breaks. Update tests to use `pytest-asyncio` and `respx.AsyncMockRouter` (or equivalent). Run `pytest tests/unit/test_tracker_adapter_*.py -v`.
   - **If sync-with-executor:** Document the `asyncio.to_thread` or `loop.run_in_executor` pattern in the ADR with a concrete code example. Add a test that exercises the pattern from an async caller. Do NOT modify the Protocol.
   - Either path: write `docs/reference/ADR-010-tracker-adapter-async.md` with the decision, alternatives considered, trade-offs, and a one-line entry in `docs/CEAL_PROJECT_LEDGER.md` Decision Log.
6. **Implement Finding #13 per decision #1.**
   - **If workspace available:** Create `scripts/smoke_linear_adapter.py` (or similar) that runs read+create+update+cleanup against the throwaway workspace. Take a `--team-id` arg, read `LINEAR_API_KEY` from env. Capture stdout transcript to `docs/smoke_logs/2026-05-XX_linear_adapter.md` (redact any token leaks). Add a CI-skip marker so this never runs in GHA.
   - **If workspace not available:** Write `docs/planning/LINEAR_SMOKE_PREP.md` with the explicit Josh-actions: (1) sign up for free Linear workspace, (2) create a personal API token, (3) capture team_id, (4) export `LINEAR_API_KEY`, (5) run the smoke script. Mark finding #13 [PENDING_USER_PREP] in SELF_REVIEW with a date and the prep doc reference.
7. **(P2 stretch only if decision #5 greenlit)** Implement finding #14(a): 429 retry with exponential backoff in `LinearAdapter`. Add a unit test that simulates two 429s then a 200 and asserts the retry happened. Cap retries at 3.
8. **Update `docs/planning/SELF_REVIEW.md`.**
   - Mark finding #11 [RESOLVED YYYY-MM-DD] with the ADR reference and test path.
   - Mark finding #13 either [RESOLVED YYYY-MM-DD] (smoke ran) or [PENDING_USER_PREP YYYY-MM-DD] (prep doc shipped).
   - If #14(a) shipped, mark sub-item resolved in finding #14's body without closing the parent (which still has (b) and (c) open).
   - Append a "Session ledger" line at the bottom: "Week-Three session 2026-05-XX closed findings X, Y; opened (any new) Z."
9. **Update `docs/CEAL_PROJECT_LEDGER.md`.**
   - Append timeline entry for the 2026-04-30 work (Week-Two ticket) AND this session (Week-Three).
   - Append ADR-010 to the Decision Log.
   - Append Career-pipeline track decision per decision #3.
   - Update Cumulative Metrics table (test count, ADR count, commit count).
10. **Write session note for THIS session** at `docs/session_notes/2026-05-XX_maven-os-week-three.md`. Same template.
11. **Pre-commit critical review.** What's the riskiest line? What did the tests not cover? What would surprise an auditor in three months? Surface as a Limitations sub-section in the commit message body. The async migration in particular: any caller-site assumption that broke, any test that now skips silently, any await that should have been gather, any timeout that defaulted to None.
12. **Commit (no push).** Two commits recommended for clarity: (a) ADR-010 + Protocol/adapter async migration + tests, (b) live smoke OR prep doc + SELF_REVIEW + ledger + session notes. Wait for explicit `PUSH` approval before pushing either.

---

## Acceptance criteria

- [ ] All open decisions answered before any code is written
- [ ] `data/resume.txt` working-tree state resolved per decision #4
- [ ] Retroactive session note for 2026-04-30 exists at `docs/session_notes/2026-04-30_maven-os-linear-adapter.md`
- [ ] `docs/reference/ADR-010-tracker-adapter-async.md` exists, documents the decision and alternatives
- [ ] `tools/tracker_adapter/__init__.py` and `tools/tracker_adapter/linear.py` are consistent with the ADR (async-ified or executor-pattern documented and tested)
- [ ] `tests/unit/test_tracker_adapter_linear.py` and `tests/unit/test_tracker_adapter_registry.py` pass under the new model
- [ ] Either a live-smoke transcript at `docs/smoke_logs/` OR a prep checklist at `docs/planning/LINEAR_SMOKE_PREP.md` exists, depending on decision #1
- [ ] `docs/planning/SELF_REVIEW.md` has finding #11 [RESOLVED] and finding #13 either [RESOLVED] or [PENDING_USER_PREP], with dates and evidence
- [ ] `docs/CEAL_PROJECT_LEDGER.md` updated with Week-Two ticket entry, Week-Three entry, ADR-010, Career-pipeline decision, updated cumulative metrics
- [ ] Session note for THIS session exists
- [ ] No regression in test count vs 2026-04-30 baseline (355). Record before/after.
- [ ] No `LINEAR_API_KEY` value committed, logged, or echoed in any artifact
- [ ] Commits follow project convention (check `git log --oneline -10` for style); each body includes a Limitations sub-section
- [ ] No push to GitHub without explicit `PUSH` approval

---

## What you should NOT do

- Do NOT modify `tools/handoff_lint.py`. Out of scope for this session.
- Do NOT modify `pilots/acme-corp/handoff_spec.md`, `golden_corpus.jsonl`, or `pilot_profile.yaml` beyond what is required by the async migration (e.g., a `team_id` value swap if the smoke runs, with Josh's permission).
- Do NOT bundle P2 work beyond decision #5's scope. Banned-term enforcement, magic-number threshold to YAML, schema-driven enums, workflow generalization are explicitly deferred.
- Do NOT modify `schema.sql` without also updating `schema_postgres.sql` (CLAUDE.md rule #10) — and do NOT touch them at all this session unless TD-006 is folded in by operator override.
- Do NOT pin a new top-level dependency without an ADR under `docs/reference/`. The async migration may need `pytest-asyncio` if not already present — verify first; if a new pin is required, write the ADR alongside.
- Do NOT push or share the `LINEAR_API_KEY`. If the live smoke runs, the token comes from env and never appears in any committed file, log, or commit message.
- Do NOT call destructive Linear endpoints (delete issue, archive project) even in smoke. Read/create/update only; clean up via update-to-Cancelled-state, not delete.
- Do NOT trust this prompt blindly. Verify every state claim by reading the referenced file (CLAUDE.md rule #1). The Week-Two STATUS header in `MAVEN_OS_WEEK_TWO_PROMPT.md` and the Sprint Review at `sprint_review_20260504.md` are the most current ground truth.
- Do NOT silently include `data/resume.txt` in any feature commit. Disposition first; commit it on its own if the intent is to include it.

---

## How to start

1. Verify context and capture baseline tests (Tasks 1–2).
2. Read the docs listed under "Context" in the order given.
3. **Pause and present the open-decisions list (1–6) to the user.** Wait for confirmation on each before writing any code.
4. After greenlight: `data/resume.txt` resolution → retroactive session note → ADR-010 + async migration → tests green → smoke OR prep → SELF_REVIEW + ledger updates → session note for this session → pre-commit review → commit (no push).

---

## Reference: file inventory for this work

| Path | Role |
|------|------|
| `CLAUDE.md` | Master prompt — read first |
| `docs/ai-onboarding/PROJECT_CONTEXT.md` | Full project context |
| `docs/ai-onboarding/RULES.md` | Anti-hallucination rules |
| `docs/ai-onboarding/DEBRIEF_TEMPLATE.md` | Session note template |
| `docs/CEAL_PROJECT_LEDGER.md` | Project timeline, ADRs, tech debt register — will be updated |
| `docs/planning/sprint_review_20260504.md` | Most current sprint review — read for context |
| `docs/planning/SELF_REVIEW.md` | Maven OS findings list — will be updated |
| `docs/planning/MAVEN_OS_WEEK_TWO_PROMPT.md` | Historical Week-Two ticket prompt with STATUS header — read for context, do NOT re-execute |
| `docs/reference/ADR-009-pyyaml.md` | Pattern for Maven-OS ADRs |
| `docs/reference/ADR-010-tracker-adapter-async.md` | **You will create this** |
| `docs/planning/LINEAR_SMOKE_PREP.md` | **You may create this if no live workspace** |
| `docs/smoke_logs/2026-05-XX_linear_adapter.md` | **You may create this if smoke runs** |
| `docs/session_notes/2026-04-30_maven-os-linear-adapter.md` | **You will create this (retroactive)** |
| `docs/session_notes/2026-05-XX_maven-os-week-three.md` | **You will create this** |
| `tools/tracker_adapter/__init__.py` | Protocol — will be modified per decision #2 |
| `tools/tracker_adapter/linear.py` | Concrete adapter — will be modified per decision #2 (and possibly #5) |
| `tools/tracker_adapter/registry.py` | Resolver — read; modify only if async migration breaks an assumption |
| `tests/unit/test_tracker_adapter_linear.py` | Existing 16 tests — will be modified per decision #2 |
| `tests/unit/test_tracker_adapter_registry.py` | Existing 4 tests — read; modify only if needed |
| `pilots/acme-corp/pilot_profile.yaml` | `tracker_config.team_id` may swap if smoke runs |
| `.github/workflows/handoff-lint.yml` | Out of scope (finding #12 deferred) |

---

*Authored 2026-05-04 as the kickoff prompt for the next Maven OS session. Week-Two ticket (single-session, 2026-04-30) is documented at `docs/planning/MAVEN_OS_WEEK_TWO_PROMPT.md` with a STATUS header. Sprint Review reconciliation at `docs/planning/sprint_review_20260504.md`.*
