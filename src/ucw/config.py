"""
UCW Configuration — Unified settings for the MCP server

Load order: env vars > ~/.ucw/config.env > defaults
"""

import os
from pathlib import Path


def _load_config_env():
    """Load key=value pairs from ~/.ucw/config.env if it exists."""
    config_file = Path.home() / ".ucw" / "config.env"
    if not config_file.exists():
        return
    for line in config_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


# Load config.env before reading env vars
_load_config_env()


class Config:
    # Server identity
    SERVER_NAME = "ucw"
    SERVER_VERSION = "0.1.0"
    PROTOCOL_VERSION = "2024-11-05"

    # Platform identification
    PLATFORM = os.environ.get("UCW_PLATFORM", "claude-desktop")
    PROTOCOL = "mcp"

    # Paths
    UCW_DIR = Path(os.environ.get("UCW_DATA_DIR", str(Path.home() / ".ucw")))
    LOG_DIR = UCW_DIR / "logs"
    DB_PATH = UCW_DIR / "cognitive.db"

    # Logging (NEVER to stdout — would corrupt MCP protocol)
    LOG_LEVEL = os.environ.get("UCW_LOG_LEVEL", "DEBUG")
    LOG_FILE = LOG_DIR / "ucw.log"
    ERROR_LOG = LOG_DIR / "ucw-errors.log"

    # Capture settings
    CAPTURE_RAW_BYTES = True
    ENABLE_UCW_LAYERS = True

    @classmethod
    def ensure_dirs(cls):
        """Create required directories."""
        cls.UCW_DIR.mkdir(parents=True, exist_ok=True)
        cls.LOG_DIR.mkdir(parents=True, exist_ok=True)
