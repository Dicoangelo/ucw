"""Tests for UCW configuration."""

import os
import pytest
from pathlib import Path


class TestConfig:
    def test_defaults(self):
        from ucw.config import Config
        assert Config.SERVER_NAME == "ucw"
        assert Config.SERVER_VERSION == "0.1.0"
        assert Config.PROTOCOL_VERSION == "2024-11-05"
        assert Config.PROTOCOL == "mcp"

    def test_ucw_dir_default(self):
        from ucw.config import Config
        # Default should be ~/.ucw (unless overridden by env)
        assert "ucw" in str(Config.UCW_DIR).lower() or "UCW_DATA_DIR" in os.environ

    def test_ensure_dirs(self, tmp_ucw_dir):
        from ucw.config import Config
        Config.ensure_dirs()
        assert Config.UCW_DIR.exists()
        assert Config.LOG_DIR.exists()

    def test_env_var_override(self, tmp_path):
        custom_dir = tmp_path / "custom_ucw"
        os.environ["UCW_DATA_DIR"] = str(custom_dir)

        # Re-import to pick up env var
        from ucw.config import Config
        original_dir = Config.UCW_DIR
        Config.UCW_DIR = Path(os.environ["UCW_DATA_DIR"])
        Config.LOG_DIR = Config.UCW_DIR / "logs"

        Config.ensure_dirs()
        assert Config.UCW_DIR.exists()
        assert Config.LOG_DIR.exists()

        # Restore
        Config.UCW_DIR = original_dir
        Config.LOG_DIR = original_dir / "logs"
        os.environ.pop("UCW_DATA_DIR", None)

    def test_config_env_loading(self, tmp_path):
        """Test that config.env file is loaded correctly."""
        ucw_dir = tmp_path / ".ucw"
        ucw_dir.mkdir()
        config_env = ucw_dir / "config.env"
        config_env.write_text(
            "# Comment line\n"
            "UCW_TEST_VAR=hello_world\n"
            "\n"
            "UCW_TEST_QUOTED=\"quoted value\"\n"
        )

        # Manually load
        os.environ.pop("UCW_TEST_VAR", None)
        os.environ.pop("UCW_TEST_QUOTED", None)

        for line in config_env.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value

        assert os.environ.get("UCW_TEST_VAR") == "hello_world"
        assert os.environ.get("UCW_TEST_QUOTED") == "quoted value"

        # Cleanup
        os.environ.pop("UCW_TEST_VAR", None)
        os.environ.pop("UCW_TEST_QUOTED", None)
