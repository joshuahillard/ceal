# Ceal Session Notes — Wednesday April 2, 2026 (Continuation)

**Session type:** Deep work block — Branch merge + Sprint 6 combined + Multi-AI onboarding
**Personas active:** DPM (lead), Backend Engineer, AI Architect, QA Lead
**Preceded by:** `2026-04-02_sprint6-docker-cloudsql.md` (Sprint 6 infra)

---

## Executive Summary

Merged the `codex/semantic-fidelity-guardrail` branch to production, verified Phase 2 changes, executed a combined Sprint 6 gap-fill + Docker/Cloud SQL reimplementation prompt, then built a complete multi-AI onboarding package (`docs/ai-onboarding/`) so that Claude, Codex, and Gemini can all operate on the repo with full context. Repo cleanup commit pushed.

---

## Session Timeline

### Block 1: Branch Merge + Phase 2 Verification (Cowork)

**Objective:** Merge `codex/semantic-fidelity-guardrail` to `main`, verify Phase 2 tailoring changes.

**Problem:** Cowork session could not write to `.git/index.lock` due to mounted filesystem restrictions.
**Resolution:** Provided paste-ready PowerShell merge commands for Josh to run locally.

**Findings during verification:**
- `src/tailoring/engine.py` — Guardrail v1.1 confirmed: `_extract_metric_tokens()`, `_extract_anchor_tokens()`, `_semantic_fidelity_issues()`, `strip_code_fences()`, `PROMPT_VERSION = "v1.1"`
- `src/tailoring/db_models.py` — Previously truncated at `# Idempotency: o`, missing `__table_args__` on `SkillGapTable`. Fixed by Sprint 6.
- `src/models/schema.sql` — All 11 tables present (7 Phase 1 + 4 Phase 2)

**Stakeholder meeting outcome:** Personas agreed to combine Sprint 6 (gap-fill) and Sprint 7 (Docker + Cloud SQL) into a single prompt to minimize context-switching and API usage.

### Block 2: Sprint 6 Combined Prompt Creation (Cowork)

**Prompt:** `CLAUDE_CODE_SPRINT6_COMBINED.md`

**Structure — 3 parts, 13 tasks, linear execution:**
- **Part A (Gap-Fill):** db_models.py truncation fix, Phase 2 DDL, persistence test
- **Part B (Docker + Cloud SQL):** compat.py, database.py upgrade, health endpoint, schema_postgres.sql, Dockerfile, docker-compose.yml, .env.example, deploy/cloudrun.sh, CI updates
- **Part C (Verification):** lint, test, commit, push

**Key design decision:** Part A included self-skip logic — pre-flight checks could detect if gap-fill was already done (it was, via commit `a123b96`), skipping directly to Part B.

### Block 3: Sprint 6 Execution (Claude Code on Josh's machine)

**Result:** All tasks completed successfully.
- Pre-flight correctly identified Part A was already resolved
- Part B shipped all Docker + Cloud SQL infrastructure
- **Commit:** `98177d4`
- **Tag:** `v2.6.0-sprint6-infra`
- **179 tests passing**, ruff clean
- Pushed to `origin/main`

*(Full execution details in `2026-04-02_sprint6-docker-cloudsql.md`)*

### Block 4: Repo Cleanup (Claude Code)

**Prompt:** `CLAUDE_CODE_REPO_CLEANUP.md`
- Updated `.gitignore` (IDE files, env, build artifacts)
- Moved orphaned sprint prompts to `docs/ai-onboarding/sprints/`
- Removed tracked files that should be ignored

### Block 5: Multi-AI Onboarding Package (Cowork + Claude Code)

**Objective:** Create in-repo documentation so Codex, Gemini, and Claude can all operate on the project with full context after `git clone`/`git pull`.

**Usage modes selected (all 4):**
1. Full sprint execution
2. Code review / QA
3. Consultation
4. Redundancy / failover

**7 documents created in `docs/ai-onboarding/`:**

| File | Purpose | Key Content |
|------|---------|-------------|
| `PROJECT_CONTEXT.md` | Single source of truth | Architecture, file tree (60+ files), shipped/missing table, schema (11 tables), target roles |
| `PERSONAS.md` | Stakeholder personas | 4 personas with Mission, Constraints, Fallback, Owns sections |
| `RULES.md` | Anti-hallucination rules | 10 non-negotiable + 4 incident-driven rules, protected files table |
| `SPRINT_TEMPLATE.md` | 8-Pillar prompt template | Copy-paste scaffold for any AI to execute sprints |
| `CLAUDE_SYSTEM_PROMPT.md` | Claude-specific context | Cowork memory, PS5/Windows env, meeting format, sprint authority |
| `CODEX_SYSTEM_PROMPT.md` | Codex-specific context | Multi-AI awareness, commit conventions, stop-and-report rule |
| `GEMINI_SYSTEM_PROMPT.md` | Gemini-specific context | Google career framing, X-Y-Z format, GCP alternatives, Vertex AI roadmap |

**Commit:** `3b89465` (9 files: 7 new docs + 1 moved sprint prompt + 1 modified .gitignore)
**Pushed to:** `origin/main`
**Verification:** 179 tests passing, ruff clean

---

## Deliverables Shipped

