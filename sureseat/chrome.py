"""Chrome/Chromium discovery and headless option building.

Resolution order honours the Docker-friendly env overrides in
:mod:`sureseat.config` before falling back to filesystem probing and, last,
``webdriver-manager`` (which downloads a driver on first use).
"""

import os
import shutil
import subprocess

from selenium.webdriver.chrome.options import Options

from . import config

_CHROME_CANDIDATES = [
    # macOS
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    # Linux
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/snap/bin/chromium",
    # Windows
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]

_CHROME_NAMES = [
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
]


def find_chrome_binary():
    """Return a path to a Chrome/Chromium binary, or ``None`` if not found."""
    if config.CHROME_BINARY:
        return config.CHROME_BINARY
    for path in _CHROME_CANDIDATES:
        if os.path.exists(path):
            return path
    for name in _CHROME_NAMES:
        found = shutil.which(name)
        if found:
            return found
    return None


def resolve_driver_path():
    """Return the chromedriver path.

    Uses ``CHROMEDRIVER_PATH`` when set (the Docker case), otherwise defers to
    webdriver-manager. Returns ``None`` if resolution fails.
    """
    if config.CHROMEDRIVER_PATH:
        return config.CHROMEDRIVER_PATH
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        return ChromeDriverManager().install()
    except Exception:
        return None


def build_options(user_agent):
    """Build headless Chrome ``Options`` tuned for fast, quiet validation."""
    options = Options()
    binary = find_chrome_binary()
    if binary:
        options.binary_location = binary
    for arg in (
        "--headless",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--blink-settings=imagesEnabled=false",
        "--disable-extensions",
        "--disable-plugins",
        "--disable-software-rasterizer",
        "--disable-logging",
        "--log-level=3",
        f"user-agent={user_agent}",
    ):
        options.add_argument(arg)
    return options


def kill_stale_processes():
    """Best-effort cleanup of leftover Chrome/driver processes."""
    try:
        if os.name == "posix":
            for proc in ("chrome", "chromium", "chromedriver"):
                subprocess.run(["killall", "-9", proc], stderr=subprocess.DEVNULL)
        elif os.name == "nt":
            for proc in ("chrome.exe", "chromedriver.exe"):
                subprocess.run(["taskkill", "/F", "/IM", proc], stderr=subprocess.DEVNULL)
    except Exception:
        pass
