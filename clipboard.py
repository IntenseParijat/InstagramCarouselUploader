"""Clipboard helpers."""
from __future__ import annotations

import logging

import pyperclip


class ClipboardError(RuntimeError):
    """Raised when copying a caption fails."""


def copy_caption(text: str, logger: logging.Logger) -> None:
    """Copy text to the system clipboard using pyperclip."""
    try:
        pyperclip.copy(text)
        logger.info("Caption copied to clipboard (%s characters)", len(text))
    except pyperclip.PyperclipException as exc:
        logger.exception("Clipboard copy failed")
        raise ClipboardError(str(exc)) from exc
