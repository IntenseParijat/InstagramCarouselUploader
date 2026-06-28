"""Configuration loading and validation."""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


class ConfigError(ValueError):
    """Raised when configuration is missing or invalid."""


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
class VerificationConfig:
    enabled: bool
    max_attempts: int
    initial_delay: float
    backoff: float
    timeout_seconds: float
    continue_on_timeout: bool


@dataclass(frozen=True)
class AppConfig:
    github: GitHubConfig
    paths: PathsConfig
    caption: CaptionConfig
    processing: ProcessingConfig
    verification: VerificationConfig


def _require_mapping(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise ConfigError(f"Missing or invalid '{key}' section in config.json")
    return value


def _env_or_value(value: str, env_name: str) -> str:
    return os.getenv(env_name, value or "")


def load_config(path: str | Path = "config.json") -> AppConfig:
    """Load and validate application configuration from JSON and .env."""
    load_dotenv()
    config_path = Path(path)
    if not config_path.exists():
        raise ConfigError(f"Config file not found: {config_path}")

    data = json.loads(config_path.read_text(encoding="utf-8"))
    github = _require_mapping(data, "github")
    paths = _require_mapping(data, "paths")
    caption = _require_mapping(data, "caption")
    processing = _require_mapping(data, "processing")
    verification = data.get("verification", {})
    if not isinstance(verification, dict):
        raise ConfigError("Invalid 'verification' section in config.json")

    app_config = AppConfig(
        github=GitHubConfig(
            token=_env_or_value(str(github.get("token", "")), "GITHUB_TOKEN"),
            owner=_env_or_value(str(github.get("owner", "")), "GITHUB_OWNER"),
            repo=_env_or_value(str(github.get("repo", "")), "GITHUB_REPO"),
            branch=str(github.get("branch", "main")),
            upload_folder=str(github.get("upload_folder", "screenshots")).strip("/"),
        ),
        paths=PathsConfig(images=Path(str(paths.get("images", ""))).expanduser()),
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
        verification=VerificationConfig(
            enabled=bool(verification.get("enabled", processing.get("verify_upload", True))),
            max_attempts=max(1, int(verification.get("max_attempts", 12))),
            initial_delay=max(0.0, float(verification.get("initial_delay", 0.5))),
            backoff=max(1.0, float(verification.get("backoff", 1.7))),
            timeout_seconds=max(1.0, float(verification.get("timeout_seconds", 45))),
            continue_on_timeout=bool(verification.get("continue_on_timeout", True)),
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
