"""Exceptions raised by the BetaSeries API client."""

from __future__ import annotations


class BetaSeriesError(Exception):
    """Base error for all BetaSeries API failures."""


class BetaSeriesAuthError(BetaSeriesError):
    """The device flow failed definitively (invalid secret, expired code, ...)."""


class BetaSeriesAuthTimeoutError(BetaSeriesError):
    """The device flow was not completed within its expires_in window."""
