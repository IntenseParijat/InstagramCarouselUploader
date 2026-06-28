"""GitHub REST API client for uploading original images."""
from __future__ import annotations

import base64
import logging
from pathlib import Path
from time import sleep
from urllib.parse import quote

import requests

from config import GitHubConfig


class GitHubApiError(RuntimeError):
    """Raised when GitHub cannot complete an upload."""


class GitHubClient:
    """Small GitHub Contents API wrapper with retries and verification."""

    def __init__(self, config: GitHubConfig, retry_count: int, logger: logging.Logger) -> None:
        self.config = config
        self.retry_count = retry_count
        self.logger = logger
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {config.token}",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )

    def validate_ready(self) -> None:
        """Ensure credentials and repository identifiers are configured."""
        missing = [
            name
            for name, value in {
                "github.token": self.config.token,
                "github.owner": self.config.owner,
                "github.repo": self.config.repo,
            }.items()
            if not value
        ]
        if missing:
            raise GitHubApiError(f"Missing required GitHub config: {', '.join(missing)}")

    def upload_file(self, path: Path, verify: bool = True) -> str:
        """Create or update a file and return its raw.githubusercontent.com URL."""
        self.validate_ready()
        remote_path = f"{self.config.upload_folder}/{path.name}" if self.config.upload_folder else path.name
        api_url = self._contents_url(remote_path)
        raw_url = self.raw_url(remote_path)
        content = base64.b64encode(path.read_bytes()).decode("ascii")
        sha = self._get_existing_sha(api_url)
        payload = {
            "message": f"Upload {path.name}",
            "content": content,
            "branch": self.config.branch,
        }
        if sha:
            payload["sha"] = sha

        response = self._request_with_retries("PUT", api_url, json=payload)
        self.logger.info("GitHub upload response for %s: %s", path.name, response.status_code)
        if response.status_code not in {200, 201}:
            raise GitHubApiError(f"GitHub upload failed for {path.name}: {response.status_code} {response.text}")
        if verify:
            self.verify_raw_url(raw_url)
        return raw_url

    def raw_url(self, remote_path: str) -> str:
        """Build a raw GitHub URL for a repository path."""
        quoted_parts = "/".join(quote(part) for part in remote_path.split("/"))
        return (
            f"https://raw.githubusercontent.com/{self.config.owner}/{self.config.repo}/"
            f"{self.config.branch}/{quoted_parts}"
        )

    def verify_raw_url(self, raw_url: str) -> None:
        """Ensure the raw URL is reachable before adding it to a caption."""
        response = self._request_with_retries("GET", raw_url)
        if response.status_code != 200:
            raise GitHubApiError(f"Raw URL verification failed: {response.status_code} {raw_url}")

    def _contents_url(self, remote_path: str) -> str:
        quoted_path = "/".join(quote(part) for part in remote_path.split("/"))
        return f"https://api.github.com/repos/{self.config.owner}/{self.config.repo}/contents/{quoted_path}"

    def _get_existing_sha(self, api_url: str) -> str | None:
        response = self._request_with_retries("GET", api_url, params={"ref": self.config.branch})
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            raise GitHubApiError(f"Could not inspect existing GitHub file: {response.status_code} {response.text}")
        data = response.json()
        sha = data.get("sha")
        return str(sha) if sha else None

    def _request_with_retries(self, method: str, url: str, **kwargs: object) -> requests.Response:
        last_response: requests.Response | None = None
        for attempt in range(1, self.retry_count + 1):
            try:
                response = self.session.request(method, url, timeout=30, **kwargs)
                last_response = response
                self.logger.debug("GitHub/API %s %s -> %s", method, url, response.status_code)
                if response.status_code not in {403, 429, 500, 502, 503, 504}:
                    return response
            except requests.RequestException as exc:
                self.logger.exception("Network error on attempt %s for %s %s", attempt, method, url)
                if attempt == self.retry_count:
                    raise GitHubApiError(str(exc)) from exc
            sleep(min(2**attempt, 10))
        if last_response is None:
            raise GitHubApiError(f"Request failed without response: {method} {url}")
        return last_response
