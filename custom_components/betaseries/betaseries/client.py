"""BetaSeries API client for authenticated data endpoints."""

from __future__ import annotations

import contextlib
from datetime import date
import json
from typing import TYPE_CHECKING

from .collection_episode import CollectionEpisode
from .collection_show import CollectionShow
from .const import (
    API_VERSION,
    BASE_URL,
    EPISODES_LIST_ENDPOINT,
    INVALID_CREDENTIALS_ERROR_CODES,
    MEMBERS_INFOS_ENDPOINT,
    PLANNING_MEMBER_ENDPOINT,
    SHOWS_DISPLAY_ENDPOINT,
    SHOWS_EPISODES_ENDPOINT,
)
from .episode import Episode
from .exceptions import AuthError, Error
from .member_data import MemberData
from .member_identity import MemberIdentity
from .member_stats import MemberStats
from .show import Show
from .show_additional_information import ShowAdditionalInformation
from .show_images import ShowImages

if TYPE_CHECKING:
    from collections.abc import Iterable
    from typing import Any

    import aiohttp


class Client:
    """Fetch authenticated BetaSeries member data.

    More endpoints (services) will be added as later milestones (v3) grow
    this client's surface.

    Attributes:
        _session (aiohttp.ClientSession): Injected HTTP session.
        _api_key (str): BetaSeries API key (client_id).
        _access_token (str): OAuth access token obtained via Auth.
        _locale (str): Preferred response language, sent as the "locale" query param.

    """

    def __init__(
        self, session: aiohttp.ClientSession, api_key: str, access_token: str, locale: str = "fr"
    ) -> None:
        """Initialize the client with an injected aiohttp session.

        Args:
            session (aiohttp.ClientSession): Injected HTTP session.
            api_key (str): BetaSeries API key (client_id).
            access_token (str): OAuth access token obtained via Auth.
            locale (str): Preferred response language, sent as the "locale" query param (default "fr").

        """
        self._session = session
        self._api_key = api_key
        self._access_token = access_token
        self._locale = locale

    @staticmethod
    async def _raise_for_error(response: aiohttp.ClientResponse, action: str) -> None:
        """Raise AuthError/Error if the response signals a request failure.

        The raised exception carries the response's status and raw body
        (Error.status/Error.body) so callers can log or otherwise surface
        the exact BetaSeries error themselves - this client has no logging
        of its own, by design (see Error's docstring).

        BetaSeries returns HTTP 401 when the Authorization header itself is
        malformed, but HTTP 400 with `errors[0]["code"]` in
        INVALID_CREDENTIALS_ERROR_CODES for a rejected api_key or access
        token (expired, revoked, ...) - both must surface as AuthError so
        callers can trigger reauthentication.

        Args:
            response (aiohttp.ClientResponse): The response to check.
            action (str): Present-tense description of the request, used in the error message.

        Returns:
            None: Returns normally when the response is a plain HTTP 200.

        Raises:
            AuthError: If the access token was rejected.
            Error: If the request failed for any other reason.

        """
        if response.status == 200:
            return

        body = await response.text()

        if response.status == 401:
            msg = "Access token was rejected"
            raise AuthError(msg, status=response.status, body=body)
        if response.status == 400:
            with contextlib.suppress(ValueError):
                payload: dict[str, Any] = json.loads(body)
                errors: list[dict[str, Any]] = payload.get("errors") or []
                if errors and errors[0].get("code") in INVALID_CREDENTIALS_ERROR_CODES:
                    msg = "Access token was rejected"
                    raise AuthError(msg, status=response.status, body=body)
        msg = f"Failed to {action} (HTTP {response.status})"
        raise Error(msg, status=response.status, body=body)

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

    @property
    def _params(self) -> dict[str, str]:
        """Return the query params required on every BetaSeries request.

        Returns:
            dict[str, str]: Params to send on every request (currently just "locale").

        """
        return {"locale": self._locale}

    async def fetch_member_data(self) -> MemberData:
        """Fetch the member's data and statistics (GET /members/infos).

        Returns:
            MemberData: The member's identity and viewing statistics.

        """
        async with self._session.get(
            f"{BASE_URL}{MEMBERS_INFOS_ENDPOINT}",
            headers=self._headers,
            params=self._params,
        ) as response:
            await self._raise_for_error(response, "fetch member data")
            payload = await response.json()

        member = payload["member"]
        stats = member["stats"]
        return MemberData(
            identity=MemberIdentity(id=str(member["id"]), login=member["login"]),
            stats=MemberStats(
                xp=member["xp"],
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

    async def fetch_planning(self, month: str) -> CollectionEpisode:
        """Fetch the member's episodes for a given month (GET /planning/member).

        Args:
            month (str): Month to fetch the planning for, as "YYYY-MM".

        Returns:
            CollectionEpisode: The member's episodes for that month, in API order.

        """
        async with self._session.get(
            f"{BASE_URL}{PLANNING_MEMBER_ENDPOINT}",
            headers=self._headers,
            params={**self._params, "month": month},
        ) as response:
            await self._raise_for_error(response, "fetch planning")
            payload = await response.json()

        episodes = tuple(self._parse_episode(episode) for episode in payload["episodes"])
        return CollectionEpisode(episodes)

    async def fetch_show_episodes(self, show_id: str) -> CollectionEpisode:
        """Fetch every episode of a single show (GET /shows/episodes).

        Unlike fetch_shows, this only accepts a single show id - no bulk
        (multiple ids) support is documented or verified for this endpoint.

        Args:
            show_id (str): BetaSeries show id to fetch episodes for.

        Returns:
            CollectionEpisode: The show's episodes, in API order.

        """
        async with self._session.get(
            f"{BASE_URL}{SHOWS_EPISODES_ENDPOINT}",
            headers=self._headers,
            params={**self._params, "id": show_id},
        ) as response:
            await self._raise_for_error(response, "fetch show episodes")
            payload = await response.json()

        episodes = tuple(self._parse_episode(episode) for episode in payload["episodes"])
        return CollectionEpisode(episodes)

    async def fetch_episodes_to_watch(self) -> CollectionEpisode:
        """Fetch the member's episodes still to watch, flattened across shows (GET /episodes/list).

        Unlike fetch_planning/fetch_show_episodes, the payload nests episodes
        under each show ("shows": [{"unseen": [...]}, ...]) rather than
        returning them as a flat list - flattened here so callers only ever
        deal with CollectionEpisode. See fetch_episodes_to_watch_by_show() to
        keep the per-show grouping instead.

        Returns:
            CollectionEpisode: The member's unseen episodes, across shows.

        """
        shows = await self._fetch_episodes_to_watch()
        episodes = tuple(self._parse_episode(episode) for show in shows for episode in show["unseen"])
        return CollectionEpisode(episodes)

    async def fetch_episodes_to_watch_by_show(self) -> CollectionShow:
        """Fetch the member's episodes still to watch, grouped by show (GET /episodes/list).

        Same payload/request as fetch_episodes_to_watch(), kept grouped by
        show instead of flattened: each Show comes back with its `episodes`
        already populated.

        Returns:
            CollectionShow: Each show mapped to its unseen episodes.

        """
        shows = await self._fetch_episodes_to_watch()
        return CollectionShow(
            {
                str(show["id"]): Show(
                    id=str(show["id"]),
                    title=show["title"],
                    episodes=CollectionEpisode(tuple(self._parse_episode(episode) for episode in show["unseen"])),
                )
                for show in shows
            }
        )

    async def _fetch_episodes_to_watch(self) -> list[dict[str, Any]]:
        """Fetch the raw show payloads for GET /episodes/list.

        Returns:
            list[dict[str, Any]]: Each show, with its "unseen" episodes list.

        """
        async with self._session.get(
            f"{BASE_URL}{EPISODES_LIST_ENDPOINT}",
            headers=self._headers,
            params=self._params,
        ) as response:
            await self._raise_for_error(response, "fetch episodes to watch")
            payload = await response.json()

        return payload["shows"]

    async def fetch_shows(self, show_ids: Iterable[str]) -> CollectionShow:
        """Fetch shows, with their full additional information (GET /shows/display).

        Accepts any number of ids so callers needing just one (e.g. the next
        episode's show) and callers needing many (e.g. a future carousel) share
        the same method.

        Args:
            show_ids (Iterable[str]): BetaSeries show ids to fetch.

        Returns:
            CollectionShow: Each requested show id mapped to its Show.

        """
        shows = await self._fetch_shows(show_ids)
        return CollectionShow({str(show["id"]): self._parse_show(show) for show in shows})

    async def _fetch_shows(self, show_ids: Iterable[str]) -> list[dict[str, Any]]:
        """Fetch raw show payloads for one or more shows (GET /shows/display).

        The endpoint returns a singular "show" key when a single id is
        requested and a plural "shows" list otherwise; both shapes are
        normalized here so callers never see the difference.

        Args:
            show_ids (Iterable[str]): BetaSeries show ids to fetch.

        Returns:
            list[dict[str, Any]]: One raw show payload per requested id.

        """
        async with self._session.get(
            f"{BASE_URL}{SHOWS_DISPLAY_ENDPOINT}",
            headers=self._headers,
            params={**self._params, "id": ",".join(show_ids)},
        ) as response:
            await self._raise_for_error(response, "fetch shows")
            payload = await response.json()

        return payload["shows"] if "shows" in payload else [payload["show"]]

    @staticmethod
    def _parse_show(show: dict[str, Any]) -> Show:
        """Build a fully-populated Show from a single /shows/display payload entry.

        Args:
            show (dict[str, Any]): One entry of the "shows"/"show" payload.

        Returns:
            Show: The parsed show, with description, slug and additional_information populated.

        """
        return Show(
            id=str(show["id"]),
            title=show["title"],
            description=show.get("description"),
            slug=show.get("slug"),
            additional_information=Client._parse_show_additional_information(show),
        )

    @staticmethod
    def _parse_show_images(images: dict[str, Any]) -> ShowImages:
        """Build a ShowImages from a single show's "images" payload block.

        Args:
            images (dict[str, Any]): The "images" block of a /shows/display entry (may be empty).

        Returns:
            ShowImages: The parsed image URLs, with None for any missing field.

        """
        clearlogo: dict[str, Any] | None = images.get("clearlogo")
        return ShowImages(
            show=images.get("show"),
            banner=images.get("banner"),
            box=images.get("box"),
            poster=images.get("poster"),
            clearlogo=clearlogo.get("url") if clearlogo else None,
        )

    @staticmethod
    def _parse_show_additional_information(show: dict[str, Any]) -> ShowAdditionalInformation:
        """Build a ShowAdditionalInformation from a single /shows/display payload entry.

        Args:
            show (dict[str, Any]): One entry of the "shows"/"show" payload.

        Returns:
            ShowAdditionalInformation: The parsed additional information.

        """
        genres: dict[str, str] = show.get("genres") or {}
        showrunners: list[dict[str, Any]] = show.get("showrunners") or []
        aliases: dict[str, str] = show.get("aliases") or {}
        notes: dict[str, Any] = show.get("notes") or {}
        themoviedb_id = show.get("themoviedb_id")
        return ShowAdditionalInformation(
            original_title=show["original_title"],
            imdb_id=show.get("imdb_id") or None,
            themoviedb_id=str(themoviedb_id) if themoviedb_id else None,
            genres=tuple(genres.values()),
            showrunners=tuple(person["name"] for person in showrunners),
            aliases=tuple(aliases.values()),
            seasons=int(show["seasons"]),
            followers=int(show["followers"]),
            network=show["network"],
            country=show.get("country") or None,
            original_language=show.get("originalLanguage"),
            length=int(show["length"]),
            rating=show["rating"],
            notes_mean=notes.get("mean", 0),
            notes_total=notes.get("total", 0),
            next_trailer=show.get("next_trailer"),
            resource_url=show["resource_url"],
            images=Client._parse_show_images(show.get("images") or {}),
        )

    @staticmethod
    def _parse_episode(episode: dict[str, Any]) -> Episode:
        """Build an Episode from a single /planning/member payload entry.

        Args:
            episode (dict[str, Any]): One entry of the "episodes" payload list.

        Returns:
            Episode: The parsed episode, together with its show.

        """
        show = episode["show"]
        return Episode(
            id=str(episode["id"]),
            season=episode["season"],
            number=episode["episode"],
            code=episode["code"],
            title=episode["title"],
            description=episode["description"],
            air_date=date.fromisoformat(episode["date"]),
            seen=episode["user"]["seen"],
            platforms=tuple(link["platform"] for link in episode["platform_links"]),
            resource_url=episode["resource_url"],
            show=Show(
                id=str(show["id"]),
                title=show["title"],
                description=show.get("description"),
                slug=show.get("slug"),
            ),
        )
