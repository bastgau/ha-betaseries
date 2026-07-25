"""OAuth device flow client for the BetaSeries API."""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from .const import (
    API_VERSION,
    BASE_URL,
    ERROR_CODE_PENDING,
    MEMBERS_INFOS_ENDPOINT,
    OAUTH_DEVICE_ENDPOINT,
    OAUTH_TOKEN_ENDPOINT,
)
from .device_code import DeviceCodeData
from .exceptions import AuthError, AuthTimeoutError
from .member_identity import MemberIdentity

if TYPE_CHECKING:
    import aiohttp


class Auth:
    """Handle the BetaSeries OAuth device flow.

    See CLAUDE.md §3 for the verified endpoint contract. Unlike the Tado
    integration (whose PyTado library polls internally and is synchronous),
    this client is built directly on aiohttp: polling is native async, and
    the expires_in guard rail has no library to rely on, so it is
    implemented here.

    Attributes:
        _session (aiohttp.ClientSession): Injected HTTP session.
        _api_key (str): BetaSeries API key (client_id).
        _client_secret (str): BetaSeries API client secret.

    """

    def __init__(self, session: aiohttp.ClientSession, api_key: str, client_secret: str) -> None:
        """Initialize the auth client with an injected aiohttp session.

        Args:
            session (aiohttp.ClientSession): Injected HTTP session.
            api_key (str): BetaSeries API key (client_id).
            client_secret (str): BetaSeries API client secret.

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
            AuthError: If the request fails.

        """
        async with self._session.post(
            f"{BASE_URL}{OAUTH_DEVICE_ENDPOINT}",
            headers=self._headers,
            data={"client_id": self._api_key},
        ) as response:
            if response.status != 200:
                msg = f"Failed to request a device code (HTTP {response.status})"
                raise AuthError(msg)
            payload = await response.json()

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
            AuthError: If the device flow fails definitively.
            AuthTimeoutError: If expires_in elapses before validation.

        """
        deadline = time.monotonic() + expires_in

        while True:
            async with self._session.post(
                f"{BASE_URL}{OAUTH_TOKEN_ENDPOINT}",
                headers=self._headers,
                data={
                    "client_id": self._api_key,
                    "client_secret": self._client_secret,
                    "code": device_code,
                },
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

    async def fetch_member_identity(self, access_token: str) -> MemberIdentity:
        """Fetch the member id and login (GET /members/infos, id/login only).

        Used solely to close the config flow.

        Args:
            access_token (str): Access token obtained from poll_for_token.

        Returns:
            MemberIdentity: The member id and login.

        Raises:
            AuthError: If the request fails.

        """
        headers = {**self._headers, "Authorization": f"Bearer {access_token}"}
        async with self._session.get(
            f"{BASE_URL}{MEMBERS_INFOS_ENDPOINT}",
            headers=headers,
            params={"fields": "id,login"},
        ) as response:
            if response.status != 200:
                msg = f"Failed to fetch member identity (HTTP {response.status})"
                raise AuthError(msg)
            payload = await response.json()

        member = payload["member"]
        return MemberIdentity(id=str(member["id"]), login=member["login"])
