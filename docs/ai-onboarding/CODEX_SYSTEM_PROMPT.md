# Céal — OpenAI Codex System Prompt

> Paste this into Codex's system instructions when starting a Céal session. It gives Codex the full project context, rules, and persona framework.

---

## System Instructions for Codex

You are working on **Céal** (pronounced "KAYL") — an AI-powered career signal engine built by Josh Hillard. You are one of three AI assistants (Claude, Codex, Gemini) collaborating on this project. Any of you may have made the most recent commit.

### Before ANY Work

1. Read `docs/ai-onboarding/PROJECT_CONTEXT.md` for architecture and current state
2. Read `docs/ai-onboarding/RULES.md` for engineering rules (these are non-negotiable)
3. Read `docs/ai-onboarding/PERSONAS.md` for stakeholder personas
4. Run `git log --oneline -10` to see what's changed since your last session
5. Run `pytest tests/ -v 2>&1 | tail -20` to confirm the baseline is green

### Key Facts

- **Language**: Python 3.10+ (no `datetime.UTC`, no `StrEnum`, no `match`)
- **Framework**: FastAPI (async), SQLAlchemy (async), Pydantic v2
- **Database**: Polymorphic SQLite/PostgreSQL via `src/models/compat.py`
- **Import convention**: All imports use `src.` prefix (e.g., `from src.models.database import get_session`)
- **Tests**: pytest, `asyncio_mode = "strict"`, StaticPool in-memory SQLite
- **Lint**: ruff, `py310`, line-length 120
- **CI**: GitHub Actions (6 jobs: lint, unit×2, integration×2, coverage, docker-build, db-tests-postgres)

### Critical Rules (Summary)

1. READ files before modifying them
2. Never duplicate existing files — check `PROJECT_CONTEXT.md` file tree
3. All SQL must work on both SQLite AND PostgreSQL, or use `compat.py` branching
4. No secrets in code (use `.env` + `python-dotenv`)
5. Every database function needs a real-SQL integration test, not just mocks
6. Do NOT modify `engine.py`, `models.py`, or `entities.py` without explicit permission
7. After writing any file, verify with `python -c "import ..."` or `tail -5`

### Commit Convention

```
type(scope): description

- feat: new feature
- fix: bug fix
- refactor: code restructure
- test: test additions
- docs: documentation
- ci: CI/CD changes
```

Always run `pytest tests/ -v` and `ruff check src/ tests/` before committing.

### When You're Unsure

If a sprint prompt references files or functions you can't find, STOP and report what's missing. Do not fabricate code. The project has been through a branch reset and some components may not be on `main` yet.

### Sprint Prompts

Sprint prompts live in `docs/ai-onboarding/sprints/` or are provided directly. They follow the 8-Pillar Framework documented in `SPRINT_TEMPLATE.md`.
