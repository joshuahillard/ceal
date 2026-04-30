"""tools/handoff_lint.py: Maven Implementation OS handoff linter.

Enforces Maven_Implementation_OS_Master_Prompt.md v1.2 Deliverable 2:
- fifteen named section anchors required in any order
- every affected_artifacts entry carries type + value + verification_method
- severity in {critical, major, minor, info}
- schema_contract delta > 25 percent versus a prior handoff requires
  scope_change_authorized_by set in the signoff block; otherwise the
  linter ESCALATEs.

Exit codes:
  0  PASS             all checks pass
  1  BLOCK            missing or invalid sections, artifact_refs, or severity
  2  ESCALATE         schema delta > 25 percent without authorization
  3  HARNESS_FAULT    linter could not interpret the file (I/O or parse fail)

Precedence when multiple issues are present: BLOCK wins over ESCALATE
wins over PASS. HARNESS_FAULT short-circuits everything.

First Principle #8 (Operable without engineering): human triage is
written to stderr first, then a machine-readable JSON summary to
stdout. Pipe-friendly: `handoff_lint FILE | jq .`.

First Principle #9 (Validation is not authorization): a PASS here does
not authorize any state transition. The state machine gates that.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any

import yaml


class ExitCode(IntEnum):
    PASS = 0
    BLOCK = 1
    ESCALATE = 2
    HARNESS_FAULT = 3


REQUIRED_SECTIONS: frozenset[str] = frozenset({
    "pilot_identity",
    "customer_ask",
    "translated_requirement",
    "scope",
    "source_of_truth_integrations",
    "schema_contract",
    "affected_artifacts",
    "payload_examples",
    "error_handling",
    "intelligent_field_evaluations",
    "downstream_impact_analysis",
    "severity_and_acceptance",
    "hallucination_guardrails",
    "rollback_plan",
    "signoff",
})

ALLOWED_SEVERITY: frozenset[str] = frozenset({"critical", "major", "minor", "info"})
ARTIFACT_REF_REQUIRED_KEYS: frozenset[str] = frozenset({"type", "value", "verification_method"})
DELTA_ESCALATION_THRESHOLD_PCT: float = 25.0

_SECTION_ANCHOR_RE = re.compile(r"^<!--\s*section:\s*([a-z_][a-z0-9_]*)\s*-->\s*$", re.MULTILINE)
_YAML_BLOCK_RE = re.compile(r"```yaml\s*\n(.*?)\n```", re.DOTALL)


@dataclass
class LintResult:
    exit_code: ExitCode
    messages: list[str] = field(default_factory=list)
    sections_found: list[str] = field(default_factory=list)
    sections_missing: list[str] = field(default_factory=list)
    sections_empty: list[str] = field(default_factory=list)
    severity: str | None = None
    schema_digest: str | None = None
    delta_pct: float | None = None
    delta_check: str = "skipped_no_baseline"   # skipped_no_baseline | performed

    def to_json(self) -> str:
        payload = {
            "exit_code": int(self.exit_code),
            "result": self.exit_code.name,
            "sections_found_count": len(self.sections_found),
            "sections_missing": sorted(self.sections_missing),
            "sections_empty": sorted(self.sections_empty),
            "severity": self.severity,
            "schema_digest": self.schema_digest,
            "delta_pct": self.delta_pct,
            "delta_check": self.delta_check,
            "messages": self.messages,
        }
        return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def _split_sections(markdown: str) -> dict[str, str]:
    """Return {section_name: body_text} using <!-- section: NAME --> anchors."""
    matches = list(_SECTION_ANCHOR_RE.finditer(markdown))
    sections: dict[str, str] = {}
    for idx, m in enumerate(matches):
        name = m.group(1)
        start = m.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(markdown)
        sections[name] = markdown[start:end]
    return sections


def _extract_first_yaml_block(body: str) -> Any:
    """Return parsed YAML from the first fenced yaml block in body, or None."""
    match = _YAML_BLOCK_RE.search(body)
    if not match:
        return None
    return yaml.safe_load(match.group(1))


def compute_schema_digest(schema: dict[str, Any]) -> str:
    """sha256 of canonical JSON (sorted keys) of the schema_contract."""
    canonical = json.dumps(schema, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _leaf_paths(obj: Any, prefix: str = "") -> set[str]:
    """Dotted leaf paths through a nested mapping; lists are treated as leaves."""
    paths: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            child = f"{prefix}.{k}" if prefix else str(k)
            if isinstance(v, dict):
                paths |= _leaf_paths(v, child)
            else:
                paths.add(child)
    elif prefix:
        paths.add(prefix)
    return paths


def compute_delta_pct(prior: dict[str, Any], current: dict[str, Any]) -> float:
    """Structural delta between two schema dicts as percent of the union.

    Delta counts fields added or removed; a pure value change at an
    existing leaf is not counted. This matches the intent of the
    25-percent-scope-change rule: scope drift is structural.
    """
    a = _leaf_paths(prior)
    b = _leaf_paths(current)
    union = a | b
    if not union:
        return 0.0
    return round(100.0 * len(a.symmetric_difference(b)) / len(union), 2)


def _load_prior_schema(against: Path) -> dict[str, Any] | None:
    """Read and parse the schema_contract block from a prior handoff file."""
    content = against.read_text(encoding="utf-8")
    sections = _split_sections(content)
    body = sections.get("schema_contract")
    if body is None:
        return None
    block = _extract_first_yaml_block(body)
    if not isinstance(block, dict):
        return None
    schema = block.get("schema_contract")
    return schema if isinstance(schema, dict) else block


def _read_scope_change_authorization(signoff_body: str) -> str | None:
    """Return scope_change_authorized_by if set to a non-empty string, else None."""
    try:
        block = _extract_first_yaml_block(signoff_body)
    except yaml.YAMLError:
        return None
    if not isinstance(block, dict):
        return None
    val = block.get("scope_change_authorized_by")
    if isinstance(val, str) and val.strip():
        return val.strip()
    return None


def lint_handoff(path: Path, against: Path | None = None) -> LintResult:
    """Lint one handoff_spec.md. Returns a LintResult with populated exit_code.

    Never raises on expected failure paths (missing file, parse errors,
    malformed YAML). Unexpected exceptions propagate so CI still fails
    loudly on a harness bug.
    """
    # Stage 1: I/O
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return LintResult(
            exit_code=ExitCode.HARNESS_FAULT,
            messages=[f"HARNESS_FAULT: file not found: {path}"],
        )
    except OSError as e:
        return LintResult(
            exit_code=ExitCode.HARNESS_FAULT,
            messages=[f"HARNESS_FAULT: could not read {path}: {e}"],
        )

    # Stage 2: section anchors
    sections = _split_sections(content)
    found = set(sections.keys())
    missing = sorted(REQUIRED_SECTIONS - found)
    empty = sorted(name for name in REQUIRED_SECTIONS & found if not sections[name].strip())

    result = LintResult(
        exit_code=ExitCode.PASS,
        sections_found=sorted(found),
        sections_missing=missing,
        sections_empty=empty,
    )

    if missing:
        result.messages.append(f"BLOCK: missing required sections: {', '.join(missing)}")
    if empty:
        result.messages.append(f"BLOCK: empty required sections: {', '.join(empty)}")

    # Stage 3: affected_artifacts structure
    if "affected_artifacts" in sections:
        try:
            block = _extract_first_yaml_block(sections["affected_artifacts"])
        except yaml.YAMLError as e:
            result.messages.append(f"BLOCK: affected_artifacts yaml parse error: {e}")
            block = None
        if block is None:
            result.messages.append("BLOCK: affected_artifacts yaml block missing or unparseable")
        else:
            refs = block.get("affected_artifacts") if isinstance(block, dict) else None
            if not isinstance(refs, list) or not refs:
                result.messages.append("BLOCK: affected_artifacts must be a non-empty list")
            else:
                for idx, ref in enumerate(refs):
                    if not isinstance(ref, dict):
                        result.messages.append(
                            f"BLOCK: affected_artifacts[{idx}] is not a mapping"
                        )
                        continue
                    missing_keys = ARTIFACT_REF_REQUIRED_KEYS - set(ref.keys())
                    if missing_keys:
                        result.messages.append(
                            f"BLOCK: affected_artifacts[{idx}] missing keys: "
                            f"{', '.join(sorted(missing_keys))}"
                        )
                    for key in ARTIFACT_REF_REQUIRED_KEYS:
                        val = ref.get(key)
                        if isinstance(val, str) and not val.strip():
                            result.messages.append(
                                f"BLOCK: affected_artifacts[{idx}].{key} is empty"
                            )

    # Stage 4: severity
    if "severity_and_acceptance" in sections:
        try:
            block = _extract_first_yaml_block(sections["severity_and_acceptance"])
        except yaml.YAMLError as e:
            result.messages.append(f"BLOCK: severity_and_acceptance yaml parse error: {e}")
            block = None
        if isinstance(block, dict):
            sev = block.get("severity")
            result.severity = sev if isinstance(sev, str) else None
            if result.severity not in ALLOWED_SEVERITY:
                result.messages.append(
                    f"BLOCK: severity must be one of {sorted(ALLOWED_SEVERITY)}, "
                    f"got {result.severity!r}"
                )
        else:
            result.messages.append("BLOCK: severity_and_acceptance yaml block missing")

    # Stage 5: schema_contract digest
    current_schema: dict[str, Any] | None = None
    if "schema_contract" in sections:
        try:
            block = _extract_first_yaml_block(sections["schema_contract"])
        except yaml.YAMLError as e:
            result.messages.append(f"BLOCK: schema_contract yaml parse error: {e}")
            block = None
        if isinstance(block, dict):
            candidate = block.get("schema_contract")
            current_schema = candidate if isinstance(candidate, dict) else block
            if isinstance(current_schema, dict):
                result.schema_digest = compute_schema_digest(current_schema)
            else:
                result.messages.append("BLOCK: schema_contract must be a mapping")
                current_schema = None
        else:
            result.messages.append("BLOCK: schema_contract yaml block missing")

    # Stage 6: delta check against prior
    prior_schema: dict[str, Any] | None = None
    if against is not None:
        try:
            prior_schema = _load_prior_schema(against)
        except FileNotFoundError:
            return LintResult(
                exit_code=ExitCode.HARNESS_FAULT,
                messages=[f"HARNESS_FAULT: --against file not found: {against}"],
            )
        except yaml.YAMLError as e:
            return LintResult(
                exit_code=ExitCode.HARNESS_FAULT,
                messages=[f"HARNESS_FAULT: --against yaml parse error: {e}"],
            )

    if prior_schema is not None and current_schema is not None:
        delta = compute_delta_pct(prior_schema, current_schema)
        result.delta_pct = delta
        result.delta_check = "performed"
        if delta > DELTA_ESCALATION_THRESHOLD_PCT:
            authorized = _read_scope_change_authorization(sections.get("signoff", ""))
            if not authorized:
                result.messages.append(
                    f"ESCALATE: schema_contract delta {delta} percent exceeds "
                    f"{DELTA_ESCALATION_THRESHOLD_PCT} percent threshold and "
                    f"scope_change_authorized_by is not set"
                )

    # Stage 7: resolve final exit code. BLOCK > ESCALATE > PASS.
    if any(m.startswith("BLOCK:") for m in result.messages):
        result.exit_code = ExitCode.BLOCK
    elif any(m.startswith("ESCALATE:") for m in result.messages):
        result.exit_code = ExitCode.ESCALATE
    else:
        result.exit_code = ExitCode.PASS

    return result


def _render_human_triage(result: LintResult, path: Path) -> str:
    lines: list[str] = []
    lines.append(f"[handoff_lint] {path}: {result.exit_code.name} ({int(result.exit_code)})")
    if result.sections_missing:
        lines.append(f"  missing sections: {', '.join(result.sections_missing)}")
    if result.sections_empty:
        lines.append(f"  empty sections: {', '.join(result.sections_empty)}")
    if result.severity:
        lines.append(f"  severity: {result.severity}")
    if result.schema_digest:
        lines.append(f"  schema_digest: {result.schema_digest[:16]}...")
    lines.append(f"  delta_check: {result.delta_check}")
    if result.delta_pct is not None:
        lines.append(f"  delta_pct: {result.delta_pct}")
    for msg in result.messages:
        lines.append(f"  {msg}")
    return "\n".join(lines)


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    """Run a git subcommand from process cwd; never raises on nonzero rc."""
    try:
        return subprocess.run(
            ["git", *args],
            capture_output=True,
            check=False,
            text=True,
            encoding="utf-8",
        )
    except FileNotFoundError as e:
        raise RuntimeError(f"git binary not available: {e}") from e


def resolve_baseline_from_git_ref(git_ref: str, handoff_path: str) -> Path | None:
    """Materialize <git_ref>:<handoff_path> to a temp file for --against use.

    Returns the temp path on success or None if the file does not exist at
    the given ref (new-pilot case). Raises RuntimeError if the ref itself
    cannot be resolved or git is unavailable; the caller turns that into
    HARNESS_FAULT so CI fails loudly rather than silently skipping.

    handoff_path must be forward-slash repo-relative; git's REV:PATH
    syntax does not accept backslashes.
    """
    probe = _git("cat-file", "-e", f"{git_ref}:{handoff_path}")
    if probe.returncode != 0:
        rev_probe = _git("rev-parse", "--verify", f"{git_ref}^{{commit}}")
        if rev_probe.returncode != 0:
            raise RuntimeError(
                f"git ref not resolvable: {git_ref!r} "
                f"(stderr: {rev_probe.stderr.strip()})"
            )
        # Rev is valid; file absent at that rev. New-pilot case.
        return None

    show = _git("show", f"{git_ref}:{handoff_path}")
    if show.returncode != 0:
        raise RuntimeError(
            f"git show failed for {git_ref}:{handoff_path} "
            f"(stderr: {show.stderr.strip()})"
        )

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".baseline.md", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(show.stdout)
        tmp_path = Path(tmp.name)
    return tmp_path


def _build_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="handoff_lint",
        description="Lint a Maven Implementation OS handoff_spec.md. "
        "See module docstring for exit codes.",
    )
    parser.add_argument("path", type=Path, help="Path to handoff_spec.md")
    baseline_group = parser.add_mutually_exclusive_group()
    baseline_group.add_argument(
        "--against",
        type=Path,
        default=None,
        help="Path to a prior handoff_spec.md for the 25-percent-delta rule. "
        "If absent (and --baseline-from-git-ref is not supplied), the rule "
        "is skipped with delta_check=skipped_no_baseline.",
    )
    baseline_group.add_argument(
        "--baseline-from-git-ref",
        type=str,
        default=None,
        metavar="REF",
        help="Resolve the baseline from a git revision (e.g. 'origin/main'). "
        "Mutually exclusive with --against. If the handoff file is not "
        "present at the ref (new pilot), delta_check=skipped_no_baseline.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_argparser().parse_args(argv)

    against: Path | None = args.against
    cleanup_path: Path | None = None

    if args.baseline_from_git_ref is not None:
        handoff_rel_posix = args.path.as_posix()
        try:
            resolved = resolve_baseline_from_git_ref(
                args.baseline_from_git_ref, handoff_rel_posix
            )
        except RuntimeError as e:
            result = LintResult(
                exit_code=ExitCode.HARNESS_FAULT,
                messages=[f"HARNESS_FAULT: {e}"],
            )
            print(_render_human_triage(result, args.path), file=sys.stderr)
            print(result.to_json())
            return int(result.exit_code)
        if resolved is None:
            print(
                f"[handoff_lint] baseline not present on ref "
                f"{args.baseline_from_git_ref!r} for {handoff_rel_posix}; "
                f"proceeding without --against",
                file=sys.stderr,
            )
        else:
            against = resolved
            cleanup_path = resolved

    try:
        result = lint_handoff(args.path, against=against)
    except yaml.YAMLError as e:
        result = LintResult(
            exit_code=ExitCode.HARNESS_FAULT,
            messages=[f"HARNESS_FAULT: unexpected yaml parse failure: {e}"],
        )
    finally:
        if cleanup_path is not None:
            try:
                cleanup_path.unlink(missing_ok=True)
            except OSError:
                pass

    print(_render_human_triage(result, args.path), file=sys.stderr)
    print(result.to_json())
    return int(result.exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
