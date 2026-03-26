"""
Schema Migration System — Safe, incremental database changes.

Each migration has up() and down() functions. State tracked in schema_migrations table.
Migrations are idempotent — running twice produces the same result.
"""

import importlib
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Tuple

from ucw.server.logger import get_logger

log = get_logger("migrations")

MIGRATIONS_DIR = Path(__file__).parent / "migrations"

MIGRATION_TRACKING_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    applied_at  TEXT DEFAULT (datetime('now')),
    checksum    TEXT
);
"""


def _ensure_tracking_table(conn: sqlite3.Connection) -> None:
    conn.executescript(MIGRATION_TRACKING_SQL)
    conn.commit()


def _applied_versions(conn: sqlite3.Connection) -> set:
    _ensure_tracking_table(conn)
    cur = conn.execute("SELECT version FROM schema_migrations ORDER BY version")
    return {row[0] for row in cur.fetchall()}


def _discover_migrations() -> List[Tuple[int, str, str]]:
    """Discover migration modules in migrations/ dir.

    Returns sorted (version, name, module_name).
    """
    migrations = []
    if not MIGRATIONS_DIR.exists():
        return migrations
    for path in sorted(MIGRATIONS_DIR.glob("*.py")):
        if path.name.startswith("__"):
            continue
        parts = path.stem.split("_", 1)
        if len(parts) < 2 or not parts[0].isdigit():
            continue
        version = int(parts[0])
        name = parts[1]
        module_name = f"ucw.db.migrations.{path.stem}"
        migrations.append((version, name, module_name))
    return migrations


def get_status(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Get migration status — applied and pending."""
    applied = _applied_versions(conn)
    discovered = _discover_migrations()
    result = []
    for version, name, _ in discovered:
        result.append({
            "version": version,
            "name": name,
            "applied": version in applied,
        })
    return result


def migrate_up(conn: sqlite3.Connection) -> List[str]:
    """Apply all pending migrations. Returns list of applied migration names."""
    applied = _applied_versions(conn)
    discovered = _discover_migrations()
    results = []

    for version, name, module_name in discovered:
        if version in applied:
            continue
        try:
            mod = importlib.import_module(module_name)
            if not hasattr(mod, "up"):
                log.warning(f"Migration {name} has no up() function, skipping")
                continue

            log.info(f"Applying migration {version:03d}_{name}")
            mod.up(conn)
            conn.execute(
                "INSERT OR IGNORE INTO schema_migrations (version, name) VALUES (?, ?)",
                (version, f"{version:03d}_{name}"),
            )
            conn.commit()
            results.append(f"{version:03d}_{name}")
            log.info(f"Migration {version:03d}_{name} applied")
        except Exception as exc:
            conn.rollback()
            log.error(f"Migration {version:03d}_{name} failed: {exc}")
            raise RuntimeError(f"Migration {version:03d}_{name} failed: {exc}") from exc

    return results


def migrate_down(conn: sqlite3.Connection, target_version: int = 0) -> List[str]:
    """Rollback migrations down to target_version. Returns list of rolled-back names."""
    applied = _applied_versions(conn)
    discovered = _discover_migrations()
    results = []

    for version, name, module_name in reversed(discovered):
        if version not in applied or version <= target_version:
            continue
        try:
            mod = importlib.import_module(module_name)
            if not hasattr(mod, "down"):
                log.warning(f"Migration {name} has no down() function, skipping")
                continue

            log.info(f"Rolling back migration {version:03d}_{name}")
            mod.down(conn)
            conn.execute("DELETE FROM schema_migrations WHERE version = ?", (version,))
            conn.commit()
            results.append(f"{version:03d}_{name}")
        except Exception as exc:
            conn.rollback()
            log.error(f"Rollback {version:03d}_{name} failed: {exc}")
            raise RuntimeError(f"Rollback {version:03d}_{name} failed: {exc}") from exc

    return results
