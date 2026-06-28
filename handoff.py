"""Manual Instagram handoff workflow."""
from __future__ import annotations

import logging
from pathlib import Path
import webbrowser

from explorer import open_selected_files

INSTAGRAM_URL = "https://www.instagram.com/"


def open_instagram(logger: logging.Logger) -> None:
    """Open Instagram homepage in the system default browser."""
    logger.info("Opening Instagram homepage")
    if not webbrowser.open(INSTAGRAM_URL):
        logger.warning("webbrowser.open returned False for %s", INSTAGRAM_URL)


def prompt_user_for_post_completion(images: list[Path]) -> None:
    """Print the manual posting instructions and wait for confirmation."""
    filenames = [image.name for image in images]
    print(
        "\n==================================================\n\n"
        "READY\n\n"
        "Caption has been copied to clipboard.\n\n"
        "Instagram has been opened.\n\n"
        "Selected images:\n"
    )
    for filename in filenames:
        print(filename)
    print(
        "\nNext Steps\n\n"
        "1. Drag the selected files into Instagram.\n\n"
        "2. Click Next.\n\n"
        "3. Edit if desired.\n\n"
        "4. Paste the caption.\n\n"
        "5. Share.\n\n"
        "Press ENTER here after the post has been successfully shared.\n\n"
        "=================================================="
    )
    input()


def handoff_to_user(images: list[Path], logger: logging.Logger) -> None:
    """Open Instagram and Explorer, then wait for the user to publish manually."""
    open_instagram(logger)
    logger.info("Instagram opened")
    open_selected_files(images, logger)
    logger.info("Explorer opened")
    logger.info("Waiting for user...")
    prompt_user_for_post_completion(images)
    logger.info("User confirmed")
