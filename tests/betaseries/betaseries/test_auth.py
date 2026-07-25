"""Tests for Auth (OAuth device flow client).

aiohttp.ClientSession is mocked by hand (FakeResponse/FakeSession below)
instead of using aioresponses: aioresponses 0.7.9 (latest published) is
incompatible with aiohttp 3.14.1 installed here (ClientResponse.__init__
now requires a stream_writer keyword argument aioresponses does not pass).
"""

from __future__ import annotations

import asyncio
from typing import Any, Self
from unittest.mock import AsyncMock

from custom_components.betaseries.betaseries.auth import Auth
from custom_components.betaseries.betaseries.exceptions import (
    AuthError,
    AuthTimeoutError,
)
import pytest

API_KEY = "test-api-key"
CLIENT_SECRET = "test-client-secret"


class FakeResponse:
    """Minimal async context manager standing in for an aiohttp response."""

    def __init__(self, status: int, payload: dict[str, Any] | None = None) -> None:
        """Initialize the fake response.

        Args:
            status (int): HTTP status code to report.
            payload (dict[str, Any] | None): JSON body returned by .json().

        """
        self.status = status
        self._payload = payload or {}

    async def json(self) -> dict[str, Any]:
        """Return the JSON payload.

        Returns:
            dict[str, Any]: The configured payload.

        """
        return self._payload

    async def __aenter__(self) -> Self:
        """Enter the async context manager.

        Returns:
            Self: This same fake response.

        """
        return self

    async def __aexit__(self, *_args: object) -> None:
        """Exit the async context manager."""


class FakeSession:
    """Stand-in for aiohttp.ClientSession returning queued FakeResponses.

    Attributes:
        post_responses (list[FakeResponse]): Responses returned by .post(), in order.
        get_responses (list[FakeResponse]): Responses returned by .get(), in order.
        get_calls (list[tuple[tuple[Any, ...], dict[str, Any]]]): Args/kwargs of each .get() call, in order.

    """

    def __init__(
        self,
        post_responses: list[FakeResponse] | None = None,
        get_responses: list[FakeResponse] | None = None,
    ) -> None:
        """Initialize the fake session with queued responses.

        Args:
            post_responses (list[FakeResponse] | None): Responses for .post(), in order.
            get_responses (list[FakeResponse] | None): Responses for .get(), in order.

        """
        self.post_responses = list(post_responses or [])
        self.get_responses = list(get_responses or [])
        self.get_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def post(self, *_args: object, **_kwargs: object) -> FakeResponse:
        """Return the next queued POST response.

        Returns:
            FakeResponse: The next queued response.

        """
        return self.post_responses.pop(0)

    def get(self, *args: Any, **kwargs: Any) -> FakeResponse:
        """Return the next queued GET response, recording the call's args/kwargs.

        Args:
            *args (Any): Positional arguments the caller passed to .get().
            **kwargs (Any): Keyword arguments the caller passed to .get().

        Returns:
            FakeResponse: The next queued response.

        """
        self.get_calls.append((args, kwargs))
        return self.get_responses.pop(0)


async def test_request_device_code_success() -> None:
    """Return a DeviceCodeData built from the JSON payload on HTTP 200."""
    session = FakeSession(
        post_responses=[
            FakeResponse(
                200,
                {
                    "device_code": "abc123",
                    "user_code": "XYZ789",
                    "verification_url": "https://www.betaseries.com/device",
                    "expires_in": 1800,
                    "interval": 5,
                },
            )
        ]
    )
    auth = Auth(session, API_KEY, CLIENT_SECRET)  # type: ignore[arg-type]

    result = await auth.request_device_code()

    assert result.device_code == "abc123"
    assert result.user_code == "XYZ789"
    assert result.verification_url == "https://www.betaseries.com/device"
    assert result.expires_in == 1800
    assert result.interval == 5


