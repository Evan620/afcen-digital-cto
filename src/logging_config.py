"""Structured logging configuration for Digital CTO.

Provides JSON-formatted logs for production with proper correlation IDs
and request tracing.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

from pythonjsonlogger import jsonlogger

from src.config import settings


# ── Custom JSON Formatter ──


class DigitalCTOJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with Digital CTO specific fields."""

    def add_fields(self, log_record: dict, record: logging.LogRecord, message_dict: dict) -> None:
        super().add_fields(log_record, record, message_dict)

        # Add Digital CTO specific fields
        log_record["environment"] = settings.environment
        log_record["service"] = "digital_cto"

        # Add timestamp if not present
        if "timestamp" not in log_record:
            log_record["timestamp"] = datetime.utcnow().isoformat() + "Z"

        # Simplify level name
        log_record["level"] = record.levelname.lower()

        # Remove redundant fields
        log_record.pop("asctime", None)
        log_record.pop("msecs", None)
        log_record.pop("relativeCreated", None)


# ── Console Formatter for Development ──


class ColorFormatter(logging.Formatter):
    """Colored console formatter for development."""

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",    # Cyan
        "INFO": "\033[32m",     # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",    # Red
        "CRITICAL": "\033[35m", # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        # Add color to levelname
        levelcolor = self.COLORS.get(record.levelname, "")
        record.levelname = f"{levelcolor}{record.levelname}{self.RESET}"
        return super().format(record)


# ── Setup Logging ──


def setup_logging() -> logging.Logger:
    """Configure structured logging for the application.

    Returns:
        The root logger
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    # Clear existing handlers
    root_logger.handlers.clear()

    if settings.environment == "production":
        # JSON handler for production
        json_handler = logging.StreamHandler(sys.stdout)
        json_handler.setFormatter(DigitalCTOJsonFormatter(
            fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
            timestamp=True,
        ))
        root_logger.addHandler(json_handler)
    else:
        # Colored console handler for development
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(ColorFormatter(
            fmt="%(asctime)s | %(name)-30s | %(levelname)-8s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        root_logger.addHandler(console_handler)

    # Set log levels for noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)

    return root_logger


# Initialize logging on import
logger = setup_logging()
