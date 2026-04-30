"""Unit tests for tools/handoff_lint.py.

Covers the four required exit paths (PASS, BLOCK, ESCALATE,
HARNESS_FAULT) plus authorization and delta-computation corner cases.
Tests hit the in-process entry point (lint_handoff) rather than
subprocess; the CLI wrapper is separately smoke-tested via main().
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from tools.handoff_lint import (
    REQUIRED_SECTIONS,
    ExitCode,
    compute_delta_pct,
    compute_schema_digest,
    lint_handoff,
    main,
)


def _minimal_valid_handoff(
    schema_yaml: str | None = None,
    severity: str = "major",
    scope_change_authorized_by: str | None = None,
) -> str:
    """Render a syntactically valid handoff_spec.md body for tests.

    Non-structural sections contain trivial placeholder content so the
    empty-section check does not fire.
    """
    schema_yaml = schema_yaml or _DEFAULT_SCHEMA_YAML
    auth_line = (
        f'scope_change_authorized_by: "{scope_change_authorized_by}"'
        if scope_change_authorized_by is not None
        else "scope_change_authorized_by: null"
    )
    return _HANDOFF_TEMPLATE.format(
        schema_yaml=schema_yaml,
        severity=severity,
        scope_change_authorized_by_line=auth_line,
    )


_DEFAULT_SCHEMA_YAML = """schema_contract:
  ticket:
    id: {type: "string"}
    subject: {type: "string"}
    priority: {type: "enum"}
    status: {type: "enum"}
  account:
    id: {type: "string"}
    tier: {type: "enum"}
"""


_HANDOFF_TEMPLATE = """# Handoff Test

<!-- section: pilot_identity -->
## Pilot identity
- pilot_id: test-001

<!-- section: customer_ask -->
body

<!-- section: translated_requirement -->
body

<!-- section: scope -->
body

<!-- section: source_of_truth_integrations -->
body

<!-- section: schema_contract -->
```yaml
{schema_yaml}
```

<!-- section: affected_artifacts -->
```yaml
affected_artifacts:
  - type: "api_endpoint"
    value: "https://example.test/api/v1/tickets"
    verification_method: "curl with pilot token returns 200"
  - type: "schema_field"
    value: "ticket.priority"
    verification_method: "admin UI displays field with enum values"
```

<!-- section: payload_examples -->
body

<!-- section: error_handling -->
body

<!-- section: intelligent_field_evaluations -->
body

<!-- section: downstream_impact_analysis -->
body

<!-- section: severity_and_acceptance -->
```yaml
severity: "{severity}"
acceptance_check:
  condition: "test condition"
  evidence_path: "evidence/test.md"
```

<!-- section: hallucination_guardrails -->
body

<!-- section: rollback_plan -->
body

<!-- section: signoff -->
```yaml
signoff:
  customer_engineering: {{signer: "a", signed_ts_utc: null}}
  customer_business_sponsor: {{signer: "b", signed_ts_utc: null}}
  maven_fde: {{signer: "c", signed_ts_utc: null}}
  maven_im: {{signer: "d", signed_ts_utc: null}}
{scope_change_authorized_by_line}
```
"""


@pytest.fixture
def tmp_git_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Disposable git repo in tmp_path with an empty initial commit.

    Tests that use this fixture run with process cwd set to tmp_path so
    git commands resolve against this repo. We intentionally do not pin
    the default branch name; tests reference commits by SHA.
    """
    subprocess.run(
        ["git", "init"],
        cwd=tmp_path, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.test"],
        cwd=tmp_path, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "init"],
        cwd=tmp_path, check=True, capture_output=True,
    )
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _git_commit_all(repo: Path, msg: str) -> None:
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", msg], cwd=repo, check=True, capture_output=True)


def _git_head_sha(repo: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo, check=True, capture_output=True, text=True, encoding="utf-8",
    ).stdout.strip()


# -------- PASS ----------------------------------------------------------------

def test_pass_on_valid_handoff_no_baseline(tmp_path: Path) -> None:
    path = tmp_path / "handoff.md"
    path.write_text(_minimal_valid_handoff(), encoding="utf-8")

    result = lint_handoff(path)

    assert result.exit_code is ExitCode.PASS, result.messages
    assert not result.sections_missing
    assert not result.sections_empty
    assert result.severity == "major"
    assert result.schema_digest is not None
    assert result.delta_check == "skipped_no_baseline"
    assert result.delta_pct is None


