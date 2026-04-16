# Pre-Reset Artifact Rescue — 2026-04-16

This note records the historical rescue performed before deleting any remaining top-level documentation trees outside the git repo root.

## Scope

Rescued into `docs/historical/`:

- `Ceal/prompts/` loose sprint execution prompts
- Unique or materially different files from `Ceal/session_notes/`

Not yet deleted by this note:

- Top-level duplicate trees such as `Ceal/docs/`, `Ceal/Foundations/`, `Ceal/Governance/`, `Ceal/Program-Management/`, and `Ceal/design-docs/`

## Rationale

The top-level prompt files are not redundant copies of the current `docs/sprints/` files. They reflect the original pre-reset sprint numbering and planning workflow. At least some files have semantic rather than cosmetic drift from the post-reset canonical prompts.

The loose session notes also contain pre-reset history that is either absent from, or materially different than, the canonical in-repo `docs/session_notes/` collection.

Deleting those trees without a rescue step would remove historically meaningful portfolio artifacts.

## Rescue Policy

- Preserve original filenames for historical authenticity.
- Keep rescued sprint prompts under `docs/historical/sprint-execution-prompts/`.
- Keep rescued loose session notes under `docs/historical/session-notes-pre-reset/`.
- Do not rescue exact duplicates of files already tracked canonically in repo.

## Known Remaining Follow-Up

- `docs/sprints/sprint6-combined.md` is still semantically misnamed relative to its content and should be reconciled in a later pass.
- After the rescued files are reviewed, the remaining top-level duplicate trees can be deleted with lower risk.
