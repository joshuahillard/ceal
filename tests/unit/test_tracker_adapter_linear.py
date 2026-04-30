"""Unit tests for tools/tracker_adapter/linear.py.

Mocks Linear's GraphQL endpoint via httpx.MockTransport so the GraphQL
contract is exercised at the HTTP layer. No live API calls.

Token-redaction is verified by positive assertion across every error-path
test: the API token must never appear in any raised message. The
test_safe_redacts_token_when_present test exercises the redaction path
explicitly with a synthesized upstream string.
"""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest
from tools.tracker_adapter.linear import (
    LinearAdapter,
    LinearAdapterError,
    LinearAuthError,
    LinearRateLimitError,
)

_TEST_TOKEN = "lin_api_pretend_token_aaaa1111bbbb2222"  # noqa: S105 - test fixture
_TEST_TEAM_ID = "team-uuid-abc-123"
_TEST_PILOT_ID = "acme-corp-csx-q2"
_TEST_EVENT_ID = "evt-2026-04-30-001"


def _make_client(
    handler: Callable[[httpx.Request], httpx.Response],
) -> httpx.Client:
    """httpx.Client whose transport delegates to handler(request)."""
    return httpx.Client(
        transport=httpx.MockTransport(handler),
        headers={"Authorization": _TEST_TOKEN, "Content-Type": "application/json"},
    )


def _make_adapter(
    monkeypatch: pytest.MonkeyPatch,
    handler: Callable[[httpx.Request], httpx.Response],
) -> LinearAdapter:
    monkeypatch.setenv("LINEAR_API_KEY", _TEST_TOKEN)
    return LinearAdapter(team_id=_TEST_TEAM_ID, client=_make_client(handler))


def _gql_body(request: httpx.Request) -> dict:
    return json.loads(request.content.decode("utf-8"))


# -------- Constructor --------------------------------------------------------

def test_constructor_raises_when_api_key_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LINEAR_API_KEY", raising=False)
    with pytest.raises(LinearAuthError) as exc_info:
        LinearAdapter(team_id=_TEST_TEAM_ID)
    assert "LINEAR_API_KEY" in str(exc_info.value)


# -------- push_payload: create-success ---------------------------------------

def test_push_payload_creates_when_no_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = _gql_body(request)
        query = body["query"]
        if "FindIssueByTitlePrefix" in query:
            calls.append("find")
            return httpx.Response(200, json={"data": {"issues": {"nodes": []}}})
        if "CreateIssue" in query:
            calls.append("create")
            assert body["variables"]["input"]["teamId"] == _TEST_TEAM_ID
            assert body["variables"]["input"]["title"].startswith(
                f"[MavenOS:{_TEST_PILOT_ID}:{_TEST_EVENT_ID}]"
            )
            return httpx.Response(
                200,
                json={
                    "data": {
                        "issueCreate": {
                            "success": True,
                            "issue": {"id": "issue-uuid-new-1"},
                        }
                    }
                },
            )
        pytest.fail(f"unexpected query: {query!r}")

    adapter = _make_adapter(monkeypatch, handler)
    issue_id = adapter.push_payload(
        {
            "pilot_id": _TEST_PILOT_ID,
            "event_id": _TEST_EVENT_ID,
            "title": "schema_contract change requires sign-off",
            "description": "schema delta detected; review and authorize",
        }
    )
    assert issue_id == "issue-uuid-new-1"
    assert calls == ["find", "create"]


# -------- push_payload: duplicate-detected -> update -------------------------

def test_push_payload_updates_when_match_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = _gql_body(request)
        query = body["query"]
        if "FindIssueByTitlePrefix" in query:
            calls.append("find")
            return httpx.Response(
                200,
                json={
                    "data": {
                        "issues": {"nodes": [{"id": "issue-uuid-existing-9"}]}
                    }
                },
            )
        if "UpdateIssue" in query:
            calls.append("update")
            assert body["variables"]["id"] == "issue-uuid-existing-9"
            return httpx.Response(
                200,
                json={
                    "data": {
                        "issueUpdate": {
                            "success": True,
                            "issue": {"id": "issue-uuid-existing-9"},
                        }
                    }
                },
            )
        if "CreateIssue" in query:
            pytest.fail("create must not be called when a duplicate is detected")
        pytest.fail(f"unexpected query: {query!r}")

    adapter = _make_adapter(monkeypatch, handler)
    issue_id = adapter.push_payload(
        {
            "pilot_id": _TEST_PILOT_ID,
            "event_id": _TEST_EVENT_ID,
            "title": "updated body",
        }
    )
    assert issue_id == "issue-uuid-existing-9"
    assert calls == ["find", "update"]


# -------- push_payload: missing required keys --------------------------------

def test_push_payload_raises_on_missing_pilot_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        pytest.fail("no HTTP call expected")

    adapter = _make_adapter(monkeypatch, handler)
    with pytest.raises(LinearAdapterError) as exc_info:
        adapter.push_payload({"event_id": "e"})
    assert "pilot_id" in str(exc_info.value)


# -------- read_status: found / not-found -------------------------------------

