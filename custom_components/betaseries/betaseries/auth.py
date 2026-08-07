"""OAuth device flow client for the BetaSeries API.

Never lets aiohttp's own exceptions escape: a caller of this package should
only ever have to handle AuthError/AuthTimeoutError, without knowing which
HTTP library is used underneath (see the sub-package README).
"""

from __future__ import annotations

import asyncio
import hashlib
import time

import aiohttp

from .const import (
    API_VERSION,
    BASE_URL,
    ERROR_CODE_PENDING,
    MEMBERS_AUTH_ENDPOINT,
    MEMBERS_INFOS_ENDPOINT,
    OAUTH_DEVICE_ENDPOINT,
    OAUTH_TOKEN_ENDPOINT,
    REQUEST_TIMEOUT_SECONDS,
)
from .device_code import DeviceCodeData
from .exceptions import AuthError, AuthTimeoutError
from .member_identity import MemberIdentity

# Transport failures aiohttp raises before any HTTP status exists (DNS, refused
# connection, TLS, read timeout). Wrapped into AuthError so callers only ever
# handle this package's own exceptions - see the module docstring.
_TRANSPORT_ERRORS = (aiohttp.ClientError, TimeoutError)

# Built once: ClientTimeout is immutable, and every request uses the same one.
_TIMEOUT = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)


