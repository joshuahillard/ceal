"""
Céal Alembic Environment — Async SQLite Migration Runner

Configures Alembic to use async engine (aiosqlite) matching the
production database.py configuration. Phase 2 tables only —
Phase 1 DDL remains in schema.sql.

[ETL Architect]: The render_as_batch=True flag is critical for SQLite.
SQLite doesn't support ALTER TABLE for most operations, so Alembic
uses batch mode: create new table → copy data → drop old → rename.
This is transparent to us but essential for migration correctness.
"""
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from src.tailoring.db_models import PHASE1_STUB_TABLES, Base

# Alembic Config object — provides access to .ini file values
config = context.config

# Set up Python logging from .ini config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Phase 2 ORM metadata — this is what Alembic autogenerates against
target_metadata = Base.metadata


def include_object(object, name, type_, reflected, compare_to):
    """
    Filter out Phase 1 stub tables from Alembic migration generation.

    Phase 1 tables (job_listings, resume_profiles) are defined as ORM stubs
    solely for FK resolution. Their DDL is managed by schema.sql, not Alembic.
    """
    return not (type_ == "table" and name in PHASE1_STUB_TABLES)


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode — emit SQL without connecting.

    Useful for generating migration scripts to review before applying.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # Required for SQLite ALTER TABLE support
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    """Configure context with connection and run migrations."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,  # Required for SQLite ALTER TABLE support
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Run migrations using async engine matching production config.

    Creates async engine from alembic.ini settings, connects,
    then delegates to synchronous migration runner via run_sync.
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode with async engine."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
