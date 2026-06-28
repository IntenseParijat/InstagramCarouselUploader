"""Shared utility functions."""
from __future__ import annotations

from pathlib import Path

from config import CaptionConfig


def build_caption(caption_config: CaptionConfig, raw_urls: list[str]) -> str:
    """Build an Instagram caption from configured text, URLs, and hashtags."""
    parts: list[str] = []
    if caption_config.text.strip():
        parts.append(caption_config.text.strip())
    parts.append(caption_config.download_header.strip())
    parts.extend(raw_urls)
    if caption_config.hashtags:
        parts.append(" ".join(caption_config.hashtags))
    return "\n\n".join([parts[0], "\n".join(parts[1:-1]), parts[-1]]) if len(parts) > 2 else "\n".join(parts)


def resolve_chrome_user_data(path: str) -> Path:
    """Resolve a Chrome user-data directory from config or common OS defaults."""
    if path:
        return Path(path).expanduser()
    home = Path.home()
    candidates = [
        home / "AppData/Local/Google/Chrome/User Data",
        home / "Library/Application Support/Google/Chrome",
        home / ".config/google-chrome",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]
