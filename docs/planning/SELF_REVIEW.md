# Maven OS Week-One Miniature: Self-Review

**Scope under review:** `pilots/acme-corp/` tree, `tools/handoff_lint.py`,
`tools/tracker_adapter/`, `tests/unit/test_handoff_lint.py`,
`.github/workflows/handoff-lint.yml`.

**Lens applied:** Self-Review v1.2 (unsupported API names, undefined
thresholds, missing defaults, missing sample files, position-number
cross-refs, static test counts). Only [P1]/[P2] findings are tagged
[UNRESOLVED] below; [P3] items are listed for honesty but do not block.

## Designed vs Built

| Artifact | Designed | Built | Notes |
|---|---|---|---|
| 15-section handoff_spec.md with HTML-comment anchors | Yes | Yes | Addressed by name, not position. [UNVERIFIED] placeholders throughout. |
| pilot_profile.yaml modular gate flags | Yes | Yes | All module flags set to conservative defaults. No schema validator yet. |
| golden_corpus.jsonl with 20 cases, ≥30% adversarial | Yes | Yes | 7 happy / 6 edge / 7 adversarial = 35%. All inputs are `[UNVERIFIED] placeholder:` strings. |
| Single append-only ledger.jsonl | Yes | Yes | Empty file (0 bytes). Writer path not built this week. |
| handoff_lint.py CLI, 4 exit codes, 25% delta rule | Yes | Yes | PASS/BLOCK/ESCALATE/HARNESS_FAULT enforced in-process + via CLI. Delta computed as structural leaf-path symmetric difference. |
| tracker_adapter interface (no SDK imports outside) | Yes | Protocol only | Zero concrete adapters this week. Callers cannot be wired yet. |
| pytest coverage for all four exit paths | Yes | Yes | 15 tests, all green. Full suite: 332 passed, 0 regressions. |
| handoff-lint GitHub Actions job | Yes | Yes | Triggers on `pilots/**` plus the linter and its own tests. |
| Banned-term enforcement (IaC, Cloud Run, em dashes) | Not built | No | [UNRESOLVED P2]: see below. |

## [UNRESOLVED] Findings

1. **[RESOLVED 2026-04-24] Delta-rule baseline source wired to PR base branch.**
   CI now resolves the baseline via `handoff_lint.py
   --baseline-from-git-ref origin/${{ github.base_ref }}`. The 25%
   rule gates against the PR base branch tip of
   `pilots/<pilot>/handoff_spec.md`. New pilots (file absent on base)
   fall through to `delta_check=skipped_no_baseline` with an explicit
   stderr log. Tags and ledger artifacts are not used as baselines.
   Verified locally: 18 tests green (existing 15 + 3 new git-baseline
   paths), ruff clean, CLI smoke on the shipped handoff PASSes.
   Residual caveat: if a baseline file exists on base but its
   `schema_contract` block is unparseable, the linter still reports
   `delta_check=skipped_no_baseline` (pre-existing ambiguity, not
   introduced by this change). Follow-up: add a distinct
   `skipped_baseline_malformed` state in a separate diff.

2. **[RESOLVED 2026-04-30] tracker_adapter has a concrete Linear adapter.**
   Resolved by commit `6b05a8f`. `tools/tracker_adapter/linear.py`
   implements the Protocol's three methods against Linear's GraphQL
   API via httpx; `tools/tracker_adapter/registry.py` resolves
   `active_tracker: linear` to `LinearAdapter` at runtime;
   `pilots/acme-corp/pilot_profile.yaml` adds a `tracker_config`
   block with a placeholder `team_id`. Evidence: 20 new tests
   across `tests/unit/test_tracker_adapter_linear.py` (16) and
   `tests/unit/test_tracker_adapter_registry.py` (4); full suite
   355 passing locally, 0 regressions, ruff clean. The end-to-end
   smoke test in `test_tracker_adapter_registry.py` reads the
   actual `pilots/acme-corp/pilot_profile.yaml` and confirms the
   registry returns a `LinearAdapter` with the declared team_id.
   Residual caveats now tracked as findings #11, #13, #14, #15.

3. **[UNRESOLVED P2] Banned-term enforcement is not wired into the linter.**
   The master prompt forbids "Infrastructure as Code"/"IaC", "Cloud
   Run", and em dashes. The linter currently does not scan for these.
   Adding them is mechanical (one regex per term, BLOCK on match) but
   was not built this week.

4. **[UNRESOLVED P2] 25% delta threshold is a magic number.**
   `DELTA_ESCALATION_THRESHOLD_PCT = 25.0` lives in
   `tools/handoff_lint.py` with no ADR or YAML override. Changing it
   requires a code edit + PR. Should move to `pilot_profile.yaml`
   under a `governance.scope_change_threshold_pct` key so pilots can
   tune it with IM sign-off.

5. **[UNRESOLVED P2] Severity enum, verification_method allowlist, and
   required-section list are hardcoded.** `ALLOWED_SEVERITY`,
   `REQUIRED_SECTIONS`, and the 15-anchor list are frozensets in the
   linter. A schema-contract miniature should have a schema; the
   linter should read its own rules from a versioned file so drift
   between handoff_spec.md and linter expectations is itself
   detectable.

