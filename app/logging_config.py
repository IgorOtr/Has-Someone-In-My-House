"""Configuração centralizada de logs."""

from __future__ import annotations

import logging

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging(level: str = "INFO") -> None:
    """Configura o logger raiz com um formato consistente.

    Args:
        level: Nome do nível de log (ex.: ``"INFO"``, ``"DEBUG"``). Usa
            ``INFO`` como padrão quando o valor não é um nível reconhecido.
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
