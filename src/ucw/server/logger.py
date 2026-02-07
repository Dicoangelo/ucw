"""
File-only logger — NEVER writes to stdout (would corrupt MCP protocol)
"""

import logging
from pathlib import Path
from ucw.config import Config


def get_logger(name: str) -> logging.Logger:
    """Get a logger that writes to file only."""
    Config.ensure_dirs()

    logger = logging.getLogger(f"ucw.{name}")
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, Config.LOG_LEVEL, logging.DEBUG))

    fh = logging.FileHandler(Config.LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(fh)

    eh = logging.FileHandler(Config.ERROR_LOG, encoding="utf-8")
    eh.setLevel(logging.ERROR)
    eh.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-5s [%(name)s] %(message)s\n%(exc_info)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(eh)

    logger.propagate = False
    return logger
