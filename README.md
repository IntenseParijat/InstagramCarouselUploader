# GitHub → Instagram Carousel Uploader

A Python 3.13 application that prepares Instagram carousel posts from paired screenshots. It uploads **only original images** to GitHub, builds raw download links, copies a caption to the clipboard, opens Instagram Create Post, and guides you through dragging the processed `*_output` images into Instagram.

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
- Defaults to **ATTACH** mode: no Playwright, no CDP, no Chrome launch, and no profile/cookie handling.
- Keeps optional **CDP** and **PERSISTENT** modes for users who intentionally configure browser automation.
- Splits more than 10 images into balanced carousel groups without hardcoded tables.
- Maintains `processed.json` so completed originals can be skipped.
- Writes detailed diagnostics to `upload.log`.
- Provides `rich` console progress and status output.

## Project Structure

```text
main.py              CLI orchestration
config.py            JSON/.env configuration and validation
github_api.py        GitHub REST API upload/update client
instagram.py         Instagram handoff and optional Playwright automation
browser_manager.py   CDP connection and persistent-profile launch helpers
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
```

On macOS/Linux, activate the virtual environment with:

```bash
source .venv/bin/activate
```

Playwright is only required for `browser.mode` values of `cdp` or `persistent`. If you use one of those optional modes, also run:

```bash
playwright install chrome
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

Edit `config.json`.

### Browser Modes

The `browser.mode` setting supports three values:

```json
{
  "browser": {
    "mode": "attach"
  }
}
```

### ATTACH Mode (default)

`attach` is the recommended workflow and the default in `config.json`.

In this mode the app:

1. Uploads originals to GitHub.
2. Generates and copies the caption.
3. Opens `https://www.instagram.com/create/select/` with the operating system's default browser.
4. Opens the folder containing the current carousel's `*_output` images.
5. Prints the exact output filenames.
6. Waits for you to drag those files into Instagram and press `ENTER` in the terminal.

ATTACH mode intentionally does **not** use Playwright, CDP, Chrome profile directories, cookies, or automated native file picker control. Browsers intentionally prevent websites from reading arbitrary local files, so manual drag-and-drop is the reliable handoff point.

Example console prompt:

```text
Caption copied.

Instagram opened.

Output images:

A_output.png
B_output.png
C_output.png

Drag these images into Instagram.

Press ENTER here when you're ready.
```

### CDP Mode

`cdp` connects to an already-running Chrome instance that was explicitly started with remote debugging.

The app first checks:

```text
http://127.0.0.1:9222/json/version
```

If the endpoint is unavailable, the app does **not** launch Chrome. It prints guidance like:

```text
Chrome isn't running with remote debugging.

Run:

chrome.exe
--remote-debugging-port=9222

or switch browser.mode to ATTACH.
```

To use CDP mode, close existing Chrome windows first and then start Chrome yourself with remote debugging enabled, for example:

```bash
chrome.exe --remote-debugging-port=9222
```

Starting `chrome.exe --remote-debugging-port=9222` while Chrome is already running usually forwards the request to the existing Chrome instance and does not open a debugging port.

### Persistent Mode

`persistent` launches a dedicated Playwright automation profile. It is only for automation-specific browser state and must never point at your daily Chrome profile.

Use a separate path such as:

```json
{
  "browser": {
    "mode": "persistent",
    "automation_profile": "C:/InstagramAutomationProfile"
  }
}
```

The app rejects obviously unsafe daily-profile paths such as `Default`, `Profile 1`, `Profile 2`, or a path inside the configured Chrome user-data directory.

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

Only `A.png`, `B.jpg`, and `C.png` are uploaded to GitHub. Only `A_output.png`, `B_output.webp`, and `C_output.png` are handed off for Instagram.

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
5. Opens Instagram according to `browser.mode`.
6. In default ATTACH mode, opens the output folder and lists the current carousel's output images.
7. Waits for you to drag the images into Instagram and press `ENTER`.
8. Marks the group as processed and continues to the next carousel.

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

- Use ATTACH mode and log in through your normal default browser.
- If you use CDP mode, make sure the remote-debugging Chrome instance is logged in.
- If you use persistent mode, log in once inside the dedicated automation profile.

### CDP cannot connect

- Confirm Chrome was started before the app with `--remote-debugging-port=9222`.
- Confirm `http://127.0.0.1:9222/json/version` opens locally.
- Do not expect a debugging port to appear if you run the command while a normal Chrome instance is already running.
- Switch `browser.mode` back to `attach` for the recommended workflow.

### Browser profile is missing or locked

- Prefer ATTACH mode, which uses your existing browser session without reading a profile directory.
- For persistent mode, use a dedicated automation profile path, not your daily Chrome profile.

### Clipboard copy fails

- Install desktop clipboard support for your OS.
- On Linux, `pyperclip` may require `xclip`, `xsel`, or a desktop session.

### Playwright cannot find Chrome

Only CDP and persistent modes need Playwright browser support. Run:

```bash
playwright install chrome
```

## Safety Notes

- The application never uploads files ending in `_output` to GitHub.
- The application never uploads originals to Instagram.
- ATTACH mode never controls Chrome, cookies, profiles, CDP, or the native file picker.
- The application never clicks Instagram's **Share** button.
- Review every post manually before publishing.
