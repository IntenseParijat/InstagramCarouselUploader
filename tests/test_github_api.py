from __future__ import annotations

import logging
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch

from config import GitHubConfig, VerificationConfig
from github_api import GitHubClient, UploadedFile
from main import verify_uploaded_files
from rich.console import Console


class GitHubRawVerificationTests(unittest.TestCase):
    def make_client(self) -> GitHubClient:
        return GitHubClient(
            GitHubConfig(token="token", owner="owner", repo="repo", branch="main", upload_folder="screenshots"),
            retry_count=1,
            logger=logging.getLogger("test"),
        )

    def make_verification(self) -> VerificationConfig:
        return VerificationConfig(
            enabled=True,
            max_attempts=3,
            initial_delay=0,
            backoff=1.7,
            timeout_seconds=10,
            continue_on_timeout=True,
        )

    @patch("github_api.sleep", return_value=None)
    def test_404_retries_until_raw_url_is_available(self, _sleep: Mock) -> None:
        client = self.make_client()
        responses = [Mock(status_code=404, headers={}), Mock(status_code=404, headers={}), Mock(status_code=200, headers={})]
        client.session.get = Mock(side_effect=responses)  # type: ignore[method-assign]

        self.assertTrue(client.verify_raw_url_with_retry("https://raw.example/file.png", self.make_verification()))
        self.assertEqual(client.session.get.call_count, 3)

    @patch("github_api.sleep", return_value=None)
    def test_404_attempt_exhaustion_continues_without_raising(self, _sleep: Mock) -> None:
        client = self.make_client()
        client.session.get = Mock(return_value=Mock(status_code=404, headers={}))  # type: ignore[method-assign]

        self.assertFalse(client.verify_raw_url_with_retry("https://raw.example/file.png", self.make_verification()))
        self.assertEqual(client.session.get.call_count, 3)

    def test_batch_verification_runs_after_upload_collection(self) -> None:
        github = Mock()
        args = Mock(skip_github=False, dry_run=False)
        config = Mock(verification=self.make_verification())
        files = [
            UploadedFile(Path("a.png"), "screenshots/a.png", "https://raw.example/a.png", True),
            UploadedFile(Path("b.png"), "screenshots/b.png", "https://raw.example/b.png", True),
        ]

        console = Console(file=StringIO(), force_terminal=False)
        verify_uploaded_files(files, config, github, args, console)

        self.assertEqual(github.verify_raw_url_with_retry.call_count, 2)
        github.verify_raw_url_with_retry.assert_any_call("https://raw.example/a.png", config.verification)
        github.verify_raw_url_with_retry.assert_any_call("https://raw.example/b.png", config.verification)


if __name__ == "__main__":
    unittest.main()
