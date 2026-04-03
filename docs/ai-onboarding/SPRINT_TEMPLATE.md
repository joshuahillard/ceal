# Céal — Sprint Prompt Template

> Copy this template when creating a new sprint prompt. Fill in each section. This structure (the "8-Pillar Framework") has been validated across 6 sprints with zero regressions when followed correctly.

---

```markdown
# Céal Sprint [N] — [Title]

## CONTEXT
You are working on the Céal project — an AI-powered career signal engine.
The project root is the `ceal/` directory containing `src/`, `tests/`, `pyproject.toml`, `requirements.txt`.

**Read these onboarding docs before starting:**
- `docs/ai-onboarding/PROJECT_CONTEXT.md` — Architecture, file inventory, current state
- `docs/ai-onboarding/PERSONAS.md` — Stakeholder personas and constraints
- `docs/ai-onboarding/RULES.md` — Engineering rules and incident history

**Branch state**: You are on `main`. Recent commits:
[List last 3-5 commits or describe what's on main]

**This sprint's scope**: [What this sprint adds/fixes]

---

## CRITICAL RULES (Anti-Hallucination)

[Copy from RULES.md, then add sprint-specific rules here]

---

## PRE-FLIGHT CHECK

```bash
# 1. Verify working directory
pwd

# 2. Verify branch
git branch --show-current

# 3. Recent commits
git log --oneline -5

# 4. Uncommitted changes
git status

# 5. Run tests
pytest tests/ -v 2>&1 | tail -20

# 6. Verify lint
ruff check src/ tests/

# 7. Verify file structure
[List the specific files this sprint depends on]

# 8. Verify files this sprint will CREATE don't exist yet
[ls checks for each new file]
```

---

## FILE INVENTORY

### Files to Create (new)
| # | File | Lines (approx) | Purpose |
|---|------|----------------|---------|

### Files to Modify (existing)
| # | File | Changes |
|---|------|---------|

---

## TASK 0: Read All Files That Will Be Modified

Before writing ANY code, read these files IN FULL:
```
[list all files to be modified]
```

Also read for reference (do not modify):
```
[list files needed for context]
```

---

## TASK N: [Task Name]

**Read first**: [file(s)]

**Persona**: [ETL Architect / QA Lead / AI Architect / DPM]

[Description of what to do, with code scaffolds if appropriate]

**Verification**:
```bash
[specific command to verify this task worked]
```

---

## FINAL VERIFICATION

```bash
pytest tests/ -v
ruff check src/ tests/
pytest tests/ --co -q 2>&1 | tail -3
```

---

## COMMIT

```bash
git add [specific files]
git status
git commit -m "[type]: [description]

[body]"

git tag -a [version] -m "[Sprint N: description]"
git push origin main --tags
```

---

## COMPLETION CHECKLIST

- [ ] [Checklist item per deliverable]
- [ ] `pytest tests/ -v` — ALL pass
- [ ] `ruff check src/ tests/` — 0 errors
- [ ] Committed and tagged
- [ ] Pushed to origin/main
```
