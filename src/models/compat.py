"""
Céal: Database Backend Compatibility Layer

Detects whether the active database is SQLite or PostgreSQL based on
the DATABASE_URL environment variable. All dialect-specific behavior
in database.py branches on these functions.

Interview talking point:
    "The compat layer means the entire application can switch between
    SQLite for local development and PostgreSQL for production by
    changing one environment variable. Zero code changes."
"""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def get_database_url() -> str:
    """Return the configured DATABASE_URL with sensible default."""
    return os.getenv("DATABASE_URL", "sqlite+aiosqlite:///data/ceal.db")


def is_postgres() -> bool:
    """True when the configured backend is PostgreSQL."""
    return get_database_url().startswith("postgresql")


def is_sqlite() -> bool:
    """True when the configured backend is SQLite."""
    return get_database_url().startswith("sqlite")
