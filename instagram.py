"""Instagram handoff and browser automation that stops before publishing."""
from __future__ import annotations

import logging
import os
from pathlib import Path
import subprocess
import sys
from typing import TYPE_CHECKING
import webbrowser

if TYPE_CHECKING:
    from playwright.sync_api import Page

from config import BrowserConfig, BrowserMode

CREATE_URL = "https://www.instagram.com/create/select/"


class InstagramAutomationError(RuntimeError):
    """Raised when Instagram automation cannot reach the review step."""


class InstagramUploader:
    """Prepares Instagram carousel uploads using the configured browser mode."""

    def __init__(self, config: BrowserConfig, logger: logging.Logger) -> None:
        self.config = config
        self.logger = logger

    def upload_outputs(self, images: list[Path]) -> None:
        """Open Instagram Create Post and hand off or automate output image upload."""
        if not images:
            raise InstagramAutomationError("No output images were provided")
        if self.config.mode == BrowserMode.ATTACH:
            self._handoff_attach(images)
            return
        self._upload_with_playwright(images)

    def _handoff_attach(self, images: list[Path]) -> None:
        """Use the user's default browser and Explorer/Finder instead of automation."""
        self.logger.info("Opening Instagram create page in the default browser")
        if not webbrowser.open(CREATE_URL):
            self.logger.warning("webbrowser.open returned False for %s", CREATE_URL)
        self._open_output_folder(images)
        filenames = [image.name for image in images]
        print("\nCaption copied.\n")
        print("Instagram opened.\n")
        print("Output images:\n")
        for filename in filenames:
            print(filename)
        print("\nDrag these images into Instagram.\n")
        input("Press ENTER here when you're ready.")

    def _open_output_folder(self, images: list[Path]) -> None:
        """Open the containing folder and select the first output file when supported."""
        folder = images[0].resolve().parent
        self.logger.info("Opening output folder for manual drag-and-drop: %s", folder)
        try:
            if os.name == "nt":
                first_image = images[0].resolve()
                subprocess.Popen(["explorer", f"/select,{first_image}"])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(folder)])
            else:
                subprocess.Popen(["xdg-open", str(folder)])
        except OSError as exc:
            self.logger.warning("Could not open output folder %s: %s", folder, exc)
            print(f"\nOpen this folder manually: {folder}")

    def _upload_with_playwright(self, images: list[Path]) -> None:
        """Open Instagram Create Post, upload images, advance to caption page, and stop."""
        try:
            from browser_manager import BrowserManager
            from playwright.sync_api import sync_playwright

            with sync_playwright() as playwright:
                browser_manager = BrowserManager(self.config, self.logger)
                context = browser_manager.context(playwright)
                managed_page = browser_manager.instagram_page(context)
                page = managed_page.page
                try:
                    page.goto(CREATE_URL, wait_until="domcontentloaded", timeout=60_000)
                    self.logger.info("Opened Instagram create page")
                    self._set_files(page, images)
                    self._advance_until_ready(page)
                    self.logger.info("Instagram upload is ready for manual caption paste and Share")
                    print(
                        "\nReady!\n\n"
                        "Caption copied to clipboard.\n\n"
                        "Press CTRL+V inside Instagram.\n\n"
                        "Click Share manually."
                    )
                    page.wait_for_timeout(2_000)
                finally:
                    browser_manager.cleanup_page(managed_page)
        except Exception as exc:  # noqa: BLE001 - convert Playwright failures to app errors.
            self.logger.exception("Playwright/Instagram automation failed")
            raise InstagramAutomationError(str(exc)) from exc

    def _set_files(self, page: "Page", images: list[Path]) -> None:
        file_paths = [str(image.resolve()) for image in images]
        with page.expect_file_chooser(timeout=60_000) as chooser_info:
            page.get_by_text("Select from computer", exact=False).click(timeout=60_000)
        chooser_info.value.set_files(file_paths)
        self.logger.info("Selected %s Instagram output images", len(images))

    def _advance_until_ready(self, page: "Page") -> None:
        for step in range(2):
            button = page.get_by_role("button", name="Next")
            button.wait_for(state="visible", timeout=120_000)
            button.click(timeout=30_000)
            self.logger.info("Clicked Instagram Next button (%s/2)", step + 1)
        page.get_by_text("Write a caption", exact=False).wait_for(state="visible", timeout=120_000)
