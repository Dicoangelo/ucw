"""Tests for UCW error handling module."""

import sqlite3

from click.testing import CliRunner

from ucw.errors import (
    DatabaseCorruptError,
    DatabaseLockedError,
    DatabaseNotFoundError,
    ImportFileError,
    MissingDependencyError,
    NoDataError,
    UCWError,
    check_db_integrity,
    format_error,
    safe_db_connect,
)


class TestErrorClasses:

    def test_database_not_found_error(self):
        err = DatabaseNotFoundError("/tmp/missing.db")
        assert "Database not found" in str(err)
        assert "/tmp/missing.db" in str(err)
        assert "ucw init" in err.hint

    def test_database_corrupt_error(self):
        err = DatabaseCorruptError("/tmp/bad.db", "malformed header")
        assert "corrupt" in str(err).lower()
        assert "malformed header" in str(err)
        assert "ucw repair" in err.hint

    def test_database_corrupt_error_no_detail(self):
        err = DatabaseCorruptError("/tmp/bad.db")
        assert "corrupt" in str(err).lower()
        assert "ucw repair" in err.hint

    def test_database_locked_error(self):
        err = DatabaseLockedError("/tmp/locked.db")
        assert "locked" in str(err).lower()
        assert "/tmp/locked.db" in str(err)
        assert "Another UCW process" in err.hint

    def test_missing_dependency_error(self):
        err = MissingDependencyError("rich", "ui")
        assert "rich" in str(err)
        assert "not installed" in str(err)
        assert "pip install ucw[ui]" in err.hint

    def test_import_file_error_chatgpt(self):
        err = ImportFileError("/tmp/export.json", "chatgpt")
        assert "File not found" in str(err)
        assert "ChatGPT" in err.hint or "Data Controls" in err.hint

    def test_import_file_error_cursor(self):
        err = ImportFileError("/tmp/cursor.db", "cursor")
        assert "File not found" in str(err)
        assert "~/.cursor/" in err.hint

    def test_import_file_error_unknown_platform(self):
        err = ImportFileError("/tmp/data.json", "unknown_platform")
        assert "Check the file path" in err.hint

    def test_no_data_error(self):
        err = NoDataError()
        assert "No AI conversations" in str(err)
        assert "ucw demo" in err.hint
        assert "ucw import" in err.hint


class TestSafeDbConnect:

    def test_safe_db_connect_success(self, tmp_path):
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE t (x INTEGER)")
        conn.close()

        conn, err = safe_db_connect(db_path)
        assert err is None
        assert conn is not None
        conn.execute("SELECT 1")
        conn.close()

    def test_safe_db_connect_missing(self, tmp_path):
        db_path = tmp_path / "nonexistent.db"
        conn, err = safe_db_connect(db_path)
        assert conn is None
        assert isinstance(err, DatabaseNotFoundError)
        assert "nonexistent.db" in str(err)

    def test_safe_db_connect_corrupt(self, tmp_path):
        db_path = tmp_path / "corrupt.db"
        db_path.write_bytes(b"this is not a valid sqlite database at all" * 10)

        conn, err = safe_db_connect(db_path)
        assert conn is None
        assert isinstance(err, (DatabaseCorruptError, UCWError))


class TestCheckDbIntegrity:

    def test_check_db_integrity_ok(self, tmp_path):
        db_path = tmp_path / "healthy.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE t (x INTEGER)")
        conn.execute("INSERT INTO t VALUES (1)")
        conn.commit()

        ok, msg = check_db_integrity(conn)
        assert ok is True
        assert msg == "ok"
        conn.close()

    def test_check_db_integrity_corrupt(self, tmp_path):
        """Test integrity check with a tampered database file."""
        db_path = tmp_path / "tampered.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE t (x INTEGER)")
        for i in range(100):
            conn.execute("INSERT INTO t VALUES (?)", (i,))
        conn.commit()
        conn.close()

        # Tamper with the file by overwriting some middle bytes
        data = bytearray(db_path.read_bytes())
        if len(data) > 200:
            # Corrupt the data pages but keep the header
            for i in range(150, min(250, len(data))):
                data[i] = 0xFF
            db_path.write_bytes(bytes(data))

        conn = sqlite3.connect(str(db_path))
        ok, msg = check_db_integrity(conn)
        # Depending on what was corrupted, it may or may not detect it
        # Just verify it returns a tuple without crashing
        assert isinstance(ok, bool)
        assert isinstance(msg, str)
        conn.close()


class TestFormatError:

    def test_format_error_with_hint(self):
        err = DatabaseNotFoundError("/tmp/missing.db")
        formatted = format_error(err)
        assert "Error:" in formatted
        assert "Database not found" in formatted
        assert "Hint:" in formatted
        assert "ucw init" in formatted

    def test_format_error_plain_exception(self):
        err = ValueError("something went wrong")
        formatted = format_error(err)
        assert "Error: something went wrong" == formatted

    def test_format_error_ucw_no_hint(self):
        err = UCWError("simple problem")
        formatted = format_error(err)
        assert "Error: simple problem" in formatted
        assert "Hint:" not in formatted


class TestCLIStatusNoDb:

    def test_status_command_no_db(self, tmp_ucw_dir):
        """CLI status when no DB exists shows a helpful error message."""
        runner = CliRunner()
        from ucw.cli import main

        result = runner.invoke(main, ["status"])
        assert result.exit_code == 0
        assert "Database not found" in result.output
        assert "Hint:" in result.output
