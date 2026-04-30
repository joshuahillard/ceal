"""Linear concrete tracker adapter.

Implements the TrackerAdapter Protocol (see tools/tracker_adapter/__init__.py)
against Linear's GraphQL API. Linear has no Python SDK; we hit the GraphQL
endpoint directly via httpx (already a Ceal dep, see CLAUDE.md).

Auth: personal API token from LINEAR_API_KEY env var, read at instantiation.
The token is treated as a secret -- never logged, never raised in error
messages. _safe redacts the token from any externally-derived string before
it is raised. Verified positively in test_safe_redacts_token_when_present
and across every error-path test.

Idempotency: push_payload uses a deterministic title prefix
"[MavenOS:<pilot_id>:<event_id>]" to detect existing issues. If the prefix
matches an existing issue in this team, issueUpdate fires; otherwise
issueCreate. Linear's filter API supports startsWith on title, so the
match is server-side rather than scanning all team issues.

Stub note: read_status and list_stale return a canonical
ImplementationState dict whose schema is referenced by
Maven_OS_Enterprise_Malleability_Analysis.md Part C. That document is not
in-repo at the time of this commit; the dict shape used here is a working
stub and may evolve when Part C lands.

GraphQL caveat: queries below are written against the public Linear
GraphQL schema as documented late 2025. They are exercised in unit tests
via httpx.MockTransport, NOT against a live Linear workspace. Live smoke
is deferred to a follow-up session.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

LINEAR_GRAPHQL_ENDPOINT = "https://api.linear.app/graphql"


class LinearAdapterError(RuntimeError):
    """Raised when the Linear API returns an unexpected shape or status.

    Never includes the API token in its message. _safe redacts the token
    from any externally-derived string before it is raised or logged.
    """


class LinearAuthError(LinearAdapterError):
    """Raised on missing token at construction or HTTP 401 from Linear."""


class LinearRateLimitError(LinearAdapterError):
    """Raised on HTTP 429 from Linear."""


class LinearAdapter:
    """Concrete TrackerAdapter for Linear.

    Construct with team_id; api_key is read from LINEAR_API_KEY env var
    at instantiation. Pass a custom httpx.Client for testing
    (e.g. with httpx.MockTransport).
    """

    def __init__(
        self,
        team_id: str,
        *,
        client: httpx.Client | None = None,
        endpoint: str = LINEAR_GRAPHQL_ENDPOINT,
    ) -> None:
        self.team_id = team_id
        self.endpoint = endpoint
        api_key = os.environ.get("LINEAR_API_KEY")
        if not api_key:
            raise LinearAuthError(
                "LINEAR_API_KEY env var is not set. "
                "Set it to a Linear personal API token before constructing LinearAdapter."
            )
        self._api_key = api_key
        if client is None:
            client = httpx.Client(
                headers={
                    "Authorization": api_key,
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
        self._client = client

    def push_payload(self, payload: dict) -> str:
        """Create or upsert a Linear issue from a canonical payload.

        payload must contain non-empty 'pilot_id' and 'event_id' (used to
        build the deterministic title prefix). Optional: 'title',
        'description'.

        Returns the Linear issue id (a UUID string).
        """
        pilot_id = payload.get("pilot_id")
        event_id = payload.get("event_id")
        if not pilot_id or not event_id:
            raise LinearAdapterError(
                "payload must include non-empty 'pilot_id' and 'event_id'"
            )
        title_prefix = f"[MavenOS:{pilot_id}:{event_id}]"
        body_title = (payload.get("title") or "").strip()
        title = f"{title_prefix} {body_title}".strip() if body_title else title_prefix
        description = payload.get("description") or ""

        existing_id = self._find_issue_by_title_prefix(title_prefix)
        if existing_id is not None:
            return self._issue_update(existing_id, title=title, description=description)
        return self._issue_create(title=title, description=description)

    def read_status(self, ticket_id: str) -> dict:
        """Return canonical ImplementationState dict for the given Linear issue id.

        Raises LinearAdapterError if the issue cannot be found.
        """
        query = """
        query GetIssue($id: String!) {
          issue(id: $id) {
            id
            identifier
            title
            description
            state { name }
            assignee { name email }
            labels { nodes { name } }
            priority
            createdAt
            updatedAt
            url
          }
        }
        """
        result = self._gql(query, {"id": ticket_id})
        issue = (result.get("data") or {}).get("issue")
        if issue is None:
            raise LinearAdapterError(f"issue not found: {ticket_id!r}")
        return self._to_canonical(issue)

    def list_stale(self, threshold_hours: int) -> list[dict]:
        """List issues in this team whose updatedAt is older than threshold_hours.

        Returns canonical ImplementationState dicts. Empty list when no matches.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=threshold_hours)
        query = """
        query ListStaleIssues($teamId: ID!, $cutoff: DateTime!) {
          issues(
            filter: { team: { id: { eq: $teamId } }, updatedAt: { lt: $cutoff } }
          ) {
            nodes {
              id
              identifier
              title
              description
              state { name }
              assignee { name email }
              labels { nodes { name } }
              priority
              createdAt
              updatedAt
              url
            }
          }
        }
        """
        result = self._gql(
            query,
            {"teamId": self.team_id, "cutoff": cutoff.isoformat()},
        )
        nodes = ((result.get("data") or {}).get("issues") or {}).get("nodes") or []
        return [self._to_canonical(node) for node in nodes]

    def close(self) -> None:
        """Close the underlying HTTP client. Safe to call multiple times."""
        if self._client is not None:
            self._client.close()

    # --- private helpers ---

    def _gql(self, query: str, variables: dict) -> dict[str, Any]:
        """POST a GraphQL query/mutation and return the parsed JSON.

        Raises LinearAuthError on 401, LinearRateLimitError on 429,
        LinearAdapterError on any other non-2xx, non-JSON, or
        GraphQL-error response. Token never appears in raised messages.
        """
        try:
            response = self._client.post(
                self.endpoint,
                json={"query": query, "variables": variables},
            )
        except httpx.HTTPError as e:
            raise LinearAdapterError(
                f"Linear API request failed: {self._safe(str(e))}"
            ) from e

        if response.status_code == 401:
            raise LinearAuthError("Linear API rejected the API token (HTTP 401)")
        if response.status_code == 429:
            raise LinearRateLimitError("Linear API rate limit exceeded (HTTP 429)")
        if not (200 <= response.status_code < 300):
            raise LinearAdapterError(
                f"Linear API returned HTTP {response.status_code}: "
                f"{self._safe(response.text[:500])}"
            )

        try:
            payload = response.json()
        except ValueError as e:
            raise LinearAdapterError(
                f"Linear API returned non-JSON: {self._safe(response.text[:200])}"
            ) from e

        if isinstance(payload, dict) and payload.get("errors"):
            raise LinearAdapterError(
                f"Linear GraphQL errors: {self._safe(str(payload['errors']))}"
            )
        return payload

    def _safe(self, text: str) -> str:
        """Redact the API token from a string before logging or raising."""
        if self._api_key and self._api_key in text:
            return text.replace(self._api_key, "[REDACTED]")
        return text

    def _find_issue_by_title_prefix(self, prefix: str) -> str | None:
        query = """
        query FindIssueByTitlePrefix($teamId: ID!, $prefix: String!) {
          issues(
            filter: { team: { id: { eq: $teamId } }, title: { startsWith: $prefix } }
            first: 1
          ) {
            nodes { id }
          }
        }
        """
        result = self._gql(query, {"teamId": self.team_id, "prefix": prefix})
        nodes = ((result.get("data") or {}).get("issues") or {}).get("nodes") or []
        return nodes[0].get("id") if nodes else None

    def _issue_create(self, *, title: str, description: str) -> str:
        mutation = """
        mutation CreateIssue($input: IssueCreateInput!) {
          issueCreate(input: $input) {
            success
            issue { id }
          }
        }
        """
        result = self._gql(
            mutation,
            {
                "input": {
                    "teamId": self.team_id,
                    "title": title,
                    "description": description,
                }
            },
        )
        payload = (result.get("data") or {}).get("issueCreate") or {}
        if not payload.get("success") or not (payload.get("issue") or {}).get("id"):
            raise LinearAdapterError("issueCreate returned no usable issue payload")
        return payload["issue"]["id"]

    def _issue_update(self, issue_id: str, *, title: str, description: str) -> str:
        mutation = """
        mutation UpdateIssue($id: String!, $input: IssueUpdateInput!) {
          issueUpdate(id: $id, input: $input) {
            success
            issue { id }
          }
        }
        """
        result = self._gql(
            mutation,
            {"id": issue_id, "input": {"title": title, "description": description}},
        )
        payload = (result.get("data") or {}).get("issueUpdate") or {}
        if not payload.get("success") or not (payload.get("issue") or {}).get("id"):
            raise LinearAdapterError("issueUpdate returned no usable issue payload")
        return payload["issue"]["id"]

    @staticmethod
    def _to_canonical(issue: dict) -> dict:
        """Map a Linear issue node to the canonical ImplementationState dict.

        Stub schema (revise when Maven_OS_Enterprise_Malleability_Analysis.md
        Part C lands in-repo):

            ticket_id:   str | None  tracker-native id (Linear UUID)
            identifier:  str | None  human-readable id (e.g. "ENG-123")
            title:       str
            description: str
            state:       str | None  tracker-native state name
            assignee:    dict | None {name, email}
            labels:      list[str]
            priority:    int | None  Linear: 0=None, 1=Urgent, 2=High, 3=Med, 4=Low
            created_at:  str | None  ISO 8601
            updated_at:  str | None  ISO 8601
            url:         str | None  human-clickable
            raw:         dict        original payload, for debugging
        """
        labels_node = (issue.get("labels") or {}).get("nodes") or []
        return {
            "ticket_id": issue.get("id"),
            "identifier": issue.get("identifier"),
            "title": issue.get("title") or "",
            "description": issue.get("description") or "",
            "state": (issue.get("state") or {}).get("name"),
            "assignee": issue.get("assignee"),
            "labels": [label["name"] for label in labels_node if label.get("name")],
            "priority": issue.get("priority"),
            "created_at": issue.get("createdAt"),
            "updated_at": issue.get("updatedAt"),
            "url": issue.get("url"),
            "raw": issue,
        }
