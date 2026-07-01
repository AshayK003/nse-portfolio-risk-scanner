"""
Shared logging module — provides a loguru-compatible logger with stdlib fallback.

Both app.py and data/prices.py had identical loguru-compat wrappers.
This module is the single source of truth.

Import via:
    from engine._log import logger

Uses loguru when available, falls back to stdlib logging with kwargs-to-format compat.
"""

from __future__ import annotations

import logging
import sys

try:
    from loguru import logger as _loguru_logger

    logger = _loguru_logger
except ImportError:

    class _LoguruCompatLogger:
        """Drop-in replacement for loguru.logger using stdlib logging.

        Supports the loguru-style `logger.info("message {}", var)` syntax
        via __call__, plus the most common loguru methods.
        """

        def __init__(self, name: str = "nse_risk_scanner"):
            self._logger = logging.getLogger(name)
            self._logger.setLevel(logging.INFO)
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(logging.Formatter("%(message)s"))
            if not self._logger.handlers:
                self._logger.addHandler(handler)

        def _log(self, level: int, msg: str, *args, **kwargs) -> None:
            if kwargs:
                msg = msg.format(**kwargs)
            self._logger.log(level, msg, *args)

        def info(self, msg: str, *args, **kwargs) -> None:
            self._log(logging.INFO, msg, *args, **kwargs)

        def warning(self, msg: str, *args, **kwargs) -> None:
            self._log(logging.WARNING, msg, *args, **kwargs)

        def debug(self, msg: str, *args, **kwargs) -> None:
            self._log(logging.DEBUG, msg, *args, **kwargs)

        def error(self, msg: str, *args, **kwargs) -> None:
            self._log(logging.ERROR, msg, *args, **kwargs)

        def exception(self, msg: str, *args, **kwargs) -> None:
            self._log(logging.ERROR, msg, *args, **kwargs)

        def __call__(self, msg: str, *args, **kwargs) -> None:
            """Support loguru-style logger.info(...) as logger(...)."""
            self._log(logging.INFO, msg, *args, **kwargs)

    logger = _LoguruCompatLogger()
