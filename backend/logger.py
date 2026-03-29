"""Sistema de logging estructurado en JSON con rotación de archivos."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from typing import Any


# ---------------------------------------------------------------------------
# Formatter JSON
# ---------------------------------------------------------------------------

class JSONFormatter(logging.Formatter):
    """Formatea registros de log como JSON en una sola línea."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        # Campos extra pasados con extra={...}
        for key, value in record.__dict__.items():
            if key not in (
                "args", "created", "exc_info", "exc_text", "filename",
                "funcName", "id", "levelname", "levelno", "lineno",
                "message", "module", "msecs", "msg", "name", "pathname",
                "process", "processName", "relativeCreated", "stack_info",
                "thread", "threadName",
            ):
                log_obj.setdefault(key, value)
        return json.dumps(log_obj, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# Configuración del logger
# ---------------------------------------------------------------------------

def setup_logger(name: str = "instantvende") -> logging.Logger:
    """Crea y configura el logger de la aplicación con tres handlers:

    1. Archivo rotativo (JSON) — logs/app.log
    2. Consola (texto legible)
    3. Archivo de errores (JSON) — logs/errors.log
    """
    os.makedirs("logs", exist_ok=True)

    logger = logging.getLogger(name)
    if logger.handlers:
        # Evitar duplicar handlers si se llama múltiples veces
        return logger

    logger.setLevel(logging.INFO)

    # --- Handler 1: archivo rotativo principal (JSON) ---
    file_handler = RotatingFileHandler(
        "logs/app.log",
        maxBytes=10_000_000,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(JSONFormatter())

    # --- Handler 2: consola (texto legible) ---
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(
        logging.Formatter("%(levelname)s  %(name)s  %(message)s")
    )

    # --- Handler 3: archivo de errores (JSON, solo WARNING+) ---
    error_handler = RotatingFileHandler(
        "logs/errors.log",
        maxBytes=5_000_000,  # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.WARNING)
    error_handler.setFormatter(JSONFormatter())

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.addHandler(error_handler)

    return logger


# ---------------------------------------------------------------------------
# Utilidad de log con contexto
# ---------------------------------------------------------------------------

def log_with_context(
    logger: logging.Logger,
    level: str,
    message: str,
    **context: Any,
) -> None:
    """Registra un mensaje incluyendo campos de contexto extra.

    Ejemplo::

        log_with_context(logger, "info", "Mensaje recibido", phone="51999000000", intent="purchase")
    """
    log_fn = getattr(logger, level.lower(), logger.info)
    log_fn(message, extra=context)
