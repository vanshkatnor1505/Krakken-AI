"""
Logging service for Kraken AI.

Provides a centralized Loguru logger configuration with
colored console output and rotating log files.
"""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

from app.config import config


class LogManager:
    """Configures and provides the application logger."""

    def __init__(self) -> None:
        self._configured = False

    def setup(self) -> None:
        """Configure Loguru once."""

        if self._configured:
            return

        logger.remove()

        log_directory: Path = config.logs_dir
        log_directory.mkdir(parents=True, exist_ok=True)

        # Console logger
        logger.add(
            sys.stdout,
            level="DEBUG" if config.debug else "INFO",
            colorize=True,
            backtrace=True,
            diagnose=config.debug,
            enqueue=True,
            format=(
                "<green>{time:HH:mm:ss}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan>"
                " - <level>{message}</level>"
            ),
        )

        # General application log
        logger.add(
            log_directory / "krakken.log",
            rotation="00:00",
            retention="30 days",
            compression="zip",
            level="DEBUG",
            enqueue=True,
            encoding="utf-8",
        )

        # Error log
        logger.add(
            log_directory / "errors.log",
            level="ERROR",
            rotation="10 MB",
            retention="60 days",
            compression="zip",
            enqueue=True,
            encoding="utf-8",
        )

        self._configured = True

        logger.success("Logger initialized successfully.")

    @property
    def instance(self):
        """Return the configured Loguru logger."""
        return logger


log_manager = LogManager()