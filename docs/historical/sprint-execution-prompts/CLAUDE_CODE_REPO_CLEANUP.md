# Céal — Repo Cleanup + AI Onboarding Commit

## CONTEXT

This is a housekeeping commit. The `docs/ai-onboarding/` folder has been created with onboarding docs for Claude, Codex, and Gemini. This prompt handles:
1. Moving orphaned sprint prompts into the docs structure
2. Updating `.gitignore` for cleanliness
3. Removing files that shouldn't be tracked
4. Committing the AI onboarding package

## PRE-FLIGHT

```bash
pwd
git branch --show-current
git status
```

## TASK 1: Update `.gitignore`

**Read first**: `.gitignore`

Append these entries (do NOT remove existing entries):

```
# Ruff cache
.ruff_cache/

# OS files
desktop.ini
Thumbs.db

# Local utility scripts
push_to_github.sh

# Temporary sprint prompts (canonical versions live in docs/ai-onboarding/sprints/)
CLAUDE_CODE_*.md
```

## TASK 2: Move Sprint Prompts

Create the `docs/ai-onboarding/sprints/` directory, then move:

```bash
mkdir -p docs/ai-onboarding/sprints

# Move the completed sprint prompt (for reference)
mv CLAUDE_CODE_SPRINT6_GAPFILL.md docs/ai-onboarding/sprints/sprint6-combined.md 2>/dev/null || true
```

## TASK 3: Remove Tracked Files That Should Be Ignored

```bash
# Remove from git tracking (not from disk)
git rm --cached push_to_github.sh 2>/dev/null || true
git rm --cached CLAUDE_CODE_SPRINT6_GAPFILL.md 2>/dev/null || true
git rm --cached .ruff_cache -r 2>/dev/null || true
```

## TASK 4: Verify the AI Onboarding Docs Exist

```bash
ls docs/ai-onboarding/PROJECT_CONTEXT.md
ls docs/ai-onboarding/PERSONAS.md
ls docs/ai-onboarding/RULES.md
ls docs/ai-onboarding/SPRINT_TEMPLATE.md
ls docs/ai-onboarding/CLAUDE_SYSTEM_PROMPT.md
ls docs/ai-onboarding/CODEX_SYSTEM_PROMPT.md
ls docs/ai-onboarding/GEMINI_SYSTEM_PROMPT.md
```

## TASK 5: Run Tests + Lint

```bash
pytest tests/ -v 2>&1 | tail -10
ruff check src/ tests/
```

## TASK 6: Commit

```bash
git add .gitignore
git add docs/ai-onboarding/
git add docs/ai-onboarding/sprints/ 2>/dev/null || true
git status

git commit -m "docs: add multi-AI onboarding package for Claude, Codex, and Gemini

- Add docs/ai-onboarding/ with project context, personas, rules, sprint template
- Add platform-specific system prompts (Claude, Codex, Gemini)
- Update .gitignore for ruff cache, OS files, local scripts
- Move orphaned sprint prompts to docs/ai-onboarding/sprints/"

git push origin main
```
