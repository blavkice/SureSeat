"""IMAP harvesting of Affluences confirmation emails.

:class:`EmailClient` owns an optional persistent IMAP connection (useful when
polling the inbox in a loop) and knows how to:

* search for confirmation emails and extract ``(date, link)`` pairs;
* delete Affluences emails to keep the inbox clean.
"""

import email
import imaplib
import re
from dataclasses import dataclass
from datetime import date as date_cls, datetime, timedelta

from .. import config
from ..i18n import MONTHS, MONTHS_PATTERN

_LINK_RE = re.compile(
    r"(https://affluences\.com.*?/reservation/confirm\?reservationToken=[a-zA-Z0-9-]+)"
)
_DATE_RE = re.compile(
    rf"(\d{{1,2}})\s+({MONTHS_PATTERN})\s+(\d{{4}})", re.IGNORECASE
)


@dataclass
class Reservation:
    """A confirmation email's parsed date and confirmation link."""
    date: date_cls
    link: str


def _parse_body(msg):
    """Extract the (preferably HTML) text body from an email message."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode(errors="ignore")
        return ""
    payload = msg.get_payload(decode=True)
    return payload.decode(errors="ignore") if payload else ""


def _extract_reservation(body):
    """Return a :class:`Reservation` from an email body, or ``None``."""
    m_date = _DATE_RE.search(body)
    m_link = _LINK_RE.search(body)
    if not (m_date and m_link):
        return None
    try:
        day = int(m_date.group(1))
        month = MONTHS.get(m_date.group(2).lower(), 0)
        year = int(m_date.group(3))
        when = datetime(year, month, day).date()
    except ValueError:
        return None
    link = m_link.group(1).replace("&amp;", "&")
    return Reservation(date=when, link=link)


class EmailClient:
    """Gmail IMAP client scoped to a single account."""

    def __init__(self, user, app_password, server=None):
        self.user = user
        self.app_password = app_password
        self.server = server or config.IMAP_SERVER
        self._persistent = None

    # -- connection management ---------------------------------------------

    def _connect(self):
        mail = imaplib.IMAP4_SSL(self.server)
        mail.login(self.user, self.app_password)
        return mail

    def _persistent_connection(self):
        """Return a live persistent connection, (re)connecting as needed."""
        if self._persistent is None:
            try:
                self._persistent = self._connect()
            except Exception:
                return None
        else:
            try:
                self._persistent.noop()
            except Exception:
                try:
                    self._persistent = self._connect()
                except Exception:
                    self._persistent = None
        return self._persistent

    def close(self):
        """Close the persistent connection if one is open."""
        if self._persistent is not None:
            try:
                self._persistent.logout()
            except Exception:
                pass
            self._persistent = None

    # -- queries -----------------------------------------------------------

    def find_confirmations(self, hours=None, use_persistent=False):
        """Find confirmation reservations.

        ``hours``: when set, search emails received in the last N hours;
        otherwise search ``UNSEEN`` emails. ``use_persistent`` reuses the
        long-lived connection (faster for polling loops).
        """
        mail = None
        try:
            if use_persistent:
                mail = self._persistent_connection()
                if not mail:
                    return []
            else:
                mail = self._connect()

            mail.select("inbox")

            if hours is not None:
                since = (datetime.now() - timedelta(hours=hours)).strftime("%d-%b-%Y")
                queries = [
                    f'(SINCE {since} FROM "no-reply@affluences.com")',
                    f'(SINCE {since} FROM "Affluences")',
                ]
            else:
                queries = [
                    '(UNSEEN FROM "no-reply@affluences.com")',
                    '(UNSEEN FROM "Affluences")',
                ]

            ids = []
            for query in queries:
                _, messages = mail.search(None, query)
                if messages[0]:
                    ids = messages[0].split()
                    break

            found = []
            for email_id in ids:
                # BODY.PEEK[] does not set the \Seen flag, so retries still match.
                _, data = mail.fetch(email_id, "(BODY.PEEK[])")
                msg = email.message_from_bytes(data[0][1])
                reservation = _extract_reservation(_parse_body(msg))
                if reservation:
                    found.append(reservation)
            return found
        except Exception:
            return []
        finally:
            if not use_persistent and mail is not None:
                try:
                    mail.logout()
                except Exception:
                    pass

    def delete_affluences_emails(self, days=7):
        """Delete Affluences emails from the last ``days`` days.

        Returns ``(found_count, deleted_count, error)``.
        """
        found = deleted = 0
        try:
            mail = self._connect()
            mail.select("inbox")
            since = (datetime.now() - timedelta(days=days)).strftime("%d-%b-%Y")

            queries = [
                f'(SINCE {since} FROM "no-reply@affluences.com")',
                f'(SINCE {since} FROM "Affluences")',
                f'(SINCE {since} SUBJECT "prenotazione")',
                f'(SINCE {since} SUBJECT "reservation")',
            ]
            ids = set()
            for query in queries:
                try:
                    _, messages = mail.search(None, query)
                    if messages[0]:
                        ids.update(messages[0].split())
                except Exception:
                    continue

            found = len(ids)
            for email_id in ids:
                try:
                    mail.store(email_id, "+FLAGS", "\\Deleted")
                    deleted += 1
                except Exception:
                    continue

            mail.expunge()
            mail.logout()
            return found, deleted, None
        except Exception as exc:
            return found, deleted, str(exc)
