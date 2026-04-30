"""Tracker adapter boundary.

No tracker SDK imports are permitted outside this package. Concrete
per-tracker adapters (linear.py, clickup.py, notion.py, jira.py) live
here and each maps the tracker-native shape to the canonical
`ImplementationState` schema declared in
Maven_OS_Enterprise_Malleability_Analysis.md Part C.

Week-one scope: stub only. The Protocol below fixes the interface so
callers can be written against it; no concrete adapter is shipped
this week.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class TrackerAdapter(Protocol):
    """Canonical interface every tracker adapter must implement.

    Callers program against this Protocol; the active adapter is
    resolved at runtime from pilot_profile.yaml active_tracker.
    """

    def push_payload(self, payload: dict) -> str:
        """Create or upsert a ticket; return the tracker-native ticket id."""
        ...

    def read_status(self, ticket_id: str) -> dict:
        """Return canonical ImplementationState dict for ticket_id."""
        ...

    def list_stale(self, threshold_hours: int) -> list[dict]:
        """Return ImplementationState dicts for tickets older than threshold."""
        ...
