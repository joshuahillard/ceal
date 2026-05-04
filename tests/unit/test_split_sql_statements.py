"""
Pure-function tests for _split_sql_statements().

Regression coverage for TD-006: a CREATE TRIGGER line *inside* a
PostgreSQL DO $$ ... $$ block must not poison the splitter's
SQLite-trigger tracking. Pre-fix, this caused the loader to emit one
giant 4262-char "statement" containing many separate commands, which
asyncpg's prepared protocol then rejected.
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")

from src.models.database import _split_sql_statements  # noqa: E402


class TestSplitSqlStatementsSqliteTriggers:
    def test_sqlite_trigger_block_emits_as_single_statement(self):
        sql = """
        CREATE TABLE t (id INTEGER PRIMARY KEY, updated_at TEXT);

        CREATE TRIGGER trg_t_updated_at
            AFTER UPDATE ON t
            FOR EACH ROW
        BEGIN
            UPDATE t SET updated_at = datetime('now') WHERE id = NEW.id;
        END;

        CREATE TABLE other (id INTEGER PRIMARY KEY);
        """
        stmts = _split_sql_statements(sql)
        assert len(stmts) == 3
        assert stmts[0].startswith("CREATE TABLE t")
        assert stmts[1].startswith("CREATE TRIGGER trg_t_updated_at")
        assert "UPDATE t SET updated_at" in stmts[1]
        assert stmts[2].startswith("CREATE TABLE other")


class TestSplitSqlStatementsPostgresDollarQuotes:
    def test_create_trigger_inside_do_block_does_not_poison_state(self):
        """TD-006 regression: CREATE TRIGGER inside DO $$...$$ must stay scoped."""
        sql = """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_x') THEN
                CREATE TRIGGER trg_x BEFORE UPDATE ON t FOR EACH ROW EXECUTE FUNCTION fn();
            END IF;
        END;
        $$;

        CREATE INDEX idx_a ON t(a);
        CREATE INDEX idx_b ON t(b);
        """
        stmts = _split_sql_statements(sql)
        assert len(stmts) == 3, f"expected 3 statements, got {len(stmts)}: {[s[:60] for s in stmts]}"
        assert stmts[0].startswith("DO $$")
        assert stmts[0].endswith("$$")
        assert stmts[1] == "CREATE INDEX idx_a ON t(a)"
        assert stmts[2] == "CREATE INDEX idx_b ON t(b)"

    def test_plpgsql_function_body_emits_as_single_statement(self):
        sql = """
        CREATE OR REPLACE FUNCTION fn() RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE INDEX idx_a ON t(a);
        """
        stmts = _split_sql_statements(sql)
        assert len(stmts) == 2
        assert stmts[0].startswith("CREATE OR REPLACE FUNCTION fn()")
        assert "LANGUAGE plpgsql" in stmts[0]
        assert stmts[1] == "CREATE INDEX idx_a ON t(a)"

    def test_real_schema_postgres_emits_expected_statement_count(self):
        """Pinned regression on the real schema: pre-fix=18, post-fix=37."""
        from pathlib import Path

        schema = Path("src/models/schema_postgres.sql").read_text()
        stmts = _split_sql_statements(schema)
        assert len(stmts) >= 30, (
            f"splitter regression: only {len(stmts)} statements emitted "
            f"(expected ~37). The CREATE-TRIGGER-inside-DO-block guard may have regressed."
        )

        # A properly bounded statement opens and closes its dollar-quote exactly
        # once: a plpgsql function or a DO block contains exactly one $$...$$ pair.
        # Pre-fix #17 had three pairs (6 markers) by absorbing 15 indexes +
        # a second function + a second DO block + 2 INSERTs.
        for stmt in stmts:
            marker_count = stmt.count("$$")
            assert marker_count in (0, 2), (
                f"splitter emitted statement with {marker_count} '$$' markers "
                f"(expected 0 or 2): {stmt[:120]!r}..."
            )
