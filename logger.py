"""
Professional VSA Swing Scanner
Logging System
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager

from config import (
    LOG_FILE,
    LOG_LEVEL,
    LOG_TO_FILE,
)


class Log:

    _logger = None

    # ------------------------------------------------------------------
    # Initialize
    # ------------------------------------------------------------------

    @classmethod
    def initialize(cls):

        if cls._logger is not None:
            return

        logger = logging.getLogger("VSA")

        logger.setLevel(
            getattr(logging, LOG_LEVEL.upper())
        )

        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(message)s",
            datefmt="%H:%M:%S",
        )

        console = logging.StreamHandler()

        console.setFormatter(formatter)

        logger.addHandler(console)

        if LOG_TO_FILE:

            file_handler = logging.FileHandler(
                LOG_FILE,
                encoding="utf-8",
            )

            file_handler.setFormatter(formatter)

            logger.addHandler(file_handler)

        logger.propagate = False

        cls._logger = logger

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    @classmethod
    def debug(cls, message: str, *args):

        cls.initialize()

        cls._logger.debug(message, *args)
    
    
    @classmethod
    def info(cls, message: str, *args):

        cls.initialize()

        cls._logger.info(message, *args)

    @classmethod
    def warn(cls, message: str, *args):

        cls.initialize()

        cls._logger.warning(message, *args)

    @classmethod
    def error(cls, message: str, *args):

        cls.initialize()

        cls._logger.error(message, *args)

    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------

    @classmethod
    def divider(cls):

        cls.info("-" * 70)

    @classmethod
    def section(cls, title: str):

        cls.info("")

        cls.info("=" * 70)

        cls.info(title.upper())

        cls.info("=" * 70)

    # ------------------------------------------------------------------
    # Timer
    # ------------------------------------------------------------------

    @classmethod
    @contextmanager
    def timer(cls, task: str):

        cls.initialize()

        start = time.perf_counter()

        cls.info(f"{task} started")

        try:

            yield

        finally:

            elapsed = (
                time.perf_counter()
                - start
            ) * 1000

            cls.info(
                f"{task} completed ({elapsed:.1f} ms)"
            )

# ------------------------------------------------------------------
# Initialize logger on import
# ------------------------------------------------------------------

Log.initialize()            