| Artifact | Type | Commit |
|----------|------|--------|
| Sprint 6 infrastructure (compat.py, database.py, Dockerfile, etc.) | Code (13 files, +712 lines) | `98177d4` |
| `docs/ai-onboarding/PROJECT_CONTEXT.md` | Doc | `3b89465` |
| `docs/ai-onboarding/PERSONAS.md` | Doc | `3b89465` |
| `docs/ai-onboarding/RULES.md` | Doc | `3b89465` |
| `docs/ai-onboarding/SPRINT_TEMPLATE.md` | Doc | `3b89465` |
| `docs/ai-onboarding/CLAUDE_SYSTEM_PROMPT.md` | Doc | `3b89465` |
| `docs/ai-onboarding/CODEX_SYSTEM_PROMPT.md` | Doc | `3b89465` |
| `docs/ai-onboarding/GEMINI_SYSTEM_PROMPT.md` | Doc | `3b89465` |
| `CLAUDE_CODE_SPRINT6_COMBINED.md` | Prompt | N/A (Cowork folder) |
| `CLAUDE_CODE_REPO_CLEANUP.md` | Prompt | N/A (Cowork folder) |

---

## Test Suite Status

| Metric | Value |
|--------|-------|
| Total tests | 179 |
| Passed | 179 |
| Failed | 0 |
| Lint errors | 0 |
| CI jobs | 6 (lint, unit 3.11/3.12, integration, coverage, docker-build, db-tests-postgres) |

---

## Git Log (Session Commits)

```
3b89465 docs: add multi-AI onboarding package + repo cleanup
98177d4 feat(infra): Sprint 6 — Docker + Cloud SQL reimplementation
```

Tags: `v2.6.0-sprint6-infra`
Branch: `main`, pushed to `origin/main`

---

## Architecture Decisions

### Multi-AI Collaboration Model
**Decision:** All AI onboarding docs live inside the repo at `docs/ai-onboarding/`, not in external wikis or platform-specific configs.
**Why:** Any AI platform reads the docs after `git clone`. No external dependencies, no sync issues. GitHub is the single source of truth.
**Trade-off:** Docs add ~150KB to the repo, but context accuracy is worth more than repo size.

### Combined Sprint Prompt Strategy
**Decision:** Merged Sprint 6 (gap-fill) and Sprint 7 (Docker + Cloud SQL) into one prompt.
**Why:** API usage constraints. Fewer prompts = fewer context windows = less token spend. Part A self-skip logic prevents redundant work.

---

## Blockers Hit

1. **`.git/index.lock` permission error** — Cowork mount cannot write to `.git/`. Workaround: paste-ready PowerShell commands for local execution.
2. **Stale pytest overlay** — Tests loaded from old session path, not current code. Confirmed committed code was clean via `git show`.
3. **`pyproject.toml` parse error** — `pip install -e ".[dev]"` failed. Used `pip install -r requirements.txt` instead.
4. **Sprint 6 pre-flight reference errors** — Original prompt referenced `compat.py`, `health.py`, `Dockerfile` as existing. They didn't exist on current `main`. Fixed with conditional checks in combined prompt.

---

## What's Missing From Main (Still)

| Component | Original Sprint | Status |
|-----------|----------------|--------|
| CRM routes (applications, Kanban, state machine, reminders) | Sprint 2 | NOT reimplemented |
| Auto-Apply (prefill engine, approval queue, confidence scoring) | Sprint 3 | NOT reimplemented |

Reference code exists at `C:\Users\joshb\Documents\GitHub\ceal\` (old branch).

---

## Next Steps

1. **Verify CI** — `docker-build` and `db-tests-postgres` jobs are new, untested on GitHub Actions
2. **Docker smoke test** — `docker compose up --build` then `curl localhost:8000/health`
3. **Sprint 8: CRM + Auto-Apply reimplementation** — Draft prompt using 8-Pillar template
4. **Tier 1 Application Blitz** — Start applying to 5 target roles (Stripe, Square, Plaid, Coinbase, Datadog)
5. **NotebookLM sync** — Add onboarding docs + sprint notes to Ceal notebook

---

## Level of Effort

| Block | Duration (est.) | Complexity |
|-------|----------------|------------|
| Branch merge + Phase 2 verification | 45 min | Medium |
| Sprint 6 combined prompt creation | 1 hour | High |
| Sprint 6 execution (Claude Code) | 30 min | Medium — clean run |
| Repo cleanup | 15 min | Low |
| Multi-AI onboarding package | 1.5 hours | High — 7 docs, cross-platform context |
| Memory updates | 15 min | Low |
| **Session total** | **~4.25 hours** | **High** |

---

## Career Translation (X-Y-Z Bullets)

**Multi-AI Onboarding:**
> Designed a multi-AI collaboration framework enabling 3 LLM platforms (Claude, Codex, Gemini) to operate on a shared codebase with zero context drift, as measured by 7 structured onboarding documents covering architecture, rules, personas, and platform-specific constraints, by creating an in-repo documentation package that uses git as the single source of truth.

**Combined Sprint 6:**
> Reimplemented Docker containerization and Cloud SQL polymorphic database layer after a branch reset, as measured by 179 passing tests with zero regressions and a 6-stage CI pipeline, by combining two sprint scopes into a single 13-task prompt with self-skip logic that eliminated redundant work.

**Cumulative (Sprints 1-6 + onboarding):**
> Shipped 6 engineering sprints plus a multi-AI onboarding framework in one week, totaling 71+ tasks across 179 tests, by developing an 8-pillar anti-hallucination prompt engineering pattern with 14 rules that enables deterministic LLM-driven development across Claude, Codex, and Gemini.
