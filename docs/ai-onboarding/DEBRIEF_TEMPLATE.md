# Ceal — Session Debrief Template

> Use this prompt when Codex or Gemini completed work but did NOT create session notes. Paste it into any AI (Claude Cowork, Claude Code, Gemini, Codex) to generate notes from the git log.

---

## When to Use

- After a Codex async task completes and you see new commits on `main`
- After a Gemini session where notes weren't included in the commit
- During a Cowork catch-up session to document work done elsewhere
- When the scheduled "ceal-debrief" task runs automatically

## Debrief Prompt

Copy everything below the line and paste it as a prompt:

---

```
You are generating session notes for the Ceal project. Work was done by another AI (Codex or Gemini) and no session notes were created. Your job is to reconstruct what happened from the git log and diffs.

## Steps

1. Run: `git log --oneline --since="[START_DATE]" --until="[END_DATE]"`
   (Replace dates with the window you want to cover, e.g., "2026-04-02" to "2026-04-03")

2. For each commit not already documented in `docs/session_notes/`, run:
   `git show [HASH] --stat`
   `git show [HASH]` (read the full diff)

3. Check existing session notes:
   `ls docs/session_notes/`
   Compare commit hashes — skip any already documented.

4. For each undocumented commit (or group of related commits), create a session note at:
   `docs/session_notes/YYYY-MM-DD_short-description.md`

5. Use this format:

# Ceal Session Notes — [Day] [Date]

**Session type:** [Inferred from commits: sprint / bug fix / refactor / docs]
**AI platform:** [Inferred from commit style — Codex uses conventional commits, Gemini may vary]
**Commit(s):** [hash(es)]

## Objective
[Inferred from commit messages and diff content]

## Tasks Completed
| # | Task | Files | Status |
|---|------|-------|--------|
[One row per logical change]

## Files Changed
[From git show --stat]

## Test Results
| Metric | Value |
|--------|-------|
| Total tests | [Run pytest to get current count] |
| Passed | |
| Failed | |
| Lint errors | [Run ruff check src/ tests/] |

## Architecture Decisions
[Inferred from the diff — any new patterns, new dependencies, schema changes]

## What's NOT in This Session
[Inferred from what was changed vs what's still missing per PROJECT_CONTEXT.md]

## Career Translation (X-Y-Z Bullet)
> Accomplished [X] as measured by [Y], by doing [Z]

6. Commit the session note:
   `git add docs/session_notes/YYYY-MM-DD_short-description.md`
   `git commit -m "docs: add debrief session notes for [date] [platform] work"`
   `git push origin main`

## Rules
- Do NOT fabricate information. If you can't determine something from the diff, say "Unable to determine from diff."
- Do NOT modify any code files. This is a documentation-only task.
- If the commits span multiple days, create separate notes per day.
- Always run `pytest` and `ruff` to get current test/lint counts — don't guess.
```

---

## Usage Examples

**Cover yesterday's Codex work:**
Replace `[START_DATE]` with `2026-04-02` and `[END_DATE]` with `2026-04-03`.

**Cover all undocumented work since last known session:**
Replace the `git log` command with:
`git log --oneline docs/session_notes/ | head -1` to find the last documented commit, then:
`git log --oneline [LAST_DOCUMENTED_HASH]..HEAD`

**Run in Claude Code:**
Paste the prompt directly. Claude Code can run git commands and create files.

**Run in Cowork:**
Cowork can read the mounted repo but can't write to `.git/`. It will generate the notes content and provide paste-ready PowerShell commands for Josh to commit locally.
