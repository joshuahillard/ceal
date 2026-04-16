# Ceal Session Notes — Thursday April 16, 2026

**Session type:** Documentation reconciliation / Claude Code fast-path fix
**Branch:** `main`
**Focus:** Correct stale AI entrypoints, refresh canonical repo-state counts, and document why the reconciliation was required

---

## Why This Session Happened

The active onboarding and prompt documents had drifted from the live repo. That drift created three operational problems:

1. Claude Code and companion onboarding docs still pointed at deleted paths such as `src/pipeline.py`, `src/scraper/`, and `src/normalizer.py`.
2. Canonical prompt examples still advertised Sprint 10-era repo state (`246` passing tests) even though the current verified state is `317` passing tests.
3. Sprint prompt guidance still referenced non-canonical or missing locations, which made it harder to decide what was safe to preserve, archive, or delete.

The result was avoidable latency. Every new AI session had to re-verify repo structure before useful work could begin.

---

## What Changed

- Corrected the active Claude Code entrypoints in `CLAUDE.md` and `docs/prompts/CLAUDE_CODE_MASTER_PROMPT.md` to reflect the current source tree and canonical docs locations.
- Updated `docs/prompts/RUNTIME_PROMPTS.md` so the compact runtime contract matches the current rules and current repo state.
- Refreshed `docs/prompts/PORTABLE_PERSONA_LIBRARY.md` to point at real source files and the current verified test count.
- Corrected sprint-prompt locations in `docs/ai-onboarding/CODEX_SYSTEM_PROMPT.md` and `docs/ai-onboarding/GEMINI_SYSTEM_PROMPT.md`.
- Updated `docs/ai-onboarding/PROJECT_CONTEXT.md` to include the current test file counts and the canonical `docs/sprints/` location.
- Added a Sprint 11 ledger entry and refreshed current cumulative metrics in `docs/CEAL_PROJECT_LEDGER.md`.
- Updated `docs/reference/SETUP_INSTRUCTIONS.md`, `docs/TASK_PORTFOLIO_DASHBOARD.md`, and the `.gitignore` comment so the active docs no longer point at stale locations or stale counts.

---

## Verification

- `python -m pytest --collect-only -q`
- `python -m pytest --tb=no -q`
- `python -m ruff check src tests`
- Targeted searches across the active Claude-facing docs for stale paths and stale counts

Verified current repo-state values used in the reconciliation:

- Tests collected: `317`
- Tests passing: `317`
- Ruff: clean
- Unit test files: `23`
- Integration test files: `6`
- Latest release tag: `v2.10.0-sprint10-pdf-generation`

Scope note:

- This verification covered the local default SQLite test run (`python -m pytest ...`) and lint.
- It did not prove PostgreSQL CI was green.
- As of April 16, 2026, `origin/main` still fails the `DB Tests (PostgreSQL)` GitHub Actions job on the schema-loader multi-statement asyncpg error (`cannot insert multiple commands into a prepared statement`).

---

## Why These Changes Matter

These were not cosmetic edits. The Claude Code prompt surface is operational infrastructure for this repo. If the entrypoints are wrong, every future session pays a tax in duplicated inspection, false starts, and trust rebuilding.

The fast-path fix restores one practical rule:

> If a document is used to start AI work, it must match the live repo before it can be treated as canonical.

That rule is now reflected in the active docs and in the ledger entry for Sprint 11.

---

## Remaining Follow-Up

- Top-level historical prompt dumps and loose session notes still need an archive-or-delete decision before destructive cleanup.
- `docs/sprints/sprint6-combined.md` is still semantically misnamed relative to its content and should be renamed or explicitly re-framed in a later pass.
