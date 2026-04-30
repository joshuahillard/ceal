# Ceal Sprint 12 Tracker-Adapter Prompt
**Ready-to-paste Claude prompt for the next concrete project step**
*Version: 1.0 | April 24, 2026*

---

## Purpose

This is the next execution prompt after baseline resolution for
`handoff_lint` was wired in CI.

It keeps the same rationale:
- prevent hallucinations
- stay bound to repo artifacts
- fail safe on missing evidence
- optimize for compact prompt text

It does **not** ask for more prompt work. It asks Claude to move the project
forward by closing the next highest-value open P1 in the pilot track:
**a first concrete tracker adapter, preferably Linear**.

---

## Paste This Into Claude

```text
CEAL S12 PILOT MASTER v1.2

Use this file as the canonical Sprint 12 pilot prompt source:
- ceal/docs/prompts/SPRINT12_PILOT_PROMPTS.md

Verdict priority:
- HARNESS_FAULT > BLOCK > ESCALATE > PASS

TASK: Implement the first concrete tracker adapter (Linear)

Goal:
Add a concrete adapter under `ceal/tools/tracker_adapter/` so the declared
`active_tracker: "linear"` in `ceal/pilots/acme-corp/pilot_profile.yaml`
resolves to real code instead of a Protocol-only placeholder.

Why this is next:
- `ceal/docs/planning/SELF_REVIEW.md` identifies the Protocol-only tracker boundary as the remaining unresolved P1.
- Sprint 12 only becomes a usable pilot-platform if one tracker path actually resolves.
- `linear` is already the declared active tracker in the pilot profile, so it is the shortest path to consistency.

Source of truth, in order:
1. ceal/tools/tracker_adapter/__init__.py
2. ceal/pilots/acme-corp/pilot_profile.yaml
3. ceal/docs/planning/SELF_REVIEW.md
4. ceal/pilots/acme-corp/handoff_spec.md
5. ceal/docs/prompts/SPRINT12_PILOT_PROMPTS.md

Hard rules:
- Never invent customer facts, citations, tracker IDs, tool calls, or payload fields.
- Keep diffs minimal and local to this task.
- Do not import tracker SDKs outside `ceal/tools/tracker_adapter/`.
- Prefer a small, testable adapter plus resolver path over a broad framework.
- If the real Linear API shape is not documented in-repo, build a boundary that is explicit about placeholders and environment assumptions rather than guessing undocumented payloads.
- Preserve `[UNVERIFIED]` markers in pilot artifacts unless an allowed source proves otherwise.
- Treat `ceal/docs/prompts/SPRINT12_PILOT_PROMPTS.md` as canonical for pilot guardrail semantics.

Inspect first:
- ceal/tools/tracker_adapter/__init__.py
- ceal/pilots/acme-corp/pilot_profile.yaml
- ceal/docs/planning/SELF_REVIEW.md
- ceal/pilots/acme-corp/handoff_spec.md
- any existing tests that would be the natural home for tracker-adapter coverage

Acceptance:
- `ceal/tools/tracker_adapter/linear.py` exists and implements the `TrackerAdapter` Protocol.
- There is a small resolver path so `active_tracker: "linear"` can map to the concrete adapter without SDK leakage outside the package.
- The adapter surface is explicit about required env vars / auth assumptions.
- Tests cover resolver behavior and the adapter contract enough to prevent silent regression.
- Docs touched explain clearly that this is the first concrete adapter, not a full multi-tracker framework.

Prefer this implementation shape unless the repo proves a better one already exists:
- `linear.py` with a small HTTP client boundary using stdlib/httpx already present in the repo
- a `get_tracker_adapter(name: str)` style resolver in `ceal/tools/tracker_adapter/__init__.py`
- unit tests with mocked HTTP responses; no live API calls

Out of scope:
- implementing clickup/notion/jira
- building a full state machine
- changing pilot_profile semantics beyond what is required to resolve `linear`
- speculative support for undocumented Linear fields

Verify:
- targeted tests for the tracker adapter module
- ruff on touched files
- report honestly what ran

Deliver:
- implement the change
- summarize touched files
- report verification
- call out any remaining open risk briefly
```

---

## Notes

- This prompt assumes the prompt-pack work is complete and Claude should stay
  in code/workflow execution mode.
- If the Linear adapter lands cleanly, the next likely tasks are either
  corpus realism (replace placeholder golden rows) or a pilot-profile validator.
