"""Static configuration and runtime constants.

Values that an operator may want to tweak (paths, worker counts, the Chrome
binary location) are read from environment variables so the same code runs
unchanged locally and inside Docker.
"""

import os

# --- Paths -----------------------------------------------------------------

# Project root (the directory that contains this package).
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Where the multilingual lookup tables live.
DATA_DIR = os.environ.get("SURESEAT_DATA_DIR", BASE_DIR)
MONTHS_FILE = os.path.join(DATA_DIR, "months.csv")
KEYWORDS_FILE = os.path.join(DATA_DIR, "keywords.csv")

# Persisted user data. Overridable so a Docker volume can hold them.
PLACES_FILE = os.environ.get("SURESEAT_PLACES_FILE", "places.json")
CREDENTIALS_FILE = os.environ.get("SURESEAT_CREDS_FILE", ".streamlit/.creds")

# --- Email / IMAP ----------------------------------------------------------

IMAP_SERVER = os.environ.get("SURESEAT_IMAP_SERVER", "imap.gmail.com")

# --- Concurrency -----------------------------------------------------------

MAX_WORKERS = int(os.environ.get("SURESEAT_MAX_WORKERS", "5"))

# Number of API booking requests fired per batch before a small pause.
API_BATCH_SIZE = int(os.environ.get("SURESEAT_API_BATCH_SIZE", "3"))

# --- Selenium / Chrome -----------------------------------------------------

# When set (e.g. in Docker) the system chromedriver is used and the
# webdriver-manager download is skipped entirely.
CHROMEDRIVER_PATH = os.environ.get("CHROMEDRIVER_PATH")

# Explicit Chrome/Chromium binary override.
CHROME_BINARY = os.environ.get("CHROME_BINARY")

# Page load / script timeout for headless validation, in seconds.
SELENIUM_TIMEOUT = int(os.environ.get("SURESEAT_SELENIUM_TIMEOUT", "7"))

# --- HTTP ------------------------------------------------------------------

AFFLUENCES_RESERVE_URL = "https://reservation.affluences.com/api/reserve/{resource_id}"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]

# --- Time slots ------------------------------------------------------------

# Canonical 30-minute slot labels ("00:00" .. "23:30").
ORARI = [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 30)]

# Late-night hours, shown with a "(night)" suffix in the UI.
ORARI_DISPLAY = [
    f"{t} (night)" if int(t[:2]) < 7 else t
    for t in ORARI
]
