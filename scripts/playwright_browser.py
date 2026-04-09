#!/usr/bin/env python3
"""Shared Playwright browser launch helpers for local smoke tests."""

from __future__ import annotations

import os
import platform
from pathlib import Path
from typing import Any


DEFAULT_LAUNCH_ARGS = [
    "--disable-dev-shm-usage",
    "--disable-features=Translate,OptimizationHints,MediaRouter",
    "--disable-popup-blocking",
    "--no-default-browser-check",
    "--no-first-run",
]

MACOS_CHROME_PATHS = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    str(Path.home() / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
]

WINDOWS_CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]

LINUX_CHROME_PATHS = [
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/snap/bin/chromium",
]

LOCAL_BROWSER_PATTERNS = [
    ".playwright-browsers/chromium-*/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
    ".playwright-browsers/chromium-*/chrome-linux/chrome",
    ".playwright-browsers/chromium-*/chrome-win/chrome.exe",
]


def _candidate_executables() -> list[str]:
    candidates: list[str] = []
    configured = os.environ.get("PLAYWRIGHT_CHROME_EXECUTABLE")
    if configured:
        candidates.append(configured)

    system = platform.system()
    if system == "Darwin":
        candidates.extend(MACOS_CHROME_PATHS)
    elif system == "Windows":
        candidates.extend(WINDOWS_CHROME_PATHS)
    else:
        candidates.extend(LINUX_CHROME_PATHS)

    repo_root = Path(__file__).resolve().parent.parent
    for pattern in LOCAL_BROWSER_PATTERNS:
        for candidate in sorted(repo_root.glob(pattern), reverse=True):
            candidates.append(str(candidate))

    return candidates


async def launch_browser(
    playwright: Any,
    *,
    headless: bool,
    extra_args: list[str] | None = None,
) -> Any:
    """Launch the installed Chrome app when available, then fall back gracefully."""
    launch_args = [*DEFAULT_LAUNCH_ARGS, *(extra_args or [])]
    browser_type = playwright.chromium
    errors: list[str] = []

    for executable in _candidate_executables():
        if not Path(executable).exists():
            continue
        try:
            return await browser_type.launch(
                executable_path=executable,
                headless=headless,
                args=launch_args,
            )
        except Exception as exc:  # pragma: no cover - best-effort fallback path
            errors.append(f"executable_path={executable}: {exc}")

    try:
        return await browser_type.launch(
            channel="chrome",
            headless=headless,
            args=launch_args,
        )
    except Exception as exc:
        errors.append(f'channel="chrome": {exc}')

    try:
        return await browser_type.launch(headless=headless, args=launch_args)
    except Exception as exc:
        errors.append(f"bundled chromium: {exc}")
        raise RuntimeError(
            "Unable to launch Playwright browser. Tried system Chrome app, "
            'Playwright channel="chrome", and bundled Chromium. '
            + " | ".join(errors)
        ) from exc
