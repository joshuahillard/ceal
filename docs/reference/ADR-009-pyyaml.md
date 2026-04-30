# ADR-009: PyYAML as Top-Level Dependency

*Date: April 22, 2026*

**Decision:** Pin `PyYAML==6.0.3` as a top-level entry in `requirements.txt` and `pyproject.toml`. Previously transitively installed via other dependencies.

**Why:** The Maven OS Week-One handoff linter (`tools/handoff_lint.py`) parses fenced `yaml` blocks from `pilots/<pilot>/handoff_spec.md` (schema_contract, affected_artifacts, severity_and_acceptance, signoff). The linter is now a CI gate enforced by `.github/workflows/handoff-lint.yml`; a transitively-installed parser could vanish without notice when a parent dependency is upgraded, breaking the gate at runtime. Pinning a top-level dep is the minimum bar for a supply-chain event.

**Trade-off:** Exact pin (`==6.0.3`) over compatible-release range (`~=6.0`). Maximizes reproducibility of the lint gate; security fixes land via a deliberate bump rather than a silent transitive upgrade. `ruamel.yaml` was not evaluated; revisit if the linter ever needs to write YAML or preserve comments.

**Status:** Active. Single consumer: `tools/handoff_lint.py`. ADR recorded retroactively on April 30, 2026 to close SELF_REVIEW finding #7.
