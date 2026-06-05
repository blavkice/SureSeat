"""Persistence for the user's saved places (resource id + label)."""

import json
import os

from . import config


class PlacesStore:
    """Load / save the list of ``{"name", "id"}`` place entries as JSON."""

    def __init__(self, path=None):
        self.path = path or config.PLACES_FILE

    def load(self):
        """Return the saved places, or an empty list if none/unreadable."""
        try:
            if os.path.exists(self.path):
                with open(self.path, "r") as f:
                    return json.load(f)
        except (OSError, ValueError):
            pass
        return []

    def save(self, places):
        """Persist ``places`` to disk. Returns ``True`` on success."""
        try:
            with open(self.path, "w") as f:
                json.dump(places, f, indent=2)
            return True
        except OSError:
            return False
