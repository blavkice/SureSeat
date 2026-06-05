"""Multilingual lookup tables loaded from CSV.

Two tables are exposed:

* ``MONTHS``    - month name (any supported language) -> month number.
* ``KEYWORDS``  - button / success / already-confirmed phrases used when
                  scraping the confirmation page with Selenium.

Both fall back to a minimal English/Italian set if the CSV files are missing,
so the app keeps working even without the data files.
"""

import re

from . import config

_MONTHS_FALLBACK = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}

_KEYWORDS_FALLBACK = {
    "button": ["confirm", "conferma"],
    "success": ["success", "confirmed", "confermata", "validata"],
    "already": ["already confirmed", "già confermata"],
}


def load_months(path=None):
    """Return a {month_name_lower: month_number} mapping."""
    path = path or config.MONTHS_FILE
    months = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            next(f)  # skip header
            for line in f:
                line = line.strip()
                if line:
                    name, num = line.rsplit(",", 1)
                    months[name.lower()] = int(num)
    except (OSError, ValueError):
        return dict(_MONTHS_FALLBACK)
    return months or dict(_MONTHS_FALLBACK)


def load_keywords(path=None):
    """Return a {"button"|"success"|"already": [phrases]} mapping."""
    path = path or config.KEYWORDS_FILE
    keywords = {"button": [], "success": [], "already": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            next(f)  # skip header
            for line in f:
                line = line.strip()
                if line:
                    keyword, ktype = line.rsplit(",", 1)
                    if ktype in keywords:
                        keywords[ktype].append(keyword.lower())
    except OSError:
        return {k: list(v) for k, v in _KEYWORDS_FALLBACK.items()}
    # If any bucket ended up empty, fall back for that bucket.
    for bucket, fallback in _KEYWORDS_FALLBACK.items():
        if not keywords[bucket]:
            keywords[bucket] = list(fallback)
    return keywords


MONTHS = load_months()
MONTHS_PATTERN = "|".join(re.escape(m) for m in MONTHS.keys())
KEYWORDS = load_keywords()
