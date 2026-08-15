"""BetaSeries API client for authenticated data endpoints.

Never lets aiohttp's own exceptions escape: a caller of this package should
only ever have to handle Error/AuthError, without knowing which HTTP library
is used underneath (see the sub-package README).
"""

from __future__ import annotations

import contextlib
from datetime import date, datetime
import json
from typing import TYPE_CHECKING

import aiohttp

from .badge import Badge
from .collection_badge import CollectionBadge
from .collection_episode import CollectionEpisode
from .collection_show import CollectionShow
from .collection_timeline_event import CollectionTimelineEvent
from .collection_watch_list_show import CollectionWatchListShow
from .const import (
    API_VERSION,
    BASE_URL,
    EPISODES_DISPLAY_ENDPOINT,
    EPISODES_LIST_ENDPOINT,
    EPISODES_LIST_EXCLUDE_CHARACTERS,
    EPISODES_NOTE_ENDPOINT,
    EPISODES_WATCHED_ENDPOINT,
    ERROR_CODE_NOT_WATCHED,
    INVALID_CREDENTIALS_ERROR_CODES,
    MEMBERS_BADGES_ENDPOINT,
    MEMBERS_DESTROY_ENDPOINT,
    MEMBERS_INFOS_ENDPOINT,
    PLANNING_MEMBER_ENDPOINT,
    REQUEST_TIMEOUT_SECONDS,
    SEASONS_NOTE_ENDPOINT,
    SEASONS_WATCHED_ENDPOINT,
    SHOWS_DISPLAY_ENDPOINT,
    SHOWS_EPISODES_ENDPOINT,
    SHOWS_NOTE_ENDPOINT,
    SHOWS_SEARCH_DEFAULT_LIMIT,
    SHOWS_SEARCH_ENDPOINT,
    SHOWS_SEARCH_ORDER,
    SHOWS_SHOW_ENDPOINT,
    TIMELINE_MEMBER_ENDPOINT,
)
from .episode import Episode
from .episode_watched_event import EpisodeWatchedEvent
from .exceptions import AuthError, Error, NotWatchedError
from .member_data import MemberData
from .member_identity import MemberIdentity
from .member_stats import MemberStats
from .season_watched_event import SeasonWatchedEvent
from .show import Show
from .show_additional_information import ShowAdditionalInformation
from .show_images import ShowImages
from .timeline_event_type import TimelineEventType
from .watch_list_show import WatchListShow

if TYPE_CHECKING:
    from collections.abc import Iterable
    from typing import Any

    from .timeline_event import TimelineEvent

# Transport failures aiohttp raises before any HTTP status exists (DNS, refused
# connection, TLS, read timeout). Wrapped into Error - never AuthError, which
# callers read as "the credentials were rejected" and answer with a
# reauthentication prompt (see coordinator.py); a network blip must not ask the
# user to authenticate again.
_TRANSPORT_ERRORS = (aiohttp.ClientError, TimeoutError)

# Built once: ClientTimeout is immutable, and every request uses the same one.
_TIMEOUT = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)


