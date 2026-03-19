"""
Centralised logging configuration.

  - DEBUG+  →  rotating file handler  (bot.log, 5 MB × 3 backups)
  - INFO+   →  stdout console handler
  - DEBUG+  →  stdout when --verbose is passed

Call ``configure_logging()`` exactly once at application startup before
the first ``get_logger()`` call in any module.
"""

import logging
import logging.handlers
import sys
from pathlib import Path

LOG_FILE = Path("bot.log")
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False


def configure_logging(verbose: bool = False) -> None:
    """
    Wire up file and console handlers on the root logger.

    Safe to call multiple times — only the first call has any effect.

    Args:
        verbose: When ``True``, emit DEBUG messages on the console too.
    """
    global _configured
    if _configured:
        return

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)  # Handlers control their own minimum level

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    # Rotating file handler — captures DEBUG and above
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE,
        maxBytes=5 * 1024 * 1024,  # 5 MB per file
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # Console handler — INFO by default, DEBUG when --verbose is active
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    console_handler.setFormatter(formatter)

    root.addHandler(file_handler)
    root.addHandler(console_handler)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """
    Return a named child logger.

    ``configure_logging()`` must be called before the first log statement;
    this function itself does *not* trigger configuration.
    """
    return logging.getLogger(name)
