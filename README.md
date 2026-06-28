# GitHub → Instagram Carousel Uploader

A production-quality Python 3.13 application that prepares Instagram carousel posts from paired screenshots. It uploads **only original images** to GitHub, builds raw download links, copies a caption to the clipboard, opens Instagram Create Post, uploads **only processed `*_output` images**, advances to the final review/caption screen, and stops before publishing.

> This tool never clicks **Share**. You review, paste the caption, and publish manually.

## Features

- Matches originals with `*_output` files while ignoring extension differences (`A.png` + `A_output.webp`).
- Supports `png`, `jpg`, `jpeg`, and `webp`.
- Logs missing originals or missing outputs and skips incomplete pairs.
- Uploads originals to GitHub through the REST Contents API.
- Updates existing GitHub files when they already exist.
- Generates `raw.githubusercontent.com` URLs and optionally verifies HTTP 200 responses.
- Builds captions from configured text, download header, raw URLs, and hashtags.
- Copies captions to the Windows/system clipboard with `pyperclip`.
- Uses Playwright file chooser APIs; it does not automate OS file dialogs.
- Uses existing Chrome profile by default or a Playwright persistent profile when configured.
- Splits more than 10 images into balanced carousel groups without hardcoded tables.
- Maintains `processed.json` so completed originals can be skipped.
- Writes detailed diagnostics to `upload.log`.
- Provides `rich` console progress and status output.

## Project Structure

```text
main.py              CLI orchestration
config.py            JSON/.env configuration and validation
github_api.py        GitHub REST API upload/update client
instagram.py         Playwright Instagram automation
pairing.py           Image scanning and pair matching
grouping.py          Balanced carousel grouping
clipboard.py         pyperclip wrapper
logging_utils.py     logging setup
state.py             processed.json database
utils.py             caption and path helpers
config.json          example configuration
processed.json       processed-file state
requirements.txt     Python dependencies
README.md            this guide
```

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows PowerShell/CMD users can activate the venv from .venv\Scripts
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
playwright install chrome
```

On macOS/Linux, activate the virtual environment with:

```bash
source .venv/bin/activate
```

## GitHub Token Setup

1. Create a GitHub fine-grained token or classic PAT.
2. Grant access to the target repository.
3. Ensure the token can read and write repository contents.
4. Put it in `config.json` as `github.token`, or preferably set it in `.env`:

```env
GITHUB_TOKEN=ghp_your_token_here
GITHUB_OWNER=your-user-or-org
GITHUB_REPO=your-repository
```

Environment variables override `github.token`, `github.owner`, and `github.repo` from `config.json`.

## Configuration

Edit `config.json`:

```json
{
  "github": {
    "token": "",
    "owner": "",
    "repo": "",
    "branch": "main",
    "upload_folder": "screenshots"
  },
  "paths": {
    "images": "C:/path/to/folder"
  },
  "instagram": {
    "use_existing_chrome": true,
    "chrome_user_data": "C:/Users/YOU/AppData/Local/Google/Chrome/User Data",
    "chrome_profile": "Default",
    "playwright_profile": "./playwright_profile"
  },
  "caption": {
    "text": "Your custom caption",
    "download_header": "Download original for wallpaper:",
    "hashtags": ["#Wallpaper", "#Game", "#Screenshot"]
  },
  "processing": {
    "skip_processed": true,
    "overwrite_github": true,
    "verify_upload": true,
    "retry_count": 3
  }
}
```

### Chrome Profile Setup

For best results, log in to Instagram in Chrome first, then close Chrome before running the app.

Common Chrome user-data directories:

- Windows: `C:/Users/<you>/AppData/Local/Google/Chrome/User Data`
- macOS: `/Users/<you>/Library/Application Support/Google/Chrome`
- Linux: `/home/<you>/.config/google-chrome`

Set `chrome_profile` to the profile directory name, such as `Default`, `Profile 1`, or `Profile 2`.

If you do not want to use your existing Chrome profile, set:

```json
"use_existing_chrome": false
```

The app will then use `instagram.playwright_profile` as a persistent browser profile.

## How to Run

```bash
python main.py
```

Useful flags:

```bash
python main.py --dry-run
python main.py --resume
python main.py --force
python main.py --skip-github
python main.py --skip-instagram
python main.py --verbose
```

Flag behavior:

- `--dry-run`: scans, groups, and prints captions without uploading or opening Instagram.
- `--resume`: uses `processed.json` to skip completed originals.
- `--force`: ignores `processed.json` and processes all matched pairs.
- `--skip-github`: does not upload originals; still builds expected raw URLs.
- `--skip-instagram`: uploads originals and copies captions but does not open Instagram.
- `--verbose`: prints more console logs while always writing full logs to `upload.log`.

## Expected Folder Input

```text
folder/
  A.png
  A_output.png
  B.jpg
  B_output.webp
  C.png
  C_output.png
```

Only `A.png`, `B.jpg`, and `C.png` are uploaded to GitHub. Only `A_output.png`, `B_output.webp`, and `C_output.png` are selected for Instagram.

## Carousel Splitting

Instagram allows up to 10 images. The app computes balanced groups automatically:

- 11 → 6 + 5
- 15 → 5 + 5 + 5
- 22 → 8 + 7 + 7
- 30 → 10 + 10 + 10

The algorithm never exceeds 10 images per group.

## Workflow Details

For each balanced carousel group, the app:

1. Uploads original files to GitHub or updates existing files.
2. Verifies raw URLs if enabled.
3. Builds a caption.
4. Copies the caption to the clipboard.
5. Opens `https://www.instagram.com/create/select/`.
6. Uses Playwright's file chooser to upload output images.
7. Clicks **Next** until the caption/review page is visible.
8. Stops and prints:

```text
Ready!

Caption copied to clipboard.

Press CTRL+V inside Instagram.

Click Share manually.
```

## Troubleshooting

### GitHub authentication fails

- Confirm `GITHUB_TOKEN` or `github.token` is set.
- Confirm the token has repository contents read/write access.
- Confirm `owner`, `repo`, and `branch` are correct.
- Check `upload.log` for GitHub response codes and messages.

### Raw URL verification fails

- Confirm the repository and branch are public, or disable `verify_upload` if raw URLs are not publicly reachable immediately.
- Confirm `upload_folder` does not contain leading/trailing slashes.

### Instagram asks you to log in

- Open Chrome manually with the configured profile and log in to Instagram.
- Close Chrome completely, then rerun the app.
- Verify `chrome_user_data` and `chrome_profile` are correct.

### Browser profile is missing or locked

- Close all Chrome windows using that profile.
- Set `use_existing_chrome` to `false` to use the Playwright profile instead.

### Clipboard copy fails

- Install desktop clipboard support for your OS.
- On Linux, `pyperclip` may require `xclip`, `xsel`, or a desktop session.

### Playwright cannot find Chrome

Run:

```bash
playwright install chrome
```

## Safety Notes

- The application never uploads files ending in `_output` to GitHub.
- The application never uploads originals to Instagram.
- The application never clicks Instagram's **Share** button.
- Review every post manually before publishing.