def test_read_status_returns_canonical_dict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": {
                    "issue": {
                        "id": "uuid-1",
                        "identifier": "ENG-123",
                        "title": "T",
                        "description": "D",
                        "state": {"name": "In Progress"},
                        "assignee": {"name": "A", "email": "a@example.test"},
                        "labels": {"nodes": [{"name": "bug"}, {"name": "p1"}]},
                        "priority": 2,
                        "createdAt": "2026-04-01T00:00:00Z",
                        "updatedAt": "2026-04-29T00:00:00Z",
                        "url": "https://linear.app/x/issue/ENG-123",
                    }
                }
            },
        )

    adapter = _make_adapter(monkeypatch, handler)
    state = adapter.read_status("uuid-1")
    assert state["ticket_id"] == "uuid-1"
    assert state["identifier"] == "ENG-123"
    assert state["state"] == "In Progress"
    assert state["labels"] == ["bug", "p1"]
    assert state["priority"] == 2
    assert state["raw"]["id"] == "uuid-1"


def test_read_status_raises_when_issue_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": {"issue": None}})

    adapter = _make_adapter(monkeypatch, handler)
    with pytest.raises(LinearAdapterError) as exc_info:
        adapter.read_status("missing-uuid")
    assert "missing-uuid" in str(exc_info.value)


# -------- list_stale ---------------------------------------------------------

def test_list_stale_returns_canonical_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_vars: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        body = _gql_body(request)
        captured_vars.update(body["variables"])
        return httpx.Response(
            200,
            json={
                "data": {
                    "issues": {
                        "nodes": [
                            {
                                "id": "uuid-1",
                                "identifier": "ENG-1",
                                "title": "T1",
                                "description": "",
                                "state": {"name": "Open"},
                                "assignee": None,
                                "labels": {"nodes": []},
                                "priority": 4,
                                "createdAt": "2026-01-01T00:00:00Z",
                                "updatedAt": "2026-02-01T00:00:00Z",
                                "url": "https://linear.app/x/issue/ENG-1",
                            }
                        ]
                    }
                }
            },
        )

    adapter = _make_adapter(monkeypatch, handler)
    stale = adapter.list_stale(threshold_hours=24)
    assert len(stale) == 1
    assert stale[0]["ticket_id"] == "uuid-1"
    assert captured_vars["teamId"] == _TEST_TEAM_ID
    assert "T" in captured_vars["cutoff"]  # ISO 8601 has a T separator


def test_list_stale_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": {"issues": {"nodes": []}}})

    adapter = _make_adapter(monkeypatch, handler)
    assert adapter.list_stale(threshold_hours=1) == []


# -------- HTTP error paths ---------------------------------------------------

def test_auth_error_on_401(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="invalid token")

    adapter = _make_adapter(monkeypatch, handler)
    with pytest.raises(LinearAuthError) as exc_info:
        adapter.read_status("any")
    assert "401" in str(exc_info.value)
    assert _TEST_TOKEN not in str(exc_info.value)


def test_rate_limit_on_429(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="rate limited")

    adapter = _make_adapter(monkeypatch, handler)
    with pytest.raises(LinearRateLimitError) as exc_info:
        adapter.read_status("any")
    assert "429" in str(exc_info.value)
    assert _TEST_TOKEN not in str(exc_info.value)


def test_server_error_on_500(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="server fire")

    adapter = _make_adapter(monkeypatch, handler)
    with pytest.raises(LinearAdapterError) as exc_info:
        adapter.read_status("any")
    msg = str(exc_info.value)
    assert "500" in msg
    assert _TEST_TOKEN not in msg


def test_non_json_response(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>not json</html>")

    adapter = _make_adapter(monkeypatch, handler)
    with pytest.raises(LinearAdapterError) as exc_info:
        adapter.read_status("any")
    assert "non-JSON" in str(exc_info.value)
    assert _TEST_TOKEN not in str(exc_info.value)


def test_graphql_errors_field_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"errors": [{"message": "Authentication required"}]},
        )

    adapter = _make_adapter(monkeypatch, handler)
    with pytest.raises(LinearAdapterError) as exc_info:
        adapter.read_status("any")
    assert "GraphQL errors" in str(exc_info.value)
    assert _TEST_TOKEN not in str(exc_info.value)


# -------- Token redaction (positive assertion) -------------------------------

def test_safe_redacts_token_when_present(monkeypatch: pytest.MonkeyPatch) -> None:
    """If an upstream string contains the API token, _safe must redact it."""
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text=f"Token {_TEST_TOKEN} rejected")

    adapter = _make_adapter(monkeypatch, handler)
    with pytest.raises(LinearAdapterError) as exc_info:
        adapter.read_status("any")
    msg = str(exc_info.value)
    assert _TEST_TOKEN not in msg
    assert "[REDACTED]" in msg


def test_safe_passes_through_when_token_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A clean upstream string is preserved verbatim."""
    monkeypatch.setenv("LINEAR_API_KEY", _TEST_TOKEN)
    adapter = LinearAdapter(
        team_id=_TEST_TEAM_ID,
        client=_make_client(lambda r: httpx.Response(200, json={"data": {}})),
    )
    assert adapter._safe("normal text") == "normal text"


# -------- create / update mutation contract checks ---------------------------

def test_issue_create_failure_raises_when_success_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = _gql_body(request)
        query = body["query"]
        if "FindIssueByTitlePrefix" in query:
            return httpx.Response(200, json={"data": {"issues": {"nodes": []}}})
        if "CreateIssue" in query:
            return httpx.Response(
                200,
                json={"data": {"issueCreate": {"success": False, "issue": None}}},
            )
        pytest.fail(f"unexpected query: {query!r}")

    adapter = _make_adapter(monkeypatch, handler)
    with pytest.raises(LinearAdapterError):
        adapter.push_payload({"pilot_id": "p", "event_id": "e"})
