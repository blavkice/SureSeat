"""Booking domain: API client, email harvesting and Selenium validation."""

from .api import BookingClient
from .email_client import EmailClient, Reservation
from .validator import Validator, ValidationResult

__all__ = [
    "BookingClient",
    "EmailClient",
    "Reservation",
    "Validator",
    "ValidationResult",
]
