"""HTTP client for the Affluences reservation API."""

import random

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .. import config


def build_session():
    """Create a connection-pooled, retrying :class:`requests.Session`."""
    session = requests.Session()
    retry = Retry(total=2, backoff_factor=0.3,
                  status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def random_headers():
    """Headers mimicking a browser request to the Affluences frontend."""
    return {
        "User-Agent": random.choice(config.USER_AGENTS),
        "Content-Type": "application/json",
        "Origin": "https://affluences.com",
        "Referer": "https://affluences.com/",
        "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
    }


class BookingClient:
    """Submits booking requests for a resource over a shared HTTP session."""

    def __init__(self, session=None):
        self.session = session or build_session()

    def book_slot(self, user_email, date, start_time, end_time, resource_id):
        """Submit a single reservation.

        Returns ``(ok: bool, message: str)``.
        """
        url = config.AFFLUENCES_RESERVE_URL.format(resource_id=resource_id)
        payload = {
            "email": user_email,
            "date": date.strftime("%Y-%m-%d"),
            "start_time": start_time,
            "end_time": end_time,
            "person_count": 1,
            "note": "Reservation",
        }
        try:
            res = self.session.post(url, headers=random_headers(),
                                    json=payload, timeout=10)
            if res.status_code in (200, 201):
                return True, "Sent"
            if res.status_code == 400 and "quota" in res.text.lower():
                return False, "Quota Limit"
            return False, "Not Reserved"
        except requests.RequestException:
            return False, "Connection Error"
