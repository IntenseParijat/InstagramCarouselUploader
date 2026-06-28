"""Shared utility functions."""
from __future__ import annotations

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
