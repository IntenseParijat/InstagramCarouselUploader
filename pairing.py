"""Image discovery and original/output pairing."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
OUTPUT_SUFFIX = "_output"


@dataclass(frozen=True, order=True)
class ImagePair:
    """A matched original image and Instagram-ready output image."""

    key: str
    original: Path
    output: Path


def _is_supported(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS


def scan_image_pairs(folder: Path, logger: logging.Logger) -> list[ImagePair]:
    """Scan a folder and match originals to *_output images by stem."""
    originals: dict[str, Path] = {}
    outputs: dict[str, Path] = {}

    for path in sorted(folder.iterdir(), key=lambda item: item.name.lower()):
        if not _is_supported(path):
            continue
        stem = path.stem
        if stem.lower().endswith(OUTPUT_SUFFIX):
            key = stem[: -len(OUTPUT_SUFFIX)]
            outputs.setdefault(key.lower(), path)
        else:
            originals.setdefault(stem.lower(), path)

    pairs: list[ImagePair] = []
    for key, original in originals.items():
        output = outputs.get(key)
        if output is None:
            logger.warning("Skipping %s because matching *_output image is missing", original.name)
            continue
        pairs.append(ImagePair(key=original.stem, original=original, output=output))

    for key, output in outputs.items():
        if key not in originals:
            logger.warning("Skipping %s because matching original image is missing", output.name)

    return sorted(pairs, key=lambda pair: pair.original.name.lower())