6. **[UNRESOLVED P2] Golden corpus is 100% placeholder.**
   All 20 `input` fields are `[UNVERIFIED] placeholder:` strings.
   This satisfies the schema and the ≥30% adversarial floor on count,
   but it does not yet test anything. First customer-contact action
   should be replacing these with real (or realistically shaped)
   inputs from pilot ticket history.

7. **[RESOLVED 2026-04-30] PyYAML pin documented via ADR-009.**
   Resolved by commit `09bf55c`. Full ADR at
   `docs/reference/ADR-009-pyyaml.md`; cross-referenced in
   `docs/CEAL_PROJECT_LEDGER.md` Decision Log. The pin is
   `PyYAML==6.0.3`; single consumer is `tools/handoff_lint.py`.

8. **[UNRESOLVED P2] Workflow verified by component, not end-to-end.**
   `act` is not installed on the local Windows environment. The
   three workflow steps (ruff, pytest, CLI smoke) were executed
   locally and all pass, but the workflow was not exercised through
   a GHA-equivalent runner. Failure modes specific to the Actions
   environment (checkout depth, path-filter semantics, cache key
   misses) are unverified.

9. **[P3] Test-count baseline drift vs. session prompt.**
   The session-open message asserted "93 tests, green" but the
   pre-existing suite was 317. The miniature was built against the
   real baseline (332 post-merge), not the stated one. Flag so the
   prompt can be refreshed; no build impact.

10. **[P3] `pilot_profile.yaml` has no validator.**
    Any typo in a module flag silently passes. A Pydantic model
    mirroring the Malleability Analysis Part D schema would catch
    this; deferred.

11. **[UNRESOLVED P2] Sync/async Protocol mismatch.**
    The `TrackerAdapter` Protocol declares sync method signatures
    (`def`, not `async def`) while the rest of Ceal is async
    (asyncio + SQLAlchemy 2.0 async + httpx async). The Linear
    adapter is sync because the Protocol is sync; making it async
    would either require modifying the Protocol (intentionally out
    of scope this session) or wrapping calls in a thread executor.
    A future ADR should decide whether to async-ify the Protocol
    or keep sync as the canonical contract.

12. **[UNRESOLVED P2] handoff-lint workflow hardcoded to acme-corp.**
    `.github/workflows/handoff-lint.yml` runs the linter on
    `pilots/acme-corp/handoff_spec.md` only. The path filter
    triggers on `pilots/**`, so a new pilot's PR will fire the
    workflow but the action is hardcoded to acme-corp.
    Generalization (loop over `pilots/*/handoff_spec.md` or use a
    matrix strategy) is a follow-up.

13. **[UNRESOLVED P1] Linear GraphQL queries not live-validated.**
    The five GraphQL operations in `tools/tracker_adapter/linear.py`
    (FindIssueByTitlePrefix, GetIssue, ListStaleIssues,
    CreateIssue, UpdateIssue) are written against the public Linear
    schema as documented late 2025 and exercised at the HTTP-mock
    layer only. A live smoke against a throwaway Linear workspace
    with a real `LINEAR_API_KEY` is needed to catch any schema
    drift before this adapter sees production traffic.

14. **[UNRESOLVED P2] Linear adapter operational gaps.**
    Three known production gaps in the first concrete adapter:
    (a) `push_payload`'s title-prefix idempotency is fragile if a
    user manually edits a Linear issue title and removes the
    `[MavenOS:...]` prefix; the next push will create a duplicate.
    (b) No retry on rate limit -- `LinearRateLimitError` raises
    immediately on HTTP 429. (c) `list_stale` does not paginate;
    Linear's `issues` query returns at most ~50 nodes per page by
    default, so teams with more stale issues will silently lose
    the tail. All three are addressable but out of scope for the
    first concrete adapter.

15. **[UNRESOLVED P2] Canonical ImplementationState dict is a stub.**
    Both `read_status` and `list_stale` return a dict whose schema
    is referenced by `Maven_OS_Enterprise_Malleability_Analysis.md`
    Part C. That document is not in-repo at the time of writing.
    The current dict shape (`ticket_id`, `identifier`, `title`,
    `description`, `state`, `assignee`, `labels`, `priority`,
    `created_at`, `updated_at`, `url`, `raw`) is a working stub
    and may evolve when Part C lands. Downstream consumers should
    not depend on the exact key set yet.

## Honest Next Step

Findings **#1** (CI baseline), **#2** (concrete tracker adapter),
and **#7** (PyYAML ADR) are now closed. The next-priority items,
ordered by risk:

1. **Finding #13** -- live Linear smoke against a throwaway
   workspace to validate the GraphQL queries before any production
   traffic.
2. **Finding #11** -- sync/async ADR for the `tracker_adapter`
   Protocol; needed before any async-context caller wires the
   Linear adapter.
3. **Finding #6** -- replace placeholder `golden_corpus` rows with
   realistically shaped inputs from real pilot ticket history.
4. **Findings #3, #4, #5, #12** -- mechanical P2 hardening
   (banned-term enforcement, 25% threshold to per-pilot YAML,
   schema-driven enums, workflow generalization).
5. **Findings #14, #15** -- operational gaps in the Linear adapter
   (idempotency edge, retry, pagination, canonical schema stub).
6. **Findings #8, #10** -- workflow end-to-end verification and
   pilot_profile validator.

Finding #9 (P3 test-count drift) is informational only.
