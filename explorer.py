"""Open Windows Explorer with the current carousel output files selected."""
from __future__ import annotations

from collections.abc import Sequence
import logging
import os
from pathlib import Path
import subprocess
import sys


class ExplorerError(RuntimeError):
    """Raised when output images cannot be handed off to the file manager."""


def open_selected_files(images: Sequence[Path], logger: logging.Logger) -> None:
    """Open the containing folder with only the provided output images selected."""
    if not images:
        raise ExplorerError("No output images were provided")

    resolved = [image.resolve() for image in images]
    folder = resolved[0].parent
    if any(image.parent != folder for image in resolved):
        raise ExplorerError("All output images in a carousel group must be in the same folder")

    if os.name == "nt":
        _open_windows_selection(folder, resolved, logger)
        return

    logger.info("Explorer selection is only available on Windows; opening folder %s", folder)
    opener = ["open", str(folder)] if sys.platform == "darwin" else ["xdg-open", str(folder)]
    try:
        subprocess.Popen(opener)
    except OSError as exc:
        logger.warning("Could not open output folder %s: %s", folder, exc)
        print(f"\nOpen this folder manually: {folder}")


def _open_windows_selection(folder: Path, images: Sequence[Path], logger: logging.Logger) -> None:
    """Use the Windows Shell COM API to select multiple files in Explorer."""
    try:
        import pythoncom
        import win32com.client

        pythoncom.CoInitialize()
        shell = win32com.client.Dispatch("Shell.Application")
        folder_item = shell.Namespace(str(folder))
        if folder_item is None:
            raise ExplorerError(f"Windows Shell could not open folder: {folder}")
        shell.Open(str(folder))
        windows = shell.Windows()
        explorer = None
        target = os.path.normcase(str(folder.resolve()))
        for index in range(windows.Count):
            window = windows.Item(index)
            try:
                current = os.path.normcase(str(Path(window.Document.Folder.Self.Path).resolve()))
                if current == target:
                    explorer = window
                    break
            except Exception:  # noqa: BLE001 - COM windows can expose non-file locations.
                continue
        if explorer is None:
            explorer = windows.Item(windows.Count - 1)
        document = explorer.Document
        document.SelectItem(folder_item.ParseName(images[0].name), 1 | 4 | 8 | 16)
        for image in images[1:]:
            document.SelectItem(folder_item.ParseName(image.name), 1 | 8 | 16)
        logger.info("Explorer opened with %s selected output image(s)", len(images))
    except ImportError as exc:
        logger.warning("pywin32 is unavailable; falling back to selecting the first file only: %s", exc)
        subprocess.Popen(["explorer", f"/select,{images[0]}"])
    except Exception as exc:  # noqa: BLE001 - COM errors should fall back gracefully.
        logger.warning("Windows Explorer multi-selection failed; selecting first file only: %s", exc)
        subprocess.Popen(["explorer", f"/select,{images[0]}"])
