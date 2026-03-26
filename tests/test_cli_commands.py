"""Tests for UCW doctor and repair CLI commands."""

import sqlite3

import pytest
from click.testing import CliRunner

from ucw.cli import main


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def tmp_db(tmp_ucw_dir):
    """Create a real SQLite database in the temp UCW directory."""
    from ucw.config import Config

    db_path = Config.DB_PATH
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=wal")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS cognitive_events "
        "(id INTEGER PRIMARY KEY, content_length INTEGER, light_topic TEXT, "
        "instinct_gut_signal TEXT)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS sessions (id INTEGER PRIMARY KEY, name TEXT)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_topic ON cognitive_events(light_topic)")
    conn.commit()
    conn.close()
    return db_path


class TestDoctor:
    def test_doctor_no_db(self, runner, tmp_ucw_dir):
        """Doctor when no DB exists should show FAIL for database."""
        result = runner.invoke(main, ["doctor"])
        assert "[FAIL]" in result.output
        assert "Database not found" in result.output

    def test_doctor_with_db(self, runner, tmp_db):
        """Doctor with DB should show PASS for all critical checks."""
        result = runner.invoke(main, ["doctor"])
        assert "[PASS] Python" in result.output
        assert "[PASS] SQLite" in result.output
        assert "[PASS] UCW directory" in result.output
        assert "[PASS] Database:" in result.output
        assert "[PASS] Database writable" in result.output
        assert "[PASS] WAL mode enabled" in result.output

    def test_doctor_exit_code(self, runner, tmp_db):
        """Exit code should be 0 when all critical checks pass."""
        result = runner.invoke(main, ["doctor"])
        assert result.exit_code == 0

    def test_doctor_exit_code_fail(self, runner, tmp_ucw_dir):
        """Exit code should be 1 when there are FAILs (no DB)."""
        result = runner.invoke(main, ["doctor"])
        assert result.exit_code == 1

    def test_doctor_shows_summary(self, runner, tmp_db):
        """Doctor should print a summary line at the end."""
        result = runner.invoke(main, ["doctor"])
        assert "passed" in result.output
        assert "failed" in result.output
        assert "warnings" in result.output

    def test_doctor_optional_deps(self, runner, tmp_db):
        """Doctor should check optional dependencies."""
        result = runner.invoke(main, ["doctor"])
        # At minimum, one of these should appear (PASS or WARN)
        assert "rich" in result.output or "sentence-transformers" in result.output


class TestRepair:
    def test_repair_healthy_db(self, runner, tmp_db):
        """Repair on healthy DB should report all OK/FIX."""
        result = runner.invoke(main, ["repair"])
        assert result.exit_code == 0
        assert "[OK] Integrity check passed" in result.output
        assert "[OK] Quick check passed" in result.output
        assert "VACUUM" in result.output

    def test_repair_check_only(self, runner, tmp_db):
        """--check flag should only run diagnostics, not modify."""
        result = runner.invoke(main, ["repair", "--check"])
        assert result.exit_code == 0
        assert "[OK] Integrity check passed" in result.output
        assert "[FIX]" not in result.output

    def test_repair_no_db(self, runner, tmp_ucw_dir):
        """Repair when no DB exists should show error."""
        result = runner.invoke(main, ["repair"])
        assert result.exit_code == 1
        assert "Database not found" in result.output

    def test_repair_rebuilds_indexes(self, runner, tmp_db):
        """Repair should rebuild indexes."""
        result = runner.invoke(main, ["repair"])
        assert "Rebuilt" in result.output or "No indexes" in result.output

    def test_repair_enables_wal(self, runner, tmp_ucw_dir):
        """Repair should enable WAL mode if not set."""
        from ucw.config import Config

        # Create DB without WAL
        conn = sqlite3.connect(str(Config.DB_PATH))
        conn.execute(
            "CREATE TABLE IF NOT EXISTS test_table (id INTEGER PRIMARY KEY)"
        )
        conn.commit()
        conn.close()

        result = runner.invoke(main, ["repair"])
        assert result.exit_code == 0
        assert "WAL mode" in result.output
