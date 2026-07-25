"""Exceptions raised by the BetaSeries API client."""

from __future__ import annotations


class Error(Exception):
    """Base error for all BetaSeries API failures."""


class AuthError(Error):
    """The device flow failed definitively (invalid secret, expired code, ...)."""


class AuthTimeoutError(Error):
    """The device flow was not completed within its expires_in window."""
