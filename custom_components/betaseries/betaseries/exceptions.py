"""Exceptions raised by the BetaSeries API client."""

from __future__ import annotations


class Error(Exception):
    """Base error for all BetaSeries API failures.

    Carries the triggering response's status/body (when there is one) so
    callers can log or otherwise surface the exact BetaSeries error
    themselves - this client has no logging of its own, by design, so it
    stays usable outside.

    Attributes:
        status (int | None): HTTP status of the response that caused this error, if any.
        body (str | None): Raw response body that caused this error, if any.

    """

    def __init__(self, message: str, *, status: int | None = None, body: str | None = None) -> None:
        """Initialize the error, optionally carrying the response that caused it.

        Args:
            message (str): Human-readable error message.
            status (int | None): HTTP status of the response that caused this error, if any.
            body (str | None): Raw response body that caused this error, if any.

        """
        super().__init__(message)
        self.status = status
        self.body = body


class AuthError(Error):
    """The device flow failed definitively (invalid secret, expired code, ...)."""


class AuthTimeoutError(Error):
    """The device flow was not completed within its expires_in window."""


class NotWatchedError(Error):
    """The target episode/season is not marked as watched, a precondition for the requested action."""
