"""Tests for Auth (OAuth device flow client).

aiohttp.ClientSession is mocked by hand (FakeResponse/FakeSession below)
instead of using aioresponses: aioresponses 0.7.9 (latest published) is
incompatible with aiohttp 3.14.1 installed here (ClientResponse.__init__
now requires a stream_writer keyword argument aioresponses does not pass).
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any, Self
from unittest.mock import AsyncMock

import aiohttp
from custom_components.betaseries.betaseries.auth import Auth
from custom_components.betaseries.betaseries.const import REQUEST_TIMEOUT_SECONDS
from custom_components.betaseries.betaseries.exceptions import (
    AuthError,
    AuthTimeoutError,
)
import pytest

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

API_KEY = "test-api-key"
CLIENT_SECRET = "test-client-secret"


class FakeResponse:
    """Minimal async context manager standing in for an aiohttp response."""

    def __init__(self, status: int, payload: dict[str, Any] | None = None) -> None:
        """Initialize the fake response."""
        self.status = status
        self._payload = payload or {}

    async def json(self) -> dict[str, Any]:
        """Return the JSON payload."""
        return self._payload

    async def text(self) -> str:
        """Return the raw text body (the payload, JSON-encoded)."""
        return json.dumps(self._payload)

    async def __aenter__(self) -> Self:
        """Enter the async context manager."""
        return self

    async def __aexit__(self, *_args: object) -> None:
        """Exit the async context manager."""


class FakeSession:
    """Stand-in for aiohttp.ClientSession returning queued FakeResponses.

    A queued Exception is raised instead of returned, standing in for a
    transport failure: aiohttp raises those from the call itself, before any
    response exists (see _TRANSPORT_ERRORS in auth.py/client.py).
    """

    def __init__(
        self,
        post_responses: list[FakeResponse | Exception] | None = None,
        get_responses: list[FakeResponse | Exception] | None = None,
    ) -> None:
        """Initialize the fake session with queued responses."""
        self.post_responses = list(post_responses or [])
        self.get_responses = list(get_responses or [])
        self.get_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
        self.post_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def post(self, *args: Any, **kwargs: Any) -> FakeResponse:
        """Return the next queued POST response, recording the call's args/kwargs."""
        self.post_calls.append((args, kwargs))
        return _unqueue(self.post_responses)

    def get(self, *args: Any, **kwargs: Any) -> FakeResponse:
        """Return the next queued GET response, recording the call's args/kwargs."""
        self.get_calls.append((args, kwargs))
        return _unqueue(self.get_responses)


def _unqueue(queued: list[FakeResponse | Exception]) -> FakeResponse:
    """Pop the next queued item, raising it when it stands in for a transport failure."""
    item = queued.pop(0)
    if isinstance(item, Exception):
        raise item
    return item


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
    """Raise AuthError when the device code request fails."""
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
    """Raise AuthError without retrying on a non-pending error."""
    session = FakeSession(
        post_responses=[FakeResponse(400, {"errors": [{"code": error_code, "text": "Invalid client_secret."}]})]
    )
    auth = Auth(session, API_KEY, CLIENT_SECRET)  # type: ignore[arg-type]

    with pytest.raises(AuthError):
        await auth.poll_for_token("device-code", expires_in=1800, interval=5)


@pytest.mark.parametrize("status", [401, 403, 500, 503])
async def test_poll_for_token_unexpected_status(status: int) -> None:
    """Raise AuthError on a status that is neither 200 nor 400."""
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
    """Raise AuthError when fetching the member identity fails."""
    session = FakeSession(get_responses=[FakeResponse(status)])
    auth = Auth(session, API_KEY, CLIENT_SECRET)  # type: ignore[arg-type]

    with pytest.raises(AuthError):
        await auth.fetch_member_identity("token123")


# Annotated as a named list rather than inline in the decorator: pytest.mark.parametrize
# takes its cases untyped, so an inline lambda has no expected type to infer its
# parameter from and reads as untyped.
_TRANSPORT_CALLS: list[tuple[str, Callable[[Auth], Coroutine[Any, Any, object]]]] = [
    ("post_responses", lambda auth: auth.request_device_code()),
    ("post_responses", lambda auth: auth.poll_for_token("device-code", 1800, 0)),
    ("get_responses", lambda auth: auth.fetch_member_identity("token123")),
]


@pytest.mark.parametrize(
    ("queue_kwarg", "call"),
    _TRANSPORT_CALLS,
    ids=["request_device_code", "poll_for_token", "fetch_member_identity"],
)
@pytest.mark.parametrize(
    "transport_error",
    [aiohttp.ClientConnectionError("cannot connect"), TimeoutError()],
    ids=["connection", "timeout"],
)
async def test_transport_failure_surfaces_as_auth_error(
    queue_kwarg: str,
    call: Callable[[Auth], Coroutine[Any, Any, object]],
    transport_error: Exception,
) -> None:
    """Wrap aiohttp's own failures into AuthError, on every request Auth makes.

    A caller only ever handles this package's exceptions: before this, a
    network failure escaped as a raw aiohttp error and the config flow, which
    catches AuthError, showed "Unknown error occurred" instead of its
    translated "cannot connect" message.
    """
    queued: list[FakeResponse | Exception] = [transport_error]
    session = FakeSession(**{queue_kwarg: queued})
    auth = Auth(session, API_KEY, CLIENT_SECRET)  # type: ignore[arg-type]

    with pytest.raises(AuthError) as raised:
        await call(auth)

    assert raised.value.__cause__ is transport_error


async def test_every_request_declares_its_own_timeout() -> None:
    """Send an explicit ClientTimeout on the device flow too.

    See the matching test in test_client.py: the point is that the deadline is
    chosen by this package, not inherited from aiohttp's 300 s default.
    """
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
        ],
        get_responses=[FakeResponse(200, {"member": {"id": 42, "login": "test_user"}})],
    )
    auth = Auth(session, API_KEY, CLIENT_SECRET)  # type: ignore[arg-type]

    await auth.request_device_code()
    await auth.fetch_member_identity("token123")

    assert session.post_calls[0][1]["timeout"].total == REQUEST_TIMEOUT_SECONDS
    assert session.get_calls[0][1]["timeout"].total == REQUEST_TIMEOUT_SECONDS
