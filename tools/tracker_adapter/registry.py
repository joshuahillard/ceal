"""Tracker adapter registry / resolver.

Maps active_tracker names from pilot_profile.yaml to concrete adapter
classes. Lives next to the Protocol (tools/tracker_adapter/__init__.py)
without modifying it.

The registry is intentionally small and explicit. Each new concrete
adapter must be registered here. The Protocol's __init__.py docstring
states that all per-tracker adapters live in tools/tracker_adapter/;
the registry enforces the runtime resolution of active_tracker so an
unknown name fails loudly rather than silently passing through a typo.
"""

from __future__ import annotations

from tools.tracker_adapter import TrackerAdapter
from tools.tracker_adapter.linear import LinearAdapter


class UnknownTrackerError(ValueError):
    """Raised when active_tracker names a tracker with no concrete adapter."""


_REGISTRY: dict[str, type[TrackerAdapter]] = {
    "linear": LinearAdapter,
    # "clickup": ClickUpAdapter,  # not yet built
    # "notion":  NotionAdapter,   # not yet built
    # "jira":    JiraAdapter,     # not yet built
}


AVAILABLE_TRACKERS: frozenset[str] = frozenset(_REGISTRY.keys())


def get_adapter(name: str, **config) -> TrackerAdapter:
    """Resolve a concrete TrackerAdapter from an active_tracker name.

    Args:
        name: One of the keys in AVAILABLE_TRACKERS. Must match a value
              from pilot_profile.yaml's active_tracker field.
        **config: Forwarded to the adapter constructor (e.g. team_id="..."
                  for Linear).

    Returns:
        An instance of the concrete adapter class.

    Raises:
        UnknownTrackerError: name is not in AVAILABLE_TRACKERS.
        Whatever the adapter constructor raises (e.g. LinearAuthError if
        LINEAR_API_KEY is missing).
    """
    cls = _REGISTRY.get(name)
    if cls is None:
        raise UnknownTrackerError(
            f"active_tracker={name!r} has no concrete adapter. "
            f"Available: {sorted(AVAILABLE_TRACKERS)}."
        )
    return cls(**config)