@pytest.mark.parametrize("status", [400, 401, 403, 500, 503])
async def test_request_device_code_failure(status: int) -> None:
    """Raise AuthError when the device code request fails.

    Args:
        status (int): Non-200 HTTP status returned by the fake response.

    """
    session = FakeSession(post_responses=[FakeResponse(status)])
    auth = Auth(session, API_KEY, CLIENT_SECRET)  # type: ignore[arg-type]

    with pytest.raises(AuthError):
        await auth.request_device_code()


async def test_poll_for_token_pending_then_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Retry on pending (code 2001) and return the token once validated."""
    sleep_mock = AsyncMock()
    monkeypatch.setattr(asyncio, "sleep", sleep_mock)

    session = FakeSession(
        post_responses=[
            FakeResponse(400, {"errors": [{"code": 2001, "text": "En attente de l'identification."}]}),
            FakeResponse(200, {"access_token": "token123", "token_type": "bearer"}),
        ]
    )
    auth = Auth(session, API_KEY, CLIENT_SECRET)  # type: ignore[arg-type]

    token = await auth.poll_for_token("device-code", expires_in=1800, interval=5)

    assert token == "token123"
    sleep_mock.assert_awaited_once_with(5)


@pytest.mark.parametrize("error_code", [4001, 4002, 9999])
async def test_poll_for_token_definitive_error(error_code: int) -> None:
    """Raise AuthError without retrying on a non-pending error.

    Args:
        error_code (int): BetaSeries error code, distinct from ERROR_CODE_PENDING.

    """
    session = FakeSession(
        post_responses=[FakeResponse(400, {"errors": [{"code": error_code, "text": "Invalid client_secret."}]})]
    )
    auth = Auth(session, API_KEY, CLIENT_SECRET)  # type: ignore[arg-type]

    with pytest.raises(AuthError):
        await auth.poll_for_token("device-code", expires_in=1800, interval=5)


@pytest.mark.parametrize("status", [401, 403, 500, 503])
async def test_poll_for_token_unexpected_status(status: int) -> None:
    """Raise AuthError on a status that is neither 200 nor 400.

    Args:
        status (int): HTTP status returned by the fake response.

    """
    session = FakeSession(post_responses=[FakeResponse(status)])
    auth = Auth(session, API_KEY, CLIENT_SECRET)  # type: ignore[arg-type]

    with pytest.raises(AuthError):
        await auth.poll_for_token("device-code", expires_in=1800, interval=5)


async def test_poll_for_token_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Raise AuthTimeoutError once expires_in has elapsed.

    time.monotonic() is not mocked here: it is the same module object used
    internally by asyncio's event loop for scheduling, so patching it would
    break the loop itself. Using expires_in=0 makes the deadline already
    elapsed by the time the first pending response is checked, without
    needing to mock the clock.
    """
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())

    session = FakeSession(
        post_responses=[FakeResponse(400, {"errors": [{"code": 2001, "text": "En attente de l'identification."}]})]
    )
    auth = Auth(session, API_KEY, CLIENT_SECRET)  # type: ignore[arg-type]

    with pytest.raises(AuthTimeoutError):
        await auth.poll_for_token("device-code", expires_in=0, interval=5)


async def test_fetch_member_identity_success() -> None:
    """Return a MemberIdentity built from the JSON payload on HTTP 200."""
    session = FakeSession(get_responses=[FakeResponse(200, {"member": {"id": 42, "login": "test_user"}})])
    auth = Auth(session, API_KEY, CLIENT_SECRET)  # type: ignore[arg-type]

    identity = await auth.fetch_member_identity("token123")

    assert identity.id == "42"
    assert identity.login == "test_user"


@pytest.mark.parametrize("status", [400, 401, 403, 500, 503])
async def test_fetch_member_identity_failure(status: int) -> None:
    """Raise AuthError when fetching the member identity fails.

    Args:
        status (int): Non-200 HTTP status returned by the fake response.

    """
    session = FakeSession(get_responses=[FakeResponse(status)])
    auth = Auth(session, API_KEY, CLIENT_SECRET)  # type: ignore[arg-type]

    with pytest.raises(AuthError):
        await auth.fetch_member_identity("token123")
