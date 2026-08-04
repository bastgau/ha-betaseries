"""Data returned by POST /oauth/device."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DeviceCodeData:
    """Represent the response of POST /oauth/device.

    Attributes:
        device_code (str): Opaque code to poll for the access token.
        user_code (str): Short code the user types on the BetaSeries website.
        verification_url (str): URL where the user enters the user_code.
        expires_in (int): Seconds before the device_code expires.
        interval (int): Minimum seconds to wait between two poll attempts.

    """

    device_code: str
    user_code: str
    verification_url: str
    expires_in: int
    interval: int
