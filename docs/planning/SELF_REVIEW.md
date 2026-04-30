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

2. **[UNRESOLVED P1] tracker_adapter ships as Protocol-only.**
   No `linear.py`/`clickup.py`/`notion.py`/`jira.py` exists, so
   `active_tracker: linear` in pilot_profile.yaml has no resolver.
   Any caller that imports a concrete adapter will ImportError. The
   Control-Surface Boundary is preserved (no SDK leakage) but the
   boundary encloses empty space.

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

7. **[UNRESOLVED P2] PyYAML added without an ADR.**
   `requirements.txt` now pins `PyYAML==6.0.3`. It was previously
   transitively installed. Adding a top-level dep is a supply-chain
   event and deserves at least a one-line decision record under
   `docs/reference/` before the week closes.

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

## Honest Next Step

Before adding more surface area, close finding **#1** (baseline
resolution in CI) and **#2** (at least one concrete tracker adapter,
probably Linear given it is the declared `active_tracker`). Without
those two, the linter is a gate that never actually gates, and the
pilot_profile's `active_tracker` points at a method that does not
resolve. Everything else in this list is load-bearing but can wait
one week.
