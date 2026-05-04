"""
TD-006 positive smoke: init_db() must load multi-command DDL blocks
(DO $$...$$ + CREATE TRIGGER + plpgsql function bodies) cleanly against
PostgreSQL. Pre-fix this fails at setup with
"cannot insert multiple commands into a prepared statement".
"""
from __future__ import annotations

import os

import pytest
import pytest_asyncio
from sqlalchemy import text

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")

from src.models.compat import is_sqlite  # noqa: E402
from src.models.database import engine, get_session, init_db  # noqa: E402
from tests.integration.conftest import drop_all_tables  # noqa: E402

pytestmark = [
    pytest.mark.skipif(is_sqlite(), reason="PostgreSQL-only DDL execution path (TD-006)"),
]


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(drop_all_tables)
    await init_db()
    yield
    await engine.dispose()


class TestInitDbMultiCommandDdl:
    @pytest.mark.asyncio
    async def test_trigger_functions_registered_in_pg_proc(self):
        """Both plpgsql functions defined in schema_postgres.sql must exist post-init."""
        async with get_session() as session:
            result = await session.execute(
                text(
                    "SELECT proname FROM pg_proc "
                    "WHERE proname IN ('trg_applications_updated_at_fn', 'update_updated_at_column') "
                    "ORDER BY proname"
                )
            )
        names = {row[0] for row in result}
        assert names == {"trg_applications_updated_at_fn", "update_updated_at_column"}

    @pytest.mark.asyncio
    async def test_triggers_registered_in_pg_trigger(self):
        """Both DO-block-wrapped triggers must be registered after init_db()."""
        async with get_session() as session:
            result = await session.execute(
                text(
                    "SELECT tgname FROM pg_trigger "
                    "WHERE tgname IN ('trg_applications_updated_at', 'trg_jobs_updated_at') "
                    "ORDER BY tgname"
                )
            )
        names = {row[0] for row in result}
        assert names == {"trg_applications_updated_at", "trg_jobs_updated_at"}

    @pytest.mark.asyncio
    async def test_init_db_is_idempotent(self):
        """Re-running init_db() must not error on the multi-command DDL path."""
        await init_db()
        await init_db()
