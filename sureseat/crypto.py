"""Machine-tied credential storage.

Credentials are obfuscated with a XOR cipher keyed on a SHA-256 of
``hostname + username`` and stored base64-encoded. This is *not* strong
cryptography - it only avoids plaintext secrets at rest and ties the file to
the machine that wrote it. Treat the app password as recoverable on that host.
"""

import base64
import getpass
import hashlib
import json
import os
import socket

from . import config


def _machine_key():
    machine_id = f"{socket.gethostname()}-{getpass.getuser()}".encode()
    digest = hashlib.sha256(machine_id).digest()
    return base64.urlsafe_b64encode(digest)


def _xor(data, key):
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


def encrypt(text):
    """Encrypt a unicode string into a base64 token."""
    token = _xor(text.encode(), _machine_key())
    return base64.b64encode(token).decode()


def decrypt(token):
    """Reverse :func:`encrypt`. Returns ``None`` if the token is unreadable."""
    try:
        raw = base64.b64decode(token.encode())
        return _xor(raw, _machine_key()).decode()
    except Exception:
        return None


class CredentialStore:
    """Load and persist the Gmail address + app password pair."""

    def __init__(self, path=None):
        self.path = path or config.CREDENTIALS_FILE

    def load(self):
        """Return ``(email, password)`` or ``(None, None)`` if unavailable."""
        try:
            if not os.path.exists(self.path):
                return None, None
            with open(self.path, "r") as f:
                content = json.load(f)
            email = decrypt(content.get("email", ""))
            password = decrypt(content.get("password", ""))
            if email and password:
                return email, password
        except (OSError, ValueError):
            pass
        return None, None

    def save(self, email, password):
        """Persist credentials encrypted. Returns ``True`` on success."""
        try:
            directory = os.path.dirname(self.path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            payload = {"email": encrypt(email), "password": encrypt(password)}
            with open(self.path, "w") as f:
                json.dump(payload, f)
            return True
        except OSError:
            return False