class Auth:
    """Handle the BetaSeries OAuth device flow.

    See CLAUDE.md §3 for the verified endpoint contract. Built directly on
    aiohttp: polling is native async, and the expires_in guard rail has no
    underlying library to rely on, so it is implemented here.

    Attributes:
        _session (aiohttp.ClientSession): Injected HTTP session.
        _api_key (str): BetaSeries API key (client_id).
        _client_secret (str): BetaSeries API client secret, unused by authenticate_with_password.

    """

    def __init__(self, session: aiohttp.ClientSession, api_key: str, client_secret: str = "") -> None:
        """Initialize the auth client with an injected aiohttp session.

        Args:
            session (aiohttp.ClientSession): Injected HTTP session.
            api_key (str): BetaSeries API key (client_id).
            client_secret (str): BetaSeries API client secret. Only request_device_code/poll_for_token need it - omit it when only authenticate_with_password will be used.

        """
        self._session = session
        self._api_key = api_key
        self._client_secret = client_secret

    @property
    def _headers(self) -> dict[str, str]:
        """Return the headers required on every BetaSeries request.

        Returns:
            dict[str, str]: Headers to send on every request.

        """
        return {
            "X-BetaSeries-Key": self._api_key,
            "X-BetaSeries-Version": API_VERSION,
        }

    async def request_device_code(self) -> DeviceCodeData:
        """Request a device code to start the device flow (POST /oauth/device).

        Returns:
            DeviceCodeData: The device code and verification details.

        Raises:
            AuthError: If the request fails, or BetaSeries cannot be reached at all.

        """
        try:
            async with self._session.post(
                f"{BASE_URL}{OAUTH_DEVICE_ENDPOINT}",
                headers=self._headers,
                data={"client_id": self._api_key},
                timeout=_TIMEOUT,
            ) as response:
                if response.status != 200:
                    msg = f"Failed to request a device code (HTTP {response.status})"
                    raise AuthError(msg)
                payload = await response.json()
        except _TRANSPORT_ERRORS as err:
            msg = f"Could not reach BetaSeries to request a device code: {err}"
            raise AuthError(msg) from err

        return DeviceCodeData(
            device_code=payload["device_code"],
            user_code=payload["user_code"],
            verification_url=payload["verification_url"],
            expires_in=payload["expires_in"],
            interval=payload["interval"],
        )

    async def poll_for_token(self, device_code: str, expires_in: int, interval: int) -> str:
        """Poll POST /oauth/access_token until the user validates the device code.

        Args:
            device_code (str): Device code obtained from request_device_code.
            expires_in (int): Seconds before the device_code expires.
            interval (int): Minimum seconds to wait between two poll attempts.

        Returns:
            str: The access token once the device code has been validated.

        Raises:
            AuthError: If the device flow fails definitively, or BetaSeries cannot be reached at all.
            AuthTimeoutError: If expires_in elapses before validation.

        """
        deadline = time.monotonic() + expires_in

        while True:
            try:
                async with self._session.post(
                    f"{BASE_URL}{OAUTH_TOKEN_ENDPOINT}",
                    headers=self._headers,
                    data={
                        "client_id": self._api_key,
                        "client_secret": self._client_secret,
                        "code": device_code,
                    },
                    timeout=_TIMEOUT,
                ) as response:
                    if response.status == 200:
                        payload = await response.json()
                        return payload["access_token"]

                    if response.status == 400:
                        payload = await response.json()
                        errors = payload.get("errors", [])
                        if errors and errors[0].get("code") == ERROR_CODE_PENDING:
                            if time.monotonic() >= deadline:
                                msg = "Device code expired before it was validated"
                                raise AuthTimeoutError(msg)
                            await asyncio.sleep(interval)
                            continue

                    msg = f"Failed to obtain an access token (HTTP {response.status})"
                    raise AuthError(msg)
            except _TRANSPORT_ERRORS as err:
                # Deliberately not retried until the deadline, unlike the
                # "pending" case above: a poll that cannot reach BetaSeries at
                # all ends the flow, so the user gets told straight away
                # rather than staring at the code screen for 30 minutes.
                msg = f"Could not reach BetaSeries while polling for an access token: {err}"
                raise AuthError(msg) from err

    async def fetch_member_identity(self, access_token: str) -> MemberIdentity:
        """Fetch the member id and login (GET /members/infos).

        Used solely during initial authentication, once poll_for_token()
        succeeds, before the full Client (and MemberData) is available.

        Args:
            access_token (str): Access token obtained from poll_for_token.

        Returns:
            MemberIdentity: The member id and login.

        Raises:
            AuthError: If the request fails, or BetaSeries cannot be reached at all.

        """
        headers = {**self._headers, "Authorization": f"Bearer {access_token}"}
        try:
            async with self._session.get(
                f"{BASE_URL}{MEMBERS_INFOS_ENDPOINT}",
                headers=headers,
                timeout=_TIMEOUT,
            ) as response:
                if response.status != 200:
                    msg = f"Failed to fetch member identity (HTTP {response.status})"
                    raise AuthError(msg)
                payload = await response.json()
        except _TRANSPORT_ERRORS as err:
            msg = f"Could not reach BetaSeries to fetch the member identity: {err}"
            raise AuthError(msg) from err

        member = payload["member"]
        return MemberIdentity(id=str(member["id"]), login=member["login"])

    async def authenticate_with_password(self, login: str, password: str) -> tuple[str, MemberIdentity]:
        """Authenticate with a BetaSeries login/password (POST /members/auth).

        Alternative to the device flow: a single blocking request instead of
        polling, offered because the device flow can get stuck on some
        Android setups waiting for the browser to hand control back to the
        Home Assistant app. See CLAUDE.md §3 for the trade-off this carries
        (the returned token is never revoked, not even by a password change).
        The response already carries the member identity, so callers don't
        need a follow-up fetch_member_identity() call.

        Args:
            login (str): BetaSeries account login.
            password (str): BetaSeries account password, in cleartext - this method hashes it.

        Returns:
            tuple[str, MemberIdentity]: The access token and the authenticated member's identity.

        Raises:
            AuthError: If the credentials are rejected, or BetaSeries cannot be reached at all.

        """
        try:
            async with self._session.post(
                f"{BASE_URL}{MEMBERS_AUTH_ENDPOINT}",
                headers=self._headers,
                params={"login": login, "password": hashlib.md5(password.encode()).hexdigest()},  # noqa: S324
                timeout=_TIMEOUT,
            ) as response:
                if response.status != 200:
                    msg = f"Failed to authenticate with login/password (HTTP {response.status})"
                    raise AuthError(msg)
                payload = await response.json()
        except _TRANSPORT_ERRORS as err:
            msg = f"Could not reach BetaSeries to authenticate with login/password: {err}"
            raise AuthError(msg) from err

        user = payload["user"]
        return payload["token"], MemberIdentity(id=str(user["id"]), login=user["login"])
