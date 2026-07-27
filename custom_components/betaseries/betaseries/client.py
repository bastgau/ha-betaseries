"""BetaSeries API client for authenticated data endpoints."""

from __future__ import annotations

import contextlib
from datetime import date, datetime
import json
from typing import TYPE_CHECKING

from .collection_episode import CollectionEpisode
from .collection_show import CollectionShow
from .collection_timeline_event import CollectionTimelineEvent
from .const import (
    API_VERSION,
    BASE_URL,
    EPISODES_DISPLAY_ENDPOINT,
    EPISODES_LIST_ENDPOINT,
    INVALID_CREDENTIALS_ERROR_CODES,
    MEMBERS_INFOS_ENDPOINT,
    PLANNING_MEMBER_ENDPOINT,
    SHOWS_DISPLAY_ENDPOINT,
    SHOWS_EPISODES_ENDPOINT,
    TIMELINE_MEMBER_ENDPOINT,
)
from .episode import Episode
from .episode_watched_event import EpisodeWatchedEvent
from .exceptions import AuthError, Error
from .member_data import MemberData
from .member_identity import MemberIdentity
from .member_stats import MemberStats
from .season_watched_event import SeasonWatchedEvent
from .show import Show
from .show_additional_information import ShowAdditionalInformation
from .show_images import ShowImages
from .timeline_event_type import TimelineEventType

if TYPE_CHECKING:
    from collections.abc import Iterable
    from typing import Any

    import aiohttp

    from .timeline_event import TimelineEvent


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

        return CollectionEpisode(self._parse_episodes(payload["episodes"]))

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

        return CollectionEpisode(self._parse_episodes(payload["episodes"]))

    async def fetch_episodes_by_id(self, episode_ids: Iterable[str]) -> CollectionEpisode:
        """Fetch one or more episodes by id (GET /episodes/display).

        Accepts any number of ids in a single request (bulk, like
        fetch_shows) - unlike fetch_show_episodes, which only accepts a
        single show id.

        Args:
            episode_ids (Iterable[str]): BetaSeries episode ids to fetch.

        Returns:
            CollectionEpisode: The requested episodes, each with its show.

        """
        async with self._session.get(
            f"{BASE_URL}{EPISODES_DISPLAY_ENDPOINT}",
            headers=self._headers,
            params={**self._params, "id": ",".join(episode_ids)},
        ) as response:
            await self._raise_for_error(response, "fetch episodes by id")
            payload = await response.json()

        return CollectionEpisode(self._parse_episodes(payload["episodes"]))

    async def fetch_timeline(
        self,
        member_id: str,
        *,
        nbpp: int | None = None,
        since_id: str | None = None,
        last_id: str | None = None,
        types: Iterable[TimelineEventType] | None = None,
    ) -> CollectionTimelineEvent:
        """Fetch a member's timeline events (GET /timeline/member).

        Only EpisodeWatchedEvent/SeasonWatchedEvent are currently modeled
        (see timeline_event.py); events of any other type - whether a known
        TimelineEventType without a dedicated subclass yet, or a value this
        client doesn't recognize at all (the API doesn't document an
        exhaustive enum for this field, see
        docs/watch-history-calendar-exploration.md) - are silently dropped
        rather than failing the whole fetch.

        Args:
            member_id (str): BetaSeries member id to fetch the timeline for.
            nbpp (int | None): Number of events per page, maximum 100 (Optional).
            since_id (str | None): Return events older than this event id (Optional).
            last_id (str | None): Return events newer than this event id (Optional).
            types (Iterable[TimelineEventType] | None): Only return events of these types (Optional).

        Returns:
            CollectionTimelineEvent: The member's modeled timeline events, in API order (newest first).

        """
        params: dict[str, str] = {**self._params, "id": member_id}
        if nbpp is not None:
            params["nbpp"] = str(nbpp)
        if since_id is not None:
            params["since_id"] = since_id
        if last_id is not None:
            params["last_id"] = last_id
        if types is not None:
            params["types"] = ",".join(types)

        async with self._session.get(
            f"{BASE_URL}{TIMELINE_MEMBER_ENDPOINT}",
            headers=self._headers,
            params=params,
        ) as response:
            await self._raise_for_error(response, "fetch timeline")
            payload = await response.json()

        events = (self._parse_timeline_event(event) for event in payload["events"])
        return CollectionTimelineEvent(tuple(event for event in events if event is not None))

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
        return CollectionEpisode(self._parse_episodes(episode for show in shows for episode in show["unseen"]))

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
                    episodes=CollectionEpisode(self._parse_episodes(show["unseen"])),
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
    def _parse_timeline_event(event: dict[str, Any]) -> TimelineEvent | None:
        """Build a TimelineEvent from a single /timeline/member payload entry.

        Only EPISODE_WATCHED/SEASON_WATCHED get a subclass instance; any
        other type - known but not yet modeled, or entirely unrecognized -
        returns None (see fetch_timeline's docstring). A SEASON_WATCHED
        event whose "ref" doesn't match the verified "{show_id}.{season}"
        format also returns None, rather than raising and failing the
        whole fetch over one malformed entry.

        Args:
            event (dict[str, Any]): One entry of the "events" payload list.

        Returns:
            TimelineEvent | None: The parsed event, or None if this event type isn't modeled.

        """
        try:
            event_type = TimelineEventType(event["type"])
        except ValueError:
            return None

        event_id = str(event["id"])
        event_date = datetime.strptime(event["date"], "%Y-%m-%d %H:%M:%S")  # noqa: DTZ007 (API doesn't return a timezone)

        if event_type is TimelineEventType.EPISODE_WATCHED:
            return EpisodeWatchedEvent(id=event_id, date=event_date, episode_id=str(event["ref_id"]))
        if event_type is TimelineEventType.SEASON_WATCHED:
            try:
                show_id, season = event["ref"].split(".")
                return SeasonWatchedEvent(id=event_id, date=event_date, show_id=show_id, season=int(season))
            except ValueError:
                return None
        return None

    @staticmethod
    def _parse_episodes(episodes: Iterable[dict[str, Any]]) -> tuple[Episode, ...]:
        """Build Episodes from a list of /planning/member-shaped payload entries.

        Episodes referencing the same show (by id) share a single Show
        instance instead of each rebuilding their own equal-but-distinct
        copy - relevant when many episodes of the same show appear in one
        response (e.g. fetch_episodes_by_id with several episode ids from
        the same show).

        Args:
            episodes (Iterable[dict[str, Any]]): Entries of an "episodes" payload list.

        Returns:
            tuple[Episode, ...]: The parsed episodes, in payload order.

        """
        shows_by_id: dict[str, Show] = {}
        return tuple(Client._parse_episode(episode, shows_by_id) for episode in episodes)

    @staticmethod
    def _parse_episode(episode: dict[str, Any], shows_by_id: dict[str, Show]) -> Episode:
        """Build an Episode from a single /planning/member payload entry.

        Args:
            episode (dict[str, Any]): One entry of the "episodes" payload list.
            shows_by_id (dict[str, Show]): Cache of Show instances shared across a batch (see _parse_episodes).

        Returns:
            Episode: The parsed episode, together with its show.

        """
        show_payload = episode["show"]
        show_id = str(show_payload["id"])

        show = shows_by_id.get(show_id)
        if show is None:
            show = Show(
                id=show_id,
                title=show_payload["title"],
                description=show_payload.get("description"),
                slug=show_payload.get("slug"),
            )
            shows_by_id[show_id] = show

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
            show=show,
        )
