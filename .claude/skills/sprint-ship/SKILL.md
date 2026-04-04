## Sprint Ship
Standardized commit-tag-push workflow with guards.

1. Run targeted tests from Task Card Verify section (if active)
2. Run full test suite: `python -m pytest tests/ --tb=short -q`
   - If any tests fail, stop and report. Do not proceed to commit.
3. Confirm correct repo: `git remote -v`
   - If remote does not match `github.com/joshuahillard/ceal`, stop and ask.
4. Run linter: `ruff check src/`
5. Stage changes relevant to this sprint (specific files, not `git add .`)
6. Create conventional commit with descriptive message
7. Create version tag if user specifies (format: `vX.Y.Z-sprintN-description`)
8. Attempt push: `git push origin main` (and tags if created: `git push --tags`)
   - If push hangs or prompts for credentials, kill it and report clearly
   - Do NOT retry push more than once
9. Report: commit hash, tag (if created), test count, push status, files touched

### PowerShell Notes
- Do not use bash-style `timeout` command on Windows
- Use `$env:` syntax for environment variables
- Avoid BOM encoding in file writes