def _to_int(value: Any, default: int = 0) -> int:
    """Coerce a payload value to an int, falling back when it is missing or malformed.

    BetaSeries returns numeric show fields as strings ("2", "5998"), so a
    plain int() is needed - but a missing key (None) or an unexpected value
    must not raise and fail the whole refresh over one optional detail.

    Args:
        value (Any): The raw payload value to coerce.
        default (int): Value returned when `value` is missing or not numeric.

    Returns:
        int: The coerced integer, or `default`.

    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# The only trailer host verified in practice (see bruno/Shows/display.bru):
# next_trailer is a bare video id, meaningless without knowing which platform
# it belongs to. Other hosts are possible but unconfirmed, so no URL is built
# for them rather than guessing a template.
_YOUTUBE_TRAILER_HOST = "youtube"


def _trailer_url(next_trailer: Any, next_trailer_host: Any) -> str | None:
    """Build a playable trailer URL, only for a confirmed host.

    Args:
        next_trailer (Any): The raw "next_trailer" payload value (a bare video id, or falsy).
        next_trailer_host (Any): The raw "next_trailer_host" payload value.

    Returns:
        str | None: The trailer's URL, or None if there is none or its host is not one this can build a URL for.

    """
    if next_trailer and next_trailer_host == _YOUTUBE_TRAILER_HOST:
        return f"https://www.youtube.com/watch?v={next_trailer}"
    return None


class Client:  # pylint: disable=too-many-public-methods
    """Fetch authenticated BetaSeries member data.

    More endpoints (services) will be added as later milestones (v3) grow
    this client's surface.

    Attributes:
        _session (aiohttp.ClientSession): Injected HTTP session.
        _api_key (str): BetaSeries API key (client_id).
        _access_token (str): OAuth access token obtained via Auth.
        _locale (str): Preferred response language, sent as the "locale" query param.

    """

    def __init__(self, session: aiohttp.ClientSession, api_key: str, access_token: str, locale: str = "fr") -> None:
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
        callers can trigger reauthentication. HTTP 400 with `errors[0]["code"]`
        equal to ERROR_CODE_NOT_WATCHED means the write action's target
        episode/season is not marked as watched - surfaced as NotWatchedError
        so callers can tell this apart from a generic failure (verified via
        Bruno on /episodes/note, /seasons/note and DELETE /episodes/watched).

        Args:
            response (aiohttp.ClientResponse): The response to check.
            action (str): Present-tense description of the request, used in the error message.

        Returns:
            None

        Raises:
            AuthError: If the access token was rejected.
            NotWatchedError: If the target episode/season is not marked as watched.
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
                error_code = errors[0].get("code") if errors else None
                if error_code in INVALID_CREDENTIALS_ERROR_CODES:
                    msg = "Access token was rejected"
                    raise AuthError(msg, status=response.status, body=body)
                if error_code == ERROR_CODE_NOT_WATCHED:
                    msg = "Target is not marked as watched"
                    raise NotWatchedError(msg, status=response.status, body=body)
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

    async def _get(self, endpoint: str, action: str, params: dict[str, str] | None = None) -> Any:
        """Perform an authenticated GET and return the decoded payload.

        Every endpoint this client reads shares this exact shape, so the
        headers, the always-present params, the error check and the transport
        error wrapping all live here rather than being repeated per method.

        Args:
            endpoint (str): Path to request, appended to BASE_URL.
            action (str): Present-tense description of the request, used in error messages.
            params (dict[str, str] | None): Query params for this endpoint, merged over the always-present ones.

        Returns:
            Any: The decoded JSON payload.

        Raises:
            Error: If the request failed, BetaSeries being unreachable included. _raise_for_error() narrows a rejected api_key or access token to the AuthError subclass, which callers answer with a reauthentication.

        """
        try:
            async with self._session.get(
                f"{BASE_URL}{endpoint}",
                headers=self._headers,
                params={**self._params, **(params or {})},
                timeout=_TIMEOUT,
            ) as response:
                # AuthError/Error raised here are this package's own and pass
                # straight through the except below, which only sees aiohttp's.
                await self._raise_for_error(response, action)
                return await response.json()
        except _TRANSPORT_ERRORS as err:
            msg = f"Could not reach BetaSeries to {action}: {err}"
            raise Error(msg) from err

    async def _post(self, endpoint: str, action: str, data: dict[str, str]) -> None:
        """Perform an authenticated POST, raising if it failed.

        Mirrors _get's error handling; the response body is discarded since no
        write action currently needs it back (the caller refreshes the
        relevant coordinator instead - see services.py).

        Args:
            endpoint (str): Path to request, appended to BASE_URL.
            action (str): Present-tense description of the request, used in error messages.
            data (dict[str, str]): Form-urlencoded body fields for this request.

        Returns:
            None

        Raises:
            Error: If the request failed, BetaSeries being unreachable included. _raise_for_error() narrows a rejected api_key/access token to AuthError, and a failed watched-precondition to NotWatchedError.

        """
        try:
            async with self._session.post(
                f"{BASE_URL}{endpoint}",
                headers=self._headers,
                params=self._params,
                data=data,
                timeout=_TIMEOUT,
            ) as response:
                await self._raise_for_error(response, action)
        except _TRANSPORT_ERRORS as err:
            msg = f"Could not reach BetaSeries to {action}: {err}"
            raise Error(msg) from err

    async def _delete(self, endpoint: str, action: str, data: dict[str, str]) -> None:
        """Perform an authenticated DELETE, raising if it failed.

        Mirrors _post; see its docstring for the shared reasoning.

        Args:
            endpoint (str): Path to request, appended to BASE_URL.
            action (str): Present-tense description of the request, used in error messages.
            data (dict[str, str]): Form-urlencoded body fields for this request.

        Returns:
            None

        Raises:
            Error: If the request failed, BetaSeries being unreachable included. _raise_for_error() narrows a rejected api_key/access token to AuthError, and a failed watched-precondition to NotWatchedError.

        """
        try:
            async with self._session.delete(
                f"{BASE_URL}{endpoint}",
                headers=self._headers,
                params=self._params,
                data=data,
                timeout=_TIMEOUT,
            ) as response:
                await self._raise_for_error(response, action)
        except _TRANSPORT_ERRORS as err:
            msg = f"Could not reach BetaSeries to {action}: {err}"
            raise Error(msg) from err

    async def fetch_member_data(self) -> MemberData:
        """Fetch the member's data and statistics (GET /members/infos).

        Returns:
            MemberData: The member's identity and viewing statistics.

        """
        payload = await self._get(MEMBERS_INFOS_ENDPOINT, "fetch member data")

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

    async def fetch_badges(self, member_id: str) -> CollectionBadge:
        """Fetch every badge earned by a member (GET /members/badges).

        Called by MemberCoordinator only when stats.badges (the count from
        fetch_member_data()) changes, rather than on every refresh - this
        client has no state of its own to know when that's the case.

        Args:
            member_id (str): BetaSeries member id to fetch badges for.

        Returns:
            CollectionBadge: The member's earned badges, sorted by date earned (oldest first).

        """
        payload = await self._get(MEMBERS_BADGES_ENDPOINT, "fetch member badges", {"id": member_id})

        badges = (self._parse_badge(badge) for badge in payload["badges"])
        return CollectionBadge(tuple(sorted(badges, key=lambda badge: badge.date)))

    async def fetch_planning(self, month: str) -> CollectionEpisode:
        """Fetch the member's episodes for a given month (GET /planning/member).

        Args:
            month (str): Month to fetch the planning for, as "YYYY-MM".

        Returns:
            CollectionEpisode: The member's episodes for that month, in API order.

        """
        payload = await self._get(PLANNING_MEMBER_ENDPOINT, "fetch planning", {"month": month})

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
        payload = await self._get(SHOWS_EPISODES_ENDPOINT, "fetch show episodes", {"id": show_id})

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
        payload = await self._get(EPISODES_DISPLAY_ENDPOINT, "fetch episodes by id", {"id": ",".join(episode_ids)})

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
        params: dict[str, str] = {"id": member_id}
        if nbpp is not None:
            params["nbpp"] = str(nbpp)
        if since_id is not None:
            params["since_id"] = since_id
        if last_id is not None:
            params["last_id"] = last_id
        if types is not None:
            params["types"] = ",".join(types)

        payload = await self._get(TIMELINE_MEMBER_ENDPOINT, "fetch timeline", params)

        events = (self._parse_timeline_event(event) for event in payload["events"])
        return CollectionTimelineEvent(tuple(event for event in events if event is not None))

    async def fetch_episodes_to_watch(self, *, exclude_characters: bool = False) -> CollectionEpisode:
        """Fetch the member's episodes still to watch, flattened across shows (GET /episodes/list).

        Unlike fetch_planning/fetch_show_episodes, the payload nests episodes
        under each show ("shows": [{"unseen": [...]}, ...]) rather than
        returning them as a flat list - flattened here so callers only ever
        deal with CollectionEpisode. See fetch_episodes_to_watch_by_show() to
        keep the per-show grouping instead.

        Args:
            exclude_characters (bool): Ask the API to leave out each episode's cast, which this client never parses (Optional, defaults to False - the API's own behavior).

        Returns:
            CollectionEpisode: The member's unseen episodes, across shows.

        """
        shows = await self._fetch_episodes_to_watch(exclude_characters=exclude_characters)
        return CollectionEpisode(self._parse_episodes(episode for show in shows for episode in show["unseen"]))

    async def fetch_episodes_to_watch_by_show(self, *, exclude_characters: bool = False) -> CollectionShow:
        """Fetch the member's episodes still to watch, grouped by show (GET /episodes/list).

        Same payload/request as fetch_episodes_to_watch(), kept grouped by
        show instead of flattened: each Show comes back with its `episodes`
        already populated.

        Args:
            exclude_characters (bool): Ask the API to leave out each episode's cast, which this client never parses (Optional, defaults to False - the API's own behavior).

        Returns:
            CollectionShow: Each show mapped to its unseen episodes.

        """
        shows = await self._fetch_episodes_to_watch(exclude_characters=exclude_characters)
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

    async def fetch_watch_list(
        self, shows_limit: int, episodes_limit: int, *, exclude_characters: bool = False
    ) -> tuple[CollectionWatchListShow, int, int]:
        """Fetch the shows still to watch, capped to a few episodes each (GET /episodes/list).

        Unlike fetch_episodes_to_watch(), this keeps each show's `remaining`
        count, and caps the payload through the showsLimit/limit query params.
        Those only truncate the returned shows: the two counters are the
        endpoint's own and stay global (verified - the list may hold 10 shows
        while `total_shows` reports 37), which is why they are returned
        alongside the collection rather than inside it.

        Args:
            shows_limit (int): Maximum number of shows to return (showsLimit).
            episodes_limit (int): Maximum number of episodes per show (limit).
            exclude_characters (bool): Ask the API to leave out each episode's cast, which this client never parses (Optional, defaults to False - the API's own behavior).

        Returns:
            tuple[CollectionWatchListShow, int, int]: The listed shows, the total shows to watch, and the total episodes to watch.

        """
        payload = await self._get(
            EPISODES_LIST_ENDPOINT,
            "fetch watch list",
            {
                "showsLimit": str(shows_limit),
                "limit": str(episodes_limit),
                **self._episodes_list_excludes(exclude_characters=exclude_characters),
            },
        )

        shows = CollectionWatchListShow(tuple(self._parse_watch_list_show(show) for show in payload["shows"]))
        return shows, _to_int(payload.get("total")), _to_int(payload.get("totalEpisodes"))

    @staticmethod
    def _parse_watch_list_show(show: dict[str, Any]) -> WatchListShow:
        """Build a WatchListShow from one entry of the /episodes/list payload.

        The poster is read from the episodes' embedded show object, which is
        where this endpoint carries it - the top-level show entry has no
        images of its own.

        Args:
            show (dict[str, Any]): One entry of the "shows" payload list.

        Returns:
            WatchListShow: The parsed show, with its unseen episodes.

        """
        unseen: list[dict[str, Any]] = show["unseen"]
        embedded: dict[str, Any] = unseen[0]["show"] if unseen else {}
        return WatchListShow(
            id=str(show["id"]),
            title=show["title"],
            remaining=show.get("remaining") or 0,
            poster=embedded.get("poster") or None,
            episodes=CollectionEpisode(Client._parse_episodes(unseen)),
        )

    @staticmethod
    def _episodes_list_excludes(*, exclude_characters: bool) -> dict[str, str]:
        """Build the `excludes` query param of GET /episodes/list, if any.

        Left to the caller rather than always sent: the endpoint's default is
        to include everything, and this client has no business shrinking a
        payload its user may want whole.

        Args:
            exclude_characters (bool): Whether to leave out each episode's cast.

        Returns:
            dict[str, str]: The `excludes` param, or nothing to exclude.

        """
        return {"excludes": EPISODES_LIST_EXCLUDE_CHARACTERS} if exclude_characters else {}

    async def _fetch_episodes_to_watch(self, *, exclude_characters: bool) -> list[dict[str, Any]]:
        """Fetch the raw show payloads for GET /episodes/list.

        Args:
            exclude_characters (bool): Ask the API to leave out each episode's cast.

        Returns:
            list[dict[str, Any]]: Each show, with its "unseen" episodes list.

        """
        payload = await self._get(
            EPISODES_LIST_ENDPOINT,
            "fetch episodes to watch",
            self._episodes_list_excludes(exclude_characters=exclude_characters),
        )

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
        payload = await self._get(SHOWS_DISPLAY_ENDPOINT, "fetch shows", {"id": ",".join(show_ids)})

        return payload["shows"] if "shows" in payload else [payload["show"]]

    async def search_shows(self, title: str, *, limit: int = SHOWS_SEARCH_DEFAULT_LIMIT) -> tuple[Show, ...]:
        """Search the BetaSeries catalog by title (GET /shows/search).

        Returns an ordered tuple rather than a CollectionShow: the API ranks
        results, and that ranking is the point of a search - CollectionShow is
        an id-keyed lookup table with no iteration API, which would lose it.

        The member's own relationship to each result (`in_account`) is only
        filled in because this client always authenticates its requests; the
        endpoint returns it "if a token is provided" (OpenAPI wording).

        Args:
            title (str): The searched title. Sent as-is; the API does the matching.
            limit (int): Maximum number of results to ask for (API caps it at 100).

        Returns:
            tuple[Show, ...]: The matching shows, in the order the API ranked them.

        """
        payload = await self._get(
            SHOWS_SEARCH_ENDPOINT,
            "search shows",
            {"title": title, "nbpp": str(limit), "order": SHOWS_SEARCH_ORDER},
        )

        # Same singular/plural shape as /shows/display (see _fetch_shows), plus
        # a third case that endpoint cannot produce: a search matching nothing.
        if "shows" in payload:
            shows: list[dict[str, Any]] = payload["shows"] or []
        elif "show" in payload:
            shows = [payload["show"]]
        else:
            shows = []

        return tuple(self._parse_show(show) for show in shows)

    async def add_show(self, show_id: str) -> None:
        """Add a show to the member's account (POST /shows/show).

        Args:
            show_id (str): BetaSeries show id to add.

        Returns:
            None

        """
        await self._post(SHOWS_SHOW_ENDPOINT, "add show", {"id": show_id})

    async def mark_episodes_watched(self, episode_ids: Iterable[str]) -> None:
        """Mark one or more episodes as watched (POST /episodes/watched).

        Accepts any number of ids in a single request, same bulk pattern as
        fetch_episodes_by_id (verified via Bruno, bruno/Episodes/watched.bru).

        Args:
            episode_ids (Iterable[str]): BetaSeries episode ids to mark as watched.

        Returns:
            None

        """
        await self._post(EPISODES_WATCHED_ENDPOINT, "mark episodes watched", {"id": ",".join(episode_ids)})

    async def mark_episodes_unwatched(self, episode_ids: Iterable[str]) -> None:
        """Remove the watched mark from one or more episodes (DELETE /episodes/watched).

        Raises NotWatchedError (via _delete/_raise_for_error) if an episode
        targeted was not marked as watched (verified via Bruno,
        bruno/Episodes/unwatched.bru).

        Args:
            episode_ids (Iterable[str]): BetaSeries episode ids to mark as unwatched.

        Returns:
            None

        """
        await self._delete(EPISODES_WATCHED_ENDPOINT, "mark episodes unwatched", {"id": ",".join(episode_ids)})

    async def rate_episodes(self, episode_ids: Iterable[str], note: int) -> None:
        """Rate one or more episodes (POST /episodes/note).

        Raises NotWatchedError (via _post/_raise_for_error) if an episode
        targeted is not marked as watched - rating requires it to be
        (verified via Bruno, bruno/Episodes/note.bru).

        Args:
            episode_ids (Iterable[str]): BetaSeries episode ids to rate.
            note (int): Rating from 1 to 5.

        Returns:
            None

        """
        await self._post(EPISODES_NOTE_ENDPOINT, "rate episodes", {"id": ",".join(episode_ids), "note": str(note)})

    async def unrate_episodes(self, episode_ids: Iterable[str]) -> None:
        """Remove the rating from one or more episodes (DELETE /episodes/note).

        Args:
            episode_ids (Iterable[str]): BetaSeries episode ids to unrate.

        Returns:
            None

        """
        await self._delete(EPISODES_NOTE_ENDPOINT, "unrate episodes", {"id": ",".join(episode_ids)})

    async def mark_season_watched(self, show_id: str, season: int) -> None:
        """Mark every episode of a season as watched (POST /seasons/watched).

        Args:
            show_id (str): BetaSeries show id.
            season (int): Season number.

        Returns:
            None

        """
        await self._post(SEASONS_WATCHED_ENDPOINT, "mark season watched", {"id": show_id, "season": str(season)})

    async def mark_season_unwatched(self, show_id: str, season: int) -> None:
        """Remove the watched mark from every episode of a season (DELETE /seasons/watched).

        Args:
            show_id (str): BetaSeries show id.
            season (int): Season number.

        Returns:
            None

        """
        await self._delete(SEASONS_WATCHED_ENDPOINT, "mark season unwatched", {"id": show_id, "season": str(season)})

    async def rate_season(self, show_id: str, season: int, note: int) -> None:
        """Rate a season (POST /seasons/note).

        A separate action from mark_season_watched, not one of its
        parameters (verified via Bruno, bruno/Seasons/note.bru) - rating
        requires the season to already be fully watched, raising
        NotWatchedError (via _post/_raise_for_error) otherwise.

        Args:
            show_id (str): BetaSeries show id.
            season (int): Season number.
            note (int): Rating from 1 to 5.

        Returns:
            None

        """
        await self._post(
            SEASONS_NOTE_ENDPOINT, "rate season", {"id": show_id, "season": str(season), "note": str(note)}
        )

    async def unrate_season(self, show_id: str, season: int) -> None:
        """Remove a season's rating (DELETE /seasons/note).

        No note/rate field needed in the body (verified via Bruno,
        bruno/Seasons/unnote.bru).

        Args:
            show_id (str): BetaSeries show id.
            season (int): Season number.

        Returns:
            None

        """
        await self._delete(SEASONS_NOTE_ENDPOINT, "unrate season", {"id": show_id, "season": str(season)})

    async def rate_show(self, show_id: str, note: int) -> None:
        """Rate a show (POST /shows/note).

        Args:
            show_id (str): BetaSeries show id.
            note (int): Rating from 1 to 5.

        Returns:
            None

        """
        await self._post(SHOWS_NOTE_ENDPOINT, "rate show", {"id": show_id, "note": str(note)})

    async def unrate_show(self, show_id: str) -> None:
        """Remove a show's rating (DELETE /shows/note).

        Args:
            show_id (str): BetaSeries show id.

        Returns:
            None

        """
        await self._delete(SHOWS_NOTE_ENDPOINT, "unrate show", {"id": show_id})

    async def delete_token(self) -> None:
        """Destroy the active access token (POST /members/destroy).

        Returns:
            None

        """
        await self._post(MEMBERS_DESTROY_ENDPOINT, "delete token", {})

    @staticmethod
    def _parse_badge(badge: dict[str, Any]) -> Badge:
        """Build a Badge from a single /members/badges payload entry.

        Args:
            badge (dict[str, Any]): One entry of the "badges" payload list.

        Returns:
            Badge: The parsed badge.

        """
        return Badge(
            id=str(badge["id"]),
            code=badge["code"],
            name=badge["name"],
            description=badge["description"],
            date=datetime.strptime(badge["date"], "%Y-%m-%d %H:%M:%S"),  # noqa: DTZ007 (API doesn't return a timezone)
            height=badge.get("height"),
            width=badge.get("width"),
            level=badge.get("level"),
        )

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

        Every field is read with .get() and a fallback: this endpoint returns
        by far the richest and most variable payload of the ones this client
        consumes, and a single missing key would otherwise raise a bare
        KeyError that fails the whole refresh rather than degrading one show's
        optional details. Fallbacks match each field's declared type, so
        callers never see a None where the model promises a value.

        Every field uses `.get(key) or <fallback>` rather than
        `.get(key, <fallback>)`: the two-argument form only covers a *missing*
        key, and this endpoint routinely sends the key with a null/empty value
        instead of omitting it (verified: empty imdb_id, zero themoviedb_id,
        null picture). The `or` form normalizes both cases to the fallback.

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
        # "platforms" carries several buckets (svods, svod, vod...); only the
        # SVOD list is read, and each entry is an object rather than a name.
        platforms: dict[str, Any] = show.get("platforms") or {}
        svods: list[dict[str, Any]] = platforms.get("svods") or []
        return ShowAdditionalInformation(
            original_title=show.get("original_title") or "",
            imdb_id=show.get("imdb_id") or None,
            themoviedb_id=str(themoviedb_id) if themoviedb_id else None,
            genres=tuple(genres.values()),
            showrunners=tuple(person["name"] for person in showrunners if person.get("name")),
            aliases=tuple(aliases.values()),
            # Numeric fields come back as strings ("2", "5998"), hence the int().
            seasons=_to_int(show.get("seasons")),
            followers=_to_int(show.get("followers")),
            network=show.get("network") or "",
            country=show.get("country") or None,
            original_language=show.get("originalLanguage"),
            length=_to_int(show.get("length")),
            rating=show.get("rating") or "",
            notes_mean=notes.get("mean") or 0,
            notes_total=notes.get("total") or 0,
            trailer_url=_trailer_url(show.get("next_trailer"), show.get("next_trailer_host")),
            resource_url=show.get("resource_url") or "",
            images=Client._parse_show_images(show.get("images") or {}),
            creation=str(show["creation"]) if show.get("creation") else None,
            broadcast_status=show.get("status") or None,
            platforms=tuple(svod["name"] for svod in svods if svod.get("name")),
            in_account=bool(show.get("in_account")),
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