def test_pass_with_zero_delta_against_prior(tmp_path: Path) -> None:
    """Identical schemas exercise the delta_check=performed path at delta=0."""
    prior = tmp_path / "prior.md"
    prior.write_text(_minimal_valid_handoff(), encoding="utf-8")
    current = tmp_path / "current.md"
    current.write_text(_minimal_valid_handoff(), encoding="utf-8")

    result = lint_handoff(current, against=prior)

    assert result.exit_code is ExitCode.PASS, result.messages
    assert result.delta_check == "performed"
    assert result.delta_pct == 0.0


def test_pass_when_large_delta_is_authorized(tmp_path: Path) -> None:
    prior = tmp_path / "prior.md"
    prior.write_text(_minimal_valid_handoff(), encoding="utf-8")
    big_mutation = """schema_contract:
  order:
    id: {type: "string"}
    total: {type: "number"}
    currency: {type: "string"}
  customer:
    id: {type: "string"}
    email: {type: "string"}
"""
    current = tmp_path / "current.md"
    current.write_text(
        _minimal_valid_handoff(
            schema_yaml=big_mutation,
            scope_change_authorized_by="im_lead@example.test",
        ),
        encoding="utf-8",
    )

    result = lint_handoff(current, against=prior)

    assert result.exit_code is ExitCode.PASS, result.messages
    assert result.delta_check == "performed"
    assert result.delta_pct is not None and result.delta_pct > 25.0


# -------- BLOCK ---------------------------------------------------------------

def test_block_missing_artifact_ref_verification_method(tmp_path: Path) -> None:
    # Include the 4-space leading indent so the replace removes the full
    # line, not just the trailing substring (which would corrupt the
    # next item's indentation and produce invalid YAML).
    content = _minimal_valid_handoff().replace(
        '    verification_method: "curl with pilot token returns 200"\n',
        "",
    )
    path = tmp_path / "handoff.md"
    path.write_text(content, encoding="utf-8")

    result = lint_handoff(path)

    assert result.exit_code is ExitCode.BLOCK
    assert any(
        "affected_artifacts[0]" in m and "verification_method" in m
        for m in result.messages
    ), result.messages


def test_block_missing_required_section(tmp_path: Path) -> None:
    content = _minimal_valid_handoff().replace(
        "<!-- section: rollback_plan -->\nbody\n\n",
        "",
    )
    path = tmp_path / "handoff.md"
    path.write_text(content, encoding="utf-8")

    result = lint_handoff(path)

    assert result.exit_code is ExitCode.BLOCK
    assert "rollback_plan" in result.sections_missing


def test_block_invalid_severity(tmp_path: Path) -> None:
    path = tmp_path / "handoff.md"
    path.write_text(_minimal_valid_handoff(severity="catastrophic"), encoding="utf-8")

    result = lint_handoff(path)

    assert result.exit_code is ExitCode.BLOCK
    assert any("severity must be one of" in m for m in result.messages), result.messages


# -------- ESCALATE ------------------------------------------------------------

def test_escalate_on_delta_over_25_percent_without_authorization(tmp_path: Path) -> None:
    prior = tmp_path / "prior.md"
    prior.write_text(_minimal_valid_handoff(), encoding="utf-8")
    # Replace schema wholesale; sym_diff = union, delta = 100%.
    big_mutation = """schema_contract:
  order:
    id: {type: "string"}
    total: {type: "number"}
    currency: {type: "string"}
"""
    current = tmp_path / "current.md"
    current.write_text(
        _minimal_valid_handoff(schema_yaml=big_mutation),
        encoding="utf-8",
    )

    result = lint_handoff(current, against=prior)

    assert result.exit_code is ExitCode.ESCALATE, result.messages
    assert result.delta_pct is not None and result.delta_pct > 25.0
    assert any("ESCALATE" in m for m in result.messages)


# -------- HARNESS_FAULT -------------------------------------------------------

def test_harness_fault_on_missing_file(tmp_path: Path) -> None:
    result = lint_handoff(tmp_path / "does_not_exist.md")

    assert result.exit_code is ExitCode.HARNESS_FAULT
    assert any("HARNESS_FAULT" in m for m in result.messages)


def test_harness_fault_on_missing_against_file(tmp_path: Path) -> None:
    path = tmp_path / "handoff.md"
    path.write_text(_minimal_valid_handoff(), encoding="utf-8")

    result = lint_handoff(path, against=tmp_path / "nope.md")

    assert result.exit_code is ExitCode.HARNESS_FAULT


