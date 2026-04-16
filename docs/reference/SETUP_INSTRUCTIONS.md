# How to Set Up the v1.1 Prompt System in Claude Code
**Step-by-step instructions for Josh**
*April 3, 2026*

---

## Part 1: Set Up Claude Code for Ceal (One-Time)

### Step 1: Open the Master Prompt

On your machine, open this file in any text editor:

```
C:\Users\joshb\Documents\GitHub\ceal\docs\CLAUDE_CODE_MASTER_PROMPT.md
```

This is the file that just got pushed in commit `e0b8fce`.

### Step 2: Copy the Contents

Select everything in that file and copy it to your clipboard.

### Step 3: Paste into Claude Code

Open Claude Code and go to your Ceal project settings. You have two options depending on how you're set up:

**Option A — CLAUDE.md file (recommended):**
Create or replace the file at the root of your Ceal repo:

```
C:\Users\joshb\Documents\GitHub\ceal\CLAUDE.md
```

Paste the full contents of `CLAUDE_CODE_MASTER_PROMPT.md` into that file. Claude Code reads this automatically at the start of every session.

**Option B — Project custom instructions:**
In Claude Code, open Settings > Project Instructions for your Ceal project and paste the contents there. This works the same way but lives outside the repo.

Option A is better because it's version-controlled and travels with the repo.

### Step 4: Verify

Start a new Claude Code session in the Ceal project. Ask it: "What project are you working on and what are the rules?" It should respond with Ceal's core contract details without you providing any extra context.

---

## Part 2: How to Use Task Cards (Daily Workflow)

This is how you give Claude Code work to do, going forward.

### Step 1: Open the Runtime Prompts Reference

Keep this file open in a tab while you work:

```
docs/prompts/RUNTIME_PROMPTS.md
```

This has the Task Card template, all five Mode Packs, the Snapshot block, and worked examples.

### Step 2: Fill In a Task Card

Copy the Task Card template and fill in the brackets. Here's a real example:

```
TASK: Add Alembic auto-migration on app startup

Goal: Wire Alembic to run pending migrations when the app starts, so new schema changes apply automatically.
Scope: src/models/database.py, alembic/env.py
Out of scope: Web routes, tailoring engine, CLI flags.

Inspect first:
- src/models/database.py::init_db
- alembic/env.py::run_migrations_online

Acceptance:
- App startup runs pending Alembic migrations before serving requests
- Existing DB with missing columns gets updated without data loss
- New empty DB gets full schema from migrations

Verify:
- python -m pytest tests/integration/ -v -k "database"
- ruff check src/models/

Deliver:
- implement changes
- summarize touched files
- report verification honestly
```

### Step 3: Add a Mode Pack If Needed

If your task touches a specific domain, copy the relevant Mode Pack from RUNTIME_PROMPTS.md and paste it after the Task Card. You don't need to modify the Mode Pack — just paste it as-is.

For the example above, you'd add `MODE: db` since it's a database task.

### Step 4: Add a Snapshot If Needed

Most tasks don't need this. Only add it when the task depends on knowing the current branch, tag, or failing tests. Copy the Snapshot block and fill in current values:

```
SNAPSHOT:
- Branch: main | Latest release tag: v2.10.0-sprint10-pdf-generation
- Tests: 317 passing, 0 warnings, ruff clean
- Known issues: TD-003 — existing DBs missing regime columns
```

### Step 5: Paste and Go

Paste the filled-in Task Card (plus Mode Pack and Snapshot if needed) into Claude Code. That's your entire prompt. No preamble, no "hey Claude," no re-explaining the project. The CLAUDE.md file already gave it the Core Contract.

---

## Part 3: Multi-Message Tasks

When a task is too big for one message (like a full sprint), use the continuation format.

### Message 1
Paste the Task Card as normal, but add at the end:

```
Implement Part A only: [describe Part A]. Stop after committing.
```

### Message 2
After Claude Code commits Part A, paste:

```
Continue from commit [hash].
Part A done. Now: [describe Part B].
State: [1-2 sentences about what changed].
```

### Message 3+
Same pattern. Keep continuations short — under 3 lines. Claude Code still has the full conversation context from Message 1, so you don't need to repeat anything.

---

## Part 4: After Every Sprint (Maintenance)

### Update the Snapshot Values

Open `RUNTIME_PROMPTS.md` and update the example Snapshot block with current values (tag, test count, known issues). This way you can copy-paste it fresh next time.

### Update the Project Ledger

Open `CEAL_PROJECT_LEDGER.md` and append:
- A new timeline entry for the sprint
- Any new ADRs (architectural decisions)
- A retrospective (what went well, what went wrong, lesson)
- Updated cumulative metrics
- A new X-Y-Z resume bullet

### Update the Core Contract (rarely)

Only if the tech stack changed or a new hard rule was adopted. Open `CLAUDE_CODE_MASTER_PROMPT.md` (and `CLAUDE.md` if using Option A) and update the relevant line.

---

## Part 5: Setting Up a New Project (Future Use)

### Step 1: Copy the Templates

Copy the entire `docs/templates/` folder from the Ceal repo into your new project's `docs/` folder.

### Step 2: Rename the Files

Remove "TEMPLATE" from each filename. For example:
- `PROJECT_LEDGER_TEMPLATE.md` becomes `PROJECT_LEDGER.md`
- `RUNTIME_PROMPTS_TEMPLATE.md` becomes `RUNTIME_PROMPTS.md`

### Step 3: Fill In the Brackets

Start with `RUNTIME_PROMPTS` — fill in the Core Contract (project description, stack, rules, key paths). This takes about 15 minutes.

Then fill in `CLAUDE_CODE_MASTER_PROMPT` using the same Core Contract info.

Then fill in the Project Binding section at the bottom of `PERSONA_LIBRARY` (which personas own which files in this project).

Start the `PROJECT_LEDGER` with a Phase 0 entry.

The `PROMPT_ARCHITECTURE` doc only needs the project name filled in — the design rationale is the same regardless of project.

### Step 4: Set Up Claude Code

Same as Part 1 — copy the filled-in `CLAUDE_CODE_MASTER_PROMPT.md` into a `CLAUDE.md` file at the root of the new project's repo.

---

## Quick Reference Card

| I want to... | Do this |
|---------------|---------|
| Start a Claude Code session | CLAUDE.md handles it automatically |
| Give Claude Code a task | Fill in a Task Card, paste it |
| Task touches the database | Add MODE: db after the Task Card |
| Task touches LLM/AI code | Add MODE: ml after the Task Card |
| Task touches web routes | Add MODE: web after the Task Card |
| Task is resume/career related | Add MODE: product after the Task Card |
| Task touches CI/Docker/deploy | Add MODE: infra after the Task Card |
| Task depends on current branch/tag | Add a SNAPSHOT block |
| Task is too big for one message | Use the continuation format |
| Sprint is done | Update Ledger + Snapshot values |
| Starting a brand new project | Copy templates/, fill brackets, create CLAUDE.md |
