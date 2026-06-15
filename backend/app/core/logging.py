"""Структурное JSON-логирование."""

import logging

from pythonjsonlogger import json as jsonlogger


def configure_logging(level: str = "INFO") -> None:
    """Настроить корневой логгер на JSON-формат."""
    handler = logging.StreamHandler()
    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        rename_fields={"asctime": "timestamp", "levelname": "level"},
    )
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
