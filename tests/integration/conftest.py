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
# Marker-based auto-skip: @pytest.mark.sqlite_only tests skip on PostgreSQL
# ---------------------------------------------------------------------------

def pytest_collection_modifyitems(config, items):
    """Skip tests marked sqlite_only when running against PostgreSQL."""
    if is_sqlite():
        return
    skip_pg = pytest.mark.skip(reason="SQLite-only introspection test — skipped on PostgreSQL")
    for item in items:
        if "sqlite_only" in item.keywords:
            item.add_marker(skip_pg)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def drop_all_tables(sync_conn) -> None:
    """
    Drop all tables for clean test isolation.

    Works on both SQLite and PostgreSQL by using SQLAlchemy's inspector
    rather than dialect-specific introspection SQL.
    """
    if is_sqlite():
        sync_conn.execute(sa_text("PRAGMA foreign_keys=OFF"))

    inspector = inspect(sync_conn)
    for table in inspector.get_table_names():
        sync_conn.execute(sa_text(f'DROP TABLE IF EXISTS "{table}"'))  # noqa: S608

    if is_sqlite():
        sync_conn.execute(sa_text("PRAGMA foreign_keys=ON"))
