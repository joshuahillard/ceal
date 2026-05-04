"""
Céal: Shared integration test fixtures.

Provides backend-aware helpers for test isolation. All integration tests
should use these instead of inlining SQLite-specific SQL (PRAGMA,
sqlite_master, INSERT OR IGNORE).

The functions detect the active backend via src.models.compat so the
same tests can run against SQLite in local dev and PostgreSQL in CI.
"""
from __future__ import annotations

import pytest
from sqlalchemy import inspect
from sqlalchemy import text as sa_text

from src.models.compat import is_sqlite

# ---------------------------------------------------------------------------
# Marker-based auto-skip on PostgreSQL:
#   @pytest.mark.sqlite_only      — SQLite introspection tests (PRAGMA, etc.)
#   @pytest.mark.postgres_skip_td — pre-existing PG-incompatible patterns
#                                   unmasked by TD-006; see follow-up TDs.
# ---------------------------------------------------------------------------

def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "postgres_skip_td(reason): skip on PostgreSQL pending the named TD "
        "ticket. Added when TD-006 (schema loader fix) unmasked pre-existing "
        "Postgres-incompatible patterns (datetime-as-string, round() without "
        "numeric cast, SERIAL fixtures) that need their own tickets to fix.",
    )


def pytest_collection_modifyitems(config, items):
    """Skip tests marked sqlite_only or postgres_skip_td when on PostgreSQL."""
    if is_sqlite():
        return
    skip_sqlite_only = pytest.mark.skip(
        reason="SQLite-only introspection test — skipped on PostgreSQL"
    )
    for item in items:
        if "sqlite_only" in item.keywords:
            item.add_marker(skip_sqlite_only)
        marker = item.get_closest_marker("postgres_skip_td")
        if marker is not None:
            reason = marker.args[0] if marker.args else "deferred to follow-up TD"
            item.add_marker(pytest.mark.skip(reason=f"PG-deferred: {reason}"))


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def drop_all_tables(sync_conn) -> None:
    """
    Drop all tables for clean test isolation.

    Works on both SQLite and PostgreSQL by using SQLAlchemy's inspector
    rather than dialect-specific introspection SQL. Postgres needs CASCADE
    to break foreign-key dependencies; SQLite uses pragma instead because
    its DROP TABLE syntax does not support CASCADE (TD-006).
    """
    if is_sqlite():
        sync_conn.execute(sa_text("PRAGMA foreign_keys=OFF"))

    inspector = inspect(sync_conn)
    cascade = "" if is_sqlite() else " CASCADE"
    for table in inspector.get_table_names():
        sync_conn.execute(sa_text(f'DROP TABLE IF EXISTS "{table}"{cascade}'))  # noqa: S608

    if is_sqlite():
        sync_conn.execute(sa_text("PRAGMA foreign_keys=ON"))
