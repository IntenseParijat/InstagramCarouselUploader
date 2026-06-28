"""Playwright browser connection and dedicated-profile launch management."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

from playwright.sync_api import Browser, BrowserContext, Page

from config import BrowserConfig, BrowserMode, ConfigError
from utils import resolve_chrome_user_data

INSTAGRAM_HOST = "instagram.com"


@dataclass
class ManagedPage:
    """A page returned by BrowserManager and whether this app created it."""

    page: Page
    created_by_app: bool


class BrowserManager:
    """Create or reuse browser contexts without touching user-owned tabs."""

    def __init__(self, config: BrowserConfig, logger: logging.Logger) -> None:
        self.config = config
        self.logger = logger
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    def context(self, playwright: Any) -> BrowserContext:
        """Return a BrowserContext for the configured browser mode."""
        self.logger.info("Browser mode selected: %s", self.config.mode.value)
        if self.config.mode == BrowserMode.CDP:
            return self._connect_cdp(playwright)
        if self.config.mode == BrowserMode.PERSISTENT:
            return self._launch_persistent(playwright)
        raise ConfigError("ATTACH mode does not use Playwright. Use InstagramUploader.upload_outputs() for ATTACH handoff.")

    def instagram_page(self, context: BrowserContext) -> ManagedPage:
        """Reuse an existing Instagram tab or create a new application-owned page."""
        for page in context.pages:
            if INSTAGRAM_HOST in page.url.lower():
                self.logger.info("Existing Instagram tab reused: %s", page.url)
                return ManagedPage(page=page, created_by_app=False)
        self.logger.info("New Instagram tab created")
        return ManagedPage(page=context.new_page(), created_by_app=True)

    def cleanup_page(self, managed_page: ManagedPage) -> None:
        """Close only pages created by this application."""
        if managed_page.created_by_app and not managed_page.page.is_closed():
            self.logger.info("Closing application-created Instagram tab")
            managed_page.page.close()
        else:
            self.logger.info("Leaving user-owned browser tab open")

    def _connect_cdp(self, playwright: Any) -> BrowserContext:
        endpoint = self._cdp_endpoint()
        version_url = f"{endpoint}/json/version"
        try:
            with urlopen(version_url, timeout=2) as response:  # noqa: S310 - local Chrome CDP endpoint only.
                if response.status != 200:
                    raise ConfigError(f"Chrome remote debugging returned HTTP {response.status} at {version_url}")
        except (URLError, TimeoutError, OSError) as exc:
            raise ConfigError(
                "Chrome isn't running with remote debugging.\n\n"
                "Run:\n\n"
                "chrome.exe\n"
                f"--remote-debugging-port={self.config.remote_debugging_port}\n\n"
                "or switch browser.mode to ATTACH."
            ) from exc
        return self._connect_to_endpoint(playwright, endpoint)

    def _connect_to_endpoint(self, playwright: Any, endpoint: str) -> BrowserContext:
        self.logger.info("Connecting to Chrome over CDP: %s", endpoint)
        self._browser = playwright.chromium.connect_over_cdp(endpoint)
        if not self._browser.contexts:
            raise ConfigError("Connected to Chrome over CDP but no browser context was available")
        self._context = self._browser.contexts[0]
        self.logger.info("Browser reuse active via CDP context")
        return self._context

    def _launch_persistent(self, playwright: Any) -> BrowserContext:
        profile = self.config.automation_profile.expanduser()
        self._validate_automation_profile(profile)
        profile.mkdir(parents=True, exist_ok=True)
        self.logger.info("Launching dedicated Playwright persistent profile at %s", profile)
        self._context = playwright.chromium.launch_persistent_context(user_data_dir=str(profile), headless=False)
        return self._context

    def _validate_automation_profile(self, profile: Path) -> None:
        resolved = profile.expanduser().resolve()
        user_data = resolve_chrome_user_data(self.config.user_data_dir).expanduser()
        unsafe = {"default", "profile 1", "profile 2", "user data"}
        if resolved.name.lower() in unsafe:
            raise ConfigError(
                "Persistent mode requires a dedicated automation profile, not a daily Chrome profile such as "
                "Default or Google Chrome\\User Data. Use a separate path like C:\\InstagramAutomationProfile."
            )
        try:
            if resolved == user_data.resolve() or user_data.resolve() in resolved.parents:
                raise ConfigError(
                    "Persistent mode cannot use a profile inside your daily Chrome user-data directory. "
                    "Use a dedicated automation profile such as C:\\InstagramAutomationProfile."
                )
        except FileNotFoundError:
            pass

    def _cdp_endpoint(self) -> str:
        return f"http://127.0.0.1:{self.config.remote_debugging_port}"
