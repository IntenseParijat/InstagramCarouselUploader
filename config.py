"""Configuration loading and validation."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


class ConfigError(ValueError):
    """Raised when configuration is missing or invalid."""


class BrowserMode(str, Enum):
    """Supported browser launch/connect modes."""

    ATTACH = "attach"
    CDP = "cdp"
    PERSISTENT = "persistent"


@dataclass(frozen=True)
class GitHubConfig:
    token: str
    owner: str
    repo: str
    branch: str
    upload_folder: str


@dataclass(frozen=True)
class PathsConfig:
    images: Path


@dataclass(frozen=True)
class BrowserConfig:
    mode: BrowserMode
    chrome_path: str
    remote_debugging_port: int
    launch_if_needed: bool
    user_data_dir: str
    profile_directory: str
    automation_profile: Path


@dataclass(frozen=True)
class CaptionConfig:
    text: str
    download_header: str
    hashtags: list[str]


@dataclass(frozen=True)
class ProcessingConfig:
    skip_processed: bool
    overwrite_github: bool
    verify_upload: bool
    retry_count: int


@dataclass(frozen=True)
class AppConfig:
    github: GitHubConfig
    paths: PathsConfig
    browser: BrowserConfig
    caption: CaptionConfig
    processing: ProcessingConfig


# Backward-compatible alias for older imports while the browser subsystem owns the
# new configuration shape.
InstagramConfig = BrowserConfig


def _require_mapping(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise ConfigError(f"Missing or invalid '{key}' section in config.json")
    return value


def _env_or_value(value: str, env_name: str) -> str:
    return os.getenv(env_name, value or "")


def _browser_mode(value: Any) -> BrowserMode:
    try:
        return BrowserMode(str(value or BrowserMode.ATTACH.value).lower())
    except ValueError as exc:
        allowed = ", ".join(mode.value for mode in BrowserMode)
        raise ConfigError(f"browser.mode must be one of: {allowed}") from exc


def load_config(path: str | Path = "config.json") -> AppConfig:
    """Load and validate application configuration from JSON and .env."""
    load_dotenv()
    config_path = Path(path)
    if not config_path.exists():
        raise ConfigError(f"Config file not found: {config_path}")

    data = json.loads(config_path.read_text(encoding="utf-8"))
    github = _require_mapping(data, "github")
    paths = _require_mapping(data, "paths")
    browser = _require_mapping(data, "browser")
    caption = _require_mapping(data, "caption")
    processing = _require_mapping(data, "processing")

    app_config = AppConfig(
        github=GitHubConfig(
            token=_env_or_value(str(github.get("token", "")), "GITHUB_TOKEN"),
            owner=_env_or_value(str(github.get("owner", "")), "GITHUB_OWNER"),
            repo=_env_or_value(str(github.get("repo", "")), "GITHUB_REPO"),
            branch=str(github.get("branch", "main")),
            upload_folder=str(github.get("upload_folder", "screenshots")).strip("/"),
        ),
        paths=PathsConfig(images=Path(str(paths.get("images", ""))).expanduser()),
        browser=BrowserConfig(
            mode=_browser_mode(browser.get("mode", BrowserMode.ATTACH.value)),
            chrome_path=str(browser.get("chrome_path", "")),
            remote_debugging_port=int(browser.get("remote_debugging_port", 9222)),
            launch_if_needed=bool(browser.get("launch_if_needed", False)),
            user_data_dir=str(browser.get("user_data_dir", "")),
            profile_directory=str(browser.get("profile_directory", "Default")),
            automation_profile=Path(str(browser.get("automation_profile", "./playwright_profile"))).expanduser(),
        ),
        caption=CaptionConfig(
            text=str(caption.get("text", "")),
            download_header=str(caption.get("download_header", "Download original for wallpaper:")),
            hashtags=[str(tag) for tag in caption.get("hashtags", [])],
        ),
        processing=ProcessingConfig(
            skip_processed=bool(processing.get("skip_processed", True)),
            overwrite_github=bool(processing.get("overwrite_github", True)),
            verify_upload=bool(processing.get("verify_upload", True)),
            retry_count=max(1, int(processing.get("retry_count", 3))),
        ),
    )
    validate_config(app_config)
    return app_config


def validate_config(config: AppConfig) -> None:
    """Validate values that are required before the workflow starts."""
    if not config.paths.images or str(config.paths.images) == ".":
        raise ConfigError("paths.images must point to a folder containing images")
    if not config.paths.images.exists() or not config.paths.images.is_dir():
        raise ConfigError(f"Image folder does not exist: {config.paths.images}")
    if not config.caption.download_header:
        raise ConfigError("caption.download_header cannot be empty")
    if config.browser.remote_debugging_port <= 0:
        raise ConfigError("browser.remote_debugging_port must be a positive integer")
