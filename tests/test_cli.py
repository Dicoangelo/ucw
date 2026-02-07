"""Tests for UCW CLI."""

import json
import pytest
from click.testing import CliRunner
from ucw.cli import main


class TestCLI:
    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_version(self, runner):
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_init(self, runner, tmp_ucw_dir):
        result = runner.invoke(main, ["init"])
        assert result.exit_code == 0
        assert "UCW initialized" in result.output
        assert (tmp_ucw_dir / "config.env").exists()

    def test_init_creates_config_env(self, runner, tmp_ucw_dir):
        # Remove config.env if it exists
        config_env = tmp_ucw_dir / "config.env"
        if config_env.exists():
            config_env.unlink()

        result = runner.invoke(main, ["init"])
        assert result.exit_code == 0
        assert config_env.exists()
        content = config_env.read_text()
        assert "UCW Configuration" in content

    def test_init_preserves_existing_config(self, runner, tmp_ucw_dir):
        config_env = tmp_ucw_dir / "config.env"
        config_env.write_text("MY_CUSTOM=value\n")

        result = runner.invoke(main, ["init"])
        assert result.exit_code == 0
        # Should NOT overwrite existing config
        assert config_env.read_text() == "MY_CUSTOM=value\n"

    def test_mcp_config(self, runner):
        result = runner.invoke(main, ["mcp-config"])
        assert result.exit_code == 0
        assert "mcpServers" in result.output
        assert "ucw" in result.output

    def test_status_no_db(self, runner, tmp_ucw_dir):
        result = runner.invoke(main, ["status"])
        assert result.exit_code == 0
        assert "No database found" in result.output
