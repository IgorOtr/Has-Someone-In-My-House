"""Centralized logging configuration."""

from __future__ import annotations

import logging

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging(level: str = "INFO") -> None:
    """Configure the root logger with a consistent format.

    Args:
        level: Logging level name (e.g. ``"INFO"``, ``"DEBUG"``). Falls back
            to ``INFO`` when the value is not a recognized level.
    """
    resolved_level = logging.getLevelName(level.upper())
    if not isinstance(resolved_level, int):
        resolved_level = logging.INFO

    logging.basicConfig(
        level=resolved_level,
        format=_LOG_FORMAT,
        datefmt=_DATE_FORMAT,
        force=True,
    )
