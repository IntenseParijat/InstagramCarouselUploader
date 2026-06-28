"""GitHub REST API client for uploading original images."""
from __future__ import annotations

import base64
from dataclasses import dataclass
import logging
from pathlib import Path
from time import monotonic, sleep
from urllib.parse import quote

import requests

from config import GitHubConfig, VerificationConfig


class GitHubApiError(RuntimeError):
    """Raised when GitHub cannot complete an upload."""


@dataclass(frozen=True)
class UploadedFile:
    """Result of uploading or planning one original image."""

    local_path: Path
    github_path: str
    raw_url: str
    uploaded: bool


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

    def upload_file(self, path: Path) -> UploadedFile:
        """Create or update a file and return upload metadata without RAW CDN verification."""
        self.validate_ready()

        remote_path = self.github_path(path)
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

        response = self._request_with_retries(
            "PUT",
            api_url,
            json=payload,
        )

        self.logger.info(
            "GitHub upload response for %s: %s",
            path.name,
            response.status_code,
        )

        if response.status_code not in (200, 201):
            raise GitHubApiError(
                f"GitHub upload failed for {path.name}: "
                f"{response.status_code} {response.text}"
            )

        data = response.json()

        content_info = data.get("content", {})

        returned_path = str(content_info.get("path", ""))

        returned_sha = str(content_info.get("sha", ""))

        if returned_path.strip("/") != remote_path.strip("/"):
            raise GitHubApiError(
                f"GitHub returned unexpected path "
                f"'{returned_path}' "
                f"(expected '{remote_path}')"
            )

        self.logger.info(
            "Upload confirmed. SHA=%s",
            returned_sha,
        )

        return UploadedFile(
            local_path=path,
            github_path=remote_path,
            raw_url=raw_url,
            uploaded=True,
        )

    def github_path(self, path: Path) -> str:
        """Build the repository path for a local file."""
        return f"{self.config.upload_folder}/{path.name}" if self.config.upload_folder else path.name

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

    def verify_raw_url_with_retry(self, raw_url: str, verification: VerificationConfig) -> bool:
        """Wait for GitHub's eventually consistent RAW CDN to serve an uploaded file."""
        deadline = monotonic() + verification.timeout_seconds
        delay = verification.initial_delay
        self.logger.info("Waiting for GitHub RAW CDN: %s", raw_url)
        last_status: int | None = None
        for attempt in range(1, verification.max_attempts + 1):
            if monotonic() >= deadline:
                return self._handle_raw_timeout(raw_url, last_status)
            try:
                response = self.session.get(raw_url, timeout=min(30, max(1, verification.timeout_seconds)))
            except requests.RequestException as exc:
                self.logger.info("Attempt %s/%s RAW CDN request failed: %s", attempt, verification.max_attempts, exc)
                self._sleep_before_next_attempt(delay, deadline)
                delay *= verification.backoff
                continue
            last_status = response.status_code
            self.logger.info("Attempt %s/%s RAW CDN status: %s", attempt, verification.max_attempts, response.status_code)
            if response.status_code == 200:
                self.logger.info("Verified after %s attempts: %s", attempt, raw_url)
                return True
            if response.status_code == 404:
                self.logger.info("GitHub RAW CDN has not propagated yet: %s", raw_url)
                self._sleep_before_next_attempt(delay, deadline)
                delay *= verification.backoff
                continue
            if response.status_code == 429:
                retry_after = self._retry_after_seconds(response)
                self.logger.info("RAW CDN rate limited; retrying after %.1f seconds", retry_after)
                self._sleep_before_next_attempt(retry_after, deadline)
                continue
            if 500 <= response.status_code <= 599:
                self.logger.info("RAW CDN server error; retrying: %s", response.status_code)
                self._sleep_before_next_attempt(delay, deadline)
                delay *= verification.backoff
                continue
            raise GitHubApiError(f"Raw URL verification failed: {response.status_code} {raw_url}")
        return self._handle_raw_timeout(raw_url, last_status)

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

    def _handle_raw_timeout(self, raw_url: str, last_status: int | None) -> bool:
        self.logger.warning(
            "RAW CDN propagation timed out. GitHub upload confirmed. RAW CDN not yet propagated. Continuing. "
            "Last status for %s: %s",
            raw_url,
            last_status,
        )
        return False

    def _retry_after_seconds(self, response: requests.Response) -> float:
        value = response.headers.get("Retry-After")
        if not value:
            return 1.0
        try:
            return max(0.0, float(value))
        except ValueError:
            return 1.0

    def _sleep_before_next_attempt(self, delay: float, deadline: float) -> None:
        remaining = deadline - monotonic()
        if remaining <= 0:
            return
        sleep(min(delay, remaining))
