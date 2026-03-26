"""UCW Error Handling — Actionable error messages for every failure mode."""

import sqlite3
from pathlib import Path


class UCWError(Exception):
    """Base UCW error with actionable message."""
    def __init__(self, message: str, hint: str = ""):
        self.hint = hint
        super().__init__(message)

    def __str__(self):
        msg = super().__str__()
        if self.hint:
            msg += f"\n  Hint: {self.hint}"
        return msg


class DatabaseNotFoundError(UCWError):
    def __init__(self, path):
        super().__init__(
            f"Database not found: {path}",
            "Run `ucw init` to create the database, or `ucw demo` to load sample data."
        )


class DatabaseCorruptError(UCWError):
    def __init__(self, path, detail=""):
        super().__init__(
            f"Database may be corrupt: {path}" + (f" ({detail})" if detail else ""),
            "Run `ucw repair` to attempt automatic repair, or `ucw repair --check` to diagnose."
        )


class DatabaseLockedError(UCWError):
    def __init__(self, path):
        super().__init__(
            f"Database is locked: {path}",
            "Another UCW process may be running. Check with `ps aux | grep ucw` or wait a moment and retry."
        )


class MissingDependencyError(UCWError):
    def __init__(self, package, install_extra):
        super().__init__(
            f"{package} not installed.",
            f"Install with: pip install ucw[{install_extra}]"
        )


class ImportFileError(UCWError):
    def __init__(self, path, platform):
        hints = {
            "chatgpt": "Export your ChatGPT data from Settings > Data Controls > Export Data.",
            "cursor": "Cursor data is usually at ~/.cursor/. Check your Cursor installation.",
            "grok": "Export your Grok data from X Settings > Your Account > Download Archive.",
        }
        super().__init__(
            f"File not found: {path}",
            hints.get(platform, "Check the file path and try again.")
        )


class NoDataError(UCWError):
    def __init__(self):
        super().__init__(
            "No AI conversations captured yet.",
            "Run `ucw demo` to see sample data, or `ucw import` to bring in your history."
        )


def safe_db_connect(db_path, timeout=5.0):
    """Connect to SQLite with graceful error handling.

    Returns (conn, None) on success, (None, error) on failure.
    """
    path = Path(db_path)

    if not path.exists():
        return None, DatabaseNotFoundError(path)

    try:
        conn = sqlite3.connect(str(path), timeout=timeout)
        # Quick health check
        conn.execute("SELECT 1")
        return conn, None
    except sqlite3.DatabaseError as e:
        if "locked" in str(e).lower():
            return None, DatabaseLockedError(path)
        if "corrupt" in str(e).lower() or "malformed" in str(e).lower():
            return None, DatabaseCorruptError(path, str(e))
        return None, UCWError(f"Database error: {e}", "Run `ucw doctor` for diagnostics.")
    except Exception as e:
        return None, UCWError(f"Unexpected error: {e}", "Run `ucw doctor` for diagnostics.")


def check_db_integrity(conn):
    """Run integrity check. Returns (ok: bool, message: str)."""
    try:
        result = conn.execute("PRAGMA integrity_check").fetchone()[0]
        return result == "ok", result
    except Exception as e:
        return False, str(e)


def format_error(error):
    """Format a UCWError for CLI output."""
    if isinstance(error, UCWError):
        msg = f"Error: {error.args[0]}"
        if error.hint:
            msg += f"\n  Hint: {error.hint}"
        return msg
    return f"Error: {error}"
