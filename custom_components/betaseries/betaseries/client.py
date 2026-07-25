"""BetaSeries API client for authenticated data endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .const import API_VERSION, BASE_URL, MEMBER_DATA_FIELDS, MEMBERS_INFOS_ENDPOINT
from .exceptions import Error
from .member_data import MemberData
from .member_stats import MemberStats

if TYPE_CHECKING:
    import aiohttp


class Client:  # pylint: disable=too-few-public-methods
    """Fetch authenticated BetaSeries member data.

    More endpoints (planning, services) will be added as later milestones
    (v2/v3) grow this client's surface.

    Attributes:
        _session (aiohttp.ClientSession): Injected HTTP session.
        _api_key (str): BetaSeries API key (client_id).
        _access_token (str): OAuth access token obtained via Auth.

    """

    def __init__(self, session: aiohttp.ClientSession, api_key: str, access_token: str) -> None:
        """Initialize the client with an injected aiohttp session.

        Args:
            session (aiohttp.ClientSession): Injected HTTP session.
            api_key (str): BetaSeries API key (client_id).
            access_token (str): OAuth access token obtained via Auth.

        """
        self._session = session
        self._api_key = api_key
        self._access_token = access_token

    @property
    def _headers(self) -> dict[str, str]:
        """Return the headers required on every authenticated BetaSeries request.

        Returns:
            dict[str, str]: Headers to send on every request.

        """
        return {
            "X-BetaSeries-Key": self._api_key,
            "X-BetaSeries-Version": API_VERSION,
            "Authorization": f"Bearer {self._access_token}",
        }

    async def fetch_member_data(self) -> MemberData:
        """Fetch the member's data and statistics (GET /members/infos).

        Returns:
            MemberData: The member's id, login, xp and viewing statistics.

        Raises:
            Error: If the request fails.

        """
        async with self._session.get(
            f"{BASE_URL}{MEMBERS_INFOS_ENDPOINT}",
            headers=self._headers,
            params={"fields": MEMBER_DATA_FIELDS},
        ) as response:
            if response.status != 200:
                msg = f"Failed to fetch member data (HTTP {response.status})"
                raise Error(msg)
            payload = await response.json()

        member = payload["member"]
        stats = member["stats"]
        return MemberData(
            id=str(member["id"]),
            login=member["login"],
            xp=member["xp"],
            stats=MemberStats(
                episodes_to_watch=stats["episodes_to_watch"],
                time_to_spend=stats["time_to_spend"],
                progress=stats["progress"],
                shows_to_watch=stats["shows_to_watch"],
                movies_to_watch=stats["movies_to_watch"],
                shows_current=stats["shows_current"],
                badges=stats["badges"],
                shows=stats["shows"],
                shows_finished=stats["shows_finished"],
                episodes=stats["episodes"],
                time_on_tv=stats["time_on_tv"],
                movies=stats["movies"],
                streak_days=stats["streak_days"],
                member_since_days=stats["member_since_days"],
                episodes_per_month=stats["episodes_per_month"],
                favorite_genre=stats["favorite_genre"],
            ),
        )
