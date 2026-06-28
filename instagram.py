"""Instagram browser automation that stops before publishing."""
from __future__ import annotations

import logging
from pathlib import Path

from playwright.sync_api import BrowserContext, Error as PlaywrightError, Page, sync_playwright

from config import InstagramConfig
from utils import resolve_chrome_user_data

CREATE_URL = "https://www.instagram.com/create/select/"


class InstagramAutomationError(RuntimeError):
    """Raised when Instagram automation cannot reach the review step."""


class InstagramUploader:
    """Automates selecting carousel files in Instagram without clicking Share."""

    def __init__(self, config: InstagramConfig, logger: logging.Logger) -> None:
        self.config = config
        self.logger = logger

    def upload_outputs(self, images: list[Path]) -> None:
        """Open Instagram Create Post, upload images, advance to caption page, and stop."""
        if not images:
            raise InstagramAutomationError("No output images were provided")
        try:
            with sync_playwright() as playwright:
                context = self._launch_context(playwright)
                page = context.new_page()
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
        except PlaywrightError as exc:
            self.logger.exception("Playwright/Instagram automation failed")
            raise InstagramAutomationError(str(exc)) from exc

    def _launch_context(self, playwright: object) -> BrowserContext:
        chromium = playwright.chromium  # type: ignore[attr-defined]
        if self.config.use_existing_chrome:
            user_data = resolve_chrome_user_data(self.config.chrome_user_data)
            if not user_data.exists():
                raise InstagramAutomationError(f"Chrome user-data directory does not exist: {user_data}")
            args = [f"--profile-directory={self.config.chrome_profile}"] if self.config.chrome_profile else []
            self.logger.info("Launching Chrome profile at %s (%s)", user_data, self.config.chrome_profile)
            return chromium.launch_persistent_context(
                user_data_dir=str(user_data),
                channel="chrome",
                headless=False,
                args=args,
            )
        profile = self.config.playwright_profile
        profile.mkdir(parents=True, exist_ok=True)
        self.logger.info("Launching Playwright persistent profile at %s", profile)
        return chromium.launch_persistent_context(user_data_dir=str(profile), headless=False)

    def _set_files(self, page: Page, images: list[Path]) -> None:
        file_paths = [str(image.resolve()) for image in images]
        with page.expect_file_chooser(timeout=60_000) as chooser_info:
            page.get_by_text("Select from computer", exact=False).click(timeout=60_000)
        chooser_info.value.set_files(file_paths)
        self.logger.info("Selected %s Instagram output images", len(images))

    def _advance_until_ready(self, page: Page) -> None:
        for step in range(2):
            button = page.get_by_role("button", name="Next")
            button.wait_for(state="visible", timeout=120_000)
            button.click(timeout=30_000)
            self.logger.info("Clicked Instagram Next button (%s/2)", step + 1)
        page.get_by_text("Write a caption", exact=False).wait_for(state="visible", timeout=120_000)
