"""Shared fixtures for UCW tests."""

import os
import pytest
from pathlib import Path


@pytest.fixture
def tmp_ucw_dir(tmp_path):
    """Set UCW_DATA_DIR to a temp directory for isolated tests."""
    ucw_dir = tmp_path / ".ucw"
    ucw_dir.mkdir()
    (ucw_dir / "logs").mkdir()
    os.environ["UCW_DATA_DIR"] = str(ucw_dir)

    # Reload config to pick up new env var
    from ucw import config
    config.Config.UCW_DIR = ucw_dir
    config.Config.LOG_DIR = ucw_dir / "logs"
    config.Config.DB_PATH = ucw_dir / "cognitive.db"
    config.Config.LOG_FILE = ucw_dir / "logs" / "ucw.log"
    config.Config.ERROR_LOG = ucw_dir / "logs" / "ucw-errors.log"

    yield ucw_dir

    # Cleanup
    os.environ.pop("UCW_DATA_DIR", None)
