# Instagram Carousel Uploader

A Python 3.13 command-line application that prepares Instagram carousel posts while leaving the Instagram UI actions to you. It uploads original screenshots to GitHub, generates RAW download URLs, builds and copies captions, opens Instagram, and opens Windows Explorer with only the current carousel's processed `*_output` images selected.

## Features

* Upload original screenshots to GitHub.
* Automatically generate RAW URLs.
* Automatically group screenshots into balanced Instagram carousel posts.
* Automatically generate captions.
* Automatically copy captions to clipboard.
* Automatically open Instagram.
* Automatically open Windows Explorer with only the processed `*_output` images selected.
* Resume interrupted sessions.
* Skip previously processed uploads.
* Rich console output.
* Comprehensive logging.

## Workflow

1. Run the application.
2. The application uploads only the original screenshots to GitHub and overwrites existing files when needed.
3. RAW GitHub URLs are generated after every original is uploaded, then verified as a batch so GitHub's eventually consistent RAW CDN has time to propagate.
4. A caption is generated and copied to the clipboard.
5. Instagram opens at `https://www.instagram.com/` in the system default browser.
6. Windows Explorer opens with only the current carousel group's processed `*_output` screenshots selected.
7. Drag the selected files into Instagram.
8. Click through Instagram's flow, edit if desired, paste the caption, and share.
9. Press `ENTER` in the terminal after the post has been successfully shared.
10. The application marks the group as processed and continues with the next balanced carousel group.

The app does not automate Instagram's DOM, file chooser, navigation, or publishing controls. You remain in control of every Instagram UI action.

## Installation

### Requirements

* Python 3.13
* A GitHub Personal Access Token with repository contents read/write access
* Windows for Explorer multi-file selection
  * On macOS/Linux, the app falls back to opening the output folder because Windows Explorer selection is unavailable.

### Setup

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

On macOS/Linux, activate the virtual environment with:

```bash
source .venv/bin/activate
```

### GitHub Personal Access Token setup

1. Create a fine-grained GitHub token or classic PAT.
2. Grant access to the target repository.
3. Ensure the token can read and write repository contents.
4. Put credentials in `.env` or `config.json`.

Recommended `.env`:

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
    "images": "C:/path/to/screenshots"
  },
  "caption": {
    "text": "Your caption text",
    "download_header": "Download original for wallpaper:",
    "hashtags": ["#Wallpaper", "#Game", "#Screenshot"]
  },
  "processing": {
    "skip_processed": true,
    "overwrite_github": true,
    "verify_upload": true,
    "retry_count": 3
  },
  "verification": {
    "enabled": true,
    "max_attempts": 12,
    "initial_delay": 0.5,
    "backoff": 1.7,
    "timeout_seconds": 45,
    "continue_on_timeout": true
  }
}
```

There is no browser configuration. The only browser action is:

```python
webbrowser.open("https://www.instagram.com/")
```

## Running

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

* `--dry-run`: scans, groups, and prints captions without uploading, copying, or opening Instagram.
* `--resume`: uses `processed.json` to skip completed originals.
* `--force`: ignores `processed.json` and processes all matched pairs.
* `--skip-github`: does not upload originals; still builds expected RAW URLs.
* `--skip-instagram`: uploads originals and copies captions, but does not open Instagram or Explorer.
* `--verbose`: prints more console logs while always writing detailed logs to `upload.log`.

## Expected project input

Place originals and processed output images in the configured `paths.images` folder:

```text
screenshots/
  A.png
  A_output.png
  B.jpg
  B_output.png
  C.webp
  C_output.webp
```

Only originals (`A.png`, `B.jpg`, `C.webp`) are uploaded to GitHub. Only matching output files (`A_output.png`, `B_output.png`, `C_output.webp`) are selected for the Instagram handoff.

## Captions

Captions keep this format:

```text
{caption}

Download original for wallpaper:

url1
url2
url3

#hashtags
```

The generated caption is automatically copied to the clipboard before Instagram opens.

## Carousel grouping

Instagram carousels allow up to 10 images. The app keeps the existing balanced grouping behavior:

* 11 images → 6 + 5
* 15 images → 5 + 5 + 5
* 22 images → 8 + 7 + 7
* 30 images → 10 + 10 + 10

## Project structure

```text
main.py           CLI orchestration
config.py         JSON/.env configuration and validation
explorer.py       Windows Explorer output-image selection
handoff.py        Instagram and user-confirmation handoff
github_api.py     GitHub REST API upload/update client
pairing.py        Image scanning and pair matching
grouping.py       Balanced carousel grouping
clipboard.py      pyperclip wrapper
logging_utils.py  logging setup
state.py          processed.json database
utils.py          caption helpers
config.json       example configuration
processed.json    processed-file state
requirements.txt  Python dependencies
README.md         project documentation
```

## Troubleshooting

### GitHub authentication fails

* Confirm `GITHUB_TOKEN` or `github.token` is set.
* Confirm the token has repository contents read/write access.
* Confirm `owner`, `repo`, and `branch` are correct.
* Check `upload.log` for GitHub response codes and response bodies.

### RAW URL verification waits

* Confirm the repository and branch are public, or disable `verification.enabled` if RAW URLs are not publicly reachable.
* Confirm `upload_folder` does not contain leading or trailing slashes.
* New uploads can return transient 404 responses from GitHub's RAW CDN even after the Contents API confirms the upload. The app now retries these responses and continues when propagation takes longer than the configured timeout.

### Instagram asks you to log in

* Log in through your normal default browser.
* Re-run the application after the browser session is authenticated.

### Explorer does not select every output image

* Install dependencies with `python -m pip install -r requirements.txt` on Windows so `pywin32` is available.
* If COM selection is unavailable, the app falls back to selecting the first output file and prints the complete filename list in the terminal.

### Clipboard copy fails

* Ensure desktop clipboard support is available.
* On Linux, `pyperclip` may require `xclip`, `xsel`, or a desktop session.

## Removed browser automation

The project intentionally no longer includes Playwright, CDP mode, persistent browser profiles, remote debugging, cookies, DOM automation, file chooser automation, Instagram page automation, Chrome profile handling, or Playwright profile handling.
