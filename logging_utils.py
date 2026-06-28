"""Logging setup."""
from __future__ import annotations

import logging
from pathlib import Path


def configure_logging(verbose: bool = False, log_path: Path = Path("upload.log")) -> logging.Logger:
    """Configure file and console logging for the application."""
    level = logging.DEBUG if verbose else logging.INFO
    logger = logging.getLogger("carousel_uploader")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level)
    stream_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger
