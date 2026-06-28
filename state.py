"""Persistent processed-file database."""
from __future__ import annotations

import json
import logging
from pathlib import Path


class ProcessedState:
    """Tracks originals that have already completed the workflow."""

    def __init__(self, path: Path = Path("processed.json")) -> None:
        self.path = path
        self.processed: set[str] = set()

    def load(self, logger: logging.Logger) -> None:
        """Load state from disk, starting empty on corrupt or absent files."""
        if not self.path.exists():
            self.processed = set()
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.processed = {str(item) for item in data.get("processed", [])}
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not read %s; starting with empty state: %s", self.path, exc)
            self.processed = set()

    def contains(self, filename: str) -> bool:
        """Return True when filename is already processed."""
        return filename in self.processed

    def add(self, filename: str) -> None:
        """Mark filename as processed and save immediately."""
        self.processed.add(filename)
        self.save()

    def save(self) -> None:
        """Persist state atomically enough for this local workflow."""
        self.path.write_text(
            json.dumps({"processed": sorted(self.processed)}, indent=2) + "\n",
            encoding="utf-8",
        )
