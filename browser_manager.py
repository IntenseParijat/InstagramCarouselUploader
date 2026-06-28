"""Playwright browser connection and launch management."""
from __future__ import annotations

from dataclasses import dataclass
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
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
        self._launched_process: subprocess.Popen[bytes] | None = None

    def context(self, playwright: Any) -> BrowserContext:
        """Return a BrowserContext for the configured browser mode."""
        self.logger.info("Browser mode selected: %s", self.config.mode.value)
        if self.config.mode == BrowserMode.CDP:
            return self._connect_cdp(playwright)
        if self.config.mode == BrowserMode.PERSISTENT:
            return self._launch_persistent(playwright)
        return self._launch_ephemeral(playwright)

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
        try:
            return self._connect_to_endpoint(playwright, endpoint)
        except Exception as exc:  # noqa: BLE001 - convert Playwright/network errors to config guidance.
            self.logger.warning("CDP connection failed at %s: %s", endpoint, exc)
            if not self._should_launch_chrome():
                raise ConfigError(
                    "Chrome is not running with remote debugging. Start Chrome with "
                    f"--remote-debugging-port={self.config.remote_debugging_port} or enable browser.launch_if_needed."
                ) from exc
            chrome_path = self._find_chrome()
            user_data_dir = resolve_chrome_user_data(self.config.user_data_dir)
            self._launch_chrome(chrome_path, user_data_dir)
            self._wait_for_cdp()
            return self._connect_to_endpoint(playwright, endpoint)

    def _connect_to_endpoint(self, playwright: Any, endpoint: str) -> BrowserContext:
        self.logger.info("Connecting to Chrome over CDP: %s", endpoint)
        self._browser = playwright.chromium.connect_over_cdp(endpoint)
        if not self._browser.contexts:
            raise ConfigError("Connected to Chrome over CDP but no browser context was available")
        self._context = self._browser.contexts[0]
        self.logger.info("Browser reuse active via CDP context")
        return self._context

    def _should_launch_chrome(self) -> bool:
        message = "Chrome is not running with remote debugging.\n\nStart it automatically?\n\n[Y/n] "
        if self.config.launch_if_needed:
            print(f"{message}Y")
            return True
        if not sys.stdin.isatty():
            print(f"{message}n")
            return False
        answer = input(message).strip().lower()
        return answer in {"", "y", "yes"}

    def _launch_chrome(self, chrome_path: Path, user_data_dir: Path) -> None:
        args = [
            str(chrome_path),
            f"--remote-debugging-port={self.config.remote_debugging_port}",
            f"--user-data-dir={user_data_dir}",
        ]
        if self.config.profile_directory:
            args.append(f"--profile-directory={self.config.profile_directory}")
        self.logger.info("Launching Chrome for CDP: %s", " ".join(args))
        self._launched_process = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _wait_for_cdp(self, timeout_seconds: int = 30) -> None:
        version_url = f"{self._cdp_endpoint()}/json/version"
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            try:
                with urlopen(version_url, timeout=2) as response:  # noqa: S310 - local Chrome CDP endpoint only.
                    if response.status == 200:
                        self.logger.info("CDP endpoint is available: %s", version_url)
                        return
            except URLError:
                time.sleep(0.5)
        raise ConfigError(f"Timed out waiting for Chrome remote debugging at {version_url}")

    def _launch_persistent(self, playwright: Any) -> BrowserContext:
        profile = self.config.automation_profile.expanduser()
        self._validate_automation_profile(profile)
        profile.mkdir(parents=True, exist_ok=True)
        self.logger.info("Launching dedicated Playwright persistent profile at %s", profile)
        self._context = playwright.chromium.launch_persistent_context(user_data_dir=str(profile), headless=False)
        return self._context

    def _launch_ephemeral(self, playwright: Any) -> BrowserContext:
        self.logger.info("Launching temporary Chromium for testing")
        self._browser = playwright.chromium.launch(headless=False)
        self._context = self._browser.new_context()
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

    def _find_chrome(self) -> Path:
        configured = Path(self.config.chrome_path).expanduser() if self.config.chrome_path else None
        if configured and configured.exists():
            return configured
        names = ["chrome", "google-chrome", "google-chrome-stable", "chromium", "chromium-browser"]
        for name in names:
            found = shutil.which(name)
            if found:
                return Path(found)
        registry_path = self._find_chrome_in_registry()
        if registry_path:
            return registry_path
        candidates = [
            Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / "Google/Chrome/Application/chrome.exe",
            Path.home() / "AppData/Local/Google/Chrome/Application/chrome.exe",
            Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        raise ConfigError("Could not automatically locate Chrome. Set browser.chrome_path in config.json.")

    def _find_chrome_in_registry(self) -> Path | None:
        if os.name != "nt":
            return None
        import winreg

        keys = [
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"),
            (
                winreg.HKEY_LOCAL_MACHINE,
                r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe",
            ),
        ]
        for root, key_path in keys:
            try:
                with winreg.OpenKey(root, key_path) as key:
                    value, _ = winreg.QueryValueEx(key, None)
            except OSError:
                continue
            candidate = Path(value)
            if candidate.exists():
                return candidate
        return None

    def _cdp_endpoint(self) -> str:
        return f"http://127.0.0.1:{self.config.remote_debugging_port}"
