"""
Database compatibility layer for SQLite <-> PostgreSQL.

Céal supports both SQLite (local dev, tests) and PostgreSQL (Cloud Run production).
This module centralizes dialect detection and provides helpers for the few places
where raw SQL differs between backends.

Interview point: "I built a polymorphic database layer that lets the same codebase
run on SQLite for development and PostgreSQL for production — zero code changes
between environments, controlled entirely by DATABASE_URL."
"""

from __future__ import annotations

import os

# ---------------------------------------------------------------------------
# Backend detection
# ---------------------------------------------------------------------------

def get_database_url() -> str:
    """Return the configured DATABASE_URL, defaulting to local SQLite."""
    return os.environ.get(
        "DATABASE_URL",
        "sqlite+aiosqlite:///data/ceal.db",
    )


def is_postgres(url: str | None = None) -> bool:
    """Check if the database URL points to PostgreSQL."""
    db_url = url or get_database_url()
    return db_url.startswith("postgresql")


def is_sqlite(url: str | None = None) -> bool:
    """Check if the database URL points to SQLite."""
    db_url = url or get_database_url()
    return db_url.startswith("sqlite")
