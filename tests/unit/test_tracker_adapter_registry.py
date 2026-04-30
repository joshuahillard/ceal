"""Unit tests for tools/tracker_adapter/registry.py."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from tools.tracker_adapter.linear import LinearAdapter
from tools.tracker_adapter.registry import (
    AVAILABLE_TRACKERS,
    UnknownTrackerError,
    get_adapter,
)


def test_unknown_tracker_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LINEAR_API_KEY", "test-token")  # noqa: S105
    with pytest.raises(UnknownTrackerError) as exc_info:
        get_adapter("notatracker", team_id="t")
    msg = str(exc_info.value)
    assert "notatracker" in msg
    assert "linear" in msg


def test_linear_resolves_to_linear_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LINEAR_API_KEY", "test-token")  # noqa: S105
    adapter = get_adapter("linear", team_id="team-uuid")
    try:
        assert isinstance(adapter, LinearAdapter)
        assert adapter.team_id == "team-uuid"
    finally:
        adapter.close()


def test_available_trackers_includes_linear() -> None:
    assert "linear" in AVAILABLE_TRACKERS


def test_acme_corp_pilot_profile_resolves_to_linear_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end smoke: pilots/acme-corp/pilot_profile.yaml -> registry -> LinearAdapter.

    Closes SELF_REVIEW finding #2: active_tracker: linear in the pilot
    profile must resolve at runtime to a concrete adapter instance.
    """
    monkeypatch.setenv("LINEAR_API_KEY", "test-token")  # noqa: S105

    repo_root = Path(__file__).resolve().parents[2]
    profile_path = repo_root / "pilots" / "acme-corp" / "pilot_profile.yaml"
    with profile_path.open("r", encoding="utf-8") as f:
        profile = yaml.safe_load(f)

    tracker_name = profile["active_tracker"]
    tracker_cfg = (profile.get("tracker_config") or {}).get(tracker_name) or {}

    adapter = get_adapter(tracker_name, **tracker_cfg)
    try:
        assert isinstance(adapter, LinearAdapter)
        # team_id is whatever the pilot profile declares (currently
        # "[UNVERIFIED]" until pilot intake fills in the real UUID).
        assert adapter.team_id == tracker_cfg["team_id"]
    finally:
        adapter.close()
