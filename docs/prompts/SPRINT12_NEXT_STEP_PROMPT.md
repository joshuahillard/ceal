# Ceal Sprint 12 Next-Step Prompt
**Ready-to-paste Claude prompt for the next concrete project step**
*Version: 1.0 | April 24, 2026*

---

## Purpose

This is the next execution prompt after the Sprint 12 pilot guardrail pack was
stabilized at `v1.2`.

It keeps the same rationale:
- prevent hallucinations
- stay bound to repo artifacts
- fail safe on missing evidence
- optimize for compact prompt text

It does **not** ask for more prompt work. It asks Claude to move the project
forward by closing the highest-value open P1 in the pilot track:
**baseline resolution for handoff-lint in CI**.

---

## Paste This Into Claude

```text
CEAL S12 PILOT MASTER v1.2

Use this file as the canonical Sprint 12 pilot prompt source:
- ceal/docs/prompts/SPRINT12_PILOT_PROMPTS.md

Verdict priority:
- HARNESS_FAULT > BLOCK > ESCALATE > PASS

TASK: Wire handoff-lint baseline resolution in CI

Goal:
Make the handoff-lint workflow resolve a real prior baseline for
`ceal/pilots/<pilot>/handoff_spec.md` on pull requests, so the 25 percent
schema-delta rule actually gates changes instead of silently skipping with
`delta_check=skipped_no_baseline`.

Why this is next:
- `docs/planning/SELF_REVIEW.md` identifies baseline resolution as an unresolved P1.
- The pilot-platform direction is only credible if the linter can compare a changed handoff to a real previous revision.
- This is the shortest path from prompt hardening to an actually enforced operational guardrail.

Source of truth, in order:
1. ceal/pilots/acme-corp/handoff_spec.md
2. ceal/pilots/acme-corp/pilot_profile.yaml
3. ceal/pilots/acme-corp/golden_corpus.jsonl
4. ceal/pilots/acme-corp/ledger.jsonl
5. ceal/docs/planning/SELF_REVIEW.md
6. ceal/tools/handoff_lint.py
7. ceal/.github/workflows/handoff-lint.yml

Hard rules:
- Never invent customer facts, citations, KB IDs, tracker IDs, tool calls, or payload fields.
- Keep diffs minimal and local to this task.
- Do not weaken the linter to make CI green.
- If no prior baseline exists on the PR base, handle that explicitly and fail safe only when required.
- Preserve `[UNVERIFIED]` markers unless an allowed source proves otherwise.
- Treat `ceal/docs/prompts/SPRINT12_PILOT_PROMPTS.md` as canonical for pilot guardrail semantics.

Inspect first:
- ceal/.github/workflows/handoff-lint.yml
- ceal/tools/handoff_lint.py
- ceal/tests/unit/test_handoff_lint.py
- ceal/docs/planning/SELF_REVIEW.md
- ceal/pilots/acme-corp/handoff_spec.md

Acceptance:
- PR workflow resolves a prior `handoff_spec.md` baseline from the PR base branch or base commit when one exists.
- The workflow passes `--against` to `python -m tools.handoff_lint` when a baseline exists.
- The no-baseline case is explicit and intentional, not accidental.
- Tests cover the baseline-resolution behavior enough to prevent silent regression.
- Any docs touched explain the chosen baseline policy in one clear place.

Prefer this policy unless the repo proves a better one already exists:
- Compare the changed handoff against the version on the PR base branch (`origin/main` / base SHA), not tags and not a future ledger artifact.

Verify:
- targeted tests for `tests/unit/test_handoff_lint.py`
- any workflow-local or script-level verification needed for the baseline path
- report honestly what ran

Deliver:
- implement the change
- summarize touched files
- report verification
- call out any remaining open risk briefly
```

---

## Notes

- This prompt assumes the prompt-pack work is complete and Claude should move
  back into code and workflow execution.
- If baseline resolution lands cleanly, the next likely task is the second
  unresolved P1 from `SELF_REVIEW.md`: a concrete tracker adapter.
