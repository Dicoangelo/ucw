"""Tests for UCW file-only logger."""

import logging

from ucw.server.logger import get_logger


class TestGetLogger:
    def test_returns_logger(self, tmp_ucw_dir):
        log = get_logger("test_module")
        assert isinstance(log, logging.Logger)

    def test_logger_name_prefixed(self, tmp_ucw_dir):
        log = get_logger("mymodule")
        assert log.name == "ucw.mymodule"

    def test_logger_does_not_propagate(self, tmp_ucw_dir):
        log = get_logger("no_propagate")
        assert log.propagate is False

    def test_logger_has_file_handlers(self, tmp_ucw_dir):
        log = get_logger("handlers_check")
        assert len(log.handlers) >= 1
        handler_types = [type(h).__name__ for h in log.handlers]
        assert "FileHandler" in handler_types

    def test_same_logger_returned_on_repeat_call(self, tmp_ucw_dir):
        log1 = get_logger("repeated")
        log2 = get_logger("repeated")
        assert log1 is log2

    def test_logger_writes_to_file(self, tmp_ucw_dir):
        log = get_logger("filewrite")
        log.info("test message for file logging")

        from ucw.config import Config
        log_content = Config.LOG_FILE.read_text()
        assert "test message for file logging" in log_content

    def test_error_log_captures_errors(self, tmp_ucw_dir):
        log = get_logger("errorlog")
        log.error("critical failure test")

        from ucw.config import Config
        err_content = Config.ERROR_LOG.read_text()
        assert "critical failure test" in err_content

    def test_different_modules_get_different_loggers(self, tmp_ucw_dir):
        log_a = get_logger("mod_alpha")
        log_b = get_logger("mod_beta")
        assert log_a is not log_b
        assert log_a.name != log_b.name
