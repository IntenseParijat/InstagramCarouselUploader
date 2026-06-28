"""Command-line entry point for GitHub to Instagram carousel preparation."""
from __future__ import annotations

import argparse
import logging
from pathlib import Path
import sys

from rich.console import Console
from rich.progress import track

from clipboard import copy_caption
from config import AppConfig, ConfigError, load_config
from github_api import GitHubClient
from grouping import split_balanced
from instagram import InstagramUploader
from logging_utils import configure_logging
from pairing import ImagePair, scan_image_pairs
from state import ProcessedState
from utils import build_caption



def parse_args() -> argparse.Namespace:
    """Parse command-line flags."""
    parser = argparse.ArgumentParser(description="Prepare Instagram carousel posts from paired screenshots.")
    parser.add_argument("--config", default="config.json", help="Path to config.json")
    parser.add_argument("--dry-run", action="store_true", help="Plan work without uploading or opening Instagram")
    parser.add_argument("--resume", action="store_true", help="Use processed.json to skip completed originals")
    parser.add_argument("--force", action="store_true", help="Ignore processed.json and repost all matched pairs")
    parser.add_argument("--skip-github", action="store_true", help="Do not upload originals; generate raw URLs only")
    parser.add_argument("--skip-instagram", action="store_true", help="Do not launch Instagram")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose console logging")
    return parser.parse_args()


def filter_processed(
    pairs: list[ImagePair],
    state: ProcessedState,
    config: AppConfig,
    args: argparse.Namespace,
    logger: logging.Logger,
) -> list[ImagePair]:
    """Apply processed.json skipping rules."""
    if args.force or not (args.resume or config.processing.skip_processed):
        return pairs
    filtered: list[ImagePair] = []
    for pair in pairs:
        if state.contains(pair.original.name):
            logger.info("Skipping already processed original: %s", pair.original.name)
            continue
        filtered.append(pair)
    return filtered


def upload_or_build_urls(
    group: list[ImagePair],
    config: AppConfig,
    github: GitHubClient,
    args: argparse.Namespace,
    console: Console,
) -> list[str]:
    """Upload originals or build deterministic raw URLs when GitHub is skipped."""
    urls: list[str] = []
    for pair in track(group, description="Uploading originals", console=console):
        remote_path = f"{config.github.upload_folder}/{pair.original.name}" if config.github.upload_folder else pair.original.name
        if args.skip_github or args.dry_run:
            urls.append(github.raw_url(remote_path))
        else:
            urls.append(github.upload_file(pair.original, verify=config.processing.verify_upload))
    return urls


def process_group(
    index: int,
    group: list[ImagePair],
    config: AppConfig,
    state: ProcessedState,
    args: argparse.Namespace,
    logger: logging.Logger,
    console: Console,
) -> None:
    """Process one Instagram carousel group."""
    console.rule(f"[bold cyan]Carousel {index}: {len(group)} images")
    github = GitHubClient(config.github, config.processing.retry_count, logger)
    raw_urls = upload_or_build_urls(group, config, github, args, console)
    caption = build_caption(config.caption, raw_urls)
    if args.dry_run:
        console.print("[yellow]Dry run caption:[/yellow]\n" + caption)
        return
    copy_caption(caption, logger)
    if not args.skip_instagram:
        InstagramUploader(config.browser, logger).upload_outputs([pair.output for pair in group])
    for pair in group:
        state.add(pair.original.name)


def run() -> int:
    """Run the application and return a process exit code."""
    args = parse_args()
    logger = configure_logging(args.verbose)
    console = Console()
    state = ProcessedState(Path("processed.json"))
    try:
        config = load_config(args.config)
        state.load(logger)
        pairs = scan_image_pairs(config.paths.images, logger)
        pairs = filter_processed(pairs, state, config, args, logger)
        if not pairs:
            console.print("[yellow]No matched image pairs to process.[/yellow]")
            return 0
        groups = split_balanced(pairs, maximum=10)
        console.print(f"[green]Found {len(pairs)} pairs in {len(groups)} carousel group(s).[/green]")
        for index, group in enumerate(groups, start=1):
            process_group(index, group, config, state, args, logger, console)
        console.print("[bold green]✓ Complete[/bold green]")
        return 0
    except KeyboardInterrupt:
        logger.warning("Interrupted by user; progress saved after last successful group")
        console.print("[yellow]Interrupted. Progress saved after last successful upload group.[/yellow]")
        return 130
    except (ConfigError, Exception) as exc:  # noqa: BLE001 - log stack traces for production support.
        logger.exception("Fatal error")
        console.print(f"[bold red]Error:[/bold red] {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(run())