# -------- Unit tests for helpers ---------------------------------------------

def test_required_sections_count_is_15() -> None:
    assert len(REQUIRED_SECTIONS) == 15


def test_compute_delta_pct_identical_schemas_is_zero() -> None:
    a = {"x": {"id": "string"}, "y": {"name": "string"}}
    assert compute_delta_pct(a, a) == 0.0


def test_compute_delta_pct_disjoint_schemas_is_100() -> None:
    a = {"x": {"id": "string"}}
    b = {"y": {"name": "string"}}
    assert compute_delta_pct(a, b) == 100.0


def test_compute_schema_digest_is_deterministic_across_key_order() -> None:
    a = {"ticket": {"id": "string", "subject": "string"}}
    b = {"ticket": {"subject": "string", "id": "string"}}
    assert compute_schema_digest(a) == compute_schema_digest(b)


# -------- CLI entry smoke ----------------------------------------------------

def test_main_returns_exit_code_integer(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "handoff.md"
    path.write_text(_minimal_valid_handoff(), encoding="utf-8")

    rc = main([str(path)])

    assert rc == int(ExitCode.PASS)
    captured = capsys.readouterr()
    # Human triage lands on stderr, JSON summary on stdout.
    assert "handoff_lint" in captured.err
    assert '"result":"PASS"' in captured.out


def test_main_returns_harness_fault_on_missing_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = main([str(tmp_path / "does_not_exist.md")])

    assert rc == int(ExitCode.HARNESS_FAULT)


# -------- Baseline resolution from git ref -----------------------------------

def test_git_baseline_zero_delta_passes(
    tmp_git_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Baseline at a git rev identical to current → PASS with delta_pct=0."""
    handoff_rel = "pilots/test/handoff_spec.md"
    handoff_abs = tmp_git_repo / handoff_rel
    handoff_abs.parent.mkdir(parents=True, exist_ok=True)
    handoff_abs.write_text(_minimal_valid_handoff(), encoding="utf-8")
    _git_commit_all(tmp_git_repo, "baseline")
    baseline_sha = _git_head_sha(tmp_git_repo)

    rc = main([handoff_rel, "--baseline-from-git-ref", baseline_sha])

    assert rc == int(ExitCode.PASS)
    captured = capsys.readouterr()
    assert '"delta_check":"performed"' in captured.out
    assert '"delta_pct":0.0' in captured.out


def test_git_baseline_large_delta_escalates(
    tmp_git_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Baseline at a git rev disjoint from current schema → ESCALATE."""
    handoff_rel = "pilots/test/handoff_spec.md"
    handoff_abs = tmp_git_repo / handoff_rel
    handoff_abs.parent.mkdir(parents=True, exist_ok=True)
    handoff_abs.write_text(_minimal_valid_handoff(), encoding="utf-8")
    _git_commit_all(tmp_git_repo, "baseline")
    baseline_sha = _git_head_sha(tmp_git_repo)
    big_mutation = """schema_contract:
  order:
    id: {type: "string"}
    total: {type: "number"}
"""
    handoff_abs.write_text(
        _minimal_valid_handoff(schema_yaml=big_mutation), encoding="utf-8"
    )

    rc = main([handoff_rel, "--baseline-from-git-ref", baseline_sha])

    assert rc == int(ExitCode.ESCALATE)
    captured = capsys.readouterr()
    assert '"result":"ESCALATE"' in captured.out


def test_git_baseline_missing_file_on_ref_falls_through(
    tmp_git_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Ref exists but handoff file absent at that ref → PASS with skip log."""
    baseline_sha = _git_head_sha(tmp_git_repo)
    handoff_rel = "pilots/test/handoff_spec.md"
    handoff_abs = tmp_git_repo / handoff_rel
    handoff_abs.parent.mkdir(parents=True, exist_ok=True)
    handoff_abs.write_text(_minimal_valid_handoff(), encoding="utf-8")
    # Intentionally NOT committed: file is absent at baseline_sha.

    rc = main([handoff_rel, "--baseline-from-git-ref", baseline_sha])

    assert rc == int(ExitCode.PASS)
    captured = capsys.readouterr()
    assert '"delta_check":"skipped_no_baseline"' in captured.out
    assert "baseline not present on ref" in captured.err